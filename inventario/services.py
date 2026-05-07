from .models import HistorialEstadoEquipo, EstadoEquipo
from auditoria.utils import registrar_auditoria
from tickets.models import ReemplazoEquipoIncidencia
from django.utils import timezone

ESTADO_OPERATIVO = "Operativo"
ESTADO_OBSERVACION = "Observación"
ESTADO_EN_REPARACION = "En reparación"
ESTADO_INOPERATIVO = "Inoperativo"
ESTADO_BAJA = "Dado de baja"


def get_estado_equipo(nombre):
    estado, _ = EstadoEquipo.objects.get_or_create(nombre=nombre)
    return estado


def registrar_cambio_manual_estado_equipo(*, equipo, nuevo_estado, usuario, observacion):
    estado_anterior = equipo.estado
    if estado_anterior == nuevo_estado:
        return None

    historial = HistorialEstadoEquipo.objects.create(
        equipo=equipo,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado,
        usuario_que_cambio=usuario,
        observacion=observacion.strip(),
    )
    equipo.estado = nuevo_estado
    equipo.estado_tecnico = nuevo_estado
    equipo.activo = nuevo_estado.nombre != "Dado de baja"
    if nuevo_estado.nombre in {ESTADO_INOPERATIVO, ESTADO_BAJA}:
        equipo.disponibilidad = equipo.DISPONIBILIDAD_NO_DISPONIBLE
        equipo.origen_ocupacion = equipo.ORIGEN_OCUPACION_MANUAL
    equipo.save(update_fields=["estado", "estado_tecnico", "activo", "disponibilidad", "origen_ocupacion", "actualizado_en"])
    
    registrar_auditoria(
        None, 
        "Inventario", 
        "cambió estado equipo", 
        f"Equipo {equipo.codigo_equipo}: {estado_anterior} -> {nuevo_estado}. Motivo: {observacion}. "
        f"equipo_id={equipo.id}; usuario_id={usuario.id if usuario else 'sistema'}; origen=Administración.",
        equipo.id,
        metadata={
            "equipo_id": equipo.id,
            "estado_anterior": str(estado_anterior),
            "estado_nuevo": str(nuevo_estado),
            "usuario_id": usuario.id if usuario else None,
            "origen": "Administración",
        },
        actor=usuario,
    )
    return historial


def cambiar_estado_equipo_por_incidencia(*, equipo, estado_nombre, usuario, incidencia_codigo, motivo):
    if not equipo:
        return None

    nuevo_estado = get_estado_equipo(estado_nombre)
    estado_anterior = equipo.estado
    if estado_anterior and estado_anterior.nombre == ESTADO_BAJA and nuevo_estado.nombre != ESTADO_BAJA:
        return None
    if estado_anterior == nuevo_estado:
        return None

    historial = HistorialEstadoEquipo.objects.create(
        equipo=equipo,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado,
        usuario_que_cambio=usuario,
        observacion=f"{motivo} Incidencia {incidencia_codigo}.",
    )
    equipo.estado = nuevo_estado
    equipo.estado_tecnico = nuevo_estado
    equipo.activo = nuevo_estado.nombre != ESTADO_BAJA
    if nuevo_estado.nombre in {ESTADO_INOPERATIVO, ESTADO_BAJA}:
        equipo.disponibilidad = equipo.DISPONIBILIDAD_NO_DISPONIBLE
        equipo.origen_ocupacion = equipo.ORIGEN_OCUPACION_INCIDENCIA
    equipo.save(update_fields=["estado", "estado_tecnico", "activo", "disponibilidad", "origen_ocupacion", "actualizado_en"])

    registrar_auditoria(
        None,
        "Inventario",
        "cambió estado equipo",
        f"Equipo {equipo.codigo_equipo}: {estado_anterior} -> {nuevo_estado}. Motivo: {motivo} Incidencia {incidencia_codigo}. "
        f"equipo_id={equipo.id}; usuario_id={usuario.id if usuario else 'sistema'}; origen=Incidencia.",
        equipo.id,
        metadata={
            "equipo_id": equipo.id,
            "estado_anterior": str(estado_anterior),
            "estado_nuevo": str(nuevo_estado),
            "usuario_id": usuario.id if usuario else None,
            "incidencia_codigo": incidencia_codigo,
            "origen": "Incidencia",
        },
        actor=usuario,
    )
    return historial


def registrar_reemplazo_temporal_por_incidencia(*, incidencia, usuario):
    reemplazo = incidencia.equipo_reemplazo
    if not reemplazo:
        return None

    area_anterior = reemplazo.area
    area_nueva = incidencia.area
    area_anterior_nombre = area_anterior.name if area_anterior else "Sin área"
    area_nueva_nombre = area_nueva.name if area_nueva else "Sin área"
    equipo_original = incidencia.equipo
    equipo_original_codigo = equipo_original.codigo_equipo if equipo_original else "equipo no institucional"

    if area_anterior_id := getattr(area_anterior, "id", None):
        area_cambia = area_anterior_id != getattr(area_nueva, "id", None)
    else:
        area_cambia = area_nueva is not None

    if area_cambia:
        reemplazo.area = area_nueva
    reemplazo.disponibilidad = reemplazo.DISPONIBILIDAD_REEMPLAZO_TEMPORAL
    reemplazo.origen_ocupacion = reemplazo.ORIGEN_OCUPACION_REEMPLAZO
    update_fields = ["disponibilidad", "origen_ocupacion", "actualizado_en"]
    if area_cambia:
        update_fields.append("area")
    reemplazo.save(update_fields=update_fields)
    ReemplazoEquipoIncidencia.objects.update_or_create(
        incidencia=incidencia,
        equipo_reemplazo=reemplazo,
        activo=True,
        defaults={
            "equipo_original": equipo_original,
            "area_origen": area_anterior,
            "area_destino": area_nueva,
            "usuario": usuario,
            "motivo": f"Reemplazo temporal por incidencia {incidencia.codigo}.",
            "metadata": {
                "incidencia_id": incidencia.id,
                "codigo": incidencia.codigo,
                "equipo_original_id": getattr(equipo_original, "id", None),
                "equipo_reemplazo_id": reemplazo.id,
            },
        },
    )

    descripcion_area = (
        f"Área actualizada de {area_anterior_nombre} a {area_nueva_nombre}."
        if area_cambia
        else f"Permanece en el área {area_nueva_nombre}."
    )
    registrar_auditoria(
        None,
        "Inventario",
        "registró reemplazo temporal",
        (
            f"Equipo {reemplazo.codigo_equipo} usado como reemplazo temporal en la incidencia "
            f"{incidencia.codigo} para cubrir a {equipo_original_codigo}. {descripcion_area} "
            f"Acción realizada por {usuario.get_full_name() or usuario.username if usuario else 'Sistema'}."
        ),
        reemplazo.id,
        metadata={
            "incidencia_id": incidencia.id,
            "codigo": incidencia.codigo,
            "equipo_original_id": getattr(equipo_original, "id", None),
            "equipo_reemplazo_id": reemplazo.id,
            "area_origen_id": getattr(area_anterior, "id", None),
            "area_destino_id": getattr(area_nueva, "id", None),
            "origen": "Incidencia",
        },
        actor=usuario,
    )
    return reemplazo


def actualizar_estado_equipo_por_incidencia(*, equipo, usuario, incidencia_codigo):
    if not equipo or not equipo.activo or equipo.estado_tecnico.nombre != ESTADO_OPERATIVO:
        return None
    return cambiar_estado_equipo_por_incidencia(
        equipo=equipo,
        estado_nombre=ESTADO_OBSERVACION,
        usuario=usuario,
        incidencia_codigo=incidencia_codigo,
        motivo="Apertura de incidencia.",
    )


def marcar_equipo_en_reparacion_por_asignacion(*, equipo, usuario, incidencia_codigo):
    if not equipo or not equipo.activo or equipo.estado_tecnico.nombre == ESTADO_BAJA:
        return None
    return cambiar_estado_equipo_por_incidencia(
        equipo=equipo,
        estado_nombre=ESTADO_EN_REPARACION,
        usuario=usuario,
        incidencia_codigo=incidencia_codigo,
        motivo="Asignación de especialista.",
    )


def aplicar_inventario_al_resolver_incidencia(*, incidencia, usuario):
    equipo = incidencia.equipo
    if incidencia.tipo_resolucion == incidencia.RESOLUCION_REEMPLAZADO and incidencia.equipo_reemplazo:
        registrar_reemplazo_temporal_por_incidencia(incidencia=incidencia, usuario=usuario)

    if not equipo:
        return []

    cambios = []
    if incidencia.tipo_resolucion == incidencia.RESOLUCION_REPARADO:
        cambio = cambiar_estado_equipo_por_incidencia(
            equipo=equipo,
            estado_nombre=ESTADO_EN_REPARACION,
            usuario=usuario,
            incidencia_codigo=incidencia.codigo,
            motivo="Resolución técnica marcada como reparado; permanece en reparación hasta cierre.",
        )
        if cambio:
            cambios.append(cambio)
    elif incidencia.tipo_resolucion == incidencia.RESOLUCION_REEMPLAZADO:
        cambio = cambiar_estado_equipo_por_incidencia(
            equipo=equipo,
            estado_nombre=ESTADO_INOPERATIVO,
            usuario=usuario,
            incidencia_codigo=incidencia.codigo,
            motivo="Resolución técnica con reemplazo temporal.",
        )
        if cambio:
            cambios.append(cambio)
        if incidencia.equipo_reemplazo:
            cambio = cambiar_estado_equipo_por_incidencia(
                equipo=incidencia.equipo_reemplazo,
                estado_nombre=ESTADO_OPERATIVO,
                usuario=usuario,
                incidencia_codigo=incidencia.codigo,
                motivo="Equipo habilitado como reemplazo temporal.",
            )
            if cambio:
                cambios.append(cambio)
    elif incidencia.tipo_resolucion == incidencia.RESOLUCION_BAJA:
        cambio = cambiar_estado_equipo_por_incidencia(
            equipo=equipo,
            estado_nombre=ESTADO_BAJA,
            usuario=usuario,
            incidencia_codigo=incidencia.codigo,
            motivo="Resolución técnica indica baja definitiva.",
        )
        if cambio:
            cambios.append(cambio)
    return cambios


def aplicar_inventario_al_cerrar_incidencia(*, incidencia, usuario):
    cerrar_reemplazos_temporales_por_incidencia(incidencia=incidencia, usuario=usuario)
    if not incidencia.equipo or incidencia.tipo_resolucion != incidencia.RESOLUCION_REPARADO:
        return None
    return cambiar_estado_equipo_por_incidencia(
        equipo=incidencia.equipo,
        estado_nombre=ESTADO_OPERATIVO,
        usuario=usuario,
        incidencia_codigo=incidencia.codigo,
        motivo="Cierre confirmado por solicitante tras reparación.",
    )


def cerrar_reemplazos_temporales_por_incidencia(*, incidencia, usuario):
    cerrados = []
    reemplazos = ReemplazoEquipoIncidencia.objects.select_related("equipo_reemplazo", "area_origen").filter(
        incidencia=incidencia,
        activo=True,
    )
    for reemplazo in reemplazos:
        equipo = reemplazo.equipo_reemplazo
        reemplazo.activo = False
        reemplazo.fecha_fin = timezone.now()
        reemplazo.save(update_fields=["activo", "fecha_fin"])
        if equipo:
            equipo.disponibilidad = equipo.DISPONIBILIDAD_LIBRE
            equipo.origen_ocupacion = None
            if reemplazo.area_origen_id:
                equipo.area = reemplazo.area_origen
                equipo.save(update_fields=["disponibilidad", "origen_ocupacion", "area", "actualizado_en"])
            else:
                equipo.save(update_fields=["disponibilidad", "origen_ocupacion", "actualizado_en"])
            registrar_auditoria(
                None,
                "Inventario",
                "cerró reemplazo temporal",
                (
                    f"Equipo {equipo.codigo_equipo} liberado como reemplazo temporal "
                    f"al cerrar la incidencia {incidencia.codigo}."
                ),
                equipo.id,
                metadata={
                    "incidencia_id": incidencia.id,
                    "codigo": incidencia.codigo,
                    "reemplazo_id": reemplazo.id,
                    "equipo_reemplazo_id": equipo.id,
                    "origen": "Incidencia",
                },
                actor=usuario,
            )
        cerrados.append(reemplazo)
    return cerrados
