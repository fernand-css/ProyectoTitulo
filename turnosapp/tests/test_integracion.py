"""Estructura accesible del flujo; no sustituye auditoría de navegador."""
from html.parser import HTMLParser
from django.test import TestCase
from django.urls import reverse
from . import test_servicios as preparacion


class Documento(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elementos = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elementos.append((tag, dict(attrs)))


class IntegracionTotemTests(TestCase):
    setUp = preparacion.EmisionTests.setUp
    pacientes = preparacion.EmisionTests.pacientes
    recetas = preparacion.EmisionTests.recetas

    def comprobar(self, respuesta):
        elementos = Documento(respuesta.content.decode()).elementos
        ids = [attrs["id"] for _, attrs in elementos if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sum(tag == "main" for tag, _ in elementos), 1)
        for tag, attrs in elementos:
            if tag == "label":
                self.assertIn(attrs["for"], ids)
            for id_asociado in attrs.get("aria-describedby", "").split():
                self.assertIn(id_asociado, ids)
        self.assertIn("no-store", respuesta["Cache-Control"])

    def test_entrada_error_y_resultado_con_semantica_y_sin_identidad_publica(self):
        ruta = reverse("turnosapp:totem")
        self.comprobar(self.client.get(ruta))
        op = self.client.session["turnos_totem"]["operacion"]
        error = self.client.post(ruta, {"rut": "invalido", "operacion_id": op})
        self.comprobar(error)
        self.assertContains(error, 'aria-invalid="true"', status_code=400)
        resultado = self.client.post(ruta, {"rut": self.paciente.rut, "operacion_id": op})
        self.comprobar(resultado)
        self.assertNotContains(resultado, self.paciente.rut)
        self.assertNotContains(resultado, self.receta.codigo)
