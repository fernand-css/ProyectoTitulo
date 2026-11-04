"""Modelos compartidos: auditoría y noticias públicas de la comuna, sin datos de pacientes."""

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


class NoticiaComuna(models.Model):
    """Noticia pública del sitio municipal que se muestra en el inicio.

    Guarda solo el texto y los enlaces: la imagen se pide al sitio de la municipalidad y no se copia
    al servidor ni al repositorio. Se llena con `actualizar_noticias`; abrir el inicio nunca la consulta.
    """

    id_externo = models.PositiveIntegerField(unique=True)
    titulo = models.CharField(max_length=300)
    resumen = models.TextField(blank=True)
    publicada_el = models.DateField(null=True, blank=True)
    url = models.URLField(max_length=300)
    imagen_url = models.URLField(max_length=300, blank=True)
    es_salud = models.BooleanField(default=False)
    obtenida_en = models.DateTimeField(auto_now=True)

    class Meta:
        # Las que aún no tienen fecha van al final (PostgreSQL pone los nulos primero en orden descendente).
        ordering = [models.F("publicada_el").desc(nulls_last=True), "-id_externo"]

    def __str__(self):
        return self.titulo
