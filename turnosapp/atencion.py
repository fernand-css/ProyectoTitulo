"""Operación de ventanilla y cierre atómico con el control interno de recetas."""
import hashlib
import json
import time
import uuid
from datetime import timedelta
from random import uniform

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F, Max
from django.utils import timezone

from coreapp.auditoria import registrar_accion
from coreapp.mixins import tiene_rol
from coreapp.roles import JEFA, TECNICO
from recetasapp.models import EntregaReceta
from recetasapp.services import _registrar_entrega_sin_reintento, ConflictoOperacion
from .sala import registrar_anuncio
from .cola import bloquear_cola, cerrar_esperas_anteriores, ConflictoCola, solicitar_seleccion
from .models import (
    LETRA_POR_TIPO, ConfiguracionCola, ContadorTurnosDiario, EventoTurno, Letra, OcupacionVentanilla,
    OperacionAtencion, TipoAtencionVentanilla, Turno, TurnoReceta, Ventanilla, CausaNoEntrega, CierreAtencion, DetalleCierre,
)


MOTIVO_SIN_RECETAS = "Atención sin recetas del sistema"
DETALLE_OTRO_MAXIMO = 200
CAUSAS_VALIDAS = frozenset(CausaNoEntrega.values)


def resolver_causa(codigo, detalle):
    """RF-05-14: (código, texto legible) de una causa de no entrega.

    Con código, el texto es el nombre de la causa, u «Otro: <detalle>» (que exige el detalle). Sin código, un texto
    libre (llamadas anteriores a la enmienda) cuenta como «Otro» y se guarda tal cual. Sin ninguno, ("", "").
    """
    if codigo:
        if codigo == CausaNoEntrega.OTRO:
            if not detalle:
                raise ValidationError("Escribe el detalle de la causa «Otro».")
            return codigo, f"Otro: {detalle}"
        return codigo, CausaNoEntrega(codigo).label
    if detalle:
        return CausaNoEntrega.OTRO.value, detalle
    return "", ""
TIPO_POR_LETRA = {letra: tipo for tipo, letra in LETRA_POR_TIPO.items()}
# Quién puede pedir cada operación; el resto de la autorización se revisa en su rama.
ROLES = {
    "configurar": (JEFA,), "crear_ventanilla": (JEFA,), "pesos": (JEFA,),
    # Spec 10: la Q.F. termina cualquier ventanilla; el Técnico, solo la propia (se revisa en la rama).
    "terminar_turno": (JEFA, TECNICO), "reclasificar": (JEFA, TECNICO), "urgencia": (JEFA, TECNICO),
}


def _obtener(modelo, pk):
    objeto = modelo.objects.filter(pk=pk).first()
    if objeto is None:
        raise ValidationError("El registro solicitado no está disponible.")
    return objeto


def _propia(ventanilla, actor):
    if ventanilla.operador_id != actor.pk:
        raise PermissionDenied
    if not OcupacionVentanilla.objects.filter(ventanilla=ventanilla, tecnico=actor, cierre__isnull=True).exists():
        raise ValidationError("La ventanilla no tiene una ocupación vigente.")


def _evento(turno, accion, instante, actor, operacion, ventanilla=None, letra_anterior="", numero_anterior=None):
    secuencia = (turno.eventos.aggregate(maximo=Max("secuencia"))["maximo"] or 0) + 1
    evento = EventoTurno.objects.create(turno=turno, accion=accion, secuencia=secuencia,
        instante=instante, actor=actor, operacion=operacion, ventanilla=ventanilla,
        letra_anterior=letra_anterior, numero_anterior=numero_anterior)
    if accion == "rellamado":
        registrar_anuncio(evento, turno, ventanilla)
    registrar_accion(actor, "turno." + accion, evento)


@transaction.atomic
def _operar(actor, tipo, destino, identidad, datos, huella):
    roles = ROLES.get(tipo, (TECNICO,))
    if not tiene_rol(actor, *roles):
        raise PermissionDenied
    actor = get_user_model().objects.get(pk=actor.pk)
    previa = OperacionAtencion.objects.filter(pk=identidad).first()
    if previa:
        if previa.actor_id != actor.pk or previa.tipo != tipo or previa.huella != huella:
            raise ValidationError("La confirmación no corresponde a esta operación.")
        return previa.resultado
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    bloquear_cola(hoy)
    cerrar_esperas_anteriores(ahora)
    # Relectura posterior a reservar la cola, frente a reenvíos simultáneos.
    previa = OperacionAtencion.objects.filter(pk=identidad).first()
    if previa:
        if previa.actor_id != actor.pk or previa.tipo != tipo or previa.huella != huella:
            raise ValidationError("La confirmación no corresponde a esta operación.")
        return previa.resultado
    if not tiene_rol(actor, *roles):
        raise PermissionDenied
    es_turno = tipo in ("rellamar", "ausente", "reincorporar", "finalizar", "reclasificar", "urgencia")
    turno = _obtener(Turno, destino) if es_turno else None
    ventanilla = (turno.ventanilla if turno else _obtener(Ventanilla, destino)) if tipo not in ("pesos", "crear_ventanilla", "reincorporar") else None
    operacion = OperacionAtencion.objects.create(id=identidad, actor=actor, tipo=tipo,
        turno=turno, ventanilla=ventanilla, huella=huella)
    seleccionar = False
    if tipo == "ocupar":
        if not ventanilla.habilitada or ventanilla.retirada or ventanilla.operador_id:
            raise ValidationError("La ventanilla no está libre y habilitada.")
        if Ventanilla.objects.filter(operador=actor).exists():
            raise ValidationError("Ya tienes una ventanilla ocupada.")
        ventanilla.operador = actor
        ventanilla.automatico = False
        ventanilla.fecha_activacion = None
        OcupacionVentanilla.objects.create(ventanilla=ventanilla, tecnico=actor, apertura=ahora)
    elif tipo in ("iniciar", "pausar", "liberar"):
        _propia(ventanilla, actor)
        if tipo == "iniciar":
            if not ventanilla.habilitada or ventanilla.retirada:
                raise ValidationError("La ventanilla no está habilitada.")
            ventanilla.automatico = True
            ventanilla.fecha_activacion = hoy
            ventanilla.disponible_desde = ahora
            seleccionar = True
        elif tipo == "pausar":
            ventanilla.automatico = False
        else:
            if Turno.objects.filter(ventanilla=ventanilla, estado="llamado").exists():
                raise ValidationError("Finaliza la atención vigente antes de liberar la ventanilla.")
            OcupacionVentanilla.objects.filter(ventanilla=ventanilla, cierre__isnull=True).update(cierre=ahora, motivo="liberada")
            ventanilla.operador = None
            ventanilla.automatico = False
            ventanilla.fecha_activacion = None
    elif tipo == "configurar":
        habilitada = datos["habilitada"] if datos["habilitada"] is not None else ventanilla.habilitada
        retirada = datos["retirada"] if datos["retirada"] is not None else ventanilla.retirada
        if retirada:
            habilitada = False
        if (not habilitada or retirada) and Turno.objects.filter(ventanilla=ventanilla, estado="llamado").exists() and not datos["confirmar"]:
            raise ValidationError("Confirma deshabilitar la ventanilla con atención en curso.")
        ventanilla.habilitada, ventanilla.retirada = habilitada, retirada
        if not habilitada:
            ventanilla.automatico = False
        if datos["tipos"] is not None:
            if set(datos["tipos"]) - set(TipoAtencionVentanilla.objects.values_list("codigo", flat=True)):
                raise ValidationError("Tipos de atención no válidos.")
            ventanilla.tipos.set(datos["tipos"])
        seleccionar = True
    elif tipo == "finalizar":
        if turno.estado != "llamado" or ventanilla is None:
            raise ValidationError("El turno ya no tiene una atención vigente.")
        _propia(ventanilla, actor)
        if turno.operador_id != actor.pk:
            raise PermissionDenied
        vinculos = list(turno.recetas_vinculadas.order_by("receta_id"))
        if not vinculos:
            # Enmienda RF-05-13: sin recetas del sistema el cierre lleva un motivo fijo y no pide texto.
            datos = {**datos, "motivo": MOTIVO_SIN_RECETAS}
        ids = {v.receta_id for v in vinculos}
        seleccion = set(datos["recetas"])
        motivos, causas = datos["motivos"], datos.get("causas", {})
        if seleccion - ids or set(map(int, motivos)) - ids or set(map(int, causas)) - ids:
            raise ValidationError("La selección no corresponde a las recetas del turno.")
        # RF-05-14: la causa general vale para las recetas sin causa ni texto propios.
        # Sin recetas (RF-05-13) el motivo es fijo y no lleva causa.
        general = resolver_causa(datos.get("causa", ""), datos["motivo"]) if vinculos else ("", MOTIVO_SIN_RECETAS)
        no_entregadas = {}
        entregas = {}
        for vinculo in vinculos:
            anterior = EntregaReceta.objects.filter(turno_receta=vinculo).first()
            if anterior:
                entregas[vinculo.pk] = anterior
            elif vinculo.receta_id in seleccion:
                entregas[vinculo.pk] = _registrar_entrega_sin_reintento(actor, vinculo.receta_id,
                    uuid.uuid5(identidad, f"entrega:{vinculo.receta_id}"), turno_receta_id=vinculo.pk, fecha=hoy)
            else:
                clave = str(vinculo.receta_id)
                propia = (causas.get(clave) or motivos.get(clave)) and resolver_causa(causas.get(clave, ""), motivos.get(clave, ""))
                no_entregadas[vinculo.pk] = propia or general
                if not no_entregadas[vinculo.pk][1]:
                    raise ValidationError("Indica un motivo para cada receta no entregada.")
        if not entregas and not general[1]:
            raise ValidationError("Indica el motivo del cierre sin entrega.")
        cierre = CierreAtencion.objects.create(turno=turno, actor=actor, operacion=operacion, instante=ahora,
            resultado="con_entrega" if entregas else "sin_entrega", causa=general[0], motivo=general[1])
        for vinculo in vinculos:
            entrega = entregas.get(vinculo.pk)
            causa, motivo = ("", "") if entrega else no_entregadas[vinculo.pk]
            detalle = DetalleCierre(cierre=cierre, turno_receta=vinculo, entregada=entrega is not None,
                entrega=entrega, causa=causa, motivo=motivo)
            detalle.full_clean()
            detalle.save()
        turno.estado = "atendido" if entregas else "cerrado_sin_entrega"
        turno.cerrado_en, turno.ventanilla, turno.operador = ahora, None, None
        turno.modificado_por, turno.modificado_en = actor, ahora
        turno.save(update_fields=["estado", "cerrado_en", "ventanilla", "operador", "modificado_por", "modificado_en"])
        ventanilla.disponible_desde = ahora
        _evento(turno, turno.estado, ahora, actor, operacion, ventanilla)
        seleccionar = True
    elif tipo in ("rellamar", "ausente"):
        if turno.estado != "llamado" or ventanilla is None:
            raise ValidationError("El turno ya no tiene una atención vigente.")
        _propia(ventanilla, actor)
        if turno.operador_id != actor.pk:
            raise PermissionDenied
        if tipo == "rellamar":
            turno.ultimo_llamado = ahora
            turno.modificado_por, turno.modificado_en = actor, ahora
            turno.save(update_fields=["ultimo_llamado", "modificado_por", "modificado_en"])
            _evento(turno, "rellamado", ahora, actor, operacion, ventanilla)
        else:
            if ahora < turno.ultimo_llamado + timedelta(seconds=60):
                raise ValidationError("Espera un minuto desde el último llamado antes de marcar ausente.")
            turno.estado, turno.cerrado_en = "ausente", ahora
            turno.ventanilla, turno.operador = None, None
            turno.modificado_por, turno.modificado_en = actor, ahora
            turno.save(update_fields=["estado", "cerrado_en", "ventanilla", "operador", "modificado_por", "modificado_en"])
            ventanilla.disponible_desde = ahora
            _evento(turno, "ausente", ahora, actor, operacion, ventanilla)
            seleccionar = True
    elif tipo == "reincorporar":
        if turno.estado != "ausente" or turno.fecha != hoy:
            raise ValidationError("Solo puedes reincorporar un ausente de la jornada actual.")
        vinculos = TurnoReceta.objects.filter(turno=turno)
        if vinculos.exists() and not vinculos.filter(entrega__isnull=True).exists():
            raise ValidationError("Todas las recetas de este turno ya se retiraron; no se puede reincorporar.")
        # Por RUT (paciente_id puede ser nulo y IS NULL juntaría a todos los no registrados).
        if Turno.objects.filter(rut=turno.rut, estado__in=["esperando", "llamado"]).exclude(pk=turno.pk).exists():
            raise ValidationError("El paciente ya tiene otro turno activo.")
        # Spec 08: una receta no puede estar a la vez en un turno activo y en una entrega a domicilio abierta.
        from entregasapp.consultas import recetas_con_despacho_abierto
        if recetas_con_despacho_abierto(vinculos.filter(entrega__isnull=True).values_list("receta_id", flat=True)):
            raise ValidationError("Una receta de este turno tiene una entrega a domicilio abierta. Anula la entrega antes de reincorporar.")
        # Enmienda 04 del 2026-11-15: la edad o la postración ya no bloquean; letra y número se conservan.
        turno.estado, turno.cerrado_en, turno.entrada_cola = "esperando", None, ahora
        turno.modificado_por, turno.modificado_en = actor, ahora
        turno.save(update_fields=["estado", "cerrado_en", "entrada_cola", "modificado_por", "modificado_en"])
        _evento(turno, "reincorporado", ahora, actor, operacion)
        seleccionar = True
    elif tipo == "terminar_turno":
        # Spec 10, RF-10-01 y RF-10-03: hora de término, ventanilla deshabilitada y el llamado de vuelta a la cola.
        if not tiene_rol(actor, JEFA) and ventanilla.operador_id != actor.pk:
            raise PermissionDenied
        llamado = Turno.objects.filter(ventanilla=ventanilla, estado="llamado").first()
        if llamado and not datos["confirmar"]:
            raise ValidationError("Confirma el término de turno: la ventanilla tiene un paciente llamado.")
        if llamado is None and ventanilla.operador_id is None and not ventanilla.habilitada:
            raise ValidationError("La ventanilla ya está deshabilitada y sin operador.")
        if llamado:
            de_otro_dia = llamado.fecha < hoy
            cambios = {"ventanilla": None, "operador": None, "modificado_por": actor, "modificado_en": ahora}
            if de_otro_dia:
                cambios.update(estado="sin_atencion_cierre", cerrado_en=ahora)
            else:
                # Conserva entrada_cola: vuelve con su antigüedad (decisión del 2026-11-14).
                cambios.update(estado="esperando", ultimo_llamado=None)
            if not Turno.objects.filter(pk=llamado.pk, estado="llamado", ventanilla=ventanilla).update(**cambios):
                raise ConflictoCola
            llamado.refresh_from_db()
            _evento(llamado, "sin_atencion_cierre" if de_otro_dia else "devuelto_a_cola", ahora, actor, operacion, ventanilla)
            turno = operacion.turno = llamado
        OcupacionVentanilla.objects.filter(ventanilla=ventanilla, cierre__isnull=True).update(cierre=ahora, motivo="termino_turno")
        ventanilla.operador = None
        ventanilla.automatico = False
        ventanilla.fecha_activacion = None
        ventanilla.habilitada = False
        ventanilla.disponible_desde = ahora
        seleccionar = True
    elif tipo in ("reclasificar", "urgencia"):
        # Spec 10, RF-10-04 a RF-10-06: número nuevo de la serie de destino, con la antigüedad intacta.
        if turno.estado != "esperando" or turno.fecha != hoy:
            raise ValidationError("Solo se puede cambiar un turno que sigue esperando en la jornada actual.")
        if turno.letra == Letra.URGENCIA:
            raise ValidationError("El turno ya es urgencia, y la urgencia no se puede quitar.")
        nueva = Letra.URGENCIA if tipo == "urgencia" else datos["letra"]
        if nueva == turno.letra:
            raise ValidationError("El turno ya está en esa fila.")
        contador, _ = ContadorTurnosDiario.objects.get_or_create(fecha=turno.fecha, letra=nueva)
        observado = contador.ultimo_numero
        if not ContadorTurnosDiario.objects.filter(pk=contador.pk, ultimo_numero=observado).update(
                ultimo_numero=F("ultimo_numero") + 1):
            raise ConflictoCola
        letra_anterior, numero_anterior = turno.letra, turno.numero
        if not Turno.objects.filter(pk=turno.pk, estado="esperando", letra=letra_anterior, numero=numero_anterior).update(
                letra=nueva, numero=observado + 1, tipo_atencion=TIPO_POR_LETRA[nueva],
                modificado_por=actor, modificado_en=ahora):
            raise ConflictoCola
        turno.refresh_from_db()
        _evento(turno, "urgencia" if tipo == "urgencia" else "reclasificado", ahora, actor, operacion,
            letra_anterior=letra_anterior, numero_anterior=numero_anterior)
        seleccionar = True
    elif tipo == "pesos":
        config = ConfiguracionCola.objects.filter(pk=1).first()
        if config is None:
            raise ValidationError("Prepara la configuración de cola antes de cambiar los pesos.")
        for nombre, valor in datos.items():
            setattr(config, nombre, valor)
        config.version += 1
        config.modificado_por = actor
        config.save()
        registrar_accion(actor, "cola.pesos_cambiados", config)
        seleccionar = True
    elif tipo == "crear_ventanilla":
        if Ventanilla.objects.filter(numero=datos["numero"]).exists():
            raise ValidationError("El número de ventanilla ya existe.")
        if set(datos["tipos"]) - set(TipoAtencionVentanilla.objects.values_list("codigo", flat=True)):
            raise ValidationError("Tipos de atención no válidos.")
        ventanilla = Ventanilla.objects.create(numero=datos["numero"], creado_por=actor, modificado_por=actor)
        ventanilla.tipos.set(datos["tipos"])
        operacion.ventanilla = ventanilla
    else:
        raise ValidationError("La acción solicitada no es válida.")
    if ventanilla is not None:
        ventanilla.version += 1
        ventanilla.modificado_por = actor
        ventanilla.save()
        registrar_accion(actor, "ventanilla." + tipo, ventanilla)
    resultado = {"operacion": str(identidad)}
    if turno:
        resultado.update(turno=turno.pk, estado=turno.estado)
        if tipo in ("reclasificar", "urgencia"):
            resultado["codigo"] = turno.codigo
    if ventanilla:
        resultado.update(ventanilla=ventanilla.pk, automatico=ventanilla.automatico)
    if seleccionar:
        pendiente = solicitar_seleccion(tipo, uuid.uuid5(identidad, "seleccion"))
        resultado["pendiente"] = str(pendiente.pk)
    operacion.resultado = resultado
    operacion.save()
    return resultado


def _ejecutar(actor, tipo, destino, operacion_id, datos=None):
    try:
        identidad = uuid.UUID(str(operacion_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("La confirmación no es válida.") from None
    datos = datos or {}
    huella = hashlib.sha256(json.dumps({"tipo": tipo, "destino": destino, "datos": datos}, sort_keys=True).encode()).hexdigest()
    for intento in range(12):
        try:
            return _operar(actor, tipo, destino, identidad, datos, huella)
        except (ConflictoCola, ConflictoOperacion):
            pass
        except OperationalError as error:
            if not any(marca in str(error).lower() for marca in ("locked", "busy")):
                raise
        except IntegrityError as error:
            if not any(marca in str(error).lower() for marca in (
                "operacionatencion", "ventanilla.operador_id", "ocupacion_vigente_", "turno_activo_rut_dia_unico",
                "contador_fecha_letra_unico", "turno_numero_letra_diario_unico",
                "turnosapp_turno.rut", "turnosapp_estadocoladiaria.fecha", "turnosapp_estadocoladiaria_fecha_",
            )):
                raise
        if intento < 11:
            time.sleep(min(.02 * 2 ** intento, .12) + uniform(0, .02))
    raise ValidationError("La operación está ocupada. Reintenta con la misma confirmación.")


def ocupar_ventanilla(actor, ventanilla_id, operacion_id):
    return _ejecutar(actor, "ocupar", ventanilla_id, operacion_id)


def iniciar_automatico(actor, ventanilla_id, operacion_id):
    return _ejecutar(actor, "iniciar", ventanilla_id, operacion_id)


def pausar_ventanilla(actor, ventanilla_id, operacion_id):
    return _ejecutar(actor, "pausar", ventanilla_id, operacion_id)


def liberar_ventanilla(actor, ventanilla_id, operacion_id):
    return _ejecutar(actor, "liberar", ventanilla_id, operacion_id)


def configurar_ventanilla(actor, ventanilla_id, operacion_id, *, habilitada=None, retirada=None, tipos=None, confirmar=False):
    if any(valor is not None and not isinstance(valor, bool) for valor in (habilitada, retirada)) or not isinstance(confirmar, bool):
        raise ValidationError("Indica estados válidos para la ventanilla.")
    if tipos is not None and (not isinstance(tipos, (list, tuple)) or any(not isinstance(t, str) for t in tipos)):
        raise ValidationError("Indica tipos de atención válidos.")
    return _ejecutar(actor, "configurar", ventanilla_id, operacion_id, {"habilitada": habilitada,
        "retirada": retirada, "tipos": sorted(set(tipos)) if tipos is not None else None, "confirmar": confirmar})


def configurar_pesos(actor, operacion_id, *, preferencial, cronicos, general):
    if any(not isinstance(valor, int) or isinstance(valor, bool) or valor < 1 for valor in (preferencial, cronicos, general)):
        raise ValidationError("Los pesos deben ser enteros positivos.")
    return _ejecutar(actor, "pesos", None, operacion_id, {"peso_preferencial": preferencial, "peso_cronicos": cronicos, "peso_general": general})


def crear_ventanilla(actor, operacion_id, *, numero, tipos):
    if not isinstance(numero, int) or isinstance(numero, bool) or numero < 1 or not isinstance(tipos, (tuple, list)) or any(not isinstance(t, str) for t in tipos):
        raise ValidationError("Número o tipos de ventanilla no válidos.")
    return _ejecutar(actor, "crear_ventanilla", None, operacion_id, {"numero": numero, "tipos": sorted(set(tipos))})


def rellamar(actor, turno_id, operacion_id):
    return _ejecutar(actor, "rellamar", turno_id, operacion_id)


def marcar_ausente(actor, turno_id, operacion_id):
    return _ejecutar(actor, "ausente", turno_id, operacion_id)


def reincorporar(actor, turno_id, operacion_id):
    return _ejecutar(actor, "reincorporar", turno_id, operacion_id)


def finalizar_atencion(actor, turno_id, operacion_id, *, recetas_entregadas, motivo="", motivos=None,
                       causa="", causas=None):
    """Cierra la atención. `causa`/`causas` (RF-05-14) son códigos de `CausaNoEntrega`; `motivo`/`motivos`, el
    detalle de «Otro» o, sin código, el texto libre anterior a la enmienda (se guarda como «Otro»)."""
    if not isinstance(recetas_entregadas, (list, tuple)) or any(not isinstance(pk, int) or isinstance(pk, bool) or pk < 1 for pk in recetas_entregadas):
        raise ValidationError("Indica las recetas entregadas del turno.")
    if not isinstance(motivo, str) or len(motivo) > 500 or (motivos is not None and not isinstance(motivos, dict)):
        raise ValidationError("Indica motivos válidos de hasta 500 caracteres.")
    if not isinstance(causa, str) or (causa and causa not in CAUSAS_VALIDAS) or (causas is not None and not isinstance(causas, dict)):
        raise ValidationError("Indica una causa de no entrega válida.")
    normalizados = {}
    for pk, texto in (motivos or {}).items():
        if not str(pk).isdigit() or int(pk) < 1 or not isinstance(texto, str) or len(texto) > 500:
            raise ValidationError("Indica motivos válidos para las recetas no entregadas.")
        normalizados[str(int(pk))] = texto.strip()
    codigos = {}
    for pk, codigo in (causas or {}).items():
        if not str(pk).isdigit() or int(pk) < 1 or not isinstance(codigo, str) or (codigo and codigo not in CAUSAS_VALIDAS):
            raise ValidationError("Indica una causa de no entrega válida.")
        if codigo:
            codigos[str(int(pk))] = codigo
    for codigo, texto in [(causa, motivo.strip()), *((codigos[pk], normalizados.get(pk, "")) for pk in codigos)]:
        if codigo == CausaNoEntrega.OTRO and len(texto) > DETALLE_OTRO_MAXIMO:
            raise ValidationError(f"El detalle de «Otro» admite hasta {DETALLE_OTRO_MAXIMO} caracteres.")
    datos = {"recetas": sorted(set(recetas_entregadas)), "motivo": motivo.strip(), "motivos": normalizados}
    if causa or codigos:
        # Solo con causas: las llamadas anteriores conservan la misma huella de la operación.
        datos.update(causa=causa, causas=codigos)
    return _ejecutar(actor, "finalizar", turno_id, operacion_id, datos)


def terminar_turno_ventanilla(actor, ventanilla_id, operacion_id, *, confirmar=False):
    """Spec 10, RF-10-01: «Término de turno». La Q.F. sobre cualquier ventanilla; el Técnico, sobre la suya."""
    if not isinstance(confirmar, bool):
        raise ValidationError("Indica si confirmas el término de turno.")
    return _ejecutar(actor, "terminar_turno", ventanilla_id, operacion_id, {"confirmar": confirmar})


def reclasificar_turno(actor, turno_id, operacion_id, *, letra):
    """Spec 10, RF-10-04: cambia un turno en espera entre las filas P, G y C."""
    if letra not in (Letra.PREFERENCIAL, Letra.GENERAL, Letra.CRONICOS):
        raise ValidationError("Elige la fila P, G o C.")
    return _ejecutar(actor, "reclasificar", turno_id, operacion_id, {"letra": str(letra)})


def marcar_urgencia(actor, turno_id, operacion_id):
    """Spec 10, RF-10-05: número nuevo de la serie U; se llama antes que P, C y G (RF-05-13)."""
    return _ejecutar(actor, "urgencia", turno_id, operacion_id)
