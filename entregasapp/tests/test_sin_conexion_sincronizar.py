"""Spec 11, RF-11-06, RF-11-07, RF-11-09 y RF-11-11: sincronización de registros hechos sin conexión.

Datos sintéticos. Cada registro lleva la hora del celular en ISO con zona, como lo envía sincronizar.js.
"""

import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.db import OperationalError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from entregasapp import sin_conexion
from entregasapp.models import IntentoEntrega
from entregasapp.services import anular_entrega, reasignar, registrar_no_entregada
from recetasapp.models import Receta
from .ayudas import equipo, hoy, visita

URL = reverse("entregasapp:sincronizar")


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.intento = visita(self.equipo, (1, 0))
        self.client.force_login(self.encargado)

    def registro(self, intento=None, *, resultado="entregada", motivo="", nota="", hace=timedelta(minutes=10),
                 operacion=None, cuenta=None):
        return {
            "operacion_id": str(operacion or uuid.uuid4()), "intento": (intento or self.intento).pk,
            "resultado": resultado, "motivo": motivo, "nota": nota,
            "registrado_en": (timezone.now() - hace).isoformat(), "cuenta": (cuenta or self.encargado).pk,
        }

    def enviar(self, *registros, cliente=None):
        return (cliente or self.client).post(URL, json.dumps({"registros": list(registros)}),
                                             content_type="application/json")

    def resultados(self, *registros):
        respuesta = self.enviar(*registros)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertIn("no-store", respuesta["Cache-Control"])
        return respuesta.json()["resultados"]


class SincronizarTests(Base):
    def test_lote_mixto_se_aplica_y_el_reenvio_da_ya_aplicado(self):
        otra = visita(self.equipo, (2, 0))
        lote = [self.registro(), self.registro(otra, resultado="no_entregada", motivo="otro", nota="Portón cerrado")]
        primera = self.resultados(*lote)
        self.assertEqual([(r["operacion_id"], r["estado"]) for r in primera],
                         [(lote[0]["operacion_id"], "aplicado"), (lote[1]["operacion_id"], "aplicado")])
        segunda = self.resultados(*lote)
        self.assertEqual([r["estado"] for r in segunda], ["ya_aplicado", "ya_aplicado"])
        self.intento.refresh_from_db()
        otra.refresh_from_db()
        self.assertEqual((self.intento.resultado, otra.resultado, otra.nota), ("entregada", "no_entregada", "Portón cerrado"))
        self.assertIsNotNone(self.intento.sincronizado_en)
        self.assertEqual(Receta.objects.filter(entregas_completadas=1).count(), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="intento.entregado").count(), 1)

    def assertRechazo(self, registro, codigo):
        (resultado,) = self.resultados(registro)
        self.assertEqual((resultado["estado"], resultado["codigo"]), ("rechazado", codigo))
        self.assertEqual(resultado["mensaje"], sin_conexion.Rechazo.MENSAJES[codigo])
        return resultado

    def assertAuditado(self, intento, codigo):
        registro = RegistroAuditoria.objects.get(accion="intento.sincronizacion_rechazada")
        self.assertEqual((registro.objeto_tipo, registro.objeto_id, registro.usuario),
                         ("entregasapp.IntentoEntrega", f"{intento.pk}:{codigo}", self.encargado))

    def test_reasignada_gana_el_servidor(self):
        reasignar(self.equipo["qf"], self.intento.entrega_id, fecha=hoy(), encargado_id=self.equipo["encargado2"].pk,
                  intento_id=self.intento.pk, operacion_id=uuid.uuid4())
        resultado = self.assertRechazo(self.registro(), "reasignada")
        self.assertEqual(resultado["mensaje"], "La Q.F. reasignó esta visita antes de que llegara tu registro.")
        nuevo = self.intento.entrega.intentos.order_by("-numero").first()
        self.assertEqual(nuevo.resultado, "pendiente")
        self.assertAuditado(self.intento, "reasignada")

    def test_anulada(self):
        anular_entrega(self.equipo["qf"], self.intento.entrega_id, "otro", "Nota sintética de anulación")
        self.assertRechazo(self.registro(), "anulada")
        self.assertAuditado(self.intento, "anulada")

    def test_ya_registrada_con_otra_operacion(self):
        registrar_no_entregada(self.encargado, self.intento.pk, "sin_receptor", "", uuid.uuid4())
        self.assertRechazo(self.registro(), "ya_registrada")

    def test_visita_de_otro_encargado(self):
        ajena = visita(self.equipo, (1, 1), encargado=self.equipo["encargado2"])
        self.assertRechazo(self.registro(ajena), "no_asignada")
        ajena.refresh_from_db()
        self.assertEqual(ajena.resultado, "pendiente")

    def test_registro_de_otra_cuenta(self):
        registro = self.registro(cuenta=self.equipo["encargado2"])
        self.assertRechazo(registro, "otro_usuario")
        self.intento.refresh_from_db()
        self.assertEqual(self.intento.resultado, "pendiente")
        self.assertFalse(RegistroAuditoria.objects.filter(accion="intento.entregado").exists())
        self.assertAuditado(self.intento, "otro_usuario")

    def test_hora_y_plazo(self):
        IntentoEntrega.objects.filter(pk=self.intento.pk).update(fecha_programada=hoy() - timedelta(days=3))
        self.assertRechazo(self.registro(hace=-timedelta(minutes=10)), "hora_invalida")
        self.assertRechazo(self.registro(hace=timedelta(days=3)), "fuera_de_plazo")
        sin_zona = self.registro()
        sin_zona["registrado_en"] = "2026-11-18T10:00:00"
        self.assertRechazo(sin_zona, "hora_invalida")
        sin_zona["registrado_en"] = "no es una hora"
        self.assertRechazo(sin_zona, "hora_invalida")

    def test_registros_no_validos(self):
        casos = [
            self.registro(resultado="no_entregada"),  # sin motivo
            self.registro(resultado="no_entregada", motivo="otro"),  # «Otro» sin nota
            self.registro(resultado="no_entregada", motivo="sin_receptor", nota="x" * 201),
            self.registro(resultado="perdida"),
            {**self.registro(), "operacion_id": "no-es-uuid"},
            {**self.registro(), "intento": "abc"},
            "no es un objeto",
        ]
        resultados = self.resultados(*casos)
        self.assertEqual([(r["estado"], r["codigo"]) for r in resultados], [("rechazado", "invalido")] * len(casos))
        self.assertEqual(resultados[4]["operacion_id"], "")
        self.intento.refresh_from_db()
        self.assertEqual(self.intento.resultado, "pendiente")

    def test_la_auditoria_nunca_guarda_la_nota(self):
        anular_entrega(self.equipo["qf"], self.intento.entrega_id, "otro", "Nota sintética de anulación")
        self.resultados(self.registro(resultado="no_entregada", motivo="otro", nota="Nota secreta sintética"))
        for registro in RegistroAuditoria.objects.all():
            self.assertNotIn("secreta", f"{registro.accion} {registro.objeto_tipo} {registro.objeto_id}")

    def test_error_de_la_base_deja_el_registro_para_reintentar(self):
        with patch("entregasapp.services.registrar_entregada", side_effect=OperationalError("database is locked")):
            (resultado,) = self.resultados(self.registro())
        self.assertEqual(resultado["estado"], "reintentar")
        self.assertFalse(RegistroAuditoria.objects.filter(accion="intento.sincronizacion_rechazada").exists())


class LimitesTests(Base):
    def test_json_no_valido_y_lote_grande(self):
        self.assertEqual(self.client.post(URL, "{no", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(URL, json.dumps({"registros": "x"}), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(URL, json.dumps([]), content_type="application/json").status_code, 400)
        respuesta = self.enviar(*[self.registro() for _ in range(51)])
        self.assertEqual(respuesta.status_code, 413)
        self.intento.refresh_from_db()
        self.assertEqual(self.intento.resultado, "pendiente")
        self.assertEqual(self.enviar(*[self.registro(resultado="perdida") for _ in range(50)]).status_code, 200)

    def test_permisos(self):
        for actor in ("qf", "tecnico", "admin"):
            with self.subTest(actor=actor):
                self.client.force_login(self.equipo[actor])
                self.assertEqual(self.enviar(self.registro()).status_code, 403)
        self.client.logout()
        respuesta = self.enviar(self.registro())
        self.assertEqual(respuesta.status_code, 302)
        self.intento.refresh_from_db()
        self.assertEqual(self.intento.resultado, "pendiente")
        self.client.force_login(self.encargado)
        self.assertEqual(self.client.get(URL).status_code, 405)

    def test_limite_de_solicitudes_por_minuto(self):
        for _ in range(30):
            self.assertEqual(self.enviar().status_code, 200)
        self.assertEqual(self.enviar(self.registro()).status_code, 429)

    def test_exige_csrf_por_cabecera(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.encargado)
        self.assertEqual(self.enviar(self.registro(), cliente=cliente).status_code, 403)
        cliente.get(reverse("entregasapp:mis"))
        token = cliente.cookies["csrftoken"].value
        respuesta = cliente.post(URL, json.dumps({"registros": [self.registro()]}), content_type="application/json",
                                 headers={"X-CSRFToken": token})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["resultados"][0]["estado"], "aplicado")
