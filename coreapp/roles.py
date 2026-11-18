"""Roles operativos y estado actual de acceso, comprobado en la base."""

from django.contrib.auth import get_user_model

JEFA = "Jefa de Farmacia"
TECNICO = "Técnico en Farmacia"
ENCARGADO = "Encargado de entrega"
# Spec 13: cuarto rol interno, de solo consulta del panel de mermas; solo lo administra el superusuario.
DIRECTOR = "Director del CESFAM"
TOTEM = "Tótem"
SUPERUSUARIO = "superusuario"

ROLES_INTERNOS = (JEFA, TECNICO, ENCARGADO, DIRECTOR)
ETIQUETAS_ROLES = {
    JEFA: "Q.F.",
    TECNICO: "Técnico en Farmacia",
    ENCARGADO: "Encargado de terreno",
    DIRECTOR: "Dirección del CESFAM",
}


def estado_acceso(usuario):
    """Devolver habilitación y rol sin confiar en grupos/flags en caché."""
    if not usuario.is_authenticated or usuario.pk is None:
        return False, ""
    cuenta = get_user_model().objects.using(usuario._state.db).filter(pk=usuario.pk, is_active=True).first()
    if cuenta is None:
        return False, ""
    if cuenta.is_superuser:
        return True, SUPERUSUARIO
    roles = list(cuenta.groups.filter(name__in=ROLES_INTERNOS).values_list("name", flat=True))
    if len(roles) != 1 or not hasattr(cuenta, "perfil"):
        return False, ""
    return True, roles[0]
