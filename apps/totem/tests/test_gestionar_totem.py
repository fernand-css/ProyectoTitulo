"""Administración local preparada con entradas y cuentas exclusivamente sintéticas."""
import io
import warnings
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError

from apps.totem.management.commands import gestionar_totem
from apps.totem.models import DispositivoTotem
from apps.totem.services import ResultadoActivacion
from apps.turnos.models import OperacionTurno
from apps.usuarios.roles import ADMINISTRADOR, FUNCIONARIO, QF, TERRENO
from .soporte import BaseTotemPostgreSQL


class TotemAdministracionLocalTests(BaseTotemPostgreSQL):
    def setUp(self):
        super().setUp()
        self.usuario.set_password("clave-sintetica-local")
        self.usuario.save(update_fields=["password"])
        self.salida = io.StringIO()
        self.terminal = patch("apps.totem.management.commands.gestionar_totem.sys.stdin.isatty", return_value=True)
        self.terminal.start()
        self.addCleanup(self.terminal.stop)

    def llamar(self, accion, **opciones):
        return call_command("gestionar_totem", accion, str(self.dispositivo.pk), stdout=self.salida, **opciones)

    def test_generacion_exige_autenticacion_local_y_muestra_una_vez(self):
        with patch("builtins.input", return_value=self.usuario.username), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass", return_value="clave-sintetica-local",
        ) as oculto:
            self.llamar("generar", motivo="prueba_sintetica")
        oculto.assert_called_once()
        self.assertEqual(self.salida.getvalue().count("Código de activación (única entrega):"), 1)
        self.assertNotIn("clave-sintetica-local", self.salida.getvalue())
        self.assertEqual(OperacionTurno.objects.get().usuario_id, self.usuario.pk)
        self.assertEqual(DispositivoTotem.objects.count(), 1)

    def test_consumo_solo_solicita_prueba_del_codigo_no_clave_administrativa(self):
        generado = self.generar()
        with patch("builtins.input", return_value=str(generado.referencia)), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass", return_value=generado.codigo,
        ) as oculto, patch("apps.totem.management.commands.gestionar_totem.authenticate") as autenticar:
            self.llamar("consumir")
        autenticar.assert_not_called()
        oculto.assert_called_once()
        self.assertIn("Credencial técnica (única entrega):", self.salida.getvalue())
        self.assertNotIn(generado.codigo, self.salida.getvalue())

    def test_clave_incorrecta_no_genera_codigo(self):
        with patch("builtins.input", return_value=self.usuario.username), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass", return_value="clave-incorrecta",
        ):
            with self.assertRaises(CommandError):
                self.llamar("generar", motivo="alta")
        self.assertEqual(self.salida.getvalue(), "")
        self.assertEqual(OperacionTurno.objects.count(), 0)

    def test_autenticado_sin_permiso_no_genera(self):
        self.usuario.user_permissions.clear()
        with patch("builtins.input", return_value=self.usuario.username), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass", return_value="clave-sintetica-local",
        ):
            with self.assertRaises(CommandError):
                self.llamar("generar", motivo="alta")
        self.assertEqual(self.salida.getvalue(), "")
        self.assertEqual(OperacionTurno.objects.count(), 0)

    def test_sin_terminal_rechaza_antes_de_pedir_secretos(self):
        with patch("apps.totem.management.commands.gestionar_totem.sys.stdin.isatty", return_value=False), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass",
        ) as oculto:
            with self.assertRaises(CommandError):
                self.llamar("generar", motivo="alta")
        oculto.assert_not_called()

    def test_fallback_de_getpass_se_rechaza(self):
        def sin_ocultar(*args, **kwargs):
            warnings.warn("No se puede ocultar", gestionar_totem.getpass.GetPassWarning)

        with patch("builtins.input", return_value=self.usuario.username), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass", side_effect=sin_ocultar,
        ):
            with self.assertRaises(CommandError):
                self.llamar("generar", motivo="alta")
        self.assertEqual(OperacionTurno.objects.count(), 0)

    def test_no_admite_secretos_en_argumentos(self):
        comando = gestionar_totem.Command()
        parser = comando.create_parser("manage.py", "gestionar_totem")
        opciones = {opcion for accion in parser._actions for opcion in accion.option_strings}
        for prohibido in ("--password", "--codigo", "--credencial", "--clave"):
            self.assertNotIn(prohibido, opciones)

    def test_consulta_administrativa_no_imprime_hash(self):
        generado = self.generar()
        hash_codigo = self.refrescar().hash_activacion
        with patch("builtins.input", return_value=self.usuario.username), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass", return_value="clave-sintetica-local",
        ):
            self.llamar("consultar")
        self.assertNotIn(hash_codigo, self.salida.getvalue())
        self.assertNotIn(generado.codigo, self.salida.getvalue())
        self.assertNotIn("hash_activacion", self.salida.getvalue())

    def test_error_de_base_no_imprime_detalles_o_secretos(self):
        with patch("builtins.input", return_value=self.usuario.username), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass", return_value="clave-sintetica-local",
        ), patch(
            "apps.totem.management.commands.gestionar_totem.generar_codigo_activacion",
            side_effect=OperationalError("detalle-sintetico-que-no-debe-exponerse"),
        ):
            with self.assertRaises(CommandError) as error:
                self.llamar("generar", motivo="alta")
        self.assertNotIn("detalle-sintetico", str(error.exception))
        self.assertEqual(self.salida.getvalue(), "")

    def test_rechazo_de_consumo_no_imprime_credencial(self):
        with patch("builtins.input", return_value="referencia-sintetica"), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass", return_value="codigo-sintetico",
        ), patch(
            "apps.totem.management.commands.gestionar_totem.consumir_codigo_activacion",
            return_value=ResultadoActivacion("rechazado", self.dispositivo.pk),
        ):
            with self.assertRaisesMessage(CommandError, "Activación rechazada."):
                self.llamar("consumir")
        self.assertEqual(self.salida.getvalue(), "")

    def test_revocacion_y_caducidad_delegan_en_servicios(self):
        self.activar()
        with patch("builtins.input", return_value=self.usuario.username), patch(
            "apps.totem.management.commands.gestionar_totem.getpass.getpass", return_value="clave-sintetica-local",
        ):
            self.llamar("revocar", motivo="seguridad")
            self.llamar("caducar")
        self.assertFalse(self.refrescar().activo)
        self.assertIn("revocado", self.salida.getvalue())
        self.assertIn("sin_cambios", self.salida.getvalue())

    def test_roles_conceden_permisos_totem_solo_a_administrador(self):
        call_command("inicializar_roles", stdout=io.StringIO())
        esperados = {codename for codename, _ in DispositivoTotem._meta.permissions}
        actuales = set(Group.objects.get(name=ADMINISTRADOR).permissions.filter(
            content_type__app_label="totem",
        ).values_list("codename", flat=True))
        self.assertEqual(actuales, esperados)
        for nombre in (FUNCIONARIO, QF, TERRENO):
            self.assertFalse(Group.objects.get(name=nombre).permissions.filter(content_type__app_label="totem").exists())
