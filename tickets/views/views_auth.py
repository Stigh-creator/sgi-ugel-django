from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse

from auditoria.utils import registrar_auditoria
from .views_utils import add_form_errors_to_messages
from ..forms.forms_usuarios import CustomPasswordChangeForm

CURRENT_PASSWORD_ERROR = "La contraseña actual no es correcta."

def custom_login_view(request):
    if request.user.is_authenticated:
        return redirect("index")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            redirect_url = "mis_incidencias"
            if user.cambio_clave_pendiente:
                redirect_url = "password_change_forced"
            elif user.role == "administrador":
                redirect_url = "dashboard_admin"
            elif user.role == "tecnico":
                redirect_url = "dashboard_tecnico"
            elif user.role == "almacen":
                redirect_url = "inventario_list"
                
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'fetch' in request.headers.get('Sec-Fetch-Mode', ''):
                return JsonResponse({"success": True, "redirect_url": reverse(redirect_url)})
                
            return redirect(redirect_url)
            
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'fetch' in request.headers.get('Sec-Fetch-Mode', ''):
            return JsonResponse({"success": False, "message": "Usuario o contraseña incorrectos, o la cuenta está inactiva."})
            
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
        if not request.user.check_password(request.POST.get("old_password", "")):
            messages.error(request, CURRENT_PASSWORD_ERROR)
            return render(request, "tickets/forced_change.html", {"form": form}, status=400)

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
