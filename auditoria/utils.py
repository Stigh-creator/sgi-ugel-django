from .models import Auditoria

def registrar_auditoria(request, modulo, accion, descripcion, referencia_id=None):
    """
    Registra una acción en la bitácora de auditoría.
    """
    ip = None
    usuario = None

    if request:
        # Obtener IP de forma segura
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        if request.user.is_authenticated:
            usuario = request.user

    Auditoria.objects.create(
        usuario=usuario,
        modulo=modulo,
        accion=accion,
        descripcion=descripcion,
        ip=ip,
        referencia_id=referencia_id
    )
