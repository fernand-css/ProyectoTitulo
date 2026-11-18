"""Activación técnica local. Ningún servicio emite turnos ni publica eventos.

Los puntos públicos requieren autocommit y abren una transacción durable propia.
Así el retorno de secretos ocurre después del commit, nunca desde un savepoint.
Los rechazos esperados del consumo son resultados y conservan sus efectos.
"""
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.turnos.models import OperacionTurno
from .credenciales import _firmar_credencial
from .models import DispositivoTotem, EstadoActivacion


VIGENCIA_CODIGO = timedelta(minutes=5)
MAX_INTENTOS = 5
MAX_VERSION_CREDENCIAL = 2147483647
# Vocabulario cerrado: el motivo no puede transportar secretos ni texto personal.
MOTIVOS = ("alta", "sustitucion", "mantenimiento", "seguridad", "prueba_sintetica")


@dataclass(frozen=True)
class ResultadoActivacion:
    estado: str
    dispositivo_id: uuid.UUID
    referencia: uuid.UUID | None = None
    version: int | None = None
    codigo: str | None = field(default=None, repr=False)
    credencial: str | None = field(default=None, repr=False)


def _exigir_transaccion_propia():
    if connection.in_atomic_block or not connection.get_autocommit():
        raise RuntimeError("El servicio de tótem requiere autocommit y una transacción propia.")


def _uuid(valor):
    if isinstance(valor, uuid.UUID):
        return valor
    if not isinstance(valor, str) or len(valor) > 36:
        raise ValidationError("Identificador técnico inválido.")
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ValidationError("Identificador técnico inválido.") from None


def _autorizar(usuario, permiso):
    if not usuario or not usuario.is_authenticated or usuario.pk is None:
        raise PermissionDenied("No tiene permiso para esta operación.")
    # Instancia fresca: evita reutilizar _perm_cache o is_active de una sesión vieja.
    actual = get_user_model().objects.filter(pk=usuario.pk, is_active=True).first()
    if actual is None or not actual.has_perm("totem." + permiso):
        raise PermissionDenied("No tiene permiso para esta operación.")
    return actual


def _motivo(motivo):
    if motivo not in MOTIVOS:
        raise ValidationError("Debe seleccionar un motivo técnico admitido.")
    return motivo


def _bloquear(dispositivo_id):
    dispositivo = DispositivoTotem.objects.select_for_update().filter(pk=dispositivo_id).first()
    if dispositivo is not None:
        # No reparar datos externos ni aceptar una combinación fuera del modelo.
        dispositivo.full_clean()
        if dispositivo.estado_activacion == EstadoActivacion.PENDIENTE:
            try:
                identify_hasher(dispositivo.hash_activacion)
            except ValueError:
                raise ValidationError("El dispositivo requiere revisión de integridad.") from None
    return dispositivo


def _ahora(dispositivo):
    ahora = timezone.now()
    anteriores = [dispositivo.creado_en, dispositivo.actualizado_en]
    anteriores += [fecha for fecha in (
        dispositivo.activado_en, dispositivo.activacion_emitida_en,
        dispositivo.activacion_cerrada_en,
    ) if fecha is not None]
    if ahora < max(anteriores):
        raise ValidationError("Reloj anterior a la historia del dispositivo; requiere revisión.")
    return ahora


def _estado(dispositivo):
    return {
        "estado_activacion": dispositivo.estado_activacion,
        "activo": dispositivo.activo,
        "version": dispositivo.version_credencial,
        "intentos_fallidos": dispositivo.intentos_fallidos,
        "referencia": str(dispositivo.referencia_activacion) if dispositivo.referencia_activacion else None,
    }


def _guardar_auditar(dispositivo, usuario, accion, anteriores, motivo=None):
    dispositivo.save()
    detalles = {
        "entidad": "dispositivo_totem", "dispositivo_id": str(dispositivo.pk),
        "anteriores": anteriores, "nuevos": _estado(dispositivo),
    }
    if motivo is not None:
        detalles["motivo"] = motivo
    OperacionTurno.objects.create(
        turno=None, usuario=usuario, accion=accion, detalles=detalles,
    )


def _cerrar(dispositivo, estado, ahora):
    dispositivo.estado_activacion = estado
    dispositivo.hash_activacion = ""
    dispositivo.activacion_cerrada_en = ahora


def _caducar(dispositivo, ahora, usuario=None):
    if (
        dispositivo.estado_activacion == EstadoActivacion.PENDIENTE
        and ahora >= dispositivo.activacion_expira_en
    ):
        anteriores = _estado(dispositivo)
        _cerrar(dispositivo, EstadoActivacion.CADUCADO, ahora)
        _guardar_auditar(dispositivo, usuario, "TOTEM_CODIGO_CADUCADO", anteriores)
        return True
    return False


def _exigir_version_disponible(dispositivo):
    if dispositivo.version_credencial >= MAX_VERSION_CREDENCIAL:
        raise ValidationError("Versión agotada; requiere revisión autorizada del dispositivo.")


def _incrementar_version(dispositivo):
    _exigir_version_disponible(dispositivo)
    dispositivo.version_credencial += 1


def _requerir_dispositivo(dispositivo):
    if dispositivo is None:
        raise ValidationError("Dispositivo técnico inexistente.")


def generar_codigo_activacion(usuario, dispositivo_id, motivo):
    """Resultado generado con secreto de un solo retorno; no cambia activo/versión."""
    _exigir_transaccion_propia()
    dispositivo_id = _uuid(dispositivo_id)
    motivo = _motivo(motivo)
    with transaction.atomic(durable=True):
        usuario = _autorizar(usuario, "generar_codigos_activacion")
        dispositivo = _bloquear(dispositivo_id)
        _requerir_dispositivo(dispositivo)
        _exigir_version_disponible(dispositivo)
        ahora = _ahora(dispositivo)
        _caducar(dispositivo, ahora, usuario)
        if dispositivo.estado_activacion == EstadoActivacion.PENDIENTE:
            anteriores = _estado(dispositivo)
            _cerrar(dispositivo, EstadoActivacion.INVALIDADO, ahora)
            _guardar_auditar(dispositivo, usuario, "TOTEM_CODIGO_INVALIDADO", anteriores, "sustitucion")
        codigo = secrets.token_urlsafe(32)
        hash_codigo = make_password(codigo)
        # La vigencia comienza después del trabajo criptográfico.
        ahora = _ahora(dispositivo)
        anteriores = _estado(dispositivo)
        dispositivo.estado_activacion = EstadoActivacion.PENDIENTE
        dispositivo.referencia_activacion = uuid.uuid4()
        dispositivo.hash_activacion = hash_codigo
        dispositivo.activacion_emitida_en = ahora
        dispositivo.activacion_expira_en = ahora + VIGENCIA_CODIGO
        dispositivo.activacion_cerrada_en = None
        dispositivo.intentos_fallidos = 0
        _guardar_auditar(dispositivo, usuario, "TOTEM_CODIGO_GENERADO", anteriores, motivo)
        resultado = ResultadoActivacion(
            "generado", dispositivo.pk, dispositivo.referencia_activacion,
            dispositivo.version_credencial, codigo=codigo,
        )
    return resultado


def consumir_codigo_activacion(dispositivo_id, referencia, codigo):
    """Retorna activado/rechazado; un rechazo esperado no lanza una excepción.

    El adaptador debe presentar el mismo mensaje para todo rechazo. Una referencia
    vieja o entrada mal formada no consume los intentos del código vigente.
    """
    _exigir_transaccion_propia()
    try:
        dispositivo_id, referencia = _uuid(dispositivo_id), _uuid(referencia)
    except ValidationError:
        return ResultadoActivacion("rechazado", uuid.UUID(int=0))
    rechazado = ResultadoActivacion("rechazado", dispositivo_id)
    if not isinstance(codigo, str) or not 1 <= len(codigo) <= 128:
        return rechazado
    with transaction.atomic(durable=True):
        dispositivo = _bloquear(dispositivo_id)
        if dispositivo is None or dispositivo.referencia_activacion != referencia:
            resultado = rechazado
        elif dispositivo.estado_activacion != EstadoActivacion.PENDIENTE:
            resultado = rechazado
        elif _caducar(dispositivo, _ahora(dispositivo)):
            resultado = rechazado
        elif dispositivo.version_credencial >= MAX_VERSION_CREDENCIAL:
            resultado = rechazado
        else:
            coincide = check_password(codigo, dispositivo.hash_activacion)
            ahora = _ahora(dispositivo)
            # La comparación puede ser costosa: comprobar otra vez el vencimiento.
            if _caducar(dispositivo, ahora):
                resultado = rechazado
            elif not coincide:
                anteriores = _estado(dispositivo)
                dispositivo.intentos_fallidos += 1
                if dispositivo.intentos_fallidos == MAX_INTENTOS:
                    _cerrar(dispositivo, EstadoActivacion.INVALIDADO, ahora)
                _guardar_auditar(dispositivo, None, "TOTEM_INTENTO_FALLIDO", anteriores)
                if dispositivo.estado_activacion == EstadoActivacion.INVALIDADO:
                    # Evento de cierre adicional, dentro de la misma transacción.
                    OperacionTurno.objects.create(
                        turno=None, usuario=None, accion="TOTEM_CODIGO_INVALIDADO",
                        detalles={"entidad": "dispositivo_totem", "dispositivo_id": str(dispositivo.pk),
                                  "referencia": str(referencia), "causa": "maximo_intentos"},
                    )
                resultado = rechazado
            else:
                anteriores = _estado(dispositivo)
                _incrementar_version(dispositivo)
                _cerrar(dispositivo, EstadoActivacion.UTILIZADO, ahora)
                dispositivo.activo = True
                dispositivo.activado_en = ahora
                _guardar_auditar(dispositivo, None, "TOTEM_ACTIVADO", anteriores)
                credencial = _firmar_credencial(dispositivo, ahora)
                resultado = ResultadoActivacion(
                    "activado", dispositivo.pk, referencia, dispositivo.version_credencial,
                    credencial=credencial,
                )
    return resultado


def caducar_codigo_activacion(usuario, dispositivo_id):
    """Materializa solo el pendiente vencido; no revoca una activación anterior."""
    _exigir_transaccion_propia()
    dispositivo_id = _uuid(dispositivo_id)
    with transaction.atomic(durable=True):
        usuario = _autorizar(usuario, "caducar_codigos_activacion")
        dispositivo = _bloquear(dispositivo_id)
        _requerir_dispositivo(dispositivo)
        cambio = _caducar(dispositivo, _ahora(dispositivo), usuario)
        resultado = ResultadoActivacion(
            "caducado" if cambio else "sin_cambios", dispositivo.pk,
            dispositivo.referencia_activacion, dispositivo.version_credencial,
        )
    return resultado


def revocar_dispositivo(usuario, dispositivo_id, motivo):
    """Invalida autorización activa y pendiente; repetir no aumenta la versión."""
    _exigir_transaccion_propia()
    dispositivo_id, motivo = _uuid(dispositivo_id), _motivo(motivo)
    with transaction.atomic(durable=True):
        usuario = _autorizar(usuario, "revocar_dispositivos")
        dispositivo = _bloquear(dispositivo_id)
        _requerir_dispositivo(dispositivo)
        ahora = _ahora(dispositivo)
        caduco = _caducar(dispositivo, ahora, usuario)
        cambio = dispositivo.activo or dispositivo.estado_activacion == EstadoActivacion.PENDIENTE
        if cambio:
            anteriores = _estado(dispositivo)
            if dispositivo.estado_activacion == EstadoActivacion.PENDIENTE:
                _cerrar(dispositivo, EstadoActivacion.INVALIDADO, ahora)
                _guardar_auditar(dispositivo, usuario, "TOTEM_CODIGO_INVALIDADO", anteriores, motivo)
                anteriores = _estado(dispositivo)
            dispositivo.activo = False
            # En el máximo se revoca por activo=False; no habrá otra activación.
            if dispositivo.version_credencial < MAX_VERSION_CREDENCIAL:
                _incrementar_version(dispositivo)
            _guardar_auditar(dispositivo, usuario, "TOTEM_REVOCADO", anteriores, motivo)
        resultado = ResultadoActivacion(
            "revocado" if cambio else ("caducado" if caduco else "sin_cambios"),
            dispositivo.pk, dispositivo.referencia_activacion, dispositivo.version_credencial,
        )
    return resultado


def consultar_dispositivo(usuario, dispositivo_id):
    """Proyección administrativa segura: nunca retorna el modelo con su hash."""
    _autorizar(usuario, "consultar_dispositivos")
    dispositivo = DispositivoTotem.objects.filter(pk=_uuid(dispositivo_id)).first()
    _requerir_dispositivo(dispositivo)
    return {
        "dispositivo_id": str(dispositivo.pk), "alias": dispositivo.alias,
        **_estado(dispositivo), "estado_efectivo": dispositivo.estado_activacion_actual,
    }
