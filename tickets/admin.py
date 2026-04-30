from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms.forms_usuarios import validate_dni, validate_person_name, validate_phone
from .models import Area, CustomUser, Estado, Incidencia


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
    list_display = ('username', 'email', 'role', 'area', 'is_staff')
    list_filter = ('role', 'area')
    fieldsets = UserAdmin.fieldsets + (
        ('Información Extra', {'fields': ('role', 'telefono', 'area')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Extra', {'fields': ('role', 'telefono', 'area')}),
    )

@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    list_display = ('id', 'creador', 'area', 'prioridad', 'estado', 'fecha_creacion')
    list_filter = ('prioridad', 'estado', 'categoria')
    readonly_fields = ('fecha_creacion',)
