"""Validación y recompresión de imágenes subidas por el personal (nombre reservado por el spec 01).

Es genérico: no sabe de domicilios. Acepta solo JPEG y PNG, corrige la orientación, aplana la transparencia
sobre blanco, reduce el lado mayor y devuelve un JPEG nuevo **sin metadatos** (EXIF, GPS, ICC ni comentarios).
El archivo original nunca se guarda.
"""

import io
import warnings

from django.core.exceptions import ValidationError

MAX_BYTES = 5 * 1024 * 1024
LADO_MAXIMO = 1600
MAX_PIXELES = 40_000_000
CALIDAD = 80
FORMATOS = ("JPEG", "PNG")


def _leer(archivo, max_bytes):
    tamano = getattr(archivo, "size", None)
    if tamano is not None and tamano > max_bytes:
        raise ValidationError("La foto pesa más de 5 MB. Toma otra con menor resolución o elige otra imagen.")
    if hasattr(archivo, "seek"):
        archivo.seek(0)
    datos = archivo.read(max_bytes + 1) if hasattr(archivo, "read") else bytes(archivo)
    if len(datos) > max_bytes:
        raise ValidationError("La foto pesa más de 5 MB. Toma otra con menor resolución o elige otra imagen.")
    if not datos:
        raise ValidationError("El archivo está vacío.")
    return datos


def procesar_imagen(archivo, *, max_bytes=MAX_BYTES, lado_max=LADO_MAXIMO, max_pixeles=MAX_PIXELES, calidad=CALIDAD):
    """Devuelve `(bytes_jpeg, ancho, alto)` o lanza `ValidationError` con un mensaje claro en español."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    datos = _leer(archivo, max_bytes)
    no_imagen = ValidationError("El archivo no es una foto JPEG o PNG válida.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            # Abrir solo lee la cabecera: el tamaño se revisa antes de decodificar los píxeles.
            with Image.open(io.BytesIO(datos), formats=FORMATOS) as imagen:
                ancho, alto = imagen.size
                if ancho * alto > max_pixeles:
                    raise ValidationError("La foto tiene demasiados píxeles. Usa una imagen de menor resolución.")
                imagen.verify()
            with Image.open(io.BytesIO(datos), formats=FORMATOS) as imagen:
                imagen.load()  # Una imagen truncada o dañada falla aquí.
                imagen = ImageOps.exif_transpose(imagen)
                if imagen.mode in ("RGBA", "LA") or (imagen.mode == "P" and "transparency" in imagen.info):
                    imagen = imagen.convert("RGBA")
                    fondo = Image.new("RGB", imagen.size, (255, 255, 255))
                    fondo.paste(imagen, mask=imagen.getchannel("A"))
                    imagen = fondo
                else:
                    imagen = imagen.convert("RGB")
                imagen.thumbnail((lado_max, lado_max), Image.Resampling.LANCZOS)
                limpia = Image.new("RGB", imagen.size)
                limpia.paste(imagen)  # Copia solo los píxeles: ningún metadato viaja a la imagen nueva.
                salida = io.BytesIO()
                limpia.save(salida, format="JPEG", quality=calidad, optimize=True)
    except ValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise no_imagen from None
    except (OSError, SyntaxError, ValueError, TypeError, EOFError):
        raise no_imagen from None
    contenido = salida.getvalue()
    return contenido, limpia.width, limpia.height
