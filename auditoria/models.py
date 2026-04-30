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
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    referencia_id = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Auditoría"
        verbose_name_plural = "Auditorías"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.usuario} - {self.modulo} - {self.accion} ({self.fecha_hora})"
