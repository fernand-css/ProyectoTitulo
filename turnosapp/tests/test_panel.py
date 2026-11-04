"""Pantallas privadas y formularios sobre datos sintéticos."""
import uuid
from datetime import timedelta
from html.parser import HTMLParser
from unittest.mock import patch

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from recetasapp.models import EntregaReceta, PreparacionReceta, Receta
from turnosapp.models import CierreAtencion, TurnoReceta, Ventanilla
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

    def preparar(self):
        recibida = timezone.now() - timedelta(minutes=3)
        return [PreparacionReceta.objects.create(turno_receta=vinculo, recibida_en=recibida) for vinculo in self.vinculos]

    def test_panel_muestra_las_recetas_del_turno_llamado_con_su_boton(self):
        preparaciones = self.preparar()
        for respuesta in (self.client.get(self.url("panel")).content.decode(),
                          self.client.get(self.url("estado")).json()["html"]):
            self.assertIn("Recetas del turno", respuesta)
            self.assertIn("CIERRE-DEMO-0", respuesta)
            self.assertIn("CIERRE-DEMO-1", respuesta)
            self.assertEqual(respuesta.count(">Marcar lista<"), 2)
            self.assertIn(reverse("recetasapp:preparacion_lista", args=[preparaciones[0].pk]), respuesta)

    def test_marcar_lista_desde_el_panel_vuelve_al_panel(self):
        preparaciones = self.preparar()
        url = reverse("recetasapp:preparacion_lista", args=[preparaciones[0].pk])
        respuesta = self.client.post(url, {"volver": "panel"})
        self.assertRedirects(respuesta, self.url("panel"), fetch_redirect_response=False)
        preparaciones[0].refresh_from_db()
        self.assertEqual(preparaciones[0].lista_por, self.personal["tecnico"])
        html = self.client.get(self.url("panel")).content.decode()
        self.assertEqual(html.count(">Corregir marca<"), 1)
        self.assertEqual(html.count(">Marcar lista<"), 1)
        deshacer = reverse("recetasapp:preparacion_deshacer", args=[preparaciones[0].pk])
        self.assertRedirects(self.client.post(deshacer, {"volver": "panel"}), self.url("panel"), fetch_redirect_response=False)
        preparaciones[0].refresh_from_db()
        self.assertIsNone(preparaciones[0].lista_en)

    def test_destino_de_retorno_solo_admite_el_panel(self):
        preparacion = self.preparar()[0]
        url = reverse("recetasapp:preparacion_lista", args=[preparacion.pk])
        for volver in ("", "https://ajeno.example/", "//ajeno.example", "otro"):
            with self.subTest(volver=volver):
                respuesta = self.client.post(url, {"volver": volver})
                self.assertRedirects(respuesta, reverse("recetasapp:preparacion"), fetch_redirect_response=False)

    def test_qf_sin_ventanilla_no_ve_recetas_del_turno(self):
        self.preparar()
        self.client.force_login(self.personal["qf"])
        self.assertNotContains(self.client.get(self.url("panel")), "Recetas del turno")

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


class AtencionReorganizadaTests(DatosCierre, TestCase):
    """La pantalla de Atención: fila y ventanillas a un lado, la persona atendida al otro."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.personal["tecnico"])

    def html(self):
        return self.client.get(reverse("turnosapp:estado")).json()["html"]

    def test_la_persona_en_ventanilla_muestra_sus_datos_y_la_ficha_del_paciente(self):
        html = self.html()
        self.assertIn("Ventanilla 1", html)
        self.assertIn("Paciente sintético Cola", html)
        self.assertIn(f'href="{reverse("recetasapp:paciente_detalle", args=[self.actual.paciente_id])}">Ver ficha del paciente</a>', html)
        self.assertIn("Finalizar y confirmar entregas", html)
        self.assertIn('class="cola-puesto cola-puesto-activo"', html)

    def test_la_fila_dice_cuantas_recetas_trae_cada_turno(self):
        con_recetas = self.turno(espera=300)
        for indice in range(2):
            receta = Receta.objects.create(
                paciente=con_recetas.paciente, codigo=f"FILA-DEMO-{indice}", fecha_inicio=self.fecha,
                fecha_fin_exclusiva=self.fecha + timedelta(days=30), vigencia_meses=1, max_entregas=3)
            TurnoReceta.objects.create(turno=con_recetas, receta=receta)
        self.turno(espera=60)  # un turno sin recetas vinculadas no menciona recetas
        html = self.html()
        fila = html[html.index('<ol class="cola-fila"'):html.index("</ol>", html.index('<ol class="cola-fila"'))]
        self.assertIn("2 recetas", fila)
        self.assertEqual(fila.count("receta"), 1)
        self.assertIn(f'href="{reverse("turnosapp:historial", args=[con_recetas.pk])}"', fila)

    def test_todas_las_ventanillas_se_listan_con_su_estado_y_se_marca_la_propia(self):
        self.activar(numero=2)
        Ventanilla.objects.filter(numero=3).update(habilitada=False)
        html = self.html()
        lista = html[html.index('id="ventanillas-titulo"'):html.index("</ul>", html.index('id="ventanillas-titulo"'))]
        self.assertIn("Ventanilla 1 (la tuya)", lista)
        self.assertIn(f"Atendiendo el turno {self.actual.numero}", lista)
        self.assertIn("Ventanilla 2", lista)
        self.assertIn("Libre, llamando", lista)
        self.assertIn("Deshabilitada", lista)

    def test_la_jefa_ve_la_fila_y_las_ventanillas_sin_controles_de_atencion(self):
        self.client.force_login(self.personal["qf"])
        html = self.html()
        self.assertIn("Fila de espera", html)
        self.assertIn("Ventanillas", html)
        self.assertIn("Gestionar ventanillas y pesos", html)
        for ausente in ("Re-llamar", "Marcar lista", "Finalizar y confirmar entregas", "Ver ficha del paciente"):
            self.assertNotIn(ausente, html)

    def test_las_migas_dicen_atencion(self):
        html = self.client.get(reverse("turnosapp:panel")).content.decode()
        self.assertIn(f'<li><a href="{reverse("turnosapp:panel")}">Atención</a></li>', html)
        self.assertNotIn(">Turnos</a></li>", html)
