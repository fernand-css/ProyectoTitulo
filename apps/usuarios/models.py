from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """Identidad operativa; los roles se representan con grupos Django."""

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
