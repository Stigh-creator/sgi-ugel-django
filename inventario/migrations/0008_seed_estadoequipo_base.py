from django.db import migrations


ESTADOS_EQUIPO_BASE = [
    "Operativo",
    "En revisión",
    "En reparación",
    "Inoperativo",
    "Dado de baja",
]


def crear_estados_equipo_base(apps, schema_editor):
    EstadoEquipo = apps.get_model("inventario", "EstadoEquipo")
    for nombre in ESTADOS_EQUIPO_BASE:
        EstadoEquipo.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0007_estadoequipo_alter_equipo_estado_and_more"),
    ]

    operations = [
        migrations.RunPython(crear_estados_equipo_base, migrations.RunPython.noop),
    ]
