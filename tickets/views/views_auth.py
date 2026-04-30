from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils import timezone

from auditoria.utils import registrar_auditoria
from .views_utils import add_form_errors_to_messages
from ..forms.forms_usuarios import CustomPasswordChangeForm

def custom_login_view(request):
    if request.user.is_authenticated:
        return redirect("index")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.cambio_clave_pendiente:
                return redirect("password_change_forced")
            if user.role == "administrador":
                return redirect("dashboard_admin")
            if user.role == "tecnico":
                return redirect("dashboard_tecnico")
            return redirect("mis_incidencias")
        messages.error(request, "Usuario o contraseña incorrectos, o la cuenta está inactiva.")
    return render(request, "registration/login.html", {"form": form})

@login_required
def logout_view(request):
    list(messages.get_messages(request))
    logout(request)
    return redirect("login")

@login_required
def password_change_forced(request):
    form = CustomPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.save(commit=False)
            user.cambio_clave_pendiente = False
            user.last_password_change = timezone.now()
            user.save(update_fields=["password", "must_change_password", "last_password_change"])
            update_session_auth_hash(request, user)
            registrar_auditoria(
                request,
                "Sistema",
                "Cambio de contraseña",
                f"El usuario {user.username} realizó el cambio de contraseña obligatorio.",
                user.id,
            )
            messages.success(request, "Contraseña actualizada.")
            return redirect("index")
        add_form_errors_to_messages(request, form)
    return render(request, "tickets/forced_change.html", {"form": form})
