from django.db import migrations, models


def populate_incidencia_codes(apps, schema_editor):
    Incidencia = apps.get_model("tickets", "Incidencia")
    for incidencia in Incidencia.objects.all().order_by("pk"):
        year = incidencia.fecha_creacion.year if incidencia.fecha_creacion else 2026
        incidencia.codigo = f"INC-{year}-{incidencia.pk:04d}"
        if incidencia.tecnico_asignado_id and incidencia.fecha_asignacion is None:
            incidencia.fecha_asignacion = incidencia.fecha_creacion
        incidencia.save(update_fields=["codigo", "fecha_asignacion"])


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0005_alter_area_options_alter_area_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="incidencia",
            name="codigo",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="incidencia",
            name="fecha_asignacion",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(populate_incidencia_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="incidencia",
            name="codigo",
            field=models.CharField(blank=True, max_length=20, unique=True),
        ),
    ]
