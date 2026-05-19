from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from .models import Equipo, Marca, TipoEquipo, EstadoEquipo, MantenimientoPreventivo, Repuesto

@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)

@admin.register(TipoEquipo)
class TipoEquipoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)

@admin.register(EstadoEquipo)
class EstadoEquipoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)

@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('foto_preview', 'codigo_equipo', 'nombre_equipo', 'tipo_equipo', 'marca', 'estado_tecnico', 'disponibilidad', 'origen_ocupacion', 'activo')
    list_filter = ('tipo_equipo', 'marca', 'estado_tecnico', 'disponibilidad', 'origen_ocupacion', 'activo', 'area')
    search_fields = ('codigo_equipo', 'nombre_equipo', 'numero_serie')
    readonly_fields = ('fecha_register', 'actualizado_en', 'foto_preview')
    campos_criticos = {
        'estado',
        'estado_tecnico',
        'disponibilidad',
        'origen_ocupacion',
        'activo',
    }

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly.extend(self.campos_criticos)
        return tuple(dict.fromkeys(readonly))

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change and self.campos_criticos.intersection(form.changed_data):
            raise ValidationError("Use los servicios del sistema para modificar estados técnicos, disponibilidad u origen de ocupación.")
        super().save_model(request, obj, form, change)

    def foto_preview(self, obj):
        if obj.foto_estado:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px;" />', obj.foto_estado.url)
        return "-"
    foto_preview.short_description = "Vista Previa"


@admin.register(Repuesto)
class RepuestoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "stock_actual", "stock_minimo", "unidad", "activo", "actualizado_en")
    list_filter = ("activo", "unidad", "categoria")
    search_fields = ("nombre", "categoria", "ubicacion")
    readonly_fields = ("actualizado_en",)


@admin.register(MantenimientoPreventivo)
class MantenimientoPreventivoAdmin(admin.ModelAdmin):
    list_display = ("equipo", "fecha_programada", "estado", "responsable", "fecha_realizado")
    list_filter = ("estado", "fecha_programada", "responsable")
    search_fields = ("equipo__codigo_equipo", "equipo__nombre_equipo", "descripcion", "resultado")
    readonly_fields = ("creado_en", "actualizado_en")
