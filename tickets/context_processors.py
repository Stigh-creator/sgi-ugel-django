from .models import NotificacionUsuario


def notificaciones_header(request):
    if not request.user.is_authenticated:
        return {}

    notificaciones = (
        NotificacionUsuario.objects.filter(usuario=request.user)
        .select_related("notificacion", "notificacion__incidencia")
        .order_by("-fecha_recibida")[:8]
    )
    no_leidas = NotificacionUsuario.objects.filter(usuario=request.user, leido=False).count()
    return {
        "header_notificaciones": notificaciones,
        "header_notificaciones_no_leidas": no_leidas,
    }
