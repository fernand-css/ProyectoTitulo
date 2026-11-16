"""Carreras del planificador con barrera y conexiones SQLite separadas."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from turnosapp.cola import procesar_pendiente
from turnosapp.models import EventoTurno, PendienteSeleccion, Turno
from .datos_cola import DatosCola


class ConcurrenciaColaTests(DatosCola, TransactionTestCase):
    def competir(self, pendientes):
        barrera = Barrier(len(pendientes))
        def ejecutar(pk):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return procesar_pendiente(pk)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(pendientes)) as pool:
            return list(pool.map(ejecutar, pendientes))

    def test_tres_procesadores_mismo_pendiente_un_llamado(self):
        self.activar()
        self.turno()
        pendiente = self.pendiente()
        resultados = self.competir([pendiente.pk] * 3)
        self.assertEqual(sum(resultados), 1)
        self.assertEqual(EventoTurno.objects.count(), 1)
        self.assertEqual(Turno.objects.filter(estado="llamado").count(), 1)

    def test_pendientes_distintos_disputan_mismo_turno(self):
        self.activar(1)
        self.activar(2)
        self.turno()
        self.assertEqual(sum(self.competir([self.pendiente().pk for _ in range(3)])), 1)
        self.assertEqual(EventoTurno.objects.count(), 1)
        self.assertFalse(PendienteSeleccion.objects.exclude(estado="procesado").exists())

    def test_tres_ventanillas_y_procesadores_comparten_cursor_sin_duplicados(self):
        for numero in range(1, 4):
            self.activar(numero)
        for tipo in ("preferencial", "preferencial", "cronicos", "general"):
            self.turno(tipo)
        self.assertEqual(sum(self.competir([self.pendiente().pk for _ in range(3)])), 3)
        llamados = list(Turno.objects.filter(estado="llamado"))
        self.assertEqual(len({t.ventanilla_id for t in llamados}), 3)
        self.assertEqual(len({t.pk for t in llamados}), 3)
        self.assertEqual(sorted(t.tipo_atencion for t in llamados), ["cronicos", "preferencial", "preferencial"])
        self.assertEqual(EventoTurno.objects.count(), 3)


TODOS = ("preferencial", "cronicos", "general", "urgencia")


class ConcurrenciaUrgenciaTests(DatosCola, TransactionTestCase):
    """Enmienda RF-05-13: tres escenarios de carga con la fila U primero."""

    competir = ConcurrenciaColaTests.competir

    def test_tres_procesadores_una_urgencia_un_solo_llamado(self):
        self.activar(1, TODOS)
        self.activar(2, TODOS)
        urgente = self.turno("urgencia")
        self.turno("preferencial", espera=2000)
        self.assertEqual(sum(self.competir([self.pendiente().pk for _ in range(3)])), 2)
        urgente.refresh_from_db()
        self.assertEqual(urgente.estado, "llamado")
        self.assertEqual(EventoTurno.objects.filter(turno=urgente).count(), 1)
        self.assertEqual(len(set(Turno.objects.filter(estado="llamado").values_list("ventanilla_id", flat=True))), 2)

    def test_tres_ventanillas_urgencias_primero_sin_duplicados(self):
        for numero in range(1, 4):
            self.activar(numero, TODOS)
        for tipo in ("general", "preferencial", "cronicos", "preferencial"):
            self.turno(tipo, espera=1000)
        urgentes = {self.turno("urgencia").pk for _ in range(2)}
        self.assertEqual(sum(self.competir([self.pendiente().pk for _ in range(3)])), 3)
        llamados = list(Turno.objects.filter(estado="llamado"))
        self.assertEqual(len({t.ventanilla_id for t in llamados}), 3)
        self.assertTrue(urgentes <= {t.pk for t in llamados})
        self.assertEqual(EventoTurno.objects.count(), 3)

    def test_urgencia_compite_con_ventanilla_incompatible(self):
        self.activar(1, ("general",))
        con_u = self.activar(2, TODOS)
        self.activar(3, ("preferencial",))
        urgente = self.turno("urgencia")
        self.turno("general")
        self.turno("preferencial")
        self.assertEqual(sum(self.competir([self.pendiente().pk for _ in range(3)])), 3)
        urgente.refresh_from_db()
        self.assertEqual(urgente.ventanilla_id, con_u.pk)
        self.assertEqual(Turno.objects.filter(estado="llamado").count(), 3)
        self.assertEqual(EventoTurno.objects.count(), 3)


class LlaveDelDiaTests(TransactionTestCase):
    """Diagnóstico del 2026-11-15 (spec 08): quien espera la cola del día sigue cuando el otro confirma.

    Antes, `bloquear_cola` comparaba la versión leída: en PostgreSQL, quien había esperado el bloqueo de la fila
    encontraba la versión cambiada y fallaba con `ConflictoCola`. Con transacciones seguidas (un lote de entregas)
    el tótem agotaba así sus reintentos.
    """

    def test_quien_espera_la_cola_sigue_y_ve_la_version_del_otro(self):
        import time
        from threading import Event
        from django.db import connection, transaction
        from django.utils import timezone
        from turnosapp.cola import bloquear_cola
        from turnosapp.models import EstadoColaDiaria

        if connection.vendor != "postgresql":
            self.skipTest("SQLite bloquea toda la base: no hay espera por fila que probar.")
        hoy = timezone.localdate()
        inicial = EstadoColaDiaria.objects.create(fecha=hoy).version
        tomada = Event()

        def primero():
            close_old_connections()
            try:
                with transaction.atomic():
                    bloquear_cola(hoy)
                    tomada.set()
                    time.sleep(0.4)  # retiene la fila sin confirmar
                return "confirmado"
            finally:
                connections.close_all()

        def segundo():
            close_old_connections()
            try:
                tomada.wait(timeout=10)
                inicio = time.monotonic()
                with transaction.atomic():
                    estado = bloquear_cola(hoy)  # lee la versión antigua y espera la fila
                    return estado.version, time.monotonic() - inicio
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            uno, dos = pool.submit(primero), pool.submit(segundo)
            self.assertEqual(uno.result(timeout=20), "confirmado")
            version, espera = dos.result(timeout=20)
        self.assertGreaterEqual(espera, 0.2)  # de verdad esperó al primero
        self.assertEqual(version, inicial + 2)  # y ve la escritura confirmada del primero
        self.assertEqual(EstadoColaDiaria.objects.get(fecha=hoy).version, inicial + 2)
