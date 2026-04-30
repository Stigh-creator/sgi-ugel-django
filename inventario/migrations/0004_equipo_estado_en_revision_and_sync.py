from django.db import migrations


def sync_equipo_flags(apps, schema_editor):
    Equipo = apps.get_model("inventario", "Equipo")
    for equipo in Equipo.objects.all():
        if not equipo.activo:
            equipo.estado = "Dado de baja"
        elif equipo.estado == "Dado de baja":
            equipo.activo = False
        equipo.save(update_fields=["estado", "activo", "actualizado_en"])


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0003_historialestadoequipo"),
    ]

    operations = [
        migrations.RunPython(sync_equipo_flags, migrations.RunPython.noop),
    ]
