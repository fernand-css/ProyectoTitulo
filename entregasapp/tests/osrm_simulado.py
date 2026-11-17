"""OSRM simulado para las pruebas y la herramienta HTTP del 09 (enmienda del 2026-11-15, RF-09-19).

Un servidor HTTP mínimo en 127.0.0.1 (puerto libre) que responde `table` y `route` de forma determinista, sin
red externa y sin registrar nada. Por defecto, la distancia «por camino» es la haversine multiplicada por
`factor`; una prueba puede entregar su propia función `distancia(a, b)` (a y b son `(latitud, longitud)`) para
construir una matriz a mano. `modo` simula fallas: "lento", "error500", "noroute", "malformado" y "nulo".
"""

import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

RADIO_M = 6_371_000.0


def haversine(a, b):
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat, dlon = lat2 - lat1, math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * RADIO_M * math.asin(min(1.0, math.sqrt(h)))


def _puntos(texto):
    """`lon,lat;lon,lat` → [(lat, lon), …]."""
    pares = []
    for par in texto.split(";"):
        lon, lat = par.split(",")
        pares.append((float(lat), float(lon)))
    return pares


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, formato, *args):  # sin registros: la URL lleva coordenadas
        return

    def _enviar(self, codigo, cuerpo, tipo="application/json"):
        datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):  # noqa: N802
        simulado = self.server.simulado
        partes = urlsplit(self.path)
        simulado.solicitudes.append(self.path)
        modo = simulado.modo
        if modo == "lento":
            time.sleep(simulado.demora)
        if modo == "error500":
            return self._enviar(500, {"code": "Error"})
        if modo == "malformado":
            return self._enviar(200, b"{no es json", "application/json")
        if modo == "noroute":
            return self._enviar(200, {"code": "NoRoute", "message": "Impossible route between points"})
        segmentos = partes.path.strip("/").split("/")
        if len(segmentos) != 4 or segmentos[1] != "v1" or segmentos[2] != "driving":
            return self._enviar(400, {"code": "InvalidUrl"})
        servicio, puntos = segmentos[0], _puntos(segmentos[3])
        consulta = parse_qs(partes.query)
        distancia = simulado.distancia
        if servicio == "table":
            if len(puntos) > simulado.max_tabla:
                return self._enviar(400, {"code": "TooBig"})
            origenes = range(len(puntos))
            if "sources" in consulta:
                origenes = [int(i) for i in consulta["sources"][0].split(";")]
            filas = [[None if modo == "nulo" and i != j else round(distancia(puntos[i], puntos[j]), 1)
                      for j in range(len(puntos))] for i in origenes]
            return self._enviar(200, {"code": "Ok", "distances": filas})
        if servicio == "route":
            a, b = puntos[0], puntos[-1]
            medio = ((a[0] + b[0]) / 2 + 0.0005, (a[1] + b[1]) / 2)
            geometria = [[p[1], p[0]] for p in (a, medio, b)]
            return self._enviar(200, {"code": "Ok", "routes": [
                {"distance": round(distancia(a, b), 1), "geometry": {"type": "LineString", "coordinates": geometria}}]})
        return self._enviar(400, {"code": "InvalidService"})


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        return  # el cliente cortó (tiempo agotado a propósito): no ensuciar la salida de las pruebas


class OsrmSimulado:
    def __init__(self, *, distancia=None, factor=1.3, modo="", demora=2.0, max_tabla=300):
        self.distancia = distancia or (lambda a, b: haversine(a, b) * factor)
        self.modo = modo
        self.demora = demora
        self.max_tabla = max_tabla
        self.solicitudes = []
        self._servidor = None
        self._hilo = None

    @property
    def url(self):
        host, puerto = self._servidor.server_address[:2]
        return f"http://{host}:{puerto}"

    def iniciar(self):
        self._servidor = _Servidor(("127.0.0.1", 0), _Manejador)
        self._servidor.simulado = self
        self._hilo = threading.Thread(target=self._servidor.serve_forever, daemon=True)
        self._hilo.start()
        return self

    def detener(self):
        if self._servidor is not None:
            self._servidor.shutdown()
            self._servidor.server_close()
            self._servidor = None

    def __enter__(self):
        return self.iniciar()

    def __exit__(self, *exc):
        self.detener()


class ConOsrmSimulado:
    """Mezcla para clases de prueba: un OSRM simulado por clase, activo en cada prueba y con la caché vacía.

    `factor_osrm = 1.0` hace que la distancia «por camino» sea la línea recta: así las pruebas anteriores a la
    enmienda conservan sus órdenes y totales, ahora calculados con la matriz de OSRM.
    """

    factor_osrm = 1.0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.osrm = OsrmSimulado(factor=cls.factor_osrm).iniciar()
        cls.addClassCleanup(cls.osrm.detener)

    def setUp(self):
        from django.core.cache import cache
        from django.test import override_settings

        cache.clear()
        self.osrm.modo = ""
        self.osrm.solicitudes.clear()
        self.osrm.distancia = lambda a, b: haversine(a, b) * self.factor_osrm
        configuracion = override_settings(OSRM_URL=self.osrm.url, OSRM_TIEMPO_ESPERA=0.5)
        configuracion.enable()
        self.addCleanup(configuracion.disable)
        self.addCleanup(cache.clear)
        super().setUp()
