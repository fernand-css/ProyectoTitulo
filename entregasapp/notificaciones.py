"""Bandeja de avisos de reparto y transportes de la demostración (spec 12).

Dos tipos de aviso: «en camino», que nace al iniciar el traslado, y «del día» (enmienda del 2026-11-18), que el
procesador crea solo, una vez por entrega y fecha, entre la hora del aviso y la hora límite.

El destino es el «correo para avisos» del padrón (segunda enmienda). Desde la tercera enmienda se envía a
cualquier correo; si `REPARTO_CORREO_DOMINIOS_PERMITIDOS` tiene dominios, solo a esos.
"""

import json
import smtplib
from datetime import datetime, timedelta
from uuid import uuid4

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import IntegrityError, connection, transaction
from django.db.models import Exists, F, OuterRef
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .checks import leer_hora
from .models import AvisoReparto, Entrega, IntentoEntrega


Estado = AvisoReparto.Estado
Tipo = AvisoReparto.Tipo
VIGENCIA = timedelta(minutes=30)
RESERVA = timedelta(minutes=2)
ESPERAS = (timedelta(seconds=60), timedelta(seconds=120))
ASUNTO = "Reparto de prueba en camino"
MENSAJE = "Tu reparto de prueba está en camino"
TEXTOS = {
    Tipo.EN_CAMINO: (ASUNTO, MENSAJE),
    Tipo.DEL_DIA: (
        "Hoy llega tu reparto de prueba",
        "Tu reparto de prueba está programado para hoy. Te avisaremos cuando vaya en camino.",
    ),
    # El cuerpo del reprogramado se completa con la fecha del intento al enviar (ver `textos`).
    Tipo.REPROGRAMADO: ("Reparto de prueba reprogramado", "Tu reparto de prueba se reprogramó para {fecha}."),
    Tipo.ENTREGADO: ("Reparto de prueba entregado", "Tu reparto de prueba fue entregado."),
    Tipo.NO_ENTREGADO: (
        "No pudimos entregar tu reparto de prueba",
        "No pudimos entregar tu reparto de prueba. La farmacia coordinará una nueva visita.",
    ),
}
VIGENCIA_RESULTADO = timedelta(hours=2)
RESULTADO_ESPERADO = {
    Tipo.ENTREGADO: IntentoEntrega.Resultado.ENTREGADA,
    Tipo.NO_ENTREGADO: IntentoEntrega.Resultado.NO_ENTREGADA,
}


def textos(tipo, fecha=None):
    """Asunto y cuerpo del aviso. Solo el reprogramado lleva dato variable: la fecha, nunca datos del paciente."""
    asunto, cuerpo = TEXTOS[tipo]
    if tipo == Tipo.REPROGRAMADO:
        hoy = timezone.localdate()
        cuerpo = cuerpo.format(fecha="hoy" if fecha in (None, hoy) else f"el {fecha:%d/%m}")
    return asunto, cuerpo
REINTENTAR = "reintentar"


def _nombre_base():
    return str(connection.settings_dict["NAME"])


def dominios_permitidos():
    return tuple(getattr(settings, "REPARTO_CORREO_DOMINIOS_PERMITIDOS", ()))


def destino(correo):
    """RF-12-15 y RF-12-16: (correo, "") si se puede enviar; si no, (None, código técnico sin la dirección).

    Lista de dominios vacía: cualquier correo (tercera enmienda). Con dominios: solo esos, en coincidencia exacta.
    """
    correo = (correo or "").strip()
    if not correo:
        return None, "sin_destino"
    permitidos = dominios_permitidos()
    if permitidos and correo.rpartition("@")[2].lower() not in permitidos:
        return None, "dominio_no_permitido"
    return correo, ""


def _firma(paciente_id, correo):
    valor = json.dumps([_nombre_base(), paciente_id, correo])
    return salted_hmac("entregasapp.aviso-reparto", valor, algorithm="sha256").hexdigest()


def _despertar_al_confirmar(aviso):
    """RF-12-25: si el aviso quedó pendiente, el despachador del servidor web lo envía apenas se confirme."""
    if aviso.estado == Estado.PENDIENTE:
        from .despachador import despachador

        transaction.on_commit(despachador.avisar)
    return aviso


def encolar_salida(intento, ahora):
    paciente_id = intento.entrega.paciente_id
    leido = Entrega.objects.filter(pk=intento.entrega_id).values_list("paciente__correo_avisos", flat=True).first()
    correo, codigo = destino(leido)
    return _despertar_al_confirmar(AvisoReparto.objects.create(
        intento=intento,
        tipo=AvisoReparto.Tipo.EN_CAMINO,
        estado=Estado.PENDIENTE if correo else Estado.OMITIDO,
        creado_en=ahora,
        vence_en=ahora + VIGENCIA,
        proximo_en=ahora,
        firma_destino=_firma(paciente_id, correo) if correo else "",
        codigo_resultado=codigo,
    ))


def encolar_resultado(intento, tipo, ahora):
    """RF-12-19 a RF-12-22: aviso de reasignación o de resultado, en la transacción del servicio que lo origina."""
    leido = Entrega.objects.filter(pk=intento.entrega_id).values_list("paciente__correo_avisos", flat=True).first()
    correo, codigo = destino(leido)
    aviso, creado = AvisoReparto.objects.get_or_create(
        intento=intento, tipo=tipo,
        defaults={
            "estado": Estado.PENDIENTE if correo else Estado.OMITIDO, "creado_en": ahora,
            "vence_en": ahora + VIGENCIA_RESULTADO, "proximo_en": ahora,
            "firma_destino": _firma(intento.entrega.paciente_id, correo) if correo else "",
            "codigo_resultado": codigo,
        },
    )
    return _despertar_al_confirmar(aviso) if creado else aviso


def _franja_del_dia(ahora):
    """Fecha local y vencimiento del aviso del día si `ahora` cae en [hora del aviso, hora límite); si no, None."""
    desde = leer_hora(settings.REPARTO_AVISO_DIA_HORA)
    hasta = leer_hora(settings.REPARTO_AVISO_DIA_LIMITE)
    local = timezone.localtime(ahora)
    if desde is None or hasta is None or not desde <= local.time() < hasta:
        return None
    return local.date(), timezone.make_aware(datetime.combine(local.date(), hasta))


def encolar_del_dia(ahora):
    """RF-12-07 a RF-12-10 y RF-12-16: crea los avisos del día que falten, solo para pacientes con destino válido."""
    franja = _franja_del_dia(ahora)
    if franja is None:
        return 0
    hoy, vence = franja
    ya_avisada = AvisoReparto.objects.filter(entrega_id=OuterRef("entrega_id"), tipo=Tipo.DEL_DIA, fecha=hoy)
    candidatos = IntentoEntrega.objects.filter(
        resultado=IntentoEntrega.Resultado.PENDIENTE, fecha_programada=hoy,
        entrega__estado=Entrega.Estado.PROGRAMADA,
    ).exclude(entrega__paciente__correo_avisos="").exclude(Exists(ya_avisada)).order_by("entrega_id").values_list(
        "pk", "entrega_id", "entrega__paciente_id", "entrega__paciente__correo_avisos",
    )
    creados = 0
    for intento_id, entrega_id, paciente_id, leido in candidatos:
        correo, _ = destino(leido)
        if correo is None:
            continue
        try:
            with transaction.atomic():
                AvisoReparto.objects.create(
                    intento_id=intento_id, entrega_id=entrega_id, fecha=hoy, tipo=Tipo.DEL_DIA,
                    estado=Estado.PENDIENTE, creado_en=ahora, vence_en=vence, proximo_en=ahora,
                    firma_destino=_firma(paciente_id, correo),
                )
        except IntegrityError:
            continue  # Otro procesador lo creó primero: la restricción única garantiza uno por entrega y fecha.
        creados += 1
    return creados


def _recuperar(ahora):
    AvisoReparto.objects.filter(estado=Estado.EN_ENVIO, reserva_hasta__lte=ahora).update(
        estado=Estado.INCIERTO, codigo_resultado="envio_interrumpido",
    )
    AvisoReparto.objects.filter(estado=Estado.RESERVADO, reserva_hasta__lte=ahora).update(
        estado=Estado.PENDIENTE, reserva=None, reserva_hasta=None,
    )
    AvisoReparto.objects.filter(estado=Estado.PENDIENTE, vence_en__lte=ahora).update(
        estado=Estado.OBSOLETO, codigo_resultado="aviso_vencido",
    )


def _reclamar(ahora):
    disponibles = AvisoReparto.objects.filter(
        estado=Estado.PENDIENTE, proximo_en__lte=ahora, vence_en__gt=ahora,
    )
    for aviso_id in list(disponibles.order_by("proximo_en", "id").values_list("pk", flat=True)[:25]):
        token = uuid4()
        if disponibles.filter(pk=aviso_id).update(
            estado=Estado.RESERVADO, reserva=token, reserva_hasta=ahora + RESERVA,
        ):
            return aviso_id, token
    return None


@transaction.atomic
def _preparar(aviso_id, token):
    reservados = AvisoReparto.objects.filter(pk=aviso_id, estado=Estado.RESERVADO, reserva=token)
    aviso = reservados.select_related("intento").first()
    if aviso is None:
        return None

    # Los registros de resultado, la reasignación y la anulación toman primero la misma fila del intento.
    if aviso.tipo == Tipo.DEL_DIA:
        # Vale cualquier intento pendiente de la entrega para esa fecha, aunque haya cambiado el Encargado.
        pendientes = IntentoEntrega.objects.filter(
            entrega_id=aviso.entrega_id, resultado=IntentoEntrega.Resultado.PENDIENTE, fecha_programada=aviso.fecha,
        )
        intento_id = pendientes.values_list("pk", flat=True).first()
        vigente = intento_id is not None and pendientes.filter(pk=intento_id).update(
            fecha_programada=F("fecha_programada"),
        )
        entrega_id = aviso.entrega_id
    elif aviso.tipo in RESULTADO_ESPERADO:
        # Entregado o no entregado: basta con que el intento conserve el resultado que originó el aviso.
        intento = aviso.intento
        vigente = IntentoEntrega.objects.filter(pk=intento.pk, resultado=RESULTADO_ESPERADO[aviso.tipo]).update(
            resultado=F("resultado"),
        )
        entrega_id = intento.entrega_id
    else:
        intento = aviso.intento
        filtro = {"pk": intento.pk, "resultado": IntentoEntrega.Resultado.PENDIENTE}
        if aviso.tipo == Tipo.EN_CAMINO:
            filtro["traslado_iniciado_en__isnull"] = False
        vigente = IntentoEntrega.objects.filter(**filtro).update(modificado_en=F("modificado_en"))
        entrega_id = intento.entrega_id
    entregas = Entrega.objects.filter(pk=entrega_id)
    if aviso.tipo not in RESULTADO_ESPERADO:
        entregas = entregas.filter(estado=Entrega.Estado.PROGRAMADA)
    paciente_id, leido = entregas.values_list("paciente_id", "paciente__correo_avisos").first() or (None, "")
    ahora = timezone.now()
    reservados = reservados.filter(reserva_hasta__gt=ahora)
    if not vigente or paciente_id is None or aviso.vence_en <= ahora:
        reservados.update(
            estado=Estado.OBSOLETO, reserva=None, reserva_hasta=None,
            codigo_resultado="aviso_vencido" if aviso.vence_en <= ahora else "visita_cambiada",
        )
        return None

    # RF-12-17: el correo del padrón debe seguir siendo el firmado y su dominio, permitido.
    correo = (leido or "").strip()
    if not correo or not constant_time_compare(aviso.firma_destino, _firma(paciente_id, correo)):
        codigo = "destino_cambiado"
    else:
        correo, codigo = destino(correo)
    if codigo:
        reservados.update(estado=Estado.OMITIDO, reserva=None, reserva_hasta=None, codigo_resultado=codigo)
        return None
    if reservados.update(
        estado=Estado.EN_ENVIO, reserva_hasta=ahora + RESERVA, intentos_envio=F("intentos_envio") + 1,
    ):
        if aviso.tipo == Tipo.REPROGRAMADO:
            return correo, aviso.tipo, {"fecha": aviso.intento.fecha_programada}
        return correo, aviso.tipo, {}
    return None


def _registrar(aviso_id, token, estado, codigo):
    envio = AvisoReparto.objects.filter(
        pk=aviso_id, reserva=token, estado__in=(Estado.EN_ENVIO, Estado.INCIERTO),
    )
    aviso = envio.first()
    if aviso is None:
        return

    ahora = timezone.now()
    if estado == REINTENTAR:
        if aviso.estado == Estado.EN_ENVIO and aviso.intentos_envio <= len(ESPERAS):
            proximo = ahora + ESPERAS[aviso.intentos_envio - 1]
            if proximo < aviso.vence_en and envio.filter(estado=Estado.EN_ENVIO).update(
                estado=Estado.PENDIENTE, proximo_en=proximo, reserva=None, reserva_hasta=None,
                codigo_resultado=codigo,
            ):
                return
        estado = Estado.FALLIDO

    campos = {"estado": estado, "codigo_resultado": codigo}
    if estado != Estado.INCIERTO:
        campos.update(reserva=None, reserva_hasta=None)
    if estado == Estado.ACEPTADO_SMTP:
        campos["aceptado_en"] = ahora
    envio.update(**campos)


def _rechazo(codigo):
    if 400 <= codigo < 500:
        return REINTENTAR, f"smtp_{codigo}"
    if 500 <= codigo < 600:
        return Estado.FALLIDO, f"smtp_{codigo}"
    return Estado.INCIERTO, "smtp_respuesta_inesperada"


def enviar_simulado(correo, tipo=Tipo.EN_CAMINO, fecha=None):
    asunto, cuerpo = textos(tipo, fecha)
    mensaje = EmailMessage(
        asunto, cuerpo, to=[correo],
        connection=get_connection(backend="django.core.mail.backends.locmem.EmailBackend"),
    )
    mensaje.send()
    return Estado.SIMULADO, "simulado"


def enviar_smtp(correo, tipo=Tipo.EN_CAMINO, fecha=None):
    asunto, cuerpo = textos(tipo, fecha)
    try:
        smtp = get_connection(backend="django.core.mail.backends.smtp.EmailBackend", timeout=10)
    except ValueError:
        return Estado.FALLIDO, "smtp_configuracion"
    try:
        try:
            smtp.open()
        except smtplib.SMTPResponseException as error:
            estado, codigo = _rechazo(error.smtp_code)
            return (Estado.FALLIDO if estado == Estado.INCIERTO else estado), codigo
        except OSError:
            return REINTENTAR, "smtp_sin_conexion"

        try:
            enviados = EmailMessage(asunto, cuerpo, to=[correo], connection=smtp).send()
        except smtplib.SMTPRecipientsRefused as error:
            codigo, _ = next(iter(error.recipients.values()), (550, None))
            return _rechazo(codigo)
        except smtplib.SMTPResponseException as error:
            return _rechazo(error.smtp_code)
        except OSError:
            return Estado.INCIERTO, "smtp_respuesta_perdida"
        except ValueError:
            return Estado.FALLIDO, "smtp_configuracion"
        if enviados == 1:
            return Estado.ACEPTADO_SMTP, "smtp_aceptado"
        return Estado.INCIERTO, "smtp_sin_confirmacion"
    finally:
        try:
            smtp.close()
        except OSError:
            pass  # Desconectarse después de aceptar el mensaje no cambia el resultado del envío.


def procesar_avisos(transporte, *, limite=25):
    """Procesa un lote acotado. Solo la comprobación previa y el resultado usan la base."""
    encolar_del_dia(timezone.now())
    _recuperar(timezone.now())
    procesados = 0
    for _ in range(limite):
        reserva = _reclamar(timezone.now())
        if reserva is None:
            break
        preparado = _preparar(*reserva)
        if preparado is not None:
            correo, tipo, extra = preparado
            _registrar(*reserva, *transporte(correo, tipo, **extra))
        procesados += 1
    return procesados
