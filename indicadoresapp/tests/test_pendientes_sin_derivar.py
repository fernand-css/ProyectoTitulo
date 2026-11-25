"""Cambio del 2026-11-25: «Pendientes de retiro» ya no ofrece «Derivar a domicilio» y la pantalla de derivación no existe."""

import uuid

from django.test import TestCase
from django.urls import reverse

from entregasapp import services as reparto
from .ayudas import equipo, hoy, paciente, preparada

PENDIENTES = reverse("recetasapp:preparacion_pendientes")


class PendientesSinDerivarTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.sin_retirar = paciente(edad=85)
        preparada(self.sin_retirar, usuario=self.e["tecnico"])
        self.en_despacho = paciente(edad=86)
        preparada(self.en_despacho, usuario=self.e["tecnico"])
        # Lo que ya viaja en un despacho (datos anteriores al cambio) se sigue mostrando como «En despacho».
        reparto.derivar_desde_merma(self.e["qf"], self.en_despacho.pk, hoy(), self.e["encargado"].pk, uuid.uuid4())

    def test_ningun_rol_ve_derivar_a_domicilio(self):
        for rol in ("qf", "admin", "tecnico"):
            self.client.force_login(self.e[rol])
            respuesta = self.client.get(PENDIENTES)
            self.assertNotContains(respuesta, "Derivar a domicilio")
            self.assertNotContains(respuesta, "/indicadores/mermas/derivar/")
            self.assertContains(respuesta, "Registrar retiro", count=1)
            self.assertContains(respuesta, "En despacho")

    def test_la_busqueda_en_vivo_tampoco_lo_trae(self):
        self.client.force_login(self.e["qf"])
        respuesta = self.client.post(PENDIENTES, {"buscar": self.sin_retirar.apellidos}, HTTP_X_BUSQUEDA_EN_VIVO="1")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Registrar retiro")
        self.assertNotContains(respuesta, "Derivar a domicilio")

    def test_la_pantalla_de_derivacion_ya_no_existe(self):
        self.client.force_login(self.e["qf"])
        self.assertEqual(self.client.get(f"/indicadores/mermas/derivar/{self.sin_retirar.pk}/").status_code, 404)

    def test_el_panel_de_mermas_no_ofrece_derivar(self):
        self.client.force_login(self.e["qf"])
        self.assertNotContains(self.client.get(reverse("indicadoresapp:mermas")), "Derivar a domicilio")
