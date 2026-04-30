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
        estado__name__in=[Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO]
    )
    if exclude_incidencia_id:
        queryset = queryset.exclude(pk=exclude_incidencia_id)
    return queryset.count()


def validate_tecnico_capacity(tecnico, *, exclude_incidencia_id=None):
    current_load = get_active_ticket_load_for_user(tecnico, exclude_incidencia_id=exclude_incidencia_id)
    if current_load >= MAX_ACTIVE_TICKETS_PER_TECH:
        raise ValidationError(
            f"{tecnico.get_full_name() or tecnico.username} ya tiene {current_load} tickets activos. "
            f"El máximo permitido es {MAX_ACTIVE_TICKETS_PER_TECH}."
        )
    return current_load


def resolve_active_tab_for_user(user, requested_tab):
    """Normaliza la pestaña solicitada respetando el alcance por rol."""
    default_tab = "asignadas" if user.role != "usuario" else "reportadas"
    return requested_tab if requested_tab in {"asignadas", "reportadas"} else default_tab


def get_visible_incidencias_queryset(user, active_tab):
    queryset = Incidencia.objects.all()
    
    # 1. Trabajador: Solo lo que él reportó
    if user.role == "usuario":
        return queryset.filter(creador_id=user.id), "reportadas"
    
    # 2. Técnico: 
    if user.role == "tecnico":
        if active_tab == "reportadas":
            return queryset.filter(creador_id=user.id), "reportadas"
        return queryset.filter(tecnico_asignado_id=user.id), "asignadas"

    # 3. Administrador: (EL FIX)
    if user.role == "administrador":
        if active_tab == "reportadas":
            # Filtro estricto: Solo lo que el Admin creó manualmente
            return queryset.filter(creador_id=user.id), "reportadas"
        # "Todas" las incidencias del sistema
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
        return queryset.filter(tecnico_asignado__isnull=False).exclude(
            estado__name__in=[Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_CERRADO]
        )
    if estado_nombre == Incidencia.ESTADO_RESUELTO:
        return queryset.filter(estado__name=Incidencia.ESTADO_RESUELTO)
    if estado_nombre == Incidencia.ESTADO_PENDIENTE:
        return queryset.filter(tecnico_asignado__isnull=True, estado__name=Incidencia.ESTADO_PENDIENTE)
    return queryset.filter(estado__id=estado_id)


def available_estado_filters():
    return Estado.objects.exclude(name__in=["En Proceso", "En Espera"]).order_by("name")


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

    if current_state in {Incidencia.ESTADO_RESUELTO, Incidencia.ESTADO_REABIERTO, Incidencia.ESTADO_CERRADO}:
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
        from inventario.services import actualizar_estado_equipo_por_incidencia

        actualizar_estado_equipo_por_incidencia(
            equipo=equipo,
            usuario=incidencia.creador,
            incidencia_codigo=incidencia.codigo,
        )

    return incidencia


def assign_incidencia_service(
    incidencia,
    *,
    tecnico,
    fecha_programada=None,
    hora_programada=None,
    observaciones=None,
):
    validate_tecnico_capacity(tecnico, exclude_incidencia_id=incidencia.pk)
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
    return incidencia


def resolver_incidencia_service(incidencia, tecnico, solucion_aplicada, evidencia=None, evidencia_2=None, evidencia_3=None):
    incidencia.tecnico_asignado = tecnico
    if not incidencia.fecha_asignacion:
        incidencia.fecha_asignacion = timezone.now()
    incidencia.solucion_aplicada = solucion_aplicada
    if evidencia:
        incidencia.evidencia_solucion = evidencia
    if evidencia_2:
        incidencia.evidencia_solucion_2 = evidencia_2
    if evidencia_3:
        incidencia.evidencia_solucion_3 = evidencia_3
    incidencia.estado = get_estado(Incidencia.ESTADO_RESUELTO)
    incidencia.save()
    return incidencia


def reabrir_incidencia_service(incidencia):
    incidencia.fecha_cierre = None
    incidencia.estado = get_estado(Incidencia.ESTADO_REABIERTO)
    incidencia.save(update_fields=["fecha_cierre", "estado"])
    return incidencia


def cerrar_incidencia_service(incidencia, usuario):
    transition_incidencia(
        incidencia,
        Incidencia.ESTADO_CERRADO,
        save_fields=["fecha_cierre"],
    )
    incidencia.fecha_cierre = timezone.now()
    incidencia.save(update_fields=["fecha_cierre"])
    return incidencia
