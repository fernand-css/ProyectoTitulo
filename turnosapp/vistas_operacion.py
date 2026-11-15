"""Pantallas privadas; todas las mutaciones pasan por los servicios del 05."""
import uuid
from datetime import timedelta
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.debug import sensitive_post_parameters
from coreapp.mixins import RolRequeridoMixin, tiene_rol
from coreapp.roles import JEFA, TECNICO
from . import atencion
from .cola import procesar_seguro
from .comprobante import generar_comprobante
from .forms import OperacionForm, VentanillaForm, PesosForm, FinalizarForm, ReclasificarForm, TerminarTurnoForm
from .models import ConfiguracionCola, PendienteSeleccion, Turno, Ventanilla
from .panel import contexto_panel


@method_decorator(never_cache, name="dispatch")
@method_decorator(sensitive_post_parameters(), name="dispatch")
class TurnosView(RolRequeridoMixin, View):
    roles_permitidos = (JEFA, TECNICO)

    def render(self, nombre, contexto, **kwargs):
        respuesta = render(self.request, "turnos/" + nombre, contexto, **kwargs)
        respuesta["Referrer-Policy"] = "same-origin"
        return respuesta


class PanelView(TurnosView):
    def get(self, request):
        return self.render("panel.html", contexto_panel(request.user, request.GET.get("pagina", 1)))


class EstadoView(TurnosView):
    def get(self, request):
        datos = contexto_panel(request.user, request.GET.get("pagina", 1))
        propia, vigente = datos["propia"], datos["vigente"]
        firma = f"{vigente.pk if vigente else ''}:{propia.automatico if propia else ''}:{propia.habilitada if propia else ''}:{propia.retirada if propia else ''}:{datos['pagina_cola'].paginator.count}"
        return JsonResponse({"html": render_to_string("turnos/_estado.html", datos, request=request), "firma": firma})


class AccionView(TurnosView):
    roles_permitidos = (TECNICO,)
    es_turno = False

    def post(self, request, pk, accion):
        acciones = {"ocupar": atencion.ocupar_ventanilla, "iniciar": atencion.iniciar_automatico,
            "pausar": atencion.pausar_ventanilla, "liberar": atencion.liberar_ventanilla}
        if self.es_turno:
            acciones = {"rellamar": atencion.rellamar, "ausente": atencion.marcar_ausente, "reincorporar": atencion.reincorporar}
        if accion not in acciones:
            raise Http404
        form = OperacionForm(request.POST)
        if form.is_valid():
            try:
                acciones[accion](request.user, pk, form.cleaned_data["operacion_id"])
            except ValidationError as error:
                form.add_error(None, error)
            except (DatabaseError, RuntimeError):
                form.add_error(None, "No pudimos confirmar la operación. Reintenta con esta misma confirmación.")
            else:
                messages.success(request, "Operación registrada.")
                return redirect("turnosapp:panel")
        return self.render("accion.html", {"form": form, "accion_url": request.path}, status=400)


class AccionTurnoView(AccionView):
    es_turno = True


class GestionView(TurnosView):
    roles_permitidos = (JEFA,)

    def get(self, request):
        return self.render("gestion.html", contexto_panel(request.user))


class VentanillaView(TurnosView):
    roles_permitidos = (JEFA,)

    def mostrar(self, form, ventanilla):
        return self.render("ventanilla_form.html", {"form": form, "ventanilla": ventanilla})

    def get(self, request, pk=None):
        ventanilla = get_object_or_404(Ventanilla, pk=pk) if pk else None
        return self.mostrar(VentanillaForm(ventanilla=ventanilla), ventanilla)

    def post(self, request, pk=None):
        ventanilla = get_object_or_404(Ventanilla, pk=pk) if pk else None
        form = VentanillaForm(request.POST, ventanilla=ventanilla)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                if ventanilla:
                    atencion.configurar_ventanilla(request.user, pk, datos["operacion_id"], tipos=datos["tipos"],
                        habilitada=datos["habilitada"], retirada=datos["retirada"], confirmar=datos["confirmar"])
                else:
                    atencion.crear_ventanilla(request.user, datos["operacion_id"], numero=datos["numero"], tipos=datos["tipos"])
            except ValidationError as error:
                form.add_error(None, error)
            except (DatabaseError, RuntimeError):
                form.add_error(None, "La configuración no fue confirmada. Reintenta con el mismo formulario.")
            else:
                messages.success(request, "Configuración de ventanilla guardada.")
                return redirect("turnosapp:gestion")
        return self.mostrar(form, ventanilla)


class PesosView(TurnosView):
    roles_permitidos = (JEFA,)

    def get(self, request):
        config = ConfiguracionCola.objects.filter(pk=1).first()
        inicial = {"preferencial": config.peso_preferencial, "cronicos": config.peso_cronicos,
            "general": config.peso_general} if config else {}
        return self.render("pesos_form.html", {"form": PesosForm(initial=inicial)})

    def post(self, request):
        form = PesosForm(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                atencion.configurar_pesos(request.user, datos["operacion_id"], preferencial=datos["preferencial"],
                    cronicos=datos["cronicos"], general=datos["general"])
            except ValidationError as error:
                form.add_error(None, error)
            except (DatabaseError, RuntimeError):
                form.add_error(None, "Los pesos no fueron confirmados. Reintenta con el mismo formulario.")
            else:
                messages.success(request, "Pesos de atención guardados.")
                return redirect("turnosapp:gestion")
        return self.render("pesos_form.html", {"form": form})


class FinalizarView(TurnosView):
    roles_permitidos = (TECNICO,)

    def get(self, request, pk):
        turno = get_object_or_404(Turno.objects.select_related("paciente"), pk=pk)
        if turno.estado != "llamado":
            return redirect("turnosapp:historial", pk=pk)
        if turno.operador_id != request.user.pk:
            raise PermissionDenied
        return self.render("finalizar.html", {"form": FinalizarForm(turno=turno), "turno": turno})

    def post(self, request, pk):
        turno = get_object_or_404(Turno.objects.select_related("paciente"), pk=pk)
        if turno.estado == "llamado" and turno.operador_id != request.user.pk:
            raise PermissionDenied
        form = FinalizarForm(request.POST, turno=turno)
        if form.is_valid():
            try:
                resultado = atencion.finalizar_atencion(request.user, pk, form.cleaned_data["operacion_id"], **form.argumentos())
            except ValidationError as error:
                form.add_error(None, error)
            except (DatabaseError, RuntimeError):
                form.add_error(None, "El cierre no fue confirmado. Reintenta con este mismo formulario.")
            else:
                pendiente = PendienteSeleccion.objects.filter(pk=resultado["pendiente"], estado="pendiente").exists()
                if pendiente:
                    messages.warning(request, "Atención finalizada. El próximo llamado está pendiente; las entregas confirmadas se conservaron.")
                else:
                    messages.success(request, "Atención finalizada. Las entregas indicadas quedaron registradas.")
                return redirect("turnosapp:panel")
        return self.render("finalizar.html", {"form": form, "turno": turno})


class HistorialView(TurnosView):
    def get(self, request, pk):
        turno = get_object_or_404(Turno.objects.select_related("paciente"), pk=pk)
        eventos = list(turno.eventos.select_related("ventanilla", "actor").order_by("secuencia"))
        etiquetas = {"llamado": "Llamado", "rellamado": "Re-llamado", "ausente": "Ausente",
            "reincorporado": "Reincorporado a la cola", "atendido": "Atención con entregas registradas",
            "cerrado_sin_entrega": "Cierre sin entrega", "sin_atencion_cierre": "Sin atención al cierre de jornada",
            "devuelto_a_cola": "Devuelto a la fila por término de turno", "reclasificado": "Cambio de fila",
            "urgencia": "Marcado como urgencia"}
        for evento in eventos:
            evento.etiqueta = etiquetas.get(evento.accion, "Evento de atención")
            if evento.numero_anterior:
                evento.etiqueta += f" (antes {evento.letra_anterior}-{evento.numero_anterior:03d})"
        # Spec 10: cambio de fila y urgencia, para la Q.F. y el Técnico, solo mientras espera hoy.
        puede_cambiar = (tiene_rol(request.user, JEFA, TECNICO) and turno.estado == "esperando"
            and turno.fecha == timezone.localdate() and turno.letra != "U")
        return self.render("historial.html", {"turno": turno,
            "eventos": eventos,
            "cierre": getattr(turno, "cierre_atencion", None), "puede_operar": tiene_rol(request.user, TECNICO),
            "hoy": timezone.localdate(), "nonce_reincorporar": uuid.uuid4(),
            "puede_cambiar": puede_cambiar, "form_reclasificar": ReclasificarForm(), "nonce_urgencia": uuid.uuid4()})


class ReintentarView(TurnosView):
    def post(self, request, referencia):
        pendiente = get_object_or_404(PendienteSeleccion, pk=referencia)
        cantidad = procesar_seguro(pendiente.pk)
        if cantidad is None:
            messages.warning(request, "El llamado sigue pendiente. Las entregas confirmadas se conservan.")
        else:
            messages.success(request, "Pendiente revisado sin repetir entregas.")
        return redirect("turnosapp:panel")


# ---- Spec 10: término de turno, cambio de fila, urgencia y comprobante del número nuevo ----

VIGENCIA_COMPROBANTE = timedelta(minutes=15)


class TerminarTurnoView(TurnosView):
    """RF-10-01: la Q.F. sobre cualquier ventanilla; el Técnico, solo sobre la que ocupa."""
    roles_permitidos = (JEFA, TECNICO)

    def ventanilla(self, request, pk):
        ventanilla = get_object_or_404(Ventanilla.objects.select_related("operador"), pk=pk)
        if not tiene_rol(request.user, JEFA) and ventanilla.operador_id != request.user.pk:
            raise PermissionDenied
        return ventanilla

    def destino(self):
        return "turnosapp:gestion" if tiene_rol(self.request.user, JEFA) else "turnosapp:panel"

    def mostrar(self, form, ventanilla, status=200):
        llamado = Turno.objects.filter(ventanilla=ventanilla, estado="llamado").first()
        return self.render("terminar.html", {"form": form, "ventanilla": ventanilla, "llamado": llamado,
            "volver_url": reverse(self.destino())}, status=status)

    def get(self, request, pk):
        return self.mostrar(TerminarTurnoForm(), self.ventanilla(request, pk))

    def post(self, request, pk):
        ventanilla = self.ventanilla(request, pk)
        form = TerminarTurnoForm(request.POST)
        if form.is_valid():
            try:
                resultado = atencion.terminar_turno_ventanilla(request.user, pk, form.cleaned_data["operacion_id"],
                    confirmar=form.cleaned_data["confirmar"])
            except ValidationError as error:
                form.add_error(None, error)
            except (DatabaseError, RuntimeError):
                form.add_error(None, "El término de turno no fue confirmado. Reintenta con este mismo formulario.")
            else:
                mensaje = f"Turno de la ventanilla {ventanilla.numero} terminado. La ventanilla quedó deshabilitada."
                if resultado.get("estado") == "esperando":
                    mensaje += " El paciente llamado volvió a la fila con su antigüedad."
                elif resultado.get("estado") == "sin_atencion_cierre":
                    mensaje += " El llamado de un día anterior quedó cerrado sin atención."
                messages.success(request, mensaje)
                return redirect(self.destino())
        return self.mostrar(form, ventanilla, status=400)


class CambioTurnoView(TurnosView):
    """RF-10-04 y RF-10-05: POST desde el historial; si resulta, abre el comprobante del número nuevo."""
    roles_permitidos = (JEFA, TECNICO)
    urgencia = False

    def post(self, request, pk):
        get_object_or_404(Turno, pk=pk)
        form = (OperacionForm if self.urgencia else ReclasificarForm)(request.POST)
        if not form.is_valid():
            messages.error(request, "Elige una fila válida e inténtalo de nuevo.")
            return redirect("turnosapp:historial", pk=pk)
        try:
            if self.urgencia:
                atencion.marcar_urgencia(request.user, pk, form.cleaned_data["operacion_id"])
            else:
                atencion.reclasificar_turno(request.user, pk, form.cleaned_data["operacion_id"],
                    letra=form.cleaned_data["letra"])
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return redirect("turnosapp:historial", pk=pk)
        except (DatabaseError, RuntimeError):
            messages.error(request, "El cambio no fue confirmado. Vuelve a intentarlo.")
            return redirect("turnosapp:historial", pk=pk)
        return redirect("turnosapp:comprobante_personal", pk=pk)


class UrgenciaView(CambioTurnoView):
    urgencia = True


def _cambio_reciente(turno, usuario):
    """El comprobante del personal se autoriza por el cambio recién registrado, no por la sesión del tótem."""
    evento = turno.eventos.filter(accion__in=["reclasificado", "urgencia"]).order_by("-secuencia").first()
    if evento is None or evento.actor_id != usuario.pk or evento.instante < timezone.now() - VIGENCIA_COMPROBANTE:
        raise Http404
    return evento


def _datos_comprobante(turno, evento):
    from .espera import estimar_espera
    from .services import requiere_renovacion
    espera = ("Tienes prioridad: te llamaremos antes que a los demás números." if turno.letra == "U"
        else estimar_espera().frase)
    return {"codigo": turno.codigo, "letra": turno.letra, "fecha": turno.fecha.strftime("%d/%m/%Y"),
        "hora": timezone.localtime(turno.creado_en).strftime("%H:%M"), "espera": espera,
        "renovacion": bool(turno.paciente and requiere_renovacion(turno.paciente, turno.fecha)),
        "reemplaza": f"{evento.letra_anterior}-{evento.numero_anterior:03d}"}


class ComprobantePersonalView(TurnosView):
    """RF-10-05: el mismo comprobante del tótem, a pantalla completa en el equipo del personal."""

    def get(self, request, pk):
        turno = get_object_or_404(Turno.objects.select_related("paciente"), pk=pk)
        evento = _cambio_reciente(turno, request.user)
        return self.render("comprobante_personal.html", {"turno": turno, "datos": _datos_comprobante(turno, evento),
            "pdf_url": reverse("turnosapp:comprobante_personal_pdf", kwargs={"pk": turno.pk})})


@method_decorator(xframe_options_sameorigin, name="dispatch")
class ComprobantePersonalPdfView(TurnosView):
    def get(self, request, pk):
        turno = get_object_or_404(Turno.objects.select_related("paciente"), pk=pk)
        evento = _cambio_reciente(turno, request.user)
        respuesta = HttpResponse(generar_comprobante(_datos_comprobante(turno, evento)), content_type="application/pdf")
        respuesta["Content-Disposition"] = 'inline; filename="numero-de-atencion.pdf"'
        respuesta["Cache-Control"] = "no-store, private, max-age=0"
        respuesta["X-Content-Type-Options"] = "nosniff"
        return respuesta
