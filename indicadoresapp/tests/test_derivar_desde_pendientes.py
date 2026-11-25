"""RF-07-13 y RF-13-22: «Derivar a domicilio» en «Pendientes de retiro», solo para la Q.F. y en las filas «Sin retirar»."""

import uuid

from django.test import TestCase
from django.urls import reverse

from entregasapp import services as reparto
from .ayudas import equipo, hoy, paciente, preparada

PENDIENTES = reverse("recetasapp:preparacion_pendientes")


class DerivarDesdePendientesTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.sin_retirar = paciente(edad=85)
        preparada(self.sin_retirar, usuario=self.e["tecnico"])
        self.en_despacho = paciente(edad=86)
        preparada(self.en_despacho, usuario=self.e["tecnico"])
        reparto.derivar_desde_merma(self.e["qf"], self.en_despacho.pk, hoy(), self.e["encargado"].pk, uuid.uuid4())

    def enlace(self, persona):
        return f'href="{reverse("indicadoresapp:mermas_derivar", args=[persona.pk])}"'

    def test_la_qf_ve_el_enlace_solo_en_las_filas_sin_retirar(self):
        for usuario in (self.e["qf"], self.e["admin"]):
            self.client.force_login(usuario)
            respuesta = self.client.get(PENDIENTES)
            self.assertContains(respuesta, self.enlace(self.sin_retirar), count=1)
            self.assertNotContains(respuesta, self.enlace(self.en_despacho))
            self.assertContains(respuesta, "En despacho")

    def test_el_tecnico_no_lo_ve_y_sigue_registrando_retiros(self):
        self.client.force_login(self.e["tecnico"])
        respuesta = self.client.get(PENDIENTES)
        self.assertNotContains(respuesta, "Derivar a domicilio")
        self.assertContains(respuesta, "Registrar retiro")

    def test_la_busqueda_en_vivo_conserva_el_enlace(self):
        self.client.force_login(self.e["qf"])
        respuesta = self.client.post(PENDIENTES, {"buscar": self.sin_retirar.apellidos},
                                     HTTP_X_BUSQUEDA_EN_VIVO="1")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.enlace(self.sin_retirar))
