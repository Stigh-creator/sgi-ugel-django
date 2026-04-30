import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_incidencias.settings')
django.setup()

from tickets.models import Area

def clean_and_load_areas():
    print("--- Borrando todas las areas existentes ---")
    Area.objects.all().delete()
    
    areas_oficiales = [
        # Bloque DIRECCIÓN
        ("Secretaría", "DIRECCIÓN"),
        ("Asesoría Jurídica (CPADD)", "DIRECCIÓN"),
        ("Trámite Documentario", "DIRECCIÓN"),
        
        # Bloque AGP
        ("Secretaría", "AGP"),
        ("Especialistas Inicial", "AGP"),
        ("Especialistas Primaria", "AGP"),
        ("Especialistas Secundaria", "AGP"),
        ("Convivencia Escolar", "AGP"),
        
        # Bloque ADMINISTRACIÓN
        ("Contabilidad", "ADMINISTRACIÓN"),
        ("Tesorería", "ADMINISTRACIÓN"),
        ("Remuneraciones", "ADMINISTRACIÓN"),
        ("Informática", "ADMINISTRACIÓN"),
        ("Almacén", "ADMINISTRACIÓN"),
        ("Personal (Escalafón)", "ADMINISTRACIÓN"),
        
        # Bloque UPDI
        ("Planificación", "UPDI"),
        ("Estadística", "UPDI"),
        ("SIAGIE", "UPDI"),
        ("Infraestructura", "UPDI"),
    ]
    
    print(f"--- Cargando {len(areas_oficiales)} areas oficiales ---")
    for name, sede in areas_oficiales:
        # Usamos update_or_create por seguridad, aunque acabamos de borrar
        Area.objects.create(name=name, sede_principal=sede)
        print(f"Area creada: {name} ({sede})")

    print("\n--- Proceso de limpieza y carga completado exitosamente ---")

if __name__ == "__main__":
    clean_and_load_areas()
