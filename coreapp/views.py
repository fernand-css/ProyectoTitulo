"""Inicio privado y recursos públicos del núcleo."""

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from . import noticias
from .mixins import CuentaHabilitadaMixin


class InicioView(CuentaHabilitadaMixin, TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Solo lee la base: las noticias se copian aparte con `actualizar_noticias`.
        contexto["noticia_destacada"], contexto["noticias_lista"] = noticias.noticias_del_inicio()
        contexto["noticias_sitio"] = noticias.SITIO
        contexto["noticias_actualizadas"] = noticias.ultima_actualizacion()
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
