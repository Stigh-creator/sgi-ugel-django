import os
from importlib.util import find_spec
from pathlib import Path

from dotenv import load_dotenv

# 1. Rutas básicas del proyecto
# Define la ruta raíz del proyecto para localizar archivos de manera absoluta
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Clave secreta para la seguridad de los datos (debe mantenerse privada en producción)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-only-change-me')
# Modo de depuración activado por defecto en entorno local; en producción debe definirse explícitamente
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'
# Dominios o direcciones IP desde las cuales se puede acceder a la aplicación
ALLOWED_HOSTS = [host.strip() for host in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]

# 2. Aplicaciones instaladas (ajustado para la base, sin extras)
# Declara los módulos internos de Django y las aplicaciones propias del proyecto
INSTALLED_APPS = [
    'django.contrib.admin',        # Administrador de interfaz de usuario
    'django.contrib.auth',         # Sistema de autenticación
    'django.contrib.contenttypes', # Permite relaciones entre modelos
    'django.contrib.sessions',     # Gestión de sesiones de usuario
    'django.contrib.messages',     # Sistema de notificaciones temporales
    'django.contrib.staticfiles',  # Gestión de archivos CSS, JS e imágenes
    'tickets',                     # Aplicación principal de gestión de incidencias
    'inventario',                  # Módulo de Inventario de equipos
    'auditoria',                   # Módulo de Auditoría del sistema
]

if find_spec("daphne"):
    INSTALLED_APPS.insert(0, "daphne")

ASGI_APPLICATION = 'gestion_incidencias.asgi.application'
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# 3. Usuario Personalizado y autenticación
# Indica a Django que utilice el modelo CustomUser en lugar del modelo de usuario por defecto
AUTH_USER_MODEL = 'tickets.CustomUser'

# 4. Middleware (Limpio de extras)
# Define capas de procesamiento que actúan durante el ciclo de petición y respuesta
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',             # Protección contra ataques CSRF
    'django.contrib.auth.middleware.AuthenticationMiddleware', # Vincula usuarios a peticiones
    'tickets.middleware.EnforcePasswordChangeMiddleware',
    'auditoria.middleware.AuditMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Archivo principal de enrutamiento que conecta las URLs con las vistas
ROOT_URLCONF = 'gestion_incidencias.urls'

# 5. Configuración del motor de plantillas (Templates)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Especifica dónde buscar los archivos HTML del proyecto
        'DIRS': [os.path.join(BASE_DIR, 'templates')], 
        'APP_DIRS': True, # Permite buscar plantillas dentro de las carpetas de las apps
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'tickets.context_processors.notificaciones_header',
            ],
        },
    },
]

# Punto de entrada para servidores web compatibles con WSGI
WSGI_APPLICATION = 'gestion_incidencias.wsgi.application'

# 6. Motor de Base de Datos
# Por defecto usa SQLite para desarrollo local. PostgreSQL se activa solo por variables de entorno.
DB_ENGINE = os.environ.get("DB_ENGINE", "django.db.backends.sqlite3")

if DB_ENGINE == "django.db.backends.postgresql":
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": os.environ.get("DB_NAME", "gestion_incidencias"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        }
    }
elif DB_ENGINE == "django.db.backends.mysql":
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": os.environ.get("DB_NAME", "gestion_incidencias"),
            "USER": os.environ.get("DB_USER", "root"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# 7. Localización y zona horaria (Ajustado para Perú)
# Define el idioma español y la zona horaria de Lima para registros de auditoría
LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True # Habilita la traducción de la interfaz
USE_TZ = True   # Habilita el soporte de zonas horarias para las fechas
DEFAULT_CHARSET = "utf-8"

# 8. Gestión de Archivos Estáticos y Medios
# URL y directorio para archivos de diseño (CSS, JavaScript, imágenes del tema)
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# URL y directorio para archivos subidos por los usuarios (ej. capturas de pantalla)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Tipo de campo por defecto para las llaves primarias de las tablas
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# 9. Rutas de Autenticación (Criterio Épica 1)
LOGIN_URL = 'login'               # El nombre (name) que definimos en urls.py
LOGIN_REDIRECT_URL = 'index'      # A dónde ir después de loguearse con éxito
LOGOUT_REDIRECT_URL = 'login'     # A dónde ir al cerrar sesión
