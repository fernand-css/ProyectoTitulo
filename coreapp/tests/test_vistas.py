"""HTTP público, sesión obligatoria y páginas de error sin detalles internos."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import OperationalError
from django.test import Client, TestCase, override_settings
from django.urls import path, reverse

from cesfam.urls import urlpatterns as rutas_proyecto


def sin_permiso(request):
    raise PermissionDenied("Detalle interno sintético")


def fallo_interno(request):
    raise RuntimeError("Detalle interno sintético")


urlpatterns = [
    *rutas_proyecto,
    path("prueba-403/", sin_permiso),
    path("prueba-500/", fallo_interno),
]
handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"


class VistasTests(TestCase):
    def test_salud_publica_comprueba_la_conexion(self):
        with patch("coreapp.views.connection.ensure_connection") as comprobar:
            respuesta = self.client.get(reverse("coreapp:salud"))
        comprobar.assert_called_once_with()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "ok"})

    def test_salud_fallida_no_expone_el_error(self):
        with patch("coreapp.views.connection.ensure_connection", side_effect=OperationalError("Detalle privado")):
            respuesta = self.client.get(reverse("coreapp:salud"))
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json(), {"estado": "error"})
        self.assertNotIn(b"Detalle privado", respuesta.content)

    def test_salud_no_admite_post(self):
        self.assertEqual(self.client.post(reverse("coreapp:salud")).status_code, 405)

    def test_worker_publico_con_mime_y_alcance_correctos(self):
        respuesta = self.client.get(reverse("coreapp:sw_js"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/javascript")
        self.assertEqual(respuesta["Service-Worker-Allowed"], "/")
        self.assertEqual(respuesta["Cache-Control"], "no-cache")

    def test_inicio_anonimo_redirige_al_login(self):
        self.assertRedirects(self.client.get("/"), reverse("usuariosapp:login") + "?next=/")

    def test_inicio_con_superusuario_muestra_rol(self):
        usuario = get_user_model().objects.create_superuser(username="admin_sintetico", password="Clave-sintetica-2026!")
        self.client.force_login(usuario)
        respuesta = self.client.get("/")
        self.assertTemplateUsed(respuesta, "index.html")
        self.assertContains(respuesta, "Administración")
        self.assertContains(respuesta, "admin_sintetico")

    def test_recursos_publicos_no_muestran_identidad(self):
        usuario = get_user_model().objects.create_user(username="identidad_sintetica_privada", first_name="NombreSinteticoPrivado")
        self.client.force_login(usuario)
        for url in ("/salud/", "/sw.js", "/usuarios/entrar/"):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertNotIn(b"identidad_sintetica_privada", respuesta.content)
                self.assertNotIn(b"NombreSinteticoPrivado", respuesta.content)
                self.assertNotIn(b"12345678-5", respuesta.content)


@override_settings(DEBUG=False, ROOT_URLCONF=__name__)
class ErroresTests(TestCase):
    def test_404_con_plantilla_propia(self):
        respuesta = self.client.get("/pagina-inexistente/")
        self.assertContains(respuesta, "No encontramos esta página", status_code=404)
        self.assertTemplateUsed(respuesta, "404.html")

    def test_403_sin_detalles_de_excepcion(self):
        respuesta = self.client.get("/prueba-403/")
        self.assertContains(respuesta, "No tienes permiso para acceder", status_code=403)
        self.assertNotContains(respuesta, "Detalle interno", status_code=403)
        self.assertTemplateUsed(respuesta, "403.html")

    def test_500_con_plantilla_independiente(self):
        respuesta = Client(raise_request_exception=False).get("/prueba-500/")
        self.assertContains(respuesta, "Ocurrió un problema temporal", status_code=500)
        self.assertNotContains(respuesta, "Detalle interno", status_code=500)
        self.assertTemplateUsed(respuesta, "500.html")
