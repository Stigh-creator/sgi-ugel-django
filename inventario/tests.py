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
            role="administrador",
            area=self.area,
            telefono="999111222",
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
        self.client.force_login(self.admin)

    def test_baja_logica_sincroniza_estado_y_activo(self):
        response = self.client.post(reverse("equipo_eliminar", args=[self.equipo.pk]))

        self.assertRedirects(response, f"{reverse('inventario_list')}?vista=bajas")
        self.equipo.refresh_from_db()
        self.assertFalse(self.equipo.activo)
        self.assertEqual(self.equipo.estado.nombre, "Dado de baja")
