"""RF-08-05 y RF-08-18: fotos privadas del domicilio, sin metadatos, máximo tres, guardado todo o nada."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from PIL import Image

from coreapp.models import RegistroAuditoria
from entregasapp.models import FotoDomicilio
from entregasapp.services import (
    MENSAJE_FOTOS_CAMBIARON, ErrorFoto, FotoNueva, gestionar_fotos, guardar_domicilio, verificar_domicilio,
)
from .ayudas import archivo, equipo, imagen, paciente

DATOS = {"sector": "azul", "localidad": "Dadinco", "direccion": "Camino a Dadinco km 2", "referencias": "Casa roja"}
PDF = b"%PDF-1.4\n%%EOF"


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


def nueva(numero=1, contenido=None, descripcion="Portón verde", nombre="foto.jpg"):
    return FotoNueva(numero, archivo(contenido or imagen(), nombre), descripcion)


class FotosBase(CarpetaPrivadaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.paciente = paciente()
        self.domicilio = guardar_domicilio(self.encargado, self.paciente.pk, DATOS)

    def ids(self):
        return list(FotoDomicilio.objects.filter(domicilio=self.domicilio).values_list("pk", flat=True))

    def guardar(self, *, borrar=(), nuevas=(), actor=None, mostradas=None):
        with self.captureOnCommitCallbacks(execute=True):
            return gestionar_fotos(actor or self.encargado, self.domicilio.pk,
                                   mostradas=self.ids() if mostradas is None else mostradas, borrar=borrar, nuevas=nuevas)

    def agregar(self, contenido=None, descripcion="Portón verde", actor=None, nombre="foto.jpg"):
        fotos = self.guardar(nuevas=[nueva(1, contenido, descripcion, nombre)], actor=actor)
        return fotos[-1]


class FotosServicioTests(FotosBase):
    """Reglas del RF-08-05, ahora a través del guardado atómico."""

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
        with self.assertRaisesMessage(ValidationError, "como máximo 3 fotos"):
            self.agregar(descripcion="Cuarta")
        with self.assertRaisesMessage(ValidationError, "no es una foto"):
            self.guardar(borrar=self.ids()[:1], nuevas=[nueva(1, PDF, nombre="plano.jpg")])
        with self.assertRaisesMessage(ValidationError, "más de 5 MB"):
            self.guardar(borrar=self.ids()[:1], nuevas=[nueva(1, imagen() + b"\0" * (6 * 1024 * 1024))])
        self.assertEqual(FotoDomicilio.objects.count(), 3)
        self.assertEqual(len(self.archivos()), 3)

    def test_descripcion_obligatoria_y_roles(self):
        for descripcion in ("", "   ", "x" * 121):
            with self.subTest(largo=len(descripcion)), self.assertRaises(ErrorFoto):
                self.agregar(descripcion=descripcion)
        with self.assertRaises(PermissionDenied):
            self.agregar(actor=self.equipo["tecnico"])
        self.agregar(actor=self.equipo["qf"])
        self.agregar(actor=self.equipo["admin"])
        self.assertEqual(len(self.archivos()), 2)
        self.agregar(descripcion="x" * 120)

    def test_borrar_elimina_la_fila_y_el_archivo_despues_de_confirmar(self):
        foto = self.agregar()
        with self.assertRaises(PermissionDenied):
            self.guardar(borrar=[foto.pk], actor=self.equipo["tecnico"])
        self.guardar(borrar=[foto.pk], actor=self.equipo["qf"])
        self.assertFalse(FotoDomicilio.objects.exists())
        self.assertEqual(self.archivos(), [])
        registro = RegistroAuditoria.objects.get(accion="domicilio.foto_eliminada")
        self.assertEqual(registro.objeto_id, str(foto.pk))

    def test_el_archivo_borrado_sigue_en_disco_hasta_confirmar(self):
        foto = self.agregar()
        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            gestionar_fotos(self.encargado, self.domicilio.pk, mostradas=[foto.pk], borrar=[foto.pk])
        self.assertEqual(len(self.archivos()), 1)
        for funcion in pendientes:
            funcion()
        self.assertEqual(self.archivos(), [])

    def test_si_falla_la_auditoria_no_queda_fila_ni_archivo_huerfano(self):
        with patch("entregasapp.services.auditar", side_effect=RuntimeError("auditoría")), self.assertRaises(RuntimeError):
            self.agregar()
        self.assertFalse(FotoDomicilio.objects.exists())
        self.assertEqual(self.archivos(), [])
        foto = self.agregar()
        with patch("entregasapp.services.auditar", side_effect=RuntimeError("auditoría")), self.assertRaises(RuntimeError):
            self.guardar(borrar=[foto.pk])
        self.assertTrue(FotoDomicilio.objects.filter(pk=foto.pk).exists())
        self.assertEqual(len(self.archivos()), 1)

    def test_agregar_o_borrar_fotos_no_cambia_la_verificacion(self):
        domicilio = verificar_domicilio(self.encargado, self.domicilio.pk, self.domicilio.version)
        foto = self.agregar()
        self.guardar(borrar=[foto.pk], nuevas=[nueva(1, descripcion="Buzón azul")])
        domicilio.refresh_from_db()
        self.assertIsNotNone(domicilio.verificado_en)
        self.assertEqual(domicilio.version, 2)


class GestionarFotosTests(FotosBase):
    """RF-08-18: borrados y fotos nuevas se aplican juntos o no se aplica nada."""

    def test_borrar_una_y_agregar_dos_deja_tres_jpeg_sin_metadatos(self):
        primera = self.agregar(descripcion="Vista 1")
        segunda = self.agregar(descripcion="Vista 2")
        nombre_borrado = segunda.archivo.name
        fotos = self.guardar(borrar=[segunda.pk], nuevas=[
            nueva(1, imagen(exif_gps=True), "Fachada blanca"),
            nueva(2, imagen("PNG", modo="RGBA"), "Árbol junto a la entrada", "arbol.png"),
        ])
        self.assertEqual([f.descripcion for f in fotos], ["Vista 1", "Fachada blanca", "Árbol junto a la entrada"])
        self.assertEqual([f.posicion for f in fotos], [1, 2, 3])
        self.assertEqual(fotos[0].pk, primera.pk)
        self.assertFalse(FotoDomicilio.objects.filter(pk=segunda.pk).exists())
        self.assertFalse((self.carpeta / nombre_borrado).exists())
        self.assertEqual(len(self.archivos()), 3)
        for foto in fotos[1:]:
            with Image.open(self.carpeta / foto.archivo.name) as guardada:
                self.assertEqual((guardada.format, len(guardada.getexif())), ("JPEG", 0))
        acciones = list(RegistroAuditoria.objects.filter(accion__startswith="domicilio.foto_")
                        .order_by("pk").values_list("accion", flat=True))
        self.assertEqual(acciones[2:], ["domicilio.foto_eliminada", "domicilio.foto_agregada", "domicilio.foto_agregada"])

    def test_la_foto_2_invalida_no_aplica_ningun_cambio(self):
        guardada = self.agregar(descripcion="Vista 1")
        antes_archivos, antes_auditoria = self.archivos(), RegistroAuditoria.objects.count()
        with self.assertRaises(ErrorFoto) as error:
            self.guardar(borrar=[guardada.pk], nuevas=[nueva(1, descripcion="Casa roja"),
                                                       nueva(2, PDF, "Letrero", "documento.jpg")])
        self.assertEqual(error.exception.numero, 2)
        self.assertEqual(error.exception.messages[0],
                         "La foto 2 no se pudo procesar: el archivo no es una foto JPEG o PNG válida.")
        self.assertEqual(self.ids(), [guardada.pk])
        self.assertEqual(self.archivos(), antes_archivos)
        self.assertEqual(RegistroAuditoria.objects.count(), antes_auditoria)

    def test_descripcion_vacia_o_larga_indica_la_foto(self):
        for descripcion in ("", "x" * 121):
            with self.subTest(largo=len(descripcion)), self.assertRaises(ErrorFoto) as error:
                self.guardar(nuevas=[nueva(1), nueva(2, descripcion=descripcion)])
            self.assertEqual(error.exception.numero, 2)
            self.assertIn("La foto 2 no se pudo procesar", error.exception.messages[0])
        self.assertEqual(self.archivos(), [])
        self.assertFalse(FotoDomicilio.objects.exists())

    def test_conjunto_cambiado_se_rechaza(self):
        foto = self.agregar()
        for mostradas, borrar in (([], ()), ([foto.pk, foto.pk + 99], ()), ([foto.pk], [foto.pk + 99]), (["x"], ())):
            with self.subTest(mostradas=mostradas, borrar=borrar), self.assertRaisesMessage(ValidationError, MENSAJE_FOTOS_CAMBIARON):
                self.guardar(mostradas=mostradas, borrar=borrar, nuevas=[nueva(1, descripcion="Otra")])
        self.assertEqual(self.ids(), [foto.pk])
        self.assertEqual(len(self.archivos()), 1)

    def test_con_tres_solo_se_agrega_si_se_marca_una_para_borrar(self):
        for numero in range(3):
            self.agregar(descripcion=f"Vista {numero + 1}")
        ids = self.ids()
        with self.assertRaisesMessage(ValidationError, "como máximo 3 fotos"):
            self.guardar(borrar=ids[:1], nuevas=[nueva(1), nueva(2)])
        fotos = self.guardar(borrar=ids[:1], nuevas=[nueva(1, descripcion="Reemplazo")])
        self.assertEqual([f.posicion for f in fotos], [1, 2, 3])
        self.assertEqual(fotos[0].descripcion, "Reemplazo")

    def test_falla_en_la_base_borra_los_archivos_nuevos(self):
        self.agregar(descripcion="Vista 1")
        with patch("entregasapp.services.FotoDomicilio.objects.create", side_effect=RuntimeError("base")), \
                self.assertRaises(RuntimeError):
            self.guardar(nuevas=[nueva(1), nueva(2)])
        self.assertEqual(len(self.archivos()), 1)
        self.assertEqual(FotoDomicilio.objects.count(), 1)

    def test_sin_cambios_no_escribe_nada(self):
        foto = self.agregar()
        antes = RegistroAuditoria.objects.count()
        self.assertEqual([f.pk for f in self.guardar()], [foto.pk])
        self.assertEqual(RegistroAuditoria.objects.count(), antes)

    def test_auditoria_sin_datos_personales(self):
        self.agregar(descripcion="Portón verde de Paciente sintético")
        self.guardar(borrar=self.ids())
        for registro in RegistroAuditoria.objects.filter(accion__startswith="domicilio.foto_"):
            texto = str({campo.name: getattr(registro, campo.name) for campo in registro._meta.concrete_fields})
            for prohibido in (self.paciente.rut, self.paciente.apellidos, "Portón", "Dadinco", DATOS["direccion"]):
                self.assertNotIn(prohibido, texto)
