"""Rutas del proyecto y prefijos de las seis apps."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("usuarios/", include("usuariosapp.urls")),
    path("recetas/", include("recetasapp.urls")),
    path("turnos/", include("turnosapp.urls")),
    path("entregas/", include("entregasapp.urls")),
    path("indicadores/", include("indicadoresapp.urls")),
    path("", include("coreapp.urls")),
]

handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
