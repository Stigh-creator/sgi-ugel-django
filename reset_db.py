import os
import sys
import django
from django.db import transaction, connection
from django.apps import apps
from django.core.management.color import no_style

# Configuración del entorno Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gestion_incidencias.settings")
django.setup()

def reset_sequences_for_apps(app_labels):
    """Reajusta secuencias de IDs para el motor actual de base de datos."""
    models = []
    for app_label in app_labels:
        models.extend(apps.get_app_config(app_label).get_models())
    sql_statements = connection.ops.sequence_reset_sql(no_style(), models)
    with connection.cursor() as cursor:
        for statement in sql_statements:
            cursor.execute(statement)
    print(f"OK: Secuencias reajustadas para {len(sql_statements)} tablas.")

from django.contrib.admin.models import LogEntry
from django.contrib.sessions.models import Session
from tickets.models import CustomUser, Area, Estado, Incidencia, IncidenciaImagen, Notificacion, NotificacionUsuario, Comentario, ReemplazoEquipoIncidencia, SLAConfiguracion, MetricaDiaria
from inventario.models import Marca, TipoEquipo, EstadoEquipo, Equipo, HistorialEstadoEquipo, Repuesto, MantenimientoPreventivo
from auditoria.models import Auditoria, EventoFallido

import cargar_maestros

def reset_database():
    print("--- Iniciando proceso de reset critico del sistema ---")
    
    try:
        with transaction.atomic():
            # 1. FASE DE LIMPIEZA TOTAL (Transaccionales)
            print("\n--- Limpiando tablas transaccionales ---")
            
            # Auditoría y Logs
            LogEntry.objects.all().delete()
            Session.objects.all().delete()
            Auditoria.objects.all().delete()
            EventoFallido.objects.all().delete()
            print("OK: LogEntry, sesiones, Auditoria y eventos fallidos eliminados.")
            
            # Incidencias (Tickets) y relacionados
            IncidenciaImagen.objects.all().delete()
            ReemplazoEquipoIncidencia.objects.all().delete()
            Comentario.objects.all().delete()
            NotificacionUsuario.objects.all().delete()
            Notificacion.objects.all().delete()
            Incidencia.objects.all().delete()
            MetricaDiaria.objects.all().delete()
            print("OK: Incidencias, Comentarios, Imagenes, Notificaciones y metricas eliminados.")
            
            # Equipos (Inventario) y relacionados
            MantenimientoPreventivo.objects.all().delete()
            HistorialEstadoEquipo.objects.all().delete()
            Equipo.objects.all().delete()
            Repuesto.objects.all().delete()
            print("OK: Equipos, Historial de estados, Repuestos y Mantenimientos eliminados.")

            # Usuarios
            CustomUser.objects.all().delete()
            print("OK: Usuarios eliminados.")
            
            # 2. FASE DE REINICIO DE MAESTROS
            print("\n--- Reiniciando tablas maestras ---")
            
            # Borrar maestros actuales
            Estado.objects.all().delete()
            Area.objects.all().delete()
            Marca.objects.all().delete()
            TipoEquipo.objects.all().delete()
            EstadoEquipo.objects.all().delete()
            SLAConfiguracion.objects.all().delete()
            print("OK: Tablas maestras (Estado, Area, Marca, TipoEquipo, EstadoEquipo, SLA) limpias.")
            
            # 3. REPOBLAR MAESTROS
            print("\n--- Repoblando tablas maestras desde cargar_maestros.py ---")
            cargar_maestros.cargar_datos_maestros()

            # 4. REINICIAR IDs (Secuencias)
            print("\n--- Reajustando contadores de ID ---")
            reset_sequences_for_apps(["tickets", "inventario", "auditoria"])
            
            print("\n--- Proceso de reset completado con exito ---")
            
    except Exception as e:
        print(f"\nERROR durante el reset: {e}")
        sys.exit(1)

def verificar_estado():
    print("\n--- Verificando estado final del sistema ---")
    
    counts = {
        "Incidencias": Incidencia.objects.count(),
        "Equipos": Equipo.objects.count(),
        "Auditoria": Auditoria.objects.count(),
        "LogEntry": LogEntry.objects.count(),
        "Sesiones": Session.objects.count(),
        "Comentarios": Comentario.objects.count(),
        "Estados": Estado.objects.count(),
        "Areas": Area.objects.count(),
        "Marcas": Marca.objects.count(),
        "Tipos Equipo": TipoEquipo.objects.count(),
        "Estados Equipo": EstadoEquipo.objects.count(),
        "SLA": SLAConfiguracion.objects.count(),
        "Usuarios": CustomUser.objects.count(),
    }
    
    error = False
    for label, count in counts.items():
        status = "OK"
        if label in ["Incidencias", "Equipos", "Auditoria", "LogEntry", "Sesiones", "Comentarios", "Usuarios"] and count > 0:
            status = "ERROR (Debe ser 0)"
            error = True
        print(f"   - {label}: {count} [{status}]")
    
    if not error:
        print("\nOK: Verificacion exitosa: El sistema esta limpio y listo para usar.")
    else:
        print("\nERROR: Verificacion fallida: Algunos registros transaccionales persisten.")

if __name__ == "__main__":
    reset_database()
    verificar_estado()
