from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class EnforcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            if not user.is_active:
                logout(request)
                messages.error(request, "Tu cuenta se encuentra inactiva. Contacta al administrador.")
                return redirect("login")

            forced_change_url = reverse("password_change_forced")
            allowed_paths = {
                forced_change_url,
                reverse("logout"),
            }

            if user.cambio_clave_pendiente and request.path not in allowed_paths:
                return redirect("password_change_forced")

            if request.method == "GET":
                last_seen = user.last_seen
                now = timezone.now()
                if not last_seen or (now - last_seen).total_seconds() >= 60:
                    get_user_model().objects.filter(pk=user.pk).update(last_seen=now)
                    user.last_seen = now

        return self.get_response(request)
