from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse

from tickets.forms.forms_usuarios import build_temporary_password
from tickets.models import Area, CustomUser


class UsuariosAdminModuleTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(name="TI")
        self.area_2 = Area.objects.create(name="Mesa de Partes")
        self.admin = CustomUser.objects.create_user(
            username="11112222",
            password="Admin1234!",
            first_name="Admin",
            last_name="General",
            role="administrador",
            area=self.area,
            is_staff=True,
            telefono="955555555",
        )
        self.usuario = CustomUser.objects.create_user(
            username="33334444",
            password="Usuario123!",
            first_name="Pedro",
            last_name="Lopez",
            role="usuario",
            area=self.area,
            telefono="966666666",
        )
        self.client.force_login(self.admin)

    def test_admin_puede_crear_usuario_con_dni_valido(self):
        response = self.client.post(
            reverse("crear_usuario"),
            {
                "username": "87654321",
                "first_name": "Maria",
                "last_name": "Perez",
                "email": "maria@example.com",
                "telefono": "977777777",
                "role": "tecnico",
                "area": self.area.pk,
            },
        )

        self.assertRedirects(response, reverse("usuarios"))
        new_user = CustomUser.objects.get(username="87654321")
        self.assertTrue(new_user.must_change_password)
        self.assertTrue(new_user.check_password(build_temporary_password("87654321")))

    def test_no_permite_crear_usuario_con_dni_invalido(self):
        response = self.client.post(
            reverse("crear_usuario"),
            {
                "username": "AB12",
                "first_name": "Maria",
                "last_name": "Perez",
                "email": "maria@example.com",
                "telefono": "977777777",
                "role": "tecnico",
                "area": self.area.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CustomUser.objects.filter(username="AB12").exists())

    def test_no_permite_crear_usuario_con_dni_duplicado(self):
        response = self.client.post(
            reverse("crear_usuario"),
            {
                "username": self.usuario.username,
                "first_name": "Otro",
                "last_name": "Usuario",
                "email": "otro@example.com",
                "telefono": "977777777",
                "role": "usuario",
                "area": self.area.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CustomUser.objects.filter(username=self.usuario.username).count(), 1)

    def test_fetch_devuelve_errores_de_validacion_sin_recargar(self):
        response = self.client.post(
            reverse("crear_usuario"),
            {
                "username": "12A",
                "first_name": "Pedro1",
                "last_name": "Lopez",
                "email": "correo-invalido",
                "telefono": "abc",
                "role": "usuario",
                "area": self.area.pk,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertIn("username", payload["errors"])
        self.assertIn("first_name", payload["errors"])

    def test_acciones_criticas_requieren_post(self):
        toggle_response = self.client.get(reverse("toggle_usuario_status", args=[self.usuario.pk]))
        reset_response = self.client.get(reverse("reset_password_admin", args=[self.usuario.pk]))

        self.assertEqual(toggle_response.status_code, 405)
        self.assertEqual(reset_response.status_code, 405)

    def test_desactivar_usuario_invalida_sesiones(self):
        other_client = self.client_class()
        other_client.force_login(self.usuario)
        self.assertTrue(Session.objects.exists())

        response = self.client.post(reverse("toggle_usuario_status", args=[self.usuario.pk]))

        self.assertRedirects(response, reverse("usuarios"))
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertFalse(Session.objects.filter(session_key=other_client.session.session_key).exists())

    def test_reset_password_admin_funciona_y_cierra_sesiones(self):
        other_client = self.client_class()
        other_client.force_login(self.usuario)

        response = self.client.post(reverse("reset_password_admin", args=[self.usuario.pk]))

        self.assertRedirects(response, reverse("usuarios"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.must_change_password)
        self.assertTrue(self.usuario.check_password(build_temporary_password(self.usuario.username)))
        self.assertFalse(Session.objects.filter(session_key=other_client.session.session_key).exists())

    def test_admin_puede_editar_usuario(self):
        response = self.client.post(
            reverse("editar_usuario", args=[self.usuario.pk]),
            {
                "first_name": "Carlos",
                "last_name": "Ramirez",
                "email": "carlos@example.com",
                "telefono": "988888888",
                "role": "tecnico",
                "area": self.area_2.pk,
            },
        )

        self.assertRedirects(response, reverse("usuarios"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Carlos")
        self.assertEqual(self.usuario.last_name, "Ramirez")
        self.assertEqual(self.usuario.role, "tecnico")
        self.assertEqual(self.usuario.area, self.area_2)

    def test_no_permite_crear_usuario_con_telefono_duplicado(self):
        self.usuario.telefono = "999111222"
        self.usuario.save(update_fields=["telefono"])

        response = self.client.post(
            reverse("crear_usuario"),
            {
                "username": "87651234",
                "first_name": "Maria",
                "last_name": "Perez",
                "email": "maria2@example.com",
                "telefono": "999111222",
                "role": "tecnico",
                "area": self.area.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CustomUser.objects.filter(username="87651234").exists())
