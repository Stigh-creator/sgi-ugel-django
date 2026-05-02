from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from auditoria.models import Auditoria
from inventario.models import Equipo, EstadoEquipo, Marca, TipoEquipo
from tickets.models import Area, Comentario, CustomUser, Incidencia
from tickets.services import (
    aceptar_incidencia_service,
    assign_incidencia_service,
    create_incidencia_service,
    get_estado,
    rechazar_incidencia_service,
)


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
        self.tecnico_2 = CustomUser.objects.create_user(
            username="44332211",
            password="Tecnico123!",
            first_name="Carlos",
            last_name="Soporte",
            role=CustomUser.ROL_TECNICO,
            area=self.area,
            telefono="900000004",
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

    def test_prioridad_es_inmutable_fuera_de_pendiente(self):
        incidencia = Incidencia.objects.create(
            creador=self.admin,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_ALTA,
            descripcion="Ticket administrativo con prioridad alta.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )

        incidencia.prioridad = Incidencia.PRIORIDAD_BAJA
        incidencia.save(update_fields=["prioridad"])

        incidencia.refresh_from_db()
        self.assertEqual(incidencia.prioridad, Incidencia.PRIORIDAD_ALTA)

    def test_tecnico_asignado_puede_aceptar_ticket_asignado(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket asignado para aceptación.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )

        aceptar_incidencia_service(incidencia, self.tecnico)

        incidencia.refresh_from_db()
        self.assertEqual(incidencia.estado_actual, Incidencia.ESTADO_EN_PROCESO)

    def test_rechazo_requiere_motivo_y_registra_estado(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket asignado para rechazo.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )

        with self.assertRaisesMessage(ValidationError, "motivo de rechazo es obligatorio"):
            rechazar_incidencia_service(incidencia, self.tecnico, "")

        motivo = rechazar_incidencia_service(incidencia, self.tecnico, "No corresponde a mi especialidad.")

        incidencia.refresh_from_db()
        self.assertEqual(motivo, "No corresponde a mi especialidad.")
        self.assertEqual(incidencia.estado_actual, Incidencia.ESTADO_RECHAZADO)
        self.assertIsNone(incidencia.tecnico_asignado)

    def test_usuario_no_asignado_no_puede_aceptar_ticket(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket asignado a otro especialista.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )

        with self.assertRaisesMessage(ValidationError, "especialista asignado"):
            aceptar_incidencia_service(incidencia, self.tecnico_2)

    def test_vista_rechazar_registra_comentario_de_motivo(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket para rechazo desde vista.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )
        self.client.force_login(self.tecnico)

        response = self.client.post(
            reverse("rechazar_incidencia", args=[incidencia.pk]),
            {"motivo": "No tengo acceso al área solicitante."},
        )

        incidencia.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incidencia.estado_actual, Incidencia.ESTADO_RECHAZADO)
        self.assertIsNone(incidencia.tecnico_asignado)
        self.assertTrue(
            Comentario.objects.filter(
                incidencia=incidencia,
                texto__icontains="No tengo acceso al área solicitante.",
            ).exists()
        )
        auditoria = Auditoria.objects.filter(referencia_id=incidencia.pk, accion="rechazó incidencia").first()
        self.assertIsNotNone(auditoria)
        self.assertIn(incidencia.codigo, auditoria.descripcion)
        self.assertIn("rechazó la incidencia", auditoria.descripcion)
        self.assertIn("Motivo: No tengo acceso al área solicitante.", auditoria.descripcion)
        self.assertIn("El ticket ha sido desvinculado", auditoria.descripcion)

    def test_detalle_asignado_muestra_aceptar_rechazar_y_oculta_resolucion(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket visible para flujo de aceptación.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )
        self.client.force_login(self.tecnico)

        response = self.client.get(reverse("detalle_incidencia", args=[incidencia.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aceptar atención")
        self.assertContains(response, "Rechazar")
        self.assertNotContains(response, "Marcar como resuelto")

    def test_reasignar_ticket_en_proceso_vuelve_a_asignado_y_muestra_botones_al_nuevo_tecnico(self):
        incidencia = Incidencia.objects.create(
            creador=self.admin,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_ALTA,
            descripcion="Ticket en proceso que será reasignado.",
            imagen_adjunta="incidencias/evidencia.jpg",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("gestionar_incidencia", args=[incidencia.pk]),
            {
                "categoria": incidencia.categoria,
                "prioridad": Incidencia.PRIORIDAD_BAJA,
                "area": self.area.pk,
                "equipo": "",
                "descripcion": incidencia.descripcion,
                "tecnico_asignado": self.tecnico_2.pk,
                "fecha_programada_atencion": "",
                "hora_programada_atencion": "",
                "observaciones_internas": "Reasignado por disponibilidad.",
            },
        )

        incidencia.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incidencia.tecnico_asignado, self.tecnico_2)
        self.assertEqual(incidencia.estado_actual, Incidencia.ESTADO_ASIGNADO)
        self.assertEqual(incidencia.prioridad, Incidencia.PRIORIDAD_ALTA)

        self.client.force_login(self.tecnico_2)
        detalle = self.client.get(reverse("detalle_incidencia", args=[incidencia.pk]))
        self.assertContains(detalle, "Aceptar atención")
        self.assertContains(detalle, "Rechazar")

        auditoria = Auditoria.objects.filter(referencia_id=incidencia.pk, accion="reasignó técnico").first()
        self.assertIsNotNone(auditoria)
        self.assertIn(incidencia.codigo, auditoria.descripcion)
        self.assertIn("Reasignado de", auditoria.descripcion)
        self.assertIn("Carlos Soporte", auditoria.descripcion)
        self.assertIn("por Ana Admin", auditoria.descripcion)

    def test_auditoria_de_asignacion_inicial_no_muestra_none(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_ALTA,
            descripcion="Ticket pendiente para primera asignación.",
            imagen_adjunta="incidencias/evidencia.jpg",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )
        self.client.force_login(self.admin)

        self.client.post(
            reverse("gestionar_incidencia", args=[incidencia.pk]),
            {
                "categoria": incidencia.categoria,
                "prioridad": incidencia.prioridad,
                "area": self.area.pk,
                "equipo": "",
                "descripcion": incidencia.descripcion,
                "tecnico_asignado": self.tecnico.pk,
                "fecha_programada_atencion": "",
                "hora_programada_atencion": "",
                "observaciones_internas": "Primera asignación.",
            },
        )

        auditoria = Auditoria.objects.filter(referencia_id=incidencia.pk, accion="asignó técnico").first()
        self.assertIsNotNone(auditoria)
        incidencia.refresh_from_db()
        self.assertIn(incidencia.codigo, auditoria.descripcion)
        self.assertIn("Asignación inicial de técnico:", auditoria.descripcion)
        self.assertNotIn("None", auditoria.descripcion)

    def test_auditoria_registra_codigo_y_cambio_real_de_prioridad_en_pendiente(self):
        incidencia = Incidencia.objects.create(
            creador=self.admin,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_ALTA,
            descripcion="Ticket pendiente para cambio de prioridad.",
            imagen_adjunta="incidencias/evidencia.jpg",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )
        self.client.force_login(self.admin)

        self.client.post(
            reverse("gestionar_incidencia", args=[incidencia.pk]),
            {
                "categoria": incidencia.categoria,
                "prioridad": Incidencia.PRIORIDAD_BAJA,
                "area": self.area.pk,
                "equipo": "",
                "descripcion": incidencia.descripcion,
                "tecnico_asignado": self.tecnico.pk,
                "fecha_programada_atencion": "",
                "hora_programada_atencion": "",
                "observaciones_internas": "Se baja prioridad tras revisión.",
            },
        )

        incidencia.refresh_from_db()
        auditoria = Auditoria.objects.filter(referencia_id=incidencia.pk, accion="actualizó prioridad").first()
        self.assertIsNotNone(auditoria)
        self.assertIn(incidencia.codigo, auditoria.descripcion)
        self.assertIn("Prioridad actualizada de Alta a Baja.", auditoria.descripcion)

    def test_ticket_rechazado_bloquea_comentarios_y_queda_en_modo_historico(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket rechazado con historial visible.",
            tecnico_asignado=None,
            estado=get_estado(Incidencia.ESTADO_RECHAZADO),
        )

        self.client.force_login(self.usuario)
        detalle = self.client.get(reverse("detalle_incidencia", args=[incidencia.pk]))
        self.assertContains(detalle, "modo histórico")
        self.assertNotContains(detalle, 'id="comment-form"')

        response = self.client.post(
            reverse("agregar_comentario", args=[incidencia.pk]),
            {"texto": "Intento de comentar en rechazo."},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_reasigna_ticket_rechazado_y_nuevo_tecnico_ve_aceptar_rechazar(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket rechazado que será reasignado.",
            imagen_adjunta="incidencias/evidencia.jpg",
            tecnico_asignado=None,
            estado=get_estado(Incidencia.ESTADO_RECHAZADO),
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("gestionar_incidencia", args=[incidencia.pk]),
            {
                "categoria": incidencia.categoria,
                "prioridad": incidencia.prioridad,
                "area": self.area.pk,
                "equipo": "",
                "descripcion": incidencia.descripcion,
                "tecnico_asignado": self.tecnico_2.pk,
                "fecha_programada_atencion": "",
                "hora_programada_atencion": "",
                "observaciones_internas": "Reasignado después de rechazo.",
            },
        )

        incidencia.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incidencia.tecnico_asignado, self.tecnico_2)
        self.assertEqual(incidencia.estado_actual, Incidencia.ESTADO_ASIGNADO)

        self.client.force_login(self.tecnico_2)
        detalle = self.client.get(reverse("detalle_incidencia", args=[incidencia.pk]))
        self.assertContains(detalle, "Aceptar atención")
        self.assertContains(detalle, "Rechazar")
