"""Bitácora solo consultable por superusuario, incluso con permisos explícitos."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from coreapp.auditoria import LOGIN_FALLIDO, registrar_evento
from coreapp.models import RegistroAuditoria
from coreapp.roles import ROLES_INTERNOS
from usuariosapp.models import Perfil
from usuariosapp.services import crear_roles


class AuditoriaAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(username="admin_consulta_sintetico")
        cls.actor = get_user_model().objects.create_user(
            username="actor-no-visible-sintetico", first_name="NombreNoVisibleSintetico",
            last_name="ApellidoNoVisibleSintetico", email="actor-no-visible@example.invalid",
        )
        cls.registro = registrar_evento(cls.actor, "perfil.editado", objeto=cls.actor)
        cls.fallido = registrar_evento(None, LOGIN_FALLIDO)
        cls.url = reverse("admin:coreapp_registroauditoria_changelist")
        cls.detalle = reverse("admin:coreapp_registroauditoria_change", args=[cls.registro.pk])

    def test_superusuario_consulta_sin_exponer_datos_personales_del_actor(self):
        self.client.force_login(self.admin)
        for ruta in (self.url, self.detalle):
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, f"Cuenta {self.actor.pk}")
                for dato in (self.actor.username, self.actor.first_name, self.actor.last_name, self.actor.email):
                    self.assertNotContains(respuesta, dato)
                self.assertNotContains(respuesta, 'name="_save"')
                self.assertNotContains(respuesta, 'value="delete_selected"')

    def test_consulta_por_actor_fecha_accion_y_referencia(self):
        self.client.force_login(self.admin)
        filtros = (
            {"actor": str(self.actor.pk)},
            {"accion__exact": "perfil.editado"},
            {"q": str(self.actor.pk), "accion__exact": "perfil.editado"},
            {"creado_en__gte": self.registro.creado_en.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), "accion__exact": "perfil.editado"},
        )
        for parametros in filtros:
            with self.subTest(parametros=parametros):
                respuesta = self.client.get(self.url, parametros)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(list(respuesta.context["cl"].result_list), [self.registro])
        respuesta = self.client.get(self.url, {"actor": "sin_actor"})
        self.assertEqual(list(respuesta.context["cl"].result_list), [self.fallido])

    def test_filtro_actor_invalido_no_provoca_error_ni_muestra_resultados(self):
        self.client.force_login(self.admin)
        for valor in ("invalido", "9" * 80, "-1"):
            with self.subTest(valor=valor):
                respuesta = self.client.get(self.url, {"actor": valor})
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(list(respuesta.context["cl"].result_list), [])

    def test_superusuario_no_puede_agregar_modificar_borrar_ni_por_accion_masiva(self):
        self.client.force_login(self.admin)
        antes = list(RegistroAuditoria.objects.order_by("pk").values())
        rutas = (
            (reverse("admin:coreapp_registroauditoria_add"), {"accion": "cambio"}),
            (self.detalle, {"accion": "alterada"}),
            (reverse("admin:coreapp_registroauditoria_delete", args=[self.registro.pk]), {"post": "yes"}),
        )
        for ruta, datos in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.post(ruta, datos).status_code, 403)
        self.client.post(self.url, {"action": "delete_selected", "_selected_action": [self.registro.pk], "post": "yes"})
        self.assertEqual(list(RegistroAuditoria.objects.order_by("pk").values()), antes)

    def test_cada_rol_incluso_staff_con_permisos_no_consulta_la_bitacora(self):
        roles = crear_roles()
        permisos = Permission.objects.filter(content_type__app_label="coreapp", content_type__model="registroauditoria")
        for numero, rol in enumerate(ROLES_INTERNOS):
            cuenta = get_user_model().objects.create_user(username=f"staff_rol_sintetico_{numero}", is_staff=True)
            Perfil.objects.create(usuario=cuenta)
            cuenta.groups.add(roles[rol])
            cuenta.user_permissions.set(permisos)
            self.client.force_login(cuenta)
            with self.subTest(rol=rol):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.get(self.detalle).status_code, 403)
                self.assertNotContains(self.client.get(reverse("admin:index")), f'href="{self.url}"')

    def test_anonimo_redirigido_y_superusuario_inactivo_no_accede(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.admin)
        get_user_model().objects.filter(pk=self.admin.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.url).status_code, 302)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CuentasAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from usuariosapp.tests.test_gestion_usuarios import cuenta_personal
        from coreapp.roles import TECNICO

        cls.admin = get_user_model().objects.create_superuser(username="root_cuentas_sintetico")
        cls.objetivo = cuenta_personal("objetivo_admin_sintetico", TECNICO)

    def setUp(self):
        from coreapp.roles import TECNICO

        self.client.force_login(self.admin)
        self.url = reverse("admin:auth_user_change", args=[self.objetivo.pk])
        self.datos = {
            "username": self.objetivo.username, "first_name": self.objetivo.first_name,
            "last_name": self.objetivo.last_name, "email": self.objetivo.email,
            "rol": TECNICO, "is_active": "on", "grupos_extra": [], "user_permissions": [],
        }

    def test_superusuario_crea_jefatura_con_correo_pendiente_y_clave_validada(self):
        from django.core import mail
        from coreapp.roles import JEFA

        clave = "Solo-pruebas-Jefatura-2026!"
        respuesta = self.client.post(reverse("admin:auth_user_add"), {
            **self.datos, "username": "jefatura_nueva_sintetica", "rol": JEFA,
            "password1": clave, "password2": clave,
        })
        self.assertEqual(respuesta.status_code, 302)
        cuenta = get_user_model().objects.get(username="jefatura_nueva_sintetica")
        self.assertTrue(cuenta.check_password(clave))
        self.assertEqual(list(cuenta.groups.values_list("name", flat=True)), [JEFA])
        self.assertEqual(cuenta.email, "")
        self.assertIsNone(cuenta.perfil.correo_verificado_en)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="usuario.creado", usuario=self.admin, objeto_id=str(cuenta.pk)).count(), 1)
        formulario = self.client.get(reverse("admin:auth_user_change", args=[cuenta.pk])).context["adminform"].form
        self.assertEqual(formulario.initial["email"], self.datos["email"])

    def test_cambio_de_rol_grupos_y_permisos_es_unico_y_auditado(self):
        from coreapp.roles import JEFA

        extra = Group.objects.create(name="Grupo adicional sintético")
        permiso = Permission.objects.filter(content_type__app_label="coreapp").first()
        respuesta = self.client.post(self.url, {
            **self.datos, "rol": JEFA, "is_staff": "on",
            "grupos_extra": [extra.pk], "user_permissions": [permiso.pk],
        })
        self.assertEqual(respuesta.status_code, 302)
        self.objetivo.refresh_from_db()
        self.assertCountEqual(self.objetivo.groups.values_list("name", flat=True), [JEFA, extra.name])
        self.assertEqual(list(self.objetivo.user_permissions.all()), [permiso])
        self.assertTrue(self.objetivo.is_staff)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="usuario.rol_cambiado", usuario=self.admin).count(), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="usuario.privilegios_cambiados", usuario=self.admin).count(), 1)

    def test_correo_admin_no_puede_marcarse_verificado_por_post(self):
        from django.core import mail

        self.assertEqual(self.client.post(self.url, {**self.datos, "email": "nuevo_admin@example.invalid", "correo_verificado_en": "2026-11-01"}).status_code, 302)
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.email, self.datos["email"])
        self.assertEqual(self.objetivo.perfil.correo_pendiente, "nuevo_admin@example.invalid")
        self.assertEqual(mail.outbox[-1].to, ["nuevo_admin@example.invalid"])

    def test_cambiar_clave_de_otra_cuenta_registra_actor_admin_y_revoca_sesion(self):
        from django.test import Client

        anterior = "Solo-pruebas-Anterior-2026!"
        nueva = "Solo-pruebas-Renovada-2026!"
        self.objetivo.set_password(anterior)
        self.objetivo.save(update_fields=["password"])
        cliente = Client()
        cliente.force_login(self.objetivo)
        respuesta = self.client.post(self.url, {**self.datos, "password1": nueva, "password2": nueva})
        self.assertEqual(respuesta.status_code, 302)
        self.objetivo.refresh_from_db()
        self.assertTrue(self.objetivo.check_password(nueva))
        self.assertFalse(self.objetivo.check_password(anterior))
        self.assertEqual(cliente.get("/").status_code, 302)
        evento = RegistroAuditoria.objects.get(accion="clave.cambiada")
        self.assertEqual(evento.usuario_id, self.admin.pk)
        self.assertEqual(evento.objeto_id, str(self.objetivo.pk))

    def test_cuenta_ordinaria_sin_rol_y_grupo_extra_operativo_se_rechazan(self):
        from coreapp.roles import JEFA

        antes = set(self.objetivo.groups.values_list("name", flat=True))
        for cambios in ({"rol": ""}, {"grupos_extra": [crear_roles()[JEFA].pk]}):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.client.post(self.url, {**self.datos, **cambios}).status_code, 200)
        self.assertEqual(set(self.objetivo.groups.values_list("name", flat=True)), antes)

    def test_staff_con_permisos_no_administra_usuarios_ni_jefaturas(self):
        from usuariosapp.tests.test_gestion_usuarios import cuenta_personal
        from coreapp.roles import JEFA

        qf = cuenta_personal("qf_staff_admin_sintetica", JEFA, is_staff=True)
        qf.user_permissions.set(Permission.objects.filter(content_type__app_label="auth"))
        self.client.force_login(qf)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:auth_user_changelist")).status_code, 403)

    def test_grupos_no_se_modifican_ni_se_borran_desde_admin(self):
        from coreapp.roles import TECNICO

        grupo = crear_roles()[TECNICO]
        url = reverse("admin:auth_group_change", args=[grupo.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"name": "Renombrado"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:auth_group_delete", args=[grupo.pk]), {"post": "yes"}).status_code, 403)
        grupo.refresh_from_db()
        self.assertEqual(grupo.name, TECNICO)

    def test_borrado_cuentas_masivo_y_directo_no_disponible(self):
        self.assertEqual(self.client.post(reverse("admin:auth_user_delete", args=[self.objetivo.pk]), {"post": "yes"}).status_code, 403)
        self.client.post(reverse("admin:auth_user_changelist"), {"action": "delete_selected", "_selected_action": [self.objetivo.pk], "post": "yes"})
        self.assertTrue(get_user_model().objects.filter(pk=self.objetivo.pk).exists())

    def test_fallo_al_auditar_admin_revierte_datos_y_m2m(self):
        from unittest.mock import patch
        from django.db import DatabaseError
        from coreapp.roles import ENCARGADO, TECNICO

        with patch("usuariosapp.services.registrar_evento", side_effect=DatabaseError("Fallo sintético")):
            with self.assertRaises(DatabaseError):
                self.client.post(self.url, {**self.datos, "first_name": "NoGuardar", "rol": ENCARGADO})
        self.objetivo.refresh_from_db()
        self.assertEqual(self.objetivo.first_name, "Persona")
        self.assertEqual(list(self.objetivo.groups.values_list("name", flat=True)), [TECNICO])

    def test_admin_no_crea_log_generico_con_representacion_personal(self):
        from django.contrib.admin.models import LogEntry

        self.client.post(self.url, {**self.datos, "first_name": "Actualizado"})
        self.assertFalse(LogEntry.objects.exists())
        self.assertEqual(RegistroAuditoria.objects.filter(accion="usuario.editado", usuario=self.admin).count(), 1)

    def test_historial_redirige_a_bitacora_filtrada_por_cuenta(self):
        self.client.post(self.url, {**self.datos, "first_name": "Actualizado"})
        respuesta = self.client.get(reverse("admin:auth_user_history", args=[self.objetivo.pk]), follow=True)
        self.assertEqual(respuesta.status_code, 200)
        registros = list(respuesta.context["cl"].result_list)
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0].objeto_id, str(self.objetivo.pk))
        self.assertEqual(registros[0].objeto_tipo, "auth.User")
