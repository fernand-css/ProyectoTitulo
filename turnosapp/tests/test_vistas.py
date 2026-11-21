"""HTTP público, CSRF y aislamiento del contexto de autoservicio."""
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

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

    def test_resultado_amplia_por_20_segundos(self):
        op = self.abrir()
        self.enviar()
        respuesta = self.client.post(reverse("turnosapp:continuar"), {"operacion_id": op})
        self.assertEqual(respuesta.json()["segundos"], 20)

    def test_resultado_cuenta_20_segundos_con_margen_para_pedir_mas_tiempo(self):
        """Enmienda del 2026-11-19: 20 s en pantalla; «Necesito más tiempo» en el último segundo sigue valiendo."""
        with patch("turnosapp.views.time.time", return_value=1000):
            op = self.abrir()
            respuesta = self.enviar()
        html = respuesta.content.decode()
        self.assertContains(respuesta, 'data-segundos="20"')
        self.assertContains(respuesta, "Esta pantalla vuelve al inicio en <span data-cuenta>20</span> segundos.")
        self.assertContains(respuesta, f'content="20;url={reverse("turnosapp:totem")}"')
        self.assertInHTML('<p class="sr-only" role="status" data-anuncio></p>', html)
        with patch("turnosapp.views.time.time", return_value=1020.5):
            respuesta = self.client.post(reverse("turnosapp:continuar"), {"operacion_id": op})
        self.assertEqual(respuesta.json(), {"vigente": True, "segundos": 20})
        with patch("turnosapp.views.time.time", return_value=1046):  # 1020,5 + 20 + 5 de margen = 1045,5
            respuesta = self.client.post(reverse("turnosapp:continuar"), {"operacion_id": op})
        self.assertEqual(respuesta.status_code, 400)

    def test_volver_al_totem_es_un_formulario_real_que_finaliza(self):
        op = self.abrir()
        respuesta = self.enviar()
        html = respuesta.content.decode()
        self.assertInHTML(
            '<button class="boton boton-secundario" type="submit" form="totem-finalizar" data-volver>Volver al tótem</button>', html)
        self.assertContains(
            respuesta, f'<form id="totem-finalizar" method="post" action="{reverse("turnosapp:finalizar")}" data-finalizar hidden>')
        self.assertContains(respuesta, 'name="csrfmiddlewaretoken"')
        self.assertContains(respuesta, "Necesito más tiempo")
        # Lo mismo que hace el navegador sin JavaScript al pulsarlo: POST a finalizar y vuelta al inicio.
        volver = self.client.post(reverse("turnosapp:finalizar"), {"operacion_id": op})
        self.assertRedirects(volver, reverse("turnosapp:totem"), fetch_redirect_response=False)
        self.assertNotIn(CLAVE, self.client.session)
        self.assertEqual(self.client.get(reverse("turnosapp:comprobante_pdf"), {"operacion": op}).status_code, 404)
        repetida = self.client.post(reverse("turnosapp:totem"), {"rut": self.paciente.rut, "operacion_id": op})
        self.assertEqual(repetida.status_code, 400)  # La operación anterior ya no sirve.

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

    def test_resultado_repetido_conserva_numero_e_incrusta_pdf_sin_imprimir(self):
        op = self.abrir()
        primera = self.enviar()
        segunda = self.enviar()
        codigo = primera.context["resultado"].codigo
        self.assertRegex(codigo, r"^[PGC]-001$")
        self.assertEqual(codigo, segunda.context["resultado"].codigo)
        html = primera.content.decode()
        self.assertIn('type="application/pdf"', html)
        self.assertIn(f'{reverse("turnosapp:comprobante_pdf")}?operacion={op}#toolbar=0&amp;navpanes=0&amp;view=Fit&amp;zoom=page-fit', html)
        self.assertIn(primera.context["resultado"].espera, html)
        self.assertInHTML(f'<div class="sr-only" role="status"><p>Tu número de atención es {codigo}. Tu llegada quedó registrada. {primera.context["resultado"].espera}</p></div>', html)
        self.assertContains(primera, "Necesito más tiempo")
        for ausente in ("data-imprimir", "Imprimir", "Nueva atención", 'class="comprobante"', self.paciente.rut, self.paciente.nombres, self.receta.codigo):
            self.assertNotContains(primera, ausente)
        self.assertEqual(Turno.objects.count(), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="turno.emitido").count(), 1)
        self.assertFalse(EntregaReceta.objects.exists())

    def test_entrada_y_error_sin_boton_nueva_atencion_ni_comprobante(self):
        respuesta = self.client.get(reverse("turnosapp:totem"))
        self.assertNotContains(respuesta, "Nueva atención")
        self.assertNotContains(respuesta, "application/pdf")
        self.assertContains(respuesta, "data-finalizar hidden")
        respuesta = self.enviar(rut="incorrecto")
        self.assertNotContains(respuesta, "application/pdf", status_code=400)
        self.assertNotContains(respuesta, "Nueva atención", status_code=400)

    def test_rechazo_y_error_rotan_la_operacion_para_la_siguiente_persona(self):
        op = self.abrir()
        respuesta = self.enviar(rut="incorrecto")
        nueva = self.client.session[CLAVE]["operacion"]
        self.assertNotEqual(op, nueva)
        self.assertContains(respuesta, f'value="{nueva}"', status_code=400)
        self.assertEqual(self.enviar().status_code, 200)  # Sin tocar nada más, con la operación nueva.
        self.enviar(rut=self.pacientes(1).rut)  # RUT distinto en la misma operación: rechazo y rotación.
        tercera = self.client.session[CLAVE]["operacion"]
        self.assertNotEqual(nueva, tercera)
        self.assertNotIn("huella", self.client.session[CLAVE])
        self.assertEqual(self.enviar(rut=self.pacientes(2).rut).status_code, 200)
        self.assertEqual(Turno.objects.count(), 2)


class TotemEnmiendaVistasTests(TestCase):
    """Enmienda 04 del 2026-11-15: no registrado con número y mismo mensaje neutro en cada rechazo."""

    setUp = preparacion.EmisionTests.setUp
    pacientes = preparacion.EmisionTests.pacientes
    recetas = preparacion.EmisionTests.recetas
    abrir = TotemVistasTests.abrir
    enviar = TotemVistasTests.enviar

    def test_rut_fuera_del_padron_recibe_numero_sin_datos_personales(self):
        rut = self.ruts[7]
        self.abrir()
        respuesta = self.enviar(rut=rut)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["resultado"].codigo, "G-001")
        self.assertNotContains(respuesta, rut)
        self.assertIsNone(Turno.objects.get().paciente)

    def test_rechazos_comparten_texto_codigo_y_estructura(self):
        from turnosapp.services import MENSAJE_NEUTRO
        respuestas = []
        op = self.abrir()
        otro = Client()
        self.abrir(otro)
        respuestas.append(self.enviar(otro, operacion_id=op))  # operación de otra sesión
        self.enviar()
        respuestas.append(self.enviar(rut=self.pacientes(1).rut))  # RUT distinto en la misma sesión
        respuestas.append(self.client.post(reverse("turnosapp:totem"), {"rut": self.paciente.rut, "operacion_id": uuid.uuid4()}))
        Turno.objects.update(estado="atendido", cerrado_en=timezone.now())
        self.abrir()
        sesion = self.client.session
        sesion[CLAVE] = {**sesion[CLAVE], "operacion": str(Turno.objects.get().operacion_id)}
        sesion.save()
        respuestas.append(self.enviar())  # operación cerrada
        for respuesta in respuestas:
            self.assertEqual(respuesta.status_code, 400)
            self.assertEqual(respuesta.templates[0].name, "turnos/totem.html")
            self.assertEqual(respuesta.context["mensaje"], MENSAJE_NEUTRO)
            self.assertNotContains(respuesta, "nueva atención", status_code=400)
            self.assertNotContains(respuesta, self.paciente.rut, status_code=400)
