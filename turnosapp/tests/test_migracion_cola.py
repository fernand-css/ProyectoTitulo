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


class MigracionUrgenciaVentanillaTests(TransactionTestCase):
    """Enmienda del 05 (RF-05-13): las ventanillas existentes admiten U al migrar."""

    def test_agrega_urgencia_a_ventanillas_y_revierte_sin_borrar_ventanillas(self):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        anterior = [n for n in finales if n[0] != "turnosapp"] + [("turnosapp", "0007_intento_totem")]
        try:
            executor.migrate(anterior)
            apps = executor.loader.project_state(anterior).apps
            Tipo = apps.get_model("turnosapp", "TipoAtencionVentanilla")
            Ventanilla = apps.get_model("turnosapp", "Ventanilla")
            tipos = [Tipo.objects.create(codigo=codigo) for codigo in ("general", "preferencial", "cronicos")]
            completa = Ventanilla.objects.create(numero=1)
            completa.tipos.set(tipos)
            solo_general = Ventanilla.objects.create(numero=2)
            solo_general.tipos.set(tipos[:1])

            actual = MigrationExecutor(connection)
            actual.migrate(finales)
            nuevas = actual.loader.project_state(finales).apps
            VentanillaNueva = nuevas.get_model("turnosapp", "Ventanilla")
            self.assertEqual(set(VentanillaNueva.objects.get(numero=1).tipos.values_list("codigo", flat=True)),
                {"general", "preferencial", "cronicos", "urgencia"})
            self.assertEqual(set(VentanillaNueva.objects.get(numero=2).tipos.values_list("codigo", flat=True)),
                {"general", "urgencia"})

            MigrationExecutor(connection).migrate(anterior)
            apps = MigrationExecutor(connection).loader.project_state(anterior).apps
            self.assertFalse(apps.get_model("turnosapp", "TipoAtencionVentanilla").objects.filter(codigo="urgencia").exists())
            self.assertEqual(apps.get_model("turnosapp", "Ventanilla").objects.count(), 2)
        finally:
            MigrationExecutor(connection).migrate(finales)

    def test_base_sin_ventanillas_no_crea_tipos(self):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        anterior = [n for n in finales if n[0] != "turnosapp"] + [("turnosapp", "0007_intento_totem")]
        try:
            executor.migrate(anterior)
            actual = MigrationExecutor(connection)
            actual.migrate(finales)
            nuevas = actual.loader.project_state(finales).apps
            self.assertEqual(nuevas.get_model("turnosapp", "TipoAtencionVentanilla").objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(finales)


class MigracionLetraAnuncioTests(TransactionTestCase):
    """Enmienda del 06 (RF-06-13): los anuncios anteriores reciben la letra de su turno."""

    def test_rellena_letra_desde_el_turno_del_evento(self):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        anterior = [n for n in finales if n[0] != "turnosapp"] + [("turnosapp", "0009_ventanilla_urgencia_datos")]
        try:
            executor.migrate(anterior)
            apps = executor.loader.project_state(anterior).apps
            Turno = apps.get_model("turnosapp", "Turno")
            EventoTurno = apps.get_model("turnosapp", "EventoTurno")
            AnuncioSala = apps.get_model("turnosapp", "AnuncioSala")
            instante = timezone.now()
            anuncios = []
            for numero, (tipo, letra) in enumerate((("preferencial", "P"), ("cronicos", "C")), start=1):
                turno = Turno.objects.create(rut=generar_ruts(2, Random(606))[numero - 1], letra=letra,
                    fecha=date(2026, 11, 2), numero=numero, tipo_atencion=tipo, operacion_id=uuid.uuid4())
                evento = EventoTurno.objects.create(turno=turno, secuencia=1, accion="llamado", instante=instante)
                anuncios.append(AnuncioSala.objects.create(evento=evento, fecha=date(2026, 11, 2), numero=numero,
                    ventanilla_numero=1, accion="llamado", instante=instante).pk)

            actual = MigrationExecutor(connection)
            actual.migrate(finales)
            nuevas = actual.loader.project_state(finales).apps
            letras = dict(nuevas.get_model("turnosapp", "AnuncioSala").objects.values_list("pk", "letra"))
            self.assertEqual([letras[pk] for pk in anuncios], ["P", "C"])

            MigrationExecutor(connection).migrate(anterior)
        finally:
            MigrationExecutor(connection).migrate(finales)
