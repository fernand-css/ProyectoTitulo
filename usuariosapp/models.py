"""Estado de verificación de correo de las cuentas del personal y límite de intentos de acceso."""

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


class IntentoAcceso(models.Model):
    """Intentos de inicio de sesión reservados por huella y ventana de 15 minutos.

    `clave` es una huella `salted_hmac` del equipo (IP de origen) o del usuario escrito junto con el equipo:
    nunca el nombre de usuario ni la IP en claro. El recuento vive en la base porque Daphne y WSGI corren en
    procesos distintos, cada uno con su propia caché en memoria. Solo se escribe desde `limite_acceso.py`.
    """

    clave = models.CharField(max_length=64)
    ventana = models.DateTimeField()
    cantidad = models.PositiveIntegerField(default=0)
    auditado = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["clave", "ventana"], name="intento_acceso_clave_ventana_unico"),
            models.CheckConstraint(condition=models.Q(cantidad__gte=0), name="intento_acceso_cantidad_no_negativa"),
        ]
        indexes = [models.Index(fields=["ventana"], name="intento_acceso_ventana_idx")]

    def __str__(self):
        return f"Intentos de acceso {self.ventana:%Y-%m-%d %H:%M}"
