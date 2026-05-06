from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from auditoria.models import EventoFallido
from tickets.models import Incidencia
from tickets.services import _procesar_evento_incidencia


class Command(BaseCommand):
    help = "Reprocesa eventos fallidos no procesados respetando un límite de intentos."

    def add_arguments(self, parser):
        parser.add_argument("--max-intentos", type=int, default=3)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        max_intentos = options["max_intentos"]
        limit = options["limit"]
        User = get_user_model()
        reprocesados = 0
        fallidos = 0

        eventos = EventoFallido.objects.filter(
            procesado=False,
            intentos__lt=max_intentos,
        ).order_by("fecha")[:limit]

        for registro in eventos:
            payload = registro.payload or {}
            try:
                incidencia = Incidencia.objects.get(pk=payload.get("incidencia_id"))
                actor = None
                if payload.get("actor_id"):
                    actor = User.objects.filter(pk=payload["actor_id"]).first()
                _procesar_evento_incidencia(
                    payload.get("evento") or registro.evento,
                    incidencia,
                    actor=actor,
                    metadata=payload.get("metadata") or {},
                )
                registro.procesado = True
                registro.ultimo_error = ""
                registro.save(update_fields=["procesado", "ultimo_error"])
                reprocesados += 1
            except Exception as exc:
                registro.intentos += 1
                registro.ultimo_error = str(exc)
                registro.error = f"{registro.error}\n[{timezone.now().isoformat()}] {exc}"
                registro.save(update_fields=["intentos", "ultimo_error", "error"])
                fallidos += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Reprocesamiento completado. Procesados: {reprocesados}. Fallidos: {fallidos}."
            )
        )
