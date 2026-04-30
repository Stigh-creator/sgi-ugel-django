# 📖 Contexto del Proyecto: SGI - UGEL

Este documento está diseñado para proporcionar una visión general rápida del proyecto a cualquier nuevo agente de IA o desarrollador que se una al equipo, evitando la necesidad de leer todos los archivos desde cero.

## 🎯 Nombre y Objetivo
- **Nombre del Proyecto:** `gestion_incidencias` (SGI - Sistema de Gestión de Incidencias)
- **Objetivo:** Es una plataforma web robusta diseñada para la Unidad de Gestión Educativa Local (UGEL). Su finalidad es centralizar, gestionar y optimizar el flujo de soporte técnico, permitiendo el reporte, seguimiento y resolución de tickets de soporte de manera eficiente entre Trabajadores, Técnicos y Administradores.

## 🛠️ Stack Técnico
- **Framework Principal:** Django (Python).
- **Entorno Virtual:** Se utiliza un `venv` activo para la gestión de dependencias.
- **Base de Datos:** PostgreSQL (preparado para producción) / SQLite (desarrollo).
- **Librerías Críticas Instaladas:**
  - `channels` y `channels_redis` (Para notificaciones en tiempo real vía WebSockets).
  - `reportlab` / `xhtml2pdf` (Generación de reportes y constancias en PDF).
  - `openpyxl` (Exportación/Manejo de archivos Excel).
  - `psycopg2-binary` (Adaptador de PostgreSQL).
  - `Pillow` (Procesamiento y compresión de imágenes/evidencias).

## 📂 Estructura de Carpetas y Arquitectura
El proyecto sigue una arquitectura modular de Django, compuesto por varias apps (`tickets`, `auditoria`, `inventario`). La aplicación central es `tickets`:

- **Modelos (`models.py` / `models/`):** Contiene la estructura de la base de datos (CustomUser, Incidencia, Comentario, Area, Notificacion).
- **Vistas (`views/`):** ¡Importante! Las vistas no están en un solo archivo `views.py`. Están divididas modularmente en la carpeta `views/` (ej. `views_incidencias.py`, `views_usuarios.py`, `views_dashboard.py`, `views_auth.py`, etc.) para mantener el código limpio.
- **URLs (`urls.py`):** Centraliza el enrutamiento y llama a las vistas modulares.
- **Formularios (`forms/`):** Al igual que las vistas, los formularios están divididos en múltiples archivos (ej. `forms_usuarios.py`, `forms_incidencias.py`).
- **Plantillas (`templates/tickets/`):** Interfaz construida con HTML5, CSS3 Vanilla (Rich Aesthetics, evitando Tailwind a menos que se indique) y JavaScript Vanilla (SweetAlert2 para modales y AJAX nativo).

## 📊 Estado Actual
- **Funcionalidades Terminadas:**
  - Sistema completo de CRUD de incidencias (con transiciones de estado: Pendiente -> En Proceso -> Resuelto -> Cerrado).
  - Sistema de roles (Trabajador, Técnico, Administrador) con permisos aislados.
  - Generación de reportes PDF.
  - Módulo de Auditoría para rastrear acciones de usuarios.
  - Dashboards con KPIs y gráficos estadísticos.
  - Perfil de usuario con recorte de imágenes (Cropper.js) y cambio de contraseña forzado.
  - Notificaciones en tiempo real por WebSockets.
- **En qué estamos trabajando (Últimos cambios):**
  - Implementación de políticas de seguridad robustas en contraseñas (evitando uso de datos personales, validación de complejidad).
  - Ajustes de responsividad y optimización de experiencia de usuario (UX/UI).

## ⚠️ Reglas de Desarrollo
Para mantener la estabilidad y consistencia del proyecto, todo asistente o desarrollador debe adherirse a las siguientes reglas:

1. **"No inventar librerías nuevas"**: Utiliza el stack actual. Si se requiere algo nuevo, consúltalo explícitamente antes de instalarlo.
2. **"Mantener la compatibilidad con el venv"**: Cualquier dependencia nueva (si se aprueba) debe registrarse en el archivo `requirements.txt`.
3. **"Consultar antes de cambiar la base de datos"**: No modifiques los modelos de Django (`models.py`) ni crees nuevas migraciones sin antes discutir el impacto y recibir aprobación directa.
