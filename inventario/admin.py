from django.contrib import admin
from django.utils.html import format_html
from .models import Equipo, Marca, TipoEquipo, EstadoEquipo

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
    list_display = ('foto_preview', 'codigo_equipo', 'nombre_equipo', 'tipo_equipo', 'marca', 'estado', 'activo')
    list_filter = ('tipo_equipo', 'marca', 'estado', 'activo', 'area')
    search_fields = ('codigo_equipo', 'nombre_equipo', 'numero_serie')
    readonly_fields = ('fecha_register', 'actualizado_en', 'foto_preview')

    def foto_preview(self, obj):
        if obj.foto_estado:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px;" />', obj.foto_estado.url)
        return "-"
    foto_preview.short_description = "Vista Previa"
