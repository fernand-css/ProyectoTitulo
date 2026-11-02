"""Matriz de permisos para una vista protegida por rol."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.views import View

from coreapp.mixins import RolRequeridoMixin, tiene_rol
from coreapp.roles import ENCARGADO, JEFA, TECNICO, TOTEM
from usuariosapp.models import Perfil


class VistaTecnico(RolRequeridoMixin, View):
    roles_permitidos = (TECNICO,)

    def get(self, request):
        return HttpResponse("Acceso autorizado")


@override_settings(LOGIN_URL="/usuarios/entrar/")
class MixinsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.usuario = get_user_model().objects.create_user(username="tecnico_sintetico")
        Perfil.objects.create(usuario=self.usuario)

    def respuesta(self, usuario):
        request = self.factory.get("/prueba-rol/")
        request.user = usuario
        return VistaTecnico.as_view()(request)

    def test_anonimo_redirigido_con_next(self):
        self.assertFalse(tiene_rol(AnonymousUser(), TECNICO))
        respuesta = self.respuesta(AnonymousUser())
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, "/usuarios/entrar/?next=/prueba-rol/")

    def test_usuario_sin_rol_recibe_403(self):
        self.assertEqual(self.respuesta(self.usuario).status_code, 403)

    def test_otro_rol_no_autoriza(self):
        self.usuario.groups.add(Group.objects.create(name=ENCARGADO))
        with self.assertRaises(PermissionDenied):
            self.respuesta(self.usuario)

    def test_grupo_correcto_autoriza(self):
        self.usuario.groups.add(Group.objects.create(name=TECNICO))
        self.assertEqual(self.respuesta(self.usuario).status_code, 200)
        self.assertTrue(tiene_rol(self.usuario, JEFA, TECNICO))

    def test_superusuario_autorizado_sin_grupos(self):
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=["is_superuser"])
        self.assertEqual(self.respuesta(self.usuario).status_code, 200)

    def test_sin_roles_permitidos_deniega_por_defecto(self):
        self.assertFalse(tiene_rol(self.usuario))

    def test_totem_no_se_crea_como_grupo(self):
        self.assertFalse(Group.objects.filter(name=TOTEM).exists())
