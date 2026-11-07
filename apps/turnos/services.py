"""Único punto de mutación del dominio; todas las operaciones usan PostgreSQL."""
from functools import partial

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.pacientes.models import Paciente
from .dominio import ACTIVOS, OCUPAN_VENTANILLA, seleccionar, validar_peso, validar_transicion
from .models import Categoria, ContadorTurno, Estado, EstadoCola, OperacionTurno, Turno, Ventanilla
from .notificaciones import publicar


def autorizar(usuario, permiso):
    if not usuario or not usuario.is_authenticated or not usuario.is_active or not usuario.has_perm(permiso):
        raise PermissionDenied("No tiene permiso para esta operación.")


def bloquear_cola():
    # El get_or_create resuelve también la primera emisión concurrente por PK única.
    EstadoCola.objects.get_or_create(pk=1)
    cola = EstadoCola.objects.select_for_update().get(pk=1)
    hoy = timezone.localdate()
    if cola.fecha_jornada != hoy:
        cola.fecha_jornada = hoy
        cola.siguiente_categoria = Categoria.GENERAL
        cola.consumidos = 0
        cola.save()
    return cola


def registrar(turno, usuario, accion, detalles=None):
    operacion = OperacionTurno.objects.create(
        turno=turno, usuario=usuario, accion=accion, detalles=detalles or {},
    )
    if turno is not None:
        evento = {
            "evento_id": operacion.pk,
            "turno_id": turno.pk,
            "version": turno.version,
            "accion": accion,
            "fecha_jornada": turno.fecha_jornada.isoformat(),
            "numero": turno.numero_visible,
            "categoria": turno.categoria,
            "estado": turno.estado,
            "ventanilla": turno.ventanilla.numero if turno.ventanilla_id else None,
        }
        transaction.on_commit(partial(publicar, evento))
    return operacion


def _validar_ocupacion(ventanilla, turno):
    """Detectar inconsistencias externas sin reparar ni transferir turnos."""
    if turno is not None and (
        ventanilla is None
        or not ventanilla.habilitada
        or ventanilla.operador_id is None
        or turno.ventanilla_id != ventanilla.pk
        or turno.operador_id != ventanilla.operador_id
    ):
        raise ValidationError(
            "La ventanilla ocupada presenta una inconsistencia; requiere revisión autorizada.",
            code="ventanilla_inconsistente",
        )


def _bloquear_turno_y_ventanilla(turno_id):
    """El llamador ya bloqueó la cola: ventanilla antes que turno.

    La primera lectura solo permite localizar la ventanilla. La referencia se
    revalida después de adquirir ambos bloqueos, incluso ante escrituras externas.
    """
    ventanilla_id = Turno.objects.values_list("ventanilla_id", flat=True).get(pk=turno_id)
    ventanilla = (
        Ventanilla.objects.select_for_update().get(pk=ventanilla_id)
        if ventanilla_id is not None else None
    )
    turno = Turno.objects.select_for_update().get(pk=turno_id)
    if turno.ventanilla_id != ventanilla_id:
        raise ValidationError(
            "La referencia de ventanilla cambió durante la operación.",
            code="ventanilla_inconsistente",
        )
    if turno.estado in OCUPAN_VENTANILLA:
        _validar_ocupacion(ventanilla, turno)
    return turno, ventanilla


@transaction.atomic
def configurar_ventanilla(usuario, ventanilla_id, habilitada, operador_id, motivo):
    """Configurar una ventanilla existente, sin modificar turnos históricos."""
    autorizar(usuario, "turnos.configurar_ventanillas")
    if type(ventanilla_id) is not int or ventanilla_id < 1:
        raise ValidationError("Identificador de ventanilla inválido.")
    if type(habilitada) is not bool:
        raise ValidationError("La habilitación debe ser un booleano.")
    if operador_id is not None and (type(operador_id) is not int or operador_id < 1):
        raise ValidationError("Identificador de operador inválido.")

    bloquear_cola()
    ventanilla = Ventanilla.objects.select_for_update().get(pk=ventanilla_id)
    ocupante = Turno.objects.select_for_update().filter(
        ventanilla=ventanilla, estado__in=OCUPAN_VENTANILLA,
    ).first()
    _validar_ocupacion(ventanilla, ocupante)
    anteriores = {"habilitada": ventanilla.habilitada, "operador_id": ventanilla.operador_id}
    nuevos = {"habilitada": habilitada, "operador_id": operador_id}
    if anteriores == nuevos:
        return ventanilla
    if ocupante is not None:
        raise ValidationError(
            "No puede deshabilitar, reasignar ni retirar el operador de una ventanilla ocupada.",
            code="ventanilla_ocupada",
        )
    if not isinstance(motivo, str) or not motivo.strip():
        raise ValidationError("Debe indicar el motivo de la modificación.")
    if habilitada and operador_id is None:
        raise ValidationError("Una ventanilla habilitada requiere un operador.")
    if operador_id is not None:
        try:
            operador = get_user_model().objects.get(pk=operador_id)
        except get_user_model().DoesNotExist as exc:
            raise ValidationError("El operador no existe.") from exc
        if not operador.is_active or not operador.has_perm("turnos.operar_turnos"):
            raise ValidationError("El operador debe estar activo y autorizado para operar turnos.")
        if Ventanilla.objects.filter(operador_id=operador_id).exclude(pk=ventanilla.pk).exists():
            raise ValidationError("El operador ya está asignado a otra ventanilla.")
    ventanilla.habilitada = habilitada
    ventanilla.operador_id = operador_id
    ventanilla.save(update_fields=["habilitada", "operador"])
    registrar(None, usuario, "VENTANILLA_CONFIGURADA", {
        "entidad": "ventanilla", "ventanilla_id": ventanilla.pk,
        "numero": ventanilla.numero, "anteriores": anteriores,
        "nuevos": nuevos, "motivo": motivo.strip(),
    })
    return ventanilla


@transaction.atomic
def emitir(identificador_sintetico, categoria):
    if categoria not in Categoria.values:
        raise ValidationError("Seleccione GENERAL o PREFERENCIAL.")
    bloquear_cola()
    try:
        paciente = Paciente.objects.select_for_update().get(
            identificador_sintetico=identificador_sintetico, activo=True,
        )
    except Paciente.DoesNotExist as exc:
        raise ValidationError("Identificador sintético no habilitado para la demostración.") from exc
    existente = Turno.objects.filter(paciente=paciente, estado__in=ACTIVOS).first()
    if existente:
        # No modifica la categoría de un turno ya emitido ni consume otro correlativo.
        return existente, False
    hoy = timezone.localdate()
    contador, _ = ContadorTurno.objects.get_or_create(fecha_jornada=hoy, categoria=categoria)
    contador.ultimo += 1
    contador.save(update_fields=["ultimo"])
    turno = Turno.objects.create(
        paciente=paciente, fecha_jornada=hoy, categoria=categoria, correlativo=contador.ultimo,
    )
    registrar(turno, None, "EMITIDO")
    return turno, True


@transaction.atomic
def llamar_siguiente(ventanilla_id, usuario):
    autorizar(usuario, "turnos.operar_turnos")
    cola = bloquear_cola()
    ventanilla = Ventanilla.objects.select_for_update().get(pk=ventanilla_id)
    if not ventanilla.habilitada or ventanilla.operador_id != usuario.pk:
        raise PermissionDenied("La ventanilla no está habilitada o asignada a usted.")
    actual = Turno.objects.select_for_update().filter(
        ventanilla=ventanilla, estado__in=OCUPAN_VENTANILLA,
    ).first()
    _validar_ocupacion(ventanilla, actual)
    if actual:
        return actual, False
    # El bloqueo global fija el orden de arbitraje y evita saltar al primero bloqueado.
    primeros = {
        categoria: Turno.objects.filter(
            fecha_jornada=cola.fecha_jornada, categoria=categoria, estado=Estado.PENDIENTE,
        ).order_by("emitido", "pk").first()
        for categoria in Categoria.values
    }
    seleccion = seleccionar(
        cola.peso_general, cola.peso_preferencial, cola.siguiente_categoria,
        cola.consumidos, {categoria for categoria, turno in primeros.items() if turno},
    )
    cola.siguiente_categoria = seleccion.siguiente_categoria
    cola.consumidos = seleccion.consumidos
    cola.save(update_fields=["siguiente_categoria", "consumidos"])
    if seleccion.categoria is None:
        return None, False
    turno = Turno.objects.select_for_update().get(pk=primeros[seleccion.categoria].pk)
    ahora = timezone.now()
    turno.estado = Estado.LLAMADO
    turno.ventanilla = ventanilla
    turno.operador = usuario
    turno.primer_llamado = ahora
    turno.ultimo_llamado = ahora
    turno.version += 1
    turno.save()
    registrar(turno, usuario, "LLAMADO")
    return turno, True


@transaction.atomic
def cambiar_estado(turno_id, usuario, destino):
    permiso = "turnos.cancelar_turnos" if destino == Estado.CANCELADO else "turnos.operar_turnos"
    autorizar(usuario, permiso)
    bloquear_cola()
    turno, ventanilla = _bloquear_turno_y_ventanilla(turno_id)
    if destino not in (Estado.EN_ATENCION, Estado.ATENDIDO, Estado.AUSENTE, Estado.CANCELADO):
        raise ValidationError("Use la operación de llamado para asignar el turno.")
    try:
        validar_transicion(turno.estado, destino)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if destino != Estado.CANCELADO:
        # Verificación actual de la asignación además de la autoría histórica.
        if ventanilla is None or turno.operador_id != usuario.pk or ventanilla.operador_id != usuario.pk:
            raise PermissionDenied("El turno no corresponde a su ventanilla.")
    anterior = turno.estado
    turno.estado = destino
    if destino == Estado.EN_ATENCION:
        turno.inicio_atencion = timezone.now()
    else:
        turno.cierre = timezone.now()
    turno.version += 1
    turno.save()
    registrar(turno, usuario, destino, {"estado_anterior": anterior})
    return turno


@transaction.atomic
def rellamar(turno_id, usuario):
    autorizar(usuario, "turnos.operar_turnos")
    bloquear_cola()
    turno, ventanilla = _bloquear_turno_y_ventanilla(turno_id)
    if turno.estado != Estado.LLAMADO:
        raise ValidationError("Solo puede re-llamar un turno en estado LLAMADO.")
    if ventanilla is None or turno.operador_id != usuario.pk or ventanilla.operador_id != usuario.pk:
        raise PermissionDenied("El turno no corresponde a su ventanilla.")
    turno.ultimo_llamado = timezone.now()
    turno.version += 1
    turno.save(update_fields=["ultimo_llamado", "version"])
    registrar(turno, usuario, "RELLAMADO")
    return turno


@transaction.atomic
def configurar_pesos(usuario, peso_general, peso_preferencial):
    autorizar(usuario, "turnos.configurar_cola")
    try:
        validar_peso(peso_general)
        validar_peso(peso_preferencial)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    cola = bloquear_cola()
    anteriores = [cola.peso_general, cola.peso_preferencial]
    cola.peso_general = peso_general
    cola.peso_preferencial = peso_preferencial
    # Cada cambio de pesos comienza un ciclo, sin créditos previos.
    cola.siguiente_categoria = Categoria.GENERAL
    cola.consumidos = 0
    cola.save()
    registrar(None, usuario, "PESOS_CONFIGURADOS", {
        "anteriores": anteriores, "nuevos": [peso_general, peso_preferencial],
    })
    return cola
