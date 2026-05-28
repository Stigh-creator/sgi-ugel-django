import unicodedata
import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.models import CharField, F, Prefetch, Q, Value
from django.db.models.functions import Cast, Lower, Replace
from django.utils.module_loading import import_string
from django.urls import reverse
from django.utils import timezone

from auditoria.utils import registrar_auditoria, registrar_evento_fallido
from .models import (
    Comentario,
    CustomUser,
    Estado,
    EstadoIncidencia,
    EstadoSLA,
    Incidencia,
    IncidenciaImagen,
    MetricaDiaria,
    Notificacion,
    NotificacionUsuario,
    ReemplazoEquipoIncidencia,
    SLAConfiguracion,
)

PRIORITY_WEIGHTS = {
    Incidencia.PRIORIDAD_BAJA: 1,
    Incidencia.PRIORIDAD_MEDIA: 1,
    Incidencia.PRIORIDAD_ALTA: 2,
    Incidencia.PRIORIDAD_CRITICA: 3,
}

VALID_TRANSITIONS = Incidencia.ALLOWED_TRANSITIONS
EVENT_VERSION = 1
POR_VENCER_UMBRAL = 0.8
LOCKED_RESOURCE_MESSAGE = "El registro está siendo procesado por otro usuario. Intente nuevamente en unos segundos."
SLA_EVENTOS = {
    "incidencia.sla_por_vencer",
    "incidencia.sla_respuesta_vencido",
    "incidencia.sla_resolucion_vencido",
}
SLA_ESTADOS_ACTIVOS = {
    Incidencia.ESTADO_PENDIENTE,
    Incidencia.ESTADO_ASIGNADO,
    Incidencia.ESTADO_EN_PROCESO,
    Incidencia.ESTADO_RECHAZADO,
    Incidencia.ESTADO_REABIERTO,
}
NOTIFICATION_TIPO_BY_EVENT = {
    "incidencia.creada": "nueva_incidencia",
    "incidencia.asignada": "asignacion",
    "incidencia.reasignada": "asignacion",
    "incidencia.aceptada": "estado",
    "incidencia.rechazada": "desasignacion",
    "incidencia.comentada": "comentario",
    "incidencia.resuelta": "incidencia_resuelta",
    "incidencia.reabierta": "estado",
    "incidencia.cerrada": "estado",
    "incidencia.sla_por_vencer": "sla",
    "incidencia.sla_respuesta_vencido": "sla",
    "incidencia.sla_resolucion_vencido": "sla",
    "inventario.estado_cambiado": "inventario",
    "inventario.reemplazo_registrado": "inventario",
}


def lock_queryset(queryset):
    if connection.features.has_select_for_update_of:
        return queryset.select_for_update(nowait=True, of=("self",))
    return queryset.select_for_update(nowait=True)


def get_locked_or_raise(queryset, *args, **kwargs):
    try:
        return lock_queryset(queryset).get(*args, **kwargs)
    except DatabaseError as exc:
        raise ValidationError(LOCKED_RESOURCE_MESSAGE) from exc


def first_locked_or_raise(queryset):
    try:
        return lock_queryset(queryset).first()
    except DatabaseError as exc:
        raise ValidationError(LOCKED_RESOURCE_MESSAGE) from exc


def get_estado(name):
    estado, _ = Estado.objects.get_or_create(name=name)
    return estado


def nombre_usuario(usuario):
    if not usuario:
        return "Sistema"
    return usuario.get_full_name() or usuario.username


def ticket_label(incidencia):
    return f"[{incidencia.codigo or f'INC-{incidencia.pk:04d}'}]"


def get_sla_configuracion(incidencia):
    return (
        SLAConfiguracion.objects.filter(
            prioridad=incidencia.prioridad,
            categoria=incidencia.categoria,
            activo=True,
        ).first()
        or SLAConfiguracion.objects.filter(
            prioridad=incidencia.prioridad,
            categoria__isnull=True,
            activo=True,
        ).first()
    )


def aplicar_sla_inicial(incidencia):
    config = get_sla_configuracion(incidencia)
    if not config:
        incidencia.estado_sla = EstadoSLA.NO_APLICA
        return incidencia
    base = incidencia.fecha_creacion or timezone.now()
    incidencia.fecha_limite_respuesta = base + timedelta(minutes=config.tiempo_respuesta_minutos)
    incidencia.fecha_limite_resolucion = base + timedelta(minutes=config.tiempo_resolucion_minutos)
    incidencia.estado_sla = EstadoSLA.EN_TIEMPO
    return incidencia


def get_sla_dashboard_counts(queryset=None, now=None):
    now = now or timezone.now()
    base_queryset = queryset if queryset is not None else Incidencia.objects.all()
    incidencias = base_queryset.filter(
        estado__name__in=SLA_ESTADOS_ACTIVOS,
    ).exclude(
        estado_sla__in=[EstadoSLA.CUMPLIDO, EstadoSLA.NO_APLICA],
    ).values(
        "fecha_creacion",
        "fecha_limite_respuesta",
        "fecha_limite_resolucion",
        "estado_sla",
    )

    vencidas = 0
    por_vencer = 0
    for incidencia in incidencias:
        limites = [limite for limite in (
            incidencia["fecha_limite_respuesta"],
            incidencia["fecha_limite_resolucion"],
        ) if limite]
        if not limites:
            continue
        if any(limite <= now for limite in limites):
            vencidas += 1
            continue
        if incidencia["estado_sla"] == EstadoSLA.POR_VENCER:
            por_vencer += 1
            continue
        base = incidencia["fecha_creacion"]
        if not base:
            continue
        for limite in limites:
            total = (limite - base).total_seconds()
            transcurrido = (now - base).total_seconds()
            if total > 0 and transcurrido >= (total * POR_VENCER_UMBRAL):
                por_vencer += 1
                break

    return {
        "por_vencer": por_vencer,
        "vencidas": vencidas,
    }


def calcular_fecha_auto_cierre(incidencia):
    config = get_sla_configuracion(incidencia)
    horas = config.auto_cierre_horas if config else 72
    return timezone.now() + timedelta(hours=horas)


def recipients_for_event(evento, incidencia, actor=None):
    usuarios = set()
    admins = CustomUser.objects.filter(
        Q(role=CustomUser.ROL_ADMIN) | Q(is_superuser=True),
        is_active=True,
    )
    if evento in SLA_EVENTOS:
        if incidencia.tecnico_asignado_id and incidencia.tecnico_asignado and incidencia.tecnico_asignado.is_active:
            usuarios.add(incidencia.tecnico_asignado)
        usuarios.update(admins)
        if actor:
            usuarios.discard(actor)
        return [u for u in usuarios if u and u.is_active]

    almacen = CustomUser.objects.filter(role=CustomUser.ROL_ALMACEN, is_active=True)
    if evento.startswith("inventario."):
        usuarios.update(almacen)
        if evento in {"inventario.reemplazo_registrado"}:
            usuarios.update(admins)
        if incidencia.tecnico_asignado_id:
            usuarios.add(incidencia.tecnico_asignado)
        if actor:
            usuarios.discard(actor)
        return [u for u in usuarios if u and u.is_active]

    if evento in {
        "incidencia.creada",
        "incidencia.asignada",
        "incidencia.reasignada",
        "incidencia.aceptada",
        "incidencia.rechazada",
        "incidencia.reabierta",
        "incidencia.cerrada",
        "inventario.integridad_alerta",
    }:
        usuarios.update(admins)
    if incidencia.creador_id:
        usuarios.add(incidencia.creador)
    if incidencia.tecnico_asignado_id:
        usuarios.add(incidencia.tecnico_asignado)
    if actor:
        usuarios.discard(actor)
    return [u for u in usuarios if u and u.is_active]


def prioridad_notificacion_para_evento(evento, incidencia):
    if evento in {"incidencia.sla_respuesta_vencido", "incidencia.sla_resolucion_vencido"}:
        return Notificacion.PRIORIDAD_CRITICA
    if evento in {"incidencia.rechazada", "incidencia.reabierta"}:
        return Notificacion.PRIORIDAD_ALTA
    if evento == "incidencia.creada" and incidencia.prioridad in {
        Incidencia.PRIORIDAD_ALTA,
        Incidencia.PRIORIDAD_CRITICA,
    }:
        return Notificacion.PRIORIDAD_ALTA if incidencia.prioridad == Incidencia.PRIORIDAD_ALTA else Notificacion.PRIORIDAD_CRITICA
    if evento in {
        "incidencia.asignada",
        "incidencia.reasignada",
        "incidencia.resuelta",
        "incidencia.sla_por_vencer",
        "inventario.estado_cambiado",
        "inventario.reemplazo_registrado",
    }:
        return Notificacion.PRIORIDAD_ALTA
    if evento == "incidencia.comentada":
        return Notificacion.PRIORIDAD_MEDIA
    return Notificacion.PRIORIDAD_BAJA


EVENTO_ACCION = {
    "incidencia.creada": "creó incidencia",
    "incidencia.asignada": "asignó técnico",
    "incidencia.aceptada": "aceptó incidencia",
    "incidencia.rechazada": "rechazó incidencia",
    "incidencia.reasignada": "reasignó técnico",
    "incidencia.comentada": "comentó incidencia",
    "incidencia.resuelta": "resolvió incidencia",
    "incidencia.reabierta": "reabrió incidencia",
    "incidencia.cerrada": "cerró incidencia",
    "incidencia.sla_por_vencer": "SLA por vencer",
    "incidencia.sla_respuesta_vencido": "SLA respuesta vencido",
    "incidencia.sla_resolucion_vencido": "SLA resolución vencido",
    "inventario.estado_cambiado": "cambió estado equipo",
    "inventario.reemplazo_registrado": "registró reemplazo temporal",
}


def build_event_message(evento, incidencia, actor=None, metadata=None):
    metadata = metadata or {}
    actor_name = nombre_usuario(actor)
    codigo = ticket_label(incidencia)
    messages = {
        "incidencia.creada": f"{codigo} Incidencia creada por {actor_name}.",
        "incidencia.asignada": f"{codigo} Técnico asignado: {metadata.get('tecnico_nombre', 'Sin técnico')}.",
        "incidencia.aceptada": f"{codigo} El técnico {actor_name} aceptó la incidencia. Estado cambiado a 'En Proceso'.",
        "incidencia.rechazada": f"{codigo} El técnico {actor_name} rechazó la incidencia. Motivo: {metadata.get('motivo', '')}. El ticket ha sido desvinculado.",
        "incidencia.reasignada": f"{codigo} Reasignado de {metadata.get('tecnico_anterior', 'Sin técnico')} a {metadata.get('tecnico_nombre', 'Sin técnico')} por {actor_name}.",
        "incidencia.comentada": f"{codigo} {actor_name} añadió un comentario al seguimiento.",
        "incidencia.resuelta": f"{codigo} Incidencia marcada como Resuelta por {actor_name}. Tipo de solución: {metadata.get('tipo_resolucion', 'No registrado')}.",
        "incidencia.reabierta": f"{codigo} Incidencia reabierta por {actor_name}. Motivo: {metadata.get('motivo', '')}.",
        "incidencia.cerrada": f"{codigo} Incidencia cerrada definitivamente por {actor_name}.",
        "incidencia.sla_por_vencer": f"{codigo} SLA por vencer. Tipo: {metadata.get('tipo_sla', 'No registrado')}.",
        "incidencia.sla_respuesta_vencido": f"{codigo} SLA de respuesta vencido.",
        "incidencia.sla_resolucion_vencido": f"{codigo} SLA de resolución vencido.",
        "inventario.estado_cambiado": f"{codigo} Cambio de inventario registrado.",
        "inventario.reemplazo_registrado": f"{codigo} Reemplazo temporal registrado: {metadata.get('equipo_reemplazo', 'Sin equipo')}.",
    }
    return messages.get(evento, f"{codigo} Evento registrado: {evento}.")


def comentario_tipo_para_evento(evento):
    return {
        "incidencia.aceptada": "confirmacion",
        "incidencia.rechazada": "observacion",
        "incidencia.resuelta": "confirmacion",
        "incidencia.reabierta": "persiste",
        "incidencia.cerrada": "confirmacion",
    }.get(evento)


def generar_hash_evento(evento, incidencia, metadata=None):
    payload = {
        "evento": evento,
        "version_evento": EVENT_VERSION,
        "incidencia_id": incidencia.id,
        "estado": incidencia.estado_actual,
        "metadata": metadata or {},
    }
    raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _procesar_evento_incidencia(evento, incidencia, actor=None, metadata=None):
    metadata = metadata or {}
    hash_evento = generar_hash_evento(evento, incidencia, metadata)
    metadata = {
        "evento": evento,
        "version_evento": EVENT_VERSION,
        "incidencia_id": incidencia.id,
        "codigo": incidencia.codigo,
        "hash_evento": hash_evento,
        **metadata,
    }
    mensaje = build_event_message(evento, incidencia, actor=actor, metadata=metadata)
    _, created = registrar_auditoria(
        None,
        "Inventario" if evento.startswith("inventario.") else "Incidencias",
        EVENTO_ACCION.get(evento, evento),
        mensaje,
        incidencia.id,
        metadata=metadata,
        actor=actor,
        evento=evento,
        hash_evento=hash_evento,
        version_evento=EVENT_VERSION,
    )
    if not created:
        return None

    tipo_comentario = comentario_tipo_para_evento(evento)
    if tipo_comentario:
        Comentario.objects.create(
            incidencia=incidencia,
            usuario=actor or incidencia.creador,
            tipo_comentario=tipo_comentario,
            texto=mensaje,
        )

    tipo_notificacion = NOTIFICATION_TIPO_BY_EVENT.get(evento, "estado")
    notificacion = Notificacion.objects.create(
        incidencia=incidencia,
        mensaje=mensaje,
        tipo=tipo_notificacion,
        prioridad=prioridad_notificacion_para_evento(evento, incidencia),
        link=reverse("detalle_incidencia", kwargs={"pk": incidencia.pk}) if incidencia.pk else None,
    )
    for usuario in recipients_for_event(evento, incidencia, actor=actor):
        NotificacionUsuario.objects.get_or_create(usuario=usuario, notificacion=notificacion)
    return notificacion


def emitir_evento_incidencia(evento, incidencia, actor=None, metadata=None):
    payload = {
        "evento": evento,
        "version": EVENT_VERSION,
        "incidencia_id": getattr(incidencia, "pk", None),
        "actor_id": getattr(actor, "pk", None),
        "timestamp": timezone.now().isoformat(),
        "metadata": metadata or {},
    }
    if getattr(settings, "USE_ASYNC", False):
        task_path = getattr(settings, "INCIDENCIA_EVENT_TASK", None)
        if task_path:
            try:
                task = import_string(task_path)
                transaction.on_commit(
                    lambda: task.delay(
                        evento,
                        incidencia.pk,
                        getattr(actor, "pk", None),
                        metadata or {},
                    )
                )
            except Exception as exc:
                registrar_evento_fallido(evento, payload, exc, version_evento=EVENT_VERSION)
                raise
            return None
    try:
        return _procesar_evento_incidencia(evento, incidencia, actor=actor, metadata=metadata)
    except Exception as exc:
        registrar_evento_fallido(evento, payload, exc, version_evento=EVENT_VERSION)
        raise


def normalize_text(value):
    return unicodedata.normalize("NFD", value or "").encode("ascii", "ignore").decode("ascii").lower().strip()


def normalize_expression(expression):
    normalized = Lower(Cast(expression, CharField()))
    replacements = (
        ("á", "a"),
        ("é", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ú", "u"),
        ("ñ", "n"),
    )
    for source, target in replacements:
        normalized = Replace(
            normalized,
            Value(source, output_field=CharField()),
            Value(target, output_field=CharField()),
            output_field=CharField(),
        )
    return normalized


def get_active_ticket_load_for_user(usuario, *, exclude_incidencia_id=None):
    queryset = Incidencia.objects.filter(tecnico_asignado=usuario).exclude(
        estado__name__in=[Incidencia.ESTADO_RECHAZADO, Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO]
    )
    if exclude_incidencia_id:
        queryset = queryset.exclude(pk=exclude_incidencia_id)
    return sum(PRIORITY_WEIGHTS.get(ticket.prioridad, 1) for ticket in queryset.only("prioridad"))


def validate_tecnico_capacity(tecnico, *, exclude_incidencia_id=None):
    if not tecnico or not tecnico.puede_ser_especialista:
        raise ValidationError("Solo técnicos o administradores activos pueden ser asignados como especialistas.")

    current_load = get_active_ticket_load_for_user(tecnico, exclude_incidencia_id=exclude_incidencia_id)
    capacidad = tecnico.capacidad_base or 4
    if current_load >= capacidad:
        raise ValidationError(
            f"{tecnico.get_full_name() or tecnico.username} ya tiene carga ponderada {current_load}. "
            f"El máximo permitido es {capacidad}."
        )
    return current_load


def normalize_equipo_tipo(nombre):
    return normalize_text(nombre).replace(" ", "")


def is_compute_equipment_type(tipo_equipo):
    tipo_normalizado = normalize_equipo_tipo(getattr(tipo_equipo, "nombre", ""))
    return any(
        token in tipo_normalizado
        for token in ("pc", "computadora", "desktop", "laptop", "notebook", "portatil")
    )


def compatible_replacement_type_ids(tipo_equipo):
    if not tipo_equipo:
        return []
    from inventario.models import TipoEquipo

    if is_compute_equipment_type(tipo_equipo):
        return [tipo.id for tipo in TipoEquipo.objects.all() if is_compute_equipment_type(tipo)]
    return [tipo_equipo.id]


def equipo_reemplazo_es_compatible(equipo, equipo_reemplazo):
    if not equipo or not equipo_reemplazo:
        return True
    return equipo_reemplazo.tipo_equipo_id in compatible_replacement_type_ids(equipo.tipo_equipo)


def replacement_blocking_states():
    return [
        Incidencia.ESTADO_PENDIENTE,
        Incidencia.ESTADO_ASIGNADO,
        Incidencia.ESTADO_EN_PROCESO,
        Incidencia.ESTADO_REABIERTO,
        Incidencia.ESTADO_PENDIENTE_VALIDACION,
        Incidencia.ESTADO_RESUELTO,
    ]


def equipos_ocupados_por_incidencias(*, exclude_incidencia_id=None):
    queryset = Incidencia.objects.filter(estado__name__in=replacement_blocking_states())
    if exclude_incidencia_id:
        queryset = queryset.exclude(pk=exclude_incidencia_id)
    equipo_ids = set(queryset.exclude(equipo_id__isnull=True).values_list("equipo_id", flat=True))
    reemplazo_ids = set(queryset.exclude(equipo_reemplazo_id__isnull=True).values_list("equipo_reemplazo_id", flat=True))
    return equipo_ids | reemplazo_ids


class IncidenciaService:
    @staticmethod
    @transaction.atomic
    def crear(*, incidencia, actor=None, extra_images=None):
        equipo = None
        if incidencia.equipo_id:
            from inventario.models import Equipo
            from inventario.services import actualizar_estado_equipo_por_incidencia

            equipo = first_locked_or_raise(Equipo.objects.filter(pk=incidencia.equipo_id))
            if not equipo or not equipo.activo or equipo.estado_tecnico.nombre != "Operativo":
                raise ValidationError("El equipo seleccionado ya no está disponible. Actualice la lista e intente nuevamente.")
            if Incidencia.objects.filter(
                Q(equipo=equipo) | Q(equipo_reemplazo=equipo),
                estado__name__in=replacement_blocking_states(),
            ).exists():
                raise ValidationError("El equipo ya está vinculado a otra incidencia activa.")

        sync_incidencia_estado(incidencia)
        incidencia.save()
        if not incidencia.fecha_limite_respuesta or not incidencia.fecha_limite_resolucion:
            aplicar_sla_inicial(incidencia)
            incidencia.save(update_fields=[
                "fecha_limite_respuesta",
                "fecha_limite_resolucion",
                "estado_sla",
            ])

        for image in extra_images or []:
            if image:
                IncidenciaImagen.objects.create(incidencia=incidencia, imagen=image)

        if equipo:
            equipo.disponibilidad = equipo.DISPONIBILIDAD_EN_USO
            equipo.origen_ocupacion = equipo.ORIGEN_OCUPACION_INCIDENCIA
            equipo.save(update_fields=["disponibilidad", "origen_ocupacion", "actualizado_en"])
            actualizar_estado_equipo_por_incidencia(
                equipo=equipo,
                usuario=actor or incidencia.creador,
                incidencia_codigo=incidencia.codigo,
            )

        emitir_evento_incidencia("incidencia.creada", incidencia, actor=actor or incidencia.creador)
        return incidencia

    @staticmethod
    @transaction.atomic
    def asignar(incidencia_id, *, tecnico, actor=None, fecha_programada=None, hora_programada=None, observaciones=None):
        from inventario.services import marcar_equipo_en_reparacion_por_asignacion

        incidencia = get_locked_or_raise(
            Incidencia.objects.select_related("tecnico_asignado", "estado", "equipo"),
            pk=incidencia_id,
        )
        if incidencia.equipo_id:
            from inventario.models import Equipo

            first_locked_or_raise(Equipo.objects.filter(pk=incidencia.equipo_id))
        validate_tecnico_capacity(tecnico, exclude_incidencia_id=incidencia.pk)
        tecnico_anterior = incidencia.tecnico_asignado
        if not incidencia.can_transition_to(Incidencia.ESTADO_ASIGNADO):
            raise ValidationError(f"No se puede asignar una incidencia en estado {incidencia.estado_actual}.")
        incidencia.tecnico_asignado = tecnico
        if not incidencia.fecha_asignacion or getattr(tecnico_anterior, "id", None) != tecnico.id:
            incidencia.fecha_asignacion = timezone.now()
        incidencia.fecha_programada_atencion = fecha_programada or None
        incidencia.hora_programada_atencion = hora_programada or None
        incidencia.observaciones_internas = observaciones or ""
        incidencia.estado = get_estado(Incidencia.ESTADO_ASIGNADO)
        incidencia.save(update_fields=[
            "tecnico_asignado",
            "fecha_asignacion",
            "fecha_programada_atencion",
            "hora_programada_atencion",
            "observaciones_internas",
            "estado",
        ])
        marcar_equipo_en_reparacion_por_asignacion(
            equipo=incidencia.equipo,
            usuario=tecnico,
            incidencia_codigo=incidencia.codigo,
        )
        evento = "incidencia.reasignada" if tecnico_anterior else "incidencia.asignada"
        emitir_evento_incidencia(
            evento,
            incidencia,
            actor=actor,
            metadata={
                "tecnico_id": tecnico.id,
                "tecnico_nombre": nombre_usuario(tecnico),
                "tecnico_anterior_id": getattr(tecnico_anterior, "id", None),
                "tecnico_anterior": nombre_usuario(tecnico_anterior) if tecnico_anterior else None,
            },
        )
        return incidencia

    @staticmethod
    @transaction.atomic
    def aceptar(incidencia_id, tecnico):
        incidencia = get_locked_or_raise(
            Incidencia.objects.select_related("tecnico_asignado", "estado"),
            pk=incidencia_id,
        )
        if incidencia.tecnico_asignado_id != tecnico.id:
            raise ValidationError("Solo el especialista asignado puede aceptar esta incidencia.")
        if not tecnico.puede_ser_especialista:
            raise ValidationError("Tu usuario no tiene permisos activos para aceptar incidencias.")
        transition_incidencia(incidencia, Incidencia.ESTADO_EN_PROCESO)
        emitir_evento_incidencia("incidencia.aceptada", incidencia, actor=tecnico)
        return incidencia

    @staticmethod
    @transaction.atomic
    def rechazar(incidencia_id, tecnico, motivo):
        incidencia = get_locked_or_raise(
            Incidencia.objects.select_related("tecnico_asignado", "estado"),
            pk=incidencia_id,
        )
        motivo = (motivo or "").strip()
        if incidencia.tecnico_asignado_id != tecnico.id:
            raise ValidationError("Solo el especialista asignado puede rechazar esta incidencia.")
        if not tecnico.puede_ser_especialista:
            raise ValidationError("Tu usuario no tiene permisos activos para rechazar incidencias.")
        if not motivo:
            raise ValidationError("El motivo de rechazo es obligatorio.")
        incidencia.tecnico_asignado = None
        transition_incidencia(incidencia, Incidencia.ESTADO_RECHAZADO, save_fields=["tecnico_asignado"])
        emitir_evento_incidencia("incidencia.rechazada", incidencia, actor=tecnico, metadata={"motivo": motivo})
        return motivo

    @staticmethod
    @transaction.atomic
    def resolver(incidencia_id, tecnico, solucion_aplicada, tipo_resolucion, equipo_reemplazo=None, evidencia=None, evidencia_2=None, evidencia_3=None):
        from inventario.models import Equipo
        from inventario.services import aplicar_inventario_al_resolver_incidencia

        incidencia = get_locked_or_raise(
            Incidencia.objects.select_related("estado", "equipo", "tecnico_asignado"),
            pk=incidencia_id,
        )
        if incidencia.equipo_id:
            first_locked_or_raise(Equipo.objects.filter(pk=incidencia.equipo_id))
        if equipo_reemplazo:
            equipo_reemplazo = get_locked_or_raise(Equipo.objects.all(), pk=equipo_reemplazo.pk)
        validate_resolution_inventory_rules(
            incidencia=incidencia,
            tipo_resolucion=tipo_resolucion,
            equipo_reemplazo=equipo_reemplazo,
        )
        reemplaza_solucion_previa = incidencia.estado_actual == Incidencia.ESTADO_REABIERTO or bool(incidencia.solucion_aplicada)
        incidencia.tecnico_asignado = tecnico
        if not incidencia.fecha_asignacion:
            incidencia.fecha_asignacion = timezone.now()
        incidencia.solucion_aplicada = solucion_aplicada
        incidencia.tipo_resolucion = tipo_resolucion
        incidencia.equipo_reemplazo = equipo_reemplazo
        incidencia.fecha_resolucion = timezone.now()
        incidencia.fecha_auto_cierre = calcular_fecha_auto_cierre(incidencia)
        incidencia.estado_sla = EstadoSLA.CUMPLIDO
        if evidencia:
            incidencia.evidencia_solucion = evidencia
        if evidencia_2:
            incidencia.evidencia_solucion_2 = evidencia_2
        elif reemplaza_solucion_previa:
            incidencia.evidencia_solucion_2 = None
        if evidencia_3:
            incidencia.evidencia_solucion_3 = evidencia_3
        elif reemplaza_solucion_previa:
            incidencia.evidencia_solucion_3 = None
        incidencia.estado = get_estado(Incidencia.ESTADO_RESUELTO)
        incidencia.save()
        aplicar_inventario_al_resolver_incidencia(incidencia=incidencia, usuario=tecnico)
        emitir_evento_incidencia(
            "incidencia.resuelta",
            incidencia,
            actor=tecnico,
            metadata={
                "tipo_resolucion": incidencia.get_tipo_resolucion_display(),
                "equipo_id": incidencia.equipo_id,
                "equipo_reemplazo_id": incidencia.equipo_reemplazo_id,
            },
        )
        return incidencia

    @staticmethod
    @transaction.atomic
    def reabrir(incidencia_id, actor, motivo=None):
        incidencia = get_locked_or_raise(Incidencia.objects.select_related("estado"), pk=incidencia_id)
        incidencia.fecha_cierre = None
        incidencia.auto_cerrado = False
        incidencia.estado = get_estado(Incidencia.ESTADO_REABIERTO)
        incidencia.save(update_fields=["fecha_cierre", "auto_cerrado", "estado"])
        emitir_evento_incidencia("incidencia.reabierta", incidencia, actor=actor, metadata={"motivo": motivo or ""})
        return incidencia

    @staticmethod
    @transaction.atomic
    def cerrar(incidencia_id, usuario, *, auto=False):
        from inventario.services import aplicar_inventario_al_cerrar_incidencia

        incidencia = get_locked_or_raise(Incidencia.objects.select_related("estado", "equipo"), pk=incidencia_id)
        transition_incidencia(incidencia, Incidencia.ESTADO_CERRADO, save_fields=["fecha_cierre", "auto_cerrado"])
        incidencia.fecha_cierre = timezone.now()
        incidencia.auto_cerrado = auto
        incidencia.save(update_fields=["fecha_cierre", "auto_cerrado"])
        aplicar_inventario_al_cerrar_incidencia(incidencia=incidencia, usuario=usuario)
        emitir_evento_incidencia("incidencia.cerrada", incidencia, actor=usuario, metadata={"auto": auto})
        return incidencia


def resolve_active_tab_for_user(user, requested_tab):
    default_tab = "reportadas" if user.es_usuario else "asignadas"
    return requested_tab if requested_tab in {"asignadas", "reportadas"} else default_tab


def get_visible_incidencias_queryset(user, active_tab):
    queryset = Incidencia.objects.all()

    if user.es_usuario:
        return queryset.filter(creador_id=user.id), "reportadas"

    if user.es_tecnico:
        if active_tab == "reportadas":
            return queryset.filter(creador_id=user.id), "reportadas"
        return queryset.filter(tecnico_asignado_id=user.id), "asignadas"

    if user.es_admin:
        if active_tab == "reportadas":
            return queryset.filter(creador_id=user.id), "reportadas"
        return queryset, "asignadas"
    
    return queryset.filter(creador_id=user.id), "reportadas"


def apply_incidencias_search(queryset, query):
    if not query:
        return queryset
    normalized_query = normalize_text(query)
    queryset = queryset.annotate(
        creador_nombre_normalizado=normalize_expression(F("creador__first_name")),
        creador_apellido_normalizado=normalize_expression(F("creador__last_name")),
        tecnico_nombre_normalizado=normalize_expression(F("tecnico_asignado__first_name")),
        tecnico_apellido_normalizado=normalize_expression(F("tecnico_asignado__last_name")),
        descripcion_normalizada=normalize_expression(F("descripcion")),
        area_normalizada=normalize_expression(F("area__name")),
    )
    return queryset.filter(
        Q(codigo__icontains=query)
        | Q(id__icontains=query)
        | Q(creador__username__icontains=query)
        | Q(creador_nombre_normalizado__contains=normalized_query)
        | Q(creador_apellido_normalizado__contains=normalized_query)
        | Q(tecnico_nombre_normalizado__contains=normalized_query)
        | Q(tecnico_apellido_normalizado__contains=normalized_query)
        | Q(descripcion_normalizada__contains=normalized_query)
        | Q(area_normalizada__contains=normalized_query)
    )


def apply_estado_filter(queryset, estado_id):
    if not estado_id:
        return queryset

    estado_nombre = Estado.objects.filter(id=estado_id).values_list("name", flat=True).first()
    if estado_nombre == Incidencia.ESTADO_ASIGNADO:
        return queryset.filter(tecnico_asignado__isnull=False).filter(
            Q(estado__name=Incidencia.ESTADO_ASIGNADO)
            | Q(estado__name=Incidencia.ESTADO_PENDIENTE)
        )
    if estado_nombre == Incidencia.ESTADO_RESUELTO:
        return queryset.filter(estado__name=Incidencia.ESTADO_RESUELTO)
    if estado_nombre == Incidencia.ESTADO_PENDIENTE:
        return queryset.filter(tecnico_asignado__isnull=True, estado__name=Incidencia.ESTADO_PENDIENTE)
    return queryset.filter(estado__id=estado_id)


def available_estado_filters():
    return Estado.objects.all().order_by("name")


def optimized_incidencias_queryset(queryset=None):
    base_queryset = Incidencia.objects.all() if queryset is None else queryset
    return base_queryset.select_related(
        "creador",
        "tecnico_asignado",
        "estado",
        "area",
        "equipo",
    ).prefetch_related(
        "imagenes",
        Prefetch("comentarios", queryset=Comentario.objects.select_related("usuario").order_by("fecha_creacion")),
    )


def obtener_metricas_operativas():
    from inventario.models import Equipo

    estados_activos = replacement_blocking_states()
    now = timezone.now()
    return {
        "tickets_abiertos": Incidencia.objects.exclude(estado__name=Incidencia.ESTADO_CERRADO).count(),
        "tickets_cerrados": Incidencia.objects.filter(estado__name=Incidencia.ESTADO_CERRADO).count(),
        "sla_respuesta_vencidos": Incidencia.objects.filter(sla_respuesta_notificado=True).exclude(estado__name=Incidencia.ESTADO_CERRADO).count(),
        "sla_resolucion_vencidos": Incidencia.objects.filter(sla_resolucion_notificado=True).exclude(estado__name=Incidencia.ESTADO_CERRADO).count(),
        "sla_por_vencer": Incidencia.objects.filter(estado_sla=EstadoSLA.POR_VENCER).exclude(estado__name=Incidencia.ESTADO_CERRADO).count(),
        "tickets_validacion_vencidos": Incidencia.objects.filter(
            estado__name=Incidencia.ESTADO_RESUELTO,
            fecha_auto_cierre__isnull=False,
            fecha_auto_cierre__lt=now,
        ).count(),
        "equipos_reparacion_sin_ticket_activo": Equipo.objects.filter(
            estado_tecnico__nombre="En reparación",
            activo=True,
        ).exclude(incidencia__estado__name__in=estados_activos).distinct().count(),
        "reemplazos_activos": ReemplazoEquipoIncidencia.objects.filter(activo=True).count(),
    }


def crear_snapshot_metricas(fecha=None):
    fecha = fecha or timezone.localdate()
    metricas = obtener_metricas_operativas()
    sla_vencidos = metricas["sla_respuesta_vencidos"] + metricas["sla_resolucion_vencidos"]
    snapshot, _ = MetricaDiaria.objects.update_or_create(
        fecha=fecha,
        defaults={
            "tickets_abiertos": metricas["tickets_abiertos"],
            "tickets_cerrados": metricas["tickets_cerrados"],
            "sla_vencidos": sla_vencidos,
            "sla_por_vencer": metricas["sla_por_vencer"],
            "tickets_validacion_vencidos": metricas["tickets_validacion_vencidos"],
            "equipos_reparacion_sin_ticket_activo": metricas["equipos_reparacion_sin_ticket_activo"],
            "reemplazos_activos": metricas["reemplazos_activos"],
            "metadata": metricas,
        },
    )
    return snapshot


def transition_incidencia(incidencia, target_state, *, save_fields=None):
    current_state = incidencia.estado_normalizado
    if target_state != current_state and target_state not in VALID_TRANSITIONS.get(current_state, set()):
        raise ValidationError(
            f"No se puede cambiar la incidencia #{incidencia.pk} de "
            f"{incidencia.estado_actual} a {target_state}."
        )
    incidencia.estado = get_estado(target_state)
    fields = ["estado"]
    if save_fields:
        fields.extend(save_fields)
    incidencia.save(update_fields=list(dict.fromkeys(fields)))
    return incidencia


def sync_incidencia_estado(incidencia):
    current_state = incidencia.estado_normalizado

    estados_con_flujo_manual = {
        Incidencia.ESTADO_EN_PROCESO,
        Incidencia.ESTADO_RECHAZADO,
        Incidencia.ESTADO_REABIERTO,
        Incidencia.ESTADO_PENDIENTE_VALIDACION,
        Incidencia.ESTADO_RESUELTO,
        Incidencia.ESTADO_CERRADO,
    }
    if current_state in estados_con_flujo_manual:
        incidencia.estado = get_estado(current_state)
        return incidencia

    target_state = (
        Incidencia.ESTADO_ASIGNADO
        if incidencia.tecnico_asignado
        else Incidencia.ESTADO_PENDIENTE
    )
    incidencia.estado = get_estado(target_state)
    return incidencia


def create_incidencia_service(*, incidencia, extra_images=None):
    return IncidenciaService.crear(
        incidencia=incidencia,
        actor=incidencia.creador,
        extra_images=extra_images,
    )


def aceptar_incidencia_service(incidencia, tecnico):
    return IncidenciaService.aceptar(incidencia.pk, tecnico)


def rechazar_incidencia_service(incidencia, tecnico, motivo):
    return IncidenciaService.rechazar(incidencia.pk, tecnico, motivo)


def assign_incidencia_service(
    incidencia,
    *,
    tecnico,
    fecha_programada=None,
    hora_programada=None,
    observaciones=None,
):
    return IncidenciaService.asignar(
        incidencia.pk,
        tecnico=tecnico,
        actor=None,
        fecha_programada=fecha_programada,
        hora_programada=hora_programada,
        observaciones=observaciones,
    )


def resolver_incidencia_service(
    incidencia,
    tecnico,
    solucion_aplicada,
    tipo_resolucion,
    equipo_reemplazo=None,
    evidencia=None,
    evidencia_2=None,
    evidencia_3=None,
):
    return IncidenciaService.resolver(
        incidencia.pk,
        tecnico,
        solucion_aplicada,
        tipo_resolucion,
        equipo_reemplazo=equipo_reemplazo,
        evidencia=evidencia,
        evidencia_2=evidencia_2,
        evidencia_3=evidencia_3,
    )


def validate_resolution_inventory_rules(*, incidencia, tipo_resolucion, equipo_reemplazo=None):
    if tipo_resolucion not in dict(Incidencia.TIPO_RESOLUCION_CHOICES):
        raise ValidationError("Debe seleccionar un tipo de resolución válido.")

    equipo = incidencia.equipo
    if not equipo:
        return

    if tipo_resolucion == Incidencia.RESOLUCION_REEMPLAZADO:
        if not equipo_reemplazo:
            raise ValidationError("Debe seleccionar un equipo de reemplazo")
        if equipo_reemplazo.id == equipo.id:
            raise ValidationError("El equipo de reemplazo no puede ser el mismo")
        if not equipo_reemplazo_es_compatible(equipo, equipo_reemplazo):
            raise ValidationError("El equipo de reemplazo debe ser del mismo tipo o compatible con el equipo afectado")
        if not equipo_reemplazo.activo or equipo_reemplazo.estado_tecnico.nombre != "Operativo":
            raise ValidationError("El equipo de reemplazo no está disponible")
        if equipo_reemplazo.disponibilidad != equipo_reemplazo.DISPONIBILIDAD_LIBRE:
            raise ValidationError("El equipo de reemplazo no está libre")
        if Incidencia.objects.filter(
            Q(equipo=equipo_reemplazo) | Q(equipo_reemplazo=equipo_reemplazo),
            estado__name__in=replacement_blocking_states(),
        ).exclude(pk=incidencia.pk).exists():
            raise ValidationError("El equipo de reemplazo ya está en otra incidencia activa")


def reabrir_incidencia_service(incidencia):
    return IncidenciaService.reabrir(incidencia.pk, incidencia.creador)


def cerrar_incidencia_service(incidencia, usuario):
    return IncidenciaService.cerrar(incidencia.pk, usuario)
