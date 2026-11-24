"""Validación de RUT mediante módulo 11, sin incluir el dato en los errores."""

import re
from itertools import cycle

from django.core.exceptions import ValidationError
from django.db.models import Q

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


# Lo que puede ser un RUT, completo o a medio escribir, ya sin puntos ni espacios: «12345», «12345678-»,
# «12345678-5», «123456785» o «10000013K».
_PATRON_BUSQUEDA = re.compile(r"[1-9][0-9]{0,8}(?:-[0-9K]?)?|[1-9][0-9]{0,7}K")


def condicion_busqueda_rut(texto, campo="rut"):
    """Condición que encuentra el RUT buscado en `campo`, o None si el texto no parece un RUT.

    Acepta puntos, guion, espacios y k minúscula. Un RUT completo y válido se busca exacto; además, el texto sin
    puntos ni espacios se busca como comienzo del RUT guardado (sin puntos, con guion), para que la búsqueda en vivo
    encuentre mientras se escribe y que el RUT sin dígito verificador («12345678» o «12.345.678») encuentre
    «12345678-5». Si el mismo texto es también un RUT completo sin guion («1234567» + «8»), salen ambos.
    """
    limpio = re.sub(r"[.\s]", "", texto).upper() if isinstance(texto, str) else ""
    if not _PATRON_BUSQUEDA.fullmatch(limpio):
        return None
    condicion = Q(**{f"{campo}__startswith": limpio})
    try:
        condicion |= Q(**{campo: normalizar_rut(limpio)})
    except ValidationError:
        pass
    return condicion


def formatear_rut(valor):
    """Devuelve un RUT válido con puntos de miles y guion."""
    cuerpo, dv = normalizar_rut(valor).split("-")
    return f"{int(cuerpo):,}-{dv}".replace(",", ".")
