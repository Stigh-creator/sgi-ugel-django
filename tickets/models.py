import os
import uuid
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

def unique_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    # Determinar el subdirectorio según la instancia
    if isinstance(instance, CustomUser):
        return os.path.join('perfiles', filename)
    elif isinstance(instance, Incidencia):
        if 'imagen_adjunta' in instance.__dict__: # No es muy fiable así, mejor pasar carpeta
             return os.path.join('incidencias', filename)
    return os.path.join('uploads', filename)

def upload_to_perfiles(instance, filename):
    ext = filename.split('.')[-1]
    return f"perfiles/{uuid.uuid4()}.{ext}"

def upload_to_incidencias(instance, filename):
    ext = filename.split('.')[-1]
    return f"incidencias/{uuid.uuid4()}.{ext}"

def upload_to_soluciones(instance, filename):
    ext = filename.split('.')[-1]
    return f"soluciones/{uuid.uuid4()}.{ext}"

def upload_to_adicionales(instance, filename):
    ext = filename.split('.')[-1]
    return f"adicionales/{uuid.uuid4()}.{ext}"

def upload_to_comentarios(instance, filename):
    ext = filename.split('.')[-1]
    return f"comentarios/{uuid.uuid4()}.{ext}"

def upload_to_informes(instance, filename):
    ext = filename.split('.')[-1]
    return f"pdf_incidencias/{uuid.uuid4()}.{ext}"

from .utils.images import process_image

nombre_valido = RegexValidator(
    regex=r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$',
    message='Solo se permiten letras, espacios, tildes y la letra "ñ".'
)

dni_valido = RegexValidator(
    regex=r'^\d{8}$',
    message='El DNI debe contener exactamente 8 dígitos numéricos.'
)

telefono_valido = RegexValidator(
    regex=r'^\d{9}$',
    message='El teléfono debe contener exactamente 9 dígitos.'
)

email_valido = EmailValidator(message="Ingrese un correo válido con el formato ejemplo@dominio.com.")

class CustomUser(AbstractUser):
    ONLINE_THRESHOLD_SECONDS = 300

    ROLE_CHOICES = (
        ("usuario", "Usuario (Trabajador)"),
        ("tecnico", "Técnico"),
        ("administrador", "Administrador/Ingeniero TI"),
    )
    
    first_name = models.CharField("First name", max_length=150, validators=[nombre_valido])
    last_name = models.CharField("Last name", max_length=150, validators=[nombre_valido])
    username = models.CharField("DNI / Username", max_length=150, unique=True, validators=[dni_valido], help_text="8 dígitos del DNI.")
    email = models.EmailField(blank=True, null=True, validators=[email_valido])

    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default="usuario")
    telefono = models.CharField(max_length=9, validators=[telefono_valido])
    area = models.ForeignKey("Area", on_delete=models.SET_NULL, null=True, blank=True)
    foto = models.ImageField(upload_to=upload_to_perfiles, null=True, blank=True)
    last_password_change = models.DateTimeField(default=timezone.now)
    must_change_password = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
            if CustomUser.objects.filter(email__iexact=self.email).exclude(pk=self.pk).exists():
                raise ValidationError({"email": "Este correo electrónico ya está en uso por otro usuario."})
        if self.telefono:
            if CustomUser.objects.filter(telefono=self.telefono).exclude(pk=self.pk).exists():
                raise ValidationError({"telefono": "Este teléfono ya está en uso por otro usuario."})

    @property
    def cambio_clave_pendiente(self):
        return self.must_change_password

    @cambio_clave_pendiente.setter
    def cambio_clave_pendiente(self, value):
        self.must_change_password = value

    @property
    def is_online(self):
        if not self.last_seen:
            return False
        return (timezone.now() - self.last_seen).total_seconds() < self.ONLINE_THRESHOLD_SECONDS

    @property
    def es_tecnico(self):
        return self.role == "tecnico"

    @property
    def es_admin(self):
        return self.role == "administrador"

    @property
    def es_usuario(self):
        return self.role == "usuario"

    @property
    def role_short_label(self):
        return {
            "administrador": "Administrador",
            "tecnico": "Técnico TI",
            "usuario": "Trabajador",
        }.get(self.role, "Usuario")

    @property
    def role_badge_class(self):
        return {
            "administrador": "role-admin-soft",
            "tecnico": "role-tech-soft",
            "usuario": "role-user-soft",
        }.get(self.role, "role-user-soft")

    @property
    def short_display_name(self):
        full_name = self.first_name.strip() or self.username
        return full_name

    @property
    def last_activity_text(self):
        if not self.last_seen:
            return "Sin registro"
        delta = timezone.now() - self.last_seen
        minutes = int(delta.total_seconds() // 60)
        if minutes < 1:
            return "Hace un momento"
        if minutes < 60:
            return f"Hace {minutes} min"
        hours = minutes // 60
        if hours < 24:
            return f"Hace {hours} h"
        days = hours // 24
        return f"Hace {days} d"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields', None)
        
        # Evitar validación completa si solo se están actualizando campos de estado (login/actividad)
        # Esto previene errores de validación que bloqueen el inicio de sesión.
        is_status_update = update_fields and set(update_fields).issubset({'last_login', 'last_seen'})
        
        if not is_status_update:
            self.full_clean()
            
        super().save(*args, **kwargs)
        
        if self.foto and not is_status_update:
            # Foto de perfil pequeña (300x300)
            process_image(self.foto, size=(300, 300), quality=70)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Area(models.Model):
    SEDE_CHOICES = (
        ("DIRECCIÓN", "Dirección"),
        ("AGP", "AGP"),
        ("ADMINISTRACIÓN", "Administración"),
        ("UPDI", "UPDI"),
    )
    name = models.CharField(max_length=100)
    sede_principal = models.CharField(max_length=20, choices=SEDE_CHOICES, null=True, blank=True)

    class Meta:
        unique_together = ('name', 'sede_principal')
        verbose_name = "Área"
        verbose_name_plural = "Áreas"

    def __str__(self):
        if self.sede_principal:
            return f"{self.sede_principal} - {self.name}"
        return self.name

class Estado(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

def get_default_estado():
    # Busca el objeto "Pendiente" por nombre. Si no existe, lo crea.
    estado, _ = Estado.objects.get_or_create(name="Pendiente")
    return estado.id

class Incidencia(models.Model):
    ESTADO_PENDIENTE = "Pendiente"
    ESTADO_ASIGNADO = "Asignado"
    ESTADO_REABIERTO = "Reabierto"
    ESTADO_RESUELTO = "Resuelto"
    ESTADO_CERRADO = "Cerrado"
    FLUJO_ESTADOS = (
        ESTADO_PENDIENTE,
        ESTADO_ASIGNADO,
        ESTADO_REABIERTO,
        ESTADO_RESUELTO,
        ESTADO_CERRADO,
    )
    ALLOWED_TRANSITIONS = {
        ESTADO_PENDIENTE: {ESTADO_ASIGNADO, ESTADO_RESUELTO},
        ESTADO_ASIGNADO: {ESTADO_RESUELTO},
        ESTADO_REABIERTO: {ESTADO_ASIGNADO, ESTADO_RESUELTO},
        ESTADO_RESUELTO: {ESTADO_CERRADO, ESTADO_REABIERTO},
        ESTADO_CERRADO: set(),
    }
    CATEGORIA_CHOICES = (
        ("hardware", "Hardware"),
        ("software", "Software"),
        ("red", "Red"),
        ("sistema", "Sistema"),
        ("otros", "Otros"),
    )

    PRIORIDAD_CHOICES = (
        ("baja", "Baja"),
        ("media", "Media"),
        ("alta", "Alta"),
        ("critica", "Crítica"),
    )

    creador = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name="incidencias_creadas")
    area = models.ForeignKey("Area", on_delete=models.CASCADE)
    equipo = models.ForeignKey('inventario.Equipo', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Para cuando el equipo no está listado (Tarea 1)
    otro_tipo = models.CharField(max_length=100, null=True, blank=True)
    otro_marca = models.CharField(max_length=100, null=True, blank=True)
    otro_modelo = models.CharField(max_length=100, null=True, blank=True)
    otro_serie = models.CharField(max_length=100, null=True, blank=True)

    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES)
    descripcion = models.TextField()
    imagen_adjunta = models.ImageField(upload_to=upload_to_incidencias, null=True, blank=True)
    codigo = models.CharField(max_length=20, unique=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    estado = models.ForeignKey("Estado", on_delete=models.PROTECT, default=get_default_estado)
    
    tecnico_asignado = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name="incidencias_asignadas")
    fecha_asignacion = models.DateTimeField(null=True, blank=True)
    fecha_programada_atencion = models.DateField(null=True, blank=True)
    hora_programada_atencion = models.TimeField(null=True, blank=True)
    observaciones_internas = models.TextField(null=True, blank=True)
    
    solucion_aplicada = models.TextField(null=True, blank=True)
    evidencia_solucion = models.ImageField(upload_to=upload_to_soluciones, null=True, blank=True)
    evidencia_solucion_2 = models.ImageField(upload_to=upload_to_soluciones, null=True, blank=True)
    evidencia_solucion_3 = models.ImageField(upload_to=upload_to_soluciones, null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    documento_informe = models.FileField(upload_to=upload_to_informes, null=True, blank=True)

    @property
    def puede_cerrar(self):
        return self.estado_visual == self.ESTADO_RESUELTO

    @property
    def esta_asignada(self):
        return self.tecnico_asignado is not None

    @property
    def puede_reabrir(self):
        return self.estado_visual == self.ESTADO_RESUELTO

    @property
    def estado_actual(self):
        return self.estado.name if self.estado_id and self.estado else self.ESTADO_PENDIENTE

    @property
    def estado_normalizado(self):
        current = self.estado_actual
        if current == "En Proceso":
            return self.ESTADO_ASIGNADO
        return current

    @property
    def estado_visual(self):
        current = self.estado_normalizado
        if current in {self.ESTADO_RESUELTO, self.ESTADO_REABIERTO, self.ESTADO_CERRADO}:
            return current
        if self.tecnico_asignado:
            return self.ESTADO_ASIGNADO
        return self.ESTADO_PENDIENTE

    @property
    def estado_badge_class(self):
        return {
            self.ESTADO_PENDIENTE: "badge-pendiente",
            self.ESTADO_ASIGNADO: "badge-asignado",
            self.ESTADO_REABIERTO: "badge-reabierto",
            self.ESTADO_RESUELTO: "badge-resuelto",
            self.ESTADO_CERRADO: "badge-cerrado",
        }.get(self.estado_visual, "badge-pendiente")

    def can_transition_to(self, target_state):
        current_state = self.estado_normalizado
        if not self.estado_id or not self.estado:
            return target_state == self.ESTADO_PENDIENTE
        if target_state == current_state:
            return True
        return target_state in self.ALLOWED_TRANSITIONS.get(current_state, set())

    def build_codigo(self):
        year = (self.fecha_creacion or timezone.now()).year
        return f"INC-{year}-{self.pk:04d}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.codigo and self.pk:
            self.codigo = self.build_codigo()
            super().save(update_fields=["codigo"])
        if self.imagen_adjunta:
            process_image(self.imagen_adjunta, size=(1024, 1024))
        if self.evidencia_solucion:
            process_image(self.evidencia_solucion, size=(1024, 1024))

    def __str__(self):
        return f"{self.codigo or f'Incidencia #{self.id}'} - {self.descripcion[:50]}"

class IncidenciaImagen(models.Model):
    incidencia = models.ForeignKey(Incidencia, on_delete=models.CASCADE, related_name="imagenes")
    imagen = models.ImageField(upload_to=upload_to_adicionales)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.imagen:
            process_image(self.imagen, size=(1024, 1024), quality=70)

    def __str__(self):
        return f"Imagen para Incidencia #{self.incidencia.id}"

class Notificacion(models.Model):
    TIPO_CHOICES = (
        ("asignacion", "Asignación"),
        ("estado", "Cambio de Estado"),
        ("comentario", "Nuevo Comentario"),
        ("nueva_incidencia", "Nueva Incidencia"), 
        ("incidencia_resuelta", "Incidencia Resuelta"), 
        ("desasignacion", "Desasignación"),
    )

    incidencia = models.ForeignKey(Incidencia, on_delete=models.CASCADE, null=True, blank=True)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    link = models.URLField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"Notificación: {self.tipo} - {self.mensaje[:30]}..."

    class Meta:
        ordering = ["-fecha_creacion"]

class NotificacionUsuario(models.Model):
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notificaciones")
    notificacion = models.ForeignKey(Notificacion, on_delete=models.CASCADE, related_name="usuarios")
    leido = models.BooleanField(default=False)
    fecha_recibida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notif para {self.usuario.username} ({'Leído' if self.leido else 'No leído'})"

    class Meta:
        ordering = ["-fecha_recibida"]
        unique_together = ('usuario', 'notificacion')

class Comentario(models.Model):
    TIPO_COMENTARIO_CHOICES = (
        ("tecnico", "Comentario Técnico"),
        ("confirmacion", "Confirmación de Solución"),
        ("persiste", "Problema Persiste"),
        ("observacion", "Observación Interna"),
    )

    incidencia = models.ForeignKey(Incidencia, on_delete=models.CASCADE, related_name="comentarios")
    usuario = models.ForeignKey('CustomUser', on_delete=models.CASCADE)
    tipo_comentario = models.CharField(max_length=20, choices=TIPO_COMENTARIO_CHOICES, default="observacion")
    texto = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    evidencia_adjunta = models.ImageField(upload_to=upload_to_comentarios, null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.evidencia_adjunta:
            # Calidad baja para el chat (performance)
            process_image(self.evidencia_adjunta, size=(600, 600), quality=50)

    def __str__(self):
        return f"Comentario en Incidencia #{self.incidencia.id} por {self.usuario.username}"

# --- SEÑALES PARA NOTIFICACIONES REAL-TIME ---
from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

@receiver(post_save, sender=NotificacionUsuario)
def send_notification_update(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        # El número de no leídos para este usuario en particular (modelo intermedio)
        unread_count = NotificacionUsuario.objects.filter(usuario=instance.usuario, leido=False).count()
        
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.usuario.id}_notifications",
            {
                "type": "send_notification",
                "message": instance.notificacion.mensaje,
                "tipo": instance.notificacion.tipo,
                "unread_count": unread_count
            }
        )
