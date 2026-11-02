"""Preparación explícita, idempotencia y conservación de cuentas existentes."""

import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from coreapp.roles import ROLES_INTERNOS, TOTEM, estado_acceso
from usuariosapp.models import Perfil
from usuariosapp.services import CUENTAS_DEMO


class ComandosTests(TestCase):
    clave = "Solo-pruebas-Cuentas-2026!"

    def ejecutar_demo(self, clave=None, **options):
        salida = StringIO()
        errores = StringIO()
        with patch.dict(os.environ, {"CESFAM_DEMO_PASSWORD": clave or ""}):
            call_command("crear_usuarios_demo", noinput=True, stdout=salida, stderr=errores, **options)
        self.assertNotIn(self.clave, salida.getvalue() + errores.getvalue())
        return salida.getvalue()

    def test_roles_solo_tres_operativos_y_repeticion_conserva_permisos(self):
        grupo = Group.objects.create(name=ROLES_INTERNOS[0])
        permiso = Permission.objects.first()
        grupo.permissions.add(permiso)
        call_command("crear_roles", stdout=StringIO())
        call_command("crear_roles", stdout=StringIO())
        self.assertEqual(set(Group.objects.values_list("name", flat=True)), set(ROLES_INTERNOS))
        self.assertEqual(list(grupo.permissions.all()), [permiso])
        self.assertFalse(Group.objects.filter(name=TOTEM).exists())
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_cuentas_sinteticas_habilitadas_con_clave_validada_y_correo_sin_verificar(self):
        self.ejecutar_demo(self.clave)
        for nombre, rol, _ in CUENTAS_DEMO:
            with self.subTest(cuenta=nombre):
                usuario = get_user_model().objects.get(username=nombre)
                self.assertTrue(usuario.check_password(self.clave))
                self.assertFalse(usuario.is_staff)
                self.assertFalse(usuario.is_superuser)
                self.assertTrue(usuario.email.endswith("@example.invalid"))
                self.assertIsNone(usuario.perfil.correo_verificado_en)
                self.assertIsNone(usuario.perfil.solicitud_correo)
                self.assertEqual(estado_acceso(usuario), (True, rol))

    def test_repeticion_no_modifica_cuentas_perfiles_roles_ni_hashes(self):
        self.ejecutar_demo(self.clave)
        Usuario = get_user_model()
        cuentas = list(Usuario.objects.order_by("pk").values())
        perfiles = list(Perfil.objects.order_by("pk").values())
        grupos = list(Usuario.groups.through.objects.order_by("pk").values())
        self.ejecutar_demo("Otra-clave-sintetica-2026!")
        self.ejecutar_demo()
        self.assertEqual(list(Usuario.objects.order_by("pk").values()), cuentas)
        self.assertEqual(list(Perfil.objects.order_by("pk").values()), perfiles)
        self.assertEqual(list(Usuario.groups.through.objects.order_by("pk").values()), grupos)

    def test_colision_con_cuenta_existente_no_la_modifica_ni_regulariza(self):
        usuario = get_user_model().objects.create_superuser(
            username="demo_qf", password=self.clave, email="previo@example.invalid",
        )
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])
        grupo = Group.objects.create(name="Grupo previo sintético")
        usuario.groups.add(grupo)
        antes = get_user_model().objects.filter(pk=usuario.pk).values().get()
        self.ejecutar_demo(self.clave)
        self.assertEqual(get_user_model().objects.filter(pk=usuario.pk).values().get(), antes)
        self.assertFalse(Perfil.objects.filter(usuario=usuario).exists())
        self.assertEqual(list(usuario.groups.all()), [grupo])

    def test_sin_clave_en_noinput_no_escribe_cuentas_ni_grupos(self):
        with self.assertRaises(CommandError):
            self.ejecutar_demo()
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Group.objects.exists())

    def test_clave_debil_se_rechaza_sin_escrituras_parciales(self):
        with self.assertRaises(CommandError):
            self.ejecutar_demo("123")
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Perfil.objects.exists())
        self.assertFalse(Group.objects.exists())

    def test_fallo_en_segunda_cuenta_revierte_toda_la_preparacion(self):
        with patch("usuariosapp.services.validate_password", side_effect=[None, ValidationError("Fallo sintético")]):
            with self.assertRaises(CommandError):
                self.ejecutar_demo(self.clave)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Perfil.objects.exists())
        self.assertFalse(Group.objects.exists())

    def test_clave_interactiva_exige_confirmacion_y_no_se_imprime(self):
        salida = StringIO()
        with patch.dict(os.environ, {"CESFAM_DEMO_PASSWORD": ""}), patch(
            "usuariosapp.management.commands.crear_usuarios_demo.getpass.getpass",
            side_effect=[self.clave, self.clave],
        ) as preguntar:
            call_command("crear_usuarios_demo", stdout=salida)
        self.assertEqual(preguntar.call_count, 2)
        self.assertEqual(get_user_model().objects.count(), 3)
        self.assertNotIn(self.clave, salida.getvalue())

    def test_confirmacion_distinta_cancela_sin_escrituras(self):
        with patch.dict(os.environ, {"CESFAM_DEMO_PASSWORD": ""}), patch(
            "usuariosapp.management.commands.crear_usuarios_demo.getpass.getpass",
            side_effect=[self.clave, "otra-clave-sintetica"],
        ):
            with self.assertRaises(CommandError):
                call_command("crear_usuarios_demo", stdout=StringIO())
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Group.objects.exists())
