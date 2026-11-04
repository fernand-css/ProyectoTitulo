"""Rol operativo único, etiqueta de presentación de la cuenta habilitada y menú principal."""

from .navegacion import Persona, armar_menu
from .roles import ETIQUETAS_ROLES, SUPERUSUARIO, estado_acceso


def rol_actual(request):
    usuario = request.user
    if not usuario.is_authenticated:
        return {"rol": "", "nombre_rol": ""}
    habilitada, rol = estado_acceso(usuario)
    if not habilitada:
        return {"rol": "", "nombre_rol": "Acceso pendiente de regularización"}
    if rol == SUPERUSUARIO:
        return {"rol": SUPERUSUARIO, "nombre_rol": "Administración"}
    return {"rol": rol, "nombre_rol": ETIQUETAS_ROLES[rol]}


def _persona(usuario, nombre_rol):
    """Nombre e iniciales de quien tiene la sesión abierta, para la zona de cuenta del menú."""
    nombre = usuario.get_full_name().strip() or usuario.get_username()
    if usuario.first_name or usuario.last_name:
        iniciales = f"{usuario.first_name[:1]}{usuario.last_name[:1]}"
    else:
        iniciales = usuario.get_username()[:1]
    return Persona(nombre=nombre, iniciales=iniciales, rol=nombre_rol)


def menu_principal(request):
    """Menú lateral y barra inferior de la persona con sesión, con la página actual marcada."""
    usuario = request.user
    if not usuario.is_authenticated:
        return {"menu_principal": None}
    contexto = rol_actual(request)
    coincidencia = getattr(request, "resolver_match", None)
    app = getattr(coincidencia, "app_name", "") or ""
    nombre = getattr(coincidencia, "url_name", "") or ""
    return {"menu_principal": armar_menu(
        contexto["rol"], app, nombre, persona=_persona(usuario, contexto["nombre_rol"]),
    )}
