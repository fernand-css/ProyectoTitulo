"""HTTP público, CSRF y aislamiento del contexto de autoservicio."""
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from turnosapp.models import Turno
from coreapp.models import RegistroAuditoria
from recetasapp.models import EntregaReceta
from turnosapp.views import CLAVE
from . import test_servicios as preparacion


class TotemVistasTests(TestCase):
    setUp = preparacion.EmisionTests.setUp
    pacientes = preparacion.EmisionTests.pacientes
    recetas = preparacion.EmisionTests.recetas
    def abrir(self, cliente=None):
        cliente = cliente or self.client
        respuesta = cliente.get(reverse("turnosapp:totem"))
        self.assertEqual(respuesta.status_code, 200)
        return cliente.session[CLAVE]["operacion"]

    def enviar(self, cliente=None, **cambios):
        cliente = cliente or self.client
        datos = {"rut": self.paciente.rut, "operacion_id": cliente.session[CLAVE]["operacion"]}
        datos.update(cambios)
        return cliente.post(reverse("turnosapp:totem"), datos)

    def test_get_no_emite_y_teclado_tiene_k(self):
        self.abrir()
        respuesta = self.client.get(reverse("turnosapp:totem"))
        self.assertContains(respuesta, 'data-tecla="K"')
        self.assertContains(respuesta, 'autocomplete="off"')
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertFalse(Turno.objects.exists())

    def test_resultado_sin_identidad_y_sesion_sin_rut(self):
        self.abrir()
        respuesta = self.enviar(tipo_atencion="urgencia", numero=999, paciente=999, recetas="999")
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, self.paciente.rut)
        self.assertNotContains(respuesta, self.paciente.nombres)
        self.assertNotContains(respuesta, self.receta.codigo)
        self.assertEqual(Turno.objects.get().numero, 1)
        self.assertEqual(Turno.objects.get().tipo_atencion, "general")
        self.assertNotIn(self.paciente.rut, str(dict(self.client.session)))
        self.assertNotIn(self.paciente.rut, respuesta.request["PATH_INFO"])
        self.assertTrue(self.enviar().context["resultado"].recuperado)

    def test_uuid_de_otro_cliente_y_otro_rut_rechazados(self):
        op = self.abrir()
        otro = Client()
        self.abrir(otro)
        self.assertEqual(self.enviar(otro, operacion_id=op).status_code, 400)
        self.assertFalse(Turno.objects.exists())
        self.enviar()
        segundo = self.pacientes(1)
        self.assertEqual(self.enviar(rut=segundo.rut).status_code, 400)
        self.assertEqual(Turno.objects.count(), 1)

    def test_sin_contexto_y_uuid_manipulado_no_emiten(self):
        self.assertEqual(self.client.post(reverse("turnosapp:totem"), {"rut": self.paciente.rut, "operacion_id": uuid.uuid4()}).status_code, 400)
        self.assertEqual(self.enviar(operacion_id=uuid.uuid4()).status_code, 400)
        self.assertFalse(Turno.objects.exists())

    def test_csrf_real_en_emision_finalizacion_y_ampliacion(self):
        cliente = Client(enforce_csrf_checks=True)
        self.abrir(cliente)
        datos = {"rut": self.paciente.rut, "operacion_id": cliente.session[CLAVE]["operacion"]}
        for nombre in ("totem", "finalizar", "continuar"):
            self.assertEqual(cliente.post(reverse("turnosapp:" + nombre), datos).status_code, 403)
        datos["csrfmiddlewaretoken"] = cliente.cookies["csrftoken"].value
        self.assertEqual(cliente.post(reverse("turnosapp:totem"), datos).status_code, 200)

    def test_expiracion_y_ampliacion_validan_contexto(self):
        with patch("turnosapp.views.time.time", return_value=1000):
            op = self.abrir()
        with patch("turnosapp.views.time.time", return_value=1100):
            respuesta = self.client.post(reverse("turnosapp:continuar"), {"operacion_id": op})
            self.assertEqual(respuesta.json()["segundos"], 120)
        with patch("turnosapp.views.time.time", return_value=1221):
            self.assertEqual(self.enviar().status_code, 400)
        self.assertFalse(Turno.objects.exists())

    def test_finalizar_invalida_operacion_y_conserva_sesion_personal(self):
        usuario = get_user_model().objects.create_user(username="totem_personal_sintetico")
        self.client.force_login(usuario)
        op = self.abrir()
        self.enviar()
        self.client.post(reverse("turnosapp:finalizar"), {"operacion_id": op})
        self.assertNotIn(CLAVE, self.client.session)
        self.assertEqual(self.client.session["_auth_user_id"], str(usuario.pk))
        self.assertEqual(self.client.post(reverse("turnosapp:totem"), {"rut": self.paciente.rut, "operacion_id": op}).status_code, 400)
        self.assertEqual(Turno.objects.count(), 1)

    def test_error_no_refleja_entrada_y_fallo_tecnico_no_refleja_excepcion(self):
        self.abrir()
        respuesta = self.enviar(rut="privado-invalido")
        self.assertEqual(respuesta.status_code, 400)
        self.assertNotContains(respuesta, "privado-invalido", status_code=400)
        with patch("turnosapp.views.emitir_turno", side_effect=RuntimeError("detalle privado")):
            respuesta = self.enviar()
        self.assertEqual(respuesta.status_code, 503)
        self.assertNotContains(respuesta, "detalle privado", status_code=503)

    def test_get_de_resultado_y_finalizar_no_abren_turnos_ajenos(self):
        op = self.abrir()
        self.enviar()
        self.abrir()  # GET nuevo invalida operación anterior.
        self.assertEqual(self.enviar(operacion_id=op).status_code, 400)
        self.assertEqual(self.client.get(reverse("turnosapp:finalizar")).status_code, 405)
        self.assertEqual(self.client.get("/turnos/totem/1/").status_code, 404)

    def test_resultado_amplia_por_30_segundos(self):
        op = self.abrir()
        self.enviar()
        respuesta = self.client.post(reverse("turnosapp:continuar"), {"operacion_id": op})
        self.assertEqual(respuesta.json()["segundos"], 30)

    def test_pestana_antigua_no_finaliza_contexto_nuevo(self):
        viejo = self.abrir()
        nuevo = self.abrir()
        self.client.post(reverse("turnosapp:finalizar"), {"operacion_id": viejo})
        self.assertEqual(self.client.session[CLAVE]["operacion"], nuevo)

    def test_ampliacion_caducada_no_revive_operacion(self):
        with patch("turnosapp.views.time.time", return_value=1000):
            op = self.abrir()
        with patch("turnosapp.views.time.time", return_value=1121):
            respuesta = self.client.post(reverse("turnosapp:continuar"), {"operacion_id": op})
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()["vigente"])

    def test_comprobante_minimo_repetido_conserva_contenido_y_no_emite(self):
        self.abrir()
        primera = self.enviar()
        segunda = self.enviar()
        def comprobante(respuesta):
            return respuesta.content.decode().split('<section class="comprobante"', 1)[1].split('</section>', 1)[0]
        papel = comprobante(primera)
        self.assertEqual(papel, comprobante(segunda))
        self.assertIn('class="comprobante-numero">1</p>', papel)
        self.assertNotIn("input", papel)
        self.assertNotIn("csrf", papel)
        self.assertNotIn(self.paciente.rut, papel)
        self.assertNotIn(self.paciente.nombres, papel)
        self.assertNotIn(self.receta.codigo, papel)
        self.assertNotIn("general", papel)
        self.assertContains(primera, "data-imprimir")
        self.assertEqual(Turno.objects.count(), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="turno.emitido").count(), 1)
        self.assertFalse(EntregaReceta.objects.exists())

    def test_entrada_y_error_no_generan_comprobante_imprimible(self):
        respuesta = self.client.get(reverse("turnosapp:totem"))
        self.assertNotContains(respuesta, 'class="comprobante"')
        self.assertNotContains(respuesta, 'data-imprimir')
        respuesta = self.enviar(rut="incorrecto")
        self.assertNotContains(respuesta, 'class="comprobante"', status_code=400)
