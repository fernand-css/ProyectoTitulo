"""Almacenamiento privado de las fotos de domicilios y ciclo de vida de sus archivos.

Las fotos viven en `ARCHIVOS_PRIVADOS_ROOT`, fuera de `MEDIA_ROOT` y de los estáticos. No existe una URL
pública: solo la vista con sesión y rol (`entregasapp.views.FotoView`) las entrega, sin caché.
"""

import os
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage

CARPETA = "domicilios"


class AlmacenamientoPrivado(FileSystemStorage):
    """Sistema de archivos local sin URL pública; la carpeta se lee del ajuste en cada uso."""

    def __init__(self):
        super().__init__()

    @property
    def base_location(self):
        return settings.ARCHIVOS_PRIVADOS_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Las fotos privadas no tienen URL pública; se sirven solo por su vista con rol.")


_almacenamiento = AlmacenamientoPrivado()


def almacenamiento_privado():
    """Callable del campo de archivo: la migración guarda esta referencia y no la ruta del entorno."""
    return _almacenamiento


def guardar_jpeg(contenido):
    """Escribe un JPEG ya procesado con nombre aleatorio y devuelve el nombre relativo guardado."""
    nombre = f"{CARPETA}/{uuid.uuid4().hex}.jpg"
    return _almacenamiento.save(nombre, ContentFile(contenido))


def borrar(nombre):
    """Elimina un archivo si existe. Se usa al revertir una subida o después de confirmar un borrado."""
    if nombre and _almacenamiento.exists(nombre):
        _almacenamiento.delete(nombre)


def abrir(nombre):
    return _almacenamiento.open(nombre, "rb")
