"""Acciones operativas reales compitiendo con selección y emisión."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from recetasapp.models import Receta
from turnosapp.atencion import ocupar_ventanilla, pausar_ventanilla, configurar_ventanilla, marcar_ausente, reincorporar, rellamar
from turnosapp.cola import procesar_pendiente
from turnosapp.models import ContadorTurnosDiario, EventoTurno, OcupacionVentanilla, Turno, Ventanilla
from turnosapp.services import emitir_turno
from .datos_cola import DatosCola


class ConcurrenciaAtencionTests(DatosCola, TransactionTestCase):
    def competir(self, operaciones):
        barrera = Barrier(len(operaciones))
        def ejecutar(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    return funcion()
                except ValidationError:
                    return None  # Conflicto de negocio esperado, no error de base ignorado.
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(operaciones)) as pool:
            return list(pool.map(ejecutar, operaciones))

    def test_dos_operadores_disputan_una_ventanilla(self):
        vent = Ventanilla.objects.get(numero=1)
        resultados = self.competir([
            lambda: ocupar_ventanilla(self.personal["tecnico"], vent.pk, uuid.uuid4()),
            lambda: ocupar_ventanilla(self.personal["admin"], vent.pk, uuid.uuid4()),
        ])
        self.assertEqual(sum(r is not None for r in resultados), 1)
        self.assertEqual(OcupacionVentanilla.objects.filter(cierre__isnull=True).count(), 1)

    def test_un_operador_no_ocupa_dos_ventanillas_simultaneas(self):
        ids = list(Ventanilla.objects.order_by("numero").values_list("pk", flat=True)[:2])
        self.competir([lambda pk=pk: ocupar_ventanilla(self.personal["tecnico"], pk, uuid.uuid4()) for pk in ids])
        self.assertEqual(Ventanilla.objects.filter(operador=self.personal["tecnico"]).count(), 1)
        self.assertEqual(OcupacionVentanilla.objects.filter(cierre__isnull=True).count(), 1)

    def test_pausa_frente_a_seleccion_no_permita_otro_llamado(self):
        vent = self.activar()
        self.turno()
        self.turno()
        pendiente = self.pendiente()
        self.competir([
            lambda: procesar_pendiente(pendiente.pk),
            lambda: pausar_ventanilla(self.personal["tecnico"], vent.pk, uuid.uuid4()),
        ])
        vent.refresh_from_db()
        self.assertFalse(vent.automatico)
        self.assertLessEqual(Turno.objects.filter(estado="llamado").count(), 1)
        eventos = EventoTurno.objects.count()
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(EventoTurno.objects.count(), eventos)

    def test_deshabilitar_frente_a_seleccion_conserva_como_maximo_llamado_previo(self):
        vent = self.activar()
        self.turno()
        self.turno()
        pendiente = self.pendiente()
        self.competir([
            lambda: procesar_pendiente(pendiente.pk),
            lambda: configurar_ventanilla(self.personal["qf"], vent.pk, uuid.uuid4(), habilitada=False, confirmar=True),
        ])
        vent.refresh_from_db()
        self.assertFalse(vent.habilitada)
        self.assertFalse(vent.automatico)
        self.assertLessEqual(Turno.objects.filter(estado="llamado").count(), 1)
        eventos = EventoTurno.objects.count()
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(EventoTurno.objects.count(), eventos)

    def test_emision_y_reincorporacion_no_crean_dos_activos(self):
        turno = self.turno()
        Turno.objects.filter(pk=turno.pk).update(estado="ausente", cerrado_en=self.ahora)
        ContadorTurnosDiario.objects.create(fecha=self.fecha, ultimo_numero=turno.numero)
        Receta.objects.create(paciente=turno.paciente, codigo="CARRERA-RETORNO-DEMO", fecha_inicio=self.fecha,
            fecha_fin_exclusiva=self.fecha + timedelta(days=30), vigencia_meses=1, max_entregas=3)
        self.competir([
            lambda: emitir_turno(turno.paciente.rut, uuid.uuid4()),
            lambda: reincorporar(self.personal["tecnico"], turno.pk, uuid.uuid4()),
        ])
        self.assertEqual(Turno.objects.filter(paciente=turno.paciente, estado__in=["esperando", "llamado"]).count(), 1)
        self.assertLessEqual(Turno.objects.count(), 2)

    def test_tres_reenvios_de_rellamado_generan_un_evento(self):
        vent = self.activar()
        turno = self.turno()
        procesar_pendiente(self.pendiente().pk)
        op = uuid.uuid4()
        resultados = self.competir([lambda: rellamar(self.personal["tecnico"], turno.pk, op)] * 3)
        self.assertTrue(all(r == resultados[0] for r in resultados))
        self.assertEqual(EventoTurno.objects.filter(accion="rellamado").count(), 1)
        self.assertEqual(Turno.objects.filter(estado="llamado", ventanilla=vent).count(), 1)
