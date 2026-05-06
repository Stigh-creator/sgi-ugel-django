from django.core.management.base import BaseCommand
from django.utils import timezone

from tickets.models import Incidencia
from tickets.services import IncidenciaService


class Command(BaseCommand):
    help = "Cierra automáticamente incidencias resueltas cuya fecha de auto-cierre ya venció."

    def handle(self, *args, **options):
        now = timezone.now()
        queryset = Incidencia.objects.select_related("estado", "creador").filter(
            estado__name=Incidencia.ESTADO_RESUELTO,
            fecha_auto_cierre__isnull=False,
            fecha_auto_cierre__lte=now,
            auto_cerrado=False,
        )
        count = 0
        for incidencia in queryset:
            IncidenciaService.cerrar(incidencia.pk, incidencia.creador, auto=True)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Auto-cierre completado. Incidencias cerradas: {count}."))
