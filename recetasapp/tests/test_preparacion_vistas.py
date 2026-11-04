"""Interfaz privada, permisos, CSRF y cabeceras de Preparación."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import Client, TestCase
from django.urls import reverse

from recetasapp.models import PreparacionReceta
from recetasapp.tests import test_preparacion_servicios as fixture
from recetasapp.tests.ayudas import actores
from turnosapp.models import Turno


class PreparacionVistasTests(TestCase):
    setUp = fixture.PreparacionServiciosTests.setUp
    pacientes = fixture.PreparacionServiciosTests.pacientes
    recetas = fixture.PreparacionServiciosTests.recetas
    emitir = fixture.PreparacionServiciosTests.emitir

    def setUpPreparacion(self):
        self.actores = actores()
        self.emitir()
        self.preparacion = PreparacionReceta.objects.get(turno_receta__receta=self.receta)

    def test_usuarios_autorizados_y_no_autorizados_y_no_store(self):
        self.setUpPreparacion()
        for nombre in ("qf", "tecnico", "admin"):
            cliente = Client()
            cliente.force_login(self.actores[nombre])
            respuesta = cliente.get(reverse("recetasapp:preparacion"))
            self.assertEqual(respuesta.status_code, 200)
            self.assertIn("no-store", respuesta["Cache-Control"])
        cliente = Client()
        cliente.force_login(self.actores["encargado"])
        self.assertEqual(cliente.get(reverse("recetasapp:preparacion")).status_code, 403)
        self.assertEqual(Client().get(reverse("recetasapp:preparacion")).status_code, 302)

    def test_post_de_marcar_exige_csrf_y_registra_la_accion(self):
        self.setUpPreparacion()
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.actores["tecnico"])
        url = reverse("recetasapp:preparacion_lista", args=[self.preparacion.pk])
        self.assertEqual(cliente.post(url).status_code, 403)
        cliente.get(reverse("recetasapp:preparacion"))
        token = cliente.cookies["csrftoken"].value
        respuesta = cliente.post(url, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.preparacion.refresh_from_db()
        self.assertIsNotNone(self.preparacion.lista_en)

    def test_busqueda_por_rut_usa_post_y_no_lo_agrega_a_la_url(self):
        self.setUpPreparacion()
        marca = datetime(2026, 11, 2, 11, tzinfo=ZoneInfo("America/Santiago"))
        PreparacionReceta.objects.filter(pk=self.preparacion.pk).update(
            lista_en=marca, lista_por=self.actores["qf"], inicio_medido=marca,
            duracion_segundos=0,
        )
        Turno.objects.filter(pk=self.preparacion.turno_receta.turno_id).update(
            estado="ausente", cerrado_en=marca,
        )
        cliente = Client()
        cliente.force_login(self.actores["qf"])
        respuesta = cliente.post(reverse("recetasapp:preparacion_pendientes"), {"buscar": self.paciente.rut})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(self.paciente.rut, respuesta.content.decode())
        self.assertNotIn(self.paciente.rut, respuesta.wsgi_request.get_full_path())
        self.assertIn("no-store", respuesta["Cache-Control"])

    def test_el_fragmento_de_actualizacion_contiene_la_lista_y_es_privado(self):
        self.setUpPreparacion()
        cliente = Client()
        cliente.force_login(self.actores["tecnico"])
        respuesta = cliente.get(reverse("recetasapp:preparacion"), {"fragmento": "1"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'data-autorefresh')
        self.assertIn("no-store", respuesta["Cache-Control"])
