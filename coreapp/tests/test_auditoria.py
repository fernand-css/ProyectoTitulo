"""Auditoría sin copiar datos del objeto ni perder su referencia al borrarlo."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ValidationError
from django.test import TestCase

from coreapp.auditoria import registrar_accion
from coreapp.models import ModeloAuditado, RegistroAuditoria


class AuditoriaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="operador_sintetico")
        self.objeto = Group.objects.create(name="Objeto sintético")

    def test_registra_exactamente_una_fila_sin_datos_del_objeto(self):
        registro = registrar_accion(self.usuario, "grupo.creado", self.objeto)
        self.assertEqual(RegistroAuditoria.objects.count(), 1)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.accion, "grupo.creado")
        self.assertEqual(registro.objeto_tipo, "auth.Group")
        self.assertEqual(registro.objeto_id, str(self.objeto.pk))
        self.assertIsNotNone(registro.creado_en)
        self.assertEqual(
            {campo.name for campo in RegistroAuditoria._meta.fields},
            {"id", "usuario", "accion", "objeto_tipo", "objeto_id", "creado_en"},
        )

    def test_conserva_referencia_si_se_borra_objeto_y_actor(self):
        registro = registrar_accion(self.usuario, "grupo.creado", self.objeto)
        referencia = registro.objeto_id
        self.objeto.delete()
        self.usuario.delete()
        registro.refresh_from_db()
        self.assertIsNone(registro.usuario)
        self.assertEqual(registro.objeto_id, referencia)
        self.assertEqual(registro.objeto_tipo, "auth.Group")

    def test_admite_accion_sin_usuario(self):
        for usuario in (None, AnonymousUser()):
            with self.subTest(usuario=usuario):
                registro = registrar_accion(usuario, "grupo.creado", self.objeto)
                self.assertIsNone(registro.usuario)

    def test_objeto_sin_guardar_no_deja_registro(self):
        with self.assertRaises(ValueError):
            registrar_accion(self.usuario, "grupo.creado", Group(name="Sin guardar"))
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_valida_longitudes_antes_de_guardar(self):
        with self.assertRaises(ValidationError):
            registrar_accion(self.usuario, "a" * 61, self.objeto)
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_modelo_base_es_abstracto_y_no_fija_usuario_propio(self):
        self.assertTrue(ModeloAuditado._meta.abstract)
        for nombre in ("creado_por", "modificado_por"):
            campo = ModeloAuditado._meta.get_field(nombre)
            self.assertTrue(campo.null)
            self.assertTrue(campo.blank)
            self.assertEqual(campo.remote_field.model, "auth.User")

    def test_orden_mas_reciente_primero(self):
        primero = registrar_accion(self.usuario, "grupo.creado", self.objeto)
        ultimo = registrar_accion(self.usuario, "grupo.consultado", self.objeto)
        self.assertEqual(list(RegistroAuditoria.objects.all()), [ultimo, primero])
