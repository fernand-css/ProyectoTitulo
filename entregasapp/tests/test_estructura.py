"""Estructura accesible de las pantallas del 08: un solo h1, ids únicos, etiquetas y textos alternativos.

No reemplaza la revisión con navegador, axe ni la usabilidad con cinco personas (RNF-04): esas quedan pendientes
de evidencia propia. Aquí se revisa lo que se puede comprobar en el HTML servido.
"""

import shutil
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from coreapp.tests.test_plantillas import DocumentoHTML
from entregasapp.services import agregar_foto, guardar_domicilio, programar_entrega, registrar_no_entregada
from .ayudas import archivo, equipo, hoy, imagen, paciente, receta


class EstructuraTests(TestCase):
    def setUp(self):
        carpeta = Path(tempfile.mkdtemp(prefix="cesfam-estructura-"))
        ajuste = override_settings(ARCHIVOS_PRIVADOS_ROOT=carpeta)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.addCleanup(shutil.rmtree, carpeta, True)
        self.equipo = equipo()
        self.persona = paciente(edad=88)
        receta(self.persona)
        domicilio = guardar_domicilio(self.equipo["encargado"], self.persona.pk, {
            "sector": "rojo", "localidad": "Dadinco", "direccion": "Camino a Dadinco km 2", "referencias": "Casa roja"})
        agregar_foto(self.equipo["encargado"], domicilio.pk, archivo(imagen()), "Portón verde")
        self.entrega = programar_entrega(self.equipo["qf"], self.persona.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        otra = paciente(edad=91)
        receta(otra)
        pendiente = programar_entrega(self.equipo["qf"], otra.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        registrar_no_entregada(self.equipo["encargado"], pendiente.intentos.get().pk, "sin_receptor", "", uuid.uuid4())
        futura = paciente(edad=93)
        receta(futura)
        programar_entrega(self.equipo["qf"], futura.pk, hoy() + timedelta(days=2), self.equipo["encargado"].pk, uuid.uuid4())

    def revisar(self, html, nombre):
        documento = DocumentoHTML(html)
        self.assertEqual(sum(1 for etiqueta, _ in documento.elementos if etiqueta == "h1"), 1, nombre)
        ids = [atributos["id"] for _, atributos in documento.elementos if "id" in atributos]
        self.assertEqual(len(ids), len(set(ids)), f"ids repetidos en {nombre}")
        etiquetados = {atributos["for"] for etiqueta, atributos in documento.elementos if etiqueta == "label" and "for" in atributos}
        for etiqueta, atributos in documento.elementos:
            if etiqueta == "img":
                self.assertTrue(atributos.get("alt"), f"imagen sin texto alternativo en {nombre}")
            if etiqueta in ("input", "select", "textarea") and atributos.get("type") not in ("hidden", "submit"):
                self.assertIn(atributos.get("id"), etiquetados, f"campo sin etiqueta en {nombre}: {atributos.get('name')}")

    def test_pantallas_de_la_farmacia(self):
        self.client.force_login(self.equipo["qf"])
        paginas = {
            "programacion": reverse("entregasapp:programacion"),
            "programar": reverse("entregasapp:programar"),
            "programar paciente": reverse("entregasapp:programar") + f"?paciente={self.persona.pk}",
            "pendientes": reverse("entregasapp:pendientes"),
            "detalle": reverse("entregasapp:detalle", args=[self.entrega.pk]),
            "domicilios": reverse("entregasapp:domicilios"),
            "domicilio": reverse("entregasapp:domicilio", args=[self.persona.pk]),
            "excepciones": reverse("entregasapp:excepciones"),
            "ficha datos": reverse("recetasapp:paciente_detalle", args=[self.persona.pk]) + "?pestana=datos",
        }
        for nombre, url in paginas.items():
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.revisar(respuesta.content.decode(), nombre)

    def test_pantallas_del_encargado(self):
        self.client.force_login(self.equipo["encargado"])
        intento = self.entrega.intentos.get()
        paginas = {
            "mis entregas": reverse("entregasapp:mis"),
            "registro": reverse("entregasapp:registro", args=[intento.pk]),
            "domicilio": reverse("entregasapp:domicilio", args=[self.persona.pk]),
            "domicilios": reverse("entregasapp:domicilios"),
        }
        for nombre, url in paginas.items():
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.revisar(respuesta.content.decode(), nombre)
        html = self.client.get(reverse("entregasapp:mis")).content.decode()
        self.assertIn('alt="Portón verde"', html)
        self.assertIn('class="visita', html)
