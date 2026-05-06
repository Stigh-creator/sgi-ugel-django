from django.core.management.base import BaseCommand

from tickets.services import crear_snapshot_metricas


class Command(BaseCommand):
    help = "Guarda un snapshot diario de métricas operativas del SGI."

    def handle(self, *args, **options):
        snapshot = crear_snapshot_metricas()
        self.stdout.write(
            self.style.SUCCESS(
                f"Snapshot de métricas guardado para {snapshot.fecha}: "
                f"abiertos={snapshot.tickets_abiertos}, cerrados={snapshot.tickets_cerrados}, "
                f"SLA vencidos={snapshot.sla_vencidos}, SLA por vencer={snapshot.sla_por_vencer}."
            )
        )
