"""Los buscadores que ofrecen RUT lo encuentran completo, en cualquier formato, y a medio escribir.

Pacientes, Todas las recetas, Pendientes de retiro, Domicilios, Programar entrega y Excepciones de reparto usan
`coreapp.utils.rut.condicion_busqueda_rut`. Datos sintéticos de entregasapp.tests.ayudas y del fixture del 07.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import Client, TestCase
from django.urls import reverse

from coreapp.utils.rut import formatear_rut
from entregasapp.tests import ayudas
from recetasapp.models import PreparacionReceta
from recetasapp.tests import test_preparacion_servicios as fixture
from recetasapp.tests.ayudas import actores
from turnosapp.models import Turno


def formatos(rut):
    """El mismo RUT escrito como lo haría una persona: completo de varias formas y a medio escribir."""
    cuerpo, dv = rut.split("-")
    con_puntos = formatear_rut(rut)
    return {
        "sin puntos": rut, "con puntos": con_puntos, "sin guion": cuerpo + dv, "k minúscula": rut.lower(),
        "con espacios": f"  {con_puntos} ", "espacio antes del DV": f"{cuerpo} {dv}",
        "sin DV": cuerpo, "sin DV con puntos": con_puntos.split("-")[0], "comienzo": cuerpo[:5],
        "comienzo con puntos": con_puntos[:6], "guion sin DV": cuerpo + "-",
    }


class BuscadoresConRutTests(TestCase):
    def setUp(self):
        equipo = ayudas.equipo()
        self.persona = ayudas.paciente(edad=85)
        self.otra = ayudas.paciente(edad=85)
        while self.otra.rut[:5] == self.persona.rut[:5]:  # que el comienzo no la encuentre por casualidad
            self.otra = ayudas.paciente(edad=85)
        self.receta = ayudas.receta(self.persona, codigo="BUSQ-RUT-1")
        ayudas.receta(self.otra, codigo="BUSQ-RUT-2")
        self.cliente = Client()
        self.cliente.force_login(equipo["qf"])

    def test_cada_buscador_encuentra_el_rut_en_todos_sus_formatos(self):
        pantallas = {
            "Pacientes": (reverse("recetasapp:pacientes"), {}, self.persona.apellidos, self.otra.apellidos),
            "Todas las recetas": (reverse("recetasapp:recetas_lista"), {}, "BUSQ-RUT-1", "BUSQ-RUT-2"),
            "Domicilios": (reverse("entregasapp:domicilios"), {}, self.persona.apellidos, self.otra.apellidos),
            "Programar entrega": (reverse("entregasapp:programar_lista"), {}, self.persona.apellidos,
                                  self.otra.apellidos),
            "Excepciones": (reverse("entregasapp:excepciones"), {"accion": "buscar"}, self.persona.apellidos,
                            self.otra.apellidos),
        }
        for pantalla, (url, extra, esperado, ajeno) in pantallas.items():
            for forma, valor in formatos(self.persona.rut).items():
                with self.subTest(pantalla=pantalla, forma=forma):
                    html = self.cliente.post(url, {**extra, "buscar": valor}).content.decode()
                    self.assertIn(esperado, html)
                    self.assertNotIn(ajeno, html)


class PendientesDeRetiroConRutTests(TestCase):
    setUp = fixture.PreparacionServiciosTests.setUp
    pacientes = fixture.PreparacionServiciosTests.pacientes
    recetas = fixture.PreparacionServiciosTests.recetas
    emitir = fixture.PreparacionServiciosTests.emitir

    def test_encuentra_el_rut_en_todos_sus_formatos(self):
        actores_ = actores()
        self.emitir()
        preparacion = PreparacionReceta.objects.get(turno_receta__receta=self.receta)
        marca = datetime(2026, 11, 2, 11, tzinfo=ZoneInfo("America/Santiago"))
        PreparacionReceta.objects.filter(pk=preparacion.pk).update(
            lista_en=marca, lista_por=actores_["qf"], inicio_medido=marca, duracion_segundos=0)
        Turno.objects.filter(pk=preparacion.turno_receta.turno_id).update(estado="ausente", cerrado_en=marca)
        cliente = Client()
        cliente.force_login(actores_["tecnico"])
        url = reverse("recetasapp:preparacion_pendientes")
        for forma, valor in formatos(self.paciente.rut).items():
            with self.subTest(forma=forma):
                self.assertIn(self.receta.codigo, cliente.post(url, {"buscar": valor}).content.decode())
        otro = "1" if self.paciente.rut[0] != "1" else "2"
        self.assertNotIn(self.receta.codigo, cliente.post(url, {"buscar": otro + "2345"}).content.decode())
