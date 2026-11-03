"""Planificador transaccional compartido; sin transporte público ni voz."""
import hashlib
import logging
import time
import uuid
from datetime import timedelta
from random import uniform

from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, OperationalError, transaction
from django.db.models import F, Max
from django.utils import timezone

from coreapp.auditoria import registrar_accion
from coreapp.mixins import tiene_rol
from coreapp.roles import TECNICO
from .models import (
    ConfiguracionCola, EstadoColaDiaria, EventoTurno, OcupacionVentanilla,
    OperacionAtencion, PendienteSeleccion, Turno, Ventanilla,
)

logger = logging.getLogger(__name__)


class ConflictoCola(Exception):
    pass


class ColaNoPreparada(Exception):
    pass


def bloquear_cola(fecha):
    """Se llama dentro de atomic; comparte el orden de escritura con las acciones."""
    estado, _ = EstadoColaDiaria.objects.get_or_create(fecha=fecha)
    if not EstadoColaDiaria.objects.filter(pk=estado.pk, version=estado.version).update(version=F("version") + 1):
        raise ConflictoCola
    estado.refresh_from_db()
    return estado


def cerrar_esperas_anteriores(instante):
    """Mutación interna con la cola reservada; no cierra pacientes ya llamados."""
    fecha = timezone.localdate(instante)
    cantidad = 0
    for turno in Turno.objects.filter(fecha__lt=fecha, estado="esperando").order_by("fecha", "numero", "pk"):
        if not Turno.objects.filter(pk=turno.pk, estado="esperando").update(
            estado="sin_atencion_cierre", cerrado_en=instante, modificado_en=instante):
            raise ConflictoCola
        secuencia = (turno.eventos.aggregate(maximo=Max("secuencia"))["maximo"] or 0) + 1
        evento = EventoTurno.objects.create(turno=turno, secuencia=secuencia, accion="sin_atencion_cierre", instante=instante)
        registrar_accion(None, "turno.sin_atencion_cierre", evento)
        cantidad += 1
    return cantidad


@transaction.atomic
def cerrar_jornada_anterior():
    instante = timezone.now()
    if not Turno.objects.filter(fecha__lt=timezone.localdate(instante), estado="esperando").exists():
        return 0
    bloquear_cola(timezone.localdate(instante))
    return cerrar_esperas_anteriores(instante)


def espera_turno(turno, instante=None):
    segundos = max(0, int(((instante or timezone.now()) - turno.entrada_cola).total_seconds()))
    return {"segundos": segundos, "advertencia": segundos >= 720, "prioridad": segundos >= 900}


def solicitar_seleccion(motivo, operacion_id=None):
    """El llamador guarda este disparador dentro de su transacción de dominio."""
    pendiente, _ = PendienteSeleccion.objects.get_or_create(
        pk=operacion_id or uuid.uuid4(), defaults={"fecha": timezone.localdate(), "motivo": motivo},
    )
    transaction.on_commit(lambda: procesar_seguro(pendiente.pk))
    return pendiente


def _candidato(ventanilla, config, cursor, instante, fecha):
    tipos = list(ventanilla.tipos.values_list("codigo", flat=True))
    llamados = Turno.objects.filter(estado="llamado").values("paciente_id")
    candidatos = Turno.objects.filter(estado="esperando", fecha=fecha, tipo_atencion__in=tipos).exclude(
        paciente_id__in=llamados,
    ).order_by("entrada_cola", "numero", "pk")
    antiguo = candidatos.filter(entrada_cola__lte=instante - timedelta(minutes=15)).first()
    if antiguo:
        return antiguo, cursor
    # Tres intervalos, sin construir una lista proporcional al tamaño de los pesos.
    pesos = [("preferencial", config.peso_preferencial), ("cronicos", config.peso_cronicos), ("general", config.peso_general)]
    total = sum(peso for _, peso in pesos)
    cursor %= total
    inicio, posiciones = 0, []
    for tipo, peso in pesos:
        posicion = cursor if inicio <= cursor < inicio + peso else inicio
        posiciones.append(((posicion - cursor) % total, tipo, posicion))
        inicio += peso
    for _, tipo, posicion in sorted(posiciones):
        candidato = candidatos.filter(tipo_atencion=tipo).first()
        if candidato:
            return candidato, (posicion + 1) % total
    return None, cursor


@transaction.atomic
def _procesar(pendiente_id):
    pendiente = PendienteSeleccion.objects.get(pk=pendiente_id)
    if pendiente.estado == "procesado":
        return 0
    instante = timezone.now()
    fecha = timezone.localdate(instante)
    config = ConfiguracionCola.objects.filter(pk=1).first()
    if config is None:
        raise ColaNoPreparada
    estado = bloquear_cola(fecha)
    cerrar_esperas_anteriores(instante)
    # La escritura anterior serializa planificadores de la misma jornada.
    pendiente.refresh_from_db()
    if pendiente.estado == "procesado":
        return 0
    config.refresh_from_db()
    estado.refresh_from_db()
    cursor = estado.cursor if estado.version_configuracion == config.version else 0
    cantidad = 0
    disponibles = Ventanilla.objects.filter(
        habilitada=True, retirada=False, automatico=True, fecha_activacion=fecha,
        operador__isnull=False,
    ).exclude(turnos__estado="llamado").order_by("disponible_desde", "numero")
    for ventanilla in disponibles:
        if not Ventanilla.objects.filter(pk=ventanilla.pk, version=ventanilla.version,
                habilitada=True, retirada=False, automatico=True, fecha_activacion=fecha,
                operador_id=ventanilla.operador_id).update(version=F("version") + 1):
            raise ConflictoCola
        operador = get_user_model().objects.get(pk=ventanilla.operador_id)
        if not tiene_rol(operador, TECNICO):
            continue
        if not OcupacionVentanilla.objects.filter(ventanilla=ventanilla, tecnico=operador, cierre__isnull=True).exists():
            continue
        turno, nuevo_cursor = _candidato(ventanilla, config, cursor, instante, fecha)
        if turno is None:
            continue
        if not Turno.objects.filter(pk=turno.pk, estado="esperando", entrada_cola=turno.entrada_cola,
                ventanilla__isnull=True, operador__isnull=True).update(
                    estado="llamado", ventanilla=ventanilla, operador=operador,
                    ultimo_llamado=instante, modificado_por=operador, modificado_en=instante):
            raise ConflictoCola
        identidad = uuid.uuid5(pendiente.pk, f"llamar:{ventanilla.pk}:{turno.pk}")
        operacion = OperacionAtencion.objects.create(
            id=identidad, actor=operador, tipo="llamado_automatico", turno=turno, ventanilla=ventanilla,
            huella=hashlib.sha256(f"{turno.pk}:{ventanilla.pk}:{pendiente.pk}".encode()).hexdigest(),
        )
        secuencia = (turno.eventos.aggregate(maximo=Max("secuencia"))["maximo"] or 0) + 1
        evento = EventoTurno.objects.create(turno=turno, secuencia=secuencia, accion="llamado",
            instante=instante, actor=operador, ventanilla=ventanilla, operacion=operacion)
        operacion.resultado = {"turno": turno.pk, "ventanilla": ventanilla.pk, "evento": str(evento.pk)}
        operacion.save(update_fields=["resultado"])
        registrar_accion(operador, "turno.llamado", evento)
        cursor = nuevo_cursor
        cantidad += 1
    EstadoColaDiaria.objects.filter(pk=estado.pk).update(cursor=cursor, version_configuracion=config.version)
    PendienteSeleccion.objects.filter(pk=pendiente.pk).update(estado="procesado", procesado_en=instante,
        ultimo_intento=instante, intentos=F("intentos") + 1, version=F("version") + 1, codigo_fallo="")
    return cantidad


def procesar_pendiente(pendiente_id):
    """Reintentos siempre fuera de atomic; errores de auditoría no son éxitos."""
    for intento in range(12):
        try:
            return _procesar(pendiente_id)
        except ConflictoCola:
            pass
        except OperationalError as error:
            if not any(marca in str(error).lower() for marca in ("locked", "busy")):
                raise
        except IntegrityError as error:
            if not any(marca in str(error).lower() for marca in (
                "turno_llamado_", "turno_activo_paciente_dia_unico", "turnosapp_turno.",
                "turnosapp_estadocoladiaria.fecha", "turnosapp_estadocoladiaria_fecha_",
            )):
                raise
        if intento < 11:
            time.sleep(min(.02 * 2 ** intento, .12) + uniform(0, .02))
    raise ConflictoCola("La cola está ocupada; el pendiente se conserva.")


def procesar_seguro(pendiente_id):
    try:
        return procesar_pendiente(pendiente_id)
    except Exception as error:
        codigo = "sin_configuracion" if isinstance(error, ColaNoPreparada) else "seleccion_pendiente"
        try:
            PendienteSeleccion.objects.filter(pk=pendiente_id, estado="pendiente").update(
                codigo_fallo=codigo, intentos=F("intentos") + 1, ultimo_intento=timezone.now())
        except DatabaseError:
            pass  # El disparador original ya está confirmado y sigue pendiente.
        if codigo != "sin_configuracion":
            logger.error("Selección automática pendiente de recuperar.")
        return None


def procesar_pendientes(limite=100):
    try:
        cerrar_jornada_anterior()
    except (DatabaseError, ConflictoCola):
        logger.error("Cierre de jornada pendiente de recuperar.")
        return 0
    pendientes = list(PendienteSeleccion.objects.filter(estado="pendiente").order_by("creado_en", "pk").values_list("pk", flat=True)[:limite])
    return sum(procesar_seguro(identificador) or 0 for identificador in pendientes)
