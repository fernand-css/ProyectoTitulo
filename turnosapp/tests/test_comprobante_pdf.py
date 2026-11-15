"""RF-04-08: comprobante en PDF solo para la sesión de la operación, sin datos personales."""
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from turnosapp.comprobante import generar_comprobante
from turnosapp.views import CLAVE
from . import test_servicios as preparacion
from .test_vistas import TotemVistasTests


def literal(texto):
    """Texto tal como ReportLab lo escribe en el PDF: WinAnsi y octal para lo que no es ASCII."""
    return "".join(c if ord(c) < 128 else "\\%03o" % c.encode("cp1252")[0] for c in texto).encode("ascii")


class ComprobantePdfTests(TestCase):
    setUp = preparacion.EmisionTests.setUp
    pacientes = preparacion.EmisionTests.pacientes
    recetas = preparacion.EmisionTests.recetas
    abrir = TotemVistasTests.abrir
    enviar = TotemVistasTests.enviar

    def pdf(self, cliente=None, operacion=None):
        cliente = cliente or self.client
        operacion = operacion or cliente.session.get(CLAVE, {}).get("operacion", "")
        return cliente.get(reverse("turnosapp:comprobante_pdf"), {"operacion": operacion})

    def sin_datos_personales(self, contenido, paciente):
        textos = (paciente.rut, paciente.rut.replace("-", ""), paciente.nombres, paciente.apellidos, self.receta.codigo)
        for texto in textos:
            for forma in (texto.encode("utf-8"), texto.encode("cp1252"), literal(texto)):
                self.assertNotIn(forma, contenido)

    def test_pdf_valido_inline_no_store_y_sin_rut_ni_nombre(self):
        self.abrir()
        codigo = self.enviar().context["resultado"].codigo
        respuesta = self.pdf()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertTrue(respuesta.content.startswith(b"%PDF"))
        self.assertTrue(respuesta["Content-Disposition"].startswith("inline"))
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertEqual(respuesta["X-Content-Type-Options"], "nosniff")
        # Con DENY el navegador no dibuja el <object> de resultado.html y muestra el texto alternativo.
        self.assertEqual(respuesta["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn(f"({codigo})".encode(), respuesta.content)  # el texto del PDF va sin comprimir
        self.assertIn(literal("(Tu número de atención)"), respuesta.content)
        self.assertNotIn(b"Necesitas renovar", respuesta.content)
        self.sin_datos_personales(respuesta.content, self.paciente)

    def test_aviso_de_renovacion_estatico_en_pdf_y_pantalla(self):
        self.recetas(self.paciente, "VENCIDA", fecha_inicio=self.fecha - timedelta(days=40), fecha_fin_exclusiva=self.fecha)
        self.abrir()
        respuesta = self.enviar()
        self.assertTrue(respuesta.context["resultado"].renovacion)
        self.assertContains(respuesta, "Necesitas renovar tu receta")
        contenido = self.pdf().content
        self.assertIn(b"(Necesitas renovar tu receta)", contenido)
        self.sin_datos_personales(contenido, self.paciente)

    def test_rut_fuera_del_padron_recibe_pdf_general(self):
        self.abrir()
        self.assertEqual(self.enviar(rut=self.ruts[8]).context["resultado"].codigo, "G-001")
        contenido = self.pdf().content
        self.assertIn(b"(G-001)", contenido)
        self.assertIn(literal("(G · General)"), contenido)
        self.assertNotIn(self.ruts[8].encode(), contenido)

    def test_rechazo_sin_sesion_otra_sesion_sin_resultado_y_tras_finalizar(self):
        self.assertEqual(self.pdf(operacion="00000000-0000-0000-0000-000000000000").status_code, 404)
        op = self.abrir()
        self.assertEqual(self.pdf().status_code, 404)  # sin resultado todavía
        self.enviar()
        otro = Client()
        self.abrir(otro)
        self.assertEqual(self.pdf(otro, op).status_code, 404)  # otro navegador con la operación ajena
        self.assertEqual(Client().get(reverse("turnosapp:comprobante_pdf"), {"operacion": op}).status_code, 404)
        self.assertEqual(self.pdf(operacion="otra").status_code, 404)
        self.assertEqual(self.pdf().status_code, 200)
        self.client.post(reverse("turnosapp:finalizar"), {"operacion_id": op})
        self.assertEqual(self.pdf(operacion=op).status_code, 404)

    def test_rechazo_tras_vencer_y_solo_get(self):
        with patch("turnosapp.views.time.time", return_value=1000):
            op = self.abrir()
            self.enviar()
            self.assertEqual(self.pdf().status_code, 200)
        with patch("turnosapp.views.time.time", return_value=1031):
            self.assertEqual(self.pdf(operacion=op).status_code, 404)
        self.assertEqual(self.client.post(reverse("turnosapp:comprobante_pdf"), {"operacion": op}).status_code, 405)

    def test_cada_letra_cabe_y_usa_su_categoria(self):
        categorias = (("P", "Preferencial"), ("G", "General"), ("C", "Crónicos"), ("U", "Urgencia"))
        for letra, categoria in categorias:
            for renovacion in (False, True):
                contenido = generar_comprobante({
                    "codigo": f"{letra}-999", "letra": letra, "fecha": "02/11/2026", "hora": "09:41",
                    "espera": "Tiempo aproximado de espera: unos 120 minutos.", "renovacion": renovacion,
                })
                self.assertTrue(contenido.startswith(b"%PDF"))
                self.assertIn(literal(f"({letra} · {categoria})"), contenido)
                self.assertIn(b"/MediaBox [ 0 0 1080 1920 ]", contenido)
