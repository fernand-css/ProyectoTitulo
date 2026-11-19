"""Inicio privado y recursos públicos del núcleo."""

import hashlib
import json

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .context_processors import contadores_de_la_peticion
from .mixins import CuentaHabilitadaMixin
from .roles import DIRECTOR, ENCARGADO, estado_acceso


class InicioView(CuentaHabilitadaMixin, TemplateView):
    template_name = "index.html"

    def get(self, request, *args, **kwargs):
        # Spec 08 (RF-08-13): el inicio del encargado de terreno abre «Mis entregas» en la misma dirección, sin
        # redirigir: así «/» sigue respondiendo 200 para todos los perfiles, como esperan los specs anteriores.
        acceso = estado_acceso(request.user)
        if acceso == (True, ENCARGADO):
            from entregasapp.views import MisEntregasView
            return MisEntregasView.as_view()(request)
        # Spec 13 (RF-13-08): el inicio de la Dirección del CESFAM es el panel de mermas, con la misma técnica.
        if acceso == (True, DIRECTOR):
            from indicadoresapp.views import PanelMermasView
            return PanelMermasView.as_view()(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Lo que espera hoy: las mismas cifras de las insignias del menú, sin repetir la consulta.
        cantidades = contadores_de_la_peticion(self.request, estado_acceso(self.request.user)[1])
        contexto["hoy_en_espera"] = cantidades.get("fila")
        contexto["hoy_por_preparar"] = cantidades.get("por_preparar")
        return contexto


# Spec 11 (RF-11-01): lo único que guarda el service worker, además de la página sin conexión (sin datos).
ESTATICOS_SIN_CONEXION = (
    "css/base.css", "css/menu.css", "css/recetas.css", "css/entregas.css",
    "js/preferencias.js", "js/alpine.min.js", "js/menu.js", "js/pwa.js",
    "js/entregas/almacen.js", "js/entregas/sincronizar.js", "js/entregas/sin_conexion.js",
    "fonts/figtree-latin-wght-normal.woff2", "fonts/atkinson-hyperlegible-next-latin-wght-normal.woff2",
    "icons/marca.svg", "icons/icon-192.png", "manifest.webmanifest",
)


class ServiceWorkerView(TemplateView):
    template_name = "pwa/sw.js"
    content_type = "application/javascript"

    def get_context_data(self, **kwargs):
        """La versión de la caché es la huella de las URL de los estáticos: llevan su versión (`?v=` o el hash de
        `collectstatic`), así que cambia en cuanto cambia un archivo y el service worker nuevo borra la caché vieja."""
        from django.templatetags.static import static
        from django.urls import reverse

        contexto = super().get_context_data(**kwargs)
        estaticos = [static(ruta) for ruta in ESTATICOS_SIN_CONEXION]
        sin_conexion = reverse("entregasapp:sin_conexion")
        contexto.update(
            estaticos=json.dumps(estaticos),
            version=hashlib.sha256("\n".join([*estaticos, sin_conexion]).encode()).hexdigest()[:16],
            sin_conexion_url=json.dumps(sin_conexion),
            sincronizar_url=json.dumps(reverse("entregasapp:sincronizar")),
            almacen_js=json.dumps(static("js/entregas/almacen.js")),
            sincronizar_js=json.dumps(static("js/entregas/sincronizar.js")),
        )
        return contexto

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
