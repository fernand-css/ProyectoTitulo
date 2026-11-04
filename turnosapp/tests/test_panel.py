"""Pantallas privadas y formularios sobre datos sintéticos."""
import uuid
from html.parser import HTMLParser
from unittest.mock import patch

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from recetasapp.models import EntregaReceta
from turnosapp.models import CierreAtencion, Ventanilla
from .datos_cierre import DatosCierre


class Estructura(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids, self.referencias = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        for nombre in ("for", "aria-describedby", "aria-labelledby"):
            self.referencias.extend(attrs.get(nombre, "").split())


class PanelTests(DatosCierre, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.personal["tecnico"])

    def url(self, nombre, **kwargs):
        return reverse("turnosapp:" + nombre, kwargs=kwargs)

    def cierre(self, **datos):
        return {"operacion_id": str(uuid.uuid4()), "confirmar": "on",
            "recetas_entregadas": [str(r.pk) for r in self.recetas_cierre], **datos}

    def test_panel_y_estado_get_solo_lectura(self):
        self.turno(espera=900)
        for nombre in ("panel", "estado", "finalizar_atencion", "historial"):
            kwargs = {"pk": self.actual.pk} if nombre in ("finalizar_atencion", "historial") else {}
            with self.subTest(nombre=nombre), CaptureQueriesContext(connection) as consultas:
                respuesta = self.client.get(self.url(nombre, **kwargs))
            self.assertEqual(respuesta.status_code, 200)
            self.assertIn("no-store", respuesta["Cache-Control"])
            self.assertFalse(any(q["sql"].lstrip().split()[0].upper() in ("INSERT", "UPDATE", "DELETE") for q in consultas))
        self.assertIn("Prioridad por espera", self.client.get(self.url("estado")).json()["html"])

    def test_roles_y_revocacion(self):
        for actor, esperado in (("encargado", 403), ("qf", 200), ("admin", 200)):
            self.client.force_login(self.personal[actor])
            self.assertEqual(self.client.get(self.url("panel")).status_code, esperado)
        self.client.force_login(self.personal["tecnico"])
        self.personal["tecnico"].groups.clear()
        self.assertEqual(self.client.get(self.url("estado")).status_code, 403)

    def test_anonimo_redirige_a_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url("estado")).status_code, 302)

    def test_qf_configura_sin_confirmar_entregas(self):
        self.client.force_login(self.personal["qf"])
        respuesta = self.client.get(self.url("panel"))
        self.assertContains(respuesta, "Gestionar ventanillas y pesos")
        self.assertContains(respuesta, "Preparación de recetas")
        self.assertContains(respuesta, "Abrir Preparación")
        self.assertNotContains(respuesta, "Finalizar y confirmar entregas")
        self.assertEqual(self.client.post(self.url("finalizar_atencion", pk=self.actual.pk), self.cierre()).status_code, 403)
        self.assertEqual(self.client.get(self.url("gestion")).status_code, 200)

    def test_tecnico_no_configura(self):
        for nombre in ("gestion", "pesos", "ventanilla_nueva"):
            self.assertEqual(self.client.get(self.url(nombre)).status_code, 403)

    def test_otra_ventanilla_no_se_puede_pausar_ni_cerrar(self):
        otra = self.activar(numero=2)
        self.client.force_login(otra.operador)
        self.assertEqual(self.client.get(self.url("finalizar_atencion", pk=self.actual.pk)).status_code, 403)
        respuesta = self.client.post(self.url("accion_ventanilla", pk=self.ventanilla.pk, accion="pausar"), {"operacion_id": uuid.uuid4()})
        self.assertEqual(respuesta.status_code, 403)

    def test_get_no_ejecuta_acciones(self):
        for nombre, argumentos in (("accion_turno", {"pk": self.actual.pk, "accion": "ausente"}),
            ("accion_ventanilla", {"pk": self.ventanilla.pk, "accion": "pausar"}),
            ("reintentar", {"referencia": self.pendiente().pk})):
            self.assertEqual(self.client.get(self.url(nombre, **argumentos)).status_code, 405)

    def test_csrf_obligatorio_en_todos_los_posts(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.personal["admin"])
        destinos = [("accion_turno", {"pk": self.actual.pk, "accion": "ausente"}),
            ("accion_ventanilla", {"pk": self.ventanilla.pk, "accion": "pausar"}),
            ("finalizar_atencion", {"pk": self.actual.pk}), ("pesos", {}),
            ("ventanilla_nueva", {}), ("ventanilla_configurar", {"pk": self.ventanilla.pk}),
            ("reintentar", {"referencia": self.pendiente().pk})]
        for nombre, argumentos in destinos:
            with self.subTest(nombre=nombre):
                self.assertEqual(cliente.post(self.url(nombre, **argumentos), self.cierre()).status_code, 403)

    def test_cierre_repetido_conserva_payload_y_una_entrega(self):
        datos = self.cierre(**{f"motivo_{self.recetas_cierre[0].pk}": "Texto conservado"})
        for _ in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                respuesta = self.client.post(self.url("finalizar_atencion", pk=self.actual.pk), datos)
            self.assertRedirects(respuesta, self.url("panel"), fetch_redirect_response=False)
        self.assertEqual(EntregaReceta.objects.count(), 2)
        self.assertEqual(CierreAtencion.objects.count(), 1)

    def test_cierre_sin_motivo_conserva_uuid_y_no_entrega(self):
        datos = self.cierre(recetas_entregadas=[])
        respuesta = self.client.post(self.url("finalizar_atencion", pk=self.actual.pk), datos)
        self.assertContains(respuesta, "Indica el motivo del cierre sin entrega")
        self.assertContains(respuesta, datos["operacion_id"])
        self.assertFalse(EntregaReceta.objects.exists())

    def test_cierre_parcial_muestra_fallo_siguiente_sin_revertir(self):
        datos = self.cierre(recetas_entregadas=[str(self.recetas_cierre[0].pk)], motivo="No disponible")
        self.turno()
        with patch("turnosapp.cola.registrar_accion", side_effect=RuntimeError("sintético")):
            with self.captureOnCommitCallbacks(execute=True):
                respuesta = self.client.post(self.url("finalizar_atencion", pk=self.actual.pk), datos)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(EntregaReceta.objects.count(), 1)
        # El callback ocurre después de construir la respuesta; el panel expone la recuperación durable.
        self.assertContains(self.client.get(self.url("panel")), "Reintentar selección pendiente")

    def test_error_operativo_conserva_confirmacion(self):
        operacion = str(uuid.uuid4())
        respuesta = self.client.post(self.url("accion_turno", pk=self.actual.pk, accion="ausente"), {"operacion_id": operacion})
        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, operacion, status_code=400)

    def test_gestion_pesos_y_tipos_invalidos(self):
        self.client.force_login(self.personal["qf"])
        respuesta = self.client.post(self.url("pesos"), {"operacion_id": uuid.uuid4(), "preferencial": 0, "cronicos": 1, "general": 1})
        self.assertTrue(respuesta.context["form"].errors)
        respuesta = self.client.post(self.url("ventanilla_nueva"), {"operacion_id": uuid.uuid4(), "numero": 9, "tipos": ["inexistente"]})
        self.assertTrue(respuesta.context["form"].errors)
        self.assertFalse(Ventanilla.objects.filter(numero=9).exists())

    def test_formularios_ids_y_referencias_accesibles(self):
        for nombre in ("finalizar_atencion", "panel"):
            kwargs = {"pk": self.actual.pk} if nombre == "finalizar_atencion" else {}
            html = self.client.get(self.url(nombre, **kwargs)).content.decode()
            estructura = Estructura(html)
            self.assertEqual(len(estructura.ids), len(set(estructura.ids)))
            self.assertFalse(set(estructura.referencias) - set(estructura.ids))
            self.assertEqual(html.count("<main"), 1)

    def test_historial_etiquetas_y_entregas(self):
        self.confirmar()
        respuesta = self.client.get(self.url("historial", pk=self.actual.pk))
        self.assertContains(respuesta, "Llamado")
        self.assertContains(respuesta, "CIERRE-DEMO-0")
