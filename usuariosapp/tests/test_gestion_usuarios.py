"""Panel Q.F., límites de escritura, atomicidad y promociones concurrentes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from coreapp.roles import ENCARGADO, JEFA, TECNICO
from usuariosapp.models import Perfil
from usuariosapp.services import cambiar_estado_cuenta, crear_roles, guardar_cuenta_admin, guardar_cuenta_gestion


CLAVE = "Solo-pruebas-Gestion-2026!"


def cuenta_personal(nombre, rol, **flags):
    usuario = get_user_model().objects.create_user(
        username=nombre, first_name="Persona", last_name="Sintética",
        email=f"{nombre}@example.invalid", **flags,
    )
    usuario.groups.add(crear_roles()[rol])
    Perfil.objects.create(usuario=usuario, correo_verificado_en=timezone.now())
    return usuario


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class GestionUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.qf = cuenta_personal("qf_gestion_sintetica", JEFA)
        cls.tecnico = cuenta_personal("tecnico_gestion_sintetico", TECNICO)
        cls.encargado = cuenta_personal("terreno_gestion_sintetico", ENCARGADO, is_active=False)
        cls.jefatura = cuenta_personal("jefatura_excluida_sintetica", JEFA)
        cls.staff = cuenta_personal("staff_excluido_sintetico", TECNICO, is_staff=True)
        cls.admin = get_user_model().objects.create_superuser(username="root_excluido_sintetico")
        cls.multirrol = cuenta_personal("multirrol_excluido_sintetico", TECNICO)
        cls.multirrol.groups.add(crear_roles()[ENCARGADO])

    def setUp(self):
        self.client.force_login(self.qf)
        self.lista = reverse("usuariosapp:gestion_usuarios")
        self.nuevo = reverse("usuariosapp:gestion_nuevo")
        self.editar = reverse("usuariosapp:gestion_editar", args=[self.tecnico.pk])
        self.estado = reverse("usuariosapp:gestion_estado", args=[self.tecnico.pk])
        self.datos = {"first_name": "Persona", "last_name": "Sintética", "email": self.tecnico.email, "rol": TECNICO}

    def test_lista_solo_cuentas_operativas_gestionables_incluidas_inactivas(self):
        respuesta = self.client.get(self.lista)
        self.assertEqual(respuesta.status_code, 200)
        self.assertCountEqual([cuenta.pk for cuenta in respuesta.context["cuentas"]], [self.tecnico.pk, self.encargado.pk])
        self.assertContains(respuesta, "Encargado de terreno")
        for usuario in (self.qf, self.jefatura, self.staff, self.admin, self.multirrol):
            self.assertNotContains(respuesta, usuario.username)

    def test_crear_tecnico_con_clave_y_correo_pendiente_sin_privilegios(self):
        respuesta = self.client.post(self.nuevo, {
            **self.datos, "username": "nuevo_operador_sintetico", "email": "nuevo@example.invalid",
            "password1": CLAVE, "password2": CLAVE, "is_superuser": "1", "is_staff": "1",
        })
        self.assertRedirects(respuesta, self.lista)
        usuario = get_user_model().objects.get(username="nuevo_operador_sintetico")
        self.assertTrue(usuario.check_password(CLAVE))
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual(usuario.email, "")
        self.assertEqual(usuario.perfil.correo_pendiente, "nuevo@example.invalid")
        self.assertIsNone(usuario.perfil.correo_verificado_en)
        self.assertEqual(list(usuario.groups.values_list("name", flat=True)), [TECNICO])
        self.assertEqual(mail.outbox[-1].to, ["nuevo@example.invalid"])
        eventos = RegistroAuditoria.objects.filter(objeto_id=str(usuario.pk), accion__in=["usuario.creado", "usuario.rol_cambiado"])
        self.assertEqual(eventos.count(), 2)
        self.assertFalse(eventos.exclude(usuario=self.qf).exists())
        formulario = self.client.get(reverse("usuariosapp:gestion_editar", args=[usuario.pk])).context["form"]
        self.assertEqual(formulario.initial["email"], "nuevo@example.invalid")
        cliente = Client()
        cliente.force_login(usuario)
        self.assertEqual(cliente.get(reverse("usuariosapp:perfil")).context["form"].initial["email"], "nuevo@example.invalid")

    def test_cambiar_rol_y_nombre_conserva_usuario_clave_y_privilegios(self):
        previo = self.tecnico.password
        respuesta = self.client.post(self.editar, {
            **self.datos, "first_name": "Actualizado", "rol": ENCARGADO,
            "username": "no-cambiar", "password1": CLAVE, "is_superuser": "1", "is_staff": "1",
        })
        self.assertRedirects(respuesta, self.lista)
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.first_name, "Actualizado")
        self.assertEqual(self.tecnico.username, "tecnico_gestion_sintetico")
        self.assertEqual(self.tecnico.password, previo)
        self.assertFalse(self.tecnico.is_superuser)
        self.assertFalse(self.tecnico.is_staff)
        self.assertEqual(list(self.tecnico.groups.values_list("name", flat=True)), [ENCARGADO])
        self.assertEqual(RegistroAuditoria.objects.filter(accion="usuario.rol_cambiado").count(), 1)

    def test_correo_editado_por_qf_no_sustituye_el_vigente(self):
        self.client.post(self.editar, {**self.datos, "email": "solicitado@example.invalid", "correo_verificado_en": timezone.now().isoformat()})
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.email, self.datos["email"])
        self.assertEqual(self.tecnico.perfil.correo_pendiente, "solicitado@example.invalid")
        self.assertEqual(mail.outbox[-1].to, ["solicitado@example.invalid"])

    def test_desactivar_revoca_sesion_conserva_cuenta_y_repetir_no_duplica_evento(self):
        cliente = Client()
        cliente.force_login(self.tecnico)
        self.assertEqual(cliente.get("/").status_code, 200)
        self.assertRedirects(self.client.post(self.estado, {"activo": "0"}), self.lista)
        self.client.post(self.estado, {"activo": "0"})
        self.assertEqual(cliente.get("/").status_code, 302)
        self.tecnico.refresh_from_db()
        self.assertFalse(self.tecnico.is_active)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="usuario.desactivado").count(), 1)
        self.client.post(self.estado, {"activo": "1"})
        self.tecnico.refresh_from_db()
        self.assertTrue(self.tecnico.is_active)

    def test_ids_de_jefatura_staff_superusuario_y_propia_no_se_exponen_ni_modifican(self):
        for usuario in (self.qf, self.jefatura, self.staff, self.admin, self.multirrol):
            with self.subTest(cuenta=usuario.pk):
                antes = get_user_model().objects.filter(pk=usuario.pk).values().get()
                url = reverse("usuariosapp:gestion_editar", args=[usuario.pk])
                estado = reverse("usuariosapp:gestion_estado", args=[usuario.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, self.datos).status_code, 404)
                self.assertEqual(self.client.post(estado, {"activo": "0"}).status_code, 404)
                self.assertEqual(get_user_model().objects.filter(pk=usuario.pk).values().get(), antes)

    def test_tecnico_encargado_y_anonimo_no_acceden_al_panel(self):
        self.assertEqual(Client().get(self.lista).status_code, 302)
        for usuario in (self.tecnico, self.encargado):
            get_user_model().objects.filter(pk=usuario.pk).update(is_active=True)
            cliente = Client()
            cliente.force_login(usuario)
            for ruta in (self.lista, self.nuevo, self.editar):
                with self.subTest(usuario=usuario.pk, ruta=ruta):
                    self.assertEqual(cliente.get(ruta).status_code, 403)
                    self.assertEqual(cliente.post(ruta, self.datos).status_code, 403)

    def test_creacion_invalida_no_escribe_ni_envia(self):
        base = {**self.datos, "username": "nuevo_sintetico", "password1": CLAVE, "password2": CLAVE}
        for cambios in ({"rol": JEFA}, {"password2": "no-coincide"}, {"password1": "123", "password2": "123"}, {"username": self.tecnico.username}):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.client.post(self.nuevo, {**base, **cambios}).status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="nuevo_sintetico").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_escrituras_exigen_csrf_y_estado_solo_post_explicito(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.qf)
        self.assertEqual(cliente.post(self.editar, self.datos).status_code, 403)
        self.assertEqual(cliente.post(self.estado, {"activo": "0"}).status_code, 403)
        self.assertEqual(self.client.get(self.estado).status_code, 405)
        self.assertEqual(self.client.post(self.estado, {}).status_code, 400)

    def test_servicio_revalida_actor_y_objetivo_con_objetos_anteriores(self):
        from django.contrib.auth.models import AnonymousUser

        datos = dict(self.datos, origen="http://testserver/", pk=self.tecnico.pk)
        with self.assertRaises(PermissionDenied):
            guardar_cuenta_gestion(AnonymousUser(), **datos)
        with self.assertRaises(PermissionDenied):
            cambiar_estado_cuenta(AnonymousUser(), self.tecnico.pk, activo=False)
        self.tecnico.groups.set([crear_roles()[JEFA]])
        with self.assertRaises(PermissionDenied):
            guardar_cuenta_gestion(self.qf, **datos)
        self.tecnico.groups.set([crear_roles()[TECNICO]])
        self.qf.groups.set([crear_roles()[TECNICO]])
        with self.assertRaises(PermissionDenied):
            guardar_cuenta_gestion(self.qf, **datos)

    def test_fallo_de_auditoria_revierte_nombres_roles_y_estado(self):
        with patch("usuariosapp.services.registrar_evento", side_effect=DatabaseError("Fallo sintético")):
            with self.assertRaises(DatabaseError):
                guardar_cuenta_gestion(self.qf, pk=self.tecnico.pk, origen="http://testserver/", **{**self.datos, "rol": ENCARGADO, "first_name": "NoGuardar"})
            with self.assertRaises(DatabaseError):
                cambiar_estado_cuenta(self.qf, self.tecnico.pk, activo=False)
        self.tecnico.refresh_from_db()
        self.assertEqual(self.tecnico.first_name, "Persona")
        self.assertTrue(self.tecnico.is_active)
        self.assertEqual(list(self.tecnico.groups.values_list("name", flat=True)), [TECNICO])

    def test_fallo_de_envio_no_deja_alta_parcial(self):
        with patch("usuariosapp.services._enviar_correo", side_effect=OSError("Fallo sintético")):
            respuesta = self.client.post(self.nuevo, {**self.datos, "username": "no_persistir_sintetico", "password1": CLAVE, "password2": CLAVE})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="no_persistir_sintetico").exists())
        self.assertFalse(RegistroAuditoria.objects.filter(accion="usuario.creado").exists())


class ConcurrenciaGestionTests(TransactionTestCase):
    def test_promocion_a_jefatura_no_permite_edicion_posterior_por_qf(self):
        qf = cuenta_personal("qf_concurrente_sintetica", JEFA)
        objetivo = cuenta_personal("objetivo_concurrente_sintetico", TECNICO)
        admin = get_user_model().objects.create_superuser(username="root_concurrente_sintetico")
        barrera = Barrier(2)

        def operar(superior):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=admin.pk if superior else qf.pk)
                barrera.wait(timeout=5)
                datos = dict(first_name="Jefatura" if superior else "CambioQF", last_name="Sintética", email=objetivo.email, rol=JEFA if superior else TECNICO)
                if superior:
                    guardar_cuenta_admin(actor, pk=objetivo.pk, datos={**datos, "username": objetivo.username}, origen="http://testserver/")
                    return "promovida"
                try:
                    guardar_cuenta_gestion(actor, pk=objetivo.pk, origen="http://testserver/", **datos)
                    return "editada"
                except PermissionDenied:
                    return "denegada"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(operar, superior) for superior in (True, False)]
            resultados = [futuro.result(timeout=10) for futuro in futuros]
        self.assertEqual(resultados[0], "promovida")
        self.assertIn(resultados[1], ("editada", "denegada"))
        objetivo.refresh_from_db()
        self.assertEqual(objetivo.first_name, "Jefatura")
        self.assertEqual(list(objetivo.groups.values_list("name", flat=True)), [JEFA])
        with self.assertRaises(PermissionDenied):
            guardar_cuenta_gestion(qf, pk=objetivo.pk, first_name="NoGuardar", last_name="Sintética", email=objetivo.email, rol=TECNICO, origen="http://testserver/")
