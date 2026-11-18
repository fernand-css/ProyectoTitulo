"""Credenciales técnicas de ocho horas, sin renovación ni almacenamiento del token.

Se usa settings.SECRET_KEY, ya exigida por config/settings.py mediante la variable
externa DJANGO_SECRET_KEY. Debe ser estable y secreta; nunca se genera aquí.
No se aceptan claves de respaldo: rotar la clave invalida las firmas anteriores.
"""
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import DispositivoTotem


VIGENCIA_CREDENCIAL = timedelta(hours=8)
_PROPOSITO = "cesfam.totem.credencial.v1"
_MENSAJE = "Credencial de dispositivo no válida."


@dataclass(frozen=True)
class IdentidadDispositivo:
    dispositivo_id: uuid.UUID
    version: int


def _firmante():
    return signing.TimestampSigner(
        key=settings.SECRET_KEY, salt=_PROPOSITO, fallback_keys=[],
    )


def _firmar_credencial(dispositivo, momento):
    """Uso interno del consumo; el servicio entrega el token después del commit."""
    return _firmante().sign_object({
        "proposito": _PROPOSITO,
        "dispositivo": str(dispositivo.pk),
        "version": dispositivo.version_credencial,
        "identificador": str(uuid.uuid4()),
        "emitida_en": momento.isoformat(),
        "expira_en": (momento + VIGENCIA_CREDENCIAL).isoformat(),
    })


def validar_credencial_dispositivo(credencial):
    """Consulta PostgreSQL en cada uso; devuelve una identidad, no una sesión.

    La futura emisión deberá revalidar activo/versión bajo su bloqueo de negocio:
    esta lectura aislada no reserva autorización frente a una revocación posterior.
    """
    if not isinstance(credencial, str) or not 1 <= len(credencial) <= 2048 or credencial.startswith("."):
        raise PermissionDenied(_MENSAJE)
    try:
        datos = _firmante().unsign_object(credencial, max_age=VIGENCIA_CREDENCIAL)
        if not isinstance(datos, dict) or set(datos) != {
            "proposito", "dispositivo", "version", "identificador", "emitida_en", "expira_en",
        }:
            raise ValueError
        if datos["proposito"] != _PROPOSITO or type(datos["version"]) is not int or datos["version"] < 1:
            raise ValueError
        dispositivo_id = uuid.UUID(datos["dispositivo"])
        uuid.UUID(datos["identificador"])
        emitida = parse_datetime(datos["emitida_en"])
        expira = parse_datetime(datos["expira_en"])
        if emitida is None or expira is None or timezone.is_naive(emitida) or timezone.is_naive(expira):
            raise ValueError
        ahora = timezone.now()
        if expira - emitida != VIGENCIA_CREDENCIAL or not emitida <= ahora < expira:
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError, AttributeError, OverflowError):
        raise PermissionDenied(_MENSAJE) from None
    if not DispositivoTotem.objects.filter(
        pk=dispositivo_id, activo=True, version_credencial=datos["version"],
    ).exists():
        raise PermissionDenied(_MENSAJE)
    return IdentidadDispositivo(dispositivo_id, datos["version"])
