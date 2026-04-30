import os
import sys
import django
from django.db import transaction, connection

# Configuración del entorno Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gestion_incidencias.settings")
django.setup()

def reset_sequences(table_names):
    """Reinicia los contadores de ID (auto-increment) en SQLite"""
    with connection.cursor() as cursor:
        for table in table_names:
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}';")
    print(f"OK: Secuencias reiniciadas para {len(table_names)} tablas.")

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission
from tickets.models import CustomUser, Area, Estado, Incidencia, IncidenciaImagen, Notificacion, NotificacionUsuario, Comentario
from inventario.models import Marca, TipoEquipo, EstadoEquipo, Equipo, HistorialEstadoEquipo
from auditoria.models import Auditoria

import cargar_maestros

def reset_database():
    print("--- Iniciando proceso de reset critico del sistema ---")
    
    try:
        with transaction.atomic():
            # 1. FASE DE LIMPIEZA TOTAL (Transaccionales)
            print("\n--- Limpiando tablas transaccionales ---")
            
            # Tablas para resetear secuencias
            tables_to_reset = [
                LogEntry._meta.db_table,
                Auditoria._meta.db_table,
                IncidenciaImagen._meta.db_table,
                Comentario._meta.db_table,
                NotificacionUsuario._meta.db_table,
                Notificacion._meta.db_table,
                Incidencia._meta.db_table,
                HistorialEstadoEquipo._meta.db_table,
                Equipo._meta.db_table,
                Estado._meta.db_table,
                Area._meta.db_table,
                Marca._meta.db_table,
                TipoEquipo._meta.db_table,
                EstadoEquipo._meta.db_table,
            ]

            # Auditoría y Logs
            LogEntry.objects.all().delete()
            Auditoria.objects.all().delete()
            print("OK: LogEntry y Auditoria eliminados.")
            
            # Incidencias (Tickets) y relacionados
            IncidenciaImagen.objects.all().delete()
            Comentario.objects.all().delete()
            NotificacionUsuario.objects.all().delete()
            Notificacion.objects.all().delete()
            Incidencia.objects.all().delete()
            print("OK: Incidencias, Comentarios, Imagenes y Notificaciones eliminados.")
            
            # Equipos (Inventario) y relacionados
            HistorialEstadoEquipo.objects.all().delete()
            Equipo.objects.all().delete()
            print("OK: Equipos e Historial de estados eliminados.")
            
            # 2. FASE DE REINICIO DE MAESTROS
            print("\n--- Reiniciando tablas maestras ---")
            
            # Borrar maestros actuales
            Estado.objects.all().delete()
            Area.objects.all().delete()
            Marca.objects.all().delete()
            TipoEquipo.objects.all().delete()
            EstadoEquipo.objects.all().delete()
            print("OK: Tablas maestras (Estado, Area, Marca, TipoEquipo, EstadoEquipo) limpias.")
            
            # 3. REINICIAR IDs (Secuencias)
            print("\n--- Reiniciando contadores de ID (PK = 1) ---")
            reset_sequences(tables_to_reset)
            
            # 4. REPOBLAR MAESTROS
            print("\n--- Repoblando tablas maestras desde cargar_maestros.py ---")
            cargar_maestros.cargar_datos_maestros()
            
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
        "Comentarios": Comentario.objects.count(),
        "Estados": Estado.objects.count(),
        "Areas": Area.objects.count(),
        "Marcas": Marca.objects.count(),
        "Tipos Equipo": TipoEquipo.objects.count(),
        "Estados Equipo": EstadoEquipo.objects.count(),
        "Usuarios (Conservados)": CustomUser.objects.count(),
    }
    
    error = False
    for label, count in counts.items():
        status = "OK"
        if label in ["Incidencias", "Equipos", "Auditoria", "LogEntry", "Comentarios"] and count > 0:
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
