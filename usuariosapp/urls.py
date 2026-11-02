"""Inicio y cierre de sesión con las vistas de autenticación de Django."""

from django.contrib.auth.views import LogoutView, PasswordResetCompleteView, PasswordResetDoneView
from django.urls import path

from .views import (
    CambiarClaveView, IniciarSesionView, PerfilView, RecuperarClaveView,
    RestablecerClaveView, SolicitarVerificacionView, VerificarCorreoView,
    EstadoCuentaView, GestionCuentaView, GestionUsuariosView,
)

app_name = "usuariosapp"

urlpatterns = [
    path("entrar/", IniciarSesionView.as_view(redirect_authenticated_user=True), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    path("perfil/", PerfilView.as_view(), name="perfil"),
    path("perfil/correo/solicitar/", SolicitarVerificacionView.as_view(), name="solicitar_verificacion"),
    path("verificar-correo/<str:token>/", VerificarCorreoView.as_view(), name="verificar_correo"),
    path("clave/cambiar/", CambiarClaveView.as_view(), name="cambiar_clave"),
    path("clave/recuperar/", RecuperarClaveView.as_view(), name="recuperar_clave"),
    path("clave/enviada/", PasswordResetDoneView.as_view(), name="recuperacion_enviada"),
    path("clave/restablecer/<uidb64>/<token>/", RestablecerClaveView.as_view(), name="restablecer_clave"),
    path("clave/lista/", PasswordResetCompleteView.as_view(), name="clave_lista"),
    path("gestion/", GestionUsuariosView.as_view(), name="gestion_usuarios"),
    path("gestion/nuevo/", GestionCuentaView.as_view(), name="gestion_nuevo"),
    path("gestion/<int:pk>/editar/", GestionCuentaView.as_view(), name="gestion_editar"),
    path("gestion/<int:pk>/estado/", EstadoCuentaView.as_view(), name="gestion_estado"),
]
