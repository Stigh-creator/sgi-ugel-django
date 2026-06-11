from django.core.management import call_command
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Ejecuta verificaciones y automatizaciones operativas principales del SGI."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Aplica correcciones seguras además del reporte.")

    def handle(self, *args, **options):
        fix = options["fix"]
        call_command("procesar_sla_incidencias")
        call_command("autocerrar_incidencias_resueltas")
        call_command("verificar_integridad_inventario", fix=fix)
        call_command("metricas_operativas_sgi")
        self.stdout.write(self.style.SUCCESS("Integridad global procesada."))
