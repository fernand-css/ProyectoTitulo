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
