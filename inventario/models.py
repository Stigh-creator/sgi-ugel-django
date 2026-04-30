from django.db import models
from tickets.models import Area
from tickets.utils.images import process_image
import uuid

def upload_to_fichas(instance, filename):
    ext = filename.split('.')[-1]
    return f"inventario_docs/{uuid.uuid4()}.{ext}"

class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class TipoEquipo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Tipo de Equipo"
        verbose_name_plural = "Tipos de Equipo"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class EstadoEquipo(models.Model):
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name = "Estado de Equipo"
        verbose_name_plural = "Estados de Equipos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Equipo(models.Model):

    codigo_equipo = models.CharField(max_length=50, unique=True)
    nombre_equipo = models.CharField(max_length=100)
    
    # Campos Normalizados
    tipo_equipo = models.ForeignKey(TipoEquipo, on_delete=models.PROTECT, verbose_name="Tipo de Equipo")
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, verbose_name="Marca")

    modelo = models.CharField(max_length=50)
    numero_serie = models.CharField(max_length=100, blank=True, null=True)
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True)
    estado = models.ForeignKey(EstadoEquipo, on_delete=models.PROTECT, verbose_name="Estado")
    observaciones = models.TextField(blank=True, null=True)
    fecha_register = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    foto_estado = models.ImageField(upload_to='equipos/estado/', null=True, blank=True, verbose_name="Foto del Estado")
    ficha_tecnica = models.FileField(upload_to=upload_to_fichas, null=True, blank=True, verbose_name="Ficha Técnica (PDF)")

    class Meta:
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        ordering = ['-fecha_register']

    def save(self, *args, **kwargs):
        if self.activo is False:
            estado_baja = EstadoEquipo.objects.filter(nombre='Dado de baja').first()
            if estado_baja:
                self.estado = estado_baja
        elif self.estado and self.estado.nombre == 'Dado de baja':
            self.activo = False
        elif self.estado and self.estado.nombre in {'Operativo', 'En revisión', 'En reparación', 'Inoperativo'} and self.activo is False:
            self.activo = True
        super().save(*args, **kwargs)
        if self.foto_estado:
            # Redimensión a máx 800px y calidad 70% (según requerimiento)
            process_image(self.foto_estado, size=(800, 800), quality=70)

    def __str__(self):
        return f"{self.codigo_equipo} - {self.nombre_equipo}"

    @property
    def descripcion_fisica(self):
        return self.observaciones or ""


class HistorialEstadoEquipo(models.Model):
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name="historial_estado")
    estado_anterior = models.ForeignKey(EstadoEquipo, on_delete=models.PROTECT, related_name="anteriores")
    estado_nuevo = models.ForeignKey(EstadoEquipo, on_delete=models.PROTECT, related_name="nuevos")
    usuario_que_cambio = models.ForeignKey(
        "tickets.CustomUser",
        on_delete=models.PROTECT,
        related_name="cambios_estado_equipo",
    )
    observacion = models.TextField()
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de Estado de Equipo"
        verbose_name_plural = "Historiales de Estado de Equipos"
        ordering = ["-fecha_registro"]

    def __str__(self):
        return f"{self.equipo.codigo_equipo}: {self.estado_anterior} -> {self.estado_nuevo}"
