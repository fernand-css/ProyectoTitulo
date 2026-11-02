"""Navegación por permisos y formularios completos renderizados por HTTP."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from coreapp.roles import ENCARGADO, JEFA, TECNICO
from coreapp.tests.test_plantillas import DocumentoHTML
from usuariosapp.tests.test_gestion_usuarios import cuenta_personal


class IntegracionUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.qf = cuenta_personal("qf_integracion_sintetica", JEFA)
        cls.tecnico = cuenta_personal("tecnico_integracion_sintetico", TECNICO, is_staff=True)
        cls.encargado = cuenta_personal("terreno_integracion_sintetico", ENCARGADO)
        cls.admin = get_user_model().objects.create_superuser(username="root_integracion_sintetico")
        cls.operador = cuenta_personal("operador_integracion_sintetico", TECNICO)

    def test_navegacion_ofrece_solo_destinos_autorizados_y_existentes(self):
        for usuario, gestion, administracion in (
            (self.qf, True, False), (self.tecnico, False, False),
            (self.encargado, False, False), (self.admin, True, True),
        ):
            with self.subTest(usuario=usuario.username):
                cliente = Client()
                cliente.force_login(usuario)
                respuesta = cliente.get("/")
                self.assertEqual(respuesta.status_code, 200)
                enlaces = {atributos["href"] for etiqueta, atributos in DocumentoHTML(respuesta.content.decode()).elementos if etiqueta == "a" and "href" in atributos}
                self.assertIn(reverse("usuariosapp:perfil"), enlaces)
                self.assertEqual(reverse("usuariosapp:gestion_usuarios") in enlaces, gestion)
                self.assertEqual(reverse("admin:index") in enlaces, administracion)
                for enlace in enlaces:
                    if enlace.startswith("/"):
                        self.assertIn(cliente.get(enlace).status_code, (200, 302))

    def test_formularios_tienen_labels_ids_unicos_main_y_enlace_activo(self):
        casos = (
            (None, reverse("usuariosapp:login"), None),
            (None, reverse("usuariosapp:recuperar_clave"), None),
            (self.encargado, reverse("usuariosapp:perfil"), reverse("usuariosapp:perfil")),
            (self.encargado, reverse("usuariosapp:cambiar_clave"), reverse("usuariosapp:perfil")),
            (self.qf, reverse("usuariosapp:gestion_nuevo"), reverse("usuariosapp:gestion_usuarios")),
            (self.qf, reverse("usuariosapp:gestion_editar", args=[self.operador.pk]), reverse("usuariosapp:gestion_usuarios")),
        )
        for usuario, ruta, activo in casos:
            with self.subTest(ruta=ruta):
                cliente = Client()
                if usuario:
                    cliente.force_login(usuario)
                respuesta = cliente.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                elementos = DocumentoHTML(respuesta.content.decode()).elementos
                ids = [atributos["id"] for _, atributos in elementos if "id" in atributos]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(len([1 for etiqueta, _ in elementos if etiqueta == "main"]), 1)
                etiquetas = {atributos["for"] for etiqueta, atributos in elementos if etiqueta == "label" and "for" in atributos}
                for etiqueta, atributos in elementos:
                    if etiqueta in ("input", "select", "textarea") and atributos.get("type") != "hidden":
                        self.assertIn(atributos.get("id"), etiquetas)
                if activo:
                    self.assertTrue(any(etiqueta == "a" and atributos.get("href") == activo and atributos.get("aria-current") == "page" for etiqueta, atributos in elementos))
