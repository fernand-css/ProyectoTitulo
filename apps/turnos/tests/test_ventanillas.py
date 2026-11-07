"""Pruebas PostgreSQL preparadas; su ejecución requiere autorización posterior."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase

from apps.pacientes.models import Paciente
from apps.turnos.models import Estado, EstadoCola, OperacionTurno, Turno, Ventanilla
from apps.turnos.services import (
    cambiar_estado, configurar_ventanilla, emitir, llamar_siguiente, rellamar,
)
from apps.usuarios.models import Usuario


class VentanillasPostgreSQLTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        if connection.vendor != "postgresql" or connection.settings_dict["NAME"] != "test_cesfam_desarrollo":
            raise RuntimeError("Estas pruebas requieren la base PostgreSQL test_cesfam_desarrollo.")
        super().setUpClass()

    def setUp(self):
        publicacion = patch("apps.turnos.services.publicar")
        self.publicacion = publicacion.start()
        self.addCleanup(publicacion.stop)
        self.administrador = Usuario.objects.create_user(username="admin_ventanillas_ficticio")
        self.administrador.user_permissions.add(Permission.objects.get(
            content_type__app_label="turnos", codename="configurar_ventanillas",
        ))
        self.operadores = [Usuario.objects.create_user(username=f"operador_ventanilla_ficticio_{i}") for i in (1, 2)]
        permiso = Permission.objects.get(content_type__app_label="turnos", codename="operar_turnos")
        for operador in self.operadores:
            operador.user_permissions.add(permiso)
        self.sin_permiso = Usuario.objects.create_user(username="sin_permiso_ficticio")
        self.ventanilla = Ventanilla.objects.create(numero=1, operador=self.operadores[0])
        self.otra = Ventanilla.objects.create(numero=2, habilitada=False)
        self.paciente = Paciente.objects.create(
            identificador_sintetico="SINT-000001", nombre_ficticio="Paciente ficticio de prueba",
        )
        EstadoCola.objects.create()

    def configurar(self, **cambios):
        argumentos = {
            "usuario": self.administrador, "ventanilla_id": self.ventanilla.pk,
            "habilitada": self.ventanilla.habilitada,
            "operador_id": self.ventanilla.operador_id,
            "motivo": "Ajuste ficticio de prueba",
        }
        argumentos.update(cambios)
        return configurar_ventanilla(**argumentos)

    def configuracion(self):
        return Ventanilla.objects.values("habilitada", "operador_id").get(pk=self.ventanilla.pk)

    def ocupar(self, estado=Estado.LLAMADO):
        emitir(self.paciente.identificador_sintetico, "GENERAL")
        turno, _ = llamar_siguiente(self.ventanilla.pk, self.operadores[0])
        if estado == Estado.EN_ATENCION:
            turno = cambiar_estado(turno.pk, self.operadores[0], estado)
        return turno

    def comprobar_ocupacion(self, estado):
        turno = self.ocupar(estado)
        configuracion = self.configuracion()
        datos_turno = Turno.objects.values().get(pk=turno.pk)
        operaciones = OperacionTurno.objects.count()
        for cambios in (
            {"habilitada": False},
            {"operador_id": self.operadores[1].pk},
            {"habilitada": False, "operador_id": None},
            {"operador_id": None},
        ):
            with self.subTest(cambios=cambios), self.assertRaises(ValidationError) as error:
                self.configurar(**cambios)
            self.assertEqual(error.exception.code, "ventanilla_ocupada")
            self.assertEqual(self.configuracion(), configuracion)
            self.assertEqual(Turno.objects.values().get(pk=turno.pk), datos_turno)
            self.assertEqual(OperacionTurno.objects.count(), operaciones)

    def paralelo(self, operaciones):
        barrera = Barrier(len(operaciones))

        def ejecutar(operacion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    operacion()
                    return "ok"
                except (ValidationError, PermissionDenied) as error:
                    return type(error).__name__
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(operaciones)) as ejecutor:
            return list(ejecutor.map(ejecutar, operaciones))

    def test_rechaza_anonimo_inactivo_y_usuarios_sin_permiso_administrativo(self):
        inactivo = Usuario.objects.create_user(username="admin_inactivo_ficticio", is_active=False)
        inactivo.user_permissions.set(self.administrador.user_permissions.all())
        original = self.configuracion()
        for usuario in (AnonymousUser(), inactivo, self.sin_permiso, self.operadores[0]):
            with self.subTest(usuario=usuario), self.assertRaises(PermissionDenied):
                self.configurar(usuario=usuario, habilitada=False)
        self.assertEqual(self.configuracion(), original)
        self.assertFalse(OperacionTurno.objects.exists())

    def test_sin_cambios_no_exige_motivo_ni_registra_operacion(self):
        resultado = self.configurar(motivo="")
        self.assertEqual(resultado.pk, self.ventanilla.pk)
        self.assertFalse(OperacionTurno.objects.exists())
        self.publicacion.assert_not_called()

    def test_ventanilla_inexistente_no_modifica_ni_audita(self):
        inexistente = max(self.ventanilla.pk, self.otra.pk) + 1
        with self.assertRaises(Ventanilla.DoesNotExist):
            self.configurar(ventanilla_id=inexistente, habilitada=False)
        self.assertEqual(self.configuracion(), {"habilitada": True, "operador_id": self.operadores[0].pk})
        self.assertFalse(OperacionTurno.objects.exists())

    def test_rechaza_tipos_e_identificadores_invalidos(self):
        for cambios in (
            {"habilitada": "false"}, {"habilitada": 0},
            {"ventanilla_id": True}, {"ventanilla_id": 0},
            {"operador_id": True}, {"operador_id": "1"}, {"operador_id": -1},
        ):
            with self.subTest(cambios=cambios), self.assertRaises(ValidationError):
                self.configurar(**cambios)
        self.assertFalse(OperacionTurno.objects.exists())

    def test_cambio_efectivo_requiere_motivo(self):
        original = self.configuracion()
        for motivo in (None, "", "  ", 1):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError):
                self.configurar(habilitada=False, motivo=motivo)
        self.assertEqual(self.configuracion(), original)
        self.assertFalse(OperacionTurno.objects.exists())

    def test_habilita_ventanilla_libre_con_operador_valido(self):
        resultado = self.configurar(ventanilla_id=self.otra.pk, operador_id=self.operadores[1].pk)
        self.assertTrue(resultado.habilitada)
        self.assertEqual(resultado.operador_id, self.operadores[1].pk)

    def test_no_habilita_ventanilla_sin_operador(self):
        with self.assertRaises(ValidationError):
            self.configurar(ventanilla_id=self.otra.pk, operador_id=None)
        self.otra.refresh_from_db()
        self.assertFalse(self.otra.habilitada)
        self.assertFalse(OperacionTurno.objects.exists())

    def test_deshabilita_ventanilla_libre_conservando_operador(self):
        resultado = self.configurar(habilitada=False)
        self.assertFalse(resultado.habilitada)
        self.assertEqual(resultado.operador_id, self.operadores[0].pk)

    def test_reasigna_ventanilla_libre(self):
        resultado = self.configurar(operador_id=self.operadores[1].pk)
        self.assertTrue(resultado.habilitada)
        self.assertEqual(resultado.operador_id, self.operadores[1].pk)

    def test_retira_operador_y_deshabilita_atomicamente(self):
        resultado = self.configurar(habilitada=False, operador_id=None)
        self.assertFalse(resultado.habilitada)
        self.assertIsNone(resultado.operador_id)

    def test_retirar_operador_sin_deshabilitar_es_rechazado(self):
        with self.assertRaises(ValidationError):
            self.configurar(operador_id=None)
        self.assertEqual(self.configuracion(), {"habilitada": True, "operador_id": self.operadores[0].pk})

    def test_rechaza_operador_inexistente(self):
        inexistente = Usuario.objects.order_by("-pk").first().pk + 1
        with self.assertRaises(ValidationError):
            self.configurar(operador_id=inexistente)
        self.assertFalse(OperacionTurno.objects.exists())

    def test_rechaza_operador_inactivo_o_sin_permiso_operativo(self):
        self.operadores[1].is_active = False
        self.operadores[1].save(update_fields=["is_active"])
        for operador in (self.operadores[1], self.sin_permiso, self.administrador):
            with self.subTest(operador=operador.pk), self.assertRaises(ValidationError):
                self.configurar(operador_id=operador.pk)
        self.assertFalse(OperacionTurno.objects.exists())

    def test_rechaza_operador_asignado_a_otra_ventanilla(self):
        self.otra.operador = self.operadores[1]
        self.otra.save(update_fields=["operador"])
        with self.assertRaises(ValidationError):
            self.configurar(operador_id=self.operadores[1].pk)
        self.assertFalse(OperacionTurno.objects.exists())

    def test_bloquea_modificaciones_con_turno_llamado(self):
        self.comprobar_ocupacion(Estado.LLAMADO)

    def test_bloquea_modificaciones_con_turno_en_atencion(self):
        self.comprobar_ocupacion(Estado.EN_ATENCION)

    def test_solicitud_sin_cambios_en_ambos_estados_ocupados_no_audita(self):
        turno = self.ocupar()
        for estado in (Estado.LLAMADO, Estado.EN_ATENCION):
            if estado == Estado.EN_ATENCION:
                cambiar_estado(turno.pk, self.operadores[0], estado)
            cantidad = OperacionTurno.objects.count()
            self.configurar(motivo=None)
            self.assertEqual(OperacionTurno.objects.count(), cantidad)

    def test_audita_una_modificacion_con_actor_y_configuracion_completa(self):
        self.configurar(habilitada=False, motivo="  Cierre ficticio de puesto  ")
        operacion = OperacionTurno.objects.get()
        self.assertIsNone(operacion.turno_id)
        self.assertEqual(operacion.usuario_id, self.administrador.pk)
        self.assertEqual(operacion.accion, "VENTANILLA_CONFIGURADA")
        self.assertEqual(operacion.detalles, {
            "entidad": "ventanilla", "ventanilla_id": self.ventanilla.pk,
            "numero": 1,
            "anteriores": {"habilitada": True, "operador_id": self.operadores[0].pk},
            "nuevos": {"habilitada": False, "operador_id": self.operadores[0].pk},
            "motivo": "Cierre ficticio de puesto",
        })
        self.publicacion.assert_not_called()

    def test_reasignacion_posterior_preserva_autoria_e_historial_del_turno(self):
        turno = self.ocupar(Estado.EN_ATENCION)
        cambiar_estado(turno.pk, self.operadores[0], Estado.ATENDIDO)
        datos_turno = Turno.objects.values().get(pk=turno.pk)
        historial = list(turno.operaciones.values())
        self.configurar(operador_id=self.operadores[1].pk)
        self.assertEqual(Turno.objects.values().get(pk=turno.pk), datos_turno)
        self.assertEqual(list(turno.operaciones.values()), historial)

    def test_error_de_auditoria_revierte_configuracion(self):
        original = self.configuracion()
        with patch("apps.turnos.services.registrar", side_effect=RuntimeError("Fallo ficticio de auditoría")):
            with self.assertRaises(RuntimeError):
                self.configurar(habilitada=False)
        self.assertEqual(self.configuracion(), original)
        self.assertFalse(OperacionTurno.objects.exists())

    def test_rollback_externo_revierte_configuracion_y_bitacora(self):
        original = self.configuracion()
        with self.assertRaises(RuntimeError), transaction.atomic():
            self.configurar(habilitada=False)
            self.assertEqual(OperacionTurno.objects.count(), 1)
            raise RuntimeError("Rollback ficticio")
        self.assertEqual(self.configuracion(), original)
        self.assertFalse(OperacionTurno.objects.exists())

    def test_ocupacion_deshabilitada_externamente_no_se_repara(self):
        turno = self.ocupar()
        Ventanilla.objects.filter(pk=self.ventanilla.pk).update(habilitada=False)
        cantidad = OperacionTurno.objects.count()
        for operacion in (
            lambda: self.configurar(),
            lambda: rellamar(turno.pk, self.operadores[0]),
            lambda: cambiar_estado(turno.pk, self.operadores[0], Estado.EN_ATENCION),
            lambda: cambiar_estado(turno.pk, self.operadores[0], Estado.AUSENTE),
            lambda: llamar_siguiente(self.ventanilla.pk, self.operadores[0]),
        ):
            with self.assertRaises((ValidationError, PermissionDenied)):
                operacion()
        turno.refresh_from_db()
        self.assertEqual(turno.estado, Estado.LLAMADO)
        self.assertFalse(self.configuracion()["habilitada"])
        self.assertEqual(OperacionTurno.objects.count(), cantidad)

    def test_ocupacion_reasignada_externamente_no_transfiere_autoria(self):
        turno = self.ocupar(Estado.EN_ATENCION)
        Ventanilla.objects.filter(pk=self.ventanilla.pk).update(operador=self.operadores[1])
        cantidad = OperacionTurno.objects.count()
        for operacion in (
            lambda: self.configurar(operador_id=self.operadores[1].pk),
            lambda: cambiar_estado(turno.pk, self.operadores[0], Estado.ATENDIDO),
            lambda: cambiar_estado(turno.pk, self.operadores[1], Estado.ATENDIDO),
            lambda: llamar_siguiente(self.ventanilla.pk, self.operadores[1]),
        ):
            with self.assertRaises(ValidationError):
                operacion()
        turno.refresh_from_db()
        self.assertEqual(turno.estado, Estado.EN_ATENCION)
        self.assertEqual(turno.operador_id, self.operadores[0].pk)
        self.assertEqual(OperacionTurno.objects.count(), cantidad)

    def test_revalida_referencia_de_ventanilla_tras_adquirir_bloqueos(self):
        turno = self.ocupar()
        cantidad = OperacionTurno.objects.count()
        with patch("apps.turnos.services.Turno.objects.values_list") as referencia:
            referencia.return_value.get.return_value = self.otra.pk
            with self.assertRaises(ValidationError) as error:
                rellamar(turno.pk, self.operadores[0])
        self.assertEqual(error.exception.code, "ventanilla_inconsistente")
        self.assertEqual(OperacionTurno.objects.count(), cantidad)

    def test_llamado_y_deshabilitacion_simultaneos_solo_confirman_uno(self):
        turno, _ = emitir(self.paciente.identificador_sintetico, "GENERAL")
        resultados = self.paralelo([
            lambda: llamar_siguiente(self.ventanilla.pk, Usuario.objects.get(pk=self.operadores[0].pk)),
            lambda: self.configurar(usuario=Usuario.objects.get(pk=self.administrador.pk), habilitada=False),
        ])
        self.assertEqual(resultados.count("ok"), 1)
        turno.refresh_from_db()
        self.assertEqual(
            (self.configuracion()["habilitada"], turno.estado),
            (True, Estado.LLAMADO) if resultados[0] == "ok" else (False, Estado.PENDIENTE),
        )
        self.assertEqual(OperacionTurno.objects.filter(accion="VENTANILLA_CONFIGURADA").count(), int(resultados[1] == "ok"))

    def test_llamado_y_reasignacion_simultaneos_preservan_operador(self):
        turno, _ = emitir(self.paciente.identificador_sintetico, "GENERAL")
        resultados = self.paralelo([
            lambda: llamar_siguiente(self.ventanilla.pk, Usuario.objects.get(pk=self.operadores[0].pk)),
            lambda: self.configurar(usuario=Usuario.objects.get(pk=self.administrador.pk), operador_id=self.operadores[1].pk),
        ])
        self.assertEqual(resultados.count("ok"), 1)
        turno.refresh_from_db()
        if resultados[0] == "ok":
            self.assertEqual(turno.estado, Estado.LLAMADO)
            self.assertEqual(turno.operador_id, self.operadores[0].pk)
            self.assertEqual(self.configuracion()["operador_id"], self.operadores[0].pk)
        else:
            self.assertEqual(turno.estado, Estado.PENDIENTE)
            self.assertIsNone(turno.operador_id)
            self.assertEqual(self.configuracion()["operador_id"], self.operadores[1].pk)

    def test_cierre_y_reasignacion_simultaneos_conservan_autoria(self):
        turno = self.ocupar(Estado.EN_ATENCION)
        resultados = self.paralelo([
            lambda: cambiar_estado(turno.pk, Usuario.objects.get(pk=self.operadores[0].pk), Estado.ATENDIDO),
            lambda: self.configurar(usuario=Usuario.objects.get(pk=self.administrador.pk), operador_id=self.operadores[1].pk),
        ])
        self.assertEqual(resultados[0], "ok")
        self.assertIn(resultados[1], ("ok", "ValidationError"))
        turno.refresh_from_db()
        self.assertEqual(turno.estado, Estado.ATENDIDO)
        self.assertEqual(turno.operador_id, self.operadores[0].pk)
        esperado = self.operadores[1].pk if resultados[1] == "ok" else self.operadores[0].pk
        self.assertEqual(self.configuracion()["operador_id"], esperado)

    def test_asignaciones_simultaneas_no_comparten_operador_incluso_sin_cola_inicial(self):
        EstadoCola.objects.all().delete()
        resultados = self.paralelo([
            lambda: self.configurar(usuario=Usuario.objects.get(pk=self.administrador.pk), operador_id=self.operadores[1].pk),
            lambda: self.configurar(usuario=Usuario.objects.get(pk=self.administrador.pk), ventanilla_id=self.otra.pk, operador_id=self.operadores[1].pk),
        ])
        self.assertCountEqual(resultados, ["ok", "ValidationError"])
        self.assertEqual(Ventanilla.objects.filter(operador=self.operadores[1]).count(), 1)
        self.assertEqual(OperacionTurno.objects.filter(accion="VENTANILLA_CONFIGURADA").count(), 1)
        self.assertEqual(EstadoCola.objects.count(), 1)
