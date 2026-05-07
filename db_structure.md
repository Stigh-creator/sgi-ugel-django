# Estructura de la Base de Datos - Gestión de Incidencias

Este documento detalla la arquitectura de datos actual del sistema de Gestión de Incidencias UGEL Morropón, incluyendo tablas, campos, tipos de datos y relaciones.

## 1. Aplicación: `tickets` (Núcleo del Sistema)

### Tabla: `CustomUser` (tickets_customuser)
Gestiona la autenticación y perfiles de usuario. Extiende de `AbstractUser` de Django.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `username` | CharField(150) | Unique, DNI(8) | DNI del usuario (usado como login). |
| `first_name` | CharField(150) | Not Null | Nombres del usuario. |
| `last_name` | CharField(150) | Not Null | Apellidos del usuario. |
| `email` | EmailField | Null, Blank | Correo institucional o personal. |
| `role` | CharField(15) | Choice | Rol: `usuario`, `tecnico`, `administrador`. |
| `telefono` | CharField(9) | Not Null | Teléfono de contacto (9 dígitos). |
| `area` | ForeignKey | FK -> `Area` (Set Null) | Área a la que pertenece el trabajador. |
| `foto` | ImageField | Null, Blank | Foto de perfil (almacenada en `perfiles/`). |
| `last_password_change` | DateTimeField | Not Null | Fecha del último cambio de contraseña. |
| `must_change_password` | BooleanField | Default: False | Obliga al cambio de clave tras reset. |
| `last_seen` | DateTimeField | Null, Blank | Última actividad para estado "En línea". |
| `capacidad_base` | PositiveIntegerField | Default: 4 | Capacidad operativa base para balanceo de carga. |
| `is_active` | BooleanField | Default: True | Habilita o bloquea el acceso del usuario. |
| `is_staff` | BooleanField | Default: False | Acceso al panel administrativo de Django. |
| `date_joined` | DateTimeField | Not Null | Fecha de creación del usuario. |

### Tabla: `Area` (tickets_area)
Dependencias administrativas de la UGEL.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `name` | CharField(100) | Not Null | Nombre del área (ej. Tesorería). |
| `sede_principal` | CharField(20) | Null, Blank, Choice | Sede: DIRECCIÓN, AGP, ADMINISTRACIÓN, UPDI. |

### Tabla: `Estado` (tickets_estado)
Catálogo maestro de estados de las incidencias.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `name` | CharField(50) | Unique, Not Null | Nombre del estado del ticket. |

*Nota: Existe una restricción de unicidad combinada para `name` y `sede_principal`.*

### Tabla: `Incidencia` (tickets_incidencia)
Entidad principal para el registro de tickets de soporte.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `codigo` | CharField(20) | Unique | Código generado (ej. INC-2024-0001). |
| `creador` | ForeignKey | FK -> `CustomUser` | Usuario que reporta la falla. |
| `area` | ForeignKey | FK -> `Area` | Área donde ocurre el problema. |
| `equipo` | ForeignKey | FK -> `Equipo` (Set Null) | Equipo inventariado afectado. |
| `categoria` | CharField(20) | Choice | hardware, software, red, sistema, otros. |
| `prioridad` | CharField(20) | Choice | baja, media, alta, critica. |
| `descripcion` | TextField | Not Null | Detalle del problema. |
| `estado` | ForeignKey | FK -> `Estado` | Estado actual del ticket. |
| `tecnico_asignado` | ForeignKey | FK -> `CustomUser` | Técnico responsable del ticket. |
| `fecha_asignacion` | DateTimeField | Null, Blank | Momento en que se asignó la incidencia. |
| `fecha_programada_atencion` | DateField | Null, Blank | Fecha programada para la atención. |
| `hora_programada_atencion` | TimeField | Null, Blank | Hora programada para la atención. |
| `observaciones_internas` | TextField | Null, Blank | Notas internas para gestión técnica. |
| `imagen_adjunta` | ImageField | Null, Blank | Foto inicial de la incidencia. |
| `otro_tipo` | CharField(100) | Null, Blank | Tipo libre cuando el equipo no existe en inventario. |
| `otro_marca` | CharField(100) | Null, Blank | Marca libre cuando el equipo no existe en inventario. |
| `otro_modelo` | CharField(100) | Null, Blank | Modelo libre cuando el equipo no existe en inventario. |
| `otro_serie` | CharField(100) | Null, Blank | Serie libre cuando el equipo no existe en inventario. |
| `solucion_aplicada` | TextField | Null, Blank | Descripción técnica de la solución. |
| `tipo_resolucion` | CharField(20) | Null, Blank, Choice | Tipo de salida técnica: reparado, reemplazado, baja, derivado. |
| `equipo_reemplazo` | ForeignKey | FK -> `Equipo` (Set Null) | Equipo que sustituye al afectado (si aplica). |
| `evidencia_solucion` | ImageField | Null, Blank | Foto de prueba de la resolución. |
| `evidencia_solucion_2` | ImageField | Null, Blank | Evidencia adicional de solución. |
| `evidencia_solucion_3` | ImageField | Null, Blank | Evidencia adicional de solución. |
| `fecha_resolucion` | DateTimeField | Null, Blank | Fecha y hora de resolución técnica. |
| `fecha_cierre` | DateTimeField | Null, Blank | Fecha de cierre administrativo. |
| `fecha_limite_respuesta` | DateTimeField | Null, Blank | Deadline para la primera respuesta (SLA). |
| `fecha_limite_resolucion` | DateTimeField | Null, Blank | Deadline para la resolución final (SLA). |
| `fecha_auto_cierre` | DateTimeField | Null, Blank | Fecha programada para cierre automático tras resolución. |
| `estado_sla` | CharField(30) | Choice | Estado SLA: en_tiempo, por_vencer, vencida, etc. |
| `sla_respuesta_notificado` | BooleanField | Default: False | Flag de notificación de vencimiento de respuesta. |
| `sla_resolucion_notificado` | BooleanField | Default: False | Flag de notificación de vencimiento de resolución. |
| `auto_cerrado` | BooleanField | Default: False | Indica si el ticket fue cerrado por el sistema. |
| `escalado` | BooleanField | Default: False | Indica si el ticket fue escalado a un nivel superior. |
| `documento_informe` | FileField | Null, Blank | Informe técnico en PDF (en `pdf_incidencias/`). |
| `fecha_creacion` | DateTimeField | Auto Add | Fecha y hora de registro. |

### Tabla: `Comentario` (tickets_comentario)
Hilo de comunicación y seguimiento para cada incidencia.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `incidencia` | ForeignKey | FK -> `Incidencia` | Ticket al que pertenece. |
| `usuario` | ForeignKey | FK -> `CustomUser` | Autor del comentario. |
| `tipo_comentario` | CharField(20) | Choice | tecnico, observacion, persiste, etc. |
| `texto` | TextField | Not Null | Contenido del mensaje. |
| `fecha_creacion` | DateTimeField | Auto Add | Fecha y hora del comentario. |
| `evidencia_adjunta` | ImageField | Null, Blank | Imagen opcional en el chat. |

### Tabla: `IncidenciaImagen` (tickets_incidenciaimagen)
Imágenes adicionales asociadas a una incidencia.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `incidencia` | ForeignKey | FK -> `Incidencia` | Incidencia propietaria de la imagen. |
| `imagen` | ImageField | Not Null | Archivo de imagen adicional. |
| `fecha_subida` | DateTimeField | Auto Add | Fecha y hora de carga. |

### Tabla: `Notificacion` (tickets_notificacion)
Eventos de notificación generados por cambios del sistema.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `incidencia` | ForeignKey | FK -> `Incidencia` (Null) | Incidencia relacionada, si aplica. |
| `mensaje` | TextField | Not Null | Texto de la notificación. |
| `tipo` | CharField(50) | Choice | asignacion, estado, comentario, nueva_incidencia, incidencia_resuelta, desasignacion. |
| `fecha_creacion` | DateTimeField | Auto Add | Fecha y hora del evento. |
| `link` | URLField(500) | Null, Blank | Enlace de destino asociado. |

### Tabla: `NotificacionUsuario` (tickets_notificacionusuario)
Tabla intermedia de entrega y lectura de notificaciones por usuario.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `usuario` | ForeignKey | FK -> `CustomUser` | Destinatario de la notificación. |
| `notificacion` | ForeignKey | FK -> `Notificacion` | Notificación recibida. |
| `leido` | BooleanField | Default: False | Indica si el usuario ya la leyó. |
| `fecha_recibida` | DateTimeField | Auto Add | Fecha y hora de recepción. |

### Tabla: `SLAConfiguracion` (tickets_slaconfiguracion)
Configuración de tiempos de respuesta y resolución por prioridad/categoría.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `prioridad` | CharField(20) | Choice | Prioridad a la que aplica el SLA. |
| `categoria` | CharField(20) | Choice, Null | Categoría específica (opcional). |
| `tiempo_respuesta_minutos` | PositiveIntegerField | Default: 240 | Minutos permitidos para responder. |
| `tiempo_resolucion_minutos` | PositiveIntegerField | Default: 1440 | Minutos permitidos para resolver. |
| `auto_cierre_horas` | PositiveIntegerField | Default: 72 | Horas para cierre automático tras resolución. |
| `activo` | BooleanField | Default: True | Estado de la configuración. |

*Nota: Existe una restricción de unicidad combinada para `prioridad` y `categoria`.*

### Tabla: `ReemplazoEquipoIncidencia` (tickets_reemplazoequipoincidencia)
Control de préstamos de equipos temporales durante incidencias.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `incidencia` | ForeignKey | FK -> `Incidencia` | Ticket que originó el reemplazo. |
| `equipo_original` | ForeignKey | FK -> `Equipo` | Equipo que está siendo reparado. |
| `equipo_reemplazo` | ForeignKey | FK -> `Equipo` | Equipo entregado temporalmente. |
| `area_origen` | ForeignKey | FK -> `Area` | Área de procedencia del equipo. |
| `area_destino` | ForeignKey | FK -> `Area` | Área donde se usará el equipo. |
| `usuario` | ForeignKey | FK -> `CustomUser` | Usuario responsable del registro. |
| `motivo` | TextField | Not Null | Justificación del reemplazo. |
| `fecha_inicio` | DateTimeField | Auto Add | Inicio del préstamo. |
| `fecha_fin` | DateTimeField | Null, Blank | Devolución del equipo. |
| `activo` | BooleanField | Default: True | Indica si el reemplazo sigue vigente. |
| `metadata` | JSONField | Default: {} | Datos técnicos adicionales. |

### Tabla: `MetricaDiaria` (tickets_metricadiaria)
Consolidado histórico de KPIs del sistema.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `fecha` | DateField | Unique | Día de la métrica. |
| `tickets_abiertos` | PositiveIntegerField | Default: 0 | Total de tickets abiertos ese día. |
| `tickets_cerrados` | PositiveIntegerField | Default: 0 | Total de tickets cerrados ese día. |
| `sla_vencidos` | PositiveIntegerField | Default: 0 | Total de tickets con SLA vencido. |
| `reemplazos_activos` | PositiveIntegerField | Default: 0 | Total de préstamos vigentes. |
| `metadata` | JSONField | Default: {} | KPIs secundarios (por área, técnico, etc). |
| `creado_en` | DateTimeField | Auto Add | Registro de creación. |
| `actualizado_en` | DateTimeField | Auto Now | Última actualización del KPI. |

*Nota: Existe una restricción de unicidad combinada para `usuario` y `notificacion`.*

---

## 2. Aplicación: `inventario` (Gestión de Activos)

### Tabla: `EstadoEquipo` (inventario_estadoequipo)
Catálogo maestro de estados operativos de los equipos.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `nombre` | CharField(50) | Unique, Not Null | Estado operativo del equipo. |

*Valores base actuales: `Operativo`, `Observación`, `En revisión`, `En reparación`, `Inoperativo`, `Dado de baja`.*

### Tabla: `Marca` (inventario_marca)
Catálogo de fabricantes de equipos.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `nombre` | CharField(100) | Unique, Not Null | Nombre de la marca (ej. HP, Dell). |

### Tabla: `TipoEquipo` (inventario_tipoequipo)
Categorías de activos tecnológicos.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `nombre` | CharField(100) | Unique, Not Null | Tipo de hardware (ej. Laptop, Servidor). |

### Tabla: `Equipo` (inventario_equipo)
Registro de hardware y activos tecnológicos.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `codigo_equipo` | CharField(50) | Unique | Código patrimonial o interno. |
| `nombre_equipo` | CharField(100) | Not Null | Nombre descriptivo (ej. PC-UPDI-01). |
| `tipo_equipo` | ForeignKey | FK -> `TipoEquipo` | Categoría (PC, Laptop, Impresora). |
| `marca` | ForeignKey | FK -> `Marca` | Marca del fabricante. |
| `modelo` | CharField(50) | Not Null | Modelo específico. |
| `numero_serie` | CharField(100) | Null, Blank | S/N de fábrica. |
| `observaciones` | TextField | Null, Blank | Descripción física, estética o accesorios del equipo. |
| `fecha_register` | DateTimeField | Auto Add | Fecha y hora de registro del activo. |
| `actualizado_en` | DateTimeField | Auto Now | Fecha y hora de última actualización. |
| `activo` | BooleanField | Default: True | Control lógico para activos o bajas administrativas. |
| `disponibilidad` | CharField(30) | Choice | Estado: `LIBRE`, `EN_USO`, `REEMPLAZO_TEMPORAL`. |
| `origen_ocupacion` | CharField(20) | Choice | Manual, Incidencia, Reemplazo, etc. |
| `foto_estado` | ImageField | Null, Blank | Evidencia fotográfica del estado del equipo. |
| `area` | ForeignKey | FK -> `Area` (Set Null) | Ubicación física actual. |
| `estado` | ForeignKey | FK -> `EstadoEquipo` | Estado funcional (Inventario). |
| `estado_tecnico` | ForeignKey | FK -> `EstadoEquipo` | Estado técnico detallado. |
| `ficha_tecnica` | FileField | Null, Blank | Manual o ficha en PDF (en `inventario_docs/`). |

### Tabla: `HistorialEstadoEquipo` (inventario_historialestadoequipo)
Bitácora de cambios de estado operativo por equipo.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `equipo` | ForeignKey | FK -> `Equipo` | Equipo afectado por el cambio. |
| `estado_anterior` | ForeignKey | FK -> `EstadoEquipo` | Estado previo del equipo. |
| `estado_nuevo` | ForeignKey | FK -> `EstadoEquipo` | Estado posterior al cambio. |
| `usuario_que_cambio` | ForeignKey | FK -> `CustomUser` | Usuario que registró el cambio. |
| `observacion` | TextField | Not Null | Justificación del cambio de estado. |
| `fecha_registro` | DateTimeField | Auto Add | Momento exacto del cambio. |

---

## 3. Aplicación: `auditoria` (Trazabilidad)

### Tabla: `Auditoria` (auditoria_auditoria)
Logs de acciones críticas para seguridad y cumplimiento.

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `usuario` | ForeignKey | FK -> `CustomUser` | Quién realizó la acción. |
| `modulo` | CharField(50) | Choice | Usuarios, Inventario, Incidencias. |
| `accion` | CharField(100) | Not Null | Verbo de la acción (ej. Creó, Editó). |
| `descripcion` | TextField | Not Null | Detalle legible de la actividad. |
| `evento` | CharField(100) | Null | Identificador del tipo de evento técnico. |
| `version_evento` | PositiveIntegerField | Default: 1 | Versión del esquema del evento. |
| `hash_evento` | CharField(64) | Unique | Hash para evitar duplicidad de registros. |
| `metadata` | JSONField | Default: {} | Datos crudos del objeto auditado. |
| `fecha_hora` | DateTimeField | Auto Add | Momento exacto del evento auditado. |
| `referencia_id` | IntegerField | Null | ID del objeto afectado. |
| `ip` | GenericIPAddress | Null | Dirección IP de origen. |

*Nota: Existe una restricción de unicidad para `evento` y `hash_evento` para evitar duplicados.*

### Tabla: `EventoFallido` (auditoria_eventofallido)
Registro de auditorías que fallaron al procesarse (asíncronas).

| Campo | Tipo | Restricciones | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | PK | Identificador único. |
| `evento` | CharField(100) | Not Null | Nombre del evento fallido. |
| `payload` | JSONField | Default: {} | Datos que no pudieron guardarse. |
| `error` | TextField | Not Null | Mensaje de excepción. |
| `intentos` | PositiveSmallIntegerField| Default: 0 | Veces que se intentó re-procesar. |
| `procesado` | BooleanField | Default: False | Indica si ya se recuperó con éxito. |
| `fecha` | DateTimeField | Auto Add | Fecha del fallo original. |

---

## 4. Análisis de Escalabilidad y Futuras Implementaciones

Tras analizar el esquema actual frente a los requerimientos futuros, se concluye lo siguiente:

### A. Gestión de Inventario (Excel)
*   **Estado**: **Implementado**.
*   **Análisis**: Se ha integrado un motor de exportación basado en `openpyxl` que permite generar reportes detallados del inventario en formato `.xlsx`, incluyendo datos de áreas, marcas y estados operativos.

### B. Gestión de Documentos (PDF)
*   **Estado**: **Implementado**.
*   **Análisis**: El sistema ya soporta la carga de documentos PDF mediante campos `FileField` en las tablas `Incidencia` (`documento_informe`) y `Equipo` (`ficha_tecnica`), permitiendo adjuntar informes técnicos y manuales de fabricante respectivamente.

### C. Despliegue en Docker
*   **Estado**: **Soportado**.
*   **Análisis**: El esquema utiliza relaciones estándar de Django y no depende de funciones específicas de motor que impidan la contenedorización. Es compatible con PostgreSQL y MariaDB en entornos Docker.

### D. Recomendaciones de Integridad
*   Se observa que el campo `codigo` de la incidencia se genera tras el primer guardado. Para escalabilidad masiva, se recomienda asegurar la atomicidad de este proceso mediante transacciones si se migra a un entorno de alta concurrencia.
