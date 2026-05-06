from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from inventario.models import Equipo
from tickets.models import Incidencia, ReemplazoEquipoIncidencia


class Command(BaseCommand):
    help = "Ejecuta verificaciones y automatizaciones operativas principales del SGI."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Aplica correcciones seguras además del reporte.")

    def handle(self, *args, **options):
        fix = options["fix"]
        call_command("procesar_sla_incidencias")
        call_command("autocerrar_incidencias_resueltas")
        call_command("verificar_integridad_inventario", fix=fix)
        if fix:
            huerfanos = ReemplazoEquipoIncidencia.objects.select_related("equipo_reemplazo", "area_origen").filter(
                activo=True,
                incidencia__estado__name=Incidencia.ESTADO_CERRADO,
            )
            corregidos = 0
            for reemplazo in huerfanos:
                reemplazo.activo = False
                reemplazo.fecha_fin = timezone.now()
                reemplazo.save(update_fields=["activo", "fecha_fin"])
                equipo = reemplazo.equipo_reemplazo
                if equipo:
                    equipo.disponibilidad = Equipo.DISPONIBILIDAD_LIBRE
                    equipo.origen_ocupacion = None
                    update_fields = ["disponibilidad", "origen_ocupacion", "actualizado_en"]
                    if reemplazo.area_origen_id:
                        equipo.area = reemplazo.area_origen
                        update_fields.append("area")
                    equipo.save(update_fields=update_fields)
                corregidos += 1
            self.stdout.write(f"Reemplazos huérfanos corregidos: {corregidos}.")
        call_command("metricas_operativas_sgi")
        self.stdout.write(self.style.SUCCESS("Integridad global procesada."))
