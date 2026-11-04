"""Padrón privado y control interno de recetas."""

from django.urls import path
from . import views

app_name = "recetasapp"

urlpatterns = [
    path("", views.RecetasView.as_view(), name="recetas"),
    path("pacientes/", views.PacientesView.as_view(), name="pacientes"),
    path("pacientes/<int:pk>/", views.PacienteView.as_view(), name="paciente_detalle"),
    path("nueva/", views.CrearRecetaView.as_view(), name="receta_nueva"),
    path("<int:pk>/", views.RecetaView.as_view(), name="receta_detalle"),
    path("<int:pk>/renovar/", views.CrearRecetaView.as_view(), name="receta_renovar"),
    path("<int:pk>/entregas/confirmar/", views.ConfirmarEntregaView.as_view(), name="entrega_confirmar"),
    path("importaciones/", views.ImportacionesView.as_view(), name="importaciones"),
    path("importaciones/nueva/", views.NuevaImportacionView.as_view(), name="importacion_nueva"),
    path("importaciones/<uuid:referencia>/", views.ImportacionView.as_view(), name="importacion_detalle"),
    path("plantillas/<str:formato>/", views.PlantillaView.as_view(), name="plantilla"),
]
