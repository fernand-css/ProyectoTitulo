"""RF-08-05: fotos privadas del domicilio, sin metadatos, con máximo de tres y sin archivos huérfanos."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from PIL import Image

from coreapp.models import RegistroAuditoria
from entregasapp.models import FotoDomicilio
from entregasapp.services import agregar_foto, eliminar_foto, guardar_domicilio, verificar_domicilio
from .ayudas import archivo, equipo, imagen, paciente

DATOS = {"sector": "azul", "localidad": "Dadinco", "direccion": "Camino a Dadinco km 2", "referencias": "Casa roja"}


class CarpetaPrivadaMixin:
    def setUp(self):
        super().setUp()
        self.carpeta = Path(tempfile.mkdtemp(prefix="cesfam-fotos-"))
        ajuste = override_settings(ARCHIVOS_PRIVADOS_ROOT=self.carpeta)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.addCleanup(shutil.rmtree, self.carpeta, True)

    def archivos(self):
        return sorted(p.name for p in self.carpeta.rglob("*") if p.is_file())


class FotosServicioTests(CarpetaPrivadaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.paciente = paciente()
        self.domicilio = guardar_domicilio(self.encargado, self.paciente.pk, DATOS)

    def agregar(self, contenido=None, descripcion="Portón verde", actor=None, nombre="foto.jpg"):
        return agregar_foto(actor or self.encargado, self.domicilio.pk, archivo(contenido or imagen(), nombre), descripcion)

    def test_jpeg_con_gps_y_png_se_guardan_privados_como_jpeg_sin_metadatos(self):
        con_gps = self.agregar(imagen(exif_gps=True))
        png = self.agregar(imagen("PNG", modo="RGBA"), "Camino de entrada", nombre="foto.png")
        self.assertEqual([con_gps.posicion, png.posicion], [1, 2])
        for foto in (con_gps, png):
            ruta = self.carpeta / foto.archivo.name
            self.assertTrue(ruta.is_file())
            self.assertTrue(foto.archivo.name.startswith("domicilios/") and foto.archivo.name.endswith(".jpg"))
            with Image.open(ruta) as guardada:
                self.assertEqual(guardada.format, "JPEG")
                self.assertEqual(len(guardada.getexif()), 0)
                self.assertEqual((foto.ancho, foto.alto), guardada.size)
            self.assertEqual(foto.bytes, ruta.stat().st_size)
        self.assertNotIn("media", str(self.carpeta / con_gps.archivo.name).split("cesfam-fotos-")[1])
        self.assertEqual(RegistroAuditoria.objects.filter(accion="domicilio.foto_agregada").count(), 2)

    def test_cuarta_foto_y_archivos_invalidos_se_rechazan_sin_dejar_archivos(self):
        for numero in range(3):
            self.agregar(descripcion=f"Vista {numero + 1}")
        with self.assertRaisesMessage(ValidationError, "ya tiene 3 fotos"):
            self.agregar(descripcion="Cuarta")
        pdf = b"%PDF-1.4\n%%EOF"
        with self.assertRaisesMessage(ValidationError, "no es una foto"):
            self.agregar(pdf, nombre="plano.jpg")
        with self.assertRaisesMessage(ValidationError, "más de 5 MB"):
            self.agregar(imagen() + b"\0" * (6 * 1024 * 1024))
        self.assertEqual(FotoDomicilio.objects.count(), 3)
        self.assertEqual(len(self.archivos()), 3)

    def test_descripcion_obligatoria_y_roles(self):
        for descripcion in ("", "   ", "x" * 121):
            with self.subTest(largo=len(descripcion)), self.assertRaises(ValidationError):
                self.agregar(descripcion=descripcion)
        with self.assertRaises(PermissionDenied):
            self.agregar(actor=self.equipo["tecnico"])
        self.agregar(actor=self.equipo["qf"])
        self.agregar(actor=self.equipo["admin"])
        self.assertEqual(len(self.archivos()), 2)

    def test_borrar_elimina_la_fila_y_el_archivo_despues_de_confirmar(self):
        foto = self.agregar()
        with self.captureOnCommitCallbacks(execute=True):
            eliminar_foto(self.equipo["qf"], foto.pk)
        self.assertFalse(FotoDomicilio.objects.exists())
        self.assertEqual(self.archivos(), [])
        registro = RegistroAuditoria.objects.get(accion="domicilio.foto_eliminada")
        self.assertEqual(registro.objeto_id, str(foto.pk))
        with self.assertRaises(PermissionDenied):
            eliminar_foto(self.equipo["tecnico"], foto.pk)

    def test_si_falla_la_auditoria_no_queda_fila_ni_archivo_huerfano(self):
        with patch("entregasapp.services.auditar", side_effect=RuntimeError("auditoría")), self.assertRaises(RuntimeError):
            self.agregar()
        self.assertFalse(FotoDomicilio.objects.exists())
        self.assertEqual(self.archivos(), [])
        foto = self.agregar()
        with patch("entregasapp.services.auditar", side_effect=RuntimeError("auditoría")), self.assertRaises(RuntimeError):
            with self.captureOnCommitCallbacks(execute=True):
                eliminar_foto(self.encargado, foto.pk)
        self.assertTrue(FotoDomicilio.objects.filter(pk=foto.pk).exists())
        self.assertEqual(len(self.archivos()), 1)

    def test_agregar_o_borrar_fotos_no_cambia_la_verificacion(self):
        domicilio = verificar_domicilio(self.encargado, self.domicilio.pk, self.domicilio.version)
        foto = self.agregar()
        with self.captureOnCommitCallbacks(execute=True):
            eliminar_foto(self.encargado, foto.pk)
        domicilio.refresh_from_db()
        self.assertIsNotNone(domicilio.verificado_en)
        self.assertEqual(domicilio.version, 2)
