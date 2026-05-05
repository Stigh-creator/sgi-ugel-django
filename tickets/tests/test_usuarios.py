from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse

from auditoria.models import Auditoria
from tickets.forms.forms_usuarios import build_temporary_password
from tickets.models import Area, CustomUser, Incidencia


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

        response = self.client.post(
            reverse("toggle_usuario_status", args=[self.usuario.pk]),
            {"motivo": "Fin temporal de acceso"},
        )

        self.assertRedirects(response, reverse("usuarios"))
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertFalse(Session.objects.filter(session_key=other_client.session.session_key).exists())

    def test_reset_password_admin_funciona_y_cierra_sesiones(self):
        other_client = self.client_class()
        other_client.force_login(self.usuario)

        response = self.client.post(
            reverse("reset_password_admin", args=[self.usuario.pk]),
            {"motivo": "Solicitud del usuario"},
        )

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

    def test_admin_normal_no_puede_editar_superusuario(self):
        superuser = CustomUser.objects.create_superuser(
            username="99990000",
            password="Super1234!",
            first_name="Super",
            last_name="Admin",
            email="super@example.com",
            role="administrador",
            area=self.area,
            telefono="900000000",
        )

        response = self.client.post(
            reverse("editar_usuario", args=[superuser.pk]),
            {
                "first_name": "Super",
                "last_name": "Admin",
                "email": "super@example.com",
                "telefono": "900000000",
                "role": "usuario",
                "area": self.area_2.pk,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertIn("No tienes permisos", payload["message"])
        superuser.refresh_from_db()
        self.assertEqual(superuser.first_name, "Super")
        self.assertEqual(superuser.role, "administrador")
        self.assertEqual(superuser.area, self.area)

    def test_admin_no_puede_cambiar_su_propio_rol(self):
        response = self.client.post(
            reverse("editar_usuario", args=[self.admin.pk]),
            {
                "first_name": self.admin.first_name,
                "last_name": self.admin.last_name,
                "email": "admin@example.com",
                "telefono": self.admin.telefono,
                "role": "usuario",
                "area": self.admin.area.pk,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn(
            "No puedes cambiar tu propio rol por motivos de seguridad. Solicita este cambio a otro administrador o al superusuario",
            payload["errors"]["role"],
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "administrador")

    def test_no_permite_cambiar_rol_del_unico_administrador_activo(self):
        response = self.client.post(
            reverse("editar_usuario", args=[self.admin.pk]),
            {
                "first_name": self.admin.first_name,
                "last_name": self.admin.last_name,
                "email": "admin@example.com",
                "telefono": self.admin.telefono,
                "role": "usuario",
                "area": self.admin.area.pk,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn(
            "No se puede cambiar el rol del único administrador activo. Debe existir al menos un administrador activo.",
            payload["errors"]["role"],
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "administrador")

    def test_cambiar_rol_de_otro_usuario_invalida_sus_sesiones(self):
        other_client = self.client_class()
        other_client.force_login(self.usuario)
        session_key = other_client.session.session_key

        response = self.client.post(
            reverse("editar_usuario", args=[self.usuario.pk]),
            {
                "first_name": self.usuario.first_name,
                "last_name": self.usuario.last_name,
                "email": "pedro@example.com",
                "telefono": self.usuario.telefono,
                "role": "tecnico",
                "area": self.usuario.area.pk,
            },
        )

        self.assertRedirects(response, reverse("usuarios"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.role, "tecnico")
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())

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

    def test_desactivar_usuario_requiere_motivo_y_audita_detalle(self):
        response = self.client.post(
            reverse("toggle_usuario_status", args=[self.usuario.pk]),
            {},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

        response = self.client.post(
            reverse("toggle_usuario_status", args=[self.usuario.pk]),
            {"motivo": "Inactividad prolongada"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        audit = Auditoria.objects.filter(modulo="Usuarios", referencia_id=self.usuario.pk).first()
        self.assertIn("Inactividad prolongada", audit.descripcion)
        self.assertIn("El administrador", audit.descripcion)

    def test_reset_password_requiere_motivo(self):
        response = self.client.post(
            reverse("reset_password_admin", args=[self.usuario.pk]),
            {},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.must_change_password)

    def test_admin_no_puede_resetear_su_propia_contrasena_desde_crud(self):
        response = self.client.post(
            reverse("reset_password_admin", args=[self.admin.pk]),
            {"motivo": "Prueba de autogestión"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No puedes restablecerte tu propia contraseña", response.json()["message"])

    def test_admin_normal_no_puede_resetear_ni_deshabilitar_superusuario(self):
        superuser = CustomUser.objects.create_superuser(
            username="99990000",
            password="Super1234!",
            first_name="Super",
            last_name="Admin",
            email="super@example.com",
            role="administrador",
            area=self.area,
            telefono="900000000",
        )

        reset_response = self.client.post(
            reverse("reset_password_admin", args=[superuser.pk]),
            {"motivo": "Prueba"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        toggle_response = self.client.post(
            reverse("toggle_usuario_status", args=[superuser.pk]),
            {"motivo": "Prueba"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(reset_response.status_code, 403)
        self.assertEqual(toggle_response.status_code, 403)
        superuser.refresh_from_db()
        self.assertTrue(superuser.is_active)

    def test_usuario_con_incidencia_activa_solo_permite_contacto(self):
        Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="hardware",
            descripcion="No enciende equipo",
        )

        blocked_response = self.client.post(
            reverse("editar_usuario", args=[self.usuario.pk]),
            {
                "first_name": "Carlos",
                "last_name": self.usuario.last_name,
                "email": "pedro.contacto@example.com",
                "telefono": "977777777",
                "role": "tecnico",
                "area": self.area_2.pk,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(blocked_response.status_code, 400)
        self.assertIn("incidencias activas o pendientes", blocked_response.json()["errors"]["__all__"][0])

        allowed_response = self.client.post(
            reverse("editar_usuario", args=[self.usuario.pk]),
            {
                "first_name": self.usuario.first_name,
                "last_name": self.usuario.last_name,
                "email": "pedro.contacto@example.com",
                "telefono": "977777777",
                "role": self.usuario.role,
                "area": self.usuario.area.pk,
            },
        )
        self.assertRedirects(allowed_response, reverse("usuarios"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "pedro.contacto@example.com")
        self.assertEqual(self.usuario.telefono, "977777777")
        self.assertEqual(self.usuario.first_name, "Pedro")
        self.assertEqual(self.usuario.role, "usuario")

    def test_superusuario_no_puede_editar_campos_bloqueados_de_tecnico_con_incidencia_activa(self):
        superuser = CustomUser.objects.create_superuser(
            username="99990000",
            password="Super1234!",
            first_name="Super",
            last_name="Admin",
            email="super@example.com",
            role="administrador",
            area=self.area,
            telefono="900000000",
        )
        self.usuario.role = "tecnico"
        self.usuario.save(update_fields=["role"])
        Incidencia.objects.create(
            creador=self.admin,
            tecnico_asignado=self.usuario,
            area=self.area,
            categoria="hardware",
            descripcion="Equipo sin acceso a red",
        )
        self.client.force_login(superuser)

        response = self.client.post(
            reverse("editar_usuario", args=[self.usuario.pk]),
            {
                "first_name": "Carlos",
                "last_name": self.usuario.last_name,
                "email": "tecnico@example.com",
                "telefono": self.usuario.telefono,
                "role": "administrador",
                "area": self.area_2.pk,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("incidencias activas o pendientes", response.json()["errors"]["__all__"][0])
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Pedro")
        self.assertEqual(self.usuario.role, "tecnico")
        self.assertEqual(self.usuario.area, self.area)

    def test_usuario_con_incidencia_activa_puede_ser_deshabilitado_con_motivo(self):
        Incidencia.objects.create(
            creador=self.usuario,
            area=self.area,
            categoria="hardware",
            descripcion="Ticket activo",
        )

        response = self.client.post(
            reverse("toggle_usuario_status", args=[self.usuario.pk]),
            {"motivo": "Suspensión administrativa con ticket activo reasignable"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)

    def test_auditoria_de_edicion_detalla_actor_campos_y_valores(self):
        response = self.client.post(
            reverse("editar_usuario", args=[self.usuario.pk]),
            {
                "first_name": "Carlos",
                "last_name": self.usuario.last_name,
                "email": "carlos@example.com",
                "telefono": self.usuario.telefono,
                "role": self.usuario.role,
                "area": self.usuario.area.pk,
            },
        )

        self.assertRedirects(response, reverse("usuarios"))
        audit = Auditoria.objects.filter(modulo="Usuarios", referencia_id=self.usuario.pk).first()
        self.assertIn("El administrador", audit.descripcion)
        self.assertIn("nombres: 'Pedro' -> 'Carlos'", audit.descripcion)
        self.assertIn("DNI: 33334444", audit.descripcion)
