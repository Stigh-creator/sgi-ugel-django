from django.core.management.base import BaseCommand
from django.db.models import Q

from inventario.models import Equipo
from tickets.models import Incidencia


class Command(BaseCommand):
    help = "Verifica equipos ocupados sin origen claro o sin incidencia activa asociada."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Corrige inconsistencias seguras.")

    def handle(self, *args, **options):
        fix = options["fix"]
        estados_activos = [
            Incidencia.ESTADO_PENDIENTE,
            Incidencia.ESTADO_ASIGNADO,
            Incidencia.ESTADO_EN_PROCESO,
            Incidencia.ESTADO_REABIERTO,
            Incidencia.ESTADO_RESUELTO,
        ]
        ocupados = Equipo.objects.filter(
            disponibilidad__in=[Equipo.DISPONIBILIDAD_EN_USO, Equipo.DISPONIBILIDAD_REEMPLAZO_TEMPORAL],
            activo=True,
        )
        fantasmas = ocupados.exclude(
            Q(incidencia__estado__name__in=estados_activos)
            | Q(incidencias_como_reemplazo__estado__name__in=estados_activos)
        ).distinct()
        sin_origen = ocupados.filter(origen_ocupacion__isnull=True)

        fixed = 0
        if fix and sin_origen.exists():
            fixed = sin_origen.update(origen_ocupacion=Equipo.ORIGEN_OCUPACION_ASIGNACION_DIRECTA)
            sin_origen = ocupados.filter(origen_ocupacion__isnull=True)

        if not fantasmas.exists() and not sin_origen.exists():
            suffix = f" Correcciones aplicadas: {fixed}." if fixed else ""
            self.stdout.write(self.style.SUCCESS(f"Inventario consistente: no se detectaron equipos fantasma.{suffix}"))
            return

        self.stdout.write(self.style.WARNING("Inconsistencias detectadas:"))
        if fixed:
            self.stdout.write(self.style.SUCCESS(f" - Corregidos con origen ASIGNACION_DIRECTA: {fixed}"))
        for equipo in fantasmas:
            self.stdout.write(f" - Fantasma: {equipo.codigo_equipo} ({equipo.get_disponibilidad_display()})")
        for equipo in sin_origen:
            self.stdout.write(f" - Sin origen: {equipo.codigo_equipo} ({equipo.get_disponibilidad_display()})")
