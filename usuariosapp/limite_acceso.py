"""Límite de intentos de inicio de sesión (cambio posterior al spec 02, 2026-11-24).

Cada intento con usuario y contraseña reserva un cupo en dos contadores de la ventana de 15 minutos en curso:
el del usuario escrito en ese equipo (`LIMITE_CUENTA`) y el del equipo (`LIMITE_EQUIPO`, para que no se prueben
muchos usuarios desde el mismo lugar). La reserva se hace antes de comprobar la contraseña, con un UPDATE
condicional sobre la cantidad: PostgreSQL reevalúa el filtro tras esperar el bloqueo de la fila, así que ni con
solicitudes simultáneas se comprueban más contraseñas que el límite. Un ingreso correcto devuelve su cupo del
equipo y borra los fallos de ese usuario en ese equipo.

Es una espera, no un bloqueo de la cuenta: la cuenta sigue habilitada y quien intenta desde otro equipo no la
deja sin acceso. Las huellas son `salted_hmac`; nunca se guardan el usuario ni la IP en claro.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from math import ceil

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from coreapp.auditoria import registrar_accion
from .models import IntentoAcceso

VENTANA = timedelta(minutes=15)
LIMITE_CUENTA = 5
LIMITE_EQUIPO = 20
CONSERVAR = timedelta(days=1)
ACCION_LIMITE = "auth.limite_intentos"


@dataclass(frozen=True)
class Reserva:
    cuenta: str
    equipo: str
    ventana: datetime


class LimiteSuperado(Exception):
    """Se agotaron los intentos de la ventana; `minutos` es la espera hasta la siguiente."""

    def __init__(self, minutos):
        super().__init__(minutos)
        self.minutos = minutos


class _Rechazo(Exception):
    def __init__(self, clave):
        super().__init__(clave)
        self.clave = clave


def huellas(usuario, ip):
    """Huella del usuario escrito en el equipo y huella del equipo. Sin mayúsculas ni espacios en los extremos,
    para que variar la escritura del usuario no dé intentos nuevos."""
    usuario = (usuario or "").strip().casefold()[:150]
    ip = ip or ""
    cuenta = salted_hmac("usuariosapp.acceso.cuenta", f"{usuario}\n{ip}", algorithm="sha256").hexdigest()
    equipo = salted_hmac("usuariosapp.acceso.equipo", ip, algorithm="sha256").hexdigest()
    return cuenta, equipo


def inicio_ventana(instante):
    paso = int(VENTANA.total_seconds())
    return datetime.fromtimestamp(int(instante.timestamp()) // paso * paso, tz=dt_timezone.utc)


def _sumar(clave, ventana, limite):
    """Suma un intento a la clave si queda bajo el límite; devuelve si fue aceptado."""
    for _ in range(8):
        if IntentoAcceso.objects.filter(clave=clave, ventana=ventana, cantidad__lt=limite).update(cantidad=F("cantidad") + 1):
            return True
        fila = IntentoAcceso.objects.filter(clave=clave, ventana=ventana).first()
        if fila is not None:
            if fila.cantidad < limite:
                continue  # Otra solicitud la creó entre ambas lecturas: reintentar el UPDATE.
            return False
        try:
            with transaction.atomic():
                IntentoAcceso.objects.create(clave=clave, ventana=ventana, cantidad=1)
        except IntegrityError:
            continue
        # Limpieza al escribir: las ventanas antiguas ya no cuentan.
        IntentoAcceso.objects.filter(ventana__lt=ventana - CONSERVAR).delete()
        return True
    return False  # Contención anómala: ante la duda no se comprueba la contraseña.


def _auditar_limite(clave, ventana):
    """Una vez por huella y ventana, sin usuario, IP ni datos de la petición."""
    with transaction.atomic():
        fila = IntentoAcceso.objects.filter(clave=clave, ventana=ventana).first()
        if fila is not None and IntentoAcceso.objects.filter(pk=fila.pk, auditado=False).update(auditado=True):
            registrar_accion(None, ACCION_LIMITE, fila)


def reservar(usuario, ip, instante=None):
    """Reserva un intento en ambos contadores o ninguno; lanza `LimiteSuperado` si alguno está lleno."""
    ahora = instante or timezone.now()
    ventana = inicio_ventana(ahora)
    cuenta, equipo = huellas(usuario, ip)
    try:
        with transaction.atomic():
            for clave, limite in ((cuenta, LIMITE_CUENTA), (equipo, LIMITE_EQUIPO)):
                if not _sumar(clave, ventana, limite):
                    raise _Rechazo(clave)
    except _Rechazo as rechazo:
        _auditar_limite(rechazo.clave, ventana)
        raise LimiteSuperado(max(1, ceil((ventana + VENTANA - ahora).total_seconds() / 60))) from None
    return Reserva(cuenta, equipo, ventana)


def ingreso_correcto(reserva):
    """El ingreso no fue un fallo: devuelve el cupo del equipo y borra los fallos del usuario en el equipo."""
    with transaction.atomic():
        IntentoAcceso.objects.filter(clave=reserva.cuenta).delete()
        IntentoAcceso.objects.filter(
            clave=reserva.equipo, ventana=reserva.ventana, cantidad__gt=0,
        ).update(cantidad=F("cantidad") - 1)
