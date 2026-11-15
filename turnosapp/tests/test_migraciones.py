"""Aplicación del esquema de turnos sobre una base anterior sintética."""

import uuid
from datetime import date, datetime, timezone as dt_timezone
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


class MigracionLetrasTests(TransactionTestCase):
    """Enmienda 04 del 2026-11-15: rellena RUT y letra sin renumerar ni chocar series."""

    def test_rellena_rut_letra_y_series_sin_renumerar_y_revierte(self):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        anteriores = [nodo for nodo in finales if nodo[0] != "turnosapp"] + [("turnosapp", "0003_anuncio_sala")]
        dia, siguiente, sin_turnos = date(2026, 11, 10), date(2026, 11, 11), date(2026, 11, 12)
        try:
            executor.migrate(anteriores)
            apps = executor.loader.project_state(anteriores).apps
            Paciente = apps.get_model("recetasapp", "Paciente")
            TurnoAnterior = apps.get_model("turnosapp", "Turno")
            ContadorAnterior = apps.get_model("turnosapp", "ContadorTurnosDiario")
            pacientes = [
                Paciente.objects.create(
                    rut=rut, nombres="Paciente sintético", apellidos=f"Letras {indice}",
                    fecha_nacimiento=date(1970, 1, 1),
                )
                for indice, rut in enumerate(generar_ruts(5, Random(415)))
            ]
            # Correlativo compartido anterior: G-1, P-2, C-3, G-4 el mismo día; P-5 sin contador.
            previos = [
                (pacientes[0], dia, 1, "general"), (pacientes[1], dia, 2, "preferencial"),
                (pacientes[2], dia, 3, "cronicos"), (pacientes[3], dia, 4, "general"),
                (pacientes[4], siguiente, 5, "preferencial"),
            ]
            ids = {
                TurnoAnterior.objects.create(
                    paciente=paciente, fecha=fecha, numero=numero, tipo_atencion=tipo, operacion_id=uuid.uuid4(),
                ).pk: (paciente.rut, fecha, numero, tipo)
                for paciente, fecha, numero, tipo in previos
            }
            ContadorAnterior.objects.create(fecha=dia, ultimo_numero=4)
            ContadorAnterior.objects.create(fecha=sin_turnos, ultimo_numero=7)
            letras = {"general": "G", "preferencial": "P", "cronicos": "C"}
            for _ in range(2):
                actual = MigrationExecutor(connection)
                actual.migrate(finales)
                nuevas = actual.loader.project_state(finales).apps
                Turno = nuevas.get_model("turnosapp", "Turno")
                Contador = nuevas.get_model("turnosapp", "ContadorTurnosDiario")
                for pk, (rut, fecha, numero, tipo) in ids.items():
                    migrado = Turno.objects.get(pk=pk)
                    self.assertEqual(
                        (migrado.rut, migrado.fecha, migrado.numero, migrado.tipo_atencion, migrado.letra),
                        (rut, fecha, numero, tipo, letras[tipo]),
                    )
                series = {(c.fecha, c.letra): c.ultimo_numero for c in Contador.objects.all()}
                self.assertEqual(series, {
                    (dia, "G"): 4, (dia, "P"): 2, (dia, "C"): 3, (siguiente, "P"): 5, (sin_turnos, "G"): 7,
                })
                # La serie continúa sin chocar con lo ya emitido en esa letra y fecha.
                Contador.objects.filter(fecha=dia, letra="P").update(ultimo_numero=3)
                nuevo = Turno.objects.create(
                    paciente_id=pacientes[0].pk, rut=pacientes[0].rut, fecha=dia, numero=3,
                    letra="P", tipo_atencion="preferencial", estado="atendido",
                    cerrado_en=datetime(2026, 11, 10, 12, tzinfo=dt_timezone.utc),
                )
                Turno.objects.filter(pk=nuevo.pk).delete()
                Contador.objects.filter(fecha=dia, letra="P").update(ultimo_numero=2)
                regreso = MigrationExecutor(connection)
                regreso.migrate(anteriores)
                previas = regreso.loader.project_state(anteriores).apps
                compartidos = {
                    c.fecha: c.ultimo_numero
                    for c in previas.get_model("turnosapp", "ContadorTurnosDiario").objects.all()
                }
                self.assertEqual(compartidos, {dia: 4, siguiente: 5, sin_turnos: 7})
                self.assertEqual(
                    sorted(previas.get_model("turnosapp", "Turno").objects.values_list("numero", flat=True)),
                    [1, 2, 3, 4, 5],
                )
        finally:
            MigrationExecutor(connection).migrate(finales)
