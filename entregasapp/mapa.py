"""Datos del mapa de una ruta (spec 09, RF-09-08 y RF-09-14), listos para `json_script`.

Lleva lo mínimo para dibujar: coordenadas, número, estado y lo que el encargado ya ve en la lista (nombre,
sector, localidad, dirección y referencias). Nunca el RUT, el teléfono, las notas ni las fotos. En «Rutas» de la
Q.F. (`consulta=True`) no hay enlaces para registrar ni para «Ir a esta parada».
"""

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .consultas import domicilio_de
from .models import IntentoEntrega


def _coordenada(valor):
    return round(float(valor), 6)


def _punto(punto, etiqueta):
    return {"lat": _coordenada(punto.latitud), "lon": _coordenada(punto.longitud), "etiqueta": etiqueta}


def _nombre(paciente):
    return f"{paciente.nombres} {paciente.apellidos}".strip()


def _ubicacion(intento):
    domicilio = domicilio_de(intento.entrega.paciente)
    if domicilio is None:
        return {"sector": "", "localidad": "", "direccion": intento.entrega.paciente.direccion or "", "referencias": ""}
    return {
        "sector": domicilio.get_sector_display() if domicilio.sector else "",
        "localidad": domicilio.localidad,
        "direccion": domicilio.direccion,
        "referencias": domicilio.referencias,
    }


def teselas():
    return {
        "url": settings.MAPA_TESELAS_URL,
        "atribucion": settings.MAPA_TESELAS_ATRIBUCION,
        "zoom_maximo": settings.MAPA_ZOOM_MAXIMO,
    }


def datos_mapa(ruta, *, consulta=False):
    """Diccionario del mapa de `ruta` (consultas.RutaDelDia)."""
    paradas = []
    for parada in ruta.paradas:
        if parada.punto is None:
            continue
        intento = parada.intento
        estado = f"Atrasada desde el {intento.fecha_programada:%d/%m}" if parada.atrasada else "Pendiente"
        paradas.append({
            "numero": parada.numero,
            "intento": intento.pk,
            "lat": _coordenada(parada.punto.latitud),
            "lon": _coordenada(parada.punto.longitud),
            "estado": estado,
            "nueva": parada.nueva,
            "titulo": _nombre(intento.entrega.paciente),
            **_ubicacion(intento),
            "url_registrar": "" if consulta or not ruta.es_hoy else reverse("entregasapp:registro", args=[intento.pk]),
            "url_ir": "" if consulta or not ruta.es_hoy else reverse("entregasapp:ir_a", args=[intento.pk]),
            "url_domicilio": reverse("entregasapp:domicilio", args=[intento.entrega.paciente_id]),
        })
    registradas = []
    for intento in ruta.registradas:
        domicilio = domicilio_de(intento.entrega.paciente)
        if domicilio is None or domicilio.latitud is None:
            continue
        registradas.append({
            "intento": intento.pk,
            "lat": _coordenada(domicilio.latitud),
            "lon": _coordenada(domicilio.longitud),
            "entregada": intento.resultado == IntentoEntrega.Resultado.ENTREGADA,
            "resultado": intento.get_resultado_display(),
            "motivo": intento.get_motivo_display() if intento.motivo else "",
            "hora": f"{timezone.localtime(intento.registrado_en):%H:%M}",
            "titulo": _nombre(intento.entrega.paciente),
            **_ubicacion(intento),
            "url_domicilio": reverse("entregasapp:domicilio", args=[intento.entrega.paciente_id]),
        })
    linea = [[_coordenada(ruta.partida.latitud), _coordenada(ruta.partida.longitud)]]
    linea += [[p["lat"], p["lon"]] for p in paradas]
    linea.append([_coordenada(ruta.origen.latitud), _coordenada(ruta.origen.longitud)])
    return {
        "origen": _punto(ruta.origen, "CESFAM"),
        "partida": None if ruta.parte_del_origen else _punto(ruta.partida, "Última visita registrada"),
        "teselas": teselas(),
        "paradas": paradas,
        "registradas": registradas,
        "linea": linea,
        "total_km": ruta.total_km,
        "sin_marcador": ruta.sin_marcador,
        "consulta": consulta,
    }


def datos_punto(domicilio):
    """Mapa pequeño de un domicilio (RF-09-11): su punto y su precisión, sin datos del paciente."""
    return {
        "lat": _coordenada(domicilio.latitud),
        "lon": _coordenada(domicilio.longitud),
        "precision": domicilio.precision_metros,
        "teselas": teselas(),
    }


def datos_ir_a(parada):
    """«Ir a esta parada» (RF-09-09): el destino y su número; la posición del encargado nunca sale del navegador."""
    return {
        "numero": parada.numero,
        "lat": _coordenada(parada.punto.latitud),
        "lon": _coordenada(parada.punto.longitud),
        "teselas": teselas(),
    }
