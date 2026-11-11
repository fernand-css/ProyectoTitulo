"""Recompresión de imágenes: solo JPEG/PNG, sin metadatos, orientada y con límites (spec 08, RF-08-05)."""

import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from coreapp.utils.custom_image import procesar_imagen


def generar(formato="JPEG", tamano=(64, 48), modo="RGB", exif=None, **opciones):
    color = (200, 40, 40) if modo == "RGB" else (200, 40, 40, 90)
    lienzo = Image.new(modo, tamano, color)
    salida = io.BytesIO()
    if exif is not None:
        opciones["exif"] = exif.tobytes()
    lienzo.save(salida, format=formato, **opciones)
    return salida.getvalue()


def exif_con_gps(orientacion=None):
    exif = Image.Exif()
    exif[0x010F] = "Fabricante sintético"
    exif[0x8825] = {1: "S", 2: (36.0, 30.0, 0.0), 3: "W", 4: (72.0, 12.0, 0.0)}
    if orientacion:
        exif[0x0112] = orientacion
    return exif


def subir(contenido, nombre="foto.jpg"):
    return SimpleUploadedFile(nombre, contenido, content_type="image/jpeg")


class ProcesarImagenTests(SimpleTestCase):
    def abrir(self, contenido):
        imagen = Image.open(io.BytesIO(contenido))
        imagen.load()
        return imagen

    def test_jpeg_con_gps_sale_como_jpeg_sin_metadatos(self):
        original = generar(exif=exif_con_gps())
        self.assertIn(0x8825, self.abrir(original).getexif())
        contenido, ancho, alto = procesar_imagen(subir(original))
        resultado = self.abrir(contenido)
        self.assertEqual((resultado.format, resultado.size, (ancho, alto)), ("JPEG", (64, 48), (64, 48)))
        self.assertEqual(len(resultado.getexif()), 0)
        for clave in ("exif", "icc_profile", "comment", "xmp", "photoshop"):
            self.assertNotIn(clave, resultado.info)
        self.assertNotIn(b"Exif", contenido[:200])
        self.assertNotIn("sintético".encode(), contenido)

    def test_corrige_la_orientacion_antes_de_quitar_el_exif(self):
        contenido, ancho, alto = procesar_imagen(subir(generar(tamano=(40, 20), exif=exif_con_gps(orientacion=6))))
        self.assertEqual((ancho, alto), (20, 40))
        self.assertEqual(len(self.abrir(contenido).getexif()), 0)

    def test_png_con_transparencia_se_aplana_a_jpeg(self):
        contenido, ancho, alto = procesar_imagen(subir(generar("PNG", modo="RGBA"), "foto.png"))
        resultado = self.abrir(contenido)
        self.assertEqual((resultado.format, resultado.mode, (ancho, alto)), ("JPEG", "RGB", (64, 48)))

    def test_reduce_el_lado_mayor_a_1600(self):
        contenido, ancho, alto = procesar_imagen(subir(generar(tamano=(3200, 100))))
        self.assertEqual((ancho, alto), (1600, 50))
        self.assertEqual(self.abrir(contenido).size, (1600, 50))

    def test_rechaza_lo_que_no_es_jpeg_ni_png(self):
        pdf = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF"
        gif = generar("GIF")
        for nombre, contenido in (("PDF renombrado", pdf), ("GIF", gif), ("texto", b"no es una imagen"), ("vacío", b"")):
            with self.subTest(nombre), self.assertRaises(ValidationError):
                procesar_imagen(subir(contenido))

    def test_rechaza_una_imagen_truncada(self):
        completa = generar(tamano=(300, 200), quality=95)
        with self.assertRaisesMessage(ValidationError, "no es una foto JPEG o PNG válida"):
            procesar_imagen(subir(completa[: len(completa) // 2]))

    def test_rechaza_mas_de_5_mb_sin_abrirla(self):
        grande = generar() + b"\0" * (6 * 1024 * 1024)
        with self.assertRaisesMessage(ValidationError, "más de 5 MB"):
            procesar_imagen(subir(grande))
        with self.assertRaisesMessage(ValidationError, "más de 5 MB"):
            procesar_imagen(io.BytesIO(grande))  # sin tamaño declarado: se cuenta al leer

    def test_rechaza_demasiados_pixeles_antes_de_decodificar(self):
        with self.assertRaisesMessage(ValidationError, "demasiados píxeles"):
            procesar_imagen(subir(generar(tamano=(64, 48))), max_pixeles=1000)
