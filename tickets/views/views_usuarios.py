from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from auditoria.utils import registrar_auditoria
from .views_utils import (
    is_admin, is_fetch_request, add_form_errors_to_messages, form_errors_to_dict, page_querystring
)
from ..models import Area, CustomUser
from ..forms.forms_usuarios import (
    AdminUserUpdateForm,
    CustomPasswordChangeForm,
    CustomUserCreationForm,
    USER_ACTIVE_INCIDENT_STATES,
    ProfilePhotoForm,
    ProfileUpdateForm,
    build_temporary_password,
)

REGISTROS_POR_PAGINA = 10
CURRENT_PASSWORD_ERROR = "La contraseña actual no es correcta."


def display_user(user):
    return user.get_full_name() or user.username


def admin_actor_label(user):
    return f"{display_user(user)} (DNI: {user.username})"


def target_user_label(user):
    return f"{display_user(user)} (DNI: {user.username})"


def protected_superuser_message():
    return "No tienes permisos para editar, restablecer contraseña o deshabilitar al superusuario."


def is_protected_superuser_target(actor, target):
    return target.is_superuser and not actor.is_superuser


def reject_request(request, message, status=400):
    if is_fetch_request(request):
        return JsonResponse({"success": False, "message": message}, status=status)
    messages.error(request, message)
    return redirect("usuarios")


def require_motivo(request, accion):
    motivo = (request.POST.get("motivo") or "").strip()
    if not motivo:
        return None, f"Debe ingresar el motivo para {accion}."
    return motivo, None


def field_display(field_name, value):
    if field_name == "role":
        return dict(CustomUser.ROLE_CHOICES).get(value, value or "Sin rol")
    if field_name == "area":
        return str(value) if value else "Sin área"
    return value or "Vacío"


def build_user_change_details(before, user):
    field_labels = {
        "first_name": "nombres",
        "last_name": "apellidos",
        "email": "correo",
        "telefono": "teléfono",
        "role": "rol",
        "area": "área",
    }
    changes = []
    for field_name, label in field_labels.items():
        old_value = before[field_name]
        new_value = getattr(user, field_name)
        if field_name == "area":
            changed = getattr(old_value, "pk", None) != getattr(new_value, "pk", None)
        else:
            changed = old_value != new_value
        if changed:
            changes.append(
                f"{label}: '{field_display(field_name, old_value)}' -> '{field_display(field_name, new_value)}'"
            )
    return changes

def delete_user_sessions(user):
    for session in Session.objects.all():
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) == str(user.pk):
            session.delete()

def render_user_row(request, user):
    return render_to_string(
        "tickets/partials/usuario_row.html",
        {"user_obj": user},
        request=request,
    )

def get_usuarios_context(request, creation_form=None, update_form=None):
    users_list = CustomUser.objects.select_related("area").annotate(
        assigned_active_incidents_count=Count(
            "incidencias_asignadas",
            filter=Q(incidencias_asignadas__estado__name__in=USER_ACTIVE_INCIDENT_STATES),
            distinct=True,
        ),
        created_active_incidents_count=Count(
            "incidencias_creadas",
            filter=Q(incidencias_creadas__estado__name__in=USER_ACTIVE_INCIDENT_STATES),
            distinct=True,
        ),
    ).annotate(
        active_incidents_count=F("assigned_active_incidents_count") + F("created_active_incidents_count")
    ).order_by("-date_joined")
    q = request.GET.get("q")
    if q:
        from ..services import normalize_text, normalize_expression
        normalized_q = normalize_text(q)
        users_list = users_list.annotate(
            nombre_normalizado=normalize_expression(F('first_name')),
            apellido_normalizado=normalize_expression(F('last_name')),
        ).filter(
            Q(username__icontains=q)
            | Q(nombre_normalizado__contains=normalized_q)
            | Q(apellido_normalizado__contains=normalized_q)
            | Q(email__icontains=q)
        ).distinct()

    area_id = request.GET.get("area")
    if area_id:
        users_list = users_list.filter(area_id=area_id)

    page_obj = Paginator(users_list, REGISTROS_POR_PAGINA).get_page(request.GET.get("page"))
    return {
        "users": page_obj,
        "page_obj": page_obj,
        "areas": Area.objects.all(),
        "query": q,
        "page_querystring": page_querystring(request),
        "creation_form": creation_form or CustomUserCreationForm(),
        "update_form": update_form or AdminUserUpdateForm(),
    }

@login_required
@user_passes_test(is_admin)
def usuarios(request):
    return render(request, "tickets/usuarios.html", get_usuarios_context(request))

@login_required
@user_passes_test(is_admin)
@require_POST
def crear_usuario(request):
    form = CustomUserCreationForm(request.POST)
    if form.is_valid():
        user = form.save()
        fecha = timezone.localtime().strftime("%d/%m/%Y %H:%M")
        registrar_auditoria(
            request,
            "Usuarios",
            "creó usuario",
            (
                f"El administrador {admin_actor_label(request.user)} creó el usuario {target_user_label(user)} "
                f"con rol '{user.get_role_display()}' y área '{field_display('area', user.area)}'. "
                f"Fecha y hora: {fecha}."
            ),
            user.id,
        )
        message = f"Usuario {user.username} creado exitosamente."
        if is_fetch_request(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": message,
                    "user_id": user.pk,
                    "row_html": render_user_row(request, user),
                },
                status=201,
            )
        messages.success(request, message)
        return redirect("usuarios")

    if is_fetch_request(request):
        return JsonResponse(
            {
                "success": False,
                "message": "No se pudo crear el usuario. Verifique los campos.",
                "errors": form_errors_to_dict(form),
            },
            status=400,
        )

    messages.error(request, "No se pudo crear el usuario. Verifique los campos.")
    context = get_usuarios_context(request, creation_form=form)
    context["show_modal_nuevo"] = True
    return render(request, "tickets/usuarios.html", context)

@login_required
@user_passes_test(is_admin)
@require_POST
def editar_usuario(request, pk):
    usuario = get_object_or_404(CustomUser, pk=pk)
    if is_protected_superuser_target(request.user, usuario):
        return reject_request(request, protected_superuser_message(), status=403)

    before = {
        "first_name": usuario.first_name,
        "last_name": usuario.last_name,
        "email": usuario.email,
        "telefono": usuario.telefono,
        "role": usuario.role,
        "area": usuario.area,
    }
    form = AdminUserUpdateForm(request.POST, instance=usuario, actor=request.user)
    if form.is_valid():
        user = form.save()

        cambios = build_user_change_details(before, user)
        if before["role"] != user.role:
            delete_user_sessions(user)

        fecha = timezone.localtime().strftime("%d/%m/%Y %H:%M")
        if cambios:
            desc = (
                f"El administrador {admin_actor_label(request.user)} modificó el usuario {target_user_label(user)}. "
                f"Campos modificados: {'; '.join(cambios)}. Fecha y hora: {fecha}."
            )
        else:
            desc = (
                f"El administrador {admin_actor_label(request.user)} revisó el usuario {target_user_label(user)} "
                f"sin cambios de datos. Fecha y hora: {fecha}."
            )

        registrar_auditoria(
            request,
            "Usuarios",
            "editó usuario",
            desc,
            user.id,
        )
        message = f"Usuario {usuario.username} actualizado."
        if is_fetch_request(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": message,
                    "user_id": user.pk,
                    "row_html": render_user_row(request, user),
                }
            )
        messages.success(request, message)
        return redirect("usuarios")

    if is_fetch_request(request):
        return JsonResponse(
            {
                "success": False,
                "message": "No se pudo actualizar el usuario.",
                "errors": form_errors_to_dict(form),
            },
            status=400,
        )

    messages.error(request, "No se pudo actualizar el usuario.")
    context = get_usuarios_context(request, update_form=form)
    context["show_modal_editar"] = True
    context["usuario_id_error"] = pk
    return render(request, "tickets/usuarios.html", context)

@login_required
@user_passes_test(is_admin)
@require_POST
def toggle_usuario_status(request, pk):
    usuario = get_object_or_404(CustomUser, pk=pk)
    if usuario == request.user:
        return reject_request(request, "No puedes desactivarte a ti mismo.")

    if is_protected_superuser_target(request.user, usuario):
        return reject_request(request, protected_superuser_message(), status=403)

    will_disable = usuario.is_active
    motivo, error = require_motivo(request, "suspender/deshabilitar este usuario" if will_disable else "activar este usuario")
    if error:
        return reject_request(request, error)

    if will_disable and usuario.role == CustomUser.ROL_ADMIN:
        active_admins = CustomUser.objects.filter(
            is_active=True,
            role=CustomUser.ROL_ADMIN,
        ).exclude(pk=usuario.pk)
        if not active_admins.exists():
            return reject_request(
                request,
                "No se puede deshabilitar el único administrador activo. Debe existir al menos un administrador activo.",
            )

    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=["is_active"])
    if not usuario.is_active:
        delete_user_sessions(usuario)

    estado = "activado" if usuario.is_active else "desactivado"
    message = f"Usuario {usuario.username} {estado}."
    fecha = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    detalle = (
        f"El administrador {admin_actor_label(request.user)} {estado} el acceso del usuario "
        f"{target_user_label(usuario)} por el motivo: '{motivo}'. Fecha y hora: {fecha}."
    )
    registrar_auditoria(
        request,
        "Usuarios",
        f"{estado} usuario",
        detalle,
        usuario.id,
    )

    if is_fetch_request(request):
        return JsonResponse(
            {
                "success": True,
                "message": message,
                "user_id": usuario.pk,
                "is_active": usuario.is_active,
                "row_html": render_user_row(request, usuario),
            }
        )

    messages.info(request, message)
    return redirect("usuarios")

@login_required
@user_passes_test(is_admin)
@require_POST
def reset_password_admin(request, pk):
    usuario = get_object_or_404(CustomUser, pk=pk)
    if usuario == request.user:
        return reject_request(request, "No puedes restablecerte tu propia contraseña desde el módulo de usuarios.")

    if is_protected_superuser_target(request.user, usuario):
        return reject_request(request, protected_superuser_message(), status=403)

    motivo, error = require_motivo(request, "restablecer la contraseña")
    if error:
        return reject_request(request, error)

    usuario.set_password(build_temporary_password(usuario.username))
    usuario.cambio_clave_pendiente = True
    usuario.last_password_change = timezone.now()
    usuario.save(update_fields=["password", "must_change_password", "last_password_change"])
    delete_user_sessions(usuario)
    fecha = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    registrar_auditoria(
        request,
        "Usuarios",
        "reseteó contraseña",
        (
            f"El administrador {admin_actor_label(request.user)} restableció la contraseña del usuario "
            f"{target_user_label(usuario)}. Motivo: '{motivo}'. Se cerraron sus sesiones activas y se marcó "
            f"cambio obligatorio de clave. Fecha y hora: {fecha}."
        ),
        usuario.id,
    )
    message = f"Clave de {usuario.username} restablecida correctamente."
    if is_fetch_request(request):
        return JsonResponse(
            {
                "success": True,
                "message": message,
                "user_id": usuario.pk,
                "row_html": render_user_row(request, usuario),
            }
        )
    messages.success(request, message)
    return redirect("usuarios")

@login_required
def mi_perfil(request):
    user = request.user
    profile_form = ProfileUpdateForm(instance=user)
    password_form = CustomPasswordChangeForm(user)
    if request.method == "POST":
        if "update_profile" in request.POST:
            profile_form = ProfileUpdateForm(request.POST, instance=user)
            if profile_form.is_valid():
                perfil_edit = profile_form.save(commit=False)
                if user.role != "administrador":
                    perfil_edit.first_name = user.first_name
                    perfil_edit.last_name = user.last_name
                    perfil_edit.area = user.area
                perfil_edit.save()
                registrar_auditoria(
                    request,
                    "Sistema",
                    "Actualizó perfil",
                    f"El usuario {user.username} actualizó sus datos de contacto.",
                    user.id,
                )
                success_msg = "Datos personales actualizados."
                if is_fetch_request(request):
                    return JsonResponse({"success": True, "message": success_msg})
                messages.success(request, success_msg)
                return redirect("mi_perfil")

            if is_fetch_request(request):
                return JsonResponse({
                    "success": False,
                    "message": "Error al actualizar el perfil. Verifique los campos.",
                    "errors": form_errors_to_dict(profile_form)
                }, status=400)
            add_form_errors_to_messages(request, profile_form)
        elif "change_password" in request.POST:
            if not user.check_password(request.POST.get("old_password", "")):
                if is_fetch_request(request):
                    return JsonResponse({
                        "success": False,
                        "message": CURRENT_PASSWORD_ERROR,
                        "errors": {"old_password": [CURRENT_PASSWORD_ERROR]},
                    }, status=400)
                messages.error(request, CURRENT_PASSWORD_ERROR)
                return render(
                    request,
                    "tickets/mi_perfil.html",
                    {"profile_form": profile_form, "password_form": password_form},
                    status=400,
                )

            password_form = CustomPasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user_updated = password_form.save(commit=False)
                user_updated.cambio_clave_pendiente = False
                user_updated.last_password_change = timezone.now()
                user_updated.save(update_fields=["password", "must_change_password", "last_password_change"])
                update_session_auth_hash(request, user_updated)
                registrar_auditoria(
                    request,
                    "Sistema",
                    "Cambio de contraseña",
                    f"El usuario {user.username} cambió su contraseña desde el perfil.",
                    user.id,
                )
                success_msg = "Contraseña cambiada exitosamente."
                if is_fetch_request(request):
                    return JsonResponse({"success": True, "message": success_msg})
                messages.success(request, success_msg)
                return redirect("mi_perfil")

            if is_fetch_request(request):
                return JsonResponse({
                    "success": False, 
                    "message": "No se pudo actualizar la contraseña. Verifique los errores.",
                    "errors": form_errors_to_dict(password_form)
                }, status=400)
            add_form_errors_to_messages(request, password_form)
    return render(
        request,
        "tickets/mi_perfil.html",
        {"profile_form": profile_form, "password_form": password_form},
    )

@login_required
@require_POST
def update_photo_view(request):
    form = ProfilePhotoForm(request.POST, request.FILES, instance=request.user)
    if form.is_valid():
        user = form.save()
        registrar_auditoria(
            request,
            "Sistema",
            "Actualizó foto",
            f"El usuario {user.username} actualizó su foto de perfil.",
            user.id,
        )
        return JsonResponse({"success": True, "message": "Foto actualizada.", "url": user.foto.url})
    error_message = next(iter(form.errors.get("foto", ["No se pudo actualizar la foto de perfil."])))
    return JsonResponse({"success": False, "message": error_message}, status=400)
