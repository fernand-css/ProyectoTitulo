"""Perfil y actualización desde la base anterior, solo con datos sintéticos."""

import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core import mail
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from coreapp.roles import TECNICO
from usuariosapp.models import Perfil
from usuariosapp.services import crear_roles


class PerfilTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="personal_sintetico")

    def test_perfil_no_verifica_correo_ni_crea_solicitud_por_omision(self):
        perfil = Perfil.objects.create(usuario=self.usuario)
        self.assertEqual(self.usuario.perfil, perfil)
        self.assertIsNone(perfil.correo_verificado_en)
        self.assertEqual(perfil.correo_pendiente, "")
        self.assertIsNone(perfil.solicitud_correo)

    def test_usuario_admite_solo_un_perfil(self):
        Perfil.objects.create(usuario=self.usuario)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Perfil.objects.create(usuario=self.usuario)

    def test_verificacion_y_solicitud_persisten_sin_alterar_correo_vigente(self):
        self.usuario.email = "actual@example.invalid"
        self.usuario.save(update_fields=["email"])
        fecha = timezone.now()
        solicitud = uuid.uuid4()
        perfil = Perfil.objects.create(
            usuario=self.usuario,
            correo_verificado_en=fecha,
            correo_pendiente="nuevo@example.invalid",
            solicitud_correo=solicitud,
        )
        perfil.refresh_from_db()
        self.usuario.refresh_from_db()
        self.assertEqual(perfil.correo_verificado_en, fecha)
        self.assertEqual(perfil.solicitud_correo, solicitud)
        self.assertEqual(perfil.correo_pendiente, "nuevo@example.invalid")
        self.assertEqual(self.usuario.email, "actual@example.invalid")

    def test_alta_directa_no_asigna_perfil_ni_rol_por_inferencia(self):
        self.assertFalse(Perfil.objects.filter(usuario=self.usuario).exists())
        self.assertFalse(self.usuario.groups.exists())

    def test_superusuario_sin_perfil_conserva_login_e_inicio(self):
        clave = "Clave-sintetica-solo-pruebas-2026!"
        admin = get_user_model().objects.create_superuser(username="admin_sintetico", password=clave)
        self.assertFalse(Perfil.objects.filter(usuario=admin).exists())
        respuesta = self.client.post(reverse("usuariosapp:login"), {"username": admin.username, "password": clave})
        self.assertRedirects(respuesta, reverse("coreapp:inicio"))
        self.assertContains(self.client.get(reverse("coreapp:inicio")), "Administración")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EdicionPerfilTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="perfil_editable_sintetico", first_name="Nombre", last_name="Sintético",
            email="vigente@example.invalid",
        )
        self.usuario.groups.add(crear_roles()[TECNICO])
        self.perfil = Perfil.objects.create(usuario=self.usuario, correo_verificado_en=timezone.now())
        self.client.force_login(self.usuario)
        self.url = reverse("usuariosapp:perfil")
        self.datos = {"first_name": "Nuevo", "last_name": "Apellido", "email": self.usuario.email}

    def test_get_muestra_datos_y_no_crea_ni_modifica_solicitudes(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, self.usuario.email)
        self.assertContains(respuesta, "Correo vigente verificado")
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.perfil.refresh_from_db()
        self.assertIsNone(self.perfil.solicitud_correo)
        self.assertEqual(len(mail.outbox), 0)

    def test_nombres_persisten_y_correo_vigente_no_necesita_otro_enlace(self):
        self.assertRedirects(self.client.post(self.url, self.datos), self.url)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Nuevo")
        self.assertEqual(self.usuario.last_name, "Apellido")
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(self.client.get(self.url), 'value="Nuevo"')

    def test_campos_de_privilegios_y_otra_cuenta_no_se_modifican(self):
        otra = get_user_model().objects.create_user(username="otra_cuenta_sintetica")
        antes = list(self.usuario.groups.values_list("pk", flat=True))
        respuesta = self.client.post(self.url, {
            **self.datos, "pk": otra.pk, "usuario_id": otra.pk, "username": "suplantado",
            "is_superuser": "1", "is_staff": "1", "groups": [], "password": "no-cambiar",
        })
        self.assertEqual(respuesta.status_code, 302)
        self.usuario.refresh_from_db()
        otra.refresh_from_db()
        self.assertEqual(self.usuario.username, "perfil_editable_sintetico")
        self.assertFalse(self.usuario.is_superuser)
        self.assertFalse(self.usuario.is_staff)
        self.assertEqual(list(self.usuario.groups.values_list("pk", flat=True)), antes)
        self.assertFalse(self.usuario.has_usable_password())
        self.assertEqual(otra.first_name, "")

    def test_datos_invalidos_no_se_guardan_y_tienen_errores_accesibles(self):
        for campo, valor in (("first_name", ""), ("last_name", ""), ("first_name", "x" * 151), ("email", "sin-formato")):
            with self.subTest(campo=campo, valor=valor):
                respuesta = self.client.post(self.url, {**self.datos, campo: valor})
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, 'aria-invalid="true"')
                self.assertContains(respuesta, f'id="id_{campo}_error"')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Nombre")
        self.assertEqual(len(mail.outbox), 0)

    def test_edicion_exige_sesion_habilitada_y_csrf(self):
        anonimo = Client()
        self.assertEqual(anonimo.get(self.url).status_code, 302)
        self.assertEqual(anonimo.post(self.url, self.datos).status_code, 302)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        self.assertEqual(cliente.post(self.url, self.datos).status_code, 403)
        self.perfil.delete()
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)

    def test_superusuario_sin_perfil_solo_lo_crea_al_guardar(self):
        admin = get_user_model().objects.create_superuser(username="admin_perfil_sintetico")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertFalse(Perfil.objects.filter(usuario=admin).exists())
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 302)
        self.assertTrue(Perfil.objects.filter(usuario=admin, correo_verificado_en=None).exists())
        self.assertEqual(len(mail.outbox), 1)


class MigracionPerfilTests(TransactionTestCase):
    destino = [("usuariosapp", "0002_perfiles_existentes")]

    def restaurar_migraciones(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def retroceder(self, destino):
        # Restaurar también si una aserción falla, antes de limpiar la base de tests.
        self.addCleanup(self.restaurar_migraciones)
        executor = MigrationExecutor(connection)
        executor.migrate(destino)
        return executor

    def test_actualizacion_desde_base_01_preserva_cuentas_claves_y_grupos(self):
        executor = self.retroceder([("usuariosapp", None)])
        estado = executor.loader.project_state([("auth", "0012_alter_user_first_name_max_length")])
        UsuarioAnterior = estado.apps.get_model("auth", "User")
        GrupoAnterior = estado.apps.get_model("auth", "Group")
        grupo = GrupoAnterior.objects.create(name=TECNICO)
        clave = "Clave-sintetica-migracion-2026!"
        password_hash = make_password(clave)
        admin = UsuarioAnterior.objects.create(
            username="admin_anterior_sintetico", password=password_hash,
            email="admin@example.invalid", is_staff=True, is_superuser=True,
        )
        tecnico = UsuarioAnterior.objects.create(
            username="tecnico_anterior_sintetico", password=password_hash,
            first_name="Persona", last_name="Sintética", email="tecnico@example.invalid",
        )
        tecnico.groups.add(grupo)
        UsuarioAnterior.objects.create(username="inactivo_sintetico", password=password_hash, is_active=False)
        antes = list(UsuarioAnterior.objects.order_by("pk").values())

        executor = MigrationExecutor(connection)
        executor.migrate(self.destino)

        Usuario = get_user_model()
        self.assertEqual(list(Usuario.objects.order_by("pk").values()), antes)
        self.assertEqual(Perfil.objects.count(), 3)
        self.assertFalse(Perfil.objects.exclude(correo_verificado_en=None).exists())
        self.assertFalse(Perfil.objects.exclude(correo_pendiente="").exists())
        self.assertFalse(Perfil.objects.exclude(solicitud_correo=None).exists())
        self.assertEqual(list(Usuario.objects.get(pk=tecnico.pk).groups.values_list("name", flat=True)), [TECNICO])
        self.assertEqual(Usuario.objects.get(pk=admin.pk).groups.count(), 0)
        self.assertTrue(Usuario.objects.get(pk=tecnico.pk).check_password(clave))
        respuesta = self.client.post(reverse("usuariosapp:login"), {"username": admin.username, "password": clave})
        self.assertRedirects(respuesta, reverse("coreapp:inicio"))
        self.assertContains(self.client.get(reverse("coreapp:inicio")), "Administración")

    def test_reaplicar_datos_conserva_perfiles_existentes_y_verificacion(self):
        self.retroceder([("usuariosapp", "0001_initial")])
        Usuario = get_user_model()
        existente = Usuario.objects.create_user(username="perfil_previo_sintetico")
        faltante = Usuario.objects.create_user(username="sin_perfil_sintetico")
        fecha = timezone.now()
        solicitud = uuid.uuid4()
        previo = Perfil.objects.create(
            usuario=existente, correo_verificado_en=fecha,
            correo_pendiente="pendiente@example.invalid", solicitud_correo=solicitud,
        )
        executor = MigrationExecutor(connection)
        executor.migrate(self.destino)
        previo.refresh_from_db()
        self.assertEqual(Perfil.objects.count(), 2)
        self.assertTrue(Perfil.objects.filter(usuario=faltante, correo_verificado_en=None).exists())
        self.assertEqual(previo.correo_verificado_en, fecha)
        self.assertEqual(previo.correo_pendiente, "pendiente@example.invalid")
        self.assertEqual(previo.solicitud_correo, solicitud)
