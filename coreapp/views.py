"""Inicio privado y recursos públicos del núcleo."""

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .context_processors import contadores_de_la_peticion
from .mixins import CuentaHabilitadaMixin
from .roles import ENCARGADO, estado_acceso


class InicioView(CuentaHabilitadaMixin, TemplateView):
    template_name = "index.html"

    def get(self, request, *args, **kwargs):
        # Spec 08 (RF-08-13): el inicio del encargado de terreno abre «Mis entregas» en la misma dirección, sin
        # redirigir: así «/» sigue respondiendo 200 para todos los perfiles, como esperan los specs anteriores.
        if estado_acceso(request.user) == (True, ENCARGADO):
            from entregasapp.views import MisEntregasView
            return MisEntregasView.as_view()(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Lo que espera hoy: las mismas cifras de las insignias del menú, sin repetir la consulta.
        cantidades = contadores_de_la_peticion(self.request, estado_acceso(self.request.user)[1])
        contexto["hoy_en_espera"] = cantidades.get("fila")
        contexto["hoy_por_preparar"] = cantidades.get("por_preparar")
        return contexto


class ServiceWorkerView(TemplateView):
    template_name = "pwa/sw.js"
    content_type = "application/javascript"

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Service-Worker-Allowed"] = "/"
        response["Cache-Control"] = "no-cache"
        return response


class SaludView(View):
    def get(self, request):
        try:
            connection.ensure_connection()
        except DatabaseError:
            return JsonResponse({"estado": "error"}, status=503)
        return JsonResponse({"estado": "ok"})


inicio = InicioView.as_view()
sw_js = ServiceWorkerView.as_view()
salud = SaludView.as_view()
