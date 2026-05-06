from django.db import IntegrityError
from django.utils import timezone

from .models import Auditoria


def registrar_evento_fallido(evento, payload, error, version_evento=1):
    from .models import EventoFallido

    payload = payload or {}
    normalized_payload = {
        "incidencia_id": payload.get("incidencia_id"),
        "evento": payload.get("evento") or evento,
        "version": payload.get("version") or payload.get("version_evento") or version_evento,
        "actor_id": payload.get("actor_id"),
        "timestamp": payload.get("timestamp") or timezone.now().isoformat(),
        "metadata": payload.get("metadata") or {},
    }
    for key, value in payload.items():
        normalized_payload.setdefault(key, value)

    return EventoFallido.objects.create(
        evento=evento,
        version_evento=version_evento,
        payload=normalized_payload,
        error=str(error),
        ultimo_error=str(error),
        intentos=1,
    )


def registrar_auditoria(
    request,
    modulo,
    accion,
    descripcion,
    referencia_id=None,
    metadata=None,
    actor=None,
    evento=None,
    hash_evento=None,
    version_evento=1,
):
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
    if actor is not None:
        usuario = actor

    payload = {
        "usuario": usuario,
        "modulo": modulo,
        "accion": accion,
        "descripcion": descripcion,
        "metadata": metadata or {},
        "ip": ip,
        "referencia_id": referencia_id,
        "evento": evento,
        "version_evento": version_evento,
        "hash_evento": hash_evento,
    }
    if evento and hash_evento:
        try:
            auditoria, created = Auditoria.objects.get_or_create(
                evento=evento,
                hash_evento=hash_evento,
                defaults=payload,
            )
            return auditoria, created
        except IntegrityError:
            return Auditoria.objects.get(
                evento=evento,
                hash_evento=hash_evento,
            ), False
    return Auditoria.objects.create(**payload), True
