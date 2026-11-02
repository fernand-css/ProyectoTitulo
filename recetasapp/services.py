"""Operaciones de farmacia autorizadas, transaccionales y auditadas."""

import calendar
import time
from datetime import timedelta
from functools import wraps
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from coreapp.auditoria import registrar_accion
from coreapp.mixins import tiene_rol
from coreapp.roles import JEFA, TECNICO
from .models import EntregaReceta, Paciente, Receta


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


@reintentar_conflictos
@transaction.atomic
def registrar_entrega(actor, receta_id, operacion_id):
    autorizar(actor, TECNICO)
    try:
        operacion_id = UUID(str(operacion_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("La confirmación de entrega no es válida.") from None
    previa = EntregaReceta.objects.filter(operacion_id=operacion_id).first()
    if previa:
        if previa.receta_id != receta_id or previa.creado_por_id != actor.pk:
            raise ValidationError("La confirmación no corresponde a esta operación.")
        return previa
    receta = Receta.objects.get(pk=receta_id)
    estado = evaluar_elegibilidad(receta)
    if not estado["elegible"]:
        raise ValidationError(estado["causas"])
    hoy = timezone.localdate()
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
            )
    except IntegrityError:
        raise ConflictoOperacion("La confirmación ya está siendo procesada.") from None
    auditar(actor, "receta.entrega", entrega)
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
