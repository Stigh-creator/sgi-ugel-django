from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

import cargar_maestros


class Command(BaseCommand):
    help = "Asegura datos base obligatorios del SGI: maestros y superusuario inicial."

    def handle(self, *args, **options):
        with transaction.atomic():
            cargar_maestros.cargar_datos_maestros()
            self._ensure_admin()

        self.stdout.write(self.style.SUCCESS("Base obligatoria SGI asegurada."))

    def _ensure_admin(self):
        User = get_user_model()
        admin, created = User.objects.update_or_create(
            username="00000000",
            defaults={
                "first_name": "Admin",
                "last_name": "Maestro",
                "email": "admin@example.com",
                "telefono": "999999999",
                "role": User.ROL_ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
                "must_change_password": False,
            },
        )
        admin.set_password("P@ssword")
        admin.save(update_fields=["password", "last_password_change"])
        estado = "creado" if created else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Superusuario Admin {estado}: DNI 00000000 / clave P@ssword."))
