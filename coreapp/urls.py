"""Rutas del núcleo compartido."""

from django.urls import path

from . import views

app_name = "coreapp"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("sw.js", views.sw_js, name="sw_js"),
    path("salud/", views.salud, name="salud"),
]
