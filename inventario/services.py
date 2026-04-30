from .models import HistorialEstadoEquipo, EstadoEquipo
from auditoria.utils import registrar_auditoria


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
    equipo.activo = nuevo_estado.nombre != "Dado de baja"
    equipo.save(update_fields=["estado", "activo", "actualizado_en"])
    
    registrar_auditoria(
        None, 
        "Inventario", 
        "cambió estado equipo", 
        f"Equipo {equipo.codigo_equipo}: {estado_anterior} -> {nuevo_estado}. Motivo: {observacion}",
        equipo.id
    )
    return historial


def actualizar_estado_equipo_por_incidencia(*, equipo, usuario, incidencia_codigo):
    if not equipo or not equipo.activo or equipo.estado.nombre != "Operativo":
        return None

    nuevo_estado = EstadoEquipo.objects.filter(nombre="En revisión").first()
    if not nuevo_estado:
        return None

    historial = HistorialEstadoEquipo.objects.create(
        equipo=equipo,
        estado_anterior=equipo.estado,
        estado_nuevo=nuevo_estado,
        usuario_que_cambio=usuario,
        observacion=f"Cambio automático por apertura de la incidencia {incidencia_codigo}.",
    )
    equipo.estado = nuevo_estado
    equipo.activo = True
    equipo.save(update_fields=["estado", "activo", "actualizado_en"])
    
    registrar_auditoria(
        None,
        "Inventario",
        "cambió estado equipo",
        f"Equipo {equipo.codigo_equipo}: Operativo -> En revisión. Motivo: Apertura de incidencia {incidencia_codigo}",
        equipo.id
    )
    return historial
