from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.utils import timezone

from ..models import Incidencia
from inventario.models import Equipo
from ..utils.exports import generate_pdf, generate_excel_inventario

@login_required
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
    incidencia = get_object_or_404(Incidencia, pk=pk)
    context = {'incidencia': incidencia}
    pdf_file = generate_pdf('tickets/exports/ticket_incidencia.html', context)
    
    if pdf_file:
        filename = f"ticket_{incidencia.codigo}.pdf"
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
    
    incidencias = Incidencia.objects.select_related('creador', 'area', 'estado', 'tecnico_asignado').all()
    
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
        'hoy': timezone.now()
    }
    
    pdf_file = generate_pdf('tickets/exports/reporte_incidencias.html', context)
    if pdf_file:
        filename = f"reporte_incidencias_{timezone.now().strftime('%Y%m%d')}.pdf"
        return FileResponse(pdf_file, content_type='application/pdf', filename=filename)
    raise Http404("Error al generar el PDF del reporte")
