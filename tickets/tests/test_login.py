from django.test import TestCase
from django.urls import reverse

from tickets.models import Area, CustomUser


class LoginModuleTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(name="Soporte")
        self.admin = CustomUser.objects.create_user(
            username="12345678",
            password="Admin1234!",
            first_name="Admin",
            last_name="Principal",
            role="administrador",
            area=self.area,
            is_staff=True,
            telefono="911111111",
        )
        self.tecnico = CustomUser.objects.create_user(
            username="23456789",
            password="Tecnico123!",
            first_name="Tec",
            last_name="Nico",
            role="tecnico",
            area=self.area,
            telefono="922222222",
        )
        self.trabajador = CustomUser.objects.create_user(
            username="34567890",
            password="Trabajador123!",
            first_name="Tra",
            last_name="Bajador",
            role="usuario",
            area=self.area,
            telefono="933333333",
        )
        self.almacen = CustomUser.objects.create_user(
            username="45678901",
            password="Almacen123!",
            first_name="Luis",
            last_name="Almacen",
            role=CustomUser.ROL_ALMACEN,
            area=self.area,
            telefono="944444444",
        )

    def test_login_redirige_admin_a_dashboard_admin(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.admin.username, "password": "Admin1234!"},
        )
        self.assertRedirects(response, reverse("dashboard_admin"))

    def test_login_redirige_tecnico_a_dashboard_tecnico(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.tecnico.username, "password": "Tecnico123!"},
        )
        self.assertRedirects(response, reverse("dashboard_tecnico"))

    def test_login_redirige_trabajador_a_mis_incidencias(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.trabajador.username, "password": "Trabajador123!"},
        )
        self.assertRedirects(response, reverse("mis_incidencias"))

    def test_login_redirige_almacen_a_inventario(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.almacen.username, "password": "Almacen123!"},
        )
        self.assertRedirects(response, reverse("inventario_list"))

    def test_login_redirige_a_cambio_obligatorio_si_aplica(self):
        self.trabajador.must_change_password = True
        self.trabajador.save(update_fields=["must_change_password"])

        response = self.client.post(
            reverse("login"),
            {"username": self.trabajador.username, "password": "Trabajador123!"},
        )
        self.assertRedirects(response, reverse("password_change_forced"))

    def test_usuario_inactivo_no_puede_iniciar_sesion(self):
        self.trabajador.is_active = False
        self.trabajador.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("login"),
            {"username": self.trabajador.username, "password": "Trabajador123!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse("_auth_user_id" in self.client.session)

    def test_middleware_fuerza_cambio_obligatorio_en_rutas_protegidas(self):
        self.trabajador.must_change_password = True
        self.trabajador.save(update_fields=["must_change_password"])
        self.client.force_login(self.trabajador)

        response = self.client.get(reverse("mis_incidencias"))
        self.assertRedirects(response, reverse("password_change_forced"))
