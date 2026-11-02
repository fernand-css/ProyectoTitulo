"""Identificadores ficticios para pruebas; no representan personas."""

from random import Random

from .rut import calcular_dv


def generar_ruts(cantidad: int, azar: Random):
    """Genera RUT únicos y repetibles usando el generador recibido."""
    cuerpos = azar.sample(range(90_000_000, 100_000_000), cantidad)
    return [f"{cuerpo}-{calcular_dv(cuerpo)}" for cuerpo in cuerpos]


def generar_rut(azar: Random):
    """Genera un RUT ficticio con dígito verificador válido."""
    return generar_ruts(1, azar)[0]
