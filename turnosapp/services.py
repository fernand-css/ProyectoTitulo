"""Emisión pública transaccional; no confirma ni reserva entregas."""

import time
import uuid
from random import uniform
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F, Q
from django.utils import timezone

from coreapp.auditoria import registrar_accion
from coreapp.utils.rut import normalizar_rut
from recetasapp.models import Paciente
from recetasapp.services import evaluar_elegibilidad
from .models import ContadorTurnosDiario, Turno, TurnoReceta


class ErrorEmision(ValidationError):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje, code=codigo)


class _Conflicto(Exception):
    pass


class _Recuperado(Exception):
    def __init__(self, turno):
        self.turno = turno


@dataclass(frozen=True)
class ResultadoEmision:
    numero: int
    fecha: date
    creado_en: datetime
    recuperado: bool


def _resultado(turno, recuperado):
    return ResultadoEmision(turno.numero, turno.fecha, turno.creado_en, recuperado)


def _anterior(paciente, fecha, operacion):
    turno = Turno.objects.filter(operacion_id=operacion).first()
    if turno is not None:
        if turno.paciente_id != paciente.pk:
            raise ErrorEmision("operacion_invalida", "La operación no es válida. Inicia una nueva atención.")
        if turno.estado not in ("esperando", "llamado"):
            raise ErrorEmision("operacion_cerrada", "Esta solicitud ya está cerrada. Inicia una nueva atención.")
        return turno
    return Turno.objects.filter(Q(estado="esperando", fecha=fecha) | Q(estado="llamado"), paciente=paciente).first()


def clasificar_atencion(paciente, fecha):
    nacimiento = paciente.fecha_nacimiento
    edad = fecha.year - nacimiento.year - ((fecha.month, fecha.day) < (nacimiento.month, nacimiento.day))
    if paciente.es_postrado or edad > 80:
        raise ErrorEmision("domicilio", "Consulta tu despacho con el personal.")
    if edad >= 60:
        return Turno.TipoAtencion.PREFERENCIAL
    return Turno.TipoAtencion.CRONICOS if paciente.es_cronico else Turno.TipoAtencion.GENERAL


@transaction.atomic
def _emitir(rut, operacion):
    from .cola import bloquear_cola, cerrar_esperas_anteriores
    instante = timezone.now()
    fecha = timezone.localdate(instante)
    bloquear_cola(fecha)
    cerrar_esperas_anteriores(instante)
    paciente = Paciente.objects.filter(rut=rut).first()
    if paciente is None:
        raise ErrorEmision("no_registrado", "Consulta con el personal para obtener atención.")
    tipo = clasificar_atencion(paciente, fecha)
    anterior = _anterior(paciente, fecha, operacion)
    if anterior:
        return _resultado(anterior, True)

    contador, _ = ContadorTurnosDiario.objects.get_or_create(fecha=fecha)
    observado = contador.ultimo_numero
    if not ContadorTurnosDiario.objects.filter(pk=contador.pk, ultimo_numero=observado).update(ultimo_numero=F("ultimo_numero") + 1):
        raise _Conflicto
    # La reserva serializa emisores. Releer después de adquirir la escritura.
    paciente.refresh_from_db()
    tipo = clasificar_atencion(paciente, fecha)
    anterior = _anterior(paciente, fecha, operacion)
    if anterior:
        raise _Recuperado(anterior)  # Revierte la reserva que no se utilizará.
    recetas = list(paciente.recetas.order_by("pk"))
    elegibles = [r for r in recetas if evaluar_elegibilidad(r, fecha)["elegible"]]
    if not elegibles:
        renovacion = any(fecha >= r.fecha_fin_exclusiva or r.entregas_completadas >= r.max_entregas for r in recetas)
        mensaje = "No hay recetas disponibles. Consulta con el personal."
        if renovacion:
            mensaje = "Requiere renovación de receta. Consulta con el personal."
        raise ErrorEmision("sin_receta", mensaje)
    turno = Turno.objects.create(
        paciente=paciente, fecha=fecha, numero=observado + 1,
        tipo_atencion=tipo, operacion_id=operacion,
    )
    for receta in elegibles:
        vinculo = TurnoReceta(turno=turno, receta=receta)
        vinculo.full_clean()
        vinculo.save()
    try:
        registrar_accion(None, "turno.emitido", turno)
    except OperationalError:
        raise
    except Exception:
        raise RuntimeError("No se pudo registrar la emisión del turno.") from None
    from .cola import solicitar_seleccion
    solicitar_seleccion("emision", uuid.uuid5(turno.operacion_id, "seleccion"))
    return _resultado(turno, False)


def emitir_turno(rut, operacion_id):
    """La vista debe vincular el UUID a su contexto de sesión antes de llamar.

    No acepta categoría, correlativo, fecha, actor ni recetas del navegador.
    Cada reintento abre una transacción nueva; no reutiliza transacciones rotas.
    """
    rut = normalizar_rut(rut)
    try:
        operacion = UUID(str(operacion_id))
    except (ValueError, TypeError, AttributeError):
        raise ErrorEmision("operacion_invalida", "La operación no es válida. Inicia una nueva atención.") from None
    from .cola import ConflictoCola
    for intento in range(12):
        try:
            return _emitir(rut, operacion)
        except _Recuperado as recuperado:
            return _resultado(recuperado.turno, True)
        except (_Conflicto, ConflictoCola):
            pass
        except OperationalError as error:
            if not any(marca in str(error).lower() for marca in ("locked", "busy")):
                raise
        except IntegrityError as error:
            # Solo las colisiones de las identidades de emisión son reintentables.
            detalle = str(error).lower()
            if not any(marca in detalle for marca in (
                "turnosapp_contadorturnosdiario.fecha", "turnosapp_turno.fecha",
                "turnosapp_turno.paciente_id", "turnosapp_turno.operacion_id",
                "turno_numero_diario_unico", "turno_activo_paciente_dia_unico",
                "turnosapp_turno_operacion_id_", "turnosapp_contadorturnosdiario_fecha_",
                "turnosapp_estadocoladiaria.fecha", "turnosapp_estadocoladiaria_fecha_",
            )):
                raise
        if intento < 11:
            time.sleep(min(0.02 * (2 ** intento), 0.12) + uniform(0, 0.02))
    raise ErrorEmision("ocupado", "El sistema está ocupado. Reintenta con la misma solicitud.")
