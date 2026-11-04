"""Configuración sensible comprobada sin leer ni modificar secretos locales."""

import importlib.util
import os
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


class ConfiguracionTests(SimpleTestCase):
    def cargar(self, _con_base=True, **entorno):
        if _con_base:
            entorno.setdefault("DB_NAME", "cesfam_sintetica")
        especificacion = importlib.util.spec_from_file_location("configuracion_prueba", settings.BASE_DIR / "cesfam/settings.py")
        modulo = importlib.util.module_from_spec(especificacion)
        with patch.dict(os.environ, entorno, clear=True), patch("dotenv.load_dotenv"):
            especificacion.loader.exec_module(modulo)
        return modulo

    def test_secret_key_ausente_o_vacia_impide_arranque(self):
        for entorno in ({}, {"SECRET_KEY": ""}, {"SECRET_KEY": "   "}):
            with self.subTest(entorno=entorno):
                with self.assertRaisesMessage(ImproperlyConfigured, "Debes definir SECRET_KEY"):
                    self.cargar(**entorno)

    def test_base_postgresql_exige_nombre_y_usa_host_y_puerto_por_defecto(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "Debes definir DB_NAME"):
            self.cargar(_con_base=False, SECRET_KEY="clave-sintetica-de-prueba")
        base = self.cargar(SECRET_KEY="clave-sintetica-de-prueba", DB_NAME="cesfam_sintetica", DB_HOST="", DB_PORT="")
        self.assertEqual(base.DATABASES["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual((base.DATABASES["default"]["HOST"], base.DATABASES["default"]["PORT"]), ("localhost", "5432"))
        base = self.cargar(SECRET_KEY="clave-sintetica-de-prueba", DB_HOST="db.example.invalid", DB_PORT="6543", DB_USER="rol_sintetico")
        self.assertEqual((base.DATABASES["default"]["HOST"], base.DATABASES["default"]["PORT"], base.DATABASES["default"]["USER"]), ("db.example.invalid", "6543", "rol_sintetico"))

    def test_defaults_seguros_y_configuracion_regional(self):
        configuracion = self.cargar(SECRET_KEY="clave-sintetica-de-prueba")
        self.assertFalse(configuracion.DEBUG)
        self.assertTrue(configuracion.SESSION_COOKIE_SECURE)
        self.assertTrue(configuracion.CSRF_COOKIE_SECURE)
        self.assertEqual(configuracion.EMAIL_BACKEND, "django.core.mail.backends.smtp.EmailBackend")
        self.assertEqual(configuracion.ALLOWED_HOSTS, [])
        self.assertEqual(configuracion.LANGUAGE_CODE, "es-cl")
        self.assertEqual(configuracion.TIME_ZONE, "America/Santiago")

    def test_desarrollo_y_lista_de_hosts(self):
        configuracion = self.cargar(SECRET_KEY="clave-sintetica-de-prueba", DEBUG="True", ALLOWED_HOSTS="localhost, 127.0.0.1, , [::1]")
        self.assertFalse(configuracion.SESSION_COOKIE_SECURE)
        self.assertFalse(configuracion.CSRF_COOKIE_SECURE)
        self.assertEqual(configuracion.EMAIL_BACKEND, "django.core.mail.backends.console.EmailBackend")
        self.assertEqual(configuracion.ALLOWED_HOSTS, ["localhost", "127.0.0.1", "[::1]"])

    def test_smtp_se_lee_del_entorno(self):
        configuracion = self.cargar(
            SECRET_KEY="clave-sintetica-de-prueba", EMAIL_HOST="smtp.example.invalid",
            EMAIL_PORT="465", EMAIL_HOST_USER="cuenta-sintetica", EMAIL_HOST_PASSWORD="valor-sintetico",
            EMAIL_USE_TLS="False", EMAIL_USE_SSL="True", DEFAULT_FROM_EMAIL="prueba@example.invalid",
        )
        self.assertEqual(configuracion.EMAIL_HOST, "smtp.example.invalid")
        self.assertEqual(configuracion.EMAIL_PORT, 465)
        self.assertEqual(configuracion.EMAIL_HOST_USER, "cuenta-sintetica")
        self.assertEqual(configuracion.EMAIL_HOST_PASSWORD, "valor-sintetico")
        self.assertFalse(configuracion.EMAIL_USE_TLS)
        self.assertTrue(configuracion.EMAIL_USE_SSL)
        self.assertEqual(configuracion.DEFAULT_FROM_EMAIL, "prueba@example.invalid")

    def test_booleanos_invalidos_fallan_con_mensaje_claro(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "La variable DEBUG debe ser true o false."):
            self.cargar(SECRET_KEY="clave-sintetica-de-prueba", DEBUG="tal-vez")

    def test_requirements_utf8_sin_bom(self):
        contenido = (settings.BASE_DIR / "requirements.txt").read_bytes()
        self.assertFalse(contenido.startswith(b"\xef\xbb\xbf"))
        self.assertIn("Django>=5.2,<5.3", contenido.decode("utf-8"))
