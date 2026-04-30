from django.core.exceptions import ValidationError
from django.test import TestCase

from inventario.models import Equipo, EstadoEquipo, Marca, TipoEquipo
from tickets.models import Area, CustomUser, Incidencia
from tickets.services import assign_incidencia_service, create_incidencia_service, get_estado


class IncidenciasBusinessRulesTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(name="Sistemas")
        self.marca = Marca.objects.create(nombre="Dell")
        self.tipo = TipoEquipo.objects.create(nombre="PC")
        self.usuario = CustomUser.objects.create_user(
            username="12345678",
            password="Usuario123!",
            first_name="Luis",
            last_name="Perez",
            role="usuario",
            area=self.area,
            telefono="900000001",
        )
        self.admin = CustomUser.objects.create_user(
            username="87654321",
            password="Admin1234!",
            first_name="Ana",
            last_name="Admin",
            role="administrador",
            area=self.area,
            telefono="900000002",
        )
        self.tecnico = CustomUser.objects.create_user(
            username="11223344",
            password="Tecnico123!",
            first_name="Tito",
            last_name="Tech",
            role="tecnico",
            area=self.area,
            telefono="900000003",
        )
        self.estado_operativo, _ = EstadoEquipo.objects.get_or_create(nombre="Operativo")
        self.estado_revision, _ = EstadoEquipo.objects.get_or_create(nombre="En revisión")
        self.estado_reparacion, _ = EstadoEquipo.objects.get_or_create(nombre="En reparación")
        self.equipo = Equipo.objects.create(
            codigo_equipo="PC-001",
            nombre_equipo="PC Mesa Partes",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )

    def test_crear_incidencia_genera_codigo_y_cambia_equipo_a_en_revision(self):
        incidencia = Incidencia(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="alta",
            descripcion="La computadora no enciende desde esta mañana.",
        )

        create_incidencia_service(incidencia=incidencia, extra_images=[])

        incidencia.refresh_from_db()
        self.equipo.refresh_from_db()
        self.assertEqual(incidencia.codigo, f"INC-{incidencia.fecha_creacion.year}-{incidencia.pk:04d}")
        self.assertEqual(self.equipo.estado.nombre, "En revisión")
        self.assertTrue(self.equipo.activo)

    def test_no_permite_crear_incidencia_si_equipo_ya_no_esta_operativo(self):
        self.equipo.estado = self.estado_reparacion
        self.equipo.save(update_fields=["estado", "actualizado_en"])
        incidencia = Incidencia(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="alta",
            descripcion="Reporte concurrente del equipo.",
        )

        with self.assertRaisesMessage(ValidationError, "ya no está disponible"):
            create_incidencia_service(incidencia=incidencia, extra_images=[])

    def test_limita_asignacion_a_cuatro_tickets_activos_por_tecnico(self):
        for index in range(4):
            Incidencia.objects.create(
                creador=self.usuario,
                area=self.area,
                categoria="software",
                prioridad="media",
                descripcion=f"Incidencia previa {index}",
                tecnico_asignado=self.tecnico,
                estado=get_estado(Incidencia.ESTADO_ASIGNADO),
                fecha_asignacion=self.usuario.last_password_change,
            )

        nueva = Incidencia.objects.create(
            creador=self.admin,
            area=self.area,
            categoria="software",
            prioridad="media",
            descripcion="Nueva incidencia para asignar",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )

        with self.assertRaisesMessage(ValidationError, "máximo permitido es 4"):
            assign_incidencia_service(nueva, tecnico=self.tecnico)
