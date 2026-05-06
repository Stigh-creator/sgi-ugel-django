import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gestion_incidencias.settings")
django.setup()

from inventario.models import Marca, TipoEquipo, EstadoEquipo
from tickets.models import Area, Estado, Incidencia, SLAConfiguracion


ESTADOS_BASE = list(Incidencia.FLUJO_ESTADOS)

AREAS_BASE = [
    {"sede_principal": "DIRECCIÓN", "name": "Secretaría"},
    {"sede_principal": "DIRECCIÓN", "name": "Asesoría Jurídica (CPADD)"},
    {"sede_principal": "DIRECCIÓN", "name": "Trámite Documentario"},
    {"sede_principal": "AGP", "name": "Secretaría"},
    {"sede_principal": "AGP", "name": "Especialistas Inicial"},
    {"sede_principal": "AGP", "name": "Especialistas Primaria"},
    {"sede_principal": "AGP", "name": "Especialistas Secundaria"},
    {"sede_principal": "AGP", "name": "Convivencia Escolar"},
    {"sede_principal": "ADMINISTRACIÓN", "name": "Contabilidad"},
    {"sede_principal": "ADMINISTRACIÓN", "name": "Tesorería"},
    {"sede_principal": "ADMINISTRACIÓN", "name": "Remuneraciones"},
    {"sede_principal": "ADMINISTRACIÓN", "name": "Informática"},
    {"sede_principal": "ADMINISTRACIÓN", "name": "Almacén"},
    {"sede_principal": "ADMINISTRACIÓN", "name": "Personal (Escalafón)"},
    {"sede_principal": "UPDI", "name": "Planificación"},
    {"sede_principal": "UPDI", "name": "Estadística"},
    {"sede_principal": "UPDI", "name": "SIAGIE"},
    {"sede_principal": "UPDI", "name": "Infraestructura"},
]

MARCAS_BASE = [
    "HP",
    "Lenovo",
    "Dell",
    "Advance",
    "Epson",
    "Canon",
    "Brother",
    "Kyocera",
    "Cisco",
    "TP-Link",
    "D-Link",
    "LG",
    "Samsung",
    "APC",
    "Yealink",
    "Sony",
    "Hikvision",
    "Logitech",
    "HyperX",
    "Western Digital",
    "Seagate",
    "Kingston",
    "Genérico / Otro",
]

TIPOS_EQUIPO_BASE = [
    "Computadora de Escritorio (PC)",
    "Laptop",
    "Impresora / Multifuncional",
    "Monitor",
    "Escáner",
    "Proyector Multimedia",
    "Switch / Router / Access Point",
    "Teléfono IP",
    "Servidor",
    "UPS / Estabilizador",
    "Webcam",
    "Auriculares / Headset",
    "Cámara de Seguridad",
    "Disco Duro Externo",
]

ESTADOS_EQUIPO_BASE = [
    'Operativo',
    'Observación',
    'En revisión',
    'En reparación',
    'Inoperativo',
    'Dado de baja',
]

SLA_BASE = [
    {"prioridad": Incidencia.PRIORIDAD_BAJA, "respuesta": 480, "resolucion": 4320, "auto_cierre": 96},
    {"prioridad": Incidencia.PRIORIDAD_MEDIA, "respuesta": 240, "resolucion": 1440, "auto_cierre": 72},
    {"prioridad": Incidencia.PRIORIDAD_ALTA, "respuesta": 120, "resolucion": 480, "auto_cierre": 48},
    {"prioridad": Incidencia.PRIORIDAD_CRITICA, "respuesta": 30, "resolucion": 240, "auto_cierre": 24},
]

def cargar_estados():
    print("\n--- Cargando Estados ---")
    for nombre in ESTADOS_BASE:
        _, created = Estado.objects.get_or_create(name=nombre)
        print(f"{'[NUEVO]' if created else '[EXISTE]'} Estado: {nombre}")


def cargar_areas():
    print("\n--- Cargando Areas ---")
    areas_map = {}
    for data in AREAS_BASE:
        area, created = Area.objects.get_or_create(
            sede_principal=data["sede_principal"],
            name=data["name"],
        )
        areas_map[(data["sede_principal"], data["name"])] = area
        print(f"{'[NUEVO]' if created else '[EXISTE]'} Area: {area}")
    return areas_map


def cargar_marcas():
    print("\n--- Cargando Marcas ---")
    marcas_map = {}
    for nombre in MARCAS_BASE:
        marca, created = Marca.objects.get_or_create(nombre=nombre)
        marcas_map[nombre] = marca
        print(f"{'[NUEVO]' if created else '[EXISTE]'} Marca: {nombre}")
    return marcas_map


def cargar_tipos_equipo():
    print("\n--- Cargando Tipos de Equipo ---")
    tipos_map = {}
    for nombre in TIPOS_EQUIPO_BASE:
        tipo, created = TipoEquipo.objects.get_or_create(nombre=nombre)
        tipos_map[nombre] = tipo
        print(f"{'[NUEVO]' if created else '[EXISTE]'} Tipo: {nombre}")
    return tipos_map


def cargar_estados_equipo():
    print("\n--- Cargando Estados de Equipo ---")
    for nombre in ESTADOS_EQUIPO_BASE:
        _, created = EstadoEquipo.objects.get_or_create(nombre=nombre)
        print(f"{'[NUEVO]' if created else '[EXISTE]'} Estado Equipo: {nombre}")


def cargar_sla_configuracion():
    print("\n--- Cargando Configuracion SLA ---")
    for data in SLA_BASE:
        sla, created = SLAConfiguracion.objects.update_or_create(
            prioridad=data["prioridad"],
            categoria=None,
            defaults={
                "tiempo_respuesta_minutos": data["respuesta"],
                "tiempo_resolucion_minutos": data["resolucion"],
                "auto_cierre_horas": data["auto_cierre"],
                "activo": True,
            },
        )
        print(f"{'[NUEVO]' if created else '[ACTUALIZADO]'} SLA: {sla}")


def cargar_datos_maestros():
    cargar_estados()
    cargar_areas()
    cargar_marcas()
    cargar_tipos_equipo()
    cargar_estados_equipo()
    cargar_sla_configuracion()


if __name__ == "__main__":
    cargar_datos_maestros()
    print("\n--- Carga de datos iniciales finalizada con exito ---")
