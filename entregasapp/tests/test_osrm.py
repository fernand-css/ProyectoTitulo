"""RF-09-19 (enmienda del 2026-11-15): cliente del servidor de rutas propio, contra un OSRM simulado."""

import time
from unittest import mock
from urllib.request import ProxyHandler

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from entregasapp import osrm
from entregasapp.ruta import Punto
from entregasapp.tests.osrm_simulado import OsrmSimulado

O = Punto("origen", -36.4988773, -72.2123601)
A = Punto(1, -36.51, -72.20)
B = Punto(2, -36.48, -72.25)


class OsrmTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.servidor = OsrmSimulado().iniciar()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.detener()
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.servidor.modo = ""
        self.servidor.max_tabla = 300
        self.servidor.solicitudes.clear()
        self.servidor.distancia = lambda a, b: round(abs(a[0] - b[0]) * 100000 + abs(a[1] - b[1]) * 50000, 1)
        configuracion = override_settings(OSRM_URL=self.servidor.url, OSRM_TIEMPO_ESPERA=0.5)
        configuracion.enable()
        self.addCleanup(configuracion.disable)

    def test_tabla_envia_longitud_latitud_con_seis_decimales(self):
        matriz = osrm.tabla([O, A, B])
        self.assertEqual(len(self.servidor.solicitudes), 1)
        url = self.servidor.solicitudes[0]
        self.assertTrue(url.startswith("/table/v1/driving/-72.212360,-36.498877;-72.200000,-36.510000;"
                                       "-72.250000,-36.480000?"), url)
        self.assertIn("annotations=distance", url)
        self.assertEqual(len(matriz), 3)
        self.assertEqual(matriz[0][0], 0.0)
        self.assertAlmostEqual(matriz[1][2], 3000 + 2500, places=0)

    def test_tabla_con_origenes_pide_solo_esas_filas(self):
        matriz = osrm.tabla([O, A, B], origenes=[0])
        self.assertIn("sources=0", self.servidor.solicitudes[0])
        self.assertEqual(len(matriz), 1)
        self.assertEqual(len(matriz[0]), 3)

    def test_tramo_devuelve_distancia_y_geometria_en_latitud_longitud(self):
        resultado = osrm.tramo(A, B)
        self.assertTrue(self.servidor.solicitudes[0].startswith("/route/v1/driving/-72.200000,-36.510000;"
                                                                "-72.250000,-36.480000?"))
        self.assertIn("overview=full", self.servidor.solicitudes[0])
        self.assertIn("geometries=geojson", self.servidor.solicitudes[0])
        self.assertAlmostEqual(resultado.distancia_m, 5500, places=0)
        self.assertEqual(resultado.geometria[0], [-36.51, -72.2])
        self.assertEqual(resultado.geometria[-1], [-36.48, -72.25])

    def test_fallas_son_no_disponible_sin_coordenadas_en_el_mensaje(self):
        casos = [(modo, llamada) for modo in ("error500", "noroute", "malformado")
                 for llamada in (lambda: osrm.tabla([O, A, B]), lambda: osrm.tramo(A, B))]
        casos.append(("nulo", lambda: osrm.tabla([O, A, B])))  # una distancia nula solo existe en la tabla
        for modo, llamada in casos:
            with self.subTest(modo=modo):
                self.servidor.modo = modo
                with self.assertRaises(osrm.OsrmNoDisponible) as error:
                    llamada()
                texto = str(error.exception) + repr(error.exception.__cause__)
                for coordenada in ("36.4988", "72.2123", "36.51", "72.25"):
                    self.assertNotIn(coordenada, texto)

    def test_tiempo_agotado_es_no_disponible_dentro_del_margen(self):
        self.servidor.modo = "lento"
        self.servidor.demora = 1.5
        inicio = time.perf_counter()
        with self.assertRaises(osrm.OsrmNoDisponible):
            osrm.tabla([O, A, B])
        self.assertLess(time.perf_counter() - inicio, 0.5 + 0.4)

    def test_servidor_apagado_es_no_disponible(self):
        with override_settings(OSRM_URL="http://127.0.0.1:9"):
            with self.assertRaises(osrm.OsrmNoDisponible):
                osrm.tramo(A, B)

    def test_respuesta_con_forma_inesperada(self):
        for cuerpo in ({"code": "Ok"}, {"code": "Ok", "distances": [[0, 1]]}, {"code": "Ok", "distances": "x"},
                       {"code": "Ok", "distances": [[0, -1, 2], [0, 0, 0], [0, 0, 0]]}, ["Ok"]):
            with self.subTest(cuerpo=cuerpo), mock.patch.object(osrm, "_consultar", return_value=cuerpo) as consultar:
                if not isinstance(cuerpo, dict):
                    consultar.side_effect = osrm.OsrmNoDisponible("forma")
                with self.assertRaises(osrm.OsrmNoDisponible):
                    osrm.tabla([O, A, B])
        for cuerpo in ({"code": "Ok", "routes": []}, {"code": "Ok", "routes": [{"distance": 10}]},
                       {"code": "Ok", "routes": [{"distance": 10, "geometry": {"coordinates": []}}]}):
            with self.subTest(cuerpo=cuerpo), mock.patch.object(osrm, "_consultar", return_value=cuerpo):
                with self.assertRaises(osrm.OsrmNoDisponible):
                    osrm.tramo(A, B)

    def test_url_vacia_desactiva_sin_consultar(self):
        with override_settings(OSRM_URL=""):
            self.assertFalse(osrm.activo())
            with self.assertRaises(osrm.OsrmNoDisponible):
                osrm.tabla([O, A])
        self.assertEqual(self.servidor.solicitudes, [])

    def test_no_usa_los_proxies_del_entorno(self):
        # Con ProxyHandler({}) el opener no agrega el manejador de proxies del entorno.
        self.assertFalse([m for m in osrm._opener().handlers if isinstance(m, ProxyHandler) and m.proxies])
        with mock.patch.dict("os.environ", {"HTTP_PROXY": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9"}):
            self.assertEqual(len(osrm.tabla([O, A])), 2)

    def test_cache_solo_para_la_matriz_de_la_ruta(self):
        osrm.tabla([O, A, B], cachear=True)
        osrm.tabla([O, A, B], cachear=True)
        self.assertEqual(len(self.servidor.solicitudes), 1)
        osrm.tabla([O, A, B], origenes=[0], cachear=True)  # con orígenes (la posición) nunca se guarda
        osrm.tabla([O, A, B], origenes=[0], cachear=True)
        self.assertEqual(len(self.servidor.solicitudes), 3)
        osrm.tabla([O, A, B])
        self.assertEqual(len(self.servidor.solicitudes), 4)

    def test_tabla_demasiado_grande_es_no_disponible(self):
        self.servidor.max_tabla = 2
        with self.assertRaises(osrm.OsrmNoDisponible):
            osrm.tabla([O, A, B])

    def test_tras_una_caida_no_vuelve_a_esperar_durante_unos_segundos(self):
        """Con OSRM caído, cada página esperaría el tiempo de espera completo; tras una falla de red o del servidor
        se usa el respaldo de inmediato durante `SEGUNDOS_CAIDO` (RNF-05)."""
        self.servidor.modo = "error500"
        with self.assertRaises(osrm.OsrmNoDisponible):
            osrm.tabla([O, A, B])
        self.servidor.modo = ""
        with self.assertRaises(osrm.OsrmNoDisponible):
            osrm.tramo(A, B)
        self.assertEqual(len(self.servidor.solicitudes), 1)  # la segunda no consultó
        cache.clear()  # pasado el plazo, vuelve a consultar
        self.assertAlmostEqual(osrm.tramo(A, B).distancia_m, 5500, places=0)
        self.assertEqual(osrm.SEGUNDOS_CAIDO, 30)

    def test_un_camino_imposible_no_marca_el_servidor_como_caido(self):
        self.servidor.modo = "noroute"
        with self.assertRaises(osrm.OsrmNoDisponible):
            osrm.tramo(A, B)
        self.servidor.modo = ""
        self.assertEqual(len(osrm.tabla([O, A, B])), 3)
