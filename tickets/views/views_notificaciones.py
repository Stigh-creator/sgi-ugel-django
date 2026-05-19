from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from ..models import NotificacionUsuario


@login_required
def leer_notificacion(request, pk):
    notificacion_usuario = get_object_or_404(
        NotificacionUsuario.objects.select_related("notificacion"),
        pk=pk,
        usuario=request.user,
    )
    if not notificacion_usuario.leido:
        notificacion_usuario.leido = True
        notificacion_usuario.save(update_fields=["leido"])

    destino = notificacion_usuario.notificacion.link or "index"
    return redirect(destino)


@login_required
@require_POST
def marcar_notificaciones_leidas(request):
    NotificacionUsuario.objects.filter(usuario=request.user, leido=False).update(leido=True)
    return redirect(request.META.get("HTTP_REFERER") or "index")
