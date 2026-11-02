"""Formato de RUT y duración para las vistas internas."""

import math
from datetime import timedelta

from django import template
from django.core.exceptions import ValidationError

from coreapp.utils.rut import formatear_rut

register = template.Library()


@register.filter(name="rut")
def rut(valor):
    try:
        return formatear_rut(valor)
    except ValidationError:
        return ""


@register.filter(name="minutos")
def minutos(valor):
    """Convierte segundos a minutos enteros, redondeando hacia arriba."""
    try:
        segundos = valor.total_seconds() if isinstance(valor, timedelta) else float(valor)
        if not math.isfinite(segundos):
            return "—"
        return f"{math.ceil(max(0, segundos) / 60)} min"
    except (TypeError, ValueError, OverflowError):
        return "—"
