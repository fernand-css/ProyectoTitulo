"""Rutas de indicadoresapp: panel de mermas (spec 13)."""

from django.urls import path

from . import views

app_name = "indicadoresapp"

urlpatterns = [
    path("mermas/", views.PanelMermasView.as_view(), name="mermas"),
    path("mermas/reporte.<str:formato>", views.ReporteMermasView.as_view(), name="mermas_reporte"),
]
