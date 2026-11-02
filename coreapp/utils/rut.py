"""Validación de RUT mediante módulo 11, sin incluir el dato en los errores."""

import re
from itertools import cycle

from django.core.exceptions import ValidationError

_PATRON_RUT = re.compile(
    r"([1-9][0-9]{0,7}|[1-9][0-9]{0,2}(?:\.[0-9]{3}){1,2})-?([0-9K])"
)


def calcular_dv(cuerpo):
    """Calcula el dígito verificador de un cuerpo numérico de hasta 8 cifras."""
    cuerpo = str(cuerpo)
    if not re.fullmatch(r"[1-9][0-9]{0,7}", cuerpo):
        raise ValidationError("Ingresa un RUT válido.", code="rut_invalido")
    suma = sum(int(digito) * factor for digito, factor in zip(reversed(cuerpo), cycle(range(2, 8))))
    resto = 11 - suma % 11
    return "0" if resto == 11 else "K" if resto == 10 else str(resto)


def normalizar_rut(valor):
    """Devuelve el RUT válido sin puntos, con guion y K mayúscula."""
    coincidencia = _PATRON_RUT.fullmatch(valor.strip().upper()) if isinstance(valor, str) else None
    if coincidencia:
        cuerpo, dv = coincidencia.groups()
        cuerpo = cuerpo.replace(".", "")
        if len(cuerpo) <= 8 and calcular_dv(cuerpo) == dv:
            return f"{cuerpo}-{dv}"
    raise ValidationError("Ingresa un RUT válido.", code="rut_invalido")


def validar_rut(valor):
    """Indica si el RUT tiene formato y dígito verificador válidos."""
    try:
        normalizar_rut(valor)
    except ValidationError:
        return False
    return True


def formatear_rut(valor):
    """Devuelve un RUT válido con puntos de miles y guion."""
    cuerpo, dv = normalizar_rut(valor).split("-")
    return f"{int(cuerpo):,}-{dv}".replace(",", ".")
