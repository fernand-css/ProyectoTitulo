"""Configuración de cesfam; los valores de cada entorno se leen desde .env."""

import os
from pathlib import Path

from django.contrib.messages import constants as mensajes
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Las variables del proceso tienen prioridad sobre el archivo local.
load_dotenv(BASE_DIR / ".env")


def _booleano_entorno(nombre, predeterminado=False):
    valor = os.getenv(nombre, str(predeterminado)).strip().lower()
    if valor in {"true", "1", "yes", "on"}:
        return True
    if valor in {"false", "0", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"La variable {nombre} debe ser true o false.")


SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Debes definir SECRET_KEY en las variables de entorno o en el archivo .env."
    )

DEBUG = _booleano_entorno("DEBUG")
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "coreapp.apps.CoreappConfig",
    "usuariosapp.apps.UsuariosappConfig",
    "recetasapp.apps.RecetasappConfig",
    "turnosapp.apps.TurnosappConfig",
    "entregasapp.apps.EntregasappConfig",
    "indicadoresapp.apps.IndicadoresappConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cesfam.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "coreapp.context_processors.rol_actual",
            ],
            "libraries": {"core_tags": "coreapp.templatetags.core_tags"},
        },
    },
]

WSGI_APPLICATION = "cesfam.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTHENTICATION_BACKENDS = ["usuariosapp.backends.BackendPersonal"]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# En desarrollo no se envía correo real; fuera de él se usa SMTP.
EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _booleano_entorno("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = _booleano_entorno("EMAIL_USE_SSL")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "farmacia@example.invalid")

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

LOGIN_URL = "usuariosapp:login"
LOGIN_REDIRECT_URL = "coreapp:inicio"
LOGOUT_REDIRECT_URL = "usuariosapp:login"

MESSAGE_TAGS = {
    mensajes.DEBUG: "message-info",
    mensajes.INFO: "message-info",
    mensajes.SUCCESS: "message-success",
    mensajes.WARNING: "message-warning",
    mensajes.ERROR: "message-error",
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
