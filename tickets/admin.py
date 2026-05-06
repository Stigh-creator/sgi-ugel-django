from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError

from .forms.forms_usuarios import validate_dni, validate_person_name, validate_phone
from .models import Area, CustomUser, Estado, Incidencia, MetricaDiaria, ReemplazoEquipoIncidencia, SLAConfiguracion


class CustomUserAdminForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = "__all__"

    def clean_username(self):
        dni = validate_dni(self.cleaned_data.get("username"))
        if CustomUser.objects.filter(username=dni).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este DNI ya se encuentra registrado.")
        return dni

    def clean_first_name(self):
        return validate_person_name(self.cleaned_data.get("first_name"), "nombres")

    def clean_last_name(self):
        return validate_person_name(self.cleaned_data.get("last_name"), "apellidos")

    def clean_telefono(self):
        return validate_phone(self.cleaned_data.get("telefono")) or None

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = CustomUserAdminForm
    list_display = ('username', 'email', 'role', 'area', 'capacidad_base', 'is_staff')
    list_filter = ('role', 'area')
    fieldsets = UserAdmin.fieldsets + (
        ('Información Extra', {'fields': ('role', 'telefono', 'area', 'capacidad_base')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Extra', {'fields': ('role', 'telefono', 'area', 'capacidad_base')}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    list_display = ('id', 'codigo', 'creador', 'area', 'prioridad', 'estado', 'estado_sla', 'fecha_creacion')
    list_filter = ('prioridad', 'estado', 'estado_sla', 'categoria')
    readonly_fields = ('fecha_creacion', 'codigo')
    campos_criticos = {
        'estado',
        'prioridad',
        'tecnico_asignado',
        'equipo',
        'equipo_reemplazo',
        'tipo_resolucion',
        'solucion_aplicada',
        'estado_sla',
        'fecha_limite_respuesta',
        'fecha_limite_resolucion',
        'fecha_auto_cierre',
        'fecha_resolucion',
        'fecha_cierre',
        'auto_cerrado',
        'escalado',
    }

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly.extend(self.campos_criticos)
        return tuple(dict.fromkeys(readonly))

    def save_model(self, request, obj, form, change):
        if change and self.campos_criticos.intersection(form.changed_data):
            raise ValidationError("Use los servicios del sistema para modificar estados, SLA, asignaciones o resoluciones de incidencias.")
        super().save_model(request, obj, form, change)


@admin.register(SLAConfiguracion)
class SLAConfiguracionAdmin(admin.ModelAdmin):
    list_display = ('prioridad', 'categoria', 'tiempo_respuesta_minutos', 'tiempo_resolucion_minutos', 'auto_cierre_horas', 'activo')
    list_filter = ('prioridad', 'categoria', 'activo')


@admin.register(ReemplazoEquipoIncidencia)
class ReemplazoEquipoIncidenciaAdmin(admin.ModelAdmin):
    list_display = ('incidencia', 'equipo_original', 'equipo_reemplazo', 'area_origen', 'area_destino', 'activo', 'fecha_inicio')
    list_filter = ('activo', 'fecha_inicio')
    search_fields = ('incidencia__codigo', 'equipo_original__codigo_equipo', 'equipo_reemplazo__codigo_equipo')
    readonly_fields = ('incidencia', 'equipo_original', 'equipo_reemplazo', 'area_origen', 'area_destino', 'usuario', 'motivo', 'fecha_inicio', 'fecha_fin', 'activo', 'metadata')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MetricaDiaria)
class MetricaDiariaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tickets_abiertos', 'tickets_cerrados', 'sla_vencidos', 'sla_por_vencer', 'reemplazos_activos')
    readonly_fields = ('fecha', 'metadata', 'creado_en', 'actualizado_en')
    list_filter = ('fecha',)
