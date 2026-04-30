from django.contrib import admin
from .models import Auditoria

@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'usuario', 'modulo', 'accion', 'ip')
    list_filter = ('modulo', 'accion', 'fecha_hora')
    search_fields = ('descripcion', 'ip', 'usuario__username')
    readonly_fields = ('fecha_hora', 'ip', 'usuario', 'modulo', 'accion', 'descripcion', 'referencia_id')

    def has_add_permission(self, request):
        return False  # La auditoría es solo lectura desde el admin

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
