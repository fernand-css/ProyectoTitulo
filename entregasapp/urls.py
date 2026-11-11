"""Rutas del reparto a domicilio (spec 08). Solo identificadores internos: nunca RUT ni nombres."""

from django.urls import path

from . import views

app_name = "entregasapp"

urlpatterns = [
    path("", views.IndiceView.as_view(), name="indice"),
    path("programacion/", views.ProgramacionView.as_view(), name="programacion"),
    path("programar/", views.ProgramarView.as_view(), name="programar"),
    path("pendientes/", views.PendientesView.as_view(), name="pendientes"),
    path("<int:pk>/", views.DetalleEntregaView.as_view(), name="detalle"),
    path("<int:pk>/reasignar/", views.ReasignarView.as_view(), name="reasignar"),
    path("<int:pk>/anular/", views.AnularView.as_view(), name="anular"),
    path("recetas/<int:pk>/revisada/", views.RevisadaView.as_view(), name="receta_revisada"),
    path("mis/", views.MisEntregasView.as_view(), name="mis"),
    path("intentos/<int:pk>/", views.RegistroView.as_view(), name="registro"),
    path("intentos/<int:pk>/entregada/", views.EntregadaView.as_view(), name="intento_entregada"),
    path("intentos/<int:pk>/no-entregada/", views.NoEntregadaView.as_view(), name="intento_no_entregada"),
    path("domicilios/", views.DomiciliosView.as_view(), name="domicilios"),
    path("domicilios/paciente/<int:pk>/", views.DomicilioView.as_view(), name="domicilio"),
    path("domicilios/<int:pk>/verificar/", views.VerificarView.as_view(), name="domicilio_verificar"),
    path("domicilios/<int:pk>/fotos/", views.FotoAgregarView.as_view(), name="foto_agregar"),
    path("fotos/<int:pk>/", views.FotoView.as_view(), name="foto"),
    path("fotos/<int:pk>/eliminar/", views.FotoEliminarView.as_view(), name="foto_eliminar"),
    path("excepciones/", views.ExcepcionesView.as_view(), name="excepciones"),
    path("excepciones/<int:pk>/retirar/", views.ExcepcionRetirarView.as_view(), name="excepcion_retirar"),
]
