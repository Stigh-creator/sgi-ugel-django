from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Auditoria
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator

User = get_user_model()

def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "administrador")

@login_required
@user_passes_test(is_admin)
def auditoria_dashboard(request):
    today = timezone.localtime(timezone.now()).date()
    start_of_week = today - timedelta(days=today.weekday())
    
    # --- NIVEL 1: MÉTRICAS DE RESUMEN ---
    total_hoy = Auditoria.objects.filter(fecha_hora__date=today).count()
    total_semana = Auditoria.objects.filter(fecha_hora__date__gte=start_of_week).count()
    
    most_active_user_data = Auditoria.objects.filter(fecha_hora__date=today)\
        .values('usuario__first_name', 'usuario__last_name', 'usuario__username')\
        .annotate(total=Count('id'))\
        .order_by('-total').first()
    
    if most_active_user_data:
        full_name = f"{most_active_user_data['usuario__first_name']} {most_active_user_data['usuario__last_name']}".strip()
        most_active_user = full_name if full_name else most_active_user_data['usuario__username']
    else:
        most_active_user = "Sin actividad"
    
    most_active_module_data = Auditoria.objects.filter(fecha_hora__date=today)\
        .values('modulo')\
        .annotate(total=Count('id'))\
        .order_by('-total').first()
    
    most_active_module = most_active_module_data['modulo'] if most_active_module_data else "N/A"

    # --- FILTROS ---
    modulo_f = request.GET.get('modulo', '')
    usuario_f = request.GET.get('usuario', '')
    desde_f = request.GET.get('desde', '')
    hasta_f = request.GET.get('hasta', '')
    q_f = request.GET.get('q', '')

    logs = Auditoria.objects.all().select_related('usuario')

    if modulo_f:
        logs = logs.filter(modulo=modulo_f)
    if usuario_f:
        logs = logs.filter(usuario_id=usuario_f)
    if desde_f:
        logs = logs.filter(fecha_hora__date__gte=desde_f)
    if hasta_f:
        logs = logs.filter(fecha_hora__date__lte=hasta_f)
    if q_f:
        logs = logs.filter(
            Q(accion__icontains=q_f) | 
            Q(descripcion__icontains=q_f) |
            Q(usuario__username__icontains=q_f) |
            Q(usuario__first_name__icontains=q_f) |
            Q(usuario__last_name__icontains=q_f)
        )

    # --- NIVEL 2: RESUMEN POR MÓDULOS (Data para las cards) ---
    def get_module_data(module_name):
        return {
            'nombre': module_name,
            'total_hoy': Auditoria.objects.filter(modulo=module_name, fecha_hora__date=today).count(),
            'ultima_accion': Auditoria.objects.filter(modulo=module_name).first()
        }

    modulos_data = {
        'Usuarios': get_module_data('Usuarios'),
        'Inventario': get_module_data('Inventario'),
        'Incidencias': get_module_data('Incidencias'),
        'Sistema': get_module_data('Sistema'),
    }

    # --- NIVEL 3: HISTORIAL DETALLADO (Paginación) ---
    paginator = Paginator(logs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        # Métricas
        'metrics': {
            'total_hoy': total_hoy,
            'total_semana': total_semana,
            'most_active_user': most_active_user,
            'most_active_module': most_active_module,
        },
        # Modulos
        'modulos_data': modulos_data,
        # Historial paginado
        'page_obj': page_obj,
        'logs_all': page_obj,
        # Listas para selects
        'usuarios_list': User.objects.all().order_by('first_name'),
        'modulos_list': ['Usuarios', 'Inventario', 'Incidencias', 'Sistema'],
        # Estado de filtros (Aseguramos que no sean None)
        'filtros_activos': any([modulo_f, usuario_f, desde_f, hasta_f, q_f]),
        'modulo_selected': modulo_f or '',
        'usuario_selected': usuario_f or '',
        'desde_selected': desde_f or '',
        'hasta_selected': hasta_f or '',
        'q_selected': q_f or '',
    }

    return render(request, 'auditoria/auditoria_dashboard.html', context)
