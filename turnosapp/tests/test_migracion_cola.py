"""Actualización desde el 04 sin inventar asociaciones o alterar números."""
import uuid
from datetime import date, timedelta
from random import Random

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from coreapp.utils.sinteticos import generar_ruts


class MigracionColaTests(TransactionTestCase):
    def test_preserva_turno_entrada_y_entregas_previas_al_05(self):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        anteriores = [n for n in finales if n[0] not in {"turnosapp", "recetasapp"}] + [
            ("recetasapp", "0002_resultadofilaimportacion_pacientes_actualizados_and_more"),
            ("turnosapp", "0001_initial"),
        ]
        try:
            executor.migrate(anteriores)
            apps = executor.loader.project_state(anteriores).apps
            paciente = apps.get_model("recetasapp", "Paciente").objects.create(
                rut=generar_ruts(1, Random(505))[0], nombres="Paciente sintético", apellidos="Migración",
                fecha_nacimiento=date(1970, 1, 1),
            )
            receta = apps.get_model("recetasapp", "Receta").objects.create(
                paciente=paciente, codigo="MIGRACION-COLA-DEMO", fecha_inicio=date(2026, 1, 1),
                fecha_fin_exclusiva=date(2027, 1, 1), vigencia_meses=12, max_entregas=6, entregas_completadas=1,
            )
            entrega = apps.get_model("recetasapp", "EntregaReceta").objects.create(receta=receta, numero=1, operacion_id=uuid.uuid4())
            operacion = uuid.uuid4()
            TurnoAnterior = apps.get_model("turnosapp", "Turno")
            turno = TurnoAnterior.objects.create(paciente=paciente, fecha=date(2026, 11, 1), numero=37, tipo_atencion="general", operacion_id=operacion)
            instante = timezone.now() - timedelta(days=2)
            TurnoAnterior.objects.filter(pk=turno.pk).update(creado_en=instante)
            apps.get_model("turnosapp", "TurnoReceta").objects.create(turno=turno, receta=receta)
            for _ in range(2):
                actual = MigrationExecutor(connection)
                actual.migrate(finales)
                nuevas = actual.loader.project_state(finales).apps
                migrado = nuevas.get_model("turnosapp", "Turno").objects.get(pk=turno.pk)
                self.assertEqual((migrado.numero, migrado.fecha, migrado.operacion_id, migrado.estado), (37, date(2026, 11, 1), operacion, "esperando"))
                self.assertEqual(migrado.entrada_cola, instante)
                self.assertEqual(nuevas.get_model("recetasapp", "Receta").objects.get(pk=receta.pk).entregas_completadas, 1)
                self.assertIsNone(nuevas.get_model("recetasapp", "EntregaReceta").objects.get(pk=entrega.pk).turno_receta_id)
                for nombre in ("Ventanilla", "ConfiguracionCola", "EventoTurno", "PendienteSeleccion", "CierreAtencion"):
                    self.assertEqual(nuevas.get_model("turnosapp", nombre).objects.count(), 0)
                MigrationExecutor(connection).migrate(anteriores)
        finally:
            MigrationExecutor(connection).migrate(finales)
