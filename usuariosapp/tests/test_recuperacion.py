"""Cambio y recuperación de claves con sesiones, auditoría y consumo único."""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from coreapp.roles import TECNICO
from usuariosapp.models import Perfil
from usuariosapp.services import cambiar_clave, crear_roles, restablecer_clave


CLAVE_ANTERIOR = "Solo-pruebas-Anterior-2026!"
CLAVE_NUEVA = "Distinta-Segura-Nueva-2026!"


def preparar_cuenta():
    usuario = get_user_model().objects.create_user(
        username="clave_sintetica", password=CLAVE_ANTERIOR,
        first_name="Persona", last_name="Sintética", email="vigente@example.invalid",
    )
    usuario.groups.add(crear_roles()[TECNICO])
    Perfil.objects.create(usuario=usuario, correo_verificado_en=timezone.now())
    return usuario


class CambioClaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = preparar_cuenta()

    def setUp(self):
        self.client.force_login(self.usuario)
        self.url = reverse("usuariosapp:cambiar_clave")
        self.datos = {"old_password": CLAVE_ANTERIOR, "new_password1": CLAVE_NUEVA, "new_password2": CLAVE_NUEVA}

    def test_cambio_conserva_sesion_actual_revoca_otra_y_audita_una_vez(self):
        otro = Client()
        otro.force_login(self.usuario)
        self.assertRedirects(self.client.post(self.url, self.datos), reverse("usuariosapp:perfil"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_NUEVA))
        self.assertFalse(self.usuario.check_password(CLAVE_ANTERIOR))
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(otro.get("/").status_code, 302)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="clave.cambiada").count(), 1)
        eventos = str(list(RegistroAuditoria.objects.filter(accion="clave.cambiada").values()))
        self.assertNotIn(CLAVE_NUEVA, eventos)
        self.assertNotIn(CLAVE_ANTERIOR, eventos)

    def test_actual_incorrecta_confirmacion_distinta_y_clave_debil_no_cambian_cuenta(self):
        casos = (
            {"old_password": "invalida"}, {"new_password2": "distinta"},
            {"new_password1": "123", "new_password2": "123"},
            {"new_password1": CLAVE_ANTERIOR, "new_password2": CLAVE_ANTERIOR},
        )
        for cambios in casos:
            with self.subTest(cambios=cambios):
                respuesta = self.client.post(self.url, {**self.datos, **cambios})
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, 'role="alert"')
                self.assertNotContains(respuesta, f'value="{CLAVE_NUEVA}"')
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_ANTERIOR))
        self.assertFalse(RegistroAuditoria.objects.filter(accion="clave.cambiada").exists())

    def test_fallo_de_auditoria_revierte_hash(self):
        anterior = self.usuario.password
        with patch("usuariosapp.services.registrar_evento", side_effect=DatabaseError("Fallo sintético")):
            with self.assertRaises(DatabaseError):
                cambiar_clave(self.usuario, actual=CLAVE_ANTERIOR, nueva=CLAVE_NUEVA)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.password, anterior)

    def test_exige_sesion_habilitacion_y_csrf(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        self.assertEqual(cliente.post(self.url, self.datos).status_code, 403)
        self.usuario.groups.clear()
        self.assertEqual(self.client.get(self.url).status_code, 403)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecuperacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = preparar_cuenta()

    def solicitar(self, **datos):
        return self.client.post(reverse("usuariosapp:recuperar_clave"), {
            "username": self.usuario.username, "email": self.usuario.email, **datos,
        })

    def enlace(self):
        self.solicitar()
        return urlsplit(re.search(r"https?://\S+", mail.outbox[-1].body).group()).path

    def formulario(self, url=None, cliente=None):
        cliente = cliente or self.client
        respuesta = cliente.get(url or self.enlace(), follow=True)
        self.assertTrue(respuesta.context["validlink"])
        return respuesta.redirect_chain[-1][0]

    def guardar(self, url):
        return self.client.post(url, {"new_password1": CLAVE_NUEVA, "new_password2": CLAVE_NUEVA})

    def test_recorrido_completo_invalida_clave_y_enlace_sin_login_automatico(self):
        url_original = self.enlace()
        url_formulario = self.formulario(url_original)
        self.assertIn("set-password", url_formulario)
        self.assertRedirects(self.guardar(url_formulario), reverse("usuariosapp:clave_lista"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_NUEVA))
        self.assertFalse(self.usuario.check_password(CLAVE_ANTERIOR))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertFalse(self.client.get(url_original, follow=True).context["validlink"])
        self.assertEqual(RegistroAuditoria.objects.filter(accion="clave.restablecida").count(), 1)
        self.assertTrue(self.client.login(username=self.usuario.username, password=CLAVE_NUEVA))

    def test_misma_respuesta_publica_para_cuenta_valida_inexistente_y_correo_incorrecto(self):
        cuerpos = []
        for datos, enviados in (({}, 1), ({"username": "no_existe_sintetico"}, 0), ({"email": "otra@example.invalid"}, 0)):
            mail.outbox.clear()
            respuesta = self.solicitar(**datos)
            self.assertEqual(respuesta.status_code, 302)
            self.assertEqual(respuesta.url, reverse("usuariosapp:recuperacion_enviada"))
            cuerpos.append(self.client.get(respuesta.url).content)
            self.assertEqual(len(mail.outbox), enviados)
        self.assertEqual(cuerpos[0], cuerpos[1])
        self.assertEqual(cuerpos[0], cuerpos[2])
        self.assertFalse(RegistroAuditoria.objects.filter(accion="clave.restablecida").exists())

    def test_inactiva_sin_verificar_sin_perfil_sin_rol_o_clave_inutilizable_no_recupera(self):
        for caso in ("inactiva", "sin_verificar", "sin_perfil", "sin_rol", "inutilizable"):
            with self.subTest(caso=caso):
                self.usuario.is_active = True
                self.usuario.set_password(CLAVE_ANTERIOR)
                self.usuario.save(update_fields=["is_active", "password"])
                self.usuario.groups.set([crear_roles()[TECNICO]])
                Perfil.objects.update_or_create(usuario=self.usuario, defaults={"correo_verificado_en": timezone.now()})
                if caso == "inactiva":
                    get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
                elif caso == "sin_verificar":
                    Perfil.objects.filter(usuario=self.usuario).update(correo_verificado_en=None)
                elif caso == "sin_perfil":
                    Perfil.objects.filter(usuario=self.usuario).delete()
                elif caso == "sin_rol":
                    self.usuario.groups.clear()
                else:
                    self.usuario.set_unusable_password()
                    self.usuario.save(update_fields=["password"])
                mail.outbox.clear()
                self.assertEqual(self.solicitar().status_code, 302)
                self.assertEqual(len(mail.outbox), 0)

    def test_correo_pendiente_no_recupera_y_vigente_verificado_si(self):
        Perfil.objects.filter(usuario=self.usuario).update(correo_pendiente="pendiente@example.invalid")
        self.solicitar(email="pendiente@example.invalid")
        self.assertEqual(len(mail.outbox), 0)
        self.solicitar(email=" VIGENTE@EXAMPLE.INVALID ")
        self.assertEqual(mail.outbox[-1].to, ["vigente@example.invalid"])

    def test_correo_compartido_no_recupera_otra_cuenta(self):
        otra = get_user_model().objects.create_user(username="otra_clave_sintetica", email=self.usuario.email, password=CLAVE_ANTERIOR)
        otra.groups.add(crear_roles()[TECNICO])
        Perfil.objects.create(usuario=otra, correo_verificado_en=timezone.now())
        url = self.formulario()
        self.assertEqual(len(mail.outbox), 1)
        self.guardar(url)
        otra.refresh_from_db()
        self.assertTrue(otra.check_password(CLAVE_ANTERIOR))

    def test_token_alterado_caducado_uid_invalido_no_permiten_restablecer(self):
        original = self.enlace()
        alterado = original.rstrip("/") + "alterado/"
        self.assertFalse(self.client.get(alterado, follow=True).context["validlink"])
        futuro = datetime.now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 2)
        with patch("django.contrib.auth.tokens.PasswordResetTokenGenerator._now", return_value=futuro):
            self.assertFalse(self.client.get(original, follow=True).context["validlink"])
        invalido = reverse("usuariosapp:restablecer_clave", kwargs={"uidb64": "invalido", "token": "invalido"})
        self.assertFalse(self.client.get(invalido).context["validlink"])
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_ANTERIOR))

    def test_revocar_habilitacion_despues_de_solicitar_invalida_el_flujo(self):
        url = self.enlace()
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
        self.assertFalse(self.client.get(url, follow=True).context["validlink"])

    def test_clave_debil_o_confirmacion_incorrecta_no_cambia_cuenta(self):
        url = self.formulario()
        for primera, segunda in (("123", "123"), (CLAVE_NUEVA, "no-coincide"), (CLAVE_ANTERIOR, CLAVE_ANTERIOR)):
            respuesta = self.client.post(url, {"new_password1": primera, "new_password2": segunda})
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, 'role="alert"')
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_ANTERIOR))

    def test_confirmacion_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        url = self.formulario(self.enlace(), cliente)
        datos = {"new_password1": CLAVE_NUEVA, "new_password2": CLAVE_NUEVA}
        self.assertEqual(cliente.post(url, datos).status_code, 403)
        datos["csrfmiddlewaretoken"] = cliente.cookies["csrftoken"].value
        self.assertEqual(cliente.post(url, datos).status_code, 302)

    def test_solicitud_exige_campos_y_csrf(self):
        url = reverse("usuariosapp:recuperar_clave")
        self.assertEqual(self.client.post(url, {}).status_code, 200)
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, {"username": self.usuario.username, "email": self.usuario.email}).status_code, 403)

    def test_fallo_de_envio_no_revela_contacto_y_conserva_respuesta(self):
        with patch("usuariosapp.forms.EmailMultiAlternatives.send", side_effect=OSError("detalle-correo-privado")):
            with self.assertLogs("usuariosapp.forms", level="ERROR") as logs:
                respuesta = self.solicitar()
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn("detalle-correo-privado", " ".join(logs.output))

    def test_fallo_de_auditoria_revierte_clave_y_no_consume_token(self):
        token = default_token_generator.make_token(self.usuario)
        anterior = self.usuario.password
        with patch("usuariosapp.services.registrar_evento", side_effect=DatabaseError("Fallo sintético")):
            with self.assertRaises(DatabaseError):
                restablecer_clave(self.usuario, nueva=CLAVE_NUEVA, token=token)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.password, anterior)
        self.assertTrue(default_token_generator.check_token(self.usuario, token))
        self.assertFalse(RegistroAuditoria.objects.filter(accion="clave.restablecida").exists())

    def test_restablecimiento_revoca_sesiones_previas(self):
        anterior = Client()
        anterior.force_login(self.usuario)
        url = self.formulario()
        self.guardar(url)
        self.assertEqual(anterior.get("/").status_code, 302)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConcurrenciaClaveTests(TransactionTestCase):
    def test_token_se_consume_una_vez_entre_dos_conexiones(self):
        usuario = preparar_cuenta()
        token = default_token_generator.make_token(usuario)
        barrera = Barrier(2)

        def restablecer():
            close_old_connections()
            try:
                cuenta = get_user_model().objects.get(pk=usuario.pk)
                barrera.wait(timeout=5)
                try:
                    restablecer_clave(cuenta, nueva=CLAVE_NUEVA, token=token)
                    return "cambiada"
                except ValidationError:
                    return "rechazada"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(restablecer) for _ in range(2)]
            resultados = [futuro.result(timeout=10) for futuro in futuros]
        self.assertCountEqual(resultados, ["cambiada", "rechazada"])
        self.assertEqual(RegistroAuditoria.objects.filter(accion="clave.restablecida").count(), 1)
