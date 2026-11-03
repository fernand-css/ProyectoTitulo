"""Aplicación del esquema de turnos sobre una base anterior sintética."""

import uuid
from datetime import date
from random import Random

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from coreapp.utils.sinteticos import generar_ruts


class MigracionTurnosTests(TransactionTestCase):
    def test_actualizacion_y_reaplicacion_conservan_dominio_anterior(self):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        # Recetas 0003 depende de turnos 0001: la base anterior al 04 usa 0002.
        anteriores = [nodo for nodo in finales if nodo[0] not in {"turnosapp", "recetasapp"}] + [
            ("turnosapp", None), ("recetasapp", "0002_resultadofilaimportacion_pacientes_actualizados_and_more"),
        ]
        try:
            executor.migrate(anteriores)
            apps = executor.loader.project_state([nodo for nodo in anteriores if nodo[1] is not None]).apps
            Usuario = apps.get_model("auth", "User")
            Perfil = apps.get_model("usuariosapp", "Perfil")
            Grupo = apps.get_model("auth", "Group")
            Registro = apps.get_model("coreapp", "RegistroAuditoria")
            Paciente = apps.get_model("recetasapp", "Paciente")
            Receta = apps.get_model("recetasapp", "Receta")
            Entrega = apps.get_model("recetasapp", "EntregaReceta")
            usuario = Usuario.objects.create(username="turnos_migracion_sintetica", password="!hash-sintetico")
            Perfil.objects.create(usuario=usuario)
            grupo = Grupo.objects.create(name="Grupo sintético de migración de turnos")
            usuario.groups.add(grupo)
            paciente = Paciente.objects.create(
                rut=generar_ruts(1, Random(405))[0], nombres="Paciente sintético",
                apellidos="Migración", fecha_nacimiento=date(1970, 1, 1),
            )
            receta = Receta.objects.create(
                paciente=paciente, codigo="MIGRACION-TURNOS-001",
                fecha_inicio=date(2026, 1, 1), fecha_fin_exclusiva=date(2027, 1, 1),
                vigencia_meses=12, max_entregas=6, entregas_completadas=1,
            )
            operacion = uuid.uuid4()
            entrega = Entrega.objects.create(
                receta=receta, numero=1, operacion_id=operacion, creado_por=usuario,
            )
            registro = Registro.objects.create(
                usuario=usuario, accion="prueba.migracion", objeto_tipo="recetasapp.Receta",
                objeto_id=str(receta.pk),
            )
            for _ in range(2):
                actualizado = MigrationExecutor(connection)
                actualizado.migrate(finales)
                nuevas = actualizado.loader.project_state(finales).apps
                for nombre in ("Turno", "TurnoReceta", "ContadorTurnosDiario"):
                    self.assertEqual(nuevas.get_model("turnosapp", nombre).objects.count(), 0)
                self.assertEqual(nuevas.get_model("auth", "User").objects.get(pk=usuario.pk).password, usuario.password)
                self.assertTrue(nuevas.get_model("auth", "User").objects.filter(pk=usuario.pk, groups=grupo.pk).exists())
                self.assertTrue(nuevas.get_model("usuariosapp", "Perfil").objects.filter(usuario_id=usuario.pk).exists())
                self.assertEqual(nuevas.get_model("recetasapp", "Paciente").objects.get(pk=paciente.pk).rut, paciente.rut)
                self.assertEqual(nuevas.get_model("recetasapp", "Receta").objects.get(pk=receta.pk).entregas_completadas, 1)
                self.assertEqual(nuevas.get_model("recetasapp", "EntregaReceta").objects.get(pk=entrega.pk).operacion_id, operacion)
                self.assertTrue(nuevas.get_model("coreapp", "RegistroAuditoria").objects.filter(pk=registro.pk, usuario_id=usuario.pk).exists())
                MigrationExecutor(connection).migrate(anteriores)
        finally:
            MigrationExecutor(connection).migrate(finales)
