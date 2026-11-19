"""Búsqueda instantánea de las listas con buscador (`static/js/busqueda_en_vivo.js`).

Mientras se escribe o se cambia un filtro, el navegador envía el mismo formulario por POST, con la cabecera
`X-Busqueda-En-Vivo: 1`, a la misma vista. La vista arma el mismo contexto y, en vez de la página completa, dibuja
solo sus zonas (`[data-zona]`) con `components/busqueda_en_vivo.html`; el script reemplaza cada zona por la del mismo
nombre sin tocar el campo donde se escribe. Sin JavaScript, la misma vista responde la página entera.

El RUT o el nombre viajan siempre en el cuerpo del POST, nunca en la URL.
"""

CABECERA = "X-Busqueda-En-Vivo"
PLANTILLA = "components/busqueda_en_vivo.html"


def es_en_vivo(request):
    return request.method == "POST" and request.headers.get(CABECERA) == "1"


def plantilla_y_contexto(request, completa, contexto, zonas):
    """La plantilla que corresponde a la solicitud y su contexto: la página completa o solo sus zonas."""
    if zonas and es_en_vivo(request):
        return PLANTILLA, {**contexto, "zonas": list(zonas)}
    return completa, contexto
