from django.test import TestCase
from django.urls import reverse

from tickets.models import Area, CustomUser

from .models import Equipo, EstadoEquipo, Marca, TipoEquipo


class InventarioRulesTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(name="UGEL")
        self.admin = CustomUser.objects.create_user(
            username="12345678",
            password="Admin1234!",
            first_name="Ana",
            last_name="Admin",
            role=CustomUser.ROL_ADMIN,
            area=self.area,
            telefono="999111222",
        )
        self.almacen = CustomUser.objects.create_user(
            username="87654321",
            password="Almacen1234!",
            first_name="Luis",
            last_name="Almacen",
            role=CustomUser.ROL_ALMACEN,
            area=self.area,
            telefono="999111333",
        )
        self.superuser = CustomUser.objects.create_superuser(
            username="11112222",
            password="Super1234!",
            first_name="Sonia",
            last_name="Super",
            role=CustomUser.ROL_ADMIN,
            area=self.area,
            telefono="999111444",
        )
        self.marca = Marca.objects.create(nombre="HP")
        self.tipo = TipoEquipo.objects.create(nombre="Laptop")
        self.estado_operativo, _ = EstadoEquipo.objects.get_or_create(nombre="Operativo")
        self.estado_baja, _ = EstadoEquipo.objects.get_or_create(nombre="Dado de baja")
        self.equipo = Equipo.objects.create(
            codigo_equipo="LP-001",
            nombre_equipo="Laptop Dirección",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Probook",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        self.client.force_login(self.almacen)

    def test_admin_solo_puede_consultar_inventario(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("inventario_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.equipo.codigo_equipo)
        self.assertNotContains(response, "Registrar Equipo")
        self.assertNotContains(response, "/inventario/exportar/excel/")
        self.assertContains(response, "/inventario/exportar/pdf/")

        response = self.client.get(reverse("equipo_detalle", args=[self.equipo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.equipo.codigo_equipo)
        self.assertNotContains(response, "Actualización manual de estado")

    def test_almacen_ingresa_directo_a_inventario(self):
        self.client.force_login(self.almacen)

        response = self.client.get(reverse("index"))

        self.assertRedirects(response, reverse("inventario_list"))

    def test_admin_no_puede_modificar_inventario(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("equipo_editar", args=[self.equipo.pk]),
            {
                "codigo_equipo": self.equipo.codigo_equipo,
                "nombre_equipo": "Nombre no permitido",
                "tipo_equipo": self.tipo.pk,
                "marca": self.marca.pk,
                "modelo": self.equipo.modelo,
                "numero_serie": self.equipo.numero_serie or "",
                "area": self.area.pk,
                "estado": self.estado_operativo.pk,
                "disponibilidad": Equipo.DISPONIBILIDAD_EN_USO,
                "observaciones": self.equipo.observaciones or "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.nombre_equipo, "Laptop Dirección")

    def test_baja_logica_sincroniza_estado_y_activo(self):
        response = self.client.post(reverse("equipo_eliminar", args=[self.equipo.pk]))

        self.assertRedirects(response, f"{reverse('inventario_list')}?vista=bajas")
        self.equipo.refresh_from_db()
        self.assertFalse(self.equipo.activo)
        self.assertEqual(self.equipo.estado.nombre, "Dado de baja")
        self.assertEqual(self.equipo.disponibilidad, Equipo.DISPONIBILIDAD_NO_DISPONIBLE)

    def test_inoperativo_se_marca_no_disponible(self):
        estado_inoperativo, _ = EstadoEquipo.objects.get_or_create(nombre="Inoperativo")

        response = self.client.post(
            reverse("equipo_actualizar_estado", args=[self.equipo.pk]),
            {
                "estado": estado_inoperativo.pk,
                "observacion": "Equipo retirado por falla crítica.",
            },
        )

        self.assertRedirects(response, reverse("equipo_detalle", args=[self.equipo.pk]))
        self.equipo.refresh_from_db()
        self.assertTrue(self.equipo.activo)
        self.assertEqual(self.equipo.estado.nombre, "Inoperativo")
        self.assertEqual(self.equipo.disponibilidad, Equipo.DISPONIBILIDAD_NO_DISPONIBLE)

    def test_almacen_puede_editar_disponibilidad_sin_cambiar_estado(self):
        response = self.client.post(
            reverse("equipo_editar", args=[self.equipo.pk]),
            {
                "codigo_equipo": self.equipo.codigo_equipo,
                "nombre_equipo": self.equipo.nombre_equipo,
                "tipo_equipo": self.tipo.pk,
                "marca": self.marca.pk,
                "modelo": self.equipo.modelo,
                "numero_serie": self.equipo.numero_serie or "",
                "area": self.area.pk,
                "estado": self.estado_operativo.pk,
                "disponibilidad": Equipo.DISPONIBILIDAD_EN_USO,
                "observaciones": self.equipo.observaciones or "",
            },
        )

        self.assertRedirects(response, reverse("inventario_list"))
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado, self.estado_operativo)
        self.assertEqual(self.equipo.disponibilidad, Equipo.DISPONIBILIDAD_EN_USO)

    def test_excel_de_inventario_solo_almacen_y_superusuario(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("inventario_export_excel"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.almacen)
        response = self.client.get(reverse("inventario_export_excel"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        self.client.force_login(self.superuser)
        response = self.client.get(reverse("inventario_export_excel"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_pdf_de_inventario_disponible_para_roles_con_acceso(self):
        for usuario in (self.admin, self.almacen, self.superuser):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.get(reverse("inventario_export_pdf"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")

                response = self.client.get(reverse("equipo_export_pdf", args=[self.equipo.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")

    def test_excel_legacy_de_inventario_bloquea_admin_y_permite_superusuario(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("export_inventario_excel"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.superuser)
        response = self.client.get(reverse("export_inventario_excel"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_pdf_dashboard_inventario_permite_admin_almacen_y_superusuario(self):
        for usuario in (self.admin, self.almacen, self.superuser):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.get(reverse("export_dashboard_inventario_pdf"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")
