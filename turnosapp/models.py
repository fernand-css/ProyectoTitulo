"""Persistencia de llegadas y numeración diaria, sin dispensación de recetas."""

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from coreapp.models import ModeloAuditado


class ContadorTurnosDiario(models.Model):
    fecha = models.DateField(unique=True)
    ultimo_numero = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ultimo_numero__gte=0), name="turnos_contador_no_negativo",
            ),
        ]

    def __str__(self):
        return f"Contador de turnos {self.fecha}"


class Turno(ModeloAuditado):
    class TipoAtencion(models.TextChoices):
        GENERAL = "general", "General"
        PREFERENCIAL = "preferencial", "Preferencial"
        CRONICOS = "cronicos", "Crónicos"

    class Estado(models.TextChoices):
        ESPERANDO = "esperando", "Esperando"

    paciente = models.ForeignKey(
        "recetasapp.Paciente", on_delete=models.PROTECT, related_name="turnos",
    )
    fecha = models.DateField()
    numero = models.PositiveIntegerField()
    tipo_atencion = models.CharField(max_length=12, choices=TipoAtencion.choices)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.ESPERANDO)
    operacion_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["fecha", "numero"], name="turno_numero_diario_unico"),
            models.UniqueConstraint(
                fields=["paciente", "fecha"], condition=Q(estado="esperando"),
                name="turno_activo_paciente_dia_unico",
            ),
            models.CheckConstraint(condition=Q(numero__gte=1), name="turno_numero_positivo"),
            models.CheckConstraint(
                condition=Q(tipo_atencion__in=["general", "preferencial", "cronicos"]),
                name="turno_tipo_valido",
            ),
            models.CheckConstraint(condition=Q(estado="esperando"), name="turno_estado_valido"),
        ]
        indexes = [
            models.Index(fields=["fecha", "estado", "tipo_atencion"], name="turno_fecha_estado_tipo_idx"),
        ]

    def __str__(self):
        return f"Turno {self.fecha} / {self.numero}"


class TurnoReceta(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="recetas_vinculadas")
    receta = models.ForeignKey(
        "recetasapp.Receta", on_delete=models.PROTECT, related_name="turnos_vinculados",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["turno", "receta"], name="turno_receta_unica"),
        ]

    def clean(self):
        super().clean()
        if self.turno_id and self.receta_id:
            # La misma comprobación debe hacerse dentro del servicio de emisión.
            if self.turno.paciente_id != self.receta.paciente_id:
                raise ValidationError({"receta": "La receta debe pertenecer al paciente del turno."})

    def __str__(self):
        return f"Vínculo de turno {self.turno_id} / receta {self.receta_id}"
