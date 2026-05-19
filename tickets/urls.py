from django.urls import path
from .views.views_auth import custom_login_view, logout_view, password_change_forced
from .views.views_usuarios import usuarios, mi_perfil, update_photo_view, crear_usuario, editar_usuario, toggle_usuario_status, reset_password_admin
from .views.views_incidencias import (
    index, dashboard_admin, dashboard_tecnico, mis_incidencias, incidencias_list,
    get_equipos_for_area, crear_incidencia, crear_incidencia_modal,
    detalle_incidencia, agregar_comentario, asignar_tecnico,
    aceptar_incidencia, rechazar_incidencia,
    resolver_incidencia, reabrir_incidencia, cerrar_incidencia,
    gestionar_incidencia, marcar_escribiendo
)
from .views.views_exports import (
    export_inventario_excel, export_ticket_pdf, export_reporte_incidencias_pdf,
    export_dashboard_incidencias_pdf, export_dashboard_inventario_pdf,
)
from .views.views_notificaciones import leer_notificacion, marcar_notificaciones_leidas

urlpatterns = [
    # Exportaciones
    path('exportar/inventario/excel/', export_inventario_excel, name='export_inventario_excel'),
    path('exportar/incidencia/<int:pk>/pdf/', export_ticket_pdf, name='export_ticket_pdf'),
    path('exportar/incidencias/reporte/pdf/', export_reporte_incidencias_pdf, name='export_reporte_pdf'),
    path('exportar/incidencias/dashboard/pdf/', export_dashboard_incidencias_pdf, name='export_dashboard_pdf'),
    path('exportar/inventario/dashboard/pdf/', export_dashboard_inventario_pdf, name='export_dashboard_inventario_pdf'),
    path('notificaciones/<int:pk>/leer/', leer_notificacion, name='leer_notificacion'),
    path('notificaciones/marcar-leidas/', marcar_notificaciones_leidas, name='marcar_notificaciones_leidas'),
    # Ruta raíz redirige según el index que ya programaste
    path('', index, name='index'),
    
    # Autenticación
    path('login/', custom_login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    
    # Dashboards (Las carcasas de la Épica 1)
    path('dashboard/admin/', dashboard_admin, name='dashboard_admin'),
    path('dashboard/tecnico/', dashboard_tecnico, name='dashboard_tecnico'),
    path('mis-incidencias/', mis_incidencias, name='mis_incidencias'),
    
    # Perfil y Usuarios
    path("usuarios/", usuarios, name="usuarios"),
    path("mi-perfil/", mi_perfil, name="mi_perfil"),
    path("mi-perfil/update-photo/", update_photo_view, name="update_photo"),
    path("usuarios/crear/", crear_usuario, name="crear_usuario"),
    path("usuarios/<int:pk>/editar/", editar_usuario, name="editar_usuario"),
    path("usuarios/<int:pk>/toggle-status/", toggle_usuario_status, name="toggle_usuario_status"),
    path("usuarios/<int:pk>/reset-password/", reset_password_admin, name="reset_password_admin"),
    path('cambio-obligatorio/', password_change_forced, name='password_change_forced'),

    # Incidencias (Épica 2 Refactorizada)
    path('incidencias/', incidencias_list, name='incidencias_list'),
    path('incidencias/get-equipos/', get_equipos_for_area, name='get_equipos_for_area'),
    path('incidencias/crear/', crear_incidencia, name='crear_incidencia'),
    path('incidencias/modal/crear/', crear_incidencia_modal, name='crear_incidencia_modal'),
    path('incidencias/<int:pk>/', detalle_incidencia, name='detalle_incidencia'),
    path('incidencias/<int:pk>/comentar/', agregar_comentario, name='agregar_comentario'),
    path('incidencias/<int:pk>/asignar/', asignar_tecnico, name='asignar_tecnico'),
    path('incidencias/<int:pk>/aceptar/', aceptar_incidencia, name='aceptar_incidencia'),
    path('incidencias/<int:pk>/rechazar/', rechazar_incidencia, name='rechazar_incidencia'),
    path('incidencias/<int:pk>/resolver/', resolver_incidencia, name='resolver_incidencia'),
    path('incidencias/<int:pk>/reabrir/', reabrir_incidencia, name='reabrir_incidencia'),
    path('incidencias/<int:pk>/cerrar/', cerrar_incidencia, name='cerrar_incidencia'),
    path('incidencias/<int:pk>/gestionar/', gestionar_incidencia, name='gestionar_incidencia'),
    path('incidencias/<int:pk>/escribiendo/', marcar_escribiendo, name='marcar_escribiendo'),
    
    # Redirecciones para compatibilidad con sidebar
    path('incidencias/administrar/', incidencias_list, name='incidencias_admin'),
    path('incidencias/asignadas/', incidencias_list, name='incidencias_asignadas'),
]
