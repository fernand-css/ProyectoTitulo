"""Escrituras del reparto a domicilio: autorizadas en el servidor, transaccionales y auditadas.

Reglas comunes (RNF-02 y CLAUDE.md):
- Sin `select_for_update()`: UPDATE condicional sobre campos propios (nunca filtrando relaciones), restricciones
  únicas de la base y reintentos acotados con transacciones nuevas.
- Las operaciones que tocan recetas o el estado de una entrega toman primero la cola del día
  (`turnosapp.cola.bloquear_cola`), el mismo orden de escritura del tótem, la ventanilla y el retiro del 07.
  Así, una receta nunca queda a la vez en un turno activo y en una entrega abierta.
- La auditoría guarda solo el tipo y el identificador del objeto; si falla, la operación se revierte.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from coreapp.mixins import tiene_rol
from coreapp.roles import ENCARGADO, JEFA, estado_acceso
from recetasapp.models import Paciente, Receta
from recetasapp.services import ConflictoOperacion, auditar, evaluar_elegibilidad, reintentar_conflictos
from . import consultas, fotos
from .models import (
    Domicilio, Entrega, FotoDomicilio, InscripcionReparto, IntentoEntrega, OrdenRuta, ParadaRuta, RecetaEntrega,
)

CAMPOS_UBICACION = ("sector", "localidad", "direccion", "referencias", "latitud", "longitud")
CAMPOS_DOMICILIO = (*CAMPOS_UBICACION, "precision_metros")
MENSAJE_DOMICILIO_CAMBIO = "El domicilio cambió; revisa los datos nuevos."


class EntregaAbiertaExistente(ValidationError):
    """El paciente ya tiene una entrega abierta; `entrega_id` permite enlazarla."""

    def __init__(self, entrega_id):
        super().__init__("El paciente ya tiene una entrega a domicilio abierta.", code="entrega_abierta")
        self.entrega_id = entrega_id


# Autorización ------------------------------------------------------------------------------------------------

def autorizar(actor, *roles):
    if not tiene_rol(actor, *roles):
        raise PermissionDenied


def es_encargado(actor):
    """Comprobación exacta del rol. No usa `tiene_rol`: el superusuario no atestigua visitas en terreno."""
    return estado_acceso(actor) == (True, ENCARGADO)


def _exigir_encargado(actor):
    if not es_encargado(actor):
        raise PermissionDenied


def _uuid(valor, mensaje="La operación no es válida. Vuelve a abrir el formulario."):
    try:
        return UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(mensaje) from None


def _bloquear_jornada(hoy):
    from turnosapp.cola import ConflictoCola, bloquear_cola

    try:
        bloquear_cola(hoy)
    except ConflictoCola:
        raise ConflictoOperacion("La jornada cambió durante la operación.") from None


def _encargado_valido(encargado_id):
    encargado = get_user_model().objects.filter(pk=encargado_id).first()
    if encargado is None or not es_encargado(encargado):
        raise ValidationError("Elige un encargado de terreno con cuenta activa.")
    return encargado


def _fecha_valida(fecha, hoy):
    if fecha is None or fecha < hoy:
        raise ValidationError("La fecha debe ser hoy o posterior.")


def _paciente(paciente_id):
    paciente = Paciente.objects.filter(pk=paciente_id).first()
    if paciente is None:
        raise ValidationError("El paciente no está disponible.")
    return paciente


# Domicilios --------------------------------------------------------------------------------------------------

def _normalizar_domicilio(datos):
    limpio = {}
    for campo in CAMPOS_DOMICILIO:
        valor = datos.get(campo)
        try:
            if campo in ("latitud", "longitud"):
                limpio[campo] = None if valor in (None, "") else Decimal(str(valor)).quantize(Decimal("0.000001"))
            elif campo == "precision_metros":
                limpio[campo] = None if valor in (None, "") else int(valor)
            else:
                limpio[campo] = (valor or "").strip()
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError("Revisa las coordenadas: deben ser números.") from None
    if (limpio["latitud"] is None) != (limpio["longitud"] is None):
        raise ValidationError("Ingresa latitud y longitud juntas, o ninguna.")
    if limpio["latitud"] is None:
        limpio["precision_metros"] = None
    return limpio


@reintentar_conflictos
@transaction.atomic
def guardar_domicilio(actor, paciente_id, datos, version=None):
    """Crea o edita el domicilio. La edición exige la versión leída: nunca sobrescribe un cambio ajeno."""
    autorizar(actor, JEFA, ENCARGADO)
    actor = get_user_model().objects.get(pk=actor.pk)
    paciente = _paciente(paciente_id)
    datos = _normalizar_domicilio(datos)
    ahora = timezone.now()
    actual = Domicilio.objects.filter(paciente=paciente).first()
    if actual is None:
        if version is not None:
            raise ValidationError(MENSAJE_DOMICILIO_CAMBIO)
        if not consultas.es_elegible(paciente, timezone.localdate(ahora)):
            raise ValidationError("El paciente no es elegible para el reparto a domicilio.")
        domicilio = Domicilio(paciente=paciente, direccion_padron=paciente.direccion,
                              creado_por=actor, modificado_por=actor, **datos)
        domicilio.full_clean(exclude=["paciente"])
        try:
            with transaction.atomic():
                domicilio.save()
        except IntegrityError:
            raise ConflictoOperacion("El domicilio se creó en paralelo.") from None
        auditar(actor, "domicilio.creado", domicilio)
        return domicilio
    if version is None or int(version) != actual.version:
        raise ValidationError(MENSAJE_DOMICILIO_CAMBIO)
    cambio_ubicacion = any(getattr(actual, campo) != datos[campo] for campo in CAMPOS_UBICACION)
    padron_cambio = actual.direccion_padron != paciente.direccion
    limpiar_verificacion = cambio_ubicacion or padron_cambio
    candidato = Domicilio(pk=actual.pk, paciente=paciente, direccion_padron=paciente.direccion, version=actual.version,
                          verificado_en=None if limpiar_verificacion else actual.verificado_en,
                          verificado_por=None if limpiar_verificacion else actual.verificado_por, **datos)
    candidato.full_clean(exclude=["paciente"], validate_unique=False)
    cambios = {**datos, "direccion_padron": paciente.direccion, "version": F("version") + 1,
               "modificado_por": actor, "modificado_en": ahora}
    if limpiar_verificacion:
        cambios.update(verificado_en=None, verificado_por=None)
    if not Domicilio.objects.filter(pk=actual.pk, version=actual.version).update(**cambios):
        raise ValidationError(MENSAJE_DOMICILIO_CAMBIO)
    actual.refresh_from_db()
    auditar(actor, "domicilio.editado", actual)
    return actual


@reintentar_conflictos
@transaction.atomic
def verificar_domicilio(actor, domicilio_id, version):
    """Solo el encargado de terreno atestigua que el domicilio es correcto."""
    _exigir_encargado(actor)
    actor = get_user_model().objects.get(pk=actor.pk)
    domicilio = Domicilio.objects.select_related("paciente").filter(pk=domicilio_id).first()
    if domicilio is None:
        raise ValidationError("El domicilio no está disponible.")
    if version is None or int(version) != domicilio.version:
        raise ValidationError(MENSAJE_DOMICILIO_CAMBIO)
    if not domicilio.sector or not domicilio.direccion.strip():
        raise ValidationError("Para verificar, el domicilio necesita sector y dirección.")
    ahora = timezone.now()
    if not Domicilio.objects.filter(pk=domicilio.pk, version=domicilio.version).update(
        verificado_en=ahora, verificado_por=actor, direccion_padron=domicilio.paciente.direccion,
        version=F("version") + 1, modificado_por=actor, modificado_en=ahora,
    ):
        raise ValidationError(MENSAJE_DOMICILIO_CAMBIO)
    domicilio.refresh_from_db()
    auditar(actor, "domicilio.verificado", domicilio)
    return domicilio


# Fotos -------------------------------------------------------------------------------------------------------

def agregar_foto(actor, domicilio_id, archivo, descripcion):
    """Procesa la imagen fuera de la transacción y guarda solo el JPEG limpio; si algo falla, borra el archivo."""
    from coreapp.utils.custom_image import procesar_imagen

    autorizar(actor, JEFA, ENCARGADO)
    descripcion = (descripcion or "").strip()
    if not descripcion or len(descripcion) > 120:
        raise ValidationError("Describe la foto en 120 caracteres o menos; sirve de texto alternativo.")
    if not Domicilio.objects.filter(pk=domicilio_id).exists():
        raise ValidationError("El domicilio no está disponible.")
    contenido, ancho, alto = procesar_imagen(archivo)
    nombre = fotos.guardar_jpeg(contenido)
    try:
        return _registrar_foto(actor, domicilio_id, nombre, descripcion, ancho, alto, len(contenido))
    except BaseException:
        fotos.borrar(nombre)
        raise


@reintentar_conflictos
@transaction.atomic
def _registrar_foto(actor, domicilio_id, nombre, descripcion, ancho, alto, tamano):
    actor = get_user_model().objects.get(pk=actor.pk)
    ocupadas = set(FotoDomicilio.objects.filter(domicilio_id=domicilio_id).values_list("posicion", flat=True))
    libres = [posicion for posicion in range(1, FotoDomicilio.MAXIMO + 1) if posicion not in ocupadas]
    if not libres:
        raise ValidationError(f"El domicilio ya tiene {FotoDomicilio.MAXIMO} fotos. Borra una antes de agregar otra.")
    try:
        with transaction.atomic():
            foto = FotoDomicilio.objects.create(
                domicilio_id=domicilio_id, posicion=libres[0], archivo=nombre, descripcion=descripcion,
                ancho=ancho, alto=alto, bytes=tamano, creado_por=actor, modificado_por=actor,
            )
    except IntegrityError:
        raise ConflictoOperacion("Otra foto ocupó esa posición.") from None
    auditar(actor, "domicilio.foto_agregada", foto)
    return foto


@transaction.atomic
def eliminar_foto(actor, foto_id):
    """Borra la fila y, después de confirmar la transacción, el archivo."""
    autorizar(actor, JEFA, ENCARGADO)
    actor = get_user_model().objects.get(pk=actor.pk)
    foto = FotoDomicilio.objects.filter(pk=foto_id).first()
    if foto is None:
        return None
    auditar(actor, "domicilio.foto_eliminada", foto)
    nombre = foto.archivo.name
    if not FotoDomicilio.objects.filter(pk=foto.pk).delete()[0]:
        raise ValidationError("La foto ya no está disponible.")
    transaction.on_commit(lambda: fotos.borrar(nombre))
    return foto.domicilio_id


# Excepciones de reparto --------------------------------------------------------------------------------------

def _validar_motivo(motivo, nota, opciones, mensaje):
    nota = (nota or "").strip()
    if motivo not in opciones:
        raise ValidationError(mensaje)
    if len(nota) > 200:
        raise ValidationError("La nota admite hasta 200 caracteres.")
    if motivo == "otro" and not nota:
        raise ValidationError("Con el motivo «Otro», escribe una nota breve.")
    return nota


@reintentar_conflictos
@transaction.atomic
def inscribir_excepcion(actor, paciente_id, motivo, nota=""):
    autorizar(actor, JEFA)
    actor = get_user_model().objects.get(pk=actor.pk)
    nota = _validar_motivo(motivo, nota, InscripcionReparto.Motivo.values, "Elige un motivo de la lista.")
    paciente = _paciente(paciente_id)
    if paciente.requiere_despacho_en(timezone.localdate()):
        raise ValidationError("El paciente ya es elegible por edad o postración; no necesita excepción.")
    try:
        with transaction.atomic():
            inscripcion = InscripcionReparto.objects.create(
                paciente=paciente, motivo=motivo, nota=nota, creado_por=actor, modificado_por=actor,
            )
    except IntegrityError:
        raise ValidationError("El paciente ya tiene una excepción de reparto vigente.") from None
    auditar(actor, "reparto.excepcion_inscrita", inscripcion)
    return inscripcion


@transaction.atomic
def retirar_excepcion(actor, inscripcion_id):
    """Conserva el registro con quién y cuándo. No cierra la entrega abierta que el paciente tenga."""
    autorizar(actor, JEFA)
    actor = get_user_model().objects.get(pk=actor.pk)
    ahora = timezone.now()
    if not InscripcionReparto.objects.filter(pk=inscripcion_id, retirada_en__isnull=True).update(
        retirada_en=ahora, retirada_por=actor, modificado_por=actor, modificado_en=ahora,
    ):
        raise ValidationError("La excepción ya fue retirada o no existe.")
    inscripcion = InscripcionReparto.objects.get(pk=inscripcion_id)
    auditar(actor, "reparto.excepcion_retirada", inscripcion)
    return inscripcion


# Programación ------------------------------------------------------------------------------------------------

def recetas_para_despacho(paciente, fecha):
    """Recetas elegibles a `fecha` según el 03, sin las de un turno activo ni las que esperan retiro (07)."""
    from recetasapp.preparacion import pendientes_retiro
    from turnosapp.models import TurnoReceta

    recetas = [r for r in paciente.recetas.order_by("pk") if evaluar_elegibilidad(r, fecha)["elegible"]]
    ids = [r.pk for r in recetas]
    if not ids:
        return []
    en_turno = set(TurnoReceta.objects.filter(
        receta_id__in=ids, turno__estado__in=("esperando", "llamado"),
    ).values_list("receta_id", flat=True))
    por_retirar = set(pendientes_retiro().filter(turno_receta__receta_id__in=ids).values_list("turno_receta__receta_id", flat=True))
    return [r for r in recetas if r.pk not in en_turno and r.pk not in por_retirar]


@reintentar_conflictos
@transaction.atomic
def programar_entrega(actor, paciente_id, fecha, encargado_id, operacion_id):
    """Nace una entrega «programada» con sus recetas fijadas y su primer intento."""
    autorizar(actor, JEFA)
    actor = get_user_model().objects.get(pk=actor.pk)
    operacion = _uuid(operacion_id)
    hoy = timezone.localdate()
    _bloquear_jornada(hoy)
    previa = Entrega.objects.filter(operacion_id=operacion).first()
    if previa is not None:
        if previa.creado_por_id != actor.pk or previa.paciente_id != paciente_id:
            raise ValidationError("La operación no corresponde a esta programación.")
        return previa
    _fecha_valida(fecha, hoy)
    encargado = _encargado_valido(encargado_id)
    paciente = _paciente(paciente_id)
    if not consultas.es_elegible(paciente, fecha):
        raise ValidationError("El paciente no es elegible para el reparto a domicilio en esa fecha.")
    abierta = consultas.entrega_abierta(paciente)
    if abierta is not None:
        raise EntregaAbiertaExistente(abierta.pk)
    recetas = recetas_para_despacho(paciente, fecha)
    if not recetas:
        raise ValidationError(
            "El paciente no tiene recetas disponibles para despacho en esa fecha: están vencidas, agotadas, "
            "aún no inician, en un turno activo o esperando retiro en farmacia."
        )
    try:
        with transaction.atomic():
            entrega = Entrega.objects.create(paciente=paciente, operacion_id=operacion, creado_por=actor, modificado_por=actor)
    except IntegrityError:
        abierta = consultas.entrega_abierta(paciente)
        if abierta is not None:
            raise EntregaAbiertaExistente(abierta.pk) from None
        raise ConflictoOperacion("La programación cambió durante la operación.") from None
    RecetaEntrega.objects.bulk_create([
        RecetaEntrega(entrega=entrega, receta=receta, creado_por=actor, modificado_por=actor) for receta in recetas
    ])
    IntentoEntrega.objects.create(entrega=entrega, numero=1, fecha_programada=fecha, encargado=encargado,
                                  creado_con=operacion, creado_por=actor, modificado_por=actor)
    auditar(actor, "entrega.programada", entrega)
    return entrega


# Registro en terreno -----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoRegistro:
    intento: IntentoEntrega
    repetido: bool  # el mismo identificador ya se había registrado: no hubo otro cambio


def _intento_para_registrar(actor, intento_id, operacion, resultado, hoy):
    """Idempotencia, asignación y fecha. Devuelve (intento, previo) donde previo indica un reenvío."""
    previo = IntentoEntrega.objects.filter(operacion_id=operacion).first()
    if previo is not None:
        if previo.pk != intento_id or previo.registrado_por_id != actor.pk or previo.resultado != resultado:
            raise ValidationError("La operación no corresponde a este registro.")
        return previo, True
    intento = IntentoEntrega.objects.select_related("entrega").filter(pk=intento_id).first()
    if intento is None:
        raise ValidationError("El intento de entrega no está disponible.")
    if intento.encargado_id != actor.pk:
        raise PermissionDenied
    if intento.resultado != IntentoEntrega.Resultado.PENDIENTE:
        mensajes = {
            "reasignado": "La entrega fue reasignada. Revisa tus entregas actualizadas.",
            "anulado": "La entrega fue anulada por la Q.F.",
        }
        raise ValidationError(mensajes.get(intento.resultado, "Este intento ya tiene un resultado registrado."))
    if intento.fecha_programada > hoy:
        raise ValidationError(f"Esta entrega está programada para el {intento.fecha_programada:%d/%m}. Regístrala desde ese día.")
    return intento, False


def _cerrar_intento(actor, intento, operacion, ahora, **resultado):
    try:
        with transaction.atomic():
            actualizados = IntentoEntrega.objects.filter(pk=intento.pk, resultado=IntentoEntrega.Resultado.PENDIENTE).update(
                registrado_en=ahora, registrado_por=actor, operacion_id=operacion,
                modificado_por=actor, modificado_en=ahora, **resultado,
            )
    except IntegrityError:
        raise ValidationError("La operación no corresponde a este registro.") from None
    if not actualizados:
        raise ConflictoOperacion("El intento cambió durante el registro.")


@reintentar_conflictos
@transaction.atomic
def registrar_entregada(actor, intento_id, operacion_id):
    """Cierra la entrega y descuenta cada receta que sigue elegible en la fecha de la visita (hoy)."""
    from recetasapp.services import _registrar_entrega_sin_reintento

    _exigir_encargado(actor)
    actor = get_user_model().objects.get(pk=actor.pk)
    operacion = _uuid(operacion_id)
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    _bloquear_jornada(hoy)
    intento, repetido = _intento_para_registrar(actor, intento_id, operacion, IntentoEntrega.Resultado.ENTREGADA, hoy)
    if repetido:
        return ResultadoRegistro(intento, True)
    _cerrar_intento(actor, intento, operacion, ahora, resultado=IntentoEntrega.Resultado.ENTREGADA)
    if not Entrega.objects.filter(pk=intento.entrega_id, estado=Entrega.Estado.PROGRAMADA).update(
        estado=Entrega.Estado.ENTREGADA, cerrada_en=ahora, modificado_por=actor, modificado_en=ahora,
    ):
        raise ConflictoOperacion("La entrega cambió durante el registro.")
    for vinculo in RecetaEntrega.objects.filter(entrega_id=intento.entrega_id, resultado=RecetaEntrega.Resultado.PENDIENTE):
        receta = Receta.objects.get(pk=vinculo.receta_id)
        causas = evaluar_elegibilidad(receta, hoy)["causas"]
        entrega_receta = None
        if not causas:
            try:
                with transaction.atomic():
                    entrega_receta = _registrar_entrega_sin_reintento(
                        actor, receta.pk, uuid.uuid5(operacion, f"receta:{receta.pk}"),
                        turno_receta_id=None, fecha=hoy, desde_despacho=vinculo,
                    )
            except ConflictoOperacion:
                raise  # Reintentar la unidad completa en una transacción nueva.
            except ValidationError as error:
                causas = error.messages or ["La receta no pudo descontarse."]
        cambios = {"resultado": RecetaEntrega.Resultado.DESCONTADA, "entrega_receta": entrega_receta} if entrega_receta else {
            "resultado": RecetaEntrega.Resultado.NO_DESCONTADA, "causa": " ".join(causas)[:200]}
        if not RecetaEntrega.objects.filter(pk=vinculo.pk, resultado=RecetaEntrega.Resultado.PENDIENTE).update(
            modificado_por=actor, modificado_en=ahora, **cambios,
        ):
            raise ConflictoOperacion("La receta de la entrega cambió durante el registro.")
    intento.refresh_from_db()
    auditar(actor, "intento.entregado", intento)
    return ResultadoRegistro(intento, False)


@reintentar_conflictos
@transaction.atomic
def registrar_no_entregada(actor, intento_id, motivo, nota, operacion_id):
    """La entrega pasa a «pendiente de gestión» sin descontar; sus recetas siguen bloqueadas en farmacia."""
    _exigir_encargado(actor)
    actor = get_user_model().objects.get(pk=actor.pk)
    nota = _validar_motivo(motivo, nota, IntentoEntrega.Motivo.values, "Elige el motivo de la no entrega.")
    operacion = _uuid(operacion_id)
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    _bloquear_jornada(hoy)
    intento, repetido = _intento_para_registrar(actor, intento_id, operacion, IntentoEntrega.Resultado.NO_ENTREGADA, hoy)
    if repetido:
        return ResultadoRegistro(intento, True)
    _cerrar_intento(actor, intento, operacion, ahora, resultado=IntentoEntrega.Resultado.NO_ENTREGADA, motivo=motivo, nota=nota)
    if not Entrega.objects.filter(pk=intento.entrega_id, estado=Entrega.Estado.PROGRAMADA).update(
        estado=Entrega.Estado.PENDIENTE_GESTION, modificado_por=actor, modificado_en=ahora,
    ):
        raise ConflictoOperacion("La entrega cambió durante el registro.")
    intento.refresh_from_db()
    auditar(actor, "intento.no_entregado", intento)
    return ResultadoRegistro(intento, False)


# Gestión de la Q.F. ------------------------------------------------------------------------------------------

@reintentar_conflictos
@transaction.atomic
def reasignar(actor, entrega_id, *, fecha, encargado_id, intento_id, operacion_id, resultado_visto=None):
    """Crea el intento siguiente; los anteriores no cambian. Un intento sin resultado queda «reasignado».

    `intento_id` y `resultado_visto` son el último intento que la Q.F. vio y su resultado en ese momento. Si
    cambiaron (otro registro o reasignación entre medio), se rechaza: frente a un registro simultáneo gana
    exactamente una operación (RF-08-15). Las pantallas siempre envían ambos.
    """
    autorizar(actor, JEFA)
    actor = get_user_model().objects.get(pk=actor.pk)
    operacion = _uuid(operacion_id)
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    _bloquear_jornada(hoy)
    previo = IntentoEntrega.objects.filter(creado_con=operacion).first()
    if previo is not None:
        if previo.entrega_id != entrega_id or previo.creado_por_id != actor.pk:
            raise ValidationError("La operación no corresponde a esta reasignación.")
        return previo
    _fecha_valida(fecha, hoy)
    encargado = _encargado_valido(encargado_id)
    entrega = Entrega.objects.filter(pk=entrega_id).first()
    if entrega is None:
        raise ValidationError("La entrega no está disponible.")
    if not entrega.abierta:
        raise ValidationError("La entrega ya está cerrada; no se puede reasignar.")
    ultimo = entrega.intentos.order_by("-numero").first()
    if ultimo is None or ultimo.pk != intento_id or (resultado_visto is not None and ultimo.resultado != resultado_visto):
        raise ValidationError("La entrega cambió. Revisa su último intento antes de reasignar.")
    if ultimo.resultado == IntentoEntrega.Resultado.PENDIENTE:
        try:
            with transaction.atomic():
                cerrados = IntentoEntrega.objects.filter(pk=ultimo.pk, resultado=IntentoEntrega.Resultado.PENDIENTE).update(
                    resultado=IntentoEntrega.Resultado.REASIGNADO, registrado_en=ahora, registrado_por=actor,
                    operacion_id=uuid.uuid5(operacion, "reasignado"), modificado_por=actor, modificado_en=ahora,
                )
        except IntegrityError:
            raise ConflictoOperacion("El intento cambió durante la reasignación.") from None
        if not cerrados:
            raise ValidationError("El intento cambió. Revisa su resultado antes de reasignar.")
    elif not (ultimo.resultado == IntentoEntrega.Resultado.NO_ENTREGADA
              and entrega.estado == Entrega.Estado.PENDIENTE_GESTION):
        raise ValidationError("La entrega cambió. Revisa su último intento antes de reasignar.")
    try:
        with transaction.atomic():
            nuevo = IntentoEntrega.objects.create(
                entrega=entrega, numero=ultimo.numero + 1, fecha_programada=fecha, encargado=encargado,
                creado_con=operacion, creado_por=actor, modificado_por=actor,
            )
    except IntegrityError:
        raise ConflictoOperacion("Otro intento se creó en paralelo.") from None
    if not Entrega.objects.filter(pk=entrega.pk, estado__in=Entrega.ABIERTAS).update(
        estado=Entrega.Estado.PROGRAMADA, modificado_por=actor, modificado_en=ahora,
    ):
        raise ConflictoOperacion("La entrega cambió durante la reasignación.")
    auditar(actor, "entrega.reasignada", nuevo)
    return nuevo


@reintentar_conflictos
@transaction.atomic
def anular_entrega(actor, entrega_id, motivo, nota=""):
    """Cierra la entrega con un motivo y libera sus recetas. Repetirla sobre una anulada no cambia nada."""
    autorizar(actor, JEFA)
    actor = get_user_model().objects.get(pk=actor.pk)
    nota = _validar_motivo(motivo, nota, Entrega.MotivoAnulacion.values, "Elige el motivo de la anulación.")
    ahora = timezone.now()
    _bloquear_jornada(timezone.localdate(ahora))
    entrega = Entrega.objects.filter(pk=entrega_id).first()
    if entrega is None:
        raise ValidationError("La entrega no está disponible.")
    if entrega.estado == Entrega.Estado.ANULADA:
        return entrega
    if not entrega.abierta:
        raise ValidationError("La entrega ya se registró como entregada; no se puede anular.")
    IntentoEntrega.objects.filter(entrega=entrega, resultado=IntentoEntrega.Resultado.PENDIENTE).update(
        resultado=IntentoEntrega.Resultado.ANULADO, registrado_en=ahora, registrado_por=actor,
        operacion_id=uuid.uuid4(), modificado_por=actor, modificado_en=ahora,
    )
    if not Entrega.objects.filter(pk=entrega.pk, estado__in=Entrega.ABIERTAS).update(
        estado=Entrega.Estado.ANULADA, cerrada_en=ahora, motivo_anulacion=motivo, nota_anulacion=nota,
        anulada_por=actor, modificado_por=actor, modificado_en=ahora,
    ):
        raise ConflictoOperacion("La entrega cambió durante la anulación.")
    entrega.refresh_from_db()
    auditar(actor, "entrega.anulada", entrega)
    return entrega


# Orden de visita (spec 09) -------------------------------------------------------------------------------------

MENSAJE_ORDEN_CAMBIO = "Tu orden cambió en otro dispositivo; revisa la lista."
SUBIR = "subir"
BAJAR = "bajar"


def _version_leida(version):
    try:
        version = int(version)
    except (TypeError, ValueError):
        raise ValidationError(MENSAJE_ORDEN_CAMBIO) from None
    if version < 0:
        raise ValidationError(MENSAJE_ORDEN_CAMBIO)
    return version


def _tomar_orden(actor, hoy, version, operacion, ahora):
    """Toma el orden de hoy desde la versión que vio el encargado. Devuelve (orden, repetido).

    Sin `select_for_update()`: el primer guardado crea el orden (la restricción `orden_ruta_unico` deja uno solo y
    el perdedor reintenta, ya con otra versión) y los siguientes suben la versión con un UPDATE condicional sobre
    campos propios. Una versión distinta de la actual nunca sobrescribe: devuelve el aviso, sin reintento.
    """
    orden = OrdenRuta.objects.filter(encargado=actor, fecha=hoy).first()
    if orden is not None and orden.ultima_operacion == operacion:
        return orden, True
    if orden is None:
        if version != 0:
            raise ValidationError(MENSAJE_ORDEN_CAMBIO)
        try:
            with transaction.atomic():
                orden = OrdenRuta.objects.create(encargado=actor, fecha=hoy, version=1, ultima_operacion=operacion,
                                                 creado_por=actor, modificado_por=actor)
        except IntegrityError:
            raise ConflictoOperacion("Otro dispositivo guardó el orden en paralelo.") from None
        return orden, False
    if not OrdenRuta.objects.filter(pk=orden.pk, version=version).update(
        version=F("version") + 1, ultima_operacion=operacion, modificado_por=actor, modificado_en=ahora,
    ):
        raise ValidationError(MENSAJE_ORDEN_CAMBIO)
    orden.refresh_from_db()
    return orden, False


def _destino_valido(destino, indice, cantidad):
    if destino == SUBIR:
        if indice == 0:
            raise ValidationError("Esta parada ya es la primera.")
        return indice - 1
    if destino == BAJAR:
        if indice == cantidad - 1:
            raise ValidationError("Esta parada ya es la última.")
        return indice + 1
    try:
        posicion = int(destino)
    except (TypeError, ValueError):
        raise ValidationError("Elige subir, bajar o una posición de la lista.") from None
    if not 1 <= posicion <= cantidad:
        raise ValidationError(f"Elige una posición entre 1 y {cantidad}.")
    return posicion - 1


@reintentar_conflictos
@transaction.atomic
def mover_parada(actor, intento_id, destino, version, operacion_id):
    """Sube, baja o mueve a una posición una visita de la ruta de hoy y guarda el orden completo (RF-09-04).

    Parte de la ruta que el encargado ve (sugerida o guardada, con las visitas nuevas ya insertadas), así que al
    guardar las nuevas quedan incorporadas. Solo el encargado asignado (comprobación exacta del rol).
    """
    _exigir_encargado(actor)
    actor = get_user_model().objects.get(pk=actor.pk)
    operacion = _uuid(operacion_id)
    version = _version_leida(version)
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    orden, repetido = _tomar_orden(actor, hoy, version, operacion, ahora)
    if repetido:
        return orden
    secuencia = [parada.intento.pk for parada in consultas.ruta_del_dia(actor, hoy, hoy).paradas]
    try:
        indice = secuencia.index(int(intento_id))
    except (TypeError, ValueError):
        raise ValidationError("Esa visita ya no está en tu ruta de hoy. Revisa la lista.") from None
    nuevo = _destino_valido(destino, indice, len(secuencia))
    secuencia.insert(nuevo, secuencia.pop(indice))
    ParadaRuta.objects.filter(orden=orden).delete()
    ParadaRuta.objects.bulk_create([
        ParadaRuta(orden=orden, intento_id=pk, posicion=posicion) for posicion, pk in enumerate(secuencia, start=1)
    ])
    auditar(actor, "ruta.ordenada", orden)
    return orden


@reintentar_conflictos
@transaction.atomic
def restablecer_orden(actor, version, operacion_id):
    """«Volver al orden sugerido»: vacía el orden de hoy (RF-09-06). Sin un orden con paradas no hace nada."""
    _exigir_encargado(actor)
    actor = get_user_model().objects.get(pk=actor.pk)
    operacion = _uuid(operacion_id)
    version = _version_leida(version)
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    if not ParadaRuta.objects.filter(orden__encargado=actor, orden__fecha=hoy).exists():
        return None
    orden, repetido = _tomar_orden(actor, hoy, version, operacion, ahora)
    if repetido:
        return orden
    ParadaRuta.objects.filter(orden=orden).delete()
    auditar(actor, "ruta.restablecida", orden)
    return orden


@transaction.atomic
def marcar_revisada(actor, receta_entrega_id):
    autorizar(actor, JEFA)
    actor = get_user_model().objects.get(pk=actor.pk)
    ahora = timezone.now()
    vinculo = RecetaEntrega.objects.filter(pk=receta_entrega_id).first()
    if vinculo is None or vinculo.resultado != RecetaEntrega.Resultado.NO_DESCONTADA:
        raise ValidationError("Solo se revisan recetas que quedaron sin descontar.")
    if vinculo.revisada_en is not None:
        return vinculo
    if not RecetaEntrega.objects.filter(
        pk=vinculo.pk, resultado=RecetaEntrega.Resultado.NO_DESCONTADA, revisada_en__isnull=True,
    ).update(revisada_en=ahora, revisada_por=actor, modificado_por=actor, modificado_en=ahora):
        vinculo.refresh_from_db()
        return vinculo
    vinculo.refresh_from_db()
    auditar(actor, "despacho.receta_revisada", vinculo)
    return vinculo
