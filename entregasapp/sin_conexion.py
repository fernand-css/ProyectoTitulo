"""Reparto sin conexión (spec 11): paquete de la ruta para el celular y sincronización de los registros guardados.

- `paquete_del_dia` solo lee (`consultas.ruta_del_dia`) y entrega lo que ya muestra la tarjeta de «Mis entregas»:
  nunca el RUT, las fotos, las coordenadas, el correo para avisos ni los nombres de los medicamentos (RF-11-02).
- `sincronizar` aplica cada registro con los servicios del 08 (`registrar_entregada`, `registrar_no_entregada`),
  cada uno en su propia transacción, con su identificador de operación (RF-11-07). Un rechazo no detiene a los
  demás; un error de la base deja el registro en el celular para el siguiente intento («reintentar»).
- Gana lo que ya está en el servidor (RF-11-09). Los rechazos se auditan con su código, nunca con la nota.
"""

import uuid
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from coreapp.auditoria import registrar_referencia
from recetasapp.services import ConflictoOperacion
from . import consultas, services
from .models import IntentoEntrega

FORMATO = 1
MAXIMO_POR_LOTE = 50

APLICADO = "aplicado"
YA_APLICADO = "ya_aplicado"
RECHAZADO = "rechazado"
REINTENTAR = "reintentar"

ENTREGADA = IntentoEntrega.Resultado.ENTREGADA
NO_ENTREGADA = IntentoEntrega.Resultado.NO_ENTREGADA


class Rechazo:
    """Códigos de rechazo de un registro (RF-11-08, RF-11-09 y RF-11-11), con el motivo en palabras (RF-11-10)."""

    OTRO_USUARIO = "otro_usuario"
    NO_ASIGNADA = "no_asignada"
    REASIGNADA = "reasignada"
    ANULADA = "anulada"
    YA_REGISTRADA = "ya_registrada"
    HORA_INVALIDA = services.HORA_INVALIDA
    FUERA_DE_PLAZO = services.FUERA_DE_PLAZO
    INVALIDO = "invalido"

    MENSAJES = {
        OTRO_USUARIO: "Este registro se hizo con otra cuenta. Entra con esa cuenta para enviarlo.",
        NO_ASIGNADA: "Esta visita ya no está asignada a ti.",
        REASIGNADA: "La Q.F. reasignó esta visita antes de que llegara tu registro.",
        ANULADA: "La Q.F. anuló esta entrega antes de que llegara tu registro.",
        YA_REGISTRADA: "Esta visita ya tenía un resultado registrado.",
        HORA_INVALIDA: "La hora del registro no es válida. Revisa la fecha y la hora del celular.",
        FUERA_DE_PLAZO: "El registro llegó más de 2 días después de hecho y ya no se puede aplicar.",
        INVALIDO: "El registro no es válido. Vuelve a registrar la visita con señal.",
    }
    CODIGOS = frozenset(MENSAJES)


# Paquete de la ruta (RF-11-02) -----------------------------------------------------------------------------

def _parada(parada):
    intento = parada.intento
    paciente = intento.entrega.paciente
    domicilio = consultas.domicilio_de(paciente)
    return {
        "intento": intento.pk,
        "numero": parada.numero if parada.numerada else None,
        "seccion": "ruta" if parada.numerada else "sin_coordenadas",
        "fecha_programada": intento.fecha_programada.isoformat(),
        "atrasada": parada.atrasada,
        "nombre": f"{paciente.nombres} {paciente.apellidos}".strip(),
        "direccion": (domicilio.direccion if domicilio else paciente.direccion) or "",
        "referencias": domicilio.referencias if domicilio else "",
        "localidad": domicilio.localidad if domicilio else "",
        "sector": domicilio.get_sector_display() if domicilio and domicilio.sector else "",
        "telefono": paciente.telefono or "",
        "recetas": len(intento.entrega.recetas.all()),
        "traslado_iniciado": intento.traslado_iniciado_en is not None,
    }


def paquete_del_dia(encargado, ahora=None):
    """Visitas pendientes de hoy y atrasadas del encargado, en el orden de su ruta (guardado o sugerido, spec 09)."""
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    ruta = consultas.ruta_del_dia(encargado, hoy=hoy)
    return {
        "formato": FORMATO,
        "fecha": hoy.isoformat(),
        "generado_en": ahora.isoformat(),
        "cuenta": encargado.pk,
        "motivos": [[valor, texto] for valor, texto in IntentoEntrega.Motivo.choices],
        "paradas": [_parada(parada) for parada in ruta.paradas],
    }


# Sincronización (RF-11-06 a RF-11-11) ----------------------------------------------------------------------

@dataclass(frozen=True)
class Registro:
    operacion_id: uuid.UUID
    intento_id: int
    resultado: str
    motivo: str
    nota: str
    registrado_en: object
    cuenta: int


class RegistroNoValido(ValueError):
    def __init__(self, codigo, intento_id=None):
        super().__init__(codigo)
        self.codigo = codigo
        self.intento_id = intento_id


def _entero(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ValueError
    return int(valor)


def leer_registro(datos):
    """Registro desde el JSON del celular, o `RegistroNoValido` con su código. Nunca repite valores recibidos."""
    if not isinstance(datos, dict):
        raise RegistroNoValido(Rechazo.INVALIDO)
    try:
        intento_id = _entero(datos.get("intento"))
    except (TypeError, ValueError):
        raise RegistroNoValido(Rechazo.INVALIDO) from None
    try:
        operacion = uuid.UUID(str(datos.get("operacion_id")))
        cuenta = _entero(datos.get("cuenta"))
    except (TypeError, ValueError, AttributeError):
        raise RegistroNoValido(Rechazo.INVALIDO, intento_id) from None
    resultado = datos.get("resultado")
    motivo, nota = datos.get("motivo") or "", datos.get("nota") or ""
    if resultado not in (ENTREGADA, NO_ENTREGADA) or not isinstance(motivo, str) or not isinstance(nota, str):
        raise RegistroNoValido(Rechazo.INVALIDO, intento_id)
    texto = datos.get("registrado_en")
    try:
        registrado_en = parse_datetime(texto) if isinstance(texto, str) else None
    except ValueError:
        registrado_en = None
    if registrado_en is None or timezone.is_naive(registrado_en):
        raise RegistroNoValido(Rechazo.HORA_INVALIDA, intento_id)
    return Registro(operacion, intento_id, resultado, motivo, nota, registrado_en, cuenta)


def _respuesta(operacion_id, estado, codigo=""):
    """Resultado de un registro. Solo devuelve el identificador si es un UUID: el celular lo usa como clave."""
    try:
        operacion = str(uuid.UUID(str(operacion_id))) if operacion_id is not None else ""
    except (TypeError, ValueError, AttributeError):
        operacion = ""
    return {"operacion_id": operacion, "estado": estado, "codigo": codigo, "mensaje": Rechazo.MENSAJES.get(codigo, "")}


def _auditar_rechazo(actor, intento_id, codigo):
    """`intento.sincronizacion_rechazada` con el intento y el código; sin la nota ni datos del paciente."""
    if intento_id is None or not IntentoEntrega.objects.filter(pk=intento_id).exists():
        return
    registrar_referencia(actor, "intento.sincronizacion_rechazada", IntentoEntrega._meta.label, f"{intento_id}:{codigo}")


def _codigo(error):
    for detalle in getattr(error, "error_list", None) or []:
        if detalle.code in Rechazo.CODIGOS:
            return detalle.code
    return Rechazo.INVALIDO


def _aplicar(actor, registro):
    if registro.resultado == ENTREGADA:
        return services.registrar_entregada(actor, registro.intento_id, registro.operacion_id,
                                            registrado_en=registro.registrado_en)
    return services.registrar_no_entregada(actor, registro.intento_id, registro.motivo, registro.nota,
                                           registro.operacion_id, registrado_en=registro.registrado_en)


def sincronizar_uno(actor, datos):
    operacion = datos.get("operacion_id") if isinstance(datos, dict) else None
    try:
        registro = leer_registro(datos)
    except RegistroNoValido as error:
        return _rechazar(actor, operacion, error.intento_id, error.codigo)
    if registro.cuenta != actor.pk:  # RF-11-11: nunca se aplica con la cuenta de otra sesión
        return _rechazar(actor, registro.operacion_id, registro.intento_id, Rechazo.OTRO_USUARIO)
    # Reenvío de algo ya aplicado: se responde sin tomar la cola del día. Solo lectura y seguro, porque un intento
    # registrado no cambia nunca; es la misma comprobación que hace el servicio antes de escribir.
    previo = IntentoEntrega.objects.filter(operacion_id=registro.operacion_id).values_list(
        "pk", "registrado_por_id", "resultado").first()
    if previo is not None:
        if previo == (registro.intento_id, actor.pk, registro.resultado):
            return _respuesta(registro.operacion_id, YA_APLICADO)
        return _rechazar(actor, registro.operacion_id, registro.intento_id, Rechazo.INVALIDO)
    try:
        resultado = _aplicar(actor, registro)
    except ConflictoOperacion:
        return _respuesta(registro.operacion_id, REINTENTAR)
    except PermissionDenied:
        codigo = Rechazo.NO_ASIGNADA
    except ValidationError as error:
        codigo = _codigo(error)
    except DatabaseError:
        return _respuesta(registro.operacion_id, REINTENTAR)
    else:
        return _respuesta(registro.operacion_id, YA_APLICADO if resultado.repetido else APLICADO)
    return _rechazar(actor, registro.operacion_id, registro.intento_id, codigo)


def _rechazar(actor, operacion, intento_id, codigo):
    try:
        _auditar_rechazo(actor, intento_id, codigo)
    except DatabaseError:  # sin auditoría no se da por cerrado: el celular lo vuelve a enviar
        return _respuesta(operacion, REINTENTAR)
    return _respuesta(operacion, RECHAZADO, codigo)


def sincronizar(actor, registros):
    """Un resultado por registro, en el mismo orden. El llamador limita el lote a MAXIMO_POR_LOTE."""
    return [sincronizar_uno(actor, datos) for datos in registros]
