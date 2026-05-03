import unicodedata

from django.core.exceptions import ValidationError
from django.db.models import F, Prefetch, Q, Value
from django.db.models.functions import Lower, Replace
from django.utils import timezone

from .models import Comentario, Estado, Incidencia, IncidenciaImagen

MAX_ACTIVE_TICKETS_PER_TECH = 4


def get_estado(name):
    estado, _ = Estado.objects.get_or_create(name=name)
    return estado


def normalize_text(value):
    return unicodedata.normalize("NFD", value or "").encode("ascii", "ignore").decode("ascii").lower().strip()


def normalize_expression(expression):
    normalized = Lower(expression)
    replacements = (
        ("á", "a"),
        ("é", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ú", "u"),
        ("ñ", "n"),
    )
    for source, target in replacements:
        normalized = Replace(normalized, Value(source), Value(target))
    return normalized


def get_active_ticket_load_for_user(usuario, *, exclude_incidencia_id=None):
    queryset = Incidencia.objects.filter(tecnico_asignado=usuario).exclude(
        estado__name__in=[Incidencia.ESTADO_RECHAZADO, Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO]
    )
    if exclude_incidencia_id:
        queryset = queryset.exclude(pk=exclude_incidencia_id)
    return queryset.count()


def validate_tecnico_capacity(tecnico, *, exclude_incidencia_id=None):
    if not tecnico or not tecnico.puede_ser_especialista:
        raise ValidationError("Solo técnicos o administradores activos pueden ser asignados como especialistas.")

    current_load = get_active_ticket_load_for_user(tecnico, exclude_incidencia_id=exclude_incidencia_id)
    if current_load >= MAX_ACTIVE_TICKETS_PER_TECH:
        raise ValidationError(
            f"{tecnico.get_full_name() or tecnico.username} ya tiene {current_load} tickets activos. "
            f"El máximo permitido es {MAX_ACTIVE_TICKETS_PER_TECH}."
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
        Incidencia.ESTADO_RESUELTO,
    ]


def equipos_ocupados_por_incidencias(*, exclude_incidencia_id=None):
    queryset = Incidencia.objects.filter(estado__name__in=replacement_blocking_states())
    if exclude_incidencia_id:
        queryset = queryset.exclude(pk=exclude_incidencia_id)
    equipo_ids = set(queryset.exclude(equipo_id__isnull=True).values_list("equipo_id", flat=True))
    reemplazo_ids = set(queryset.exclude(equipo_reemplazo_id__isnull=True).values_list("equipo_reemplazo_id", flat=True))
    return equipo_ids | reemplazo_ids


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


def transition_incidencia(incidencia, target_state, *, save_fields=None):
    if not incidencia.can_transition_to(target_state):
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
    equipo = None
    if incidencia.equipo_id:
        from inventario.models import Equipo

        equipo = Equipo.objects.filter(pk=incidencia.equipo_id).first()
        if not equipo or not equipo.activo or equipo.estado.nombre != "Operativo":
            raise ValidationError("El equipo seleccionado ya no está disponible. Actualice la lista e intente nuevamente.")

    sync_incidencia_estado(incidencia)

    incidencia.save()

    for image in extra_images or []:
        if image:
            IncidenciaImagen.objects.create(incidencia=incidencia, imagen=image)

    if equipo:
        equipo.disponibilidad = equipo.DISPONIBILIDAD_EN_USO
        equipo.save(update_fields=["disponibilidad", "actualizado_en"])
        from inventario.services import actualizar_estado_equipo_por_incidencia

        actualizar_estado_equipo_por_incidencia(
            equipo=equipo,
            usuario=incidencia.creador,
            incidencia_codigo=incidencia.codigo,
        )

    return incidencia


def aceptar_incidencia_service(incidencia, tecnico):
    if incidencia.tecnico_asignado_id != tecnico.id:
        raise ValidationError("Solo el especialista asignado puede aceptar esta incidencia.")
    if not tecnico.puede_ser_especialista:
        raise ValidationError("Tu usuario no tiene permisos activos para aceptar incidencias.")
    return transition_incidencia(incidencia, Incidencia.ESTADO_EN_PROCESO)


def rechazar_incidencia_service(incidencia, tecnico, motivo):
    motivo = (motivo or "").strip()
    if incidencia.tecnico_asignado_id != tecnico.id:
        raise ValidationError("Solo el especialista asignado puede rechazar esta incidencia.")
    if not tecnico.puede_ser_especialista:
        raise ValidationError("Tu usuario no tiene permisos activos para rechazar incidencias.")
    if not motivo:
        raise ValidationError("El motivo de rechazo es obligatorio.")
    incidencia.tecnico_asignado = None
    transition_incidencia(
        incidencia,
        Incidencia.ESTADO_RECHAZADO,
        save_fields=["tecnico_asignado"],
    )
    return motivo


def assign_incidencia_service(
    incidencia,
    *,
    tecnico,
    fecha_programada=None,
    hora_programada=None,
    observaciones=None,
):
    validate_tecnico_capacity(tecnico, exclude_incidencia_id=incidencia.pk)
    from inventario.services import marcar_equipo_en_reparacion_por_asignacion

    tecnico_anterior_id = incidencia.tecnico_asignado_id
    incidencia.tecnico_asignado = tecnico
    if tecnico_anterior_id != tecnico.id or not incidencia.fecha_asignacion:
        incidencia.fecha_asignacion = timezone.now()
    incidencia.fecha_programada_atencion = fecha_programada or None
    incidencia.hora_programada_atencion = hora_programada or None
    incidencia.observaciones_internas = observaciones or ""
    incidencia.estado = get_estado(Incidencia.ESTADO_ASIGNADO)
    incidencia.save(
        update_fields=[
            "tecnico_asignado",
            "fecha_asignacion",
            "fecha_programada_atencion",
            "hora_programada_atencion",
            "observaciones_internas",
            "estado",
        ]
    )
    marcar_equipo_en_reparacion_por_asignacion(
        equipo=incidencia.equipo,
        usuario=tecnico,
        incidencia_codigo=incidencia.codigo,
    )
    return incidencia


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
    from inventario.services import aplicar_inventario_al_resolver_incidencia

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
    return incidencia


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
        if not equipo_reemplazo.activo or equipo_reemplazo.estado.nombre != "Operativo":
            raise ValidationError("El equipo de reemplazo no está disponible")
        if equipo_reemplazo.disponibilidad != equipo_reemplazo.DISPONIBILIDAD_LIBRE:
            raise ValidationError("El equipo de reemplazo no está libre")
        if Incidencia.objects.filter(
            Q(equipo=equipo_reemplazo) | Q(equipo_reemplazo=equipo_reemplazo),
            estado__name__in=replacement_blocking_states(),
        ).exclude(pk=incidencia.pk).exists():
            raise ValidationError("El equipo de reemplazo ya está en otra incidencia activa")


def reabrir_incidencia_service(incidencia):
    incidencia.fecha_cierre = None
    incidencia.estado = get_estado(Incidencia.ESTADO_REABIERTO)
    incidencia.save(update_fields=["fecha_cierre", "estado"])
    return incidencia


def cerrar_incidencia_service(incidencia, usuario):
    from inventario.services import aplicar_inventario_al_cerrar_incidencia

    transition_incidencia(
        incidencia,
        Incidencia.ESTADO_CERRADO,
        save_fields=["fecha_cierre"],
    )
    incidencia.fecha_cierre = timezone.now()
    incidencia.save(update_fields=["fecha_cierre"])
    aplicar_inventario_al_cerrar_incidencia(incidencia=incidencia, usuario=usuario)
    return incidencia
