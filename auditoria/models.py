from django.db import models
from django.conf import settings

class Auditoria(models.Model):
    MODULO_CHOICES = (
        ('Usuarios', 'Usuarios'),
        ('Inventario', 'Inventario'),
        ('Incidencias', 'Incidencias'),
        ('Sistema', 'Sistema'),
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    modulo = models.CharField(max_length=50, choices=MODULO_CHOICES)
    accion = models.CharField(max_length=100)
    descripcion = models.TextField()
    evento = models.CharField(max_length=100, null=True, blank=True)
    version_evento = models.PositiveIntegerField(default=1)
    hash_evento = models.CharField(max_length=64, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    referencia_id = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Auditoría"
        verbose_name_plural = "Auditorías"
        ordering = ['-fecha_hora']
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "hash_evento"],
                name="uq_auditoria_evento_hash",
            )
        ]

    def __str__(self):
        return f"{self.usuario} - {self.modulo} - {self.accion} ({self.fecha_hora})"


class EventoFallido(models.Model):
    evento = models.CharField(max_length=100)
    version_evento = models.PositiveIntegerField(default=1)
    payload = models.JSONField(default=dict, blank=True)
    error = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    procesado = models.BooleanField(default=False)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "Evento fallido"
        verbose_name_plural = "Eventos fallidos"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["evento", "procesado"]),
            models.Index(fields=["procesado", "intentos"]),
            models.Index(fields=["fecha"]),
        ]

    def __str__(self):
        return f"{self.evento} v{self.version_evento} - {self.fecha}"
