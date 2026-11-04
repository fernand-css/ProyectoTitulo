"""Modelos de auditoría compartidos, sin datos de pacientes."""

from django.conf import settings
from django.db import models


class ModeloAuditado(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        abstract = True


class RegistroAuditoria(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    accion = models.CharField(max_length=60)
    objeto_tipo = models.CharField(max_length=100)
    objeto_id = models.CharField(max_length=40)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["objeto_tipo", "objeto_id"], name="audit_objeto_idx"),
            models.Index(fields=["creado_en"], name="audit_fecha_idx"),
        ]
        ordering = ["-creado_en"]
