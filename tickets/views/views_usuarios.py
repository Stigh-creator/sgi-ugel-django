from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator
from django.db.models import Q
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
    ProfilePhotoForm,
    ProfileUpdateForm,
    build_temporary_password,
)

REGISTROS_POR_PAGINA = 10
CURRENT_PASSWORD_ERROR = "La contraseña actual no es correcta."

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
    users_list = CustomUser.objects.select_related("area").all().order_by("-date_joined")
    q = request.GET.get("q")
    if q:
        from ..services import normalize_text, normalize_expression
        from django.db.models import F
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
        registrar_auditoria(
            request,
            "Usuarios",
            "creó usuario",
            f"Se creó el usuario {user.username} - {user.get_full_name()}",
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
    area_ant = usuario.area
    role_ant = usuario.role
    form = AdminUserUpdateForm(request.POST, instance=usuario, actor=request.user)
    if form.is_valid():
        user = form.save()
        
        cambios = []
        if area_ant != user.area:
            cambios.append(f"Área: {area_ant} -> {user.area}")
        if role_ant != user.role:
            cambios.append(f"Rol: {role_ant} -> {user.role}")
            delete_user_sessions(user)
            
        desc = f"Se actualizó la información de {user.username}."
        if cambios:
            desc += " Cambios: " + " | ".join(cambios)

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
        message = "No puedes desactivarte a ti mismo."
        if is_fetch_request(request):
            return JsonResponse({"success": False, "message": message}, status=400)
        messages.error(request, message)
        return redirect("usuarios")

    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=["is_active"])
    if not usuario.is_active:
        delete_user_sessions(usuario)

    estado = "activado" if usuario.is_active else "desactivado"
    message = f"Usuario {usuario.username} {estado}."
    registrar_auditoria(
        request,
        "Usuarios",
        f"{estado} usuario",
        f"Se {estado} al usuario ID: {usuario.username} - {usuario.get_full_name()}",
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
    usuario.set_password(build_temporary_password(usuario.username))
    usuario.cambio_clave_pendiente = True
    usuario.last_password_change = timezone.now()
    usuario.save(update_fields=["password", "must_change_password", "last_password_change"])
    delete_user_sessions(usuario)
    motivo = request.POST.get("motivo", "No especificado")
    registrar_auditoria(
        request,
        "Usuarios",
        "reseteó contraseña",
        f"Se restableció contraseña al usuario {usuario.username}. Motivo: {motivo}",
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
