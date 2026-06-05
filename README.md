# 📋 SGI - Sistema de Gestión de Incidencias (UGEL)

![Django](https://img.shields.io/badge/django-%23092E20.svg?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![PostgreSQL](https://img.shields.io/badge/postgresql-316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)

## 📝 Resumen del Sistema
El **SGI-UGEL** es una solución integral diseñada para digitalizar el flujo de soporte técnico y administrativo en las Unidades de Gestión Educativa Local. El sistema transforma el caos de reportes verbales o por correo en un flujo de trabajo estructurado donde cada incidencia es registrada, categorizada, asignada a un especialista y monitoreada hasta su resolución final. 

Su objetivo principal es eliminar los cuellos de botella en la atención al usuario y proporcionar métricas reales sobre el rendimiento del equipo de soporte.

## 🚀 Características Principales

- **Gestión de Tickets:** Ciclo de vida completo desde "Pendiente" hasta "Cerrado" con historial de cambios, evidencias y comentarios.
- **Roles y Permisos:**
  - 👷 **Trabajador:** Reporta problemas, comenta, valida soluciones y descarga PDF de sus incidencias.
  - 🔧 **Técnico:** Gestiona incidencias asignadas, registra soluciones con evidencias y consulta sus tickets creados.
  - 👨‍💼 **Administrador:** Supervisa incidencias, usuarios, dashboard, inventario, reportes PDF y auditoría.
  - 📦 **Almacén:** Gestiona inventario y exporta Excel de inventario.
- **Inventario:** Registro de equipos, estados técnicos, disponibilidad, historial, relación con incidencias, stock mínimo de repuestos y mantenimiento preventivo programado.
- **Dashboard de KPIs:** Vista separada de incidencias e inventario con métricas operativas y exportación PDF.
- **Notificaciones:** Campana priorizada en tiempo real para eventos de tickets, comentarios, SLA e inventario.
- **Reportes:** PDF individual y por rango de incidencias, PDF de dashboard, PDF/Excel de inventario y PDF de auditoría.
- **Seguridad:** Autenticación por DNI, permisos por rol, auditoría y control de acciones críticas mediante servicios de dominio.

## 🛠️ Stack Tecnológico

- **Backend:** Django 5.x + Python 3.11
- **Base de Datos:** PostgreSQL mediante variables de entorno o `DATABASE_URL`.
- **Frontend:** HTML5, CSS3 (Rich Aesthetics), JavaScript Vanilla
- **Documentación:** ReportLab (Generación de PDF)
- **Tiempo real:** Django Channels + Daphne/ASGI con WebSocket de notificaciones.
- **Infraestructura:** Docker Compose local con servicios `web`, `scheduler`, `db` y `redis`; despliegue preparado para Render con `render.yaml`.
- **Estáticos:** WhiteNoise para servir archivos estáticos en producción.

## Mejoras de Producción

### Servicios de dominio

Las transiciones críticas de incidencias se centralizan en `tickets.services.IncidenciaService`:

```python
IncidenciaService.asignar(...)
IncidenciaService.aceptar(...)
IncidenciaService.rechazar(...)
IncidenciaService.resolver(...)
IncidenciaService.reabrir(...)
IncidenciaService.cerrar(...)
```

Las operaciones usan `transaction.atomic()` y `select_for_update()` para bloquear incidencia y equipos relacionados durante cambios críticos.

### Estados e inventario

El inventario separa:

- `estado_tecnico`: condición real del equipo.
- `disponibilidad`: disponibilidad operativa.
- `origen_ocupacion`: causa de ocupación.

Disponibilidades soportadas:

- `LIBRE`
- `EN_USO`
- `REEMPLAZO_TEMPORAL`

### Repuestos y mantenimiento preventivo

El módulo de inventario incluye controles operativos menores para Almacén y Superusuario:

- Registro de repuestos con categoría, unidad, stock actual, stock mínimo, ubicación y observaciones.
- Alerta visual cuando el stock actual queda igual o por debajo del mínimo configurado.
- Ajuste rápido de stock desde el panel de inventario con auditoría.
- Programación de mantenimiento preventivo por equipo, fecha, frecuencia, responsable y descripción.
- Alertas de mantenimientos vencidos o próximos a 7 días.
- Registro de resultado técnico al marcar un mantenimiento como realizado.

### SLA

El modelo `SLAConfiguracion` define tiempos de:

- respuesta
- resolución
- auto-cierre

Las incidencias almacenan:

- `fecha_limite_respuesta`
- `fecha_limite_resolucion`
- `fecha_auto_cierre`
- `estado_sla`
- banderas de notificación SLA

### Eventos

Las notificaciones, auditoría y comentarios automáticos se emiten desde:

```python
emitir_evento_incidencia(evento, incidencia, actor=None, metadata=None)
```

Eventos implementados:

- `incidencia.creada`
- `incidencia.asignada`
- `incidencia.aceptada`
- `incidencia.rechazada`
- `incidencia.reasignada`
- `incidencia.comentada`
- `incidencia.resuelta`
- `incidencia.reabierta`
- `incidencia.cerrada`
- `incidencia.sla_por_vencer`
- `incidencia.sla_respuesta_vencido`
- `incidencia.sla_resolucion_vencido`
- `inventario.estado_cambiado`
- `inventario.reemplazo_registrado`

La entrega visual en la campana se actualiza en tiempo real mediante ASGI/Channels. El cliente se conecta al WebSocket `/ws/notificaciones/` y recibe nuevas notificaciones sin recargar la página. En desarrollo se usa `InMemoryChannelLayer`; para producción se recomienda Redis como backend de canales.

### Trazabilidad

`Auditoria.metadata` registra datos estructurados en JSON.
`Auditoria.evento` + `Auditoria.hash_evento` tienen una restricción única en base de datos para impedir duplicados incluso con retries o workers concurrentes.
`Auditoria.version_evento` versiona el contrato de eventos para evolucionar mensajes y metadata sin perder trazabilidad histórica.
`EventoFallido` funciona como dead letter operativo para registrar payload normalizado, error e intentos cuando un evento no puede procesarse.
`ReemplazoEquipoIncidencia` registra reemplazos temporales con incidencia, equipo original, equipo de reemplazo, áreas, responsable, fechas y metadata.
`MetricaDiaria` guarda snapshots diarios para reportes históricos sin depender solo de consultas en vivo.

### Integridad Administrativa

Los campos críticos de incidencias e inventario quedan protegidos en Django Admin. Los cambios de estado, SLA, asignaciones, resolución, disponibilidad y origen de ocupación deben pasar por los servicios de dominio para conservar auditoría, inventario y notificaciones consistentes.

### Índices Operativos

Se agregaron índices para consultas de producción en incidencias, SLA, prioridad, disponibilidad de equipos y reemplazos activos. Esto mejora listados, jobs e integridad cuando el volumen de tickets crezca.

### Comandos Programados

Ejecutar manualmente:

```bash
python manage.py procesar_sla_incidencias
python manage.py autocerrar_incidencias_resueltas
python manage.py verificar_integridad_inventario
python manage.py sistema_integridad_global
python manage.py verificar_integridad_inventario --fix
python manage.py sistema_integridad_global --fix
python manage.py metricas_operativas_sgi
python manage.py snapshot_metricas
python manage.py reprocesar_eventos_fallidos
```

En Docker Compose existe un servicio `scheduler` que ejecuta cada 15 minutos:

```bash
python manage.py procesar_sla_incidencias
python manage.py autocerrar_incidencias_resueltas
python manage.py metricas_operativas_sgi
```

En Render, `render.yaml` crea un Cron Job equivalente con frecuencia de 15 minutos.

Ejecución recomendada si se administra manualmente en producción:

```bash
*/5 * * * * /ruta/python /ruta/manage.py procesar_sla_incidencias
*/15 * * * * /ruta/python /ruta/manage.py autocerrar_incidencias_resueltas
0 7 * * * /ruta/python /ruta/manage.py verificar_integridad_inventario
5 0 * * * /ruta/python /ruta/manage.py snapshot_metricas
*/30 * * * * /ruta/python /ruta/manage.py reprocesar_eventos_fallidos
```

Todos los comandos son idempotentes.

`--fix` solo aplica correcciones seguras: SLA vencido, auto-cierre, reemplazos huérfanos cerrados y equipos ocupados sin origen pasan a `ASIGNACION_DIRECTA`. Los casos ambiguos de inventario se reportan para revisión manual.

Los eventos de negocio usan `hash_evento` en auditoría para evitar duplicar notificaciones, comentarios automáticos e historial ante retries o jobs repetidos. El hook `USE_ASYNC` + `INCIDENCIA_EVENT_TASK` deja preparado el camino para procesar eventos con Celery u otro worker sin cambiar la API de dominio.

### Backup Lógico

En producción se recomienda backup lógico diario de la base de datos y retención mínima de 7 a 30 días. Para PostgreSQL:

```bash
pg_dump --format=custom --file=/backups/sgi_$(date +%Y%m%d).dump sgi_db
```

Validar restauración periódicamente en un entorno de prueba. Un backup que no se restaura no cuenta como backup.

## 📦 Instalación y Configuración

### Prerrequisitos
- Docker Desktop y Docker Compose para el flujo recomendado.
- Python 3.11+ y Pip solo si se ejecuta sin Docker.
- Git para clonar y publicar el proyecto.

### Ejecución local con Docker

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/Stigh-creator/sgi-ugel-django.git](https://github.com/Stigh-creator/sgi-ugel-django.git)
   cd sgi-ugel-django
   ```

2. **Crear archivo de entorno:**
   Copiar `.env.example` como `.env` y ajustar al menos:
   - `DJANGO_SECRET_KEY`
   - `DB_PASSWORD`
   - `DJANGO_ALLOWED_HOSTS`
   - `DJANGO_CSRF_TRUSTED_ORIGINS` si se accede desde otra IP o dominio.
   - Variables de seguridad productiva (`DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SESSION_COOKIE_SECURE`, `DJANGO_CSRF_COOKIE_SECURE` y `DJANGO_SECURE_HSTS_SECONDS`) cuando se ejecute fuera del entorno local.

3. **Levantar servicios:**
   ```bash
   docker compose up --build
   ```

4. **Cargar catálogos base en una base limpia:**
   ```bash
   docker compose exec web python cargar_maestros.py
   ```

5. **Ingresar al sistema:**
   Abrir `http://localhost:8000`.

El `docker-compose.override.yml` está pensado para desarrollo local: monta el código dentro del contenedor y usa `runserver`. El `docker-compose.yml` base mantiene la configuración más cercana a producción con Daphne/ASGI.

### Ejecución local sin Docker

1. Crear y activar un entorno virtual.
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Configurar `.env` con PostgreSQL local.
4. Ejecutar migraciones y catálogos:
   ```bash
   python manage.py migrate
   python cargar_maestros.py
   ```
5. Levantar:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

## Despliegue en Render

El proyecto incluye `render.yaml` para crear desde GitHub:

- Servicio web Docker (`gestion-incidencias-web`).
- Base PostgreSQL (`gestion-incidencias-db`).
- Cron Job Docker (`gestion-incidencias-scheduler`) cada 15 minutos para SLA, auto-cierre y métricas.
- Disco persistente `gestion-incidencias-media` montado en `/app/media` para archivos subidos por usuarios.

Pasos generales:

1. Subir a GitHub los cambios de `Dockerfile`, `requirements.txt`, `render.yaml`, `gestion_incidencias/settings.py` y `.env.example`.
2. En Render, crear un **Blueprint** desde el repositorio.
3. Verificar que Render genere `DJANGO_SECRET_KEY`, conecte `DATABASE_URL` desde PostgreSQL y mantenga activas las variables HTTPS/cookies seguras definidas en `render.yaml`.
4. Luego del primer despliegue, ejecutar una tarea puntual para migraciones/catálogos si hace falta:
   ```bash
   python manage.py migrate
   python cargar_maestros.py
   ```

Notas importantes para producción:

- Los archivos de `media/` subidos por usuarios quedan cubiertos por el disco persistente configurado en `render.yaml`. Si se cambia de proveedor o se escala la estrategia, usar almacenamiento externo equivalente.
- Para WebSockets en una sola instancia se puede trabajar con la configuración actual; si se escala a varias instancias, configurar Redis externo y `REDIS_URL`.
- Mantener `.env` fuera de Git. El archivo versionado es `.env.example`.

## Archivos Importantes

| Archivo | Uso |
| :--- | :--- |
| `requirements.txt` | Dependencias Python, incluye Django, Channels, Daphne, PostgreSQL, ReportLab y WhiteNoise. |
| `.env.example` | Plantilla de variables locales y de producción. No contiene secretos reales. |
| `Dockerfile` | Imagen Docker para Render y ejecución productiva. |
| `docker-compose.yml` | Servicios locales principales: web, scheduler, PostgreSQL y Redis. |
| `docker-compose.override.yml` | Ajustes de desarrollo local con volumen de código y `runserver`. |
| `render.yaml` | Blueprint de Render para web, base PostgreSQL y cron programado. |
| `.dockerignore` | Evita copiar `.env`, temporales, media local y dependencias al build. |
