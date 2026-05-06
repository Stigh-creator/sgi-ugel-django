from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone

from tickets.models import EstadoSLA, Incidencia
from tickets.services import POR_VENCER_UMBRAL, emitir_evento_incidencia


class Command(BaseCommand):
    help = "Procesa vencimientos de SLA de respuesta y resolución de incidencias."

    def handle(self, *args, **options):
        now = timezone.now()
        por_vencer_count = 0
        candidatas_por_vencer = Incidencia.objects.select_related("estado", "creador", "tecnico_asignado").filter(
            estado_sla=EstadoSLA.EN_TIEMPO,
            fecha_creacion__isnull=False,
        ).filter(
            (
                models.Q(
                    estado__name__in=[Incidencia.ESTADO_PENDIENTE, Incidencia.ESTADO_ASIGNADO],
                    fecha_limite_respuesta__isnull=False,
                )
                | models.Q(
                    estado__name__in=[Incidencia.ESTADO_EN_PROCESO, Incidencia.ESTADO_REABIERTO],
                    fecha_limite_resolucion__isnull=False,
                )
            )
        )
        for incidencia in candidatas_por_vencer:
            limite = (
                incidencia.fecha_limite_respuesta
                if incidencia.estado.name in [Incidencia.ESTADO_PENDIENTE, Incidencia.ESTADO_ASIGNADO]
                else incidencia.fecha_limite_resolucion
            )
            total = (limite - incidencia.fecha_creacion).total_seconds()
            transcurrido = (now - incidencia.fecha_creacion).total_seconds()
            if total > 0 and transcurrido >= (total * POR_VENCER_UMBRAL) and now < limite:
                incidencia.estado_sla = EstadoSLA.POR_VENCER
                incidencia.save(update_fields=["estado_sla"])
                emitir_evento_incidencia(
                    "incidencia.sla_por_vencer",
                    incidencia,
                    metadata={"tipo_sla": "respuesta" if limite == incidencia.fecha_limite_respuesta else "resolucion", "fecha_limite": limite.isoformat()},
                )
                por_vencer_count += 1

        respuesta = Incidencia.objects.select_related("estado", "creador", "tecnico_asignado").filter(
            estado__name__in=[Incidencia.ESTADO_PENDIENTE, Incidencia.ESTADO_ASIGNADO],
            fecha_limite_respuesta__isnull=False,
            fecha_limite_respuesta__lt=now,
            sla_respuesta_notificado=False,
        )
        respuesta_count = 0
        for incidencia in respuesta:
            incidencia.sla_respuesta_notificado = True
            incidencia.estado_sla = EstadoSLA.RESPUESTA_VENCIDA
            incidencia.escalado = True
            incidencia.save(update_fields=["sla_respuesta_notificado", "estado_sla", "escalado"])
            emitir_evento_incidencia("incidencia.sla_respuesta_vencido", incidencia, metadata={"fecha_limite": incidencia.fecha_limite_respuesta.isoformat()})
            respuesta_count += 1

        resolucion = Incidencia.objects.select_related("estado", "creador", "tecnico_asignado").filter(
            estado__name__in=[Incidencia.ESTADO_EN_PROCESO, Incidencia.ESTADO_REABIERTO],
            fecha_limite_resolucion__isnull=False,
            fecha_limite_resolucion__lt=now,
            sla_resolucion_notificado=False,
        )
        resolucion_count = 0
        for incidencia in resolucion:
            incidencia.sla_resolucion_notificado = True
            incidencia.estado_sla = EstadoSLA.RESOLUCION_VENCIDA
            incidencia.escalado = True
            incidencia.save(update_fields=["sla_resolucion_notificado", "estado_sla", "escalado"])
            emitir_evento_incidencia("incidencia.sla_resolucion_vencido", incidencia, metadata={"fecha_limite": incidencia.fecha_limite_resolucion.isoformat()})
            resolucion_count += 1

        self.stdout.write(self.style.SUCCESS(f"SLA procesado. Por vencer: {por_vencer_count}. Respuesta vencida: {respuesta_count}. Resolución vencida: {resolucion_count}."))
