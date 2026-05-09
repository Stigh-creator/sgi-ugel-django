from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from ..models import CustomUser, Incidencia
from inventario.models import Equipo
from ..utils.exports import generate_pdf, generate_excel_inventario
from auditoria.utils import registrar_auditoria


def can_export_inventory(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.role in {CustomUser.ROL_ADMIN, CustomUser.ROL_ALMACEN}
    )


def can_view_incidencia(user, incidencia):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.role == CustomUser.ROL_ADMIN:
        return True
    if user.role == CustomUser.ROL_TECNICO:
        return incidencia.tecnico_asignado_id == user.id or incidencia.creador_id == user.id
    return incidencia.creador_id == user.id


def incidencias_exportables_para(user):
    queryset = Incidencia.objects.select_related("creador", "area", "estado", "tecnico_asignado")
    if user.is_superuser or user.role == CustomUser.ROL_ADMIN:
        return queryset
    if user.role == CustomUser.ROL_TECNICO:
        return queryset.filter(Q(tecnico_asignado=user) | Q(creador=user))
    return queryset.filter(creador=user)


def nombre_usuario(user):
    return user.get_full_name() or user.username


@login_required
@user_passes_test(can_export_inventory)
def export_inventario_excel(request):
    """
    Exporta el inventario completo a Excel.
    """
    equipos = Equipo.objects.select_related('tipo_equipo', 'marca', 'area').all()
    excel_file = generate_excel_inventario(equipos)
    
    filename = f"inventario_{timezone.now().strftime('%Y%m%d')}.xlsx"
    return FileResponse(excel_file, as_attachment=True, filename=filename)

@login_required
def export_ticket_pdf(request, pk):
    """
    Genera el PDF de un ticket individual.
    """
    incidencia = get_object_or_404(
        Incidencia.objects.select_related(
            "creador",
            "area",
            "estado",
            "tecnico_asignado",
            "equipo",
            "equipo_reemplazo",
        ).prefetch_related("imagenes", "comentarios__usuario"),
        pk=pk,
    )
    if not can_view_incidencia(request.user, incidencia):
        raise PermissionDenied("No tiene permiso para descargar este reporte.")

    generado_en = timezone.localtime(timezone.now())
    evidencias_apertura = []
    if incidencia.imagen_adjunta:
        evidencias_apertura.append({
            "url": incidencia.imagen_adjunta.url,
            "caption": "Evidencia principal registrada por el solicitante",
        })
    evidencias_apertura.extend(
        {
            "url": img.imagen.url,
            "caption": f"Evidencia adicional {index}",
        }
        for index, img in enumerate(incidencia.imagenes.all(), start=1)
        if img.imagen
    )
    evidencias_solucion = [
        {"url": field.url, "caption": caption}
        for field, caption in [
            (incidencia.evidencia_solucion, "Evidencia de solución 1"),
            (incidencia.evidencia_solucion_2, "Evidencia de solución 2"),
            (incidencia.evidencia_solucion_3, "Evidencia de solución 3"),
        ]
        if field
    ]
    evidencias_seguimiento = [
        {
            "url": comentario.evidencia_adjunta.url,
            "caption": (
                f"Comentario de {nombre_usuario(comentario.usuario)} - "
                f"{timezone.localtime(comentario.fecha_creacion).strftime('%d/%m/%Y %H:%M')}"
            ),
            "texto": comentario.texto,
        }
        for comentario in incidencia.comentarios.all()
        if comentario.evidencia_adjunta
    ]
    context = {
        'incidencia': incidencia,
        'generado_por': request.user,
        'generado_por_nombre': nombre_usuario(request.user),
        'generado_en': generado_en,
        'evidencias_apertura': evidencias_apertura,
        'evidencias_solucion': evidencias_solucion,
        'evidencias_seguimiento': evidencias_seguimiento,
    }
    pdf_file = generate_pdf('tickets/exports/ticket_incidencia.html', context)
    
    if pdf_file:
        filename = f"ticket_{incidencia.codigo}.pdf"
        registrar_auditoria(
            request,
            "Incidencias",
            "descargó PDF de incidencia",
            f"El usuario {nombre_usuario(request.user)} descargó el PDF de la incidencia {incidencia.codigo}.",
            incidencia.id,
        )
        return FileResponse(pdf_file, content_type='application/pdf', filename=filename)
    raise Http404("Error al generar el PDF")

@login_required
def export_reporte_incidencias_pdf(request):
    """
    Genera un reporte de incidencias filtrado por fecha.
    Query params: start_date, end_date (formato YYYY-MM-DD)
    """
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    incidencias = incidencias_exportables_para(request.user)
    
    if start_date_str:
        start_date = parse_date(start_date_str)
        incidencias = incidencias.filter(fecha_creacion__date__gte=start_date)
    else:
        start_date = incidencias.order_by('fecha_creacion').first().fecha_creacion if incidencias.exists() else timezone.now()

    if end_date_str:
        end_date = parse_date(end_date_str)
        incidencias = incidencias.filter(fecha_creacion__date__lte=end_date)
    else:
        end_date = timezone.now()

    context = {
        'incidencias': incidencias,
        'fecha_inicio': start_date,
        'fecha_fin': end_date,
        'hoy': timezone.now(),
        'generado_por': request.user,
        'generado_por_nombre': nombre_usuario(request.user),
        'generado_en': timezone.localtime(timezone.now()),
    }
    
    pdf_file = generate_pdf('tickets/exports/reporte_incidencias.html', context)
    if pdf_file:
        filename = f"reporte_incidencias_{timezone.now().strftime('%Y%m%d')}.pdf"
        registrar_auditoria(
            request,
            "Incidencias",
            "descargó reporte PDF de incidencias",
            (
                f"El usuario {nombre_usuario(request.user)} descargó un reporte PDF de incidencias "
                f"del {start_date} al {end_date}."
            ),
            None,
        )
        return FileResponse(pdf_file, content_type='application/pdf', filename=filename)
    raise Http404("Error al generar el PDF del reporte")
