"""Acceso a vistas por los grupos definidos en coreapp.roles."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render

from .roles import estado_acceso


def tiene_rol(usuario, *roles):
    habilitada, rol = estado_acceso(usuario)
    if not habilitada:
        return False
    return rol == "superusuario" or rol in roles


class CuentaHabilitadaMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not estado_acceso(request.user)[0]:
            return render(request, "403.html", {"acceso_pendiente": True}, status=403)
        return super().dispatch(request, *args, **kwargs)


class RolRequeridoMixin(CuentaHabilitadaMixin, UserPassesTestMixin):
    roles_permitidos = ()

    def test_func(self):
        return tiene_rol(self.request.user, *self.roles_permitidos)
