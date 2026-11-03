"""Tótem público con operaciones acotadas a la sesión del navegador."""
import logging
import time
import uuid

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EmisionTurnoForm
from .services import emitir_turno
from .sala import estado_sala

CLAVE = "turnos_totem"
logger = logging.getLogger(__name__)


@never_cache
@require_http_methods(["GET", "HEAD"])
def sala(request):
    estado = estado_sala()
    return render(request, "turnos/sala.html", {"estado": estado})


@never_cache
@require_http_methods(["GET", "HEAD"])
def sala_estado(request):
    return JsonResponse(estado_sala())


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


@never_cache
@sensitive_post_parameters("rut")
@sensitive_variables()
@require_http_methods(["GET", "POST"])
def totem(request):
    if request.method == "GET":
        return _entrada(request, _nuevo(request))
    contexto = _valido(request)
    if contexto is None:
        return _entrada(request, _nuevo(request), "La pantalla expiró. Ingresa nuevamente tu RUT.", 400)
    form = EmisionTurnoForm(request.POST)
    if not form.is_valid():
        return _entrada(request, contexto, "Ingresa un RUT válido, incluido su dígito verificador.", 400)
    huella = salted_hmac("turnos.totem.rut", form.cleaned_data["rut"]).hexdigest()
    if contexto.get("huella") and not constant_time_compare(contexto["huella"], huella):
        return _entrada(request, contexto, "Inicia una nueva atención antes de ingresar otro RUT.", 400)
    contexto = {**contexto, "huella": huella}
    request.session[CLAVE] = contexto
    # Guardar la vinculación antes de emitir permite recuperar una respuesta perdida.
    try:
        request.session.save()
        resultado = emitir_turno(form.cleaned_data["rut"], form.cleaned_data["operacion_id"])
    except ValidationError as error:
        return _entrada(request, contexto, " ".join(error.messages), 400)
    except (DatabaseError, RuntimeError):
        logger.error("No se pudo completar la operación del tótem.")
        return _entrada(request, contexto, "No pudimos confirmar el turno. Reintenta la misma solicitud o consulta con el personal.", 503)
    contexto = {**contexto, "resultado": True, "vence": time.time() + 30}
    request.session[CLAVE] = contexto
    return render(request, "turnos/resultado.html", {
        "resultado": resultado, "operacion": contexto["operacion"], "segundos": 30,
    })


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
