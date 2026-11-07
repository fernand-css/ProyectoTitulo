from django.core.validators import RegexValidator
from django.db import models


class Paciente(models.Model):
    # Espacio de nombres deliberadamente distinto de un identificador real.
    identificador_sintetico = models.CharField(
        max_length=11,
        unique=True,
        validators=[RegexValidator(
            regex=r"\ASINT-[0-9]{6}\Z",
            message="Utilice un identificador ficticio SINT-000001.",
        )],
    )
    nombre_ficticio = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("identificador_sintetico",)
        constraints = [models.CheckConstraint(
            condition=models.Q(identificador_sintetico__regex=r"^SINT-[0-9]{6}$"),
            name="paciente_identificador_sintetico",
        )]

    def __str__(self):
        return self.identificador_sintetico
