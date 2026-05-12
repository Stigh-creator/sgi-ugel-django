# 📋 SGI - Sistema de Gestión de Incidencias (UGEL)

![Django](https://img.shields.io/badge/django-%23092E20.svg?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)

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
- **Inventario:** Registro de equipos, estados técnicos, disponibilidad, historial y relación con incidencias.
- **Dashboard de KPIs:** Vista separada de incidencias e inventario con métricas operativas y exportación PDF.
- **Reportes:** PDF individual y por rango de incidencias, PDF de dashboard, PDF/Excel de inventario y PDF de auditoría.
- **Seguridad:** Autenticación por DNI, permisos por rol, auditoría y control de acciones críticas mediante servicios de dominio.

## 🛠️ Stack Tecnológico

- **Backend:** Django 5.x + Python 3.12
- **Base de Datos:** SQLite en desarrollo. PostgreSQL queda planificado para despliegue.
- **Frontend:** HTML5, CSS3 (Rich Aesthetics), JavaScript Vanilla
- **Documentación:** ReportLab (Generación de PDF)
- **Infraestructura:** Ejecución local con Django. Docker queda planificado para despliegue reproducible.

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

Ejecución recomendada en producción:

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
- Python 3.10+
- Pip (Gestor de paquetes)

### Pasos para ejecución local

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/Stigh-creator/sgi-ugel-django.git](https://github.com/Stigh-creator/sgi-ugel-django.git)
   cd sgi-ugel-django
