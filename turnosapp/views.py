"""Tótem público con operaciones acotadas a la sesión del navegador."""
import logging
import time
import uuid

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EmisionTurnoForm
from .comprobante import generar_comprobante
from .services import MENSAJE_NEUTRO, emitir_turno, registrar_intento_totem
from .sala import estado_sala

CLAVE = "turnos_totem"
logger = logging.getLogger(__name__)


@never_cache
@require_http_methods(["GET", "HEAD"])
def sala(request):
    estado = estado_sala()
    return render(request, "turnos/sala.html", {"estado": estado})


def _nuevo(request):
    contexto = {"operacion": str(uuid.uuid4()), "vence": time.time() + 120}
    request.session[CLAVE] = contexto
    return contexto


def _valido(request):
    contexto = request.session.get(CLAVE, {})
    return contexto if (contexto.get("vence", 0) > time.time() and
        constant_time_compare(str(request.POST.get("operacion_id", "")), contexto.get("operacion", ""))) else None


def _entrada(request, contexto, mensaje="", estado=200):
    contexto = {**contexto, "vence": time.time() + 120}
    contexto.pop("resultado", None)
    request.session[CLAVE] = contexto
    form = EmisionTurnoForm(initial={"operacion_id": contexto["operacion"]})
    if mensaje:
        form.fields["rut"].widget.attrs["aria-invalid"] = "true"
    return render(request, "turnos/totem.html", {
        "form": form,
        "operacion": contexto["operacion"], "mensaje": mensaje, "segundos": 120,
        "teclas": "123456789K0",
    }, status=estado)


def _claves_limite(request):
    """Huellas del equipo para RF-04-12: IP de origen y sesión. Nunca el RUT."""
    claves = [salted_hmac("turnos.totem.limite.ip", request.META.get("REMOTE_ADDR", ""), algorithm="sha256").hexdigest()]
    if request.session.session_key:
        claves.append(salted_hmac("turnos.totem.limite.sesion", request.session.session_key, algorithm="sha256").hexdigest())
    return claves


def _rechazo(request, mensaje=MENSAJE_NEUTRO, estado=400):
    """RF-04-07: tras un rechazo o error se rota la operación para la siguiente persona."""
    return _entrada(request, _nuevo(request), mensaje, estado)


def _datos_resultado(resultado):
    """Solo lo que muestra el comprobante: sin RUT, nombre, recetas ni motivo de la preferencia."""
    return {
        "codigo": resultado.codigo, "letra": resultado.letra,
        "fecha": resultado.fecha.strftime("%d/%m/%Y"),
        "hora": timezone.localtime(resultado.creado_en).strftime("%H:%M"),
        "espera": resultado.espera, "renovacion": bool(resultado.renovacion),
    }


@never_cache
@sensitive_post_parameters("rut")
@sensitive_variables()
@require_http_methods(["GET", "POST"])
def totem(request):
    if request.method == "GET":
        return _entrada(request, _nuevo(request))
    try:
        aceptada = registrar_intento_totem(_claves_limite(request))
    except (DatabaseError, ValidationError):
        logger.error("No se pudo registrar el intento del tótem.")
        return _rechazo(request, "No pudimos confirmar el turno. Reintenta o consulta con el personal.", 503)
    if not aceptada:
        return _rechazo(request)  # Pausa hasta el minuto siguiente; el servicio ya auditó sin RUT.
    contexto = _valido(request)
    if contexto is None:
        return _rechazo(request)
    form = EmisionTurnoForm(request.POST)
    if not form.is_valid():
        return _rechazo(request, "Ingresa un RUT válido, incluido su dígito verificador.")
    huella = salted_hmac("turnos.totem.rut", form.cleaned_data["rut"]).hexdigest()
    if contexto.get("huella") and not constant_time_compare(contexto["huella"], huella):
        return _rechazo(request)
    contexto = {**contexto, "huella": huella}
    request.session[CLAVE] = contexto
    # Guardar la vinculación antes de emitir permite recuperar una respuesta perdida.
    try:
        request.session.save()
        resultado = emitir_turno(form.cleaned_data["rut"], form.cleaned_data["operacion_id"])
    except ValidationError as error:
        return _rechazo(request, " ".join(error.messages))
    except (DatabaseError, RuntimeError):
        logger.error("No se pudo completar la operación del tótem.")
        # Repetir con otra operación recupera el mismo turno activo del RUT (RF-04-06).
        return _rechazo(request, "No pudimos confirmar el turno. Reintenta o consulta con el personal.", 503)
    contexto = {**contexto, "resultado": _datos_resultado(resultado), "vence": time.time() + 30}
    request.session[CLAVE] = contexto
    return render(request, "turnos/resultado.html", {
        "resultado": resultado, "operacion": contexto["operacion"], "segundos": 30,
    })


@never_cache
@xframe_options_sameorigin
@require_http_methods(["GET", "HEAD"])
def comprobante_pdf(request):
    """PDF del número, generado al momento y solo para la sesión de la operación vigente (RF-04-08).

    `resultado.html` lo incrusta con `<object>`: con el `X-Frame-Options: DENY` global del proyecto el
    navegador no lo dibuja y muestra el texto alternativo. Se permite solo el mismo origen.
    """
    contexto = request.session.get(CLAVE, {})
    datos = contexto.get("resultado")
    if not (isinstance(datos, dict) and contexto.get("vence", 0) > time.time() and constant_time_compare(
            str(request.GET.get("operacion", "")), contexto.get("operacion", ""))):
        raise Http404
    respuesta = HttpResponse(generar_comprobante(datos), content_type="application/pdf")
    respuesta["Content-Disposition"] = 'inline; filename="numero-de-atencion.pdf"'
    respuesta["Cache-Control"] = "no-store, private, max-age=0"
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta


@never_cache
@require_POST
def finalizar(request):
    if _valido(request):
        request.session.pop(CLAVE, None)
    return redirect("turnosapp:totem")


@never_cache
@require_POST
def continuar(request):
    contexto = _valido(request)
    if contexto is None:
        return JsonResponse({"vigente": False}, status=400)
    segundos = 30 if contexto.get("resultado") else 120
    request.session[CLAVE] = {**contexto, "vence": time.time() + segundos}
    return JsonResponse({"vigente": True, "segundos": segundos})
