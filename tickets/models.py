import os
import uuid
from django.contrib.auth.models import AbstractUser, UserManager
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


class EstadoIncidencia(models.TextChoices):
    PENDIENTE = "Pendiente", "Pendiente"
    ASIGNADO = "Asignado", "Asignado"
    EN_PROCESO = "En Proceso", "En Proceso"
    RECHAZADO = "Rechazado", "Rechazado"
    REABIERTO = "Reabierto", "Reabierto"
    PENDIENTE_VALIDACION = "Pendiente de validación", "Pendiente de validación"
    RESUELTO = "Resuelto", "Resuelto"
    CERRADO = "Cerrado", "Cerrado"


class EstadoSLA(models.TextChoices):
    EN_TIEMPO = "en_tiempo", "En tiempo"
    POR_VENCER = "por_vencer", "Por vencer"
    RESPUESTA_VENCIDA = "respuesta_vencida", "Respuesta vencida"
    RESOLUCION_VENCIDA = "resolucion_vencida", "Resolución vencida"
    ESCALADO = "escalado", "Escalado"
    CUMPLIDO = "cumplido", "Cumplido"
    NO_APLICA = "no_aplica", "No aplica"

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


class CustomUserManager(UserManager):
    def _superuser_default_phone(self, username):
        username_digits = "".join(char for char in str(username or "") if char.isdigit())
        candidates = []
        if len(username_digits) >= 8:
            candidates.append(f"9{username_digits[-8:]}")
        candidates.extend(str(number) for number in range(900000000, 900000100))
        for telefono in candidates:
            if not self.model.objects.filter(telefono=telefono).exists():
                return telefono
        return candidates[0]

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", self.model.ROL_ADMIN)
        extra_fields.setdefault("first_name", "Superusuario")
        extra_fields.setdefault("last_name", "Sistema")
        extra_fields.setdefault("telefono", self._superuser_default_phone(username))
        extra_fields.setdefault("must_change_password", False)

        if extra_fields.get("role") != self.model.ROL_ADMIN:
            raise ValueError("El superusuario debe tener rol Administrador.")
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class CustomUser(AbstractUser):
    ONLINE_THRESHOLD_SECONDS = 300

    ROL_TRABAJADOR = "usuario"
    ROL_TECNICO = "tecnico"
    ROL_ADMIN = "administrador"
    ROL_ALMACEN = "almacen"

    ROLE_CHOICES = (
        (ROL_TRABAJADOR, "Usuario (Trabajador)"),
        (ROL_TECNICO, "Técnico"),
        (ROL_ADMIN, "Administrador/Ingeniero TI"),
        (ROL_ALMACEN, "Responsable de Almacén"),
    )
    REQUIRED_FIELDS = ["first_name", "last_name", "telefono"]
    objects = CustomUserManager()
    
    first_name = models.CharField("First name", max_length=150, validators=[nombre_valido])
    last_name = models.CharField("Last name", max_length=150, validators=[nombre_valido])
    username = models.CharField("DNI / Username", max_length=150, unique=True, validators=[dni_valido], help_text="8 dígitos del DNI.")
    email = models.EmailField(blank=True, null=True, validators=[email_valido])

    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default=ROL_TRABAJADOR)
    telefono = models.CharField(max_length=9, validators=[telefono_valido])
    area = models.ForeignKey("Area", on_delete=models.SET_NULL, null=True, blank=True)
    foto = models.ImageField(upload_to=upload_to_perfiles, null=True, blank=True)
    last_password_change = models.DateTimeField(default=timezone.now)
    must_change_password = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    capacidad_base = models.PositiveIntegerField(default=4)

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
        return self.role == self.ROL_TECNICO

    @property
    def es_admin(self):
        return self.role == self.ROL_ADMIN

    @property
    def es_almacen(self):
        return self.role == self.ROL_ALMACEN

    @property
    def es_usuario(self):
        return self.role == self.ROL_TRABAJADOR

    @property
    def puede_ser_especialista(self):
        return self.is_active and self.role in {self.ROL_TECNICO, self.ROL_ADMIN}

    @property
    def role_short_label(self):
        return {
            self.ROL_ADMIN: "Administrador",
            self.ROL_TECNICO: "Técnico TI",
            self.ROL_ALMACEN: "Almacén",
            self.ROL_TRABAJADOR: "Trabajador",
        }.get(self.role, "Usuario")

    @property
    def role_badge_class(self):
        return {
            self.ROL_ADMIN: "role-admin-soft",
            self.ROL_TECNICO: "role-tech-soft",
            self.ROL_ALMACEN: "role-admin-soft",
            self.ROL_TRABAJADOR: "role-user-soft",
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
    estado, _ = Estado.objects.get_or_create(name="Pendiente")
    return estado.id

class Incidencia(models.Model):
    ESTADO_PENDIENTE = EstadoIncidencia.PENDIENTE
    ESTADO_ASIGNADO = EstadoIncidencia.ASIGNADO
    ESTADO_EN_PROCESO = EstadoIncidencia.EN_PROCESO
    ESTADO_RECHAZADO = EstadoIncidencia.RECHAZADO
    ESTADO_REABIERTO = EstadoIncidencia.REABIERTO
    ESTADO_PENDIENTE_VALIDACION = EstadoIncidencia.PENDIENTE_VALIDACION
    ESTADO_RESUELTO = EstadoIncidencia.RESUELTO
    ESTADO_CERRADO = EstadoIncidencia.CERRADO
    FLUJO_ESTADOS = (
        ESTADO_PENDIENTE,
        ESTADO_ASIGNADO,
        ESTADO_EN_PROCESO,
        ESTADO_RECHAZADO,
        ESTADO_REABIERTO,
        ESTADO_PENDIENTE_VALIDACION,
        ESTADO_RESUELTO,
        ESTADO_CERRADO,
    )
    ALLOWED_TRANSITIONS = {
        ESTADO_PENDIENTE: {ESTADO_ASIGNADO, ESTADO_RESUELTO},
        ESTADO_ASIGNADO: {ESTADO_EN_PROCESO, ESTADO_RECHAZADO, ESTADO_RESUELTO},
        ESTADO_EN_PROCESO: {ESTADO_PENDIENTE_VALIDACION, ESTADO_RESUELTO},
        ESTADO_RECHAZADO: {ESTADO_ASIGNADO},
        ESTADO_REABIERTO: {ESTADO_ASIGNADO, ESTADO_PENDIENTE_VALIDACION, ESTADO_RESUELTO},
        ESTADO_PENDIENTE_VALIDACION: {ESTADO_CERRADO, ESTADO_REABIERTO},
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

    PRIORIDAD_BAJA = "baja"
    PRIORIDAD_MEDIA = "media"
    PRIORIDAD_ALTA = "alta"
    PRIORIDAD_CRITICA = "critica"

    PRIORIDAD_CHOICES = (
        (PRIORIDAD_BAJA, "Baja"),
        (PRIORIDAD_MEDIA, "Media"),
        (PRIORIDAD_ALTA, "Alta"),
        (PRIORIDAD_CRITICA, "Crítica"),
    )

    RESOLUCION_REPARADO = "reparado"
    RESOLUCION_REEMPLAZADO = "reemplazado"
    RESOLUCION_BAJA = "baja"
    RESOLUCION_DERIVADO = "derivado"

    TIPO_RESOLUCION_CHOICES = (
        (RESOLUCION_REPARADO, "Reparado"),
        (RESOLUCION_REEMPLAZADO, "Reemplazado (temporal)"),
        (RESOLUCION_BAJA, "Dado de baja"),
        (RESOLUCION_DERIVADO, "Derivado / externo"),
    )

    creador = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name="incidencias_creadas")
    area = models.ForeignKey("Area", on_delete=models.CASCADE)
    equipo = models.ForeignKey('inventario.Equipo', on_delete=models.SET_NULL, null=True, blank=True)
    
    otro_tipo = models.CharField(max_length=100, null=True, blank=True)
    otro_marca = models.CharField(max_length=100, null=True, blank=True)
    otro_modelo = models.CharField(max_length=100, null=True, blank=True)
    otro_serie = models.CharField(max_length=100, null=True, blank=True)

    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES, default=PRIORIDAD_MEDIA)
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
    tipo_resolucion = models.CharField(max_length=20, choices=TIPO_RESOLUCION_CHOICES, null=True, blank=True)
    equipo_reemplazo = models.ForeignKey(
        'inventario.Equipo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidencias_como_reemplazo",
    )
    evidencia_solucion = models.ImageField(upload_to=upload_to_soluciones, null=True, blank=True)
    evidencia_solucion_2 = models.ImageField(upload_to=upload_to_soluciones, null=True, blank=True)
    evidencia_solucion_3 = models.ImageField(upload_to=upload_to_soluciones, null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    fecha_limite_respuesta = models.DateTimeField(null=True, blank=True)
    fecha_limite_resolucion = models.DateTimeField(null=True, blank=True)
    fecha_auto_cierre = models.DateTimeField(null=True, blank=True)
    estado_sla = models.CharField(max_length=30, choices=EstadoSLA.choices, default=EstadoSLA.EN_TIEMPO)
    sla_respuesta_notificado = models.BooleanField(default=False)
    sla_resolucion_notificado = models.BooleanField(default=False)
    auto_cerrado = models.BooleanField(default=False)
    escalado = models.BooleanField(default=False)
    documento_informe = models.FileField(upload_to=upload_to_informes, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["estado", "prioridad"], name="idx_inc_estado_prioridad"),
            models.Index(fields=["estado", "fecha_limite_resolucion"], name="idx_inc_estado_lim_res"),
            models.Index(fields=["prioridad"], name="idx_inc_prioridad"),
            models.Index(fields=["fecha_limite_resolucion"], name="idx_inc_limite_resol"),
            models.Index(fields=["fecha_limite_respuesta"], name="idx_inc_limite_resp"),
            models.Index(fields=["estado_sla"], name="idx_inc_estado_sla"),
        ]

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
        return self.estado_actual

    @property
    def estado_visual(self):
        current = self.estado_normalizado
        estados_explicitos = {
            self.ESTADO_ASIGNADO,
            self.ESTADO_EN_PROCESO,
            self.ESTADO_RECHAZADO,
            self.ESTADO_REABIERTO,
            self.ESTADO_PENDIENTE_VALIDACION,
            self.ESTADO_RESUELTO,
            self.ESTADO_CERRADO,
        }
        if current in estados_explicitos:
            return current
        if self.tecnico_asignado:
            return self.ESTADO_ASIGNADO
        return self.ESTADO_PENDIENTE

    @property
    def prioridad_editable(self):
        return (
            self.estado_actual == self.ESTADO_PENDIENTE
            or (self.estado_actual == self.ESTADO_RECHAZADO and not self.tecnico_asignado_id)
        )

    @property
    def prioridad_texto_plano(self):
        return self.estado_actual in {
            self.ESTADO_EN_PROCESO,
            self.ESTADO_PENDIENTE_VALIDACION,
            self.ESTADO_RESUELTO,
            self.ESTADO_CERRADO,
        }

    @property
    def esta_en_proceso(self):
        return self.estado_actual == self.ESTADO_EN_PROCESO

    @property
    def puede_registrar_solucion(self):
        return self.estado_actual in {
            self.ESTADO_EN_PROCESO,
            self.ESTADO_REABIERTO,
        }

    @property
    def puede_aceptar_o_rechazar(self):
        return self.estado_actual == self.ESTADO_ASIGNADO

    @property
    def estado_badge_class(self):
        return {
            self.ESTADO_PENDIENTE: "badge-pendiente",
            self.ESTADO_ASIGNADO: "badge-asignado",
            self.ESTADO_EN_PROCESO: "badge-asignado",
            self.ESTADO_RECHAZADO: "badge-reabierto",
            self.ESTADO_REABIERTO: "badge-reabierto",
            self.ESTADO_PENDIENTE_VALIDACION: "badge-resuelto",
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
        is_new = self.pk is None
        previous = None
        if self.pk:
            previous = Incidencia.objects.filter(pk=self.pk).values(
                "prioridad",
                "estado__name",
                "tecnico_asignado_id",
            ).first()
            previous_priority_editable = previous and (
                previous["estado__name"] == self.ESTADO_PENDIENTE
                or (
                    previous["estado__name"] == self.ESTADO_RECHAZADO
                    and not previous["tecnico_asignado_id"]
                )
            )
            if previous and not previous_priority_editable:
                self.prioridad = previous["prioridad"]

        if is_new and self.creador_id and getattr(self, 'creador', None) and self.creador.es_usuario:
            self.prioridad = self.PRIORIDAD_MEDIA

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


class SLAConfiguracion(models.Model):
    prioridad = models.CharField(max_length=20, choices=Incidencia.PRIORIDAD_CHOICES)
    categoria = models.CharField(max_length=20, choices=Incidencia.CATEGORIA_CHOICES, null=True, blank=True)
    tiempo_respuesta_minutos = models.PositiveIntegerField(default=240)
    tiempo_resolucion_minutos = models.PositiveIntegerField(default=1440)
    auto_cierre_horas = models.PositiveIntegerField(default=72)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Configuración SLA"
        verbose_name_plural = "Configuraciones SLA"
        unique_together = ("prioridad", "categoria")

    def __str__(self):
        categoria = self.get_categoria_display() if self.categoria else "Todas"
        return f"SLA {self.get_prioridad_display()} / {categoria}"


class ReemplazoEquipoIncidencia(models.Model):
    incidencia = models.ForeignKey(Incidencia, on_delete=models.PROTECT, related_name="reemplazos")
    equipo_original = models.ForeignKey(
        "inventario.Equipo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reemplazos_como_original",
    )
    equipo_reemplazo = models.ForeignKey(
        "inventario.Equipo",
        on_delete=models.PROTECT,
        related_name="reemplazos_como_temporal",
    )
    area_origen = models.ForeignKey("Area", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    area_destino = models.ForeignKey("Area", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    usuario = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name="reemplazos_registrados")
    motivo = models.TextField()
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Reemplazo de equipo por incidencia"
        verbose_name_plural = "Reemplazos de equipos por incidencias"
        indexes = [
            models.Index(fields=["incidencia", "activo"]),
            models.Index(fields=["equipo_reemplazo", "activo"]),
            models.Index(fields=["activo"], name="idx_reemplazo_activo"),
        ]

    def __str__(self):
        return f"{self.incidencia.codigo}: {self.equipo_original} -> {self.equipo_reemplazo}"


class MetricaDiaria(models.Model):
    fecha = models.DateField(unique=True)
    tickets_abiertos = models.PositiveIntegerField(default=0)
    tickets_cerrados = models.PositiveIntegerField(default=0)
    sla_vencidos = models.PositiveIntegerField(default=0)
    sla_por_vencer = models.PositiveIntegerField(default=0)
    tickets_validacion_vencidos = models.PositiveIntegerField(default=0)
    equipos_reparacion_sin_ticket_activo = models.PositiveIntegerField(default=0)
    reemplazos_activos = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Métrica diaria"
        verbose_name_plural = "Métricas diarias"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Métricas SGI {self.fecha}"

class Notificacion(models.Model):
    TIPO_CHOICES = (
        ("asignacion", "Asignación"),
        ("estado", "Cambio de Estado"),
        ("comentario", "Nuevo Comentario"),
        ("nueva_incidencia", "Nueva Incidencia"), 
        ("incidencia_resuelta", "Incidencia Resuelta"), 
        ("desasignacion", "Desasignación"),
        ("sla", "Alerta SLA"),
        ("inventario", "Inventario"),
    )
    PRIORIDAD_BAJA = "baja"
    PRIORIDAD_MEDIA = "media"
    PRIORIDAD_ALTA = "alta"
    PRIORIDAD_CRITICA = "critica"
    PRIORIDAD_CHOICES = (
        (PRIORIDAD_BAJA, "Baja"),
        (PRIORIDAD_MEDIA, "Media"),
        (PRIORIDAD_ALTA, "Alta"),
        (PRIORIDAD_CRITICA, "Crítica"),
    )

    incidencia = models.ForeignKey(Incidencia, on_delete=models.CASCADE, null=True, blank=True)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES, default=PRIORIDAD_MEDIA)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    link = models.URLField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"Notificación: {self.tipo} - {self.mensaje[:30]}..."

    @property
    def icon_class(self):
        return {
            "asignacion": "bi-person-check",
            "estado": "bi-arrow-repeat",
            "comentario": "bi-chat-left-text",
            "nueva_incidencia": "bi-ticket-perforated",
            "incidencia_resuelta": "bi-check2-circle",
            "desasignacion": "bi-person-dash",
            "sla": "bi-clock-history",
            "inventario": "bi-box-seam",
        }.get(self.tipo, "bi-bell")

    @property
    def prioridad_label(self):
        return dict(self.PRIORIDAD_CHOICES).get(self.prioridad, "Media")

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
        if channel_layer is None:
            return
        # El número de no leídos para este usuario en particular (modelo intermedio)
        unread_count = NotificacionUsuario.objects.filter(usuario=instance.usuario, leido=False).count()
        
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.usuario.id}_notifications",
            {
                "type": "send_notification",
                "notification_user_id": instance.id,
                "message": instance.notificacion.mensaje,
                "tipo": instance.notificacion.tipo,
                "prioridad": instance.notificacion.prioridad,
                "prioridad_label": instance.notificacion.prioridad_label,
                "icon_class": instance.notificacion.icon_class,
                "link": instance.notificacion.link or "",
                "unread_count": unread_count
            }
        )
