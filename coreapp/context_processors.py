"""Rol operativo único y etiqueta de presentación de la cuenta habilitada."""

from .roles import ETIQUETAS_ROLES, estado_acceso


def rol_actual(request):
    usuario = request.user
    if not usuario.is_authenticated:
        return {"rol": "", "nombre_rol": ""}
    habilitada, rol = estado_acceso(usuario)
    if not habilitada:
        return {"rol": "", "nombre_rol": "Acceso pendiente de regularización"}
    if rol == "superusuario":
        return {"rol": "superusuario", "nombre_rol": "Administración"}
    return {"rol": rol, "nombre_rol": ETIQUETAS_ROLES[rol]}
