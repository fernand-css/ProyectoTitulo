"""Comprobaciones de sistema de la configuración del mapa (spec 09, RF-09-12).

`cesfam/settings.py` lee las variables sin lanzar errores; aquí `python manage.py check` informa con texto claro
los valores que no sirven: el origen del recorrido, la URL de las teselas y el zoom máximo.
"""

import math
from numbers import Real

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
    return errores
