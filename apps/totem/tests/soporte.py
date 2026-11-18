"""Fixtures exclusivamente sintéticas; ninguna se ejecuta al importar el módulo."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TransactionTestCase, override_settings

from apps.totem.models import DispositivoTotem
from apps.totem.services import generar_codigo_activacion, consumir_codigo_activacion


class BaseTotemPostgreSQL(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        if connection.vendor != "postgresql" or connection.settings_dict["NAME"] != "test_cesfam_desarrollo":
            raise RuntimeError("Estas pruebas requieren PostgreSQL y test_cesfam_desarrollo.")
        super().setUpClass()

    def setUp(self):
        # Clave pública de fixture sin utilidad fuera de estos escenarios.
        self.ajustes = override_settings(
            SECRET_KEY="clave-publica-exclusiva-de-pruebas-sinteticas-totem",
            PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        )
        self.ajustes.enable()
        self.addCleanup(self.ajustes.disable)
        self.usuario = get_user_model().objects.create_user(username="admin-sintetico")
        contenido = ContentType.objects.get_for_model(DispositivoTotem)
        for codename, nombre in DispositivoTotem._meta.permissions:
            permiso, _ = Permission.objects.get_or_create(
                content_type=contenido, codename=codename, defaults={"name": nombre},
            )
            self.usuario.user_permissions.add(permiso)
        self.dispositivo = DispositivoTotem.objects.create(alias="totem-sintetico")

    def generar(self):
        return generar_codigo_activacion(self.usuario, self.dispositivo.pk, "prueba_sintetica")

    def activar(self):
        generado = self.generar()
        return consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)

    def refrescar(self):
        self.dispositivo.refresh_from_db()
        return self.dispositivo
