"""RF-09-12: origen del recorrido y cartografía configurables, con errores claros de `check`."""

import io
import os
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.test import SimpleTestCase, override_settings

from cesfam import settings as modulo_settings
from entregasapp.checks import revisar_mapa

VARIABLES = ("REPARTO_ORIGEN_LATITUD", "REPARTO_ORIGEN_LONGITUD", "MAPA_TESELAS_URL", "MAPA_TESELAS_ATRIBUCION",
             "MAPA_ZOOM_MAXIMO")


def ids(errores):
    return sorted(error.id for error in errores)


class ConfiguracionMapaTests(SimpleTestCase):
    def test_valores_por_defecto_sin_variables(self):
        if any(os.getenv(nombre) for nombre in VARIABLES):
            self.skipTest("El .env local define variables del mapa.")
        self.assertEqual(settings.REPARTO_ORIGEN_LATITUD, -36.4988773)
        self.assertEqual(settings.REPARTO_ORIGEN_LONGITUD, -72.2123601)
        self.assertEqual(settings.MAPA_TESELAS_URL, "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
        self.assertEqual(settings.MAPA_TESELAS_ATRIBUCION, "© colaboradores de OpenStreetMap")
        self.assertEqual(settings.MAPA_ZOOM_MAXIMO, 19)
        self.assertEqual(revisar_mapa(), [])

    def test_lectura_de_numeros_del_entorno(self):
        leer = modulo_settings._numero_entorno
        with mock.patch.dict(os.environ, {"PRUEBA_MAPA": ""}):
            self.assertEqual(leer("PRUEBA_MAPA", -36.5), -36.5)
        for texto, esperado in (("-36.4988773", -36.4988773), ("-36,4988773", -36.4988773), (" 12 ", 12.0),
                                ("noventa", "noventa"), ("95", 95.0)):
            with self.subTest(texto=texto), mock.patch.dict(os.environ, {"PRUEBA_MAPA": texto}):
                self.assertEqual(leer("PRUEBA_MAPA", 0.0), esperado)
        with mock.patch.dict(os.environ, {"PRUEBA_MAPA": "18.5"}):
            self.assertEqual(leer("PRUEBA_MAPA", 19, int), "18.5")

    def test_valores_validos_no_dan_errores(self):
        with override_settings(REPARTO_ORIGEN_LATITUD=-90, REPARTO_ORIGEN_LONGITUD=180,
                               MAPA_TESELAS_URL="https://teselas.example.invalid/{z}/{x}/{y}.png", MAPA_ZOOM_MAXIMO=22):
            self.assertEqual(revisar_mapa(), [])

    def test_origen_fuera_de_rango_o_no_numerico_es_e001(self):
        for latitud, longitud in ((95, -72.2), (-36.5, -181), ("noventa", -72.2), (float("nan"), -72.2), (True, -72.2)):
            with self.subTest(latitud=latitud, longitud=longitud), override_settings(
                    REPARTO_ORIGEN_LATITUD=latitud, REPARTO_ORIGEN_LONGITUD=longitud):
                errores = revisar_mapa()
                self.assertEqual(ids(errores), ["entregasapp.E001"])
                self.assertIn("no es una coordenada válida", errores[0].msg)
                self.assertIn("REPARTO_ORIGEN_LATITUD", errores[0].hint)

    def test_url_sin_marcadores_o_sin_https_es_e002(self):
        for url in ("https://tile.openstreetmap.org/{x}/{y}.png", "http://tile.openstreetmap.org/{z}/{x}/{y}.png", ""):
            with self.subTest(url=url), override_settings(MAPA_TESELAS_URL=url):
                errores = revisar_mapa()
                self.assertEqual(ids(errores), ["entregasapp.E002"])
                self.assertIn("{z}, {x} e {y}", errores[0].hint)

    def test_zoom_fuera_de_rango_es_e003(self):
        for zoom in (0, 23, "18.5", 19.0):
            with self.subTest(zoom=zoom), override_settings(MAPA_ZOOM_MAXIMO=zoom):
                self.assertEqual(ids(revisar_mapa()), ["entregasapp.E003"])

    def test_el_comando_check_informa_el_error(self):
        with override_settings(REPARTO_ORIGEN_LATITUD=95, MAPA_TESELAS_URL="https://teselas.example.invalid/{x}/{y}.png"):
            with self.assertRaises(SystemCheckError) as error:
                call_command("check", stdout=io.StringIO(), stderr=io.StringIO())
        texto = str(error.exception)
        self.assertIn("entregasapp.E001", texto)
        self.assertIn("entregasapp.E002", texto)


class ConfiguracionOsrmTests(SimpleTestCase):
    """RF-09-19 (enmienda del 2026-11-15): dirección y tiempo de espera del servidor de rutas."""

    def test_valores_por_defecto_y_variable_vacia(self):
        leer = modulo_settings._osrm_url_entorno
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OSRM_URL", None)
            self.assertEqual(leer(), "http://127.0.0.1:5000")
        with mock.patch.dict(os.environ, {"OSRM_URL": ""}):
            self.assertEqual(leer(), "")
        with mock.patch.dict(os.environ, {"OSRM_URL": " http://osrm.interno:5000 "}):
            self.assertEqual(leer(), "http://osrm.interno:5000")
        with mock.patch.dict(os.environ, {"PRUEBA_ESPERA": ""}):
            self.assertEqual(modulo_settings._numero_entorno("PRUEBA_ESPERA", 1.0), 1.0)
        with mock.patch.dict(os.environ, {"PRUEBA_ESPERA": "0,5"}):
            self.assertEqual(modulo_settings._numero_entorno("PRUEBA_ESPERA", 1.0), 0.5)

    def test_valores_validos_no_dan_errores(self):
        for url in ("http://127.0.0.1:5000", "https://osrm.interno", "http://osrm:5000/", ""):
            for espera in (0.2, 1.0, 2.0, 1):
                with self.subTest(url=url, espera=espera), override_settings(OSRM_URL=url, OSRM_TIEMPO_ESPERA=espera):
                    self.assertEqual(revisar_mapa(), [])

    def test_url_no_valida_es_e004(self):
        for url in ("ftp://x", "http://h:5000/?a=1", "http://h:5000/#f", "http://", "127.0.0.1:5000", "http://h:puerto",
                    "http://h?"):
            with self.subTest(url=url), override_settings(OSRM_URL=url):
                errores = revisar_mapa()
                self.assertEqual(ids(errores), ["entregasapp.E004"])
                self.assertIn("OSRM_URL", errores[0].hint)

    def test_tiempo_fuera_de_rango_es_e005(self):
        for espera in (5, 0.1, 2.5, "uno", float("nan"), True):
            with self.subTest(espera=espera), override_settings(OSRM_TIEMPO_ESPERA=espera):
                errores = revisar_mapa()
                self.assertEqual(ids(errores), ["entregasapp.E005"])
                self.assertIn("OSRM_TIEMPO_ESPERA", errores[0].hint)

    def test_check_informa_e004_y_e005(self):
        with override_settings(OSRM_URL="ftp://x", OSRM_TIEMPO_ESPERA=5):
            with self.assertRaises(SystemCheckError) as error:
                call_command("check", stdout=io.StringIO(), stderr=io.StringIO())
        self.assertIn("entregasapp.E004", str(error.exception))
        self.assertIn("entregasapp.E005", str(error.exception))

    def test_las_pruebas_corren_con_osrm_desactivado(self):
        from entregasapp import osrm
        self.assertEqual(settings.OSRM_URL, "")
        self.assertFalse(osrm.activo())
