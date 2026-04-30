# 📋 SGI - Sistema de Gestión de Incidencias (UGEL)

![Django](https://img.shields.io/badge/django-%23092E20.svg?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

## 📝 Resumen del Sistema
El **SGI-UGEL** es una solución integral diseñada para digitalizar el flujo de soporte técnico y administrativo en las Unidades de Gestión Educativa Local. El sistema transforma el caos de reportes verbales o por correo en un flujo de trabajo estructurado donde cada incidencia es registrada, categorizada, asignada a un especialista y monitoreada hasta su resolución final. 

Su objetivo principal es eliminar los cuellos de botella en la atención al usuario y proporcionar métricas reales sobre el rendimiento del equipo de soporte.

## 🚀 Características Principales

- **Gestión de Tickets:** Ciclo de vida completo desde "Pendiente" hasta "Cerrado" con historial de cambios.
- **Roles y Permisos:** - 👷 **Trabajador:** Reporta problemas y confirma soluciones.
  - 🔧 **Técnico:** Gestiona, comenta y resuelve incidencias asignadas.
  - 👨‍💼 **Administrador:** Supervisa el sistema, gestiona usuarios y visualiza estadísticas.
- **Notificaciones:** Sistema de alertas para cambios de estado y nuevas asignaciones.
- **Dashboard de KPIs:** Visualización de métricas críticas (tickets críticos, tiempos promedio, carga de trabajo por técnico).
- **Reportes PDF:** Generación de constancias de servicio y reportes mensuales de gestión.
- **Seguridad:** Autenticación robusta y manejo eficiente de archivos multimedia (evidencias de errores).

## 🛠️ Stack Tecnológico

- **Backend:** Django 5.x + Python 3.12
- **Base de Datos:** PostgreSQL (Producción) / SQLite (Desarrollo)
- **Frontend:** HTML5, CSS3 (Rich Aesthetics), JavaScript Vanilla
- **Documentación:** ReportLab (Generación de PDF)
- **Infraestructura:** Docker & Docker Compose (Listo para despliegue)

## 📦 Instalación y Configuración

### Prerrequisitos
- Python 3.10+
- Pip (Gestor de paquetes)

### Pasos para ejecución local

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/Stigh-creator/sgi-ugel-django.git](https://github.com/Stigh-creator/sgi-ugel-django.git)
   cd sgi-ugel-django