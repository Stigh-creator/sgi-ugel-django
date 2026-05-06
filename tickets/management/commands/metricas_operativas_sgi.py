from django.core.management.base import BaseCommand

from tickets.services import obtener_metricas_operativas


class Command(BaseCommand):
    help = "Muestra métricas operativas básicas para controlar bloqueos del SGI."

    def handle(self, *args, **options):
        metricas = obtener_metricas_operativas()
        self.stdout.write("Métricas operativas SGI:")
        for nombre, valor in metricas.items():
            self.stdout.write(f" - {nombre}: {valor}")
