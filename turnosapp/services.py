"""Emisión pública transaccional; no confirma ni reserva entregas."""

import time
import uuid
from random import uniform
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F, Q
from django.utils import timezone

from coreapp.auditoria import registrar_accion
from coreapp.utils.rut import normalizar_rut
from recetasapp.models import Paciente, PreparacionReceta
from recetasapp.services import evaluar_elegibilidad
from .models import LETRA_POR_TIPO, ContadorTurnosDiario, IntentoTotem, Turno, TurnoReceta


class ErrorEmision(ValidationError):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje, code=codigo)


# RF-04-11: todo rechazo de un RUT con DV válido usa el mismo código y texto, para no revelar si la
# persona está en el padrón ni si tiene un despacho abierto.
CODIGO_RECHAZO = "rechazo"
MENSAJE_NEUTRO = "Acércate a la ventanilla para continuar tu atención."
ACTIVOS = (Turno.Estado.ESPERANDO, Turno.Estado.LLAMADO)


def rechazo_neutro():
    return ErrorEmision(CODIGO_RECHAZO, MENSAJE_NEUTRO)


class _Conflicto(Exception):
    pass


class _Recuperado(Exception):
    def __init__(self, turno):
        self.turno = turno


@dataclass(frozen=True)
class ResultadoEmision:
    numero: int
    letra: str
    codigo: str
    fecha: date
    creado_en: datetime
    recuperado: bool
    espera: str
    renovacion: bool = False


def _resultado(turno, recuperado, renovacion):
    from .espera import estimar_espera
    return ResultadoEmision(
        turno.numero, turno.letra, turno.codigo, turno.fecha, turno.creado_en, recuperado,
        estimar_espera().frase, renovacion,
    )


def _anterior(rut, fecha, operacion):
    """Turno de la misma operación o turno activo del RUT, siempre de la fecha de hoy (RF-04-06)."""
    turno = Turno.objects.filter(operacion_id=operacion).first()
    if turno is not None:
        # Otro RUT, una operación cerrada o de otro día: el mismo mensaje neutro.
        if turno.rut != rut or turno.estado not in ACTIVOS or turno.fecha != fecha:
            raise rechazo_neutro()
        return turno
    return Turno.objects.filter(rut=rut, fecha=fecha, estado__in=ACTIVOS).first()


def requiere_renovacion(paciente, fecha):
    """Alguna receta vencida o agotada que todavía no se renovó (RF-04-03/RF-04-11)."""
    if paciente is None:
        return False
    return paciente.recetas.filter(
        Q(fecha_fin_exclusiva__lte=fecha) | Q(entregas_completadas__gte=F("max_entregas")),
        renovaciones__isnull=True,
    ).exists()


def clasificar_atencion(paciente, fecha):
    """P para postrado o 60 años o más (incluye 80+); C para crónico; G para el resto y sin padrón.

    Enmienda 04 del 2026-11-15: `requiere_despacho_en` ya no bloquea la emisión; solo decide el reparto (08).
    """
    if paciente is None:
        return Turno.TipoAtencion.GENERAL
    if paciente.es_postrado or paciente.edad_en(fecha) >= 60:
        return Turno.TipoAtencion.PREFERENCIAL
    return Turno.TipoAtencion.CRONICOS if paciente.es_cronico else Turno.TipoAtencion.GENERAL


def _recetas_para_turno(paciente, fecha):
    """Recetas elegibles fuera de un despacho abierto; rechazo neutro si todas están en despacho."""
    if paciente is None:
        return []
    elegibles = [r for r in paciente.recetas.order_by("pk") if evaluar_elegibilidad(r, fecha)["elegible"]]
    if not elegibles:
        return []
    # Spec 08: las recetas de una entrega a domicilio abierta no se dispensan en farmacia.
    from entregasapp.consultas import recetas_con_despacho_abierto
    en_despacho = recetas_con_despacho_abierto(r.pk for r in elegibles)
    libres = [r for r in elegibles if r.pk not in en_despacho]
    if not libres:
        raise rechazo_neutro()  # Revierte la reserva: no se consume número.
    return libres


@transaction.atomic
def _emitir(rut, operacion):
    from .cola import bloquear_cola, cerrar_esperas_anteriores
    instante = timezone.now()
    fecha = timezone.localdate(instante)
    bloquear_cola(fecha)
    cerrar_esperas_anteriores(instante)
    # El tótem no crea pacientes: quien no está en el padrón recibe turno G sin recetas.
    paciente = Paciente.objects.filter(rut=rut).first()
    anterior = _anterior(rut, fecha, operacion)
    if anterior:
        return _resultado(anterior, True, requiere_renovacion(paciente, fecha))
    tipo = clasificar_atencion(paciente, fecha)

    # Cada letra tiene su propia serie diaria (enmienda 04 del 2026-11-15).
    letra = LETRA_POR_TIPO[tipo]
    contador, _ = ContadorTurnosDiario.objects.get_or_create(fecha=fecha, letra=letra)
    observado = contador.ultimo_numero
    if not ContadorTurnosDiario.objects.filter(pk=contador.pk, ultimo_numero=observado).update(ultimo_numero=F("ultimo_numero") + 1):
        raise _Conflicto
    # La reserva serializa emisores. Releer después de adquirir la escritura.
    releido = Paciente.objects.filter(rut=rut).first()
    if (releido and releido.pk) != (paciente and paciente.pk):
        raise _Conflicto  # Una importación agregó o cambió al paciente entre lecturas.
    paciente = releido
    if LETRA_POR_TIPO[clasificar_atencion(paciente, fecha)] != letra:
        raise _Conflicto  # La clasificación cambió entre lecturas: revierte la reserva y reintenta.
    anterior = _anterior(rut, fecha, operacion)
    if anterior:
        raise _Recuperado(anterior)  # Revierte la reserva que no se utilizará.
    recetas = _recetas_para_turno(paciente, fecha)
    turno = Turno.objects.create(
        paciente=paciente, rut=rut, fecha=fecha, letra=letra, numero=observado + 1,
        tipo_atencion=tipo, operacion_id=operacion,
    )
    for receta in recetas:
        vinculo = TurnoReceta(turno=turno, receta=receta)
        vinculo.full_clean()
        vinculo.save()
        PreparacionReceta.objects.create(
            turno_receta=vinculo,
            recibida_en=turno.creado_en,
        )
    try:
        registrar_accion(None, "turno.emitido", turno)
    except OperationalError:
        raise
    except Exception:
        raise RuntimeError("No se pudo registrar la emisión del turno.") from None
    from .cola import solicitar_seleccion
    solicitar_seleccion("emision", uuid.uuid5(turno.operacion_id, "seleccion"))
    return _resultado(turno, False, requiere_renovacion(paciente, fecha))


def emitir_turno(rut, operacion_id):
    """La vista debe vincular el UUID a su contexto de sesión antes de llamar.

    No acepta categoría, correlativo, fecha, actor ni recetas del navegador.
    Cada reintento abre una transacción nueva; no reutiliza transacciones rotas.
    """
    rut = normalizar_rut(rut)
    try:
        operacion = UUID(str(operacion_id))
    except (ValueError, TypeError, AttributeError):
        raise rechazo_neutro() from None
    from .cola import ConflictoCola
    for intento in range(12):
        try:
            return _emitir(rut, operacion)
        except _Recuperado as recuperado:
            turno = recuperado.turno
            return _resultado(turno, True, requiere_renovacion(turno.paciente, turno.fecha))
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
                "turnosapp_turno.rut", "turnosapp_turno.operacion_id",
                "turno_numero_letra_diario_unico", "turno_activo_rut_dia_unico",
                "contador_fecha_letra_unico",
                "turnosapp_turno_operacion_id_",
                "turnosapp_estadocoladiaria.fecha", "turnosapp_estadocoladiaria_fecha_",
            )):
                raise
        if intento < 11:
            time.sleep(min(0.02 * (2 ** intento), 0.12) + uniform(0, 0.02))
    raise ErrorEmision("ocupado", "El sistema está ocupado. Reintenta con la misma solicitud.")


# RF-04-12: como máximo 10 solicitudes por minuto por equipo (IP de origen y sesión).
LIMITE_INTENTOS = 10
CONSERVAR_VENTANAS = timedelta(minutes=10)
ACCION_LIMITE = "totem.limite_superado"


def _contar_intento(clave, ventana):
    """Suma una solicitud a la clave si queda bajo el límite; devuelve si fue aceptada.

    UPDATE condicional sobre la cantidad: PostgreSQL reevalúa el filtro tras esperar el bloqueo de
    la fila, así que nunca pasan más de `LIMITE_INTENTOS` por ventana. La primera solicitud de la
    ventana crea la fila; una colisión de la restricción única se reintenta como actualización.
    """
    for _ in range(8):
        if IntentoTotem.objects.filter(
            clave=clave, ventana=ventana, cantidad__lt=LIMITE_INTENTOS,
        ).update(cantidad=F("cantidad") + 1):
            return True
        fila = IntentoTotem.objects.filter(clave=clave, ventana=ventana).first()
        if fila is not None:
            if fila.cantidad < LIMITE_INTENTOS:
                continue  # Otra solicitud la creó entre ambas lecturas: reintentar el UPDATE.
            # Se audita una vez por clave y ventana, sin RUT ni datos de la petición.
            if IntentoTotem.objects.filter(pk=fila.pk, auditado=False).update(auditado=True):
                registrar_accion(None, ACCION_LIMITE, fila)
            return False
        try:
            with transaction.atomic():
                IntentoTotem.objects.create(clave=clave, ventana=ventana, cantidad=1)
        except IntegrityError:
            continue
        # Limpieza al escribir: las ventanas antiguas ya no cuentan.
        IntentoTotem.objects.filter(ventana__lt=ventana - CONSERVAR_VENTANAS).delete()
        return True
    raise ErrorEmision("ocupado", "El sistema está ocupado. Reintenta con la misma solicitud.")


@transaction.atomic
def registrar_intento_totem(claves, instante=None):
    """Cuenta una solicitud del tótem para cada clave (huellas, nunca el RUT).

    Devuelve False si alguna clave superó el límite del minuto en curso.
    """
    instante = instante or timezone.now()
    ventana = instante.replace(second=0, microsecond=0)
    aceptada = True
    for clave in claves:
        aceptada = _contar_intento(clave, ventana) and aceptada
    return aceptada
