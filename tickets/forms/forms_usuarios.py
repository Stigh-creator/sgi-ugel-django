import os
import re
import unicodedata

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import CustomUser

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_PROFILE_PHOTO_SIZE = 2 * 1024 * 1024


def normalize_string(text):
    if not text:
        return ""
    text = text.lower()
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def validate_dni(value):
    dni = (value or "").strip()
    if not re.fullmatch(r"\d{8}", dni):
        raise ValidationError("El DNI debe contener exactamente 8 dígitos.")
    return dni


def validate_phone(value):
    telefono = (value or "").strip()
    if not telefono:
        raise ValidationError("El teléfono es obligatorio.")
    if not re.fullmatch(r"\d{9}", telefono):
        raise ValidationError("El teléfono debe contener exactamente 9 dígitos numéricos.")
    return telefono


def validate_email_value(value):
    email = (value or "").strip().lower()
    if email:
        EmailValidator(message="Ingrese un correo válido con el formato ejemplo@dominio.com.")(email)
    return email


def validate_person_name(value, field_name):
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"El campo {field_name} es obligatorio.")
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+", text):
        raise ValidationError(f"El campo {field_name} solo permite letras y espacios.")
    return text


def validate_profile_photo(file_obj):
    if not file_obj:
        return file_obj

    extension = os.path.splitext(file_obj.name)[1].lower()
    content_type = getattr(file_obj, "content_type", "")

    if content_type not in ALLOWED_IMAGE_TYPES or extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("La foto de perfil solo permite archivos JPG o PNG.")

    if file_obj.size > MAX_PROFILE_PHOTO_SIZE:
        raise ValidationError("La foto de perfil no debe superar los 2 MB.")

    return file_obj


def build_temporary_password(dni):
    return f"Ugel@{dni}"


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Confirmar nueva contraseña"

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
            field.help_text = None

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1", "")
        
        # Verificación de privacidad: evitar datos personales
        password_normalized = normalize_string(password)
        personal_data = []
        if self.user.first_name:
            personal_data.extend(normalize_string(self.user.first_name).split())
        if self.user.last_name:
            personal_data.extend(normalize_string(self.user.last_name).split())
        if self.user.username:
            personal_data.append(normalize_string(self.user.username))
            
        for data in personal_data:
            if data and len(data) >= 3 and data in password_normalized:
                raise ValidationError("La contraseña es demasiado similar a sus datos personales.")

        if len(password) < 10:
            raise ValidationError("La contraseña debe tener al menos 10 caracteres.")
        if not re.search(r"[A-Z]", password):
            raise ValidationError("Debe incluir al menos una letra mayúscula.")
        if not re.search(r"[a-z]", password):
            raise ValidationError("Debe incluir al menos una letra minúscula.")
        if not re.search(r"[0-9]", password):
            raise ValidationError("Debe incluir al menos un número.")
        if not re.search(r"[@#$%^&+=.!*?]", password):
            raise ValidationError("Debe incluir al menos un carácter especial (@#$%^&+=.!*?).")
        return password


class CustomUserCreationForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ("username", "first_name", "last_name", "email", "telefono", "role", "area")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

        self.fields["username"].widget.attrs.update({
            "maxlength": "8",
            "inputmode": "numeric",
            "pattern": r"\d{8}",
        })
        for name in ("first_name", "last_name"):
            self.fields[name].widget.attrs.update({
                "pattern": r"[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+",
            })
        self.fields["telefono"].widget.attrs.update({
            "maxlength": "9",
            "inputmode": "tel",
            "pattern": r"\d{9}",
        })

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["telefono"].required = True
        self.fields["role"].required = True
        self.fields["area"].required = True
        self.fields["area"].empty_label = "-- Seleccione Área --"

    def clean_username(self):
        dni = validate_dni(self.cleaned_data.get("username"))
        if CustomUser.objects.filter(username=dni).exists():
            raise ValidationError("Este DNI ya se encuentra registrado.")
        return dni

    def clean_email(self):
        email = validate_email_value(self.cleaned_data.get("email"))
        if email and CustomUser.objects.filter(email=email).exists():
            raise ValidationError("Este correo electrónico ya está en uso.")
        return email or None

    def clean_first_name(self):
        return validate_person_name(self.cleaned_data.get("first_name"), "nombres")

    def clean_last_name(self):
        return validate_person_name(self.cleaned_data.get("last_name"), "apellidos")

    def clean_telefono(self):
        telefono = validate_phone(self.cleaned_data.get("telefono"))
        if CustomUser.objects.filter(telefono=telefono).exists():
            raise ValidationError("Este teléfono ya está en uso.")
        return telefono

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["username"]
        user.cambio_clave_pendiente = True
        user.is_active = True
        user.set_password(build_temporary_password(user.username))
        if commit:
            user.save()
        return user


class AdminUserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "email", "telefono", "role", "area")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

        for name in ("first_name", "last_name"):
            self.fields[name].widget.attrs.update({
                "pattern": r"[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+",
            })
        self.fields["telefono"].widget.attrs.update({
            "maxlength": "9",
            "inputmode": "tel",
            "pattern": r"\d{9}",
        })

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["telefono"].required = True
        self.fields["role"].required = True
        self.fields["area"].required = True
        self.fields["area"].empty_label = "-- Seleccione Área --"

    def clean_first_name(self):
        return validate_person_name(self.cleaned_data.get("first_name"), "nombres")

    def clean_last_name(self):
        return validate_person_name(self.cleaned_data.get("last_name"), "apellidos")

    def clean_email(self):
        email = validate_email_value(self.cleaned_data.get("email"))
        if email and CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Este correo electrónico ya está en uso por otro usuario.")
        return email or None

    def clean_telefono(self):
        telefono = validate_phone(self.cleaned_data.get("telefono"))
        if CustomUser.objects.filter(telefono=telefono).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Este teléfono ya está en uso por otro usuario.")
        return telefono


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "email", "telefono")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["telefono"].widget.attrs.update({
            "maxlength": "9",
            "inputmode": "tel",
            "pattern": r"\d{9}",
        })
        self.fields["telefono"].required = True
        for name in ("first_name", "last_name"):
            self.fields[name].widget.attrs.update({
                "pattern": r"[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+",
            })

        if self.instance and self.instance.role != "administrador":
            self.fields["first_name"].widget.attrs["readonly"] = True
            self.fields["last_name"].widget.attrs["readonly"] = True

    def clean_email(self):
        email = validate_email_value(self.cleaned_data.get("email"))
        if email and CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Este correo electrónico ya está en uso por otro usuario.")
        return email or None

    def clean_telefono(self):
        telefono = validate_phone(self.cleaned_data.get("telefono"))
        if CustomUser.objects.filter(telefono=telefono).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Este teléfono ya está en uso por otro usuario.")
        return telefono

    def clean_first_name(self):
        value = self.cleaned_data.get("first_name")
        if self.instance and self.instance.role != "administrador":
            return self.instance.first_name
        return validate_person_name(value, "nombre")

    def clean_last_name(self):
        value = self.cleaned_data.get("last_name")
        if self.instance and self.instance.role != "administrador":
            return self.instance.last_name
        return validate_person_name(value, "apellido")

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.instance and self.instance.role != "administrador":
            user.first_name = self.instance.first_name
            user.last_name = self.instance.last_name
        if commit:
            user.save()
        return user


class ProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ("foto",)

    def clean_foto(self):
        return validate_profile_photo(self.cleaned_data.get("foto"))
