"""Operaciones de farmacia autorizadas, transaccionales y auditadas."""

import calendar
import hashlib
import time
from datetime import timedelta
from functools import wraps
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F, Max
from django.utils import timezone

from coreapp.auditoria import registrar_accion
from coreapp.mixins import tiene_rol
from coreapp.roles import JEFA, TECNICO
from .models import EntregaReceta, Paciente, PreparacionReceta, Receta


class ConflictoOperacion(ValidationError):
    pass


def autorizar(actor, *roles):
    if not tiene_rol(actor, *roles):
        raise PermissionDenied


def reintentar_conflictos(funcion):
    """Reabrir la transacción tras colisiones; nunca reutilizar una rota."""
    @wraps(funcion)
    def ejecutar(*args, **kwargs):
        for intento in range(8):
            try:
                return funcion(*args, **kwargs)
            except OperationalError as error:
                if not any(marca in str(error).lower() for marca in ("locked", "busy")):
                    raise
            except ConflictoOperacion:
                pass
            if intento < 7:
                time.sleep(0.015 * (intento + 1))
        raise OperationalError("La operación está ocupada. Inténtalo nuevamente con la misma confirmación.")
    return ejecutar


def auditar(actor, accion, objeto):
    try:
        return registrar_accion(actor, accion, objeto)
    except ValidationError:
        raise RuntimeError("No se pudo registrar la auditoría de farmacia.") from None


def calcular_fin(inicio, meses):
    if not isinstance(meses, int) or isinstance(meses, bool) or meses < 1:
        raise ValidationError("La vigencia debe ser un número entero positivo de meses.")
    try:
        anio, mes = divmod(inicio.year * 12 + inicio.month - 1 + meses, 12)
        return inicio.replace(year=anio, month=mes + 1, day=min(inicio.day, calendar.monthrange(anio, mes + 1)[1]))
    except (ValueError, OverflowError, TypeError):
        raise ValidationError("El período de vigencia está fuera del calendario admitido.") from None


def evaluar_elegibilidad(receta, fecha=None):
    fecha = fecha or timezone.localdate()
    causas = []
    if fecha < receta.fecha_inicio:
        causas.append("La receta aún no inicia su vigencia.")
    if fecha >= receta.fecha_fin_exclusiva:
        causas.append("La receta está vencida; requiere renovación.")
    if receta.entregas_completadas >= receta.max_entregas:
        causas.append("La receta agotó sus entregas; requiere renovación.")
    return {
        "elegible": not causas, "causas": causas,
        "fecha_inicio": receta.fecha_inicio,
        "ultimo_dia_valido": receta.fecha_fin_exclusiva - timedelta(days=1),
        "completadas": receta.entregas_completadas, "maximo": receta.max_entregas,
        "restantes": max(0, receta.max_entregas - receta.entregas_completadas),
    }


def _nueva_receta(actor, paciente, datos, anterior=None):
    receta = Receta(
        paciente=paciente, receta_anterior=anterior, creado_por=actor, modificado_por=actor,
        fecha_fin_exclusiva=calcular_fin(datos["fecha_inicio"], datos["vigencia_meses"]), **datos,
    )
    receta.full_clean()
    receta.save()
    auditar(actor, "receta.creada", receta)
    if anterior:
        auditar(actor, "receta.renovada", receta)
    return receta


@reintentar_conflictos
@transaction.atomic
def crear_receta(actor, *, paciente_id, codigo, fecha_inicio, vigencia_meses, max_entregas, anterior_id=None):
    autorizar(actor, JEFA)
    paciente = Paciente.objects.get(pk=paciente_id)
    anterior = Receta.objects.get(pk=anterior_id) if anterior_id else None
    if anterior and anterior.paciente_id != paciente.pk:
        raise ValidationError("La renovación debe corresponder al mismo paciente.")
    try:
        with transaction.atomic():
            return _nueva_receta(actor, paciente, {
                "codigo": codigo.strip(), "fecha_inicio": fecha_inicio,
                "vigencia_meses": vigencia_meses, "max_entregas": max_entregas,
            }, anterior)
    except IntegrityError:
        raise ValidationError("El código de receta ya existe o sus datos no son válidos.") from None


_CONTEXTO_AUTOMATICO = object()


def _registrar_entrega_sin_reintento(actor, receta_id, operacion_id, *,
        turno_receta_id=_CONTEXTO_AUTOMATICO, contador_esperado=None, fecha=None,
        desde_preparado=None):
    """Requiere atomic y cola reservada. El llamador reintenta la unidad completa."""
    autorizar(actor, JEFA, TECNICO) if desde_preparado is not None else autorizar(actor, TECNICO)
    from turnosapp.models import TurnoReceta
    try:
        operacion_id = UUID(str(operacion_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("La confirmación de entrega no es válida.") from None
    previa = EntregaReceta.objects.filter(operacion_id=operacion_id).first()
    if previa:
        if previa.receta_id != receta_id or previa.creado_por_id != actor.pk:
            raise ValidationError("La confirmación no corresponde a esta operación.")
        if turno_receta_id is not _CONTEXTO_AUTOMATICO and previa.turno_receta_id != turno_receta_id:
            raise ValidationError("La confirmación no corresponde a esta atención.")
        return previa
    activo = TurnoReceta.objects.filter(receta_id=receta_id, turno__estado="llamado").first()
    if turno_receta_id is _CONTEXTO_AUTOMATICO:
        vinculo = activo
    elif turno_receta_id is None:
        if activo:
            raise ValidationError("La atención cambió. Abre nuevamente la confirmación.")
        vinculo = None
    else:
        vinculo = TurnoReceta.objects.select_related("turno").filter(pk=turno_receta_id, receta_id=receta_id).first()
        if vinculo is None:
            raise ValidationError("La receta no corresponde a esta atención.")
    if desde_preparado is not None and (
        desde_preparado.turno_receta_id != getattr(vinculo, "pk", None)
        or desde_preparado.lista_en is None
        or vinculo.turno.estado not in ("ausente", "sin_atencion_cierre", "atendido", "cerrado_sin_entrega")
    ):
        raise ValidationError("La preparación ya no está pendiente de retiro.")
    if vinculo:
        asociada = EntregaReceta.objects.filter(turno_receta=vinculo).first()
        if asociada:
            if desde_preparado is not None:
                raise ValidationError("La receta ya fue entregada.")
            return asociada  # Conservar actor/fecha reales, sin otro descuento.
        if vinculo.turno.estado != "llamado" and desde_preparado is None:
            raise ValidationError("La atención ya no está vigente. Revisa su resultado.")
    receta = Receta.objects.get(pk=receta_id)
    if contador_esperado is not None and receta.entregas_completadas != contador_esperado:
        raise ValidationError("La receta cambió. Revisa las entregas antes de confirmar.")
    hoy = fecha or timezone.localdate()
    estado = evaluar_elegibilidad(receta, hoy)
    if not estado["elegible"]:
        raise ValidationError(estado["causas"])
    actualizadas = Receta.objects.filter(
        pk=receta.pk, entregas_completadas=receta.entregas_completadas,
        entregas_completadas__lt=F("max_entregas"),
        fecha_inicio__lte=hoy, fecha_fin_exclusiva__gt=hoy,
    ).update(entregas_completadas=F("entregas_completadas") + 1, modificado_por=actor, modificado_en=timezone.now())
    if not actualizadas:
        raise ConflictoOperacion("La receta cambió durante la confirmación.")
    try:
        with transaction.atomic():
            entrega = EntregaReceta.objects.create(
                receta=receta, numero=receta.entregas_completadas + 1,
                operacion_id=operacion_id, creado_por=actor, modificado_por=actor,
                turno_receta=vinculo,
            )
    except IntegrityError:
        raise ConflictoOperacion("La confirmación ya está siendo procesada.") from None
    auditar(actor, "receta.entrega", entrega)
    return entrega


@reintentar_conflictos
@transaction.atomic
def registrar_entrega(actor, receta_id, operacion_id, *, turno_receta_id=_CONTEXTO_AUTOMATICO, contador_esperado=None):
    from turnosapp.cola import bloquear_cola, ConflictoCola
    from turnosapp.models import OperacionAtencion
    autorizar(actor, TECNICO)
    try:
        bloquear_cola(timezone.localdate())
    except ConflictoCola:
        raise ConflictoOperacion("La atención cambió durante la confirmación.") from None
    try:
        identidad = UUID(str(operacion_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("La confirmación de entrega no es válida.") from None
    operacion = OperacionAtencion.objects.filter(pk=identidad).first()
    if operacion:
        datos = operacion.resultado
        if operacion.tipo != "entrega_receta" or operacion.actor_id != actor.pk or datos.get("receta") != receta_id:
            raise ValidationError("La confirmación no corresponde a esta operación.")
        if turno_receta_id is not _CONTEXTO_AUTOMATICO and datos.get("turno_receta") != turno_receta_id:
            raise ValidationError("La confirmación no corresponde a esta atención.")
        return EntregaReceta.objects.get(pk=datos["entrega"])
    entrega = _registrar_entrega_sin_reintento(actor, receta_id, identidad,
        turno_receta_id=turno_receta_id, contador_esperado=contador_esperado)
    if entrega.turno_receta_id:
        vinculo = entrega.turno_receta
        operacion = OperacionAtencion.objects.create(id=identidad, actor=actor, tipo="entrega_receta",
            turno_id=vinculo.turno_id, huella=hashlib.sha256(f"{receta_id}:{vinculo.pk}".encode()).hexdigest(),
            resultado={"entrega": entrega.pk, "receta": receta_id, "turno_receta": vinculo.pk})
        if entrega.operacion_id != identidad:
            auditar(actor, "receta.entrega_recuperada", operacion)
    return entrega


def _preparacion_activa(preparacion_id, hoy):
    preparacion = PreparacionReceta.objects.select_related("turno_receta__turno").filter(pk=preparacion_id).first()
    if preparacion is None:
        raise ValidationError("La preparación ya no está disponible.")
    turno = preparacion.turno_receta.turno
    if turno.fecha != hoy or turno.estado not in ("esperando", "llamado"):
        raise ValidationError("La atención ya no está activa en esta jornada.")
    return preparacion


@reintentar_conflictos
@transaction.atomic
def marcar_lista(actor, preparacion_id):
    """Marca una preparación una vez y conserva el intervalo medido."""
    from turnosapp.cola import bloquear_cola, ConflictoCola

    autorizar(actor, JEFA, TECNICO)
    actor = get_user_model().objects.get(pk=actor.pk)
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    try:
        bloquear_cola(hoy)
    except ConflictoCola:
        raise ConflictoOperacion("La cola cambió. Vuelve a cargar la preparación.") from None
    preparacion = _preparacion_activa(preparacion_id, hoy)
    if preparacion.lista_en is not None:
        return preparacion

    anterior = PreparacionReceta.objects.filter(
        lista_por=actor, lista_en__date=hoy,
    ).exclude(pk=preparacion.pk).aggregate(ultimo=Max("lista_en"))["ultimo"]
    inicio = max(preparacion.recibida_en, anterior) if anterior else preparacion.recibida_en
    duracion = max(0, int((ahora - inicio).total_seconds()))
    actualizadas = PreparacionReceta.objects.filter(
        pk=preparacion.pk, lista_en__isnull=True,
    ).update(
        lista_en=ahora, lista_por=actor, inicio_medido=inicio,
        duracion_segundos=duracion, modificado_por=actor, modificado_en=ahora,
    )
    if not actualizadas:
        preparacion.refresh_from_db()
        if preparacion.lista_en is not None:
            return preparacion
        raise ConflictoOperacion("La preparación cambió durante la operación.")
    preparacion.refresh_from_db()
    auditar(actor, "preparacion.lista", preparacion)
    return preparacion


@reintentar_conflictos
@transaction.atomic
def deshacer_lista(actor, preparacion_id):
    """Corrige una marca solo mientras el turno siga activo y sin entrega."""
    from turnosapp.cola import bloquear_cola, ConflictoCola

    autorizar(actor, JEFA, TECNICO)
    actor = get_user_model().objects.get(pk=actor.pk)
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    try:
        bloquear_cola(hoy)
    except ConflictoCola:
        raise ConflictoOperacion("La cola cambió. Vuelve a cargar la preparación.") from None
    preparacion = _preparacion_activa(preparacion_id, hoy)
    if preparacion.lista_en is None:
        raise ValidationError("La preparación aún no está marcada como lista.")
    if EntregaReceta.objects.filter(turno_receta_id=preparacion.turno_receta_id).exists():
        raise ValidationError("La receta ya se entregó y no se puede corregir la preparación.")
    actualizadas = PreparacionReceta.objects.filter(
        pk=preparacion.pk, lista_en__isnull=False,
    ).update(
        lista_en=None, lista_por=None, inicio_medido=None,
        duracion_segundos=None, modificado_por=actor, modificado_en=ahora,
    )
    if not actualizadas:
        raise ConflictoOperacion("La preparación cambió durante la operación.")
    preparacion.refresh_from_db()
    auditar(actor, "preparacion.marca_corregida", preparacion)
    return preparacion


@reintentar_conflictos
@transaction.atomic
def retirar_preparado(actor, preparacion_id, operacion_id):
    """Registra una sola entrega histórica sin reabrir ni reencolar el turno."""
    from turnosapp.cola import bloquear_cola, ConflictoCola
    from turnosapp.models import OperacionAtencion

    autorizar(actor, JEFA, TECNICO)
    actor = get_user_model().objects.get(pk=actor.pk)
    try:
        identidad = UUID(str(operacion_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("La operación de retiro no es válida.") from None
    hoy = timezone.localdate()
    try:
        bloquear_cola(hoy)
    except ConflictoCola:
        raise ConflictoOperacion("La cola cambió. Vuelve a cargar el pendiente.") from None

    huella = hashlib.sha256(f"retiro-preparado:{preparacion_id}".encode()).hexdigest()
    previa = OperacionAtencion.objects.filter(pk=identidad).first()
    if previa:
        if previa.actor_id != actor.pk or previa.tipo != "retiro_preparado" or previa.huella != huella:
            raise ValidationError("La operación no corresponde a este retiro.")
        return EntregaReceta.objects.get(pk=previa.resultado["entrega"])

    preparacion = PreparacionReceta.objects.select_related(
        "turno_receta__turno", "turno_receta__receta",
    ).filter(pk=preparacion_id).first()
    if preparacion is None or preparacion.lista_en is None:
        raise ValidationError("La preparación ya no está pendiente de retiro.")
    if preparacion.turno_receta.turno.estado not in (
        "ausente", "sin_atencion_cierre", "atendido", "cerrado_sin_entrega",
    ):
        raise ValidationError("El turno todavía está activo o fue reincorporado.")
    if EntregaReceta.objects.filter(turno_receta_id=preparacion.turno_receta_id).exists():
        raise ValidationError("La receta ya fue entregada.")

    fecha_preparacion = timezone.localdate(preparacion.lista_en)
    entrega = _registrar_entrega_sin_reintento(
        actor, preparacion.turno_receta.receta_id, identidad,
        turno_receta_id=preparacion.turno_receta_id,
        fecha=fecha_preparacion, desde_preparado=preparacion,
    )
    OperacionAtencion.objects.create(
        id=identidad, actor=actor, tipo="retiro_preparado",
        turno_id=preparacion.turno_receta.turno_id,
        huella=huella,
        resultado={"entrega": entrega.pk, "preparacion": preparacion.pk},
    )
    auditar(actor, "preparacion.retirada", preparacion)
    return entrega


@reintentar_conflictos
@transaction.atomic
def aplicar_fila(actor, datos, *, carga, numero_fila):
    """Confirmar paciente, receta y resultado juntos o revertir toda la fila."""
    from .models import ResultadoFilaImportacion

    autorizar(actor, JEFA)
    paciente_datos, receta_datos = datos
    paciente = Paciente.objects.filter(rut=paciente_datos["rut"]).first()
    cambios = {"pacientes_creados": 0, "pacientes_actualizados": 0, "recetas_creadas": 0, "recetas_actualizadas": 0}
    if paciente is None:
        paciente = Paciente(**paciente_datos, creado_por=actor, modificado_por=actor)
        paciente.full_clean()
        try:
            with transaction.atomic():
                paciente.save()
        except IntegrityError:
            raise ConflictoOperacion("El paciente cambió durante la carga.") from None
        auditar(actor, "paciente.creado", paciente)
        cambios["pacientes_creados"] = 1
    elif any(getattr(paciente, nombre) != valor for nombre, valor in paciente_datos.items()):
        anteriores = {nombre: getattr(paciente, nombre) for nombre in paciente_datos}
        for nombre, valor in paciente_datos.items():
            setattr(paciente, nombre, valor)
        paciente.full_clean()
        if not Paciente.objects.filter(pk=paciente.pk, **anteriores).update(**paciente_datos, modificado_por=actor, modificado_en=timezone.now()):
            raise ConflictoOperacion("El paciente cambió durante la carga.")
        auditar(actor, "paciente.actualizado", paciente)
        cambios["pacientes_actualizados"] = 1
    receta = None
    if receta_datos:
        receta = Receta.objects.filter(codigo=receta_datos["codigo"]).first()
        if receta is None:
            try:
                with transaction.atomic():
                    receta = _nueva_receta(actor, paciente, receta_datos)
            except IntegrityError:
                raise ConflictoOperacion("La receta cambió durante la carga.") from None
            cambios["recetas_creadas"] = 1
        else:
            if receta.paciente_id != paciente.pk:
                raise ValidationError("El código de receta ya pertenece a otro paciente.")
            nuevos = {**receta_datos, "fecha_fin_exclusiva": calcular_fin(receta_datos["fecha_inicio"], receta_datos["vigencia_meses"])}
            if any(getattr(receta, nombre) != valor for nombre, valor in nuevos.items()):
                if receta.entregas_completadas:
                    raise ValidationError("La receta tiene entregas: registra una renovación con código nuevo.")
                anteriores = {nombre: getattr(receta, nombre) for nombre in nuevos}
                for nombre, valor in nuevos.items():
                    setattr(receta, nombre, valor)
                receta.full_clean()
                if not Receta.objects.filter(pk=receta.pk, entregas_completadas=0, **anteriores).update(**nuevos, modificado_por=actor, modificado_en=timezone.now()):
                    raise ConflictoOperacion("La receta cambió durante la carga.")
                auditar(actor, "receta.actualizada", receta)
                cambios["recetas_actualizadas"] = 1
    estado = "creada" if cambios["pacientes_creados"] or cambios["recetas_creadas"] else "actualizada" if any(cambios.values()) else "sin_cambios"
    ResultadoFilaImportacion.objects.create(
        importacion=carga, numero_fila=numero_fila, estado=estado,
        paciente=paciente, receta=receta, creado_por=actor, modificado_por=actor,
        **cambios,
    )
    return cambios
