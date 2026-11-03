"""Emisión pública, sin endpoints enumerables de pacientes o turnos."""
from django.urls import path
from . import views

app_name = "turnosapp"

urlpatterns = [
    path("totem/", views.totem, name="totem"),
    path("totem/finalizar/", views.finalizar, name="finalizar"),
    path("totem/continuar/", views.continuar, name="continuar"),
]
