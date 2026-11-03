"""Emisión pública sin identificadores y operación privada protegida por roles."""
from django.urls import path
from . import views
from . import vistas_operacion as personal

app_name = "turnosapp"

urlpatterns = [
    path("panel/", personal.PanelView.as_view(), name="panel"),
    path("estado/", personal.EstadoView.as_view(), name="estado"),
    path("gestion/", personal.GestionView.as_view(), name="gestion"),
    path("gestion/ventanillas/nueva/", personal.VentanillaView.as_view(), name="ventanilla_nueva"),
    path("gestion/ventanillas/<int:pk>/", personal.VentanillaView.as_view(), name="ventanilla_configurar"),
    path("gestion/pesos/", personal.PesosView.as_view(), name="pesos"),
    path("ventanillas/<int:pk>/<slug:accion>/", personal.AccionView.as_view(), name="accion_ventanilla"),
    path("<int:pk>/finalizar/", personal.FinalizarView.as_view(), name="finalizar_atencion"),
    path("<int:pk>/historial/", personal.HistorialView.as_view(), name="historial"),
    path("<int:pk>/<slug:accion>/", personal.AccionTurnoView.as_view(), name="accion_turno"),
    path("pendientes/<uuid:referencia>/reintentar/", personal.ReintentarView.as_view(), name="reintentar"),
    path("totem/", views.totem, name="totem"),
    path("totem/finalizar/", views.finalizar, name="finalizar"),
    path("totem/continuar/", views.continuar, name="continuar"),
]
