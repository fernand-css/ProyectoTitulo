"""Verificación firmada, consumo único, atomicidad y concurrencia en SQLite."""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.core import mail, signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from coreapp.roles import TECNICO
from usuariosapp.models import Perfil
from usuariosapp.services import (
    SALT_CORREO, actualizar_perfil, confirmar_correo, consultar_verificacion_correo,
    crear_roles, solicitar_verificacion_correo,
)


def token_enviado():
    enlace = re.search(r"https?://\S+", mail.outbox[-1].body).group()
    return urlsplit(enlace).path.rstrip("/").rsplit("/", 1)[-1]


def preparar_cuenta():
    cuenta = get_user_model().objects.create_user(
        username="correo_sintetico", first_name="Persona", last_name="Sintética",
        email="vigente@example.invalid",
    )
    cuenta.groups.add(crear_roles()[TECNICO])
    Perfil.objects.create(usuario=cuenta, correo_verificado_en=timezone.now())
    return cuenta


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CorreoTests(TestCase):
    def setUp(self):
        self.usuario = preparar_cuenta()

    def solicitar(self, correo="nuevo@example.invalid"):
        actualizar_perfil(
            self.usuario, first_name="Persona", last_name="Sintética",
            email=correo, origen="http://testserver/",
        )
        return token_enviado()

    def test_correo_nuevo_solo_se_sustituye_tras_confirmar_y_audita_sin_valores(self):
        token = self.solicitar(" Nuevo@Example.Invalid ")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "vigente@example.invalid")
        self.assertEqual(mail.outbox[-1].to, ["nuevo@example.invalid"])
        confirmar_correo(token)
        self.usuario.refresh_from_db()
        perfil = self.usuario.perfil
        self.assertEqual(self.usuario.email, "nuevo@example.invalid")
        self.assertIsNotNone(perfil.correo_verificado_en)
        self.assertEqual(perfil.correo_pendiente, "")
        self.assertIsNone(perfil.solicitud_correo)
        self.assertCountEqual(RegistroAuditoria.objects.values_list("accion", flat=True), ["perfil.editado", "correo.confirmado"])
        registros = str(list(RegistroAuditoria.objects.values()))
        for dato in (token, "nuevo@example.invalid", self.usuario.username, "Sintética"):
            self.assertNotIn(dato, registros)

    def test_verificacion_inicial_del_mismo_correo(self):
        Perfil.objects.filter(usuario=self.usuario).update(correo_verificado_en=None)
        solicitar_verificacion_correo(self.usuario, origen="http://testserver/")
        token = token_enviado()
        self.assertIsNone(Perfil.objects.get(usuario=self.usuario).correo_verificado_en)
        confirmar_correo(token)
        self.assertIsNotNone(Perfil.objects.get(usuario=self.usuario).correo_verificado_en)

    def test_get_no_consume_y_post_exige_csrf_sin_iniciar_sesion(self):
        token = self.solicitar()
        url = reverse("usuariosapp:verificar_correo", kwargs={"token": token})
        cliente = Client(enforce_csrf_checks=True)
        respuesta = cliente.get(url)
        self.assertContains(respuesta, "Confirmar correo")
        self.assertEqual(respuesta["Referrer-Policy"], "no-referrer")
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertIsNotNone(Perfil.objects.get(usuario=self.usuario).solicitud_correo)
        self.assertEqual(cliente.post(url).status_code, 403)
        respuesta = cliente.post(url, {"csrfmiddlewaretoken": cliente.cookies["csrftoken"].value})
        self.assertContains(respuesta, "Tu correo quedó verificado")
        self.assertNotIn(SESSION_KEY, cliente.session)

    def test_enlace_usado_no_repite_cambio_ni_evento(self):
        token = self.solicitar()
        confirmar_correo(token)
        with self.assertRaises(ValidationError):
            confirmar_correo(token)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="correo.confirmado").count(), 1)

    def test_nueva_solicitud_invalida_enlace_anterior(self):
        anterior = self.solicitar()
        nuevo = self.solicitar("otro@example.invalid")
        with self.assertRaises(ValidationError):
            confirmar_correo(anterior)
        confirmar_correo(nuevo)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "otro@example.invalid")

    def test_reenvio_sustituye_nonce_y_mantiene_destinatario_pendiente(self):
        anterior = self.solicitar()
        self.assertTrue(solicitar_verificacion_correo(self.usuario, origen="http://testserver/"))
        nuevo = token_enviado()
        self.assertNotEqual(anterior, nuevo)
        with self.assertRaises(ValidationError):
            consultar_verificacion_correo(anterior)
        confirmar_correo(nuevo)

    def test_reenvio_verificado_sin_pendiente_no_envia_ni_audita(self):
        self.assertFalse(solicitar_verificacion_correo(self.usuario, origen="http://testserver/"))
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(RegistroAuditoria.objects.exists())

    def test_token_alterado_otro_proposito_y_estructura_incorrecta_no_cambian_datos(self):
        token = self.solicitar()
        invalidos = (
            token + "alterado", signing.dumps({"dato": "no-valido"}, salt=SALT_CORREO),
            signing.dumps({"dato": "no-valido"}, salt="otro-proposito"),
        )
        for invalido in invalidos:
            with self.subTest(token=invalido):
                with self.assertRaises(ValidationError):
                    confirmar_correo(invalido)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "vigente@example.invalid")

    def test_token_caducado_no_cambia_correo(self):
        token = self.solicitar()
        futuro = time.time() + settings.PASSWORD_RESET_TIMEOUT + 2
        with patch("django.core.signing.time.time", return_value=futuro):
            with self.assertRaises(ValidationError):
                confirmar_correo(token)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "vigente@example.invalid")

    def test_cuenta_desactivada_o_sin_rol_no_puede_confirmar(self):
        token = self.solicitar()
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            confirmar_correo(token)
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=True)
        self.usuario.groups.clear()
        with self.assertRaises(ValidationError):
            confirmar_correo(token)
        self.assertIsNotNone(Perfil.objects.get(usuario=self.usuario).solicitud_correo)

    def test_servicio_rechaza_cuenta_sin_habilitacion_y_no_modifica_nombres(self):
        self.usuario.groups.clear()
        with self.assertRaises(PermissionDenied):
            actualizar_perfil(self.usuario, first_name="Cambio", last_name="Rechazado", email=self.usuario.email, origen="http://testserver/")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Persona")

    def test_fallo_de_auditoria_revierte_confirmacion_y_permite_reintentar(self):
        token = self.solicitar()
        with patch("usuariosapp.services.registrar_evento", side_effect=DatabaseError("Fallo sintético")):
            with self.assertRaises(DatabaseError):
                confirmar_correo(token)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "vigente@example.invalid")
        consultar_verificacion_correo(token)
        confirmar_correo(token)

    def test_fallo_de_envio_revierte_nombres_solicitud_y_auditoria(self):
        token = self.solicitar()
        antes = RegistroAuditoria.objects.count()
        with patch("usuariosapp.services._enviar_correo", side_effect=OSError("Fallo sintético")):
            with self.assertRaises(OSError):
                actualizar_perfil(self.usuario, first_name="NoGuardar", last_name="Sintético", email="fallido@example.invalid", origen="http://testserver/")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Persona")
        self.assertEqual(RegistroAuditoria.objects.count(), antes)
        consultar_verificacion_correo(token)

    def test_reenvio_por_url_solo_post_y_cuenta_habilitada(self):
        url = reverse("usuariosapp:solicitar_verificacion")
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.solicitar()
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(len(mail.outbox), 2)

    def test_enlace_invalido_muestra_error_general_sin_reflejar_token(self):
        token = "valor-invalido-sintetico"
        url = reverse("usuariosapp:verificar_correo", kwargs={"token": token})
        for respuesta in (self.client.get(url), self.client.post(url)):
            self.assertContains(respuesta, "El enlace de verificación no es válido", status_code=400)
            self.assertNotContains(respuesta, token, status_code=400)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ConcurrenciaCorreoTests(TransactionTestCase):
    def test_dos_confirmaciones_simultaneas_consumen_una_vez(self):
        usuario = preparar_cuenta()
        actualizar_perfil(usuario, first_name="Persona", last_name="Sintética", email="concurrente@example.invalid", origen="http://testserver/")
        token = token_enviado()
        barrera = Barrier(2)

        def confirmar():
            close_old_connections()
            try:
                barrera.wait(timeout=5)
                try:
                    confirmar_correo(token)
                    return "confirmado"
                except ValidationError:
                    return "rechazado"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(confirmar) for _ in range(2)]
            resultados = [futuro.result(timeout=10) for futuro in futuros]
        self.assertCountEqual(resultados, ["confirmado", "rechazado"])
        self.assertEqual(RegistroAuditoria.objects.filter(accion="correo.confirmado").count(), 1)
        usuario.refresh_from_db()
        self.assertEqual(usuario.email, "concurrente@example.invalid")
