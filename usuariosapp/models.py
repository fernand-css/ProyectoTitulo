"""Estado de verificación de correo de las cuentas del personal."""

from django.conf import settings
from django.db import models


class Perfil(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    correo_verificado_en = models.DateTimeField(null=True, blank=True)
    correo_pendiente = models.EmailField(blank=True)
    solicitud_correo = models.UUIDField(null=True, blank=True)

    def __str__(self):
        return f"Perfil de cuenta {self.usuario_id}"
