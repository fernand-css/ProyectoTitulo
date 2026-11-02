"""Eventos de autenticación y cambios transaccionales sin información sensible."""

from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model, login
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.auth.signals import user_login_failed
from django.db import DatabaseError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from coreapp.auditoria import LOGIN, LOGIN_FALLIDO, LOGOUT, registrar_evento
from coreapp.models import RegistroAuditoria
from usuariosapp.models import Perfil
from usuariosapp.services import crear_cuentas_demo


class AutenticacionAuditoriaTests(TestCase):
    clave = "Solo-pruebas-Auditoria-2026!"

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            username="admin_eventos_sintetico", password=cls.clave,
        )

    def entrar(self, **datos):
        return self.client.post(reverse("usuariosapp:login"), {
            "username": self.usuario.username, "password": self.clave, **datos,
        })

    def test_login_real_registra_una_vez_actor_y_referencia(self):
        self.assertEqual(self.entrar().status_code, 302)
        registro = RegistroAuditoria.objects.get()
        self.assertEqual(registro.accion, LOGIN)
        self.assertEqual(registro.usuario_id, self.usuario.pk)
        self.assertEqual(registro.objeto_tipo, "auth.User")
        self.assertEqual(registro.objeto_id, str(self.usuario.pk))

    def test_fallo_conocido_y_desconocido_no_identifica_actor(self):
        for nombre in (self.usuario.username, "cuenta_inexistente_sintetica"):
            self.entrar(username=nombre, password="invalida-sintetica")
        self.assertEqual(RegistroAuditoria.objects.count(), 2)
        for registro in RegistroAuditoria.objects.all():
            self.assertEqual(registro.accion, LOGIN_FALLIDO)
            self.assertIsNone(registro.usuario_id)
            self.assertEqual(registro.objeto_id, "no-identificado")

    def test_no_copia_credenciales_tokens_contacto_ni_cuerpo_de_peticion(self):
        secretos = {
            "username": "identificador-intentado-sintetico",
            "password": "clave-no-registrable-sintetica",
            "email": "correo-no-registrable@example.invalid",
            "token": "token-no-registrable-sintetico",
        }
        user_login_failed.send(sender=__name__, credentials=secretos, request=None)
        contenido = str(list(RegistroAuditoria.objects.values()))
        for valor in secretos.values():
            self.assertNotIn(valor, contenido)

    def test_logout_real_registra_una_vez_y_cierra_sesion(self):
        self.entrar()
        respuesta = self.client.post(reverse("usuariosapp:logout"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(list(RegistroAuditoria.objects.order_by("pk").values_list("accion", flat=True)), [LOGIN, LOGOUT])
        registro = RegistroAuditoria.objects.get(accion=LOGOUT)
        self.assertEqual(registro.usuario_id, self.usuario.pk)

    def test_logout_anonimo_no_inventa_actor_ni_evento(self):
        self.client.post(reverse("usuariosapp:logout"))
        self.assertFalse(RegistroAuditoria.objects.exists())

    def test_logout_get_y_csrf_invalido_no_generan_evento(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        antes = RegistroAuditoria.objects.count()
        self.assertEqual(cliente.get(reverse("usuariosapp:logout")).status_code, 405)
        self.assertEqual(cliente.post(reverse("usuariosapp:logout")).status_code, 403)
        self.assertEqual(RegistroAuditoria.objects.count(), antes)
        self.assertIn(SESSION_KEY, cliente.session)

    def test_conexion_de_senales_repetida_no_duplica_eventos(self):
        config = apps.get_app_config("usuariosapp")
        config.ready()
        config.ready()
        self.entrar()
        self.assertEqual(RegistroAuditoria.objects.filter(accion=LOGIN).count(), 1)

    def test_fallo_de_auditoria_no_deja_sesion_preparada_por_login(self):
        request = RequestFactory().post("/usuarios/entrar/")
        request.user = AnonymousUser()
        request.session = import_module(settings.SESSION_ENGINE).SessionStore()
        with patch("usuariosapp.signals.registrar_evento", side_effect=DatabaseError("Fallo sintético")):
            with self.assertRaises(DatabaseError):
                login(request, self.usuario, backend="django.contrib.auth.backends.ModelBackend")
        self.assertNotIn(SESSION_KEY, request.session)
        self.assertFalse(request.user.is_authenticated)
        self.assertFalse(RegistroAuditoria.objects.exists())

    def test_fallo_al_auditar_logout_no_impide_revocar_y_no_registra_detalles(self):
        self.entrar()
        with patch("usuariosapp.signals.registrar_evento", side_effect=DatabaseError("detalle-privado-sintetico")):
            with self.assertLogs("usuariosapp.signals", level="ERROR") as logs:
                respuesta = self.client.post(reverse("usuariosapp:logout"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotIn("detalle-privado-sintetico", " ".join(logs.output))
        self.assertFalse(RegistroAuditoria.objects.filter(accion=LOGOUT).exists())

    def test_evento_desconocido_y_sin_objeto_no_se_persisten(self):
        with self.assertRaises(ValueError):
            registrar_evento(None, "accion-arbitraria")
        with self.assertRaises(ValueError):
            registrar_evento(self.usuario, LOGIN)
        self.assertFalse(RegistroAuditoria.objects.exists())


class CambiosAuditoriaTests(TestCase):
    clave = "Solo-pruebas-Auditoria-2026!"

    def test_altas_demo_y_roles_tienen_eventos_sin_duplicar_al_repetir(self):
        crear_cuentas_demo(self.clave)
        crear_cuentas_demo()
        self.assertEqual(RegistroAuditoria.objects.count(), 6)
        for cuenta in get_user_model().objects.all():
            registros = RegistroAuditoria.objects.filter(objeto_tipo="auth.User", objeto_id=str(cuenta.pk))
            self.assertCountEqual(registros.values_list("accion", flat=True), ["usuario.creado", "usuario.rol_cambiado"])
            self.assertFalse(registros.exclude(usuario=None).exists())

    def test_fallo_de_escritura_de_evento_revierte_cuentas_perfiles_y_roles(self):
        with patch("usuariosapp.services.registrar_evento", side_effect=DatabaseError("Fallo sintético")):
            with self.assertRaises(DatabaseError):
                crear_cuentas_demo(self.clave)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Perfil.objects.exists())
        self.assertFalse(Group.objects.exists())
        self.assertFalse(RegistroAuditoria.objects.exists())

    def test_fallo_posterior_revierte_eventos_ya_escritos(self):
        with patch("usuariosapp.services.validate_password", side_effect=[None, DatabaseError("Fallo sintético")]):
            with self.assertRaises(DatabaseError):
                crear_cuentas_demo(self.clave)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Group.objects.exists())
        self.assertFalse(RegistroAuditoria.objects.exists())
