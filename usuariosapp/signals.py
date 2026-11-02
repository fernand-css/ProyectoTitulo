"""Auditoría de autenticación; los cambios de cuentas se registran en servicios."""

import logging

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from coreapp.auditoria import LOGIN, LOGIN_FALLIDO, LOGOUT, registrar_evento


logger = logging.getLogger(__name__)


@receiver(user_logged_in, dispatch_uid="usuariosapp.auditoria.login")
def auditar_login(sender, request, user, **kwargs):
    try:
        registrar_evento(user, LOGIN, objeto=user)
    except Exception:
        # Django ya preparó la sesión antes de emitir esta señal.
        if request is not None:
            try:
                request.session.flush()
            finally:
                request.user = AnonymousUser()
        raise


@receiver(user_login_failed, dispatch_uid="usuariosapp.auditoria.login_fallido")
def auditar_login_fallido(sender, **kwargs):
    # No leer credentials ni request: ambos pueden contener información sensible.
    registrar_evento(None, LOGIN_FALLIDO)


@receiver(user_logged_out, dispatch_uid="usuariosapp.auditoria.logout")
def auditar_logout(sender, request, user, **kwargs):
    if user is None or not user.is_authenticated:
        return
    try:
        registrar_evento(user, LOGOUT, objeto=user)
    except Exception:
        # La revocación de la sesión debe continuar aunque falle el registro.
        # No incluir la excepción o petición: pueden contener valores privados.
        logger.error("No se pudo registrar la auditoría del cierre de sesión.")
