from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from inventario.models import Equipo, EstadoEquipo, Marca, Repuesto, TipoEquipo
from tickets.models import Area, Comentario, CustomUser, Estado, Incidencia, MetricaDiaria


class Command(BaseCommand):
    help = "Carga datos demostrativos para presentacion: inventario, repuestos, usuarios, incidencias y metricas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-demo",
            action="store_true",
            help="Elimina solo datos con prefijo DEMO antes de cargarlos nuevamente.",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            if options["reset_demo"]:
                self._reset_demo()

            areas = self._areas()
            usuarios = self._usuarios(areas)
            catalogos = self._catalogos()
            equipos = self._equipos(areas, catalogos)
            repuestos = self._repuestos()
            incidencias = self._incidencias(areas, usuarios, equipos)
            metricas = self._metricas()

        self.stdout.write(self.style.SUCCESS("Datos demostrativos cargados correctamente."))
        self.stdout.write(f"Usuarios demo: {usuarios}")
        self.stdout.write(f"Equipos demo: {equipos}")
        self.stdout.write(f"Repuestos: {repuestos}")
        self.stdout.write(f"Incidencias demo: {incidencias}")
        self.stdout.write(f"Metricas demo: {metricas}")

    def _reset_demo(self):
        incidencias = Incidencia.objects.filter(codigo__startswith="DEMO-")
        Comentario.objects.filter(incidencia__in=incidencias).delete()
        incidencias.delete()
        Equipo.objects.filter(codigo_equipo__startswith="DEMO-").delete()
        CustomUser.objects.filter(username__in=["70000001", "70000002", "70000003", "70000004", "70000005"]).delete()
        MetricaDiaria.objects.filter(metadata__origen="demo").delete()

    def _areas(self):
        base = [
            ("DIRECCIÓN", "Trámite Documentario"),
            ("ADMINISTRACIÓN", "Informática"),
            ("ADMINISTRACIÓN", "Almacén"),
            ("ADMINISTRACIÓN", "Contabilidad"),
            ("ADMINISTRACIÓN", "Tesorería"),
            ("AGP", "Especialistas Primaria"),
            ("UPDI", "SIAGIE"),
            ("UPDI", "Estadística"),
        ]
        areas = {}
        for sede, name in base:
            area, _ = Area.objects.get_or_create(sede_principal=sede, name=name)
            areas[name] = area
        return areas

    def _usuarios(self, areas):
        data = [
            ("70000001", "Admin", "Demo", CustomUser.ROL_ADMIN, areas["Informática"], "970000001"),
            ("70000002", "Rosa", "Mendoza", CustomUser.ROL_TECNICO, areas["Informática"], "970000002"),
            ("70000003", "Carlos", "Vega", CustomUser.ROL_TECNICO, areas["Informática"], "970000003"),
            ("70000004", "Elena", "Ramos", CustomUser.ROL_ALMACEN, areas["Almacén"], "970000004"),
            ("70000005", "Mariela", "Flores", CustomUser.ROL_TRABAJADOR, areas["Trámite Documentario"], "970000005"),
        ]
        creados = actualizados = 0
        for username, first, last, role, area, phone in data:
            user, created = CustomUser.objects.update_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{first.lower()}.{last.lower()}.demo@ugel.local",
                    "telefono": phone,
                    "role": role,
                    "area": area,
                    "is_staff": role == CustomUser.ROL_ADMIN,
                    "is_superuser": False,
                    "is_active": True,
                    "must_change_password": False,
                },
            )
            user.set_password("Demo12345!")
            user.save(update_fields=["password", "last_password_change"])
            creados += int(created)
            actualizados += int(not created)
        return f"{creados} creados, {actualizados} actualizados"

    def _catalogos(self):
        marcas = {}
        for nombre in ["HP", "Lenovo", "Dell", "Epson", "Brother", "Cisco", "LG", "Kingston"]:
            marcas[nombre], _ = Marca.objects.get_or_create(nombre=nombre)

        tipos = {}
        for nombre in [
            "Computadora de Escritorio (PC)",
            "Laptop",
            "Impresora / Multifuncional",
            "Monitor",
            "Switch / Router / Access Point",
            "Servidor",
        ]:
            tipos[nombre], _ = TipoEquipo.objects.get_or_create(nombre=nombre)

        estados = {}
        for nombre in ["Operativo", "Observación", "En revisión", "En reparación", "Inoperativo", "Dado de baja"]:
            estados[nombre], _ = EstadoEquipo.objects.get_or_create(nombre=nombre)

        for nombre in Incidencia.FLUJO_ESTADOS:
            Estado.objects.get_or_create(name=nombre)

        return {"marcas": marcas, "tipos": tipos, "estados": estados}

    def _equipos(self, areas, catalogos):
        m = catalogos["marcas"]
        t = catalogos["tipos"]
        e = catalogos["estados"]
        rows = [
            ("DEMO-INF-PC-001", "PC soporte informatico 01", "Computadora de Escritorio (PC)", "HP", "ProDesk 400 G5", "Informática", "Operativo", Equipo.DISPONIBILIDAD_EN_USO),
            ("DEMO-TRA-IMP-001", "Multifuncional tramite documentario", "Impresora / Multifuncional", "Epson", "EcoTank L5290", "Trámite Documentario", "Operativo", Equipo.DISPONIBILIDAD_EN_USO),
            ("DEMO-ADM-PC-001", "PC contabilidad", "Computadora de Escritorio (PC)", "Lenovo", "ThinkCentre M720s", "Contabilidad", "Operativo", Equipo.DISPONIBILIDAD_EN_USO),
            ("DEMO-UPDI-LAP-001", "Laptop SIAGIE", "Laptop", "HP", "240 G8", "SIAGIE", "Operativo", Equipo.DISPONIBILIDAD_EN_USO),
            ("DEMO-UPDI-SW-001", "Switch estadistica", "Switch / Router / Access Point", "Cisco", "CBS250-24T", "Estadística", "Operativo", Equipo.DISPONIBILIDAD_EN_USO),
            ("DEMO-ALM-LAP-001", "Laptop libre para reemplazo", "Laptop", "Dell", "Latitude 3410", "Almacén", "Operativo", Equipo.DISPONIBILIDAD_LIBRE),
            ("DEMO-ALM-MON-001", "Monitor libre para reposicion", "Monitor", "LG", "20MK400H", "Almacén", "Operativo", Equipo.DISPONIBILIDAD_LIBRE),
            ("DEMO-REP-LAP-001", "Laptop en reparacion por pantalla", "Laptop", "Dell", "Vostro 3400", "Trámite Documentario", "En reparación", Equipo.DISPONIBILIDAD_NO_DISPONIBLE),
            ("DEMO-INOP-PC-001", "PC inoperativa para baja tecnica", "Computadora de Escritorio (PC)", "HP", "ProDesk 600 G3", "Almacén", "Inoperativo", Equipo.DISPONIBILIDAD_NO_DISPONIBLE),
        ]
        creados = actualizados = 0
        for codigo, nombre, tipo, marca, modelo, area, estado, disponibilidad in rows:
            origen = None if disponibilidad == Equipo.DISPONIBILIDAD_LIBRE else Equipo.ORIGEN_OCUPACION_ASIGNACION_DIRECTA
            if estado in {"En reparación", "Inoperativo"}:
                origen = Equipo.ORIGEN_OCUPACION_INCIDENCIA
            _, created = Equipo.objects.update_or_create(
                codigo_equipo=codigo,
                defaults={
                    "nombre_equipo": nombre,
                    "tipo_equipo": t[tipo],
                    "marca": m[marca],
                    "modelo": modelo,
                    "numero_serie": codigo.replace("DEMO-", "SER-"),
                    "area": areas[area],
                    "estado": e[estado],
                    "estado_tecnico": e[estado],
                    "disponibilidad": disponibilidad,
                    "origen_ocupacion": origen,
                    "observaciones": "Dato demostrativo para validar inventario, disponibilidad y reportes.",
                    "activo": True,
                },
            )
            creados += int(created)
            actualizados += int(not created)
        return f"{creados} creados, {actualizados} actualizados"

    def _repuestos(self):
        rows = [
            ("Mouse USB optico", "Perifericos", "unidad", 24, 6),
            ("Teclado USB estandar", "Perifericos", "unidad", 18, 5),
            ("Cable HDMI 1.8 m", "Cables y conectividad", "unidad", 16, 4),
            ("Cable de red Cat 6", "Redes", "unidad", 32, 8),
            ("Memoria RAM DDR4 8 GB", "Componentes internos", "unidad", 7, 2),
            ("Disco SSD 240 GB SATA", "Almacenamiento", "unidad", 8, 2),
            ("Toner laser Brother TN-660 compatible", "Consumibles de impresion", "unidad", 6, 2),
            ("Kit tinta Epson 544", "Consumibles de impresion", "kit", 5, 2),
        ]
        creados = actualizados = 0
        for nombre, categoria, unidad, stock, minimo in rows:
            _, created = Repuesto.objects.update_or_create(
                nombre=nombre,
                defaults={
                    "categoria": categoria,
                    "unidad": unidad,
                    "stock_actual": stock,
                    "stock_minimo": minimo,
                    "ubicacion": "Almacen TI - demo",
                    "observaciones": "Dato demostrativo para validar stock y reportes.",
                    "activo": True,
                },
            )
            creados += int(created)
            actualizados += int(not created)
        return f"{creados} creados, {actualizados} actualizados"

    def _incidencias(self, areas, usuarios, equipos_result):
        del equipos_result
        estado_map = {estado.name: estado for estado in Estado.objects.all()}
        users = {user.username: user for user in CustomUser.objects.filter(username__startswith="7000000")}
        equipos = {equipo.codigo_equipo: equipo for equipo in Equipo.objects.filter(codigo_equipo__startswith="DEMO-")}
        now = timezone.now()
        rows = [
            ("DEMO-2026-001", "70000005", "Trámite Documentario", "DEMO-TRA-IMP-001", "hardware", "Cerrado", "70000002", "Impresora no imprime documentos de mesa de partes.", "Se realizo limpieza y prueba de impresion.", 12),
            ("DEMO-2026-002", "70000005", "Contabilidad", "DEMO-ADM-PC-001", "software", "Resuelto", "70000003", "Equipo lento al abrir hojas de calculo.", "Se optimizo inicio y se libero espacio.", 9),
            ("DEMO-2026-003", "70000005", "SIAGIE", "DEMO-UPDI-LAP-001", "sistema", "Pendiente de validación", "70000002", "No se puede acceder al sistema SIAGIE.", "Se corrigio configuracion del navegador.", 7),
            ("DEMO-2026-004", "70000005", "Contabilidad", "DEMO-ADM-PC-001", "red", "En Proceso", "70000002", "Puesto sin conexion a red interna.", "", 5),
            ("DEMO-2026-005", "70000005", "Tesorería", "", "otros", "Asignado", "70000003", "Instalacion de software de lectura PDF.", "", 3),
            ("DEMO-2026-006", "70000005", "Estadística", "DEMO-UPDI-SW-001", "red", "Cerrado", "70000003", "Intermitencia en conexion de equipos del area.", "Se reemplazo cable de red y se valido enlace.", 15),
            ("DEMO-2026-007", "70000005", "Trámite Documentario", "DEMO-REP-LAP-001", "hardware", "Cerrado", "70000002", "Laptop con falla de pantalla requiere prestamo temporal.", "Se entrego laptop temporal mientras se repara pantalla.", 6),
            ("DEMO-2026-008", "70000005", "Trámite Documentario", "", "hardware", "Pendiente", "", "Mouse no responde correctamente.", "", 1),
        ]
        creadas = actualizadas = 0
        for codigo, user, area, equipo, categoria, estado, tecnico, descripcion, solucion, dias in rows:
            incidencia, created = Incidencia.objects.update_or_create(
                codigo=codigo,
                defaults={
                    "creador": users[user],
                    "area": areas[area],
                    "equipo": equipos.get(equipo) if equipo else None,
                    "categoria": categoria,
                    "prioridad": Incidencia.PRIORIDAD_MEDIA,
                    "descripcion": descripcion,
                    "estado": estado_map[estado],
                    "tecnico_asignado": users.get(tecnico) if tecnico else None,
                    "fecha_asignacion": now - timedelta(days=max(dias - 1, 0)) if tecnico else None,
                    "solucion_aplicada": solucion or None,
                    "tipo_resolucion": Incidencia.RESOLUCION_REPARADO if solucion else None,
                    "fecha_resolucion": now - timedelta(days=max(dias - 2, 0)) if solucion else None,
                    "fecha_cierre": now - timedelta(days=max(dias - 3, 0)) if estado == "Cerrado" else None,
                    "estado_sla": "cumplido" if estado in {"Cerrado", "Resuelto", "Pendiente de validación"} else "en_tiempo",
                    "observaciones_internas": "Incidencia demostrativa para reportes y validacion funcional.",
                },
            )
            Incidencia.objects.filter(pk=incidencia.pk).update(fecha_creacion=now - timedelta(days=dias))
            self._comentario_demo(incidencia)
            creadas += int(created)
            actualizadas += int(not created)
        return f"{creadas} creadas, {actualizadas} actualizadas"

    def _comentario_demo(self, incidencia):
        usuario = incidencia.tecnico_asignado or incidencia.creador
        Comentario.objects.update_or_create(
            incidencia=incidencia,
            usuario=usuario,
            texto="Seguimiento demostrativo registrado para validar trazabilidad.",
            defaults={"tipo_comentario": "tecnico" if incidencia.tecnico_asignado else "observacion"},
        )

    def _metricas(self):
        today = timezone.localdate()
        creadas = actualizadas = 0
        for offset, abiertos, cerrados in [(6, 7, 2), (5, 8, 3), (4, 6, 4), (3, 5, 5), (2, 4, 6), (1, 4, 7), (0, 4, 8)]:
            _, created = MetricaDiaria.objects.update_or_create(
                fecha=today - timedelta(days=offset),
                defaults={
                    "tickets_abiertos": abiertos,
                    "tickets_cerrados": cerrados,
                    "sla_vencidos": 0,
                    "sla_por_vencer": 1,
                    "tickets_validacion_vencidos": 1 if offset in {1, 0} else 0,
                    "equipos_reparacion_sin_ticket_activo": 1,
                    "reemplazos_activos": 1,
                    "metadata": {"origen": "demo", "uso": "presentacion"},
                },
            )
            creadas += int(created)
            actualizadas += int(not created)
        return f"{creadas} creadas, {actualizadas} actualizadas"
