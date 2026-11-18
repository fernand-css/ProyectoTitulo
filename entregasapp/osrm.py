"""Cliente del servidor de rutas propio (spec 09, enmienda del 2026-11-15, RF-09-19).

Solo Django consulta a OSRM; el navegador nunca conoce su dirección. Usa la biblioteca estándar (sin dependencias
nuevas), no usa los proxies del entorno y espera a lo más `OSRM_TIEMPO_ESPERA` segundos por operación de red.
Cualquier falla (tiempo, red, código distinto de `Ok`, JSON mal formado o una distancia nula) se informa como
`OsrmNoDisponible`, con un mensaje que nunca incluye coordenadas: quien llama usa su respaldo. «Sin camino»
(`NoSegment`/`NoRoute`, por ejemplo una posición fuera del mapa cargado) es `SinCamino`, su subclase: OSRM sí
respondió, así que no se marca como caído.

Las coordenadas viajan como `longitud,latitud` con 6 decimales. La matriz de la ruta (solo domicilios y el CESFAM)
se puede guardar en la caché de Django unos minutos; la que incluye la posición del encargado, nunca.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from django.conf import settings
from django.core.cache import cache

LIMITE_RESPUESTA = 5 * 1024 * 1024  # bytes; una tabla de 202 puntos pesa bastante menos
SEGUNDOS_CACHE_TABLA = 600
# Tras una falla de red, de tiempo o del servidor, OSRM se da por no disponible unos segundos sin volver a
# esperarlo: con el servidor caído, cada consulta esperaría el tiempo de espera completo (en Windows, una conexión
# rechazada en localhost también tarda) y una página con dos consultas pasaría de los 2 s de RNF-05.
SEGUNDOS_CAIDO = 30
PERFIL = "driving"


def _clave_caido(base):
    return "osrm:caido:" + hashlib.sha256(base.encode()).hexdigest()


class OsrmNoDisponible(Exception):
    """OSRM no respondió a tiempo, falló o entregó algo que no sirve. El mensaje no lleva coordenadas."""


class SinCamino(OsrmNoDisponible):
    """OSRM respondió, pero no hay camino entre los puntos: por ejemplo, la posición queda fuera del mapa cargado.

    No es una caída: no marca el servidor como no disponible. Hereda de `OsrmNoDisponible` para que quien solo
    tiene un respaldo (la ruta en línea recta) lo siga usando sin cambios.
    """


# Códigos de OSRM que significan «respondió, pero no hay camino». El servidor real entrega `NoSegment` (un punto
# sin calle cercana en el mapa cargado) con HTTP 400; `NoRoute` puede llegar con 200 o con 400.
CODIGOS_SIN_CAMINO = frozenset({"NoSegment", "NoRoute"})


def _codigo(cuerpo):
    try:
        datos = json.loads(cuerpo)
    except (ValueError, UnicodeDecodeError):
        return None
    return datos.get("code") if isinstance(datos, dict) else None


@dataclass(frozen=True)
class Tramo:
    distancia_m: float
    geometria: list  # [[latitud, longitud], …], lista para Leaflet


def activo():
    """`False` si `OSRM_URL` está vacía: el servicio queda desactivado y todo usa su respaldo."""
    return bool((getattr(settings, "OSRM_URL", "") or "").strip())


def _coordenadas(puntos):
    """`lon,lat;lon,lat` con 6 decimales. Cada punto tiene `latitud` y `longitud`."""
    return ";".join(f"{float(p.longitud):.6f},{float(p.latitud):.6f}" for p in puntos)


def _opener():
    return build_opener(ProxyHandler({}))  # sin proxies del entorno: OSRM vive en la red interna


def _consultar(servicio, puntos, parametros):
    if not activo():
        raise OsrmNoDisponible("El servidor de rutas está desactivado.")
    base = settings.OSRM_URL.strip().rstrip("/")
    caido = _clave_caido(base)
    if cache.get(caido):
        raise OsrmNoDisponible("El servidor de rutas no respondió hace poco; se usa el respaldo.")
    url = f"{base}/{servicio}/v1/{PERFIL}/{_coordenadas(puntos)}?{parametros}"
    solicitud = Request(url, headers={"Accept": "application/json"})
    try:
        with _opener().open(solicitud, timeout=float(settings.OSRM_TIEMPO_ESPERA)) as respuesta:
            cuerpo = respuesta.read(LIMITE_RESPUESTA + 1)
    except HTTPError as error:
        # OSRM contestó con un error. «Sin camino» (p. ej. la posición fuera del mapa) no es una caída.
        try:
            codigo = _codigo(error.read(64 * 1024))
        except OSError:
            codigo = None
        finally:
            error.close()
        if error.code == 400 and codigo in CODIGOS_SIN_CAMINO:
            raise SinCamino("El servidor de rutas no encontró un camino desde ese punto.") from None
        cache.set(caido, True, SEGUNDOS_CAIDO)
        raise OsrmNoDisponible("El servidor de rutas no respondió.") from _sin_detalle(error)
    except (URLError, OSError, ValueError) as error:  # el tiempo agotado es OSError
        cache.set(caido, True, SEGUNDOS_CAIDO)
        raise OsrmNoDisponible("El servidor de rutas no respondió.") from _sin_detalle(error)
    if len(cuerpo) > LIMITE_RESPUESTA:
        raise OsrmNoDisponible("La respuesta del servidor de rutas es demasiado grande.")
    try:
        datos = json.loads(cuerpo)
    except (ValueError, UnicodeDecodeError):
        raise OsrmNoDisponible("La respuesta del servidor de rutas no se pudo leer.") from None
    if isinstance(datos, dict) and datos.get("code") in CODIGOS_SIN_CAMINO:
        raise SinCamino("El servidor de rutas no encontró un camino desde ese punto.")
    if not isinstance(datos, dict) or datos.get("code") != "Ok":
        raise OsrmNoDisponible("La respuesta del servidor de rutas no se pudo usar.")
    return datos


def _sin_detalle(error):
    """La causa encadenada no debe arrastrar la URL (que lleva coordenadas) a un registro de errores."""
    return OsrmNoDisponible(type(error).__name__)


def _metros(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor < 0:
        raise OsrmNoDisponible("El servidor de rutas no conoce un camino entre dos puntos.")
    return float(valor)


def _clave_tabla(puntos):
    texto = _coordenadas(puntos) + "|" + settings.OSRM_URL.strip()
    return "osrm:tabla:" + hashlib.sha256(texto.encode()).hexdigest()


def tabla(puntos, *, origenes=None, cachear=False):
    """Matriz de distancias por camino en metros: `matriz[i][j]` va del origen i al punto j.

    Con `origenes` (índices) solo calcula esas filas, por ejemplo `[0]` para la posición del encargado.
    `cachear=True` solo para la matriz de la ruta: domicilios y el CESFAM, nunca la posición.
    """
    puntos = list(puntos)
    if len(puntos) < 2:
        raise OsrmNoDisponible("Hacen falta al menos dos puntos.")
    if cachear and origenes is None:
        clave = _clave_tabla(puntos)
        guardada = cache.get(clave)
        if guardada is not None:
            return guardada
    parametros = "annotations=distance"
    if origenes is not None:
        parametros += "&sources=" + ";".join(str(int(indice)) for indice in origenes)
    datos = _consultar("table", puntos, parametros)
    filas = datos.get("distances")
    esperadas = len(puntos) if origenes is None else len(origenes)
    if not isinstance(filas, list) or len(filas) != esperadas:
        raise OsrmNoDisponible("La respuesta del servidor de rutas no tiene la forma esperada.")
    matriz = []
    for fila in filas:
        if not isinstance(fila, list) or len(fila) != len(puntos):
            raise OsrmNoDisponible("La respuesta del servidor de rutas no tiene la forma esperada.")
        matriz.append([_metros(valor) for valor in fila])
    if cachear and origenes is None:
        cache.set(clave, matriz, SEGUNDOS_CACHE_TABLA)
    return matriz


def tramo(desde, hasta):
    """Camino de `desde` a `hasta`: su distancia en metros y la línea `[[lat, lon], …]` para dibujarla."""
    datos = _consultar("route", [desde, hasta],
                       "overview=full&geometries=geojson&steps=false&alternatives=false")
    try:
        ruta = datos["routes"][0]
        distancia = _metros(ruta["distance"])
        coordenadas = ruta["geometry"]["coordinates"]
        geometria = [[round(float(lat), 6), round(float(lon), 6)] for lon, lat in coordenadas]
    except (KeyError, IndexError, TypeError, ValueError):
        raise OsrmNoDisponible("La respuesta del servidor de rutas no tiene la forma esperada.") from None
    if not geometria or not all(math.isfinite(v) for par in geometria for v in par):
        raise OsrmNoDisponible("La respuesta del servidor de rutas no tiene la forma esperada.")
    return Tramo(distancia, geometria)
