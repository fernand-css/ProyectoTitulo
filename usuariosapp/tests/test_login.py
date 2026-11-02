"""Login, redirecciones seguras, cierre de sesión por POST y CSRF."""

from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from coreapp.models import RegistroAuditoria
from coreapp.roles import JEFA, ROLES_INTERNOS, TECNICO
from usuariosapp.models import Perfil
from usuariosapp.services import crear_roles


class LoginTests(TestCase):
    clave = "Clave-sintetica-solo-pruebas-2026!"

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(username="admin_prueba", password=cls.clave)
        cls.inactivo = get_user_model().objects.create_user(username="inactivo_prueba", password=cls.clave, is_active=False)

    def entrar(self, **extra):
        return self.client.post(reverse("usuariosapp:login"), {"username": self.usuario.username, "password": self.clave, **extra})

    def test_formulario_con_etiquetas_visibles_y_csrf(self):
        respuesta = self.client.get(reverse("usuariosapp:login"))
        self.assertContains(respuesta, '<label for="id_username">Nombre de usuario</label>', html=True)
        self.assertContains(respuesta, '<label for="id_password">Contraseña</label>', html=True)
        self.assertContains(respuesta, 'name="csrfmiddlewaretoken"')
        self.assertContains(respuesta, 'autocomplete="current-password"')

    def test_login_lleva_al_inicio_y_muestra_rol(self):
        self.assertRedirects(self.entrar(), "/")
        self.assertIn(SESSION_KEY, self.client.session)
        self.assertContains(self.client.get("/"), "Administración")

    def test_error_de_credenciales_es_visible(self):
        respuesta = self.client.post(reverse("usuariosapp:login"), {"username": "cuenta-inexistente-sintetica", "password": "incorrecta"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'role="alert"')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_campos_vacios_tienen_errores_asociados(self):
        respuesta = self.client.post(reverse("usuariosapp:login"), {})
        self.assertContains(respuesta, 'id="id_username_error"')
        self.assertContains(respuesta, 'aria-describedby="id_username_error"')
        self.assertContains(respuesta, 'aria-invalid="true"')

    def test_cuenta_inactiva_no_inicia_sesion(self):
        respuesta = self.client.post(reverse("usuariosapp:login"), {"username": self.inactivo.username, "password": self.clave})
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_logout_get_es_rechazado_y_conserva_sesion(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("usuariosapp:logout")).status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)

    def test_logout_post_borra_sesion_y_vuelve_al_login(self):
        self.client.force_login(self.usuario)
        self.assertRedirects(self.client.post(reverse("usuariosapp:logout")), reverse("usuariosapp:login"))
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_ya_autenticado_vuelve_al_inicio(self):
        self.client.force_login(self.usuario)
        self.assertRedirects(self.client.get(reverse("usuariosapp:login")), "/")

    def test_next_interno_se_conserva(self):
        self.assertRedirects(self.entrar(next="/admin/"), "/admin/")

    def test_next_externo_se_descarta(self):
        self.assertRedirects(self.entrar(next="https://externo.example.invalid/"), "/")

    def test_inicio_preserva_destino_en_login(self):
        respuesta = self.client.get("/?origen=prueba")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(parse_qs(urlsplit(respuesta.url).query)["next"], ["/?origen=prueba"])

    def test_login_y_logout_exigen_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        credenciales = {"username": self.usuario.username, "password": self.clave}
        self.assertEqual(cliente.post(reverse("usuariosapp:login"), credenciales).status_code, 403)
        cliente.get(reverse("usuariosapp:login"))
        token = cliente.cookies["csrftoken"].value
        self.assertEqual(cliente.post(reverse("usuariosapp:login"), {**credenciales, "csrfmiddlewaretoken": token}).status_code, 302)
        self.assertEqual(cliente.post(reverse("usuariosapp:logout")).status_code, 403)
        cliente.get("/")
        token = cliente.cookies["csrftoken"].value
        self.assertEqual(cliente.post(reverse("usuariosapp:logout"), {"csrfmiddlewaretoken": token}).status_code, 302)


class LoginPersonalTests(TestCase):
    clave = "Solo-pruebas-Ingreso-2026!"

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="ingreso_sintetico", password=cls.clave)
        cls.roles = crear_roles()
        cls.usuario.groups.add(cls.roles[TECNICO])
        Perfil.objects.create(usuario=cls.usuario)

    def entrar(self, **datos):
        return self.client.post(reverse("usuariosapp:login"), {"username": self.usuario.username, "password": self.clave, **datos})

    def test_cada_rol_inicia_sesion_sin_exigir_correo_verificado(self):
        for rol in ROLES_INTERNOS:
            self.usuario.groups.set([self.roles[rol]])
            self.client.logout()
            self.assertRedirects(self.entrar(), "/")
            self.assertEqual(RegistroAuditoria.objects.filter(accion="auth.login", usuario=self.usuario).count(), ROLES_INTERNOS.index(rol) + 1)

    def test_cuentas_sin_perfil_sin_rol_multirrol_e_inactivas_no_inician_sesion(self):
        for caso in ("perfil", "sin_rol", "multirrol", "inactiva"):
            with self.subTest(caso=caso):
                Perfil.objects.get_or_create(usuario=self.usuario)
                self.usuario.groups.set([self.roles[TECNICO]])
                get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=True)
                if caso == "perfil":
                    Perfil.objects.filter(usuario=self.usuario).delete()
                elif caso == "sin_rol":
                    self.usuario.groups.clear()
                elif caso == "multirrol":
                    self.usuario.groups.add(self.roles[JEFA])
                else:
                    get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
                respuesta = self.entrar()
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(respuesta.context["form"].non_field_errors())
                self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="auth.login_fallido").count(), 4)
        self.assertFalse(RegistroAuditoria.objects.filter(accion="auth.login").exists())

    def test_fallo_al_auditar_login_http_no_persiste_sesion_ni_fecha_de_acceso(self):
        from unittest.mock import patch
        from django.db import DatabaseError

        with patch("usuariosapp.signals.registrar_evento", side_effect=DatabaseError("Fallo sintético")):
            with self.assertRaises(DatabaseError):
                self.entrar()
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.usuario.refresh_from_db()
        self.assertIsNone(self.usuario.last_login)

    def test_login_incluye_recuperacion(self):
        self.assertContains(self.client.get(reverse("usuariosapp:login")), reverse("usuariosapp:recuperar_clave"))

    def test_revocacion_entre_validacion_y_apertura_rechaza_y_audita(self):
        from unittest.mock import patch
        from django.core.exceptions import PermissionDenied

        with patch("usuariosapp.views.iniciar_sesion", side_effect=PermissionDenied):
            respuesta = self.entrar()
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="auth.login_fallido").count(), 1)
        self.assertFalse(RegistroAuditoria.objects.filter(accion="auth.login").exists())
