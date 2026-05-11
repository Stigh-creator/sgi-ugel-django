from django.urls import NoReverseMatch, reverse
from django.test import TestCase

from tickets.models import Area, CustomUser

from .models import Auditoria


class AuditoriaExportTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(name="Sistemas")
        self.admin = CustomUser.objects.create_user(
            username="12345678",
            password="Admin1234!",
            first_name="Ana",
            last_name="Admin",
            role=CustomUser.ROL_ADMIN,
            area=self.area,
            telefono="999111222",
            is_staff=True,
        )
        self.usuario = CustomUser.objects.create_user(
            username="87654321",
            password="Usuario1234!",
            first_name="Luis",
            last_name="Usuario",
            role="usuario",
            area=self.area,
            telefono="999111333",
        )
        Auditoria.objects.create(
            usuario=self.admin,
            modulo="Sistema",
            accion="inició sesión",
            descripcion="El administrador inició sesión correctamente.",
            ip="127.0.0.1",
        )

    def test_dashboard_muestra_solo_exportacion_pdf(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("auditoria_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/auditoria/exportar/pdf/")
        self.assertNotContains(response, "/auditoria/exportar/excel/")
        self.assertNotContains(response, "file-earmark-excel")

    def test_pdf_auditoria_requiere_acceso_admin(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("auditoria_export_pdf"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.admin)
        response = self.client.get(reverse("auditoria_export_pdf"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_auditoria_no_tiene_ruta_excel(self):
        with self.assertRaises(NoReverseMatch):
            reverse("auditoria_export_excel")
