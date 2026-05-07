from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from tickets.models import Area, CustomUser, Incidencia


def build_test_image(name="foto.png", size=(50, 50), image_format="PNG", content_type="image/png"):
    buffer = BytesIO()
    Image.new("RGB", size, (0, 128, 255)).save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class MiPerfilModuleTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(name="Operaciones")
        self.admin = CustomUser.objects.create_user(
            username="44445555",
            password="Admin1234!",
            first_name="Ana",
            last_name="Gomez",
            role="administrador",
            area=self.area,
            is_staff=True,
            email="ana@example.com",
            telefono="944444444",
        )
        self.usuario = CustomUser.objects.create_user(
            username="55556666",
            password="Usuario123!",
            first_name="Luis",
            last_name="Rojas",
            role="usuario",
            area=self.area,
            email="luis@example.com",
            telefono="987654321",
        )
        self.otro_usuario = CustomUser.objects.create_user(
            username="66667777",
            password="OtroUsuario123!",
            first_name="Marta",
            last_name="Salas",
            role="usuario",
            area=self.area,
            email="marta@example.com",
            telefono="123456789",
        )

    def test_usuario_puede_actualizar_su_perfil_permitido(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("mi_perfil"),
            {
                "update_profile": "1",
                "first_name": "CambioNoPermitido",
                "last_name": "CambioNoPermitido",
                "email": "nuevo@example.com",
                "telefono": "999888777",
            },
        )

        self.assertRedirects(response, reverse("mi_perfil"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Luis")
        self.assertEqual(self.usuario.last_name, "Rojas")
        self.assertEqual(self.usuario.email, "nuevo@example.com")
        self.assertEqual(self.usuario.telefono, "999888777")

    def test_admin_puede_actualizar_nombre_y_apellido(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("mi_perfil"),
            {
                "update_profile": "1",
                "first_name": "Andrea",
                "last_name": "Martinez",
                "email": "andrea@example.com",
                "telefono": "999888777",
            },
        )

        self.assertRedirects(response, reverse("mi_perfil"))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.first_name, "Andrea")
        self.assertEqual(self.admin.last_name, "Martinez")

    def test_admin_con_incidencia_activa_no_puede_cambiar_nombre_en_mi_perfil(self):
        Incidencia.objects.create(
            creador=self.usuario,
            tecnico_asignado=self.admin,
            area=self.area,
            categoria="hardware",
            descripcion="Equipo sin red",
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("mi_perfil"),
            {
                "update_profile": "1",
                "first_name": "Andrea",
                "last_name": "Martinez",
                "email": "andrea.contacto@example.com",
                "telefono": "999888777",
            },
            follow=True,
        )

        self.admin.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.admin.first_name, "Ana")
        self.assertEqual(self.admin.last_name, "Gomez")
        self.assertEqual(self.admin.email, "ana@example.com")
        self.assertContains(response, "incidencias activas o pendientes")

    def test_validacion_backend_rechaza_nombres_invalidos(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("mi_perfil"),
            {
                "update_profile": "1",
                "first_name": "Ana123",
                "last_name": "Gomez",
                "email": "ana@example.com",
                "telefono": "999888777",
            },
            follow=True,
        )

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.first_name, "Ana")
        self.assertContains(response, "solo permite letras y espacios", status_code=200)

    def test_cambio_password_actualiza_flags_de_seguridad(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("mi_perfil"),
            {
                "change_password": "1",
                "old_password": "Usuario123!",
                "new_password1": "NuevaClave123!",
                "new_password2": "NuevaClave123!",
            },
        )

        self.assertRedirects(response, reverse("mi_perfil"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("NuevaClave123!"))

    def test_cambio_password_rechaza_dni_en_nueva_clave(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("mi_perfil"),
            {
                "change_password": "1",
                "old_password": "Usuario123!",
                "new_password1": "Clave55556666!",
                "new_password2": "Clave55556666!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La contraseña es demasiado similar a sus datos personales")

    def test_cambio_password_forzado_funciona(self):
        self.client.force_login(self.usuario)
        self.usuario.must_change_password = True
        self.usuario.save(update_fields=["must_change_password"])

        response = self.client.post(
            reverse("password_change_forced"),
            {
                "old_password": "Usuario123!",
                "new_password1": "Forzada123!",
                "new_password2": "Forzada123!",
            },
        )

        self.assertRedirects(response, reverse("index"), fetch_redirect_response=False)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.must_change_password)
        self.assertTrue(self.usuario.check_password("Forzada123!"))

    def test_update_photo_rechaza_formato_invalido(self):
        self.client.force_login(self.usuario)
        invalid_file = build_test_image(name="archivo.gif", image_format="GIF", content_type="image/gif")

        response = self.client.post(reverse("update_photo"), {"foto": invalid_file})

        self.assertEqual(response.status_code, 400)
        self.assertIn("JPG, PNG o WebP", response.json()["message"])

    def test_update_photo_guarda_imagen_valida(self):
        self.client.force_login(self.usuario)
        valid_file = build_test_image()

        response = self.client.post(reverse("update_photo"), {"foto": valid_file})

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(bool(self.usuario.foto))
        self.assertTrue(response.json()["url"].startswith("/media/perfiles/"))

    def test_update_photo_guarda_imagen_webp(self):
        self.client.force_login(self.usuario)
        valid_file = build_test_image(name="perfil.webp", image_format="WEBP", content_type="image/webp")

        response = self.client.post(reverse("update_photo"), {"foto": valid_file})

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(bool(self.usuario.foto))
        self.assertTrue(self.usuario.foto.name.endswith(".webp"))

    def test_mi_perfil_rechaza_telefono_duplicado(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("mi_perfil"),
            {
                "update_profile": "1",
                "first_name": "Luis",
                "last_name": "Rojas",
                "email": "nuevo@example.com",
                "telefono": self.otro_usuario.telefono,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este teléfono ya está en uso por otro usuario.")
