"""Integración pendiente de ejecución: exige PostgreSQL y migraciones autorizadas."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from apps.pacientes.models import Paciente
from apps.turnos.models import Categoria, Estado, EstadoCola, OperacionTurno, Turno, Ventanilla
from apps.turnos.services import cambiar_estado, configurar_pesos, emitir, llamar_siguiente, rellamar
from apps.usuarios.models import Usuario
from apps.usuarios.roles import ADMINISTRADOR, FUNCIONARIO, QF, TERRENO


class ServicioPostgreSQLTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        if connection.vendor != "postgresql":
            raise RuntimeError("Estas pruebas requieren PostgreSQL; no se sustituyen por SQLite.")
        super().setUpClass()

    def setUp(self):
        self.publicacion = patch("apps.turnos.services.publicar").start()
        self.addCleanup(patch.stopall)
        self.pacientes = [Paciente.objects.create(
            identificador_sintetico=f"SINT-{i:06d}",
            nombre_ficticio=f"Paciente ficticio {i:06d}",
        ) for i in range(1, 21)]
        self.operadores = [Usuario.objects.create_user(username=f"operador_ficticio_{i}") for i in (1, 2)]
        permiso = Permission.objects.get(content_type__app_label="turnos", codename="operar_turnos")
        for operador in self.operadores:
            operador.user_permissions.add(permiso)
        self.ventanillas = [Ventanilla.objects.create(numero=i + 1, operador=operador) for i, operador in enumerate(self.operadores)]
        self.administrador = Usuario.objects.create_user(username="administrador_ficticio")
        self.administrador.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="turnos", codename__in=("cancelar_turnos", "configurar_cola"),
        ))
        self.terreno = Usuario.objects.create_user(username="terreno_ficticio")
        EstadoCola.objects.create()

    def emitir_para(self, indice, categoria=Categoria.GENERAL):
        return emitir(self.pacientes[indice].identificador_sintetico, categoria)[0]

    def paralelo(self, operaciones):
        barrera = Barrier(len(operaciones))

        def ejecutar(operacion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return operacion()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(operaciones)) as ejecutor:
            return list(ejecutor.map(ejecutar, operaciones))

    def test_numeracion_por_categoria_y_jornada(self):
        with patch("apps.turnos.services.timezone.localdate", return_value=date(2026, 11, 4)):
            primero = self.emitir_para(0)
            segundo = self.emitir_para(1)
            preferente = self.emitir_para(2, Categoria.PREFERENCIAL)
        with patch("apps.turnos.services.timezone.localdate", return_value=date(2026, 11, 5)):
            siguiente_jornada = self.emitir_para(3)
        self.assertEqual([x.numero_visible for x in (primero, segundo, preferente, siguiente_jornada)], ["G-001", "G-002", "P-001", "G-001"])
        self.assertNotEqual(primero.pk, siguiente_jornada.pk)

    def test_paciente_activo_reutiliza_turno_sin_cambiar_categoria(self):
        primero = self.emitir_para(0)
        repetido, creado = emitir(self.pacientes[0].identificador_sintetico, Categoria.PREFERENCIAL)
        self.assertFalse(creado)
        self.assertEqual(repetido.pk, primero.pk)
        self.assertEqual(repetido.categoria, Categoria.GENERAL)

    def test_flujo_completo_rellamado_y_bitacora(self):
        turno = self.emitir_para(0)
        llamado, nuevo = llamar_siguiente(self.ventanillas[0].pk, self.operadores[0])
        self.assertTrue(nuevo)
        self.assertEqual(llamado.pk, turno.pk)
        repetido = rellamar(turno.pk, self.operadores[0])
        self.assertEqual(repetido.numero_visible, turno.numero_visible)
        self.assertEqual(repetido.estado, Estado.LLAMADO)
        cambiar_estado(turno.pk, self.operadores[0], Estado.EN_ATENCION)
        terminado = cambiar_estado(turno.pk, self.operadores[0], Estado.ATENDIDO)
        self.assertIsNotNone(terminado.cierre)
        self.assertEqual(list(terminado.operaciones.values_list("accion", flat=True)), ["EMITIDO", "LLAMADO", "RELLAMADO", "EN_ATENCION", "ATENDIDO"])

    def test_fifo_y_dos_a_uno(self):
        generales = [self.emitir_para(i) for i in (0, 1, 2)]
        preferentes = [self.emitir_para(i, Categoria.PREFERENCIAL) for i in (3, 4)]
        # Empate de fecha dentro de GENERAL: la PK mantiene el desempate FIFO.
        Turno.objects.filter(pk__in=[t.pk for t in generales]).update(emitido=timezone.now() - timedelta(seconds=10))
        llamados = []
        for _ in range(5):
            turno, _ = llamar_siguiente(self.ventanillas[0].pk, self.operadores[0])
            llamados.append(turno.pk)
            cambiar_estado(turno.pk, self.operadores[0], Estado.AUSENTE)
        self.assertEqual(llamados, [generales[0].pk, generales[1].pk, preferentes[0].pk, generales[2].pk, preferentes[1].pk])

    def test_ausencia_manual_sin_umbral_y_cancelacion(self):
        turno = self.emitir_para(0)
        llamar_siguiente(self.ventanillas[0].pk, self.operadores[0])
        self.assertEqual(cambiar_estado(turno.pk, self.operadores[0], Estado.AUSENTE).estado, Estado.AUSENTE)
        pendiente = self.emitir_para(1)
        self.assertEqual(cambiar_estado(pendiente.pk, self.administrador, Estado.CANCELADO).estado, Estado.CANCELADO)

    def test_terreno_no_opera_y_operador_no_cancela(self):
        turno = self.emitir_para(0)
        with self.assertRaises(PermissionDenied):
            llamar_siguiente(self.ventanillas[0].pk, self.terreno)
        with self.assertRaises(PermissionDenied):
            cambiar_estado(turno.pk, self.operadores[0], Estado.CANCELADO)

    def test_grupos_aprobados_y_terreno_reservado(self):
        call_command("inicializar_roles", verbosity=0)
        for nombre in (FUNCIONARIO, QF):
            grupo = Group.objects.get(name=nombre)
            self.assertEqual(set(grupo.permissions.values_list("codename", flat=True)), {"operar_turnos"})
        self.assertFalse(Group.objects.get(name=TERRENO).permissions.exists())
        administrador = Group.objects.get(name=ADMINISTRADOR)
        self.assertTrue(administrador.permissions.filter(codename="configurar_cola").exists())
        self.assertFalse(administrador.permissions.filter(codename="operar_turnos").exists())

    def test_no_se_puede_operar_otra_ventanilla_o_una_deshabilitada(self):
        self.emitir_para(0)
        with self.assertRaises(PermissionDenied):
            llamar_siguiente(self.ventanillas[0].pk, self.operadores[1])
        Ventanilla.objects.filter(pk=self.ventanillas[0].pk).update(habilitada=False)
        with self.assertRaises(PermissionDenied):
            llamar_siguiente(self.ventanillas[0].pk, self.operadores[0])

    def test_no_se_reabren_terminales_ni_se_saltan_estados(self):
        turno = self.emitir_para(0)
        with self.assertRaises(ValidationError):
            cambiar_estado(turno.pk, self.operadores[0], Estado.ATENDIDO)
        cambiar_estado(turno.pk, self.administrador, Estado.CANCELADO)
        with self.assertRaises(ValidationError):
            cambiar_estado(turno.pk, self.administrador, Estado.CANCELADO)

    def test_pesos_invalidos_no_modifican_configuracion(self):
        for invalido in (0, -1, 101, True):
            with self.assertRaises(ValidationError):
                configurar_pesos(self.administrador, invalido, 1)
        cola = EstadoCola.objects.get()
        self.assertEqual((cola.peso_general, cola.peso_preferencial), (2, 1))
        configurar_pesos(self.administrador, 3, 2)
        self.assertEqual(OperacionTurno.objects.filter(accion="PESOS_CONFIGURADOS").count(), 1)

    def test_restricciones_impiden_doble_activo_y_estado_incoherente(self):
        turno = self.emitir_para(0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Turno.objects.create(paciente=turno.paciente, fecha_jornada=turno.fecha_jornada, categoria=Categoria.PREFERENCIAL, correlativo=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Turno.objects.filter(pk=turno.pk).update(estado=Estado.ATENDIDO)

    def test_publicacion_solo_despues_del_commit_y_nunca_en_rollback(self):
        with transaction.atomic():
            self.emitir_para(0)
            self.assertFalse(self.publicacion.called)
        self.assertEqual(self.publicacion.call_count, 1)
        self.publicacion.reset_mock()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.emitir_para(1)
                raise RuntimeError("Fallo simulado para rollback")
        self.assertFalse(self.publicacion.called)
        self.assertEqual(Turno.objects.count(), 1)

    def test_emisiones_simultaneas_mismo_paciente(self):
        operaciones = [lambda: emitir(self.pacientes[0].identificador_sintetico, Categoria.GENERAL)[0].pk for _ in range(4)]
        self.assertEqual(len(set(self.paralelo(operaciones))), 1)
        self.assertEqual(Turno.objects.count(), 1)

    def test_emisiones_simultaneas_distintos_pacientes(self):
        resultados = self.paralelo([
            lambda i=i: self.emitir_para(i).correlativo for i in range(6)
        ])
        self.assertEqual(sorted(resultados), list(range(1, 7)))

    def test_llamados_simultaneos_distintas_ventanillas(self):
        for i in range(3):
            self.emitir_para(i)
        ids = self.paralelo([
            lambda i=i: llamar_siguiente(self.ventanillas[i].pk, self.operadores[i])[0].pk
            for i in range(2)
        ])
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(Turno.objects.filter(estado=Estado.LLAMADO).count(), 2)

    def test_llamados_simultaneos_misma_ventanilla(self):
        self.emitir_para(0)
        self.emitir_para(1)
        ids = self.paralelo([
            lambda: llamar_siguiente(self.ventanillas[0].pk, self.operadores[0])[0].pk
            for _ in range(2)
        ])
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(Turno.objects.filter(estado=Estado.LLAMADO).count(), 1)
