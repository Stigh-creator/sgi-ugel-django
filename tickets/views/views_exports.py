from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q

from ..models import Area, CustomUser, Estado, EstadoSLA, Incidencia
from inventario.models import Equipo, EstadoEquipo, Marca, TipoEquipo
from ..utils.exports import generate_pdf, generate_excel_inventario
from auditoria.utils import registrar_auditoria


def can_export_inventory(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.role == CustomUser.ROL_ALMACEN
    )


def can_view_inventory_reports(user):
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


def build_bar_rows(items, *, label_key="name", value_key="total"):
    max_value = max([item[value_key] for item in items], default=0) or 1
    rows = []
    for item in items:
        total = item[value_key]
        rows.append({
            "label": item[label_key] or "Sin dato",
            "total": total,
            "width": max(3, int((total / max_value) * 100)) if total else 0,
        })
        rows[-1]["width_class"] = f"bar-width-{min(100, max(0, round(rows[-1]['width'] / 5) * 5))}"
    return rows


def dashboard_filters(request):
    return {
        "start_date": parse_date(request.GET.get("start_date") or ""),
        "end_date": parse_date(request.GET.get("end_date") or ""),
        "tecnico_id": request.GET.get("tecnico") or "",
        "estado_id": request.GET.get("estado") or "",
        "prioridad": request.GET.get("prioridad") or "",
        "area_id": request.GET.get("area") or "",
    }


def filtered_dashboard_queryset(request):
    filters = dashboard_filters(request)
    queryset = Incidencia.objects.select_related("creador", "area", "estado", "tecnico_asignado")

    if filters["start_date"]:
        queryset = queryset.filter(fecha_creacion__date__gte=filters["start_date"])
    if filters["end_date"]:
        queryset = queryset.filter(fecha_creacion__date__lte=filters["end_date"])
    if filters["tecnico_id"].isdigit():
        queryset = queryset.filter(tecnico_asignado_id=filters["tecnico_id"])
    if filters["estado_id"].isdigit():
        queryset = queryset.filter(estado_id=filters["estado_id"])
    if filters["prioridad"]:
        queryset = queryset.filter(prioridad=filters["prioridad"])
    if filters["area_id"].isdigit():
        queryset = queryset.filter(area_id=filters["area_id"])

    return queryset, filters


def inventory_dashboard_filters(request):
    return {
        "start_date": parse_date(request.GET.get("start_date") or ""),
        "end_date": parse_date(request.GET.get("end_date") or ""),
        "area_id": request.GET.get("area") or "",
        "tipo_id": request.GET.get("tipo") or "",
        "marca_id": request.GET.get("marca") or "",
        "estado_id": request.GET.get("estado") or "",
    }


def filtered_inventory_queryset(request):
    filters = inventory_dashboard_filters(request)
    queryset = Equipo.objects.select_related("area", "tipo_equipo", "marca", "estado_tecnico")

    if filters["start_date"]:
        queryset = queryset.filter(fecha_register__date__gte=filters["start_date"])
    if filters["end_date"]:
        queryset = queryset.filter(fecha_register__date__lte=filters["end_date"])
    if filters["area_id"].isdigit():
        queryset = queryset.filter(area_id=filters["area_id"])
    if filters["tipo_id"].isdigit():
        queryset = queryset.filter(tipo_equipo_id=filters["tipo_id"])
    if filters["marca_id"].isdigit():
        queryset = queryset.filter(marca_id=filters["marca_id"])
    if filters["estado_id"].isdigit():
        queryset = queryset.filter(estado_tecnico_id=filters["estado_id"])

    return queryset, filters


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


@login_required
@user_passes_test(lambda user: user.is_superuser or user.role == CustomUser.ROL_ADMIN)
def export_dashboard_incidencias_pdf(request):
    queryset, filters = filtered_dashboard_queryset(request)
    hoy = timezone.localdate()
    queryset_list = list(queryset.order_by("-fecha_creacion")[:20])

    criticas = queryset.filter(
        Q(prioridad=Incidencia.PRIORIDAD_ALTA) | Q(prioridad=Incidencia.PRIORIDAD_CRITICA)
    ).exclude(estado__name__in=[Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO]).count()
    pendientes_activas = queryset.filter(
        estado__name__in=[
            Incidencia.ESTADO_PENDIENTE,
            Incidencia.ESTADO_ASIGNADO,
            Incidencia.ESTADO_EN_PROCESO,
            Incidencia.ESTADO_RECHAZADO,
            Incidencia.ESTADO_REABIERTO,
        ]
    ).count()
    resueltas = queryset.filter(estado__name=Incidencia.ESTADO_RESUELTO).count()
    cerradas = queryset.filter(estado__name=Incidencia.ESTADO_CERRADO).count()
    registradas_hoy = queryset.filter(fecha_creacion__date=hoy).count()
    sin_asignar = queryset.filter(tecnico_asignado__isnull=True, estado__name=Incidencia.ESTADO_PENDIENTE).count()
    sla_vencidas = queryset.filter(
        estado_sla__in=[EstadoSLA.RESPUESTA_VENCIDA, EstadoSLA.RESOLUCION_VENCIDA]
    ).exclude(estado__name=Incidencia.ESTADO_CERRADO).count()

    estado_items = list(
        queryset.values(name=F("estado__name")).annotate(total=Count("id")).order_by("-total", "estado__name")
    )
    prioridad_labels = dict(Incidencia.PRIORIDAD_CHOICES)
    prioridad_items = [
        {
            "name": prioridad_labels.get(item["prioridad"], item["prioridad"] or "Sin prioridad"),
            "total": item["total"],
        }
        for item in queryset.values("prioridad").annotate(total=Count("id")).order_by("-total", "prioridad")
    ]
    tecnico_items = list(
        queryset.values(name=F("tecnico_asignado__first_name"))
        .annotate(total=Count("id"))
        .order_by("-total", "tecnico_asignado__first_name")[:8]
    )
    area_items = list(
        queryset.values(name=F("area__name")).annotate(total=Count("id")).order_by("-total", "area__name")[:8]
    )

    tecnico_label = "Todos"
    if filters["tecnico_id"].isdigit():
        tecnico = CustomUser.objects.filter(pk=filters["tecnico_id"]).first()
        tecnico_label = nombre_usuario(tecnico) if tecnico else "No encontrado"
    estado_label = "Todos"
    if filters["estado_id"].isdigit():
        estado = Estado.objects.filter(pk=filters["estado_id"]).first()
        estado_label = estado.name if estado else "No encontrado"
    area_label = "Todas"
    if filters["area_id"].isdigit():
        area = Area.objects.filter(pk=filters["area_id"]).first()
        area_label = area.name if area else "No encontrada"

    context = {
        "kpis": {
            "total": queryset.count(),
            "criticas": criticas,
            "pendientes_activas": pendientes_activas,
            "resueltas": resueltas,
            "cerradas": cerradas,
            "registradas_hoy": registradas_hoy,
            "sin_asignar": sin_asignar,
            "sla_vencidas": sla_vencidas,
        },
        "filters": filters,
        "filter_labels": {
            "fecha_inicio": filters["start_date"] or "Sin inicio",
            "fecha_fin": filters["end_date"] or "Sin fin",
            "tecnico": tecnico_label,
            "estado": estado_label,
            "prioridad": prioridad_labels.get(filters["prioridad"], "Todas"),
            "area": area_label,
        },
        "estado_rows": build_bar_rows(estado_items),
        "prioridad_rows": build_bar_rows(prioridad_items),
        "tecnico_rows": build_bar_rows(tecnico_items),
        "area_rows": build_bar_rows(area_items),
        "incidencias": queryset_list,
        "generado_por": request.user,
        "generado_por_nombre": nombre_usuario(request.user),
        "generado_en": timezone.localtime(timezone.now()),
    }

    pdf_file = generate_pdf("tickets/exports/dashboard_incidencias.html", context)
    if pdf_file:
        registrar_auditoria(
            request,
            "Incidencias",
            "descargó PDF de dashboard",
            f"El usuario {nombre_usuario(request.user)} descargó un PDF del dashboard de incidencias.",
            None,
        )
        filename = f"dashboard_incidencias_{timezone.now().strftime('%Y%m%d')}.pdf"
        return FileResponse(pdf_file, content_type="application/pdf", filename=filename)
    raise Http404("Error al generar el PDF del dashboard")


@login_required
@user_passes_test(can_view_inventory_reports)
def export_dashboard_inventario_pdf(request):
    queryset, filters = filtered_inventory_queryset(request)
    equipos = list(queryset.order_by("codigo_equipo")[:40])

    operativos = queryset.filter(estado_tecnico__nombre__iexact="Operativo").count()
    revision = queryset.filter(
        Q(estado_tecnico__nombre__iexact="En revisión")
        | Q(estado_tecnico__nombre__iexact="En reparacion")
        | Q(estado_tecnico__nombre__iexact="En reparación")
    ).count()
    observados = queryset.filter(
        Q(estado_tecnico__nombre__iexact="Inoperativo")
        | Q(estado_tecnico__nombre__iexact="Dado de baja")
    ).count()

    estado_items = list(
        queryset.values(name=F("estado_tecnico__nombre")).annotate(total=Count("id")).order_by("-total", "estado_tecnico__nombre")
    )
    tipo_items = list(
        queryset.values(name=F("tipo_equipo__nombre")).annotate(total=Count("id")).order_by("-total", "tipo_equipo__nombre")[:8]
    )
    area_items = list(
        queryset.values(name=F("area__name")).annotate(total=Count("id")).order_by("-total", "area__name")[:8]
    )
    marca_items = list(
        queryset.values(name=F("marca__nombre")).annotate(total=Count("id")).order_by("-total", "marca__nombre")[:8]
    )

    area_label = "Todas"
    if filters["area_id"].isdigit():
        area = Area.objects.filter(pk=filters["area_id"]).first()
        area_label = area.name if area else "No encontrada"
    tipo_label = "Todos"
    if filters["tipo_id"].isdigit():
        tipo = TipoEquipo.objects.filter(pk=filters["tipo_id"]).first()
        tipo_label = tipo.nombre if tipo else "No encontrado"
    marca_label = "Todas"
    if filters["marca_id"].isdigit():
        marca = Marca.objects.filter(pk=filters["marca_id"]).first()
        marca_label = marca.nombre if marca else "No encontrada"
    estado_label = "Todos"
    if filters["estado_id"].isdigit():
        estado = EstadoEquipo.objects.filter(pk=filters["estado_id"]).first()
        estado_label = estado.nombre if estado else "No encontrado"

    context = {
        "kpis": {
            "total": queryset.count(),
            "operativos": operativos,
            "revision": revision,
            "observados": observados,
        },
        "filter_labels": {
            "fecha_inicio": filters["start_date"] or "Sin inicio",
            "fecha_fin": filters["end_date"] or "Sin fin",
            "area": area_label,
            "tipo": tipo_label,
            "marca": marca_label,
            "estado": estado_label,
        },
        "estado_rows": build_bar_rows(estado_items),
        "tipo_rows": build_bar_rows(tipo_items),
        "area_rows": build_bar_rows(area_items),
        "marca_rows": build_bar_rows(marca_items),
        "equipos": equipos,
        "generado_por": request.user,
        "generado_por_nombre": nombre_usuario(request.user),
        "generado_en": timezone.localtime(timezone.now()),
    }

    pdf_file = generate_pdf("tickets/exports/dashboard_inventario.html", context)
    if pdf_file:
        registrar_auditoria(
            request,
            "Inventario",
            "descargó PDF de dashboard",
            f"El usuario {nombre_usuario(request.user)} descargó un PDF del dashboard de inventario.",
            None,
        )
        filename = f"dashboard_inventario_{timezone.now().strftime('%Y%m%d')}.pdf"
        return FileResponse(pdf_file, content_type="application/pdf", filename=filename)
    raise Http404("Error al generar el PDF del dashboard de inventario")
