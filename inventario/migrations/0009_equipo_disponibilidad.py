from django.db import migrations, models


def inicializar_disponibilidad(apps, schema_editor):
    Equipo = apps.get_model("inventario", "Equipo")
    Incidencia = apps.get_model("tickets", "Incidencia")

    estados_bloqueantes = ["Pendiente", "Asignado", "En Proceso", "Reabierto", "Resuelto"]
    incidencias = Incidencia.objects.filter(estado__name__in=estados_bloqueantes)
    equipos_ocupados = set(
        incidencias.exclude(equipo_id__isnull=True).values_list("equipo_id", flat=True)
    )
    equipos_ocupados.update(
        incidencias.exclude(equipo_reemplazo_id__isnull=True).values_list("equipo_reemplazo_id", flat=True)
    )

    for equipo in Equipo.objects.select_related("estado"):
        esta_libre = (
            equipo.activo
            and equipo.estado
            and equipo.estado.nombre == "Operativo"
            and equipo.id not in equipos_ocupados
        )
        equipo.disponibilidad = "LIBRE" if esta_libre else "EN_USO"
        equipo.save(update_fields=["disponibilidad"])


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0008_seed_estadoequipo_base"),
        ("tickets", "0011_incidencia_tipo_resolucion_equipo_reemplazo"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipo",
            name="disponibilidad",
            field=models.CharField(
                choices=[("LIBRE", "Libre"), ("EN_USO", "En uso")],
                default="LIBRE",
                max_length=10,
                verbose_name="Disponibilidad",
            ),
        ),
        migrations.RunPython(inicializar_disponibilidad, migrations.RunPython.noop),
    ]
