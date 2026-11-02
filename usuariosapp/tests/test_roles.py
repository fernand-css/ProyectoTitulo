"""Habilitación real por cuenta/rol y revocación tras iniciar sesión."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.test import TestCase

from coreapp.mixins import tiene_rol
from coreapp.roles import ENCARGADO, ETIQUETAS_ROLES, JEFA, TECNICO, estado_acceso
from usuariosapp.models import Perfil
from usuariosapp.services import crear_roles


class HabilitacionTests(TestCase):
    def setUp(self):
        self.roles = crear_roles()
        self.usuario = get_user_model().objects.create_user(username="rol_sintetico")
        self.perfil = Perfil.objects.create(usuario=self.usuario)
        self.usuario.groups.add(self.roles[TECNICO])

    def test_inicio_permitido_por_cada_rol_y_etiqueta_acordada(self):
        for rol in (JEFA, TECNICO, ENCARGADO):
            with self.subTest(rol=rol):
                self.usuario.groups.set([self.roles[rol]])
                self.client.force_login(self.usuario)
                respuesta = self.client.get("/")
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.context["nombre_rol"], ETIQUETAS_ROLES[rol])
                self.assertTrue(tiene_rol(self.usuario, rol))

    def test_anonimo_y_usuario_no_guardado_no_estan_habilitados(self):
        self.assertEqual(estado_acceso(AnonymousUser()), (False, ""))
        self.assertEqual(estado_acceso(get_user_model()(username="no_guardado")), (False, ""))

    def test_falta_de_perfil_bloquea_inicio_aunque_tenga_rol(self):
        self.perfil.delete()
        self.client.force_login(self.usuario)
        respuesta = self.client.get("/")
        self.assertContains(respuesta, "pendiente de regularización", status_code=403)
        self.assertContains(respuesta, "Cerrar sesión", status_code=403)
        self.assertFalse(tiene_rol(self.usuario, TECNICO))

    def test_retiro_de_rol_bloquea_siguiente_peticion_con_sesion(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.usuario.groups.clear()
        self.assertEqual(self.client.get("/").status_code, 403)

    def test_multirrol_no_concede_ninguno_de_los_permisos(self):
        self.usuario.groups.add(self.roles[JEFA])
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get("/").status_code, 403)
        self.assertFalse(tiene_rol(self.usuario, JEFA, TECNICO))

    def test_desactivacion_bloquea_siguiente_peticion_con_sesion(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get("/").status_code, 200)
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertFalse(tiene_rol(self.usuario, TECNICO))

    def test_superusuario_activo_sin_perfil_conserva_acceso(self):
        self.perfil.delete()
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_superuser=True)
        self.assertTrue(tiene_rol(self.usuario, JEFA))
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get("/").status_code, 200)
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
        self.assertFalse(tiene_rol(self.usuario, JEFA))

    def test_no_confia_en_grupos_prefetch_ni_flags_de_un_objeto_antiguo(self):
        almacenado = get_user_model().objects.prefetch_related("groups").get(pk=self.usuario.pk)
        self.assertEqual(estado_acceso(almacenado), (True, TECNICO))
        get_user_model().objects.get(pk=self.usuario.pk).groups.set([self.roles[ENCARGADO]])
        self.assertEqual(estado_acceso(almacenado), (True, ENCARGADO))
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
        self.assertEqual(estado_acceso(almacenado), (False, ""))

    def test_grupos_ajenos_no_otorgan_rol_operativo(self):
        self.usuario.groups.set([Group.objects.create(name="Grupo ajeno sintético")])
        self.assertEqual(estado_acceso(self.usuario), (False, ""))
