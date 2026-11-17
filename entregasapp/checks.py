"""Comprobaciones de sistema de la configuración del mapa (spec 09, RF-09-12).

`cesfam/settings.py` lee las variables sin lanzar errores; aquí `python manage.py check` informa con texto claro
los valores que no sirven: el origen del recorrido, la URL de las teselas y el zoom máximo.
"""

import math
from numbers import Real
from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Error, register


def _numero(valor):
    return isinstance(valor, Real) and not isinstance(valor, bool) and math.isfinite(valor)


@register()
def revisar_mapa(app_configs=None, **kwargs):
    errores = []
    latitud = getattr(settings, "REPARTO_ORIGEN_LATITUD", None)
    longitud = getattr(settings, "REPARTO_ORIGEN_LONGITUD", None)
    if not (_numero(latitud) and -90 <= latitud <= 90 and _numero(longitud) and -180 <= longitud <= 180):
        errores.append(Error(
            f"El origen del recorrido no es una coordenada válida: latitud {latitud!r}, longitud {longitud!r}.",
            hint="Usa números con punto decimal: la latitud entre -90 y 90 y la longitud entre -180 y 180 "
                 "(REPARTO_ORIGEN_LATITUD y REPARTO_ORIGEN_LONGITUD en .env).",
            id="entregasapp.E001",
        ))
    url = getattr(settings, "MAPA_TESELAS_URL", "")
    if not isinstance(url, str) or not url.startswith("https://") or not all(marca in url for marca in ("{z}", "{x}", "{y}")):
        errores.append(Error(
            f"La URL de las teselas del mapa no es válida: {url!r}.",
            hint="Debe empezar con https:// e incluir {z}, {x} e {y} (MAPA_TESELAS_URL en .env).",
            id="entregasapp.E002",
        ))
    zoom = getattr(settings, "MAPA_ZOOM_MAXIMO", None)
    if not (isinstance(zoom, int) and not isinstance(zoom, bool) and 1 <= zoom <= 22):
        errores.append(Error(
            f"El zoom máximo del mapa no es válido: {zoom!r}.",
            hint="Usa un número entero entre 1 y 22 (MAPA_ZOOM_MAXIMO en .env).",
            id="entregasapp.E003",
        ))
    errores += revisar_osrm()
    return errores


def _url_osrm_valida(url):
    try:
        partes = urlsplit(url)
        partes.port  # noqa: B018  (un puerto no numérico lanza ValueError)
    except ValueError:
        return False
    return partes.scheme in ("http", "https") and bool(partes.hostname) and not partes.query and not partes.fragment \
        and "?" not in url and "#" not in url


def revisar_osrm():
    """RF-09-19: dirección y tiempo de espera del servidor de rutas. No comprueba que el servidor responda."""
    errores = []
    url = getattr(settings, "OSRM_URL", "")
    if not isinstance(url, str) or (url.strip() and not _url_osrm_valida(url.strip())):
        errores.append(Error(
            f"La dirección del servidor de rutas no es válida: {url!r}.",
            hint="Usa http:// o https:// con un host, sin consulta ni fragmento, por ejemplo http://127.0.0.1:5000; "
                 "déjala vacía para desactivar el servicio (OSRM_URL en .env).",
            id="entregasapp.E004",
        ))
    espera = getattr(settings, "OSRM_TIEMPO_ESPERA", None)
    if not (_numero(espera) and 0.2 <= espera <= 2.0):
        errores.append(Error(
            f"El tiempo de espera del servidor de rutas no es válido: {espera!r}.",
            hint="Usa un número de segundos entre 0.2 y 2.0, para respetar la respuesta en 2 s o menos "
                 "(OSRM_TIEMPO_ESPERA en .env).",
            id="entregasapp.E005",
        ))
    return errores
