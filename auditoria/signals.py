from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from inventario.models import Equipo
from .models import Auditoria
import threading

_thread_locals = threading.local()

def set_current_request(request):
    _thread_locals.request = request

def get_current_request():
    return getattr(_thread_locals, 'request', None)

@receiver(pre_save, sender=Equipo)
def capturar_estado_anterior(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_instance = Equipo.objects.get(pk=instance.pk)
        except Equipo.DoesNotExist:
            instance._old_instance = None
    else:
        instance._old_instance = None

@receiver(post_save, sender=Equipo)
def auditar_equipo(sender, instance, created, **kwargs):
    request = get_current_request()
    usuario = request.user if request and request.user.is_authenticated else None
    User = get_user_model()
    if usuario and not User.objects.filter(pk=usuario.pk).exists():
        usuario = None
    
    ip = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

    if created:
        accion = "registró equipo"
        descripcion = f"Se registró el equipo {instance.codigo_equipo} ({instance.nombre_equipo})"
    else:
        old = getattr(instance, '_old_instance', None)
        accion = "editó equipo"
        descripcion = f"Se actualizó el equipo {instance.codigo_equipo}"

        if old:
            if old.estado != instance.estado:
                accion = "cambió estado"
                descripcion = f"Se cambió el estado de {instance.codigo_equipo} de {old.estado} a {instance.estado}"
            elif old.area != instance.area:
                accion = "reasignó área"
                area_nombre = instance.area.name if instance.area else "Sin Área"
                descripcion = f"Se reasignó el equipo {instance.codigo_equipo} al área {area_nombre}"
            elif not instance.activo and old.activo:
                accion = "dio baja lógica"
                descripcion = f"Se dio de baja lógica al equipo {instance.codigo_equipo}"

    Auditoria.objects.create(
        usuario=usuario,
        modulo='Inventario',
        accion=accion,
        descripcion=descripcion,
        metadata={
            "equipo_id": instance.id,
            "codigo_equipo": instance.codigo_equipo,
            "origen": "signal",
        },
        ip=ip,
        referencia_id=instance.id
    )
