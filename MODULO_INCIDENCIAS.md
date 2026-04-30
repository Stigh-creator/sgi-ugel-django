# 📋 Módulo de Incidencias - Documentación Completa

## Tabla de Contenidos
1. [Introducción](#introducción)
2. [Estructura de Modelos](#estructura-de-modelos)
3. [Roles y Permisos](#roles-y-permisos)
4. [Funcionalidades por Rol](#funcionalidades-por-rol)
5. [Flujos de Trabajo](#flujos-de-trabajo)
6. [Formularios y Validaciones](#formularios-y-validaciones)
7. [URLs y Rutas](#urls-y-rutas)
8. [Servicios y Lógica](#servicios-y-lógica)
9. [Notificaciones](#notificaciones)
10. [Reportes PDF](#reportes-pdf)
11. [Casos de Uso](#casos-de-uso)
12. [Diagramas](#diagramas)

---

## Introducción

El módulo de incidencias es el core del sistema de gestión de soporte técnico. Permite que trabajadores reporten problemas, técnicos resuelvan tickets y administradores supervisen toda la operación. El sistema cuenta con:

- ✅ Sistema de roles con permisos diferenciados
- ✅ Flujos de estado automáticos e intuitivos
- ✅ Notificaciones en tiempo real (WebSocket)
- ✅ Generación de reportes en PDF
- ✅ Búsqueda y filtrado avanzado
- ✅ Procesamiento automático de imágenes
- ✅ Seguimiento de presencia online

---

## Estructura de Modelos

### 📋 Modelo Incidencia

Entidad central que representa un ticket de soporte.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `creador` | ForeignKey(CustomUser) | Persona que reporta el problema |
| `area` | ForeignKey(Area) | Departamento afectado |
| `categoria` | CharField | Hardware, Software, Red, Sistema |
| `prioridad` | CharField | Baja, Media, Alta, Crítica |
| `descripcion` | TextField | Detalle del problema reportado |
| `imagen_adjunta` | ImageField | Evidencia visual (JPG/PNG, max 2MB) |
| `estado` | ForeignKey(Estado) | Pendiente → En Proceso → Resuelto → Cerrado |
| `tecnico_asignado` | ForeignKey(CustomUser, null=True) | Técnico responsable |
| `fecha_programada_atencion` | DateField | Fecha estimada de resolución |
| `observaciones_internas` | TextField | Notas privadas (solo técnico/admin) |
| `solucion_aplicada` | TextField | Descripción de la solución |
| `evidencia_solucion` | ImageField | Comprobante de la solución |
| `fecha_creacion` | DateTimeField | Cuándo se creó |
| `fecha_cierre` | DateTimeField | Cuándo se cerró |

**Propiedades Especiales:**
```python
@property
puede_cerrar()      # True si estado es "Resuelto"

@property
esta_asignada()     # True si hay tecnico_asignado
```

**Procesamiento Automático:**
- Redimensiona imágenes adjuntas a 1024x1024px
- Comprime en formato JPG con quality=70
- Genera thumbnails automáticamente

---

### 👤 Modelo CustomUser

Extensión personalizada del modelo User de Django.

**Campos Base (heredados de AbstractUser):**
- `username`, `email`, `first_name`, `last_name`, `password`

**Campos Adicionales:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `role` | CharField | usuario / tecnico / administrador |
| `area` | ForeignKey(Area) | Departamento del usuario |
| `telefono` | CharField | Contacto directo |
| `foto` | ImageField | Foto de perfil (redimensionada 256x256) |
| `must_change_password` | BooleanField | Fuerza cambio en primer login |
| `last_seen` | DateTimeField | Última actividad |

**Propiedades:**
```python
@property
is_online()         # True si last_seen < 2 minutos
                    # Retorna formato: "Ahora", "Hace 5 min", "Hace 2 h"

@property
es_tecnico()        # True si role == "tecnico"

@property
es_admin()          # True si role == "administrador"

@property
es_usuario()        # True si role == "usuario"
```

**Roles del Sistema:**
- **usuario** (Trabajador): Reporta problemas
- **tecnico**: Resuelve incidencias
- **administrador**: Supervisa y gestiona todo

---

### 🔔 Modelo Notificacion

Sistema de notificaciones automáticas.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `tipo` | CharField | asignacion, estado, comentario, nueva_incidencia, incidencia_resuelta, desasignacion |
| `mensaje` | TextField | Texto de la notificación |
| `incidencia` | ForeignKey(Incidencia) | Ticket relacionado |
| `usuario_origen` | ForeignKey(CustomUser) | Quién genera la notificación |
| `fecha_creacion` | DateTimeField | Cuándo se envió |

**Relación Intermedia - NotificacionUsuario:**
```python
usuario         # Receptor de la notificación
notificacion    # La notificación
leido           # Boolean (marcada como leída)
```

---

### 💬 Modelo Comentario

Historial de comunicación en cada incidencia.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `incidencia` | ForeignKey(Incidencia) | Ticket comentado |
| `autor` | ForeignKey(CustomUser) | Quién comenta |
| `tipo` | CharField | tecnico, confirmacion, persiste, observacion |
| `contenido` | TextField | Texto del comentario |
| `fecha_creacion` | DateTimeField | Cuándo se comentó |

**Tipos de Comentarios:**
- **tecnico**: Aportación técnica del soporte
- **confirmacion**: Confirmación de solución por trabajador
- **persiste**: Usuario reporta que problema continúa
- **observacion**: Notas internas del equipo

---

## Roles y Permisos

### 👷 TRABAJADOR (rol: usuario)

**Qué puede hacer:**
- ✅ Crear incidencias
- ✅ Ver sus propias incidencias
- ✅ Agregar comentarios
- ✅ Cerrar incidencias resueltas
- ✅ Reabrirlas si el problema persiste
- ✅ Actualizar su perfil

**Restricciones:**
- ❌ No ve incidencias de otros
- ❌ Área auto-completada (no puede cambiar)
- ❌ No puede asignar técnicos
- ❌ No puede acceder a dashboards

---

### 🔧 TÉCNICO (rol: tecnico)

**Qué puede hacer:**
- ✅ Ver incidencias asignadas
- ✅ Agregar comentarios técnicos
- ✅ Resolver incidencias
- ✅ Subir evidencia de solución
- ✅ Ver dashboard técnico (KPIs)
- ✅ Exportar reporte de asignadas a PDF

**Restricciones:**
- ❌ Solo ve incidencias asignadas a él
- ❌ No puede asignar a otros técnicos
- ❌ No puede crear incidencias directamente
- ❌ No puede cambiar estado manualmente

---

### 👨‍💼 ADMINISTRADOR (rol: administrador)

**Qué puede hacer:**
- ✅ Ver TODAS las incidencias
- ✅ Crear incidencias
- ✅ Asignar técnicos
- ✅ Cambiar estados manualmente
- ✅ Editar incidencias existentes
- ✅ Crear y gestionar usuarios
- ✅ Ver dashboard admin (estadísticas globales)
- ✅ Exportar reportes filtrados en PDF
- ✅ Aplicar filtros avanzados

**Restricciones:**
- ❌ No puede modificar datos originales (descripción, categoría, etc.)
- ❌ Una vez resuelta/cerrada, no puede cambiar campos técnicos

---

## Funcionalidades por Rol

### 👷 TRABAJADOR

#### 1. Crear Incidencia
**Ruta:** `POST /incidencias/crear/`

**Campos disponibles:**
```python
categoria               # Select: Hardware, Software, Red, Sistema
prioridad              # Select: Baja, Media, Alta, Crítica
area                   # Select: Filtrado por user.area (DISABLED)
descripcion            # TextField: Mínimo 10 caracteres
imagen_adjunta         # ImageField: JPG/PNG, máximo 2MB
```

**Proceso:**
1. Accede a Crear Incidencia
2. Rellena categoría, prioridad, descripción e imagen (opcional)
3. Área se auto-completa con su departamento
4. Guarda y sistema crea ticket en estado "Pendiente"
5. Recibe notificación de creación

**Respuesta del sistema:**
```
Estado: Pendiente
Asignado a: Sin técnico
Notificación: "Su incidencia #NNNN ha sido creada"
```

---

#### 2. Ver Mis Incidencias
**Ruta:** `GET /incidencias/mis-incidencias/`

**Filtros disponibles:**
- Búsqueda: ID, descripción
- Estado específico
- Prioridad específica
- Rango de fechas

**Columnas mostradas:**
- ID, Descripción, Categoría, Prioridad, Estado, Fecha Creación

---

#### 3. Ver Detalle de Incidencia
**Ruta:** `GET /incidencias/<id>/`

**Información visible:**
- Datos completos del ticket
- Descripción y categoría
- Prioridad y estado actual
- Técnico asignado (si aplica)
- Solución aplicada (si existe)
- Evidencia de solución (imagen)
- Historial de comentarios
- Fecha programada de atención

**Acciones disponibles:**
```python
if estado == "Resuelto":
    - Botón "Cerrar y Confirmar" ✓
    - Botón "Reabrir" (si persiste)
    
if estado == "Cerrado":
    - Ver detalles (sin acciones)
```

---

#### 4. Cerrar Incidencia
**Ruta:** `POST /incidencias/<id>/cerrar/`

**Requisitos:**
- Estado debe ser "Resuelto"
- Solo el creador puede cerrar
- Puede agregar comentario de confirmación

**Proceso:**
1. Sistema cambia estado a "Cerrado"
2. Registra fecha/hora de cierre
3. Crea comentario automático de confirmación
4. Notifica al técnico que resolvió

---

#### 5. Reabrir Incidencia
**Ruta:** `POST /incidencias/<id>/reabrir/`

**Requisitos:**
- Incidencia debe estar en "Resuelto" o "Cerrado"
- Debe existir comentario de "persiste"

**Proceso:**
1. Estado vuelve a "En Proceso"
2. Se notifica al técnico original
3. Se registra comentario de reapertura

---

### 🔧 TÉCNICO

#### 1. Dashboard Técnico
**Ruta:** `GET /dashboard/tecnico/`

**KPIs mostrados:**
```python
Total Histórico Asignado    # Todos los tickets asignados
Críticas Sin Finalizar      # Alta/Crítica no cerradas
Resueltas + Cerradas        # Total éxito
Últimas de Hoy              # Asignadas hoy
```

**Gráficos:**
- Distribución por estado (últimos 30 días)
- Tendencia de asignaciones

---

#### 2. Ver Incidencias Asignadas
**Ruta:** `GET /incidencias/asignadas/`

**Filtros disponibles:**
- Asignadas a mí
- Reportadas por mí
- Búsqueda por ID/descripción
- Estado específico
- Prioridad específica

**Columnas:**
- ID, Descripción, Reportado por, Prioridad, Estado, Fecha

---

#### 3. Ver Detalle de Incidencia
**Ruta:** `GET /incidencias/<id>/`

**Acciones técnicas disponibles:**
- Agregar comentario técnico
- Ver observaciones internas (privadas)
- Ver solución aplicada (si existe)
- Cambiar observaciones internas

```python
if estado == "En Proceso" OR "Pendiente":
    - Botón "Resolver Incidencia"
    
if estado == "Resuelto":
    - Botón "Editar Solución"
    - Vista de evidencia
```

---

#### 4. Resolver Incidencia
**Ruta:** `POST /incidencias/<id>/resolver/`

**Campos requeridos:**
```python
solucion_aplicada       # TextField: Mínimo 10 caracteres
evidencia_solucion      # ImageField: Opcional (JPG/PNG, 2MB max)
```

**Validaciones:**
- Solución mínimo 10 caracteres
- Si hay imagen, debe ser JPG o PNG
- Imagen máximo 2MB

**Proceso (Servicio):**
1. Sistema cambia estado a "Resuelto"
2. Guarda solución + evidencia
3. Crea comentario tipo 'confirmacion'
4. Dispara notificación al creador
5. Descuenta de su contador de "Sin Resolver"

**Respuesta:**
```
Título: "Incidencia #NNNN resuelta"
Descripción: Redirige a ver incidencia
Notificación enviada a creador: 
  "Tu incidencia #NNNN ha sido resuelta"
```

---

#### 5. Exportar Incidencias a PDF
**Ruta:** `GET /incidencias/reporte-asignadas/pdf/`

**Contenido del reporte:**
- Listado de incidencias asignadas al técnico
- Total de resueltas/cerradas
- Por estado
- Tabla con detalles de cada ticket
- Fecha de generación

---

### 👨‍💼 ADMINISTRADOR

#### 1. Dashboard Admin
**Ruta:** `GET /dashboard/`

**KPIs mostrados:**
```python
Críticas Pendientes     # Alta/Crítica no resueltas
Pendientes En Proceso   # Pendiente + En Proceso
Resueltas              # Estado Resuelto
Cerradas               # Estado Cerrado
De Hoy                 # Creadas hoy
```

**Gráficos:**
- Distribución por estado (todo el sistema)
- Distribución por área
- Tendencias (últimos 30 días)

---

#### 2. Ver Todas las Incidencias
**Ruta:** `GET /incidencias/admin/`

**Filtros avanzados:**

**Búsqueda:**
- Por ID del ticket
- Por descripción
- Por usuario creador
- Por técnico asignado
- Por área

**Ordenamiento:**
- Por ID (ascendente/descendente)
- Por descripción
- Por área
- Por prioridad
- Por estado
- Por fecha creación

**Filtros específicos:**
- Estado: Pendiente, En Proceso, Resuelto, Cerrado
- Prioridad: Baja, Media, Alta, Crítica
- Asignación:
  - Mis asignadas (técnico soy yo)
  - Sin asignar
  - Ya asignadas
- Urgentes (Alta/Crítica sin resolver)

**Columnas visibles:**
- ID, Descripción, Usuario, Técnico, Área, Prioridad, Estado, Fecha

---

#### 3. Crear Incidencia
**Ruta:** `POST /incidencias/crear/`

**Campos completos:**
```python
categoria                       # Select: Hardware, Software, Red, Sistema
prioridad                      # Select: Baja, Media, Alta, Crítica
area                          # Select: Todas las áreas disponibles
descripcion                   # TextField: Detalle completo
imagen_adjunta                # ImageField: Evidencia (opcional)
tecnico_asignado              # Select: Técnico responsable (opcional)
fecha_programada_atencion     # DateField: Estimación
hora_programada_atencion      # TimeField: Hora específica
observaciones_internas        # TextField: Notas privadas
```

**Particularidades:**
- Admin puede seleccionar cualquier área
- Puede asignar técnico directamente
- Si asigna técnico: estado automático → "En Proceso"

---

#### 4. Gestionar Incidencia
**Ruta:** `POST /incidencia/<id>/gestionar/`

**Campos editables:**
```python
tecnico_asignado              # Select: Cambiar asignación
fecha_programada_atencion     # DateField: Reprogramar
hora_programada_atencion      # TimeField: Nueva hora
observaciones_internas        # TextField: Agregar notas
estado                        # Select: Cambiar estado manualmente
```

**Campos NO editables (Bloqueados):**
- `categoria` - No puede cambiar tipo de incidencia
- `prioridad` - Fija la prioridad original
- `area` - No puede cambiar departamento
- `descripcion` - Protege descripción original
- `imagen_adjunta` - No puede cambiar evidencia original

**Bloqueos por estado:**
```python
if estado IN ["Resuelto", "Cerrado"]:
    # Todos los campos técnicos se bloquean
    tecnico_asignado = DISABLED
    estado = DISABLED
    observaciones = READONLY
```

**Lógica automática:**
```python
if admin_asigna_tecnico AND estado IN ["Pendiente", "Asignado"]:
    estado → "En Proceso" (automático)
```

---

#### 5. Crear Usuario
**Ruta:** `POST /usuarios/crear/`

**Campos requeridos:**
```python
dni                     # CharField: Único en el sistema
username                # CharField: Único, auto-generado o manual
email                   # EmailField: Único
first_name              # CharField: Nombre
last_name               # CharField: Apellido
role                    # Select: usuario, tecnico, administrador
area                    # ForeignKey: Departamento
telefono                # CharField: Contacto (opcional)
```

**Proceso:**
1. Admin rellena formulario
2. Sistema genera contraseña inicial: `Ugel@XXXX` (últimos 4 dígitos DNI)
3. Flag `must_change_password = True`
4. Usuario recibe notificación de creación
5. En primer login: Obligado a cambiar contraseña

---

#### 6. Editar Usuario
**Ruta:** `POST /usuarios/<id>/editar/`

**Campos editables:**
```python
email, first_name, last_name, role, area, telefono
```

**Acciones disponibles:**
- Cambiar rol
- Cambiar área
- Actualizar contacto
- Reset de contraseña (envía nueva: Ugel@XXXX)
- Activar/Desactivar cuenta

---

#### 7. Exportar Incidencias a PDF
**Ruta:** `GET /incidencias/informe-general/pdf/`

**Filtros aplicables:**
```python
fecha_inicio, fecha_fin     # Rango de fechas
dia_especifico              # Día exacto
mes_picker                  # Formato YYYY-MM
estado_especifico           # Filtrar por estado
tecnico_asignado            # Filtrar por técnico
usuario_creador             # Filtrar por reportante
```

**Contenido del reporte:**
- Total de incidencias (filtrado)
- Distribuidas por estado
- Distribuidas por área
- Críticas encontradas
- Tabla con detalles completos
- Gráficos de distribución
- Fecha y hora de generación

**Formatos:**
```
Título: "Informe de Incidencias [Rango de fechas]"
Encabezado: Logo, fecha de generación
Footer: "Página X de Y"
Datos: Tabla con todas las incidencias
```

---

## Flujos de Trabajo

### 🔄 Flujo Estándar: De Problema a Solución

```
1. TRABAJADOR REPORTA
   └─ Accede a "Crear Incidencia"
   └─ Rellena: Categoría, Prioridad, Descripción, Imagen
   └─ Sistema → Estado: "Pendiente"
   └─ NOTIFICACIÓN: Admin/Técnico notificados

2. ADMIN ASIGNA TÉCNICO
   └─ Accede a "Ver Todas las Incidencias"
   └─ Abre incidencia Pendiente
   └─ Selecciona técnico y programa atención
   └─ Sistema → Estado: "En Proceso" (automático)
   └─ NOTIFICACIÓN: Técnico notificado de asignación

3. TÉCNICO RESUELVE
   └─ Ve incidencia en "Incidencias Asignadas"
   └─ Agrega comentarios técnicos
   └─ Haz click en "Resolver"
   └─ Rellena: Solución (10+ caracteres) + Evidencia (opcional)
   └─ Sistema → Estado: "Resuelto"
   └─ NOTIFICACIÓN: Trabajador notificado de resolución

4. TRABAJADOR CONFIRMA
   └─ Recibe notificación "Incidencia Resuelta"
   └─ Accede al ticket
   └─ Verifica solución y evidencia
   
   OPCIÓN A: Conforme
   └─ Click en "Cerrar y Confirmar"
   └─ Sistema → Estado: "Cerrado"
   └─ NOTIFICACIÓN: Técnico notificado de cierre
   
   OPCIÓN B: Problema persiste
   └─ Click en "Reabrir"
   └─ Comenta "El problema persiste"
   └─ Sistema → Estado: "En Proceso"
   └─ NOTIFICACIÓN: Técnico notificado de reapertura
```

### 🚨 Flujo Urgente: Admin Asigna sin Reportante

```
1. ADMIN CREA DIRECTAMENTE
   └─ Accede a "Crear Incidencia"
   └─ Rellena todos los campos
   └─ Selecciona Técnico y Área
   └─ Sistema → Estado: "En Proceso" (automático)
   └─ NOTIFICACIÓN: Técnico notificado

2. (Continúa desde paso 3 del flujo estándar)
```

### 📊 Transiciones de Estado

```
Pendiente
    ↓
    └─→ [Admin asigna] → En Proceso
    
En Proceso
    ├─→ [Técnico resuelve] → Resuelto
    └─→ [Trabajador reporta persiste] → En Proceso (re-asignación)
    
Resuelto
    ├─→ [Trabajador cierra] → Cerrado
    └─→ [Trabajador reporta persiste] → En Proceso
    
Cerrado
    └─→ [Final - No hay transiciones]
```

---

## Formularios y Validaciones

### 📝 IncidenciaForm (Trabajador)

**Campos:**
```python
categoria               # CharField
prioridad              # CharField
area                   # ModelChoiceField (DISABLED)
descripcion            # TextField
imagen_adjunta         # ImageField
```

**Lógica especial:**
```python
# En __init__()
area.queryset = Area.objects.filter(id=user.area.id)
area.disabled = True  # Trabajador no puede cambiar

# En clean()
validar_imagen_size()  # Máximo 2MB
validar_imagen_type()  # JPG o PNG
```

**Validaciones:**
- `descripcion`: Mínimo 10 caracteres
- `imagen_adjunta`: JPG/PNG, máximo 2MB
- Campos requeridos: categoría, prioridad, área, descripción

---

### 📝 IncidenciaAdminForm (Administrador)

**Campos:**
```python
categoria                       # CharField (DISABLED)
prioridad                      # CharField (DISABLED)
area                          # ModelChoiceField (DISABLED)
descripcion                   # TextField (DISABLED)
imagen_adjunta                # ImageField (DISABLED)
tecnico_asignado              # ModelChoiceField
fecha_programada_atencion     # DateField
hora_programada_atencion      # TimeField
observaciones_internas        # TextField
estado                        # ModelChoiceField (oculto en creación)
```

**Lógica especial:**
```python
# Campos originales bloqueados (READ-ONLY)
categoria.disabled = True
prioridad.disabled = True
area.disabled = True
descripcion.disabled = True
imagen_adjunta.disabled = True

# Si estado es Resuelto o Cerrado
if estado IN ["Resuelto", "Cerrado"]:
    tecnico_asignado.disabled = True
    estado.disabled = True
    
# En creación nueva
if not incidencia.id:
    estado.widget = HiddenInput()  # Campo invisible
```

---

### 📝 SolucionForm (Técnico)

**Campos:**
```python
solucion_aplicada       # TextField
evidencia_solucion      # ImageField
```

**Validaciones:**
```python
# solucion_aplicada
- Mínimo 10 caracteres
- Máximo 2000 caracteres
- No puede estar vacío

# evidencia_solucion
- Opcional (null=True)
- Si existe: JPG o PNG
- Máximo 2MB
- Auto-redimensiona a 1024x1024
```

---

### 🔐 Validaciones de Seguridad General

#### Contraseña (Cambio requerido)
```python
Requisitos:
  ✓ Mínimo 10 caracteres
  ✓ Al menos 1 letra mayúscula (A-Z)
  ✓ Al menos 1 letra minúscula (a-z)
  ✓ Al menos 1 número (0-9)
  ✓ Al menos 1 carácter especial (@#$%^&+=.!*?)

Ejemplo válido: Ugel@2025
Ejemplo inválido: 1234567890 (sin especial)
```

#### Imágenes
```python
Formatos permitidos: JPG, PNG, JPEG
Tamaño máximo: 2MB
Ancho: Auto-redimensiona a 1024x1024px
Compresión: Quality=70
```

---

## URLs y Rutas

### 🔐 Autenticación
```
GET/POST  /login/                    → Login
GET       /logout/                   → Logout
GET/POST  /cambio-obligatorio/       → Cambio forzado contraseña
POST      /cambio-obligatorio/       → Procesar cambio
```

### 📊 Dashboards
```
GET  /dashboard/                     → Dashboard Admin
GET  /dashboard/tecnico/             → Dashboard Técnico
GET  /mi-perfil/                     → Perfil del Usuario Actual
POST /mi-perfil/update-photo/        → Actualizar foto (AJAX)
```

### 📋 Gestión de Incidencias
```
GET       /incidencias/admin/                → Listar todas (Admin)
GET       /incidencias/asignadas/            → Técnico: sus asignadas
GET       /incidencias/mis-incidencias/      → Trabajador: las suyas
GET/POST  /incidencias/crear/                → Crear nueva incidencia
GET       /incidencias/<id>/                 → Ver detalle
POST      /incidencias/<id>/resolver/        → Técnico resuelve
POST      /incidencias/<id>/cerrar/          → Trabajador cierra
POST      /incidencias/<id>/reabrir/         → Reabre si persiste
GET/POST  /incidencia/<id>/gestionar/        → Admin edita completa
```

### 👥 Gestión de Usuarios
```
GET       /usuarios/                         → Listar usuarios (Admin)
GET/POST  /usuarios/crear/                   → Crear usuario (Admin)
GET/POST  /usuarios/<id>/editar/             → Editar usuario (Admin)
POST      /usuarios/<id>/toggle-status/      → Activar/desactivar
POST      /usuarios/<id>/reset-password/     → Resetear contraseña
```

### 🔔 Notificaciones (HTMX/AJAX)
```
GET  /notifications/unread_count/    → Contar no leídas
GET  /notifications/list/            → Listar últimas 10
POST /notificaciones/marcar-todas/   → Marcar como leídas
POST /notificaciones/ir/<id>/        → Ir a notificación
```

### 📄 Reportes PDF
```
GET  /incidencias/informe-general/pdf/      → Reporte general (Admin)
GET  /incidencia/<id>/pdf/                  → Detalle ticket (todos)
GET  /incidencias/reporte-asignadas/pdf/    → Técnico: sus asignadas
```

---

## Servicios y Lógica

### 🔧 resolver_incidencia_service()

**Ubicación:** `tickets/services.py`

**Firma:**
```python
def resolver_incidencia_service(incidencia, tecnico, solucion_aplicada, evidencia=None):
    """
    Resuelve una incidencia aplicando solución y evidencia
    """
```

**Parámetros:**
```python
incidencia: Incidencia          # Objeto de incidencia a resolver
tecnico: CustomUser             # Técnico que resuelve
solucion_aplicada: str          # Texto de solución (10+ caracteres)
evidencia: File (opcional)      # Imagen de comprobante
```

**Acciones ejecutadas:**
1. Valida que `solucion_aplicada` sea válida (mínimo 10 caracteres)
2. Cambia `incidencia.estado` → "Resuelto"
3. Guarda `solucion_aplicada` y `evidencia_solucion`
4. Crea `Comentario` tipo 'confirmacion' automáticamente
5. Procesa imagen (redimensiona, comprime)
6. Genera `Notificacion` para el creador de la incidencia
7. Guarda cambios en BD

**Retorna:**
```python
{
    'success': True,
    'mensaje': 'Incidencia resuelta exitosamente',
    'incidencia_id': 123
}
```

**Excepciones:**
```python
ValueError: Si solucion_aplicada tiene < 10 caracteres
```

---

### 🔧 cerrar_incidencia_service()

**Ubicación:** `tickets/services.py`

**Firma:**
```python
def cerrar_incidencia_service(incidencia, usuario_que_cierra):
    """
    Cierra una incidencia después de verificar resolución
    """
```

**Parámetros:**
```python
incidencia: Incidencia          # Incidencia a cerrar
usuario_que_cierra: CustomUser  # Trabajador que cierra
```

**Validaciones previas:**
```python
if incidencia.estado != "Resuelto":
    raise PermissionError("Solo puedo cerrar incidencias Resueltas")

if incidencia.creador != usuario_que_cierra:
    raise PermissionError("Solo el creador puede cerrar su incidencia")
```

**Acciones ejecutadas:**
1. Cambia `incidencia.estado` → "Cerrado"
2. Registra `fecha_cierre` = datetime.now()
3. Crea `Comentario` tipo 'confirmacion' con texto estándar
4. Genera `Notificacion` para el técnico asignado
5. Actualiza estadísticas del técnico
6. Guarda cambios en BD

**Retorna:**
```python
{
    'success': True,
    'mensaje': 'Incidencia cerrada exitosamente',
    'fecha_cierre': '2025-04-22 10:30:00'
}
```

---

### 🔧 crear_notificacion_service()

**Ubicación:** `tickets/services.py`

**Firma:**
```python
def crear_notificacion_service(tipo, mensaje, incidencia, usuario_origen, destinatarios):
    """
    Crea notificación y la envía a destinatarios
    """
```

**Tipos de notificación:**
```python
'asignacion'           # Técnico asignado
'estado'              # Estado cambió
'comentario'          # Nuevo comentario
'nueva_incidencia'    # Nueva incidencia creada
'incidencia_resuelta' # Técnico resolvió
'desasignacion'       # Técnico desasignado
```

**Proceso:**
1. Crea registro en `Notificacion`
2. Para cada destinatario, crea `NotificacionUsuario`
3. Envía vía WebSocket (si está conectado)
4. Guarda en BD (para sincronización posterior)

---

## Notificaciones

### 🔔 Sistema en Tiempo Real (WebSocket)

**Tecnología:** Django Channels

**Activación automática:**

```python
# Cuando se asigna técnico
@receiver(post_save, sender=Incidencia)
def notificar_asignacion_tecnico(sender, instance, created=False, **kwargs):
    if instance.tecnico_asignado:
        crear_notificacion_service(
            tipo='asignacion',
            mensaje=f'Te han asignado la incidencia #{instance.id}',
            incidencia=instance,
            usuario_origen=instance.creador,
            destinatarios=[instance.tecnico_asignado]
        )

# Cuando se resuelve
def resolver_incidencia_service(...):
    # ... código ...
    crear_notificacion_service(
        tipo='incidencia_resuelta',
        mensaje=f'Tu incidencia #{incidencia.id} ha sido resuelta',
        incidencia=incidencia,
        usuario_origen=tecnico,
        destinatarios=[incidencia.creador]
    )
```

### 🔴 Estados de Notificación

```python
# NotificacionUsuario
leido: Boolean          # False (nueva) → True (leída)
fecha_lectura: DateTime # Cuándo se marcó como leída

# Contador en interfaz
unread_count            # AJAX actualiza en tiempo real
```

### 📬 Acciones con Notificaciones

```
GET  /notifications/unread_count/    → {"count": 5}
GET  /notifications/list/            → Lista últimas 10
POST /notificaciones/marcar-todas/   → Marca todas como leídas
POST /notificaciones/ir/<id>/        → Ir a la incidencia + marcar leída
```

---

## Reportes PDF

### 📊 Arquitectura de PDFs

**Librería:** WeasyPrint (para renderizado profesional)

**Plantillas:** Django Templates + CSS personalizado

---

### 📄 Tipo 1: Reporte General (Admin)

**Ruta:** `GET /incidencias/informe-general/pdf/`

**Filtros aplicables:**
```python
fecha_inicio: Date           # Desde
fecha_fin: Date              # Hasta
dia_especifico: Date         # Día exacto
mes_picker: CharField        # Formato YYYY-MM
estado_especifico: Choice    # Pendiente/En Proceso/Resuelto/Cerrado
tecnico_asignado: FK         # Técnico específico
usuario_creador: FK          # Reportante específico
```

**Contenido del documento:**

```
┌─ ENCABEZADO ──────────────────────────────────────┐
│  Logo de la Empresa                                │
│  Título: "Informe de Incidencias [Rango de fechas]"│
│  Fecha de generación: DD/MM/YYYY HH:MM:SS          │
└────────────────────────────────────────────────────┘

┌─ SECCIÓN DE ESTADÍSTICAS ──────────────────────────┐
│  Total de incidencias: 45                          │
│  Por estado:                                       │
│    - Pendiente: 5        (11%)                     │
│    - En Proceso: 10      (22%)                     │
│    - Resuelto: 20        (44%)                     │
│    - Cerrado: 10         (22%)                     │
│                                                    │
│  Críticas encontradas: 3 (Alta/Crítica)            │
│  Por prioridad:                                    │
│    - Baja: 10            (22%)                     │
│    - Media: 15           (33%)                     │
│    - Alta: 15            (33%)                     │
│    - Crítica: 5          (11%)                     │
└────────────────────────────────────────────────────┘

┌─ GRÁFICOS ─────────────────────────────────────────┐
│  [Gráfica de pastel - Distribución por estado]    │
│  [Gráfica de pastel - Distribución por área]      │
│  [Gráfica de línea - Tendencia últimos 30 días]   │
└────────────────────────────────────────────────────┘

┌─ TABLA DE DETALLES ────────────────────────────────┐
│ ID  │ Descripción│ Área      │ Prioridad │ Estado │
├─────┼──────────┼───────────┼──────────┼────────┤
│ 001 │ Monitor no enciende│ TI │ Alta │ Resuelto│
│ 002 │ Printer offline    │ Adm│ Media│ Cerrado │
│ ... │ ...       │ ...   │ ...  │ ...    │
└────────────────────────────────────────────────────┘

┌─ FOOTER ───────────────────────────────────────────┐
│ Página 1 de 2                                      │
│ Confidencial - Uso interno                         │
└────────────────────────────────────────────────────┘
```

**Formato:** A4, Horizontal (landscape)
**Fuentes:** Arial, Helvetica (compatible con weasyprint)
**Colores:** Según paleta de marca

---

### 🎫 Tipo 2: Detalle de Ticket

**Ruta:** `GET /incidencia/<id>/pdf/`

**Contenido:**

```
┌─ ENCABEZADO ─────────────────────────┐
│  Logo de la Empresa                   │
│  Título: "Detalle de Incidencia"      │
│  Fecha de generación: DD/MM/YYYY      │
└──────────────────────────────────────┘

INFORMACIÓN GENERAL
├─ ID: #001234
├─ Estado: Resuelto
├─ Creador: Juan Pérez (usuario@empresa.com)
├─ Área: Informática
├─ Técnico Asignado: Carlos López
├─ Fecha Creación: 18/04/2025 10:30
├─ Fecha Resolución: 20/04/2025 15:45
└─ Fecha Cierre: 21/04/2025 09:00

DETALLES DEL PROBLEMA
├─ Categoría: Hardware
├─ Prioridad: Alta
├─ Descripción:
│  El monitor de mi computadora dejó de encender 
│  después de una actualización de Windows. No 
│  aparece imagen en pantalla.
│
├─ Evidencia adjunta:
│  [IMAGEN DEL PROBLEMA - 800x600px]
└─

INFORMACIÓN TÉCNICA
├─ Observaciones Internas:
│  - Driver de video desactualizado
│  - Cable HDMI defectuoso verificado
│
├─ Solución Aplicada:
│  Se reemplazó el cable HDMI defectuoso por uno 
│  nuevo compatible. Se actualizaron drivers de 
│  video a versión 528.02. Se verificó funcionamiento 
│  correcto de la pantalla.
│
├─ Evidencia de Solución:
│  [IMAGEN DE SOLUCIÓN - 800x600px]
└─

HISTORIAL DE COMENTARIOS
├─ [18/04 10:30] Juan Pérez (Usuario):
│  "El monitor no enciende desde esta mañana"
│
├─ [19/04 09:00] Carlos López (Técnico):
│  "He revisado la computadora, parece ser un 
│   problema de drivers o cable de video"
│
├─ [20/04 15:45] Carlos López (Técnico):
│  "Incidencia resuelta: Cable HDMI reemplazado"
│
└─ [21/04 09:00] Juan Pérez (Confirmación):
│  "Perfecto, ya funciona correctamente!"
```

**Formato:** A4, Vertical (portrait)
**Acceso:** Todos los roles (si tienen acceso a la incidencia)

---

### 📋 Tipo 3: Reporte Técnico (Técnico)

**Ruta:** `GET /incidencias/reporte-asignadas/pdf/`

**Contenido:**

```
┌─ ENCABEZADO ──────────────────────────────┐
│  Mis Incidencias Asignadas                │
│  Técnico: Carlos López                    │
│  Fecha de generación: 22/04/2025          │
└───────────────────────────────────────────┘

ESTADÍSTICAS PERSONALES
├─ Total Asignadas: 15
├─ Resueltas: 10
├─ Cerradas: 8
├─ Tasa de Resolución: 66.7%
├─ Promedio Resolución: 2.3 días
└─ Críticas Pendientes: 2

TABLA DE INCIDENCIAS
│ ID   │ Descripción│ Prioridad │ Estado  │ Días  │
├──────┼───────────┼──────────┼─────────┼──────┤
│ 0001 │ Monitor   │ Alta     │ Cerrado │ 3    │
│ 0002 │ Printer   │ Media    │ Resuelto│ 1    │
│ ...  │ ...       │ ...      │ ...     │ ...  │
└──────┴───────────┴──────────┴─────────┴──────┘
```

---

## Casos de Uso

### 📖 Caso 1: Trabajador reporta problema

**Actores:** Trabajador

**Flujo:**

1. **Acceso:**
   - Inicia sesión en el sistema
   - Navega a menú principal
   - Selecciona "Crear Incidencia"

2. **Creación:**
   - Selecciona categoría: "Software"
   - Selecciona prioridad: "Alta"
   - Área se auto-completa (su departamento)
   - Escribe descripción: "No puedo acceder a mi email"
   - Adjunta captura de error (opcional)

3. **Confirmación:**
   - Hace click en "Crear Incidencia"
   - Sistema valida datos
   - Crea ticket con estado "Pendiente"

4. **Resultado:**
   - Ve mensaje: "Incidencia #00256 creada exitosamente"
   - Recibe notificación
   - Redirige a ver su nueva incidencia
   - Administrador ve incidencia pendiente

---

### 📖 Caso 2: Administrador asigna a técnico

**Actores:** Administrador, Técnico

**Precondiciones:**
- Incidencia existe en estado "Pendiente"
- Técnico disponible existe

**Flujo:**

1. **Búsqueda:**
   - Admin accede a "Todas las Incidencias"
   - Filtra por estado: "Pendiente"
   - Busca incidencia de software

2. **Asignación:**
   - Abre detalles de la incidencia
   - Click en "Gestionar Incidencia"
   - Selecciona técnico: "Carlos López"
   - Programa fecha de atención: "23/04/2025"
   - Guarda cambios

3. **Automatización:**
   - Sistema cambia estado a "En Proceso"
   - Crea notificación para técnico
   - Actualiza timestamp

4. **Resultado:**
   - Admin ve confirmación: "Incidencia asignada"
   - Técnico recibe notificación real-time
   - En su dashboard ve +1 en "Incidencias Asignadas"

---

### 📖 Caso 3: Técnico resuelve incidencia

**Actores:** Técnico

**Precondiciones:**
- Incidencia está "En Proceso"
- Técnico tiene asignada la incidencia

**Flujo:**

1. **Revisión:**
   - Técnico inicia sesión
   - Accede a "Mis Incidencias Asignadas"
   - Abre la incidencia #00256
   - Lee descripción y comentarios

2. **Investigación:**
   - Agrega comentario técnico: "Problema de sincronización SMTP"
   - Busca archivos de configuración
   - Prueba credenciales
   - Resuelve problema

3. **Registro:**
   - Click en "Resolver Incidencia"
   - Escribe en "Solución Aplicada":
     ```
     Se actualizó la configuración SMTP del Outlook 
     a los parámetros correctos de la empresa 
     (mail.empresa.com:587). Se verificó conexión 
     exitosa. Usuario puede acceder a email.
     ```
   - Adjunta captura de éxito

4. **Procesamiento:**
   - Hace click en "Resolver"
   - Sistema valida solución (mínimo 10 caracteres)
   - Cambia estado a "Resuelto"
   - Crea notificación para trabajador

5. **Resultado:**
   - Ve confirmación: "Incidencia resuelta"
   - Trabajador recibe notificación
   - En su perfil ve +1 en "Resueltas"

---

### 📖 Caso 4: Trabajador confirma solución

**Actores:** Trabajador

**Precondiciones:**
- Incidencia está "Resuelta"
- Trabajador es el creador

**Flujo: Conforme**

1. **Notificación:**
   - Trabajador ve notificación: "Tu incidencia #00256 fue resuelta"
   - Click en la notificación
   - Abre detalles de incidencia

2. **Verificación:**
   - Lee solución aplicada
   - Ve evidencia de la solución
   - Verifica en su email: ¡Funciona!

3. **Cierre:**
   - Click en "Cerrar y Confirmar"
   - Sistema cambia estado a "Cerrado"
   - Registra fecha/hora de cierre

4. **Resultado:**
   - Ve confirmación: "Incidencia cerrada"
   - Técnico notificado
   - Ticket archivado y completado

---

**Flujo: Problema Persiste**

1-2. (Mismo que arriba)

3. **Reapertura:**
   - Click en "Reabrir"
   - Comenta: "El problema vuelve a ocurrir después de reiniciar"
   - Adjunta nueva captura

4. **Procesamiento:**
   - Sistema cambia estado a "En Proceso"
   - Técnico original recibe notificación
   - Prioridad puede cambiar a "Crítica"

5. **Resultado:**
   - Técnico revisa nuevamente el problema
   - Investiga causa raíz más profunda

---

### 📖 Caso 5: Admin exporta reporte en PDF

**Actores:** Administrador

**Flujo:**

1. **Acceso:**
   - Admin navega a "Incidencias"
   - Busca botón "Exportar a PDF"

2. **Filtrado:**
   - Selecciona rango de fechas: "01/04/2025 - 30/04/2025"
   - Filtra por estado: "Resuelto"
   - Filtra por área: "Informática"
   - Aplica filtros

3. **Generación:**
   - Click en "Generar Reporte PDF"
   - Sistema procesa datos (2-5 segundos)
   - Genera documento con WeasyPrint

4. **Descarga:**
   - Navegador descarga: "Informe_Incidencias_2025-04.pdf"
   - Abre documento con 15 incidencias
   - Incluye gráficos y estadísticas

5. **Resultado:**
   - Documento profesional
   - Listo para presentación a directivos
   - Datos auditables y trazables

---

## Diagramas

### 🔄 Flujo de Estado

```
                    ┌────────────────┐
                    │   Pendiente    │
                    │   (Reportado)  │
                    └────────────────┘
                           │
                           │ [Admin asigna técnico]
                           ↓
                    ┌────────────────┐
                    │  En Proceso    │
                    │  (Asignado)    │
                    └────────────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
     [Técnico resuelve]    [Reapertura]
                │                │
                ↓                └──→ [Vuelve a En Proceso]
        ┌────────────────┐
        │   Resuelto     │
        │ (Confirmado)   │
        └────────────────┘
               │
               │ [Trabajador cierra]
               ↓
        ┌────────────────┐
        │   Cerrado      │
        │   (Archivado)  │
        └────────────────┘
               │
               └─→ FIN (sin transiciones)
```

---

### 👥 Modelo de Actores y Acciones

```
┌─────────────────────────────────────────────────────────┐
│                   SISTEMA DE INCIDENCIAS                 │
└─────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  TRABAJADOR  │      │   TÉCNICO    │      │ ADMINISTRADOR│
│  (usuario)   │      │ (tecnico)    │      │(administrador)
└──────────────┘      └──────────────┘      └──────────────┘
      │                     │                     │
      │                     │                     │
   ACCIONES:             ACCIONES:              ACCIONES:
   ───────               ──────                 ────────
   • Crear               • Ver asignadas        • Ver todas
   • Ver sus             • Resolver             • Crear
   • Comentar            • Comentar técnico     • Asignar
   • Cerrar              • Exportar PDF         • Editar
   • Reabrir             personal               • Crear usuarios
   • Ver perfil                                 • Exportar PDF
                                                • Dashboards

┌─────────────────────────────────────────────────────────┐
│                    FLUJO PRINCIPAL                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Trabajador               Admin           Técnico        │
│     │                       │               │            │
│     │ 1. Crear              │               │            │
│     ├──────────────→ [INCIDENCIA PENDIENTE] │            │
│     │                       │               │            │
│     │                2. Asigna              │            │
│     │                  ├──────────────→ [EN PROCESO]    │
│     │                       │               │            │
│     │                       │          3. Resuelve      │
│     │                       │          ├────────────→   │
│     │                       │         [RESUELTO]        │
│     │                                    │ ↓            │
│     │ 4. Confirma / Reabre               │ ↓            │
│     ├──────────────────────────────────→ │ ↓            │
│     │                                    │ ↓            │
│     │                                [CERRADO]         │
│     │                                    │              │
│     └────── Notificación Real-time ──────┘              │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

### 🗄️ Modelo de Datos Simplificado

```
┌─────────────────────────────────────────────────────────┐
│                     CustomUser                          │
├─────────────────────────────────────────────────────────┤
│ • id (UUID)                                             │
│ • username, email, password                             │
│ • role (usuario/tecnico/administrador)                 │
│ • area_id (FK → Area)                                  │
│ • telefono, foto                                        │
│ • last_seen, must_change_password                       │
└──────────────────────────┬──────────────────────────────┘
                           │
                 ┌─────────┼─────────┐
                 │         │         │
        ┌────────▼──┐  ┌───▼─────┐  │
        │ creador   │  │ asignado│  │
        │ (1:N)     │  │ (1:N)   │  │
        │           │  │         │  │
        │   ┌───────┴──┴────────┐│  │
        └───│  Incidencia       ││  │
            ├───────────────────┤│  │
            │ • id (UUID)       ││  │
            │ • descripcion     ││  │
            │ • categoria       ││  │
            │ • prioridad       ││  │
            │ • estado_id  (FK) ├┘  │
            │ • area_id (FK)    │   │
            │ • fecha_creacion  │   │
            │ • solucion_aplica │   │
            │ • evidencia       │   │
            └────┬──────────────┘   │
                 │                  │
          ┌──────▼──┐         ┌─────▼────┐
          │ Estado  │         │ Area      │
          ├─────────┤         ├───────────┤
          │ id      │         │ id        │
          │ nombre  │         │ nombre    │
          └─────────┘         └───────────┘

┌─────────────────────────────────────────────────────────┐
│                 Comentario                              │
├─────────────────────────────────────────────────────────┤
│ • id                                                    │
│ • incidencia_id (FK)                                   │
│ • autor_id (FK → CustomUser)                           │
│ • tipo (tecnico/confirmacion/persiste/observacion)    │
│ • contenido                                             │
│ • fecha_creacion                                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│            Notificacion / NotificacionUsuario           │
├─────────────────────────────────────────────────────────┤
│ Notificacion:                                           │
│ • id, tipo, mensaje, incidencia_id, usuario_origen_id  │
│ • fecha_creacion                                        │
│                                                         │
│ NotificacionUsuario:                                    │
│ • usuario_id (FK → CustomUser)                          │
│ • notificacion_id (FK)                                 │
│ • leido (Boolean)                                       │
│ • fecha_lectura                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Resumen Ejecutivo

### ✅ Capacidades por Rol

| Funcionalidad | Trabajador | Técnico | Admin |
|---------------|:---------:|:---------:|:-----:|
| Crear incidencias | ✅ | ❌ | ✅ |
| Ver todas | ❌ | ❌ | ✅ |
| Ver asignadas | N/A | ✅ | ✅ |
| Ver mis incidencias | ✅ | ✅ | ✅ |
| Resolver | ❌ | ✅ | ❌ |
| Asignar técnicos | ❌ | ❌ | ✅ |
| Editar incidencias | ❌ | ✅ (datos técnicos) | ✅ |
| Cerrar | ✅ | ❌ | ❌ |
| Crear usuarios | ❌ | ❌ | ✅ |
| Exportar PDF | ❌ | ✅ | ✅ |
| Dashboard | ❌ | ✅ | ✅ |

---

### 📊 Estadísticas del Sistema

- **Estados disponibles:** 4 (Pendiente, En Proceso, Resuelto, Cerrado)
- **Prioridades:** 4 (Baja, Media, Alta, Crítica)
- **Categorías:** 4 (Hardware, Software, Red, Sistema)
- **Tipos de comentarios:** 4
- **Tipos de notificaciones:** 6
- **Roles de usuario:** 3

---

### 🔐 Medidas de Seguridad

✅ Autenticación por roles (`@user_passes_test`)
✅ Campos readonly para datos originales
✅ Bloqueo en estados finales (Resuelto/Cerrado)
✅ Contraseña inicial forzada en primer login
✅ Validación de tamaño de imágenes (máximo 2MB)
✅ Contraseña con requisitos de complejidad
✅ Notificaciones de auditoría en cambios críticos

---

### 🚀 Características Avanzadas

🌐 **Notificaciones Real-Time:** WebSocket con Django Channels
📊 **Reportes en PDF:** WeasyPrint con gráficos
🖼️ **Procesamiento de imágenes:** Redimensionamiento automático
🔴 **Presencia Online:** Tracking de última actividad
🔔 **Sistema de notificaciones:** Múltiples canales
📱 **Interfaz HTMX:** Actualizaciones sin recarga completa

---

## Conclusión

El módulo de incidencias es un sistema completo de gestión de tickets que:

- ✅ Permite reportar problemas de forma simple
- ✅ Automatiza asignación y seguimiento
- ✅ Proporciona control absoluto al administrador
- ✅ Facilita trabajo colaborativo entre técnicos y usuarios
- ✅ Genera reportes profesionales
- ✅ Implementa seguridad a nivel de roles
- ✅ Mantiene historial completo y auditable

**Resultado:** Sistema profesional, escalable y listo para producción.
