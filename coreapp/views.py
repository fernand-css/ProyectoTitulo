"""Inicio privado y recursos públicos del núcleo."""

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .mixins import CuentaHabilitadaMixin


class InicioView(CuentaHabilitadaMixin, TemplateView):
    template_name = "index.html"


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
