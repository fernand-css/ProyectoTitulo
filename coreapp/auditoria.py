"""Registro explícito de acciones: actor, acción, referencia y fecha."""

from django.db import DEFAULT_DB_ALIAS

from .models import RegistroAuditoria


LOGIN = "auth.login"
LOGIN_FALLIDO = "auth.login_fallido"
LOGOUT = "auth.logout"
USUARIO_CREADO = "usuario.creado"
ROL_CAMBIADO = "usuario.rol_cambiado"
ACCIONES_CUENTAS = frozenset({
    LOGIN, LOGIN_FALLIDO, LOGOUT, USUARIO_CREADO, ROL_CAMBIADO,
    "usuario.editado", "usuario.activado", "usuario.desactivado",
    "perfil.editado", "correo.confirmado", "clave.cambiada", "clave.restablecida",
    "usuario.privilegios_cambiados",
})


def _guardar_registro(usuario, accion, objeto_tipo, objeto_id, *, using):
    registro = RegistroAuditoria(
        usuario=usuario if usuario and usuario.is_authenticated else None,
        accion=accion, objeto_tipo=objeto_tipo, objeto_id=objeto_id,
    )
    registro._state.db = using
    registro.full_clean(exclude=["usuario"] if registro.usuario_id is None else [])
    registro.save(using=using)
    return registro


def registrar_accion(usuario, accion, objeto, *, using=None):
    if objeto.pk is None or objeto._state.adding:
        raise ValueError("Guarda el objeto antes de registrar la acción.")
    alias = using or objeto._state.db or DEFAULT_DB_ALIAS
    return _guardar_registro(
        usuario, accion, objeto._meta.label, str(objeto.pk), using=alias,
    )


def registrar_evento(usuario, accion, *, objeto=None, using=None):
    """Registrar eventos de cuentas sin aceptar datos libres de la petición.

    Un intento fallido nunca identifica actor ni copia el usuario introducido.
    El llamador incluye esta escritura en la transacción del cambio de negocio.
    """
    if accion not in ACCIONES_CUENTAS:
        raise ValueError("Acción de cuenta no reconocida.")
    if accion == LOGIN_FALLIDO:
        return _guardar_registro(
            None, accion, "auth.User", "no-identificado",
            using=using or DEFAULT_DB_ALIAS,
        )
    if objeto is None:
        raise ValueError("Este evento requiere una referencia de cuenta guardada.")
    return registrar_accion(usuario, accion, objeto, using=using)
