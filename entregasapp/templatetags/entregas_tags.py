"""Etiquetas de las plantillas del reparto a domicilio."""

from django import template
from django.utils import timezone
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def horas_sin_conexion(registrado, sincronizado):
    """Spec 11 (RF-11-15): «Registrada sin conexión a las HH:MM · recibida a las HH:MM» para un resultado registrado
    sin conexión (la hora del celular y la de llegada). Si llegó otro día, la llegada dice también la fecha. Sin
    `sincronizado` (registro con señal), no muestra nada."""
    if not registrado or not sincronizado:
        return ""
    hecho, llegada = timezone.localtime(registrado), timezone.localtime(sincronizado)
    dia = f"el {llegada:%d/%m} " if llegada.date() != hecho.date() else ""
    return format_html(
        '<span class="dato-secundario sin-conexion-horas">Registrada sin conexión a las <time datetime="{}">{}</time>'
        ' · recibida {}a las <time datetime="{}">{}</time></span>',
        hecho.isoformat(), f"{hecho:%H:%M}", dia, llegada.isoformat(), f"{llegada:%H:%M}",
    )
