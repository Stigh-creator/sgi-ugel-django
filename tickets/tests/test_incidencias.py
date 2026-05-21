from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import Auditoria, EventoFallido
from inventario.models import Equipo, EstadoEquipo, HistorialEstadoEquipo, Marca, TipoEquipo
from tickets.forms.forms_incidencias import IncidenciaAdminForm, IncidenciaCierreForm, IncidenciaForm
from tickets.models import Area, Comentario, CustomUser, EstadoSLA, Incidencia, MetricaDiaria, Notificacion, NotificacionUsuario, ReemplazoEquipoIncidencia
from tickets.services import (
    aceptar_incidencia_service,
    assign_incidencia_service,
    cerrar_incidencia_service,
    create_incidencia_service,
    get_estado,
    rechazar_incidencia_service,
    reabrir_incidencia_service,
    resolver_incidencia_service,
    emitir_evento_incidencia,
    IncidenciaService,
)
from tickets.views.views_exports import incidencias_exportables_por_tab


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
        self.estado_observacion, _ = EstadoEquipo.objects.get_or_create(nombre="Observación")
        self.estado_revision, _ = EstadoEquipo.objects.get_or_create(nombre="En revisión")
        self.estado_reparacion, _ = EstadoEquipo.objects.get_or_create(nombre="En reparación")
        self.estado_inoperativo, _ = EstadoEquipo.objects.get_or_create(nombre="Inoperativo")
        self.estado_baja, _ = EstadoEquipo.objects.get_or_create(nombre="Dado de baja")
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

    def _evidencia(self, name="evidencia.gif"):
        return SimpleUploadedFile(
            name,
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

    def test_get_equipos_for_area_filtra_area_principal_para_admin_y_tecnico(self):
        area_planificacion = Area.objects.create(name="Planificación", sede_principal="UPDI")
        area_estadistica = Area.objects.create(name="Estadística", sede_principal="UPDI")
        area_administracion = Area.objects.create(name="Administración", sede_principal="ADMINISTRACIÓN")
        equipo_planificacion = Equipo.objects.create(
            codigo_equipo="UPDI-001",
            nombre_equipo="PC Planificación",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_planificacion,
            estado=self.estado_operativo,
            activo=True,
        )
        equipo_estadistica = Equipo.objects.create(
            codigo_equipo="UPDI-002",
            nombre_equipo="PC Estadística",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_estadistica,
            estado=self.estado_operativo,
            activo=True,
        )
        equipo_administracion = Equipo.objects.create(
            codigo_equipo="ADM-001",
            nombre_equipo="PC Administración",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_administracion,
            estado=self.estado_operativo,
            activo=True,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("get_equipos_for_area"), {"area": area_planificacion.pk, "categoria": "hardware"})

        self.assertContains(response, equipo_planificacion.nombre_equipo)
        self.assertContains(response, equipo_estadistica.nombre_equipo)
        self.assertNotContains(response, equipo_administracion.nombre_equipo)

    def test_get_equipos_for_area_sin_area_no_lista_equipos_en_hardware(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("get_equipos_for_area"), {"categoria": "hardware"})

        self.assertContains(response, "-- Seleccione Equipo --")
        self.assertNotContains(response, self.equipo.nombre_equipo)

    def test_admin_form_permite_equipo_de_misma_area_principal(self):
        area_planificacion = Area.objects.create(name="Planificación", sede_principal="UPDI")
        area_estadistica = Area.objects.create(name="Estadística", sede_principal="UPDI")
        equipo_misma_area_principal = Equipo.objects.create(
            codigo_equipo="UPDI-003",
            nombre_equipo="PC Estadística",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_estadistica,
            estado=self.estado_operativo,
            activo=True,
        )
        image = SimpleUploadedFile(
            "falla.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        form = IncidenciaAdminForm(
            data={
                "categoria": "hardware",
                "prioridad": "media",
                "area": area_planificacion.pk,
                "equipo": equipo_misma_area_principal.pk,
                "descripcion": "El equipo presenta fallas intermitentes al iniciar.",
                "tecnico_asignado": self.tecnico.pk,
            },
            files={"imagen_adjunta": image},
        )

        self.assertTrue(form.is_valid(), form.errors.as_text())

    def test_admin_form_rechaza_equipo_de_area_principal_distinta(self):
        area_planificacion = Area.objects.create(name="Planificación", sede_principal="UPDI")
        area_administracion = Area.objects.create(name="Administración", sede_principal="ADMINISTRACIÓN")
        equipo_otra_area_principal = Equipo.objects.create(
            codigo_equipo="ADM-002",
            nombre_equipo="PC Administración",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_administracion,
            estado=self.estado_operativo,
            activo=True,
        )
        image = SimpleUploadedFile(
            "falla.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        form = IncidenciaAdminForm(
            data={
                "categoria": "hardware",
                "prioridad": "media",
                "area": area_planificacion.pk,
                "equipo": equipo_otra_area_principal.pk,
                "descripcion": "El equipo presenta fallas intermitentes al iniciar.",
                "tecnico_asignado": self.tecnico.pk,
            },
            files={"imagen_adjunta": image},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("equipo", form.errors)
        self.assertIn("no pertenece al área principal elegida", form.errors["equipo"][0])

    def test_crear_incidencia_genera_codigo_y_cambia_equipo_a_observacion(self):
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
        self.assertEqual(self.equipo.estado.nombre, "Observación")
        self.assertTrue(self.equipo.activo)

    def test_admin_crea_incidencia_respetando_prioridad_critica(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("crear_incidencia"),
            {
                "categoria": "software",
                "prioridad": Incidencia.PRIORIDAD_CRITICA,
                "area": self.area.pk,
                "equipo": "",
                "descripcion": "El sistema principal presenta una falla crítica que impide la atención normal.",
                "imagen_adjunta": self._evidencia(),
                "tecnico_asignado": self.tecnico.pk,
                "fecha_programada_atencion": "",
                "hora_programada_atencion": "",
                "observaciones_internas": "",
            },
        )

        incidencia = Incidencia.objects.latest("pk")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incidencia.creador, self.admin)
        self.assertEqual(incidencia.prioridad, Incidencia.PRIORIDAD_CRITICA)

    def test_tecnico_crea_incidencia_respetando_prioridad_critica(self):
        self.client.force_login(self.tecnico)

        response = self.client.post(
            reverse("crear_incidencia"),
            {
                "categoria": "software",
                "prioridad": Incidencia.PRIORIDAD_CRITICA,
                "area": self.area.pk,
                "equipo": "",
                "descripcion": "El servicio interno presenta una falla crítica reportada por soporte técnico.",
                "imagen_adjunta": self._evidencia(),
            },
        )

        incidencia = Incidencia.objects.latest("pk")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incidencia.creador, self.tecnico)
        self.assertEqual(incidencia.prioridad, Incidencia.PRIORIDAD_CRITICA)

    def test_trabajador_crea_incidencia_siempre_con_prioridad_media(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("crear_incidencia"),
            {
                "categoria": "software",
                "prioridad": Incidencia.PRIORIDAD_CRITICA,
                "area": self.area.pk,
                "equipo": "",
                "descripcion": "El usuario registra una falla del sistema para validación de prioridad automática.",
                "imagen_adjunta": self._evidencia(),
            },
        )

        incidencia = Incidencia.objects.latest("pk")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incidencia.creador, self.usuario)
        self.assertEqual(incidencia.prioridad, Incidencia.PRIORIDAD_MEDIA)

    def test_trabajador_reporta_hardware_con_equipo_no_listado(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("crear_incidencia"),
            {
                "categoria": "hardware",
                "equipo": "otro",
                "otro_tipo": "Mouse",
                "otro_marca": "Logitech",
                "otro_modelo": "M90",
                "otro_serie": "",
                "descripcion": "El usuario reporta un periférico no listado con fallas intermitentes.",
                "imagen_adjunta": self._evidencia(),
            },
        )

        incidencia = Incidencia.objects.latest("pk")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incidencia.creador, self.usuario)
        self.assertEqual(incidencia.equipo, None)
        self.assertEqual(incidencia.otro_tipo, "Mouse")
        self.assertEqual(incidencia.otro_marca, "Logitech")
        self.assertEqual(incidencia.otro_modelo, "M90")
        self.assertEqual(incidencia.prioridad, Incidencia.PRIORIDAD_MEDIA)

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

    def test_asignar_tecnico_cambia_equipo_institucional_a_en_reparacion(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Incidencia lista para asignar.",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )
        self.equipo.estado = self.estado_observacion
        self.equipo.save(update_fields=["estado", "actualizado_en"])

        assign_incidencia_service(incidencia, tecnico=self.tecnico)

        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado.nombre, "En reparación")

    def test_admin_puede_asignar_incidencia_con_equipo_actual_no_operativo(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Incidencia con equipo ya fuera de operativo.",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )
        self.equipo.estado = self.estado_observacion
        self.equipo.save(update_fields=["estado", "actualizado_en"])
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("gestionar_incidencia", args=[incidencia.pk]),
            {
                "categoria": incidencia.categoria,
                "prioridad": incidencia.prioridad,
                "area": self.area.pk,
                "equipo": self.equipo.pk,
                "descripcion": incidencia.descripcion,
                "tecnico_asignado": self.tecnico.pk,
                "fecha_programada_atencion": "",
                "hora_programada_atencion": "",
                "observaciones_internas": "Asignación con equipo en observación.",
            },
        )

        incidencia.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incidencia.tecnico_asignado, self.tecnico)
        self.assertEqual(incidencia.estado_actual, Incidencia.ESTADO_ASIGNADO)

    def test_resolver_reparado_mantiene_en_reparacion_y_cierre_lo_deja_operativo(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Equipo reparable.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )
        self.equipo.estado = self.estado_reparacion
        self.equipo.save(update_fields=["estado", "actualizado_en"])

        resolver_incidencia_service(
            incidencia,
            self.tecnico,
            "Se reemplazó la fuente y el equipo volvió a encender correctamente.",
            Incidencia.RESOLUCION_REPARADO,
        )
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado.nombre, "En reparación")

        cerrar_incidencia_service(incidencia, self.usuario)
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado.nombre, "Operativo")

    def test_resolver_reemplazado_deja_antiguo_inoperativo_y_nuevo_operativo_al_cerrar(self):
        area_reemplazo = Area.objects.create(name="Gestión Pedagógica")
        reemplazo = Equipo.objects.create(
            codigo_equipo="PC-REMP",
            nombre_equipo="PC Reemplazo",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_reemplazo,
            estado=self.estado_operativo,
            activo=True,
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Equipo requiere reemplazo temporal.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        resolver_incidencia_service(
            incidencia,
            self.tecnico,
            "Se entrega equipo temporal mientras se evalúa reparación del activo original.",
            Incidencia.RESOLUCION_REEMPLAZADO,
            equipo_reemplazo=reemplazo,
        )
        self.equipo.refresh_from_db()
        reemplazo.refresh_from_db()
        self.assertEqual(self.equipo.estado.nombre, "Inoperativo")
        self.assertEqual(self.equipo.disponibilidad, Equipo.DISPONIBILIDAD_NO_DISPONIBLE)
        self.assertEqual(reemplazo.estado.nombre, "Operativo")
        self.assertEqual(reemplazo.disponibilidad, Equipo.DISPONIBILIDAD_REEMPLAZO_TEMPORAL)
        self.assertEqual(reemplazo.origen_ocupacion, Equipo.ORIGEN_OCUPACION_REEMPLAZO)
        self.assertEqual(reemplazo.area, self.area)
        self.assertTrue(ReemplazoEquipoIncidencia.objects.get(incidencia=incidencia).activo)
        self.assertTrue(
            Auditoria.objects.filter(
                modulo="Inventario",
                referencia_id=reemplazo.pk,
                descripcion__icontains="Área actualizada de Gestión Pedagógica a Sistemas",
            ).exists()
        )

        cerrar_incidencia_service(incidencia, self.usuario)
        self.equipo.refresh_from_db()
        reemplazo.refresh_from_db()
        self.assertEqual(self.equipo.estado.nombre, "Inoperativo")
        self.assertEqual(self.equipo.disponibilidad, Equipo.DISPONIBILIDAD_NO_DISPONIBLE)
        self.assertEqual(reemplazo.estado.nombre, "Operativo")
        self.assertEqual(reemplazo.disponibilidad, Equipo.DISPONIBILIDAD_LIBRE)
        self.assertIsNone(reemplazo.origen_ocupacion)
        self.assertEqual(reemplazo.area, area_reemplazo)
        self.assertFalse(ReemplazoEquipoIncidencia.objects.get(incidencia=incidencia).activo)

    def test_reemplazo_pc_y_laptop_son_compatibles(self):
        tipo_laptop = TipoEquipo.objects.create(nombre="Laptop")
        reemplazo = Equipo.objects.create(
            codigo_equipo="LAP-REMP",
            nombre_equipo="Laptop Reemplazo",
            tipo_equipo=tipo_laptop,
            marca=self.marca,
            modelo="Latitude",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="PC requiere reemplazo, pero se intenta elegir laptop.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        form = IncidenciaCierreForm(incidencia=incidencia)
        self.assertIn(reemplazo.id, list(form.fields["equipo_reemplazo"].queryset.values_list("id", flat=True)))

        resolver_incidencia_service(
            incidencia,
            self.tecnico,
            "Se entrega una laptop como equipo compatible de reemplazo temporal para el usuario.",
            Incidencia.RESOLUCION_REEMPLAZADO,
            equipo_reemplazo=reemplazo,
        )
        incidencia.refresh_from_db()
        reemplazo.refresh_from_db()
        self.assertEqual(incidencia.equipo_reemplazo, reemplazo)
        self.assertEqual(reemplazo.disponibilidad, Equipo.DISPONIBILIDAD_REEMPLAZO_TEMPORAL)
        self.assertEqual(reemplazo.origen_ocupacion, Equipo.ORIGEN_OCUPACION_REEMPLAZO)

    def test_emitir_evento_incidencia_es_idempotente(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad="media",
            descripcion="Validar idempotencia de eventos.",
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
            tecnico_asignado=self.tecnico,
        )
        metadata = {"tecnico_id": self.tecnico.id, "tecnico_nombre": self.tecnico.get_full_name()}

        emitir_evento_incidencia("incidencia.asignada", incidencia, actor=self.admin, metadata=metadata)
        emitir_evento_incidencia("incidencia.asignada", incidencia, actor=self.admin, metadata=metadata)

        self.assertEqual(Auditoria.objects.filter(evento="incidencia.asignada", referencia_id=incidencia.id).count(), 1)
        self.assertEqual(Notificacion.objects.filter(incidencia=incidencia, tipo="asignacion").count(), 1)

    def test_notificacion_asignacion_llega_a_trabajador_y_tecnico(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Validar destinatarios de asignación.",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )

        IncidenciaService.asignar(incidencia.pk, tecnico=self.tecnico, actor=self.admin)

        notificacion = Notificacion.objects.get(incidencia_id=incidencia.pk, tipo="asignacion")
        destinatarios = set(notificacion.usuarios.values_list("usuario_id", flat=True))
        self.assertIn(self.usuario.pk, destinatarios)
        self.assertIn(self.tecnico.pk, destinatarios)
        self.assertNotIn(self.admin.pk, destinatarios)

    def test_notificacion_clasifica_prioridad_critica_por_incidencia_critica(self):
        incidencia = Incidencia.objects.create(
            creador=self.admin,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_CRITICA,
            descripcion="Validar prioridad crítica en notificaciones.",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )

        emitir_evento_incidencia("incidencia.creada", incidencia, actor=self.admin)

        notificacion = Notificacion.objects.get(incidencia=incidencia, tipo="nueva_incidencia")
        self.assertEqual(notificacion.prioridad, Notificacion.PRIORIDAD_CRITICA)

    def test_notificacion_sla_vencido_llega_a_admin_y_tecnico_como_critica(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Validar notificación de SLA vencido.",
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
            tecnico_asignado=self.tecnico,
        )

        emitir_evento_incidencia("incidencia.sla_resolucion_vencido", incidencia)

        notificacion = Notificacion.objects.get(incidencia=incidencia, tipo="sla")
        destinatarios = set(notificacion.usuarios.values_list("usuario_id", flat=True))
        self.assertEqual(notificacion.prioridad, Notificacion.PRIORIDAD_CRITICA)
        self.assertIn(self.admin.pk, destinatarios)
        self.assertIn(self.tecnico.pk, destinatarios)

    def test_notificacion_inventario_llega_a_almacen_como_alta(self):
        almacen = CustomUser.objects.create_user(
            username="55667788",
            password="Almacen123!",
            first_name="Rosa",
            last_name="Almacen",
            role=CustomUser.ROL_ALMACEN,
            area=self.area,
            telefono="900000005",
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="hardware",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Validar notificación de inventario para almacén.",
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
            tecnico_asignado=self.tecnico,
        )

        emitir_evento_incidencia("inventario.estado_cambiado", incidencia, actor=self.tecnico)

        notificacion = Notificacion.objects.get(incidencia=incidencia, tipo="inventario")
        destinatarios = set(notificacion.usuarios.values_list("usuario_id", flat=True))
        self.assertEqual(notificacion.prioridad, Notificacion.PRIORIDAD_ALTA)
        self.assertIn(almacen.pk, destinatarios)
        self.assertNotIn(self.tecnico.pk, destinatarios)

    def test_campana_muestra_contador_y_prioridad(self):
        notificacion = Notificacion.objects.create(
            incidencia=None,
            mensaje="Notificación de prueba visible en campana.",
            tipo="estado",
            prioridad=Notificacion.PRIORIDAD_ALTA,
            link=reverse("index"),
        )
        NotificacionUsuario.objects.create(usuario=self.admin, notificacion=notificacion)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("dashboard_admin"))

        self.assertContains(response, "notification-badge")
        self.assertContains(response, "priority-alta")
        self.assertContains(response, "Notificación de prueba visible")

    def test_leer_notificacion_marca_como_leida(self):
        notificacion = Notificacion.objects.create(
            mensaje="Notificación para marcar como leída.",
            tipo="estado",
            prioridad=Notificacion.PRIORIDAD_MEDIA,
            link=reverse("dashboard_admin"),
        )
        relacion = NotificacionUsuario.objects.create(usuario=self.admin, notificacion=notificacion)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("leer_notificacion", args=[relacion.pk]))

        relacion.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(relacion.leido)

    def test_equipo_ocupado_requiere_origen_ocupacion(self):
        self.equipo.disponibilidad = Equipo.DISPONIBILIDAD_EN_USO
        self.equipo.origen_ocupacion = None

        with self.assertRaisesMessage(ValidationError, "origen de ocupación"):
            self.equipo.save(update_fields=["disponibilidad", "origen_ocupacion"])

    def test_dos_resoluciones_no_pueden_usar_mismo_reemplazo(self):
        reemplazo = Equipo.objects.create(
            codigo_equipo="PC-CONC",
            nombre_equipo="PC Concurrencia",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        incidencia_1 = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Primera incidencia concurrente.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )
        equipo_2 = Equipo.objects.create(
            codigo_equipo="PC-002",
            nombre_equipo="PC Segunda",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        incidencia_2 = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=equipo_2,
            categoria="hardware",
            prioridad="media",
            descripcion="Segunda incidencia concurrente.",
            tecnico_asignado=self.tecnico_2,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        resolver_incidencia_service(
            incidencia_1,
            self.tecnico,
            "Se asigna el reemplazo temporal al primer ticket concurrente.",
            Incidencia.RESOLUCION_REEMPLAZADO,
            equipo_reemplazo=reemplazo,
        )

        with self.assertRaisesMessage(ValidationError, "no está libre"):
            resolver_incidencia_service(
                incidencia_2,
                self.tecnico_2,
                "Se intenta usar el mismo reemplazo en otro ticket.",
                Incidencia.RESOLUCION_REEMPLAZADO,
                equipo_reemplazo=reemplazo,
            )

    def test_reemplazo_con_tipo_computadora_de_escritorio_muestra_laptop_libre(self):
        tipo_pc_largo = TipoEquipo.objects.create(nombre="Computadora de Escritorio (PC)")
        tipo_laptop = TipoEquipo.objects.create(nombre="Laptop")
        equipo_pc = Equipo.objects.create(
            codigo_equipo="PC-LARGO",
            nombre_equipo="PC con tipo largo",
            tipo_equipo=tipo_pc_largo,
            marca=self.marca,
            modelo="Optiplex",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        laptop_libre = Equipo.objects.create(
            codigo_equipo="LAP-LIBRE",
            nombre_equipo="Laptop libre",
            tipo_equipo=tipo_laptop,
            marca=self.marca,
            modelo="Latitude",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=equipo_pc,
            categoria="hardware",
            prioridad="media",
            descripcion="PC de escritorio requiere reemplazo compatible.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        form = IncidenciaCierreForm(incidencia=incidencia)

        self.assertIn(laptop_libre.id, list(form.fields["equipo_reemplazo"].queryset.values_list("id", flat=True)))

    def test_reemplazo_oculta_equipo_operativo_ocupado_en_otro_ticket(self):
        tipo_laptop = TipoEquipo.objects.create(nombre="Laptop")
        laptop_ocupada = Equipo.objects.create(
            codigo_equipo="LAP-OCUPADA",
            nombre_equipo="Laptop ocupada",
            tipo_equipo=tipo_laptop,
            marca=self.marca,
            modelo="Latitude",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=laptop_ocupada,
            categoria="hardware",
            prioridad="media",
            descripcion="La laptop ya está asociada a otra incidencia.",
            estado=get_estado(Incidencia.ESTADO_RESUELTO),
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="PC requiere reemplazo, pero la laptop está ocupada.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        form = IncidenciaCierreForm(incidencia=incidencia)

        self.assertNotIn(laptop_ocupada.id, list(form.fields["equipo_reemplazo"].queryset.values_list("id", flat=True)))

    def test_reemplazo_oculta_equipo_operativo_en_uso(self):
        tipo_laptop = TipoEquipo.objects.create(nombre="Laptop")
        laptop_en_uso = Equipo.objects.create(
            codigo_equipo="LAP-USO",
            nombre_equipo="Laptop en uso",
            tipo_equipo=tipo_laptop,
            marca=self.marca,
            modelo="Latitude",
            area=self.area,
            estado=self.estado_operativo,
            disponibilidad=Equipo.DISPONIBILIDAD_EN_USO,
            origen_ocupacion=Equipo.ORIGEN_OCUPACION_ASIGNACION_DIRECTA,
            activo=True,
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="PC requiere reemplazo, pero la laptop está marcada en uso.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        form = IncidenciaCierreForm(incidencia=incidencia)

        self.assertNotIn(laptop_en_uso.id, list(form.fields["equipo_reemplazo"].queryset.values_list("id", flat=True)))

    def test_reemplazo_de_tipo_no_computo_debe_coincidir_exactamente(self):
        tipo_impresora = TipoEquipo.objects.create(nombre="Impresora")
        reemplazo = Equipo.objects.create(
            codigo_equipo="IMP-REMP",
            nombre_equipo="Impresora Reemplazo",
            tipo_equipo=tipo_impresora,
            marca=self.marca,
            modelo="Laser",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="PC requiere reemplazo, pero se intenta elegir impresora.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        with self.assertRaisesMessage(ValidationError, "compatible"):
            resolver_incidencia_service(
                incidencia,
                self.tecnico,
                "Se intenta entregar un reemplazo que no pertenece a la familia de cómputo.",
                Incidencia.RESOLUCION_REEMPLAZADO,
                equipo_reemplazo=reemplazo,
            )

    def test_reemplazo_con_mismo_equipo_falla(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Intento de reemplazo inválido.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        with self.assertRaisesMessage(ValidationError, "no puede ser el mismo"):
            resolver_incidencia_service(
                incidencia,
                self.tecnico,
                "Se intenta seleccionar el mismo equipo como reemplazo temporal.",
                Incidencia.RESOLUCION_REEMPLAZADO,
                equipo_reemplazo=self.equipo,
            )

    def test_reemplazo_con_equipo_no_operativo_falla(self):
        reemplazo = Equipo.objects.create(
            codigo_equipo="PC-NOOP",
            nombre_equipo="PC No operativo",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=self.area,
            estado=self.estado_reparacion,
            activo=True,
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Reemplazo no disponible.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        with self.assertRaisesMessage(ValidationError, "no está disponible"):
            resolver_incidencia_service(
                incidencia,
                self.tecnico,
                "Se intenta usar un equipo que no está operativo.",
                Incidencia.RESOLUCION_REEMPLAZADO,
                equipo_reemplazo=reemplazo,
            )

    def test_reemplazo_con_equipo_en_otra_incidencia_activa_falla(self):
        reemplazo = Equipo.objects.create(
            codigo_equipo="PC-ACT",
            nombre_equipo="PC En incidencia",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=reemplazo,
            categoria="hardware",
            prioridad="media",
            descripcion="Incidencia activa que ocupa el reemplazo.",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Reemplazo ocupado.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        with self.assertRaisesMessage(ValidationError, "otra incidencia activa"):
            resolver_incidencia_service(
                incidencia,
                self.tecnico,
                "Se intenta usar un equipo involucrado en otro ticket activo.",
                Incidencia.RESOLUCION_REEMPLAZADO,
                equipo_reemplazo=reemplazo,
            )

    def test_reapertura_de_ticket_reemplazado_no_revierte_inventario(self):
        reemplazo = Equipo.objects.create(
            codigo_equipo="PC-REP2",
            nombre_equipo="PC Reemplazo 2",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=self.area,
            estado=self.estado_operativo,
            activo=True,
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Ticket reemplazado para reapertura.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )
        resolver_incidencia_service(
            incidencia,
            self.tecnico,
            "Se entrega reemplazo temporal y queda pendiente evaluación del original.",
            Incidencia.RESOLUCION_REEMPLAZADO,
            equipo_reemplazo=reemplazo,
        )

        reabrir_incidencia_service(incidencia)

        self.equipo.refresh_from_db()
        reemplazo.refresh_from_db()
        self.assertEqual(self.equipo.estado.nombre, "Inoperativo")
        self.assertEqual(self.equipo.disponibilidad, Equipo.DISPONIBILIDAD_NO_DISPONIBLE)
        self.assertEqual(reemplazo.estado.nombre, "Operativo")

    def test_resolver_baja_deja_equipo_dado_de_baja_y_cierre_no_lo_reactiva(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad="media",
            descripcion="Equipo sin reparación posible.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )

        resolver_incidencia_service(
            incidencia,
            self.tecnico,
            "Daño de placa principal sin posibilidad de reparación costo efectiva.",
            Incidencia.RESOLUCION_BAJA,
        )
        self.equipo.refresh_from_db()
        self.assertEqual(self.equipo.estado.nombre, "Dado de baja")
        self.assertFalse(self.equipo.activo)
        self.assertEqual(self.equipo.disponibilidad, Equipo.DISPONIBILIDAD_NO_DISPONIBLE)

    def test_equipo_dado_de_baja_no_aparece_en_formulario_incidencia(self):
        self.equipo.estado = self.estado_baja
        self.equipo.activo = False
        self.equipo.save(update_fields=["estado", "activo", "actualizado_en"])

        form = IncidenciaForm(user=self.usuario)

        self.assertNotIn(self.equipo.id, list(form.fields["equipo"].queryset.values_list("id", flat=True)))

    def test_incidencia_con_equipo_otro_no_modifica_inventario_en_resolucion(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="hardware",
            prioridad="media",
            descripcion="Equipo externo no listado.",
            otro_tipo="Laptop externa",
            otro_marca="Genérica",
            otro_modelo="X1",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )
        historial_antes = HistorialEstadoEquipo.objects.count()

        resolver_incidencia_service(
            incidencia,
            self.tecnico,
            "Se deriva el caso a proveedor externo sin modificar inventario institucional.",
            Incidencia.RESOLUCION_DERIVADO,
        )

        self.assertEqual(HistorialEstadoEquipo.objects.count(), historial_antes)

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

    def test_prioridad_se_desbloquea_en_ticket_rechazado_sin_tecnico(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket rechazado que vuelve a evaluación administrativa.",
            tecnico_asignado=None,
            estado=get_estado(Incidencia.ESTADO_RECHAZADO),
        )

        form = IncidenciaAdminForm(instance=incidencia)

        self.assertTrue(incidencia.prioridad_editable)
        self.assertFalse(form.fields["prioridad"].disabled)

    def test_admin_reasigna_ticket_rechazado_y_actualiza_prioridad(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket rechazado listo para reasignación con ajuste de prioridad.",
            imagen_adjunta="incidencias/evidencia.jpg",
            tecnico_asignado=None,
            estado=get_estado(Incidencia.ESTADO_RECHAZADO),
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("gestionar_incidencia", args=[incidencia.pk]),
            {
                "categoria": incidencia.categoria,
                "prioridad": Incidencia.PRIORIDAD_CRITICA,
                "area": self.area.pk,
                "equipo": "",
                "descripcion": incidencia.descripcion,
                "tecnico_asignado": self.tecnico_2.pk,
                "fecha_programada_atencion": "",
                "hora_programada_atencion": "",
                "observaciones_internas": "Se reajusta prioridad antes de reasignar.",
            },
        )

        incidencia.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incidencia.estado_actual, Incidencia.ESTADO_ASIGNADO)
        self.assertEqual(incidencia.tecnico_asignado, self.tecnico_2)
        self.assertEqual(incidencia.prioridad, Incidencia.PRIORIDAD_CRITICA)

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

    def test_detalle_reabierto_muestra_formulario_de_resolucion_al_tecnico_asignado(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="hardware",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket reabierto por inconformidad del usuario.",
            solucion_aplicada="Se aplicó una reparación previa que no solucionó la falla.",
            tipo_resolucion=Incidencia.RESOLUCION_REPARADO,
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_REABIERTO),
        )
        self.client.force_login(self.tecnico)

        response = self.client.get(reverse("detalle_incidencia", args=[incidencia.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Actualizar resolución")
        self.assertContains(response, "Tipo de resolución")
        self.assertContains(response, "Marcar como resuelto")

    def test_admin_no_puede_configurar_ticket_en_proceso(self):
        incidencia = Incidencia.objects.create(
            creador=self.admin,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_ALTA,
            descripcion="Ticket en proceso que ya fue aceptado por el especialista.",
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
        self.assertEqual(incidencia.tecnico_asignado, self.tecnico)
        self.assertEqual(incidencia.estado_actual, Incidencia.ESTADO_EN_PROCESO)
        self.assertEqual(incidencia.prioridad, Incidencia.PRIORIDAD_ALTA)
        self.assertFalse(Auditoria.objects.filter(referencia_id=incidencia.pk, accion="reasignó técnico").exists())

    def test_detalle_admin_muestra_configuracion_bloqueada_en_ticket_en_proceso(self):
        incidencia = Incidencia.objects.create(
            creador=self.admin,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_ALTA,
            descripcion="Ticket en proceso con gestión administrativa bloqueada.",
            imagen_adjunta="incidencias/evidencia.jpg",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("detalle_incidencia", args=[incidencia.pk]))

        self.assertContains(response, "Configuración bloqueada")
        self.assertContains(response, "ya fue aceptada por el especialista")
        self.assertNotContains(response, "Configurar ticket")

    def test_form_usuario_filtra_equipos_por_sede_principal_sin_duplicados(self):
        area_origen = Area.objects.create(name="Mesa de Partes", sede_principal="DIRECCIÓN")
        area_misma_sede = Area.objects.create(name="Trámite Documentario", sede_principal="DIRECCIÓN")
        area_otra_sede = Area.objects.create(name="Secretaría", sede_principal="AGP")
        usuario = CustomUser.objects.create_user(
            username="55667788",
            password="Usuario123!",
            first_name="Marta",
            last_name="Sede",
            role=CustomUser.ROL_TRABAJADOR,
            area=area_origen,
            telefono="900000005",
        )
        equipo_origen = Equipo.objects.create(
            codigo_equipo="DIR-001",
            nombre_equipo="PC Dirección",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_origen,
            estado=self.estado_operativo,
            activo=True,
        )
        equipo_misma_sede = Equipo.objects.create(
            codigo_equipo="DIR-002",
            nombre_equipo="PC Trámite",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_misma_sede,
            estado=self.estado_operativo,
            activo=True,
        )
        equipo_otra_sede = Equipo.objects.create(
            codigo_equipo="AGP-001",
            nombre_equipo="PC AGP",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_otra_sede,
            estado=self.estado_operativo,
            activo=True,
        )

        form = IncidenciaForm(user=usuario)
        equipo_ids = list(form.fields["equipo"].queryset.values_list("id", flat=True))

        self.assertIn(equipo_origen.id, equipo_ids)
        self.assertIn(equipo_misma_sede.id, equipo_ids)
        self.assertNotIn(equipo_otra_sede.id, equipo_ids)
        self.assertEqual(len(equipo_ids), len(set(equipo_ids)))

    def test_form_usuario_sin_sede_principal_no_muestra_equipos(self):
        area_sin_sede = Area.objects.create(name="Área sin sede")
        usuario = CustomUser.objects.create_user(
            username="66778899",
            password="Usuario123!",
            first_name="Config",
            last_name="Invalida",
            role=CustomUser.ROL_TRABAJADOR,
            area=area_sin_sede,
            telefono="900000006",
        )

        form = IncidenciaForm(user=usuario)

        self.assertFalse(form.fields["equipo"].queryset.exists())

    def test_form_usuario_rechaza_equipo_de_otra_sede_en_post_manual(self):
        area_origen = Area.objects.create(name="Soporte", sede_principal="DIRECCIÓN")
        area_otra_sede = Area.objects.create(name="Especialistas", sede_principal="AGP")
        usuario = CustomUser.objects.create_user(
            username="77889900",
            password="Usuario123!",
            first_name="Post",
            last_name="Manual",
            role=CustomUser.ROL_TRABAJADOR,
            area=area_origen,
            telefono="900000007",
        )
        equipo_otra_sede = Equipo.objects.create(
            codigo_equipo="AGP-002",
            nombre_equipo="PC Ajena",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=area_otra_sede,
            estado=self.estado_operativo,
            activo=True,
        )
        evidencia = SimpleUploadedFile(
            "evidencia.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        form = IncidenciaForm(
            data={
                "categoria": "hardware",
                "area": area_origen.pk,
                "equipo": equipo_otra_sede.pk,
                "descripcion": "Intento de registrar equipo de otra sede.",
            },
            files={"imagen_adjunta": evidencia},
            user=usuario,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("equipo", form.errors)

    def test_form_usuario_rechaza_equipo_sin_area_en_post_manual(self):
        area_origen = Area.objects.create(name="Soporte con sede", sede_principal="DIRECCIÓN")
        usuario = CustomUser.objects.create_user(
            username="77889901",
            password="Usuario123!",
            first_name="Equipo",
            last_name="SinArea",
            role=CustomUser.ROL_TRABAJADOR,
            area=area_origen,
            telefono="900000008",
        )
        equipo_sin_area = Equipo.objects.create(
            codigo_equipo="SIN-AREA",
            nombre_equipo="PC Sin área",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=None,
            estado=self.estado_operativo,
            activo=True,
        )
        evidencia = SimpleUploadedFile(
            "evidencia.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        form = IncidenciaForm(
            data={
                "categoria": "hardware",
                "area": area_origen.pk,
                "equipo": equipo_sin_area.pk,
                "descripcion": "Intento de registrar equipo sin área configurada.",
            },
            files={"imagen_adjunta": evidencia},
            user=usuario,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("equipo", form.errors)
        self.assertIn("sede principal", form.errors["equipo"][0])

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

    def test_evento_idempotente_blindado_por_bd(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket para validar idempotencia de eventos.",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )

        emitir_evento_incidencia("incidencia.creada", incidencia, actor=self.usuario, metadata={"retry": "same"})
        emitir_evento_incidencia("incidencia.creada", incidencia, actor=self.usuario, metadata={"retry": "same"})

        auditorias = Auditoria.objects.filter(evento="incidencia.creada", referencia_id=incidencia.pk)
        self.assertEqual(auditorias.count(), 1)
        auditoria = auditorias.get()
        self.assertEqual(auditoria.version_evento, 1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Auditoria.objects.create(
                    usuario=self.usuario,
                    modulo="Incidencias",
                    accion="duplicado forzado",
                    descripcion="Duplicado concurrente simulado.",
                    referencia_id=incidencia.pk,
                    evento=auditoria.evento,
                    hash_evento=auditoria.hash_evento,
                )

    def test_evento_fallido_queda_en_dead_letter(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket para validar evento fallido.",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )

        with patch("tickets.services.registrar_auditoria", side_effect=RuntimeError("Fallo simulado")):
            with self.assertRaisesMessage(RuntimeError, "Fallo simulado"):
                emitir_evento_incidencia("incidencia.creada", incidencia, actor=self.usuario)

        fallido = EventoFallido.objects.get(evento="incidencia.creada")
        self.assertEqual(fallido.version_evento, 1)
        self.assertEqual(fallido.payload["incidencia_id"], incidencia.pk)
        self.assertEqual(fallido.payload["evento"], "incidencia.creada")
        self.assertEqual(fallido.payload["version"], 1)
        self.assertEqual(fallido.payload["actor_id"], self.usuario.pk)
        self.assertIn("timestamp", fallido.payload)
        self.assertEqual(fallido.intentos, 1)
        self.assertIn("Fallo simulado", fallido.error)

    def test_reprocesar_eventos_fallidos_marca_procesado(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket para reprocesar evento fallido.",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )
        EventoFallido.objects.create(
            evento="incidencia.creada",
            version_evento=1,
            payload={
                "incidencia_id": incidencia.pk,
                "evento": "incidencia.creada",
                "version": 1,
                "actor_id": self.usuario.pk,
                "timestamp": timezone.now().isoformat(),
                "metadata": {"origen": "test"},
            },
            error="Fallo previo.",
            ultimo_error="Fallo previo.",
            intentos=1,
        )

        call_command("reprocesar_eventos_fallidos")

        fallido = EventoFallido.objects.get(evento="incidencia.creada")
        self.assertTrue(fallido.procesado)
        self.assertEqual(fallido.ultimo_error, "")
        self.assertTrue(Auditoria.objects.filter(evento="incidencia.creada", referencia_id=incidencia.pk).exists())

    def test_sla_por_vencer_se_marca_antes_del_vencimiento(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket cerca de vencer SLA.",
            estado=get_estado(Incidencia.ESTADO_PENDIENTE),
        )
        base = timezone.now() - timedelta(minutes=81)
        Incidencia.objects.filter(pk=incidencia.pk).update(
            fecha_creacion=base,
            fecha_limite_respuesta=base + timedelta(minutes=100),
            fecha_limite_resolucion=base + timedelta(minutes=200),
            estado_sla=EstadoSLA.EN_TIEMPO,
        )

        call_command("procesar_sla_incidencias")

        incidencia.refresh_from_db()
        self.assertEqual(incidencia.estado_sla, EstadoSLA.POR_VENCER)
        self.assertTrue(Auditoria.objects.filter(evento="incidencia.sla_por_vencer", referencia_id=incidencia.pk).exists())

    def test_dashboard_admin_cuenta_sla_vencido_por_fecha_aunque_estado_sla_no_se_haya_procesado(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket con SLA vencido pendiente de procesamiento automático.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
            estado_sla=EstadoSLA.EN_TIEMPO,
        )
        base = timezone.now() - timedelta(days=5)
        Incidencia.objects.filter(pk=incidencia.pk).update(
            fecha_creacion=base,
            fecha_limite_respuesta=base + timedelta(hours=4),
            fecha_limite_resolucion=base + timedelta(days=1),
            estado_sla=EstadoSLA.EN_TIEMPO,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("dashboard_admin"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["sla_vencidas"], 1)

    def test_dashboard_tecnico_cuenta_sla_vencido_por_fecha_aunque_estado_sla_no_se_haya_procesado(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket asignado con SLA vencido visible para técnico.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
            estado_sla=EstadoSLA.EN_TIEMPO,
        )
        base = timezone.now() - timedelta(days=5)
        Incidencia.objects.filter(pk=incidencia.pk).update(
            fecha_creacion=base,
            fecha_limite_respuesta=base + timedelta(hours=4),
            fecha_limite_resolucion=base + timedelta(days=1),
            estado_sla=EstadoSLA.EN_TIEMPO,
        )
        self.client.force_login(self.tecnico)

        response = self.client.get(reverse("dashboard_tecnico"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["assigned_sla_alerta"], 1)

    def test_listado_filtra_incidencias_sla_vencidas_por_fecha(self):
        vencida = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket vencido para filtro SLA.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
            estado_sla=EstadoSLA.EN_TIEMPO,
        )
        vigente = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket vigente que no debe aparecer en filtro SLA.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_EN_PROCESO),
            estado_sla=EstadoSLA.EN_TIEMPO,
        )
        now = timezone.now()
        Incidencia.objects.filter(pk=vencida.pk).update(
            fecha_creacion=now - timedelta(days=5),
            fecha_limite_respuesta=now - timedelta(days=4),
            fecha_limite_resolucion=now - timedelta(days=3),
        )
        Incidencia.objects.filter(pk=vigente.pk).update(
            fecha_creacion=now,
            fecha_limite_respuesta=now + timedelta(hours=4),
            fecha_limite_resolucion=now + timedelta(days=1),
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("incidencias_list"), {"sla": "vencidas"})

        self.assertEqual(response.status_code, 200)
        incidencias = list(response.context["incidencias"].object_list)
        self.assertIn(vencida, incidencias)
        self.assertNotIn(vigente, incidencias)
        self.assertEqual(response.context["sla_selected"], "vencidas")

    def test_listado_busca_incidencias_por_texto(self):
        encontrada = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Falla exclusiva del sistema SIGA para búsqueda.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )
        no_encontrada = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="hardware",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Incidencia de impresora sin relación.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("incidencias_list"), {"q": "SIGA"})

        self.assertEqual(response.status_code, 200)
        incidencias = list(response.context["incidencias"].object_list)
        self.assertIn(encontrada, incidencias)
        self.assertNotIn(no_encontrada, incidencias)
        self.assertEqual(response.context["query"], "SIGA")

    def test_export_reporte_admin_respeta_tab_reportadas(self):
        creada_por_admin = Incidencia.objects.create(
            creador=self.admin,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Incidencia creada por administración para reporte propio.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )
        creada_por_otro = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="hardware",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Incidencia de otro usuario que no debe entrar al reporte propio.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )

        queryset, active_tab = incidencias_exportables_por_tab(self.admin, "reportadas")

        self.assertEqual(active_tab, "reportadas")
        self.assertIn(creada_por_admin, queryset)
        self.assertNotIn(creada_por_otro, queryset)

    def test_export_reporte_tecnico_respeta_tabs_asignadas_y_reportadas(self):
        creada_por_tecnico = Incidencia.objects.create(
            creador=self.tecnico,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Incidencia creada por el técnico para su reporte propio.",
            tecnico_asignado=self.tecnico_2,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )
        asignada_al_tecnico = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="hardware",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Incidencia asignada al técnico por otro usuario.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )

        reportadas, reportadas_tab = incidencias_exportables_por_tab(self.tecnico, "reportadas")
        asignadas, asignadas_tab = incidencias_exportables_por_tab(self.tecnico, "asignadas")

        self.assertEqual(reportadas_tab, "reportadas")
        self.assertIn(creada_por_tecnico, reportadas)
        self.assertNotIn(asignada_al_tecnico, reportadas)
        self.assertEqual(asignadas_tab, "asignadas")
        self.assertIn(asignada_al_tecnico, asignadas)
        self.assertNotIn(creada_por_tecnico, asignadas)

    def test_tecnico_puede_ver_detalle_de_incidencia_creada_por_el(self):
        incidencia = Incidencia.objects.create(
            creador=self.tecnico,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Incidencia creada por el técnico y asignada a otro especialista.",
            tecnico_asignado=self.tecnico_2,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )
        self.client.force_login(self.tecnico)

        response = self.client.get(reverse("detalle_incidencia", args=[incidencia.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["incidencia"], incidencia)

    def test_usuario_sin_permiso_no_puede_comentar_incidencia_ajena(self):
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="software",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Incidencia que no pertenece al técnico no asignado.",
            tecnico_asignado=self.tecnico,
            estado=get_estado(Incidencia.ESTADO_ASIGNADO),
        )
        self.client.force_login(self.tecnico_2)

        response = self.client.post(
            reverse("agregar_comentario", args=[incidencia.pk]),
            {"texto": "Intento de comentario sin permiso."},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Comentario.objects.filter(incidencia=incidencia).exists())

    def test_snapshot_metricas_guarda_historico_diario(self):
        call_command("snapshot_metricas")

        snapshot = MetricaDiaria.objects.get(fecha=timezone.localdate())
        self.assertGreaterEqual(snapshot.tickets_abiertos, 0)
        self.assertIn("reemplazos_activos", snapshot.metadata)

    def test_integridad_global_fix_cierra_reemplazo_huerfano(self):
        reemplazo = Equipo.objects.create(
            codigo_equipo="PC-HUERFANO",
            nombre_equipo="PC Reemplazo Huérfano",
            tipo_equipo=self.tipo,
            marca=self.marca,
            modelo="Optiplex",
            area=self.area,
            estado=self.estado_operativo,
            disponibilidad=Equipo.DISPONIBILIDAD_REEMPLAZO_TEMPORAL,
            origen_ocupacion=Equipo.ORIGEN_OCUPACION_REEMPLAZO,
            activo=True,
        )
        incidencia = Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            equipo=self.equipo,
            categoria="hardware",
            prioridad=Incidencia.PRIORIDAD_MEDIA,
            descripcion="Ticket cerrado con reemplazo huérfano.",
            estado=get_estado(Incidencia.ESTADO_CERRADO),
        )
        registro = ReemplazoEquipoIncidencia.objects.create(
            incidencia=incidencia,
            equipo_original=self.equipo,
            equipo_reemplazo=reemplazo,
            area_origen=self.area,
            area_destino=self.area,
            usuario=self.tecnico,
            motivo="Reemplazo huérfano de prueba.",
            activo=True,
        )

        call_command("sistema_integridad_global", fix=True)

        registro.refresh_from_db()
        reemplazo.refresh_from_db()
        self.assertFalse(registro.activo)
        self.assertIsNotNone(registro.fecha_fin)
        self.assertEqual(reemplazo.disponibilidad, Equipo.DISPONIBILIDAD_LIBRE)
        self.assertIsNone(reemplazo.origen_ocupacion)
