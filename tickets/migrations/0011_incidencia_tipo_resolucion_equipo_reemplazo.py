from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0001_initial"),
        ("tickets", "0010_incidencia_documento_informe_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="incidencia",
            name="prioridad",
            field=models.CharField(
                choices=[
                    ("baja", "Baja"),
                    ("media", "Media"),
                    ("alta", "Alta"),
                    ("critica", "Crítica"),
                ],
                default="media",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="incidencia",
            name="tipo_resolucion",
            field=models.CharField(
                blank=True,
                choices=[
                    ("reparado", "Reparado"),
                    ("reemplazado", "Reemplazado (temporal)"),
                    ("baja", "Dado de baja"),
                    ("derivado", "Derivado / externo"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="incidencia",
            name="equipo_reemplazo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="incidencias_como_reemplazo",
                to="inventario.equipo",
            ),
        ),
    ]
