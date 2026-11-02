"""Autenticación del personal habilitado con el usuario de Django."""

from django.contrib.auth.backends import ModelBackend

from coreapp.roles import estado_acceso


class BackendPersonal(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        usuario = super().authenticate(request, username=username, password=password, **kwargs)
        return usuario if usuario is not None and estado_acceso(usuario)[0] else None
