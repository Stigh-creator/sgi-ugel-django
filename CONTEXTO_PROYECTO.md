# Contexto del Proyecto: Sistema de Gestión de Incidencias (SGI)

Este documento centraliza el funcionamiento real y técnico de la plataforma SGI, sirviendo como base para el desarrollo, auditoría y mejora del sistema.

## 1. Descripción General del Sistema

*   **Objetivo:** Centralizar y automatizar el reporte, seguimiento y resolución de incidentes técnicos (Hardware, Software, Red, Sistemas) y el control de activos institucionales de la UGEL Morropón.
*   **Problema que resuelve:** La falta de trazabilidad en los reportes de fallas, la saturación de los técnicos por falta de priorización, y la desconexión entre las incidencias reportadas y el estado real del inventario físico.
*   **Tipo de usuarios:**
    *   **Trabajador (Usuario):** Reporta incidencias, comenta en el chat de seguimiento, y cierra sus propios tickets tras validar la solución.
    *   **Técnico TI:** Atiende, diagnostica y resuelve incidencias asignadas. Puede subir evidencias fotográficas de la solución.
    *   **Administrador / Ingeniero TI:** Gestión total de usuarios, áreas, inventario, asignaciones de carga de trabajo, reportes globales y auditoría.
    *   **Almacén:** Gestiona inventario operativo, repuestos, mantenimiento preventivo y exportación Excel de equipos.

---

## 2. Módulos del Sistema

### A. Gestión de Incidencias
Permite el ciclo de vida completo de un ticket de soporte.
*   **Acciones clave:** Creación (con adjuntos), Asignación de especialista, Cambio de estados, Registro de solución técnica, Reapertura por disconformidad y Cierre definitivo.
*   **Entidades:** `Incidencia`, `Estado`, `Comentario`, `Notificacion`.

### B. Inventario de Equipos
Control detallado de los bienes tecnológicos de la institución.
*   **Acciones clave:** Registro de hardware, cambio manual de estado, trazabilidad de historial de estados por equipo, vinculación dinámica con incidencias de hardware, control de repuestos con stock mínimo y programación de mantenimiento preventivo.
*   **Entidades:** `Equipo`, `TipoEquipo`, `Marca`, `EstadoEquipo`, `HistorialEstadoEquipo`, `Repuesto`, `MantenimientoPreventivo`.

### C. Usuarios y Seguridad
Gestión de perfiles basada en el DNI como identificador único.
*   **Acciones clave:** Autenticación, control de sesiones (online/offline), perfiles con foto, y validación de carga de trabajo para técnicos.
*   **Entidades:** `CustomUser`, `Area`.

### D. Auditoría y Reportes
Registro de acciones críticas y generación de documentos.
*   **Acciones clave:** Log de auditoría para cambios en incidencias, inventario y usuarios; generación de PDF individual y por rango de incidencias; PDF del dashboard; PDF de inventario; PDF de auditoría; y exportación Excel únicamente para inventario.
*   **Entidades:** `Auditoria`.

### E. Dashboard Operativo
Permite visualizar información resumida sin sobrecargar los módulos operativos.
*   **Incidencias:** KPIs de críticas/alta prioridad, pendientes o activas, resueltas, cerradas, incidencias del día, SLA por vencer/vencidas y métricas por técnico.
*   **Inventario:** Vista separada del dashboard de incidencias, con indicadores y gráficas de equipos por estado, disponibilidad, tipo, marca y área.
*   **Exportación:** El dashboard de incidencias e inventario puede exportarse a PDF con filtros por fecha y criterios principales.

### F. Notificaciones en Tiempo Real
Permite avisar eventos relevantes sin recargar la página.
*   **Acciones clave:** Campana priorizada en el header, contador de pendientes, enlaces directos, lectura individual/masiva y entrega por WebSocket.
*   **Arquitectura:** Persistencia en `Notificacion` y `NotificacionUsuario`; emisión en tiempo real con Django Channels, Daphne/ASGI y endpoint `/ws/notificaciones/`.
*   **Eventos cubiertos:** Asignación, reasignación, rechazo, resolución, cierre, comentarios, SLA vencido/por vencer y eventos relevantes de inventario.

---

## 3. Flujo Actual del Sistema (Real)

1.  **Reporte:** Un *Trabajador* crea una incidencia. Si la categoría es "Hardware", el sistema filtra equipos con estado técnico operativo de su sede principal y valida que no estén vinculados a otra incidencia activa. Al guardar, el equipo queda con estado técnico "Observación" y origen de ocupación "Incidencia".
2.  **Asignación:** El *Administrador* asigna un *Técnico*. La validación usa capacidad dinámica (`capacidad_base`) y peso por prioridad. El equipo pasa automáticamente a "En reparación".
3.  **Gestión Técnica:** El técnico puede "Aceptar" (pasa a "En Proceso") o "Rechazar" (debe justificar y la incidencia vuelve a estar sin técnico).
4.  **Resolución:** El técnico registra la solución. El ticket queda en "Resuelto" como estado operativo equivalente a "Pendiente de validación" del usuario. Debe elegir un tipo:
    *   **Reparado:** El equipo se mantiene "En reparación" hasta que el usuario confirme el cierre.
*   **Reemplazado (temporal):** Se debe seleccionar un equipo del inventario que esté "Libre" y sea compatible. El equipo original pasa a "Inoperativo" y el de reemplazo se mueve al área del solicitante y queda con disponibilidad "Reemplazo temporal" hasta el cierre del ticket.
    *   **Dado de baja:** El equipo pasa a "Dado de baja" y queda inactivo (activo=False) en el sistema.
5.  **Cierre:** El *Trabajador* revisa la solución. Si está conforme, cierra el ticket. Si es "Reparado", el equipo vuelve a estado técnico "Operativo" automáticamente. Si fue "Reemplazado", el préstamo temporal se cierra, el reemplazo vuelve a "Libre" y se restaura su origen de área cuando aplica. Si no está conforme, puede "Reabrir". Si no responde, el job `autocerrar_incidencias_resueltas` cierra automáticamente según SLA.

---

## 4. Estados del Sistema

### Estados de Incidencias
*   **Pendiente:** Recién creada, sin técnico asignado.
*   **Asignado:** Técnico vinculado, pendiente de aceptación por su parte.
*   **En Proceso:** Técnico trabajando activamente en el problema.
*   **Rechazado:** El técnico no pudo atenderla; requiere nueva revisión por el Admin.
*   **Reabierto:** El usuario reporta que el problema persiste tras una solución inicial.
*   **Pendiente de validación:** Estado de negocio usado para representar una solución técnica pendiente de conformidad del usuario. En la UI actual convive con "Resuelto".
*   **Resuelto:** Solución técnica registrada por el técnico, pendiente de confirmación del usuario.
*   **Cerrado:** Ciclo finalizado satisfactoriamente. Inmutable.

### Estados Técnicos de Equipos
*   **Operativo:** Equipo funcional y disponible para uso o asignación.
*   **Observación:** Vinculado a una incidencia abierta pero no asignada aún.
*   **En reparación:** Siendo intervenido por un técnico o asignado a un ticket en proceso.
*   **Inoperativo:** Fallo crítico detectado; equipo no funcional (asociado a reemplazos).
*   **Dado de baja:** Equipo retirado del servicio permanentemente. No puede volver a Operativo.

### Disponibilidad de Equipos
*   **Libre:** Equipo disponible para asignación o reemplazo.
*   **En uso:** Equipo ocupado por operación regular o incidencia.
*   **Reemplazo temporal:** Equipo operativo usado como préstamo temporal en una incidencia.

### Origen de Ocupación
*   **Manual:** Cambio administrativo directo.
*   **Asignación directa:** Ocupación registrada desde datos antiguos o edición administrativa segura.
*   **Incidencia:** Ocupación causada por un ticket.
*   **Reemplazo:** Ocupación causada por reemplazo temporal.
*   **Mantenimiento:** Ocupación causada por mantenimiento programado.

### Estados SLA
*   **En tiempo:** La incidencia está dentro de sus plazos.
*   **Por vencer:** La incidencia consumió al menos el 80% del tiempo SLA sin vencer todavía.
*   **Respuesta vencida:** No se aceptó/asignó dentro del tiempo definido.
*   **Resolución vencida:** No se resolvió dentro del tiempo definido.
*   **Escalado:** Requiere atención administrativa.
*   **Cumplido:** Se resolvió/cerró dentro del flujo.
*   **No aplica:** No existe configuración SLA aplicable.

---

## 5. Reglas de Negocio (Lógica Detallada)

*   **Capacidad Operativa:** Cada técnico tiene `capacidad_base`. La carga se calcula por peso de prioridad: Baja/Media=1, Alta=2, Crítica=3. No se puede asignar si la carga ponderada supera su capacidad.
*   **Prioridad Restringida:** Los *Trabajadores* no pueden asignar prioridad "Crítica" o "Alta". El sistema fuerza "Media" por defecto para evitar abusos. Solo el *Administrador* puede elevarla.
*   **Integridad de Hardware:** Un equipo no puede estar en dos incidencias activas simultáneamente. Si está en una incidencia, desaparece de la lista de selección para otros reportes.
*   **Compatibilidad de Reemplazos:** El sistema agrupa tipos de equipo. Por ejemplo, "Computadora de Escritorio", "Laptop" y "Servidor" son compatibles entre sí para reemplazos. Una "Impresora" no puede reemplazar una "Laptop".
*   **Inmutabilidad de Historial:** Si un técnico cambia de área, los tickets que cerró en su área anterior permanecen vinculados a esa área para no alterar las estadísticas históricas.
*   **Validación de Usuarios:** No se puede cambiar el área o rol de un técnico si tiene tickets "En Proceso" o "Asignados", para evitar dejar huérfana la responsabilidad de los equipos.
*   **DNI como Identificador:** El `username` es estrictamente el DNI de 8 dígitos. Se valida mediante expresiones regulares.
*   **Presencia en Tiempo Real:** El sistema detecta si un usuario está "Online" si ha tenido actividad en los últimos 5 minutos (300 segundos).
*   **Concurrencia:** Las operaciones críticas de incidencia usan servicios de dominio con `transaction.atomic()` y `select_for_update(nowait=True)` para bloquear incidencia/equipos durante asignación, aceptación, rechazo, resolución, reapertura y cierre. Si otro proceso tiene el registro bloqueado, se falla rápido con mensaje operativo.
*   **Protección Admin:** Django Admin es de consulta/control administrativo limitado para entidades críticas. Los cambios de estado, resolución, SLA, disponibilidad y origen de ocupación deben ejecutarse mediante servicios del sistema.
*   **Auto-cierre:** Las incidencias resueltas reciben `fecha_auto_cierre`. El comando `autocerrar_incidencias_resueltas` cierra tickets vencidos de forma idempotente.
*   **SLA:** `SLAConfiguracion` define tiempos de respuesta, resolución y auto-cierre por prioridad/categoría. El comando `procesar_sla_incidencias` marca zona preventiva "Por vencer" al 80%, vencimientos y escalamiento.
*   **Edición de Prioridad:** La prioridad queda editable para administrador/técnico al crear o configurar tickets pendientes. Si un ticket fue rechazado y queda sin técnico asignado, la prioridad se desbloquea para reajuste antes de reasignarlo. Si el ticket ya fue aceptado por el técnico y está "En Proceso", la configuración administrativa se bloquea para evitar cambios fuera de flujo.
*   **PDF por Sección:** Los reportes PDF de incidencias respetan la pestaña activa del módulo. Para administrador, la vista "Creadas" exporta solo las creadas por él. Para técnico, "Asignadas" exporta solo sus tickets asignados y "Creadas" exporta solo las incidencias creadas por él.
*   **Stock mínimo de repuestos:** Almacén y superusuario pueden registrar repuestos, definir stock mínimo y ajustar el stock real. El sistema muestra alertas cuando `stock_actual <= stock_minimo`.
*   **Mantenimiento preventivo:** Almacén y superusuario pueden programar mantenimientos por equipo, fecha, frecuencia, responsable y descripción. Los mantenimientos programados para los próximos 7 días o vencidos aparecen como alerta operativa y pueden marcarse como realizados con resultado técnico.

---

## 6. Roles y Permisos

| Rol | Permisos Principales |
| :--- | :--- |
| **Trabajador** | Crear incidencias, ver sus propios tickets, comentar (chat), descargar PDF de sus incidencias, cerrar/reabrir sus tickets. |
| **Técnico** | Ver tickets asignados y creados por él, aceptar/rechazar tickets, registrar soluciones con hasta 3 fotos, descargar PDF de incidencias permitidas, ver inventario. |
| **Admin** | Gestión total de usuarios, áreas y equipos. Asignación manual de tickets, edición controlada de incidencias, dashboard, reportes PDF y auditoría. |
| **Almacén** | Gestión operativa del inventario y exportación Excel del inventario. |
| **Superusuario** | Acceso técnico total, incluida exportación Excel del inventario. |

Regla de seguridad de reportes:
*   Los PDF son accesibles para usuarios que tengan permiso de ver el módulo o registro correspondiente.
*   El Excel de inventario queda restringido a Almacén y Superusuario. El Administrador no descarga Excel de inventario para reducir riesgos de modificación externa no controlada.

---

## 7. Notas de Ayuda (Manual Rápido)

### Para el Usuario (Trabajador)
*   **¿Cómo reportar?:** Ve a "Nueva Incidencia", elige la categoría. Si es Hardware, selecciona tu equipo de la lista. Si no aparece, es porque ya tiene un reporte abierto o no está asignado a tu área.
*   **Evidencias:** Siempre sube una foto del error o del equipo. Esto ayuda al técnico a llevar los repuestos necesarios.
*   **Cierre de Ticket:** Una vez que el técnico marque "Resuelto", recibirás una notificación. Debes entrar al ticket y confirmar el cierre para que el equipo vuelva a estar "Operativo".

### Para el Técnico TI
*   **Aceptar Tickets:** Debes aceptar el ticket asignado para que el usuario sepa que ya estás en camino o trabajando en ello.
*   **Reemplazos:** Si el equipo requiere una reparación larga, usa la opción "Reemplazado (temporal)". El sistema te pedirá elegir un equipo LIBRE del almacén.
*   **Solución:** Describe detalladamente qué se hizo. Esta información es vital para el historial del equipo.

### Para el Administrador
*   **Carga de Trabajo:** Si un técnico no aparece en la lista de asignación, verifica si ya tiene 4 tickets activos.
*   **Auditoría:** Cualquier cambio manual en el estado de un equipo queda registrado con el motivo y el usuario que lo hizo en el módulo de Inventario.
*   **Reportes PDF:** Al exportar incidencias por rango, selecciona primero la pestaña correcta: "Asignadas" o "Creadas". El PDF conserva esa selección.

---

## 8. Modelo de Datos (Resumen Técnico)

*   **Relación Usuario-Área:** Cada usuario pertenece a un área específica. Las incidencias se heredan del área del creador.
*   **Relación Incidencia-Equipo:** Una incidencia de hardware apunta a un registro único en el inventario.
*   **Trazabilidad:** La tabla `HistorialEstadoEquipo` registra: `estado_anterior`, `estado_nuevo`, `usuario`, `motivo` y `fecha`.
*   **Stock de Repuestos:** `Repuesto` registra nombre, categoría, unidad, stock actual, stock mínimo, ubicación, observaciones y estado activo.
*   **Mantenimiento Preventivo:** `MantenimientoPreventivo` registra equipo, fecha programada, frecuencia, responsable, descripción, estado, resultado y fecha de realización.
*   **Reemplazos:** `ReemplazoEquipoIncidencia` registra incidencia, equipo original, equipo temporal, áreas origen/destino, responsable, fechas, estado activo y metadata.
*   **Auditoría Estructurada:** `Auditoria.metadata` almacena datos explotables en JSON: ids, código de ticket, estados anteriores/nuevos, origen y usuario.
*   **Notificaciones:** Basadas en eventos del sistema para asignación, cambios de estado, comentarios, SLA e inventario. La campana del header muestra contador, prioridad, tipo de evento y acciones de lectura.

---

## 9. Eventos de Negocio Centralizados

La lógica crítica emite eventos mediante `emitir_evento_incidencia(evento, incidencia, actor=None, metadata=None)`. Cada evento centraliza auditoría, notificación y comentario automático cuando aplica.

Eventos obligatorios:
*   `incidencia.creada`
*   `incidencia.asignada`
*   `incidencia.aceptada`
*   `incidencia.rechazada`
*   `incidencia.reasignada`
*   `incidencia.comentada`
*   `incidencia.resuelta`
*   `incidencia.reabierta`
*   `incidencia.cerrada`
*   `incidencia.sla_por_vencer`
*   `incidencia.sla_respuesta_vencido`
*   `incidencia.sla_resolucion_vencido`
*   `inventario.estado_cambiado`
*   `inventario.reemplazo_registrado`

---

## 10. Automatización Operativa

Comandos disponibles:
*   `python manage.py procesar_sla_incidencias`
*   `python manage.py autocerrar_incidencias_resueltas`
*   `python manage.py verificar_integridad_inventario`
*   `python manage.py verificar_integridad_inventario --fix`
*   `python manage.py sistema_integridad_global`
*   `python manage.py sistema_integridad_global --fix`
*   `python manage.py metricas_operativas_sgi`
*   `python manage.py snapshot_metricas`
*   `python manage.py reprocesar_eventos_fallidos`

Reglas:
*   Los jobs son idempotentes.
*   SLA vencido se notifica una sola vez por tipo de vencimiento.
*   Auto-cierre solo actúa sobre incidencias `Resuelto` con `fecha_auto_cierre` vencida.
*   Integridad de inventario reporta equipos fantasma o sin origen de ocupación. Con `--fix` solo corrige casos seguros: equipos ocupados sin origen pasan a `ASIGNACION_DIRECTA` y reemplazos activos de tickets cerrados se liberan como huérfanos corregidos.
*   `metricas_operativas_sgi` muestra conteos de SLA vencidos, SLA por vencer, tickets en validación vencidos, equipos en reparación sin ticket activo y reemplazos activos.
*   `snapshot_metricas` guarda un registro diario en `MetricaDiaria` para histórico operativo y reportes sin consultas pesadas.
*   Los eventos de negocio son idempotentes mediante `Auditoria.evento` + `Auditoria.hash_evento` con restricción única en base de datos; si un retry intenta registrar el mismo evento, no duplica auditoría, notificaciones ni comentarios automáticos.
*   `Auditoria.version_evento` permite evolucionar el contrato de eventos sin romper histórico.
*   `EventoFallido` almacena payload normalizado, error, último error e intentos cuando un evento no puede procesarse, preparando el sistema para reintentos asíncronos.
*   `reprocesar_eventos_fallidos` reintenta eventos no procesados hasta un máximo de 3 intentos por defecto y marca `procesado=True` si el reproceso termina correctamente.
*   `emitir_evento_incidencia` queda preparado para procesamiento asíncrono mediante `USE_ASYNC` e `INCIDENCIA_EVENT_TASK`.
*   Los modelos críticos tienen índices de producción para estados, prioridades, fechas SLA, disponibilidad de equipos y reemplazos activos.
*   En producción debe existir backup lógico diario con retención de 7 a 30 días y prueba periódica de restauración.

---

## 11. Arquitectura de Carpetas Actual

El proyecto mantiene una separación por dominio, con el código de negocio dentro de apps Django y los archivos visuales centralizados en `static`.

| Carpeta / archivo | Propósito actual |
| :--- | :--- |
| `gestion_incidencias/` | Configuración principal de Django: `settings.py`, `urls.py`, `asgi.py` y `wsgi.py`. |
| `tickets/` | Núcleo funcional: usuarios, incidencias, SLA, notificaciones, servicios de dominio, vistas, formularios, templates y tests. |
| `inventario/` | Gestión de equipos, repuestos, mantenimiento preventivo, exportaciones PDF/Excel, templates y tests. |
| `auditoria/` | Bitácora estructurada, middleware, señales, vistas, exportación PDF y tests. |
| `static/` | CSS y JavaScript compartido o por módulo. Incluye `static/js/notificaciones-realtime.js`. |
| `media/` | Archivos cargados por usuarios: evidencias, fotos de perfil, equipos, documentos y reportes generados. |
| `documentacion/` | Material académico y entregables externos del proyecto. |
| `cargar_maestros.py` | Script de carga de catálogos base para iniciar una base limpia. |
| `reset_db.py` | Utilidad local para reinicio controlado de datos durante desarrollo. |
| `.env` | Variables sensibles locales. No debe subirse al repositorio. |

Observación técnica: la estructura está coherente para continuar hacia PostgreSQL, Docker y despliegue. El siguiente orden recomendado es mantener `static` versionado, dejar `media` fuera de Git, no subir `venv`, y conservar `scratch`/temporales fuera del repositorio.

---

## 12. Funcionalidades Implementadas
*   [x] Autenticación DNI y Perfiles con foto procesada.
*   [x] Chat de seguimiento con miniaturas de imágenes.
*   [x] Filtros inteligentes de incidencias por buscador, área, prioridad, estado y SLA vencidas.
*   [x] Filtros personalizados de inventario por buscador, área, estado, disponibilidad, tipo y marca.
*   [x] Gestión de inventario con PDF individual de equipo, imagen del equipo y reportes PDF/Excel filtrados.
*   [x] Gestión de stock mínimo de repuestos con alertas y ajuste controlado por Almacén/Superusuario.
*   [x] Mantenimiento preventivo programado por equipo con alertas de próximos/vencidos y registro de resultado.
*   [x] Exportación PDF de incidencias individuales con solicitante, técnico, solución, evidencias iniciales/finales y fechas clave.
*   [x] Exportación PDF por rango de incidencias respetando la pestaña activa: todas/asignadas o creadas por el usuario.
*   [x] Exportación PDF de dashboard de incidencias e inventario.
*   [x] Exportación Excel de inventario restringida a Almacén y Superusuario.
*   [x] Auditoría de cambios críticos.
*   [x] Eventos base para notificaciones, auditoría y comentarios automáticos.
*   [x] Previsualización de imágenes antes de subir (UX).
*   [x] Dashboard de incidencias con KPIs y métricas SLA conectadas a fechas reales.
*   [x] Dashboard separado de inventario dentro del módulo Dashboard.
*   [x] PDF de auditoría.
*   [x] Campana de notificaciones priorizadas para administrador, técnico, almacén y trabajador.
*   [x] Entrega de notificaciones en tiempo real mediante Daphne/ASGI, Channels y WebSocket.
*   [x] Migración local a PostgreSQL mediante variables de entorno.

## 13. Pendientes y Mejoras
*   [ ] Revisión final de manual académico, capturas y anexos antes de entrega.
*   [ ] Dockerización para despliegue reproducible.
*   [ ] Configuración de entorno productivo: variables de entorno, servidor ASGI, Redis para Channels, archivos estáticos, backups y monitoreo.
