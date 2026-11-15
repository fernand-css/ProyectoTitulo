"""Spec 10, RF-10-06: carreras reales con barrera, hilos y conexiones independientes."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from turnosapp import atencion
from turnosapp.cola import procesar_pendiente
from turnosapp.models import CierreAtencion, ContadorTurnosDiario, EventoTurno, OcupacionVentanilla, Turno, Ventanilla
from .datos_cola import DatosCola

TODOS = ("preferencial", "general", "cronicos", "urgencia")


class ConcurrenciaPersonalTests(DatosCola, TransactionTestCase):
    def activar(self, numero=1, tipos=TODOS):
        ventanilla = super().activar(numero, tipos)
        OcupacionVentanilla.objects.filter(ventanilla=ventanilla).update(apertura=self.ahora - timedelta(hours=1))
        return ventanilla

    def competir(self, funciones):
        barrera = Barrier(len(funciones))

        def ejecutar(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    return funcion()
                except (ValidationError, PermissionDenied) as error:
                    return error
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(funciones)) as pool:
            return list(pool.map(ejecutar, funciones))

    def comprobar_invariantes(self):
        llamados = list(Turno.objects.filter(estado="llamado"))
        self.assertEqual(len({t.ventanilla_id for t in llamados}), len(llamados))
        self.assertFalse(Turno.objects.filter(estado="llamado", ventanilla__habilitada=False).exists())
        for letra in ("P", "G", "C", "U"):
            numeros = list(Turno.objects.filter(fecha=self.fecha, letra=letra).values_list("numero", flat=True))
            self.assertEqual(len(numeros), len(set(numeros)))

    def test_termino_de_turno_frente_al_cierre_de_la_atencion(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                Ventanilla.objects.update(habilitada=True)
                ventanilla = self.activar(1)
                turno = self.turno("general", espera=60)
                procesar_pendiente(self.pendiente().pk)
                turno.refresh_from_db()
                self.assertEqual(turno.estado, "llamado")
                resultados = self.competir([
                    lambda: atencion.terminar_turno_ventanilla(self.personal["qf"], ventanilla.pk, uuid.uuid4(), confirmar=True),
                    lambda: atencion.finalizar_atencion(self.personal["tecnico"], turno.pk, uuid.uuid4(), recetas_entregadas=[]),
                ])
                turno.refresh_from_db()
                ventanilla.refresh_from_db()
                self.assertFalse(isinstance(resultados[0], Exception), resultados[0])
                self.assertEqual((ventanilla.habilitada, ventanilla.operador_id), (False, None))
                cierres = CierreAtencion.objects.filter(turno=turno).count()
                if isinstance(resultados[1], Exception):
                    # Ganó el término: el turno volvió a la fila y no hubo cierre.
                    self.assertEqual((turno.estado, cierres), ("esperando", 0))
                    self.assertEqual(EventoTurno.objects.filter(turno=turno, accion="devuelto_a_cola").count(), 1)
                else:
                    # Ganó el cierre: la ventanilla se terminó ya sin paciente llamado.
                    self.assertEqual((turno.estado, cierres), ("cerrado_sin_entrega", 1))
                    self.assertFalse(EventoTurno.objects.filter(turno=turno, accion="devuelto_a_cola").exists())
                self.comprobar_invariantes()
                # Siguiente vuelta limpia: nada queda esperando ni ocupado.
                Turno.objects.filter(estado="esperando").update(estado="sin_atencion_cierre", cerrado_en=self.ahora)

    def test_urgencia_frente_a_la_seleccion_automatica(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                Turno.objects.filter(estado="llamado").update(estado="atendido", ventanilla=None, operador=None, cerrado_en=self.ahora)
                if not Ventanilla.objects.filter(numero=1, operador__isnull=False).exists():
                    self.activar(1)
                turno = self.turno("general", espera=30)
                anterior = turno.codigo
                pendiente = self.pendiente()
                resultados = self.competir([
                    lambda: atencion.marcar_urgencia(self.personal["tecnico"], turno.pk, uuid.uuid4()),
                    lambda: procesar_pendiente(pendiente.pk),
                ])
                turno.refresh_from_db()
                urgencias = EventoTurno.objects.filter(turno=turno, accion="urgencia").count()
                if isinstance(resultados[0], Exception):
                    # Se llamó primero con su letra anterior; la urgencia se rechazó sin consumir número.
                    self.assertEqual((turno.estado, turno.codigo, urgencias), ("llamado", anterior, 0))
                else:
                    self.assertEqual((turno.letra, urgencias), ("U", 1))
                    self.assertIn(turno.estado, ("esperando", "llamado"))
                self.assertLessEqual(EventoTurno.objects.filter(turno=turno, accion="llamado").count(), 1)
                usados = Turno.objects.filter(fecha=self.fecha, letra="U").count()
                contador = ContadorTurnosDiario.objects.filter(fecha=self.fecha, letra="U").first()
                self.assertEqual(contador.ultimo_numero if contador else 0, usados)
                self.comprobar_invariantes()

    def test_tres_urgencias_simultaneas_reciben_numeros_distintos_y_consecutivos(self):
        turnos = [self.turno(tipo) for tipo in ("general", "preferencial", "cronicos")]
        actores = [self.personal["tecnico"], self.personal["qf"], self.personal["admin"]]
        resultados = self.competir([
            lambda t=t, a=a: atencion.marcar_urgencia(a, t.pk, uuid.uuid4()) for t, a in zip(turnos, actores)
        ])
        self.assertFalse(any(isinstance(r, Exception) for r in resultados), resultados)
        self.assertEqual(sorted(r["codigo"] for r in resultados), ["U-001", "U-002", "U-003"])
        self.assertEqual(ContadorTurnosDiario.objects.get(fecha=self.fecha, letra="U").ultimo_numero, 3)
        self.assertEqual(EventoTurno.objects.filter(accion="urgencia").count(), 3)
        self.comprobar_invariantes()
