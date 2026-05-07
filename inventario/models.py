from django.db import models
from django.core.exceptions import ValidationError
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
    DISPONIBILIDAD_LIBRE = "LIBRE"
    DISPONIBILIDAD_EN_USO = "EN_USO"
    DISPONIBILIDAD_REEMPLAZO_TEMPORAL = "REEMPLAZO_TEMPORAL"
    DISPONIBILIDAD_NO_DISPONIBLE = "NO_DISPONIBLE"
    DISPONIBILIDAD_CHOICES = (
        (DISPONIBILIDAD_LIBRE, "Libre"),
        (DISPONIBILIDAD_EN_USO, "En uso"),
        (DISPONIBILIDAD_REEMPLAZO_TEMPORAL, "Reemplazo temporal"),
        (DISPONIBILIDAD_NO_DISPONIBLE, "No disponible"),
    )
    ORIGEN_OCUPACION_MANUAL = "MANUAL"
    ORIGEN_OCUPACION_ASIGNACION_DIRECTA = "ASIGNACION_DIRECTA"
    ORIGEN_OCUPACION_INCIDENCIA = "INCIDENCIA"
    ORIGEN_OCUPACION_REEMPLAZO = "REEMPLAZO"
    ORIGEN_OCUPACION_MANTENIMIENTO = "MANTENIMIENTO"
    ORIGEN_OCUPACION_CHOICES = (
        (ORIGEN_OCUPACION_MANUAL, "Manual"),
        (ORIGEN_OCUPACION_ASIGNACION_DIRECTA, "Asignación directa"),
        (ORIGEN_OCUPACION_INCIDENCIA, "Incidencia"),
        (ORIGEN_OCUPACION_REEMPLAZO, "Reemplazo temporal"),
        (ORIGEN_OCUPACION_MANTENIMIENTO, "Mantenimiento"),
    )

    codigo_equipo = models.CharField(max_length=50, unique=True)
    nombre_equipo = models.CharField(max_length=100)
    
    # Campos Normalizados
    tipo_equipo = models.ForeignKey(TipoEquipo, on_delete=models.PROTECT, verbose_name="Tipo de Equipo")
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, verbose_name="Marca")

    modelo = models.CharField(max_length=50)
    numero_serie = models.CharField(max_length=100, blank=True, null=True)
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True)
    estado = models.ForeignKey(EstadoEquipo, on_delete=models.PROTECT, verbose_name="Estado")
    estado_tecnico = models.ForeignKey(
        EstadoEquipo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipos_estado_tecnico",
        verbose_name="Estado técnico",
    )
    observaciones = models.TextField(blank=True, null=True)
    fecha_register = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    disponibilidad = models.CharField(
        max_length=30,
        choices=DISPONIBILIDAD_CHOICES,
        default=DISPONIBILIDAD_LIBRE,
        verbose_name="Disponibilidad",
    )
    origen_ocupacion = models.CharField(
        max_length=20,
        choices=ORIGEN_OCUPACION_CHOICES,
        null=True,
        blank=True,
        verbose_name="Origen de ocupación",
    )
    foto_estado = models.ImageField(upload_to='equipos/estado/', null=True, blank=True, verbose_name="Foto del Estado")
    ficha_tecnica = models.FileField(upload_to=upload_to_fichas, null=True, blank=True, verbose_name="Ficha Técnica (PDF)")

    class Meta:
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        ordering = ['-fecha_register']
        indexes = [
            models.Index(fields=["disponibilidad"], name="idx_equipo_disponibilidad"),
            models.Index(fields=["estado_tecnico", "disponibilidad"], name="idx_equipo_estado_disp"),
        ]

    def clean(self):
        super().clean()
        if self.disponibilidad != self.DISPONIBILIDAD_LIBRE and not self.origen_ocupacion:
            raise ValidationError({"origen_ocupacion": "Debe especificar origen de ocupación cuando el equipo no está libre."})

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)

        if self.estado_id and self.estado_tecnico_id != self.estado_id:
            self.estado_tecnico = self.estado
            if update_fields is not None:
                update_fields.add("estado_tecnico")

        if self.activo is False:
            estado_baja = EstadoEquipo.objects.filter(nombre='Dado de baja').first()
            if estado_baja:
                self.estado = estado_baja
                self.estado_tecnico = estado_baja
                if update_fields is not None:
                    update_fields.update({"estado", "estado_tecnico"})
            self.disponibilidad = self.DISPONIBILIDAD_NO_DISPONIBLE
            self.origen_ocupacion = self.origen_ocupacion or self.ORIGEN_OCUPACION_MANUAL
            if update_fields is not None:
                update_fields.update({"disponibilidad", "origen_ocupacion"})
        elif self.estado and self.estado.nombre == 'Dado de baja':
            self.activo = False
            self.disponibilidad = self.DISPONIBILIDAD_NO_DISPONIBLE
            self.origen_ocupacion = self.origen_ocupacion or self.ORIGEN_OCUPACION_MANUAL
            if update_fields is not None:
                update_fields.update({"activo", "disponibilidad", "origen_ocupacion"})
        elif self.estado_tecnico and self.estado_tecnico.nombre == 'Inoperativo':
            self.disponibilidad = self.DISPONIBILIDAD_NO_DISPONIBLE
            self.origen_ocupacion = self.origen_ocupacion or self.ORIGEN_OCUPACION_MANUAL
            if update_fields is not None:
                update_fields.update({"disponibilidad", "origen_ocupacion"})
        elif self.estado_tecnico and self.estado_tecnico.nombre in {'Operativo', 'Observación', 'En revisión', 'En reparación', 'Inoperativo'} and self.activo is False:
            self.activo = True
            if update_fields is not None:
                update_fields.add("activo")
        if self.disponibilidad == self.DISPONIBILIDAD_LIBRE:
            self.origen_ocupacion = None
            if update_fields is not None:
                update_fields.add("origen_ocupacion")
        elif not self.origen_ocupacion:
            raise ValidationError("Debe especificar origen de ocupación cuando el equipo no está libre.")
        if update_fields is not None:
            kwargs["update_fields"] = list(update_fields)
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
