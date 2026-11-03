"""Emisores simultáneos con conexiones reales independientes."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from recetasapp.models import Receta
from recetasapp.services import registrar_entrega
from recetasapp.tests.ayudas import actores, cargar

from coreapp.models import RegistroAuditoria
from turnosapp.models import Turno, ContadorTurnosDiario
from turnosapp.services import emitir_turno
from . import test_servicios as preparacion


class ConcurrenciaTurnosTests(TransactionTestCase):
    setUp = preparacion.EmisionTests.setUp
    pacientes = preparacion.EmisionTests.pacientes
    recetas = preparacion.EmisionTests.recetas

    def competir(self, solicitudes):
        barrera = Barrier(len(solicitudes))
        def ejecutar(solicitud):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return solicitud() if callable(solicitud) else emitir_turno(*solicitud)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(solicitudes)) as pool:
            return list(pool.map(ejecutar, solicitudes))

    def verificar(self, cantidad):
        self.assertEqual(Turno.objects.count(), cantidad)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="turno.emitido").count(), cantidad)
        self.assertEqual(ContadorTurnosDiario.objects.get().ultimo_numero, cantidad)
        self.assertEqual(len(set(Turno.objects.values_list("fecha", "numero"))), cantidad)
        self.assertTrue(all(t.recetas_vinculadas.count() == 1 for t in Turno.objects.all()))

    def test_mismo_uuid_tres_emisores(self):
        operacion = uuid.uuid4()
        resultados = self.competir([(self.paciente.rut, operacion)] * 3)
        self.assertEqual({r.numero for r in resultados}, {1})
        self.verificar(1)

    def test_distintos_uuid_mismo_paciente(self):
        resultados = self.competir([(self.paciente.rut, uuid.uuid4()) for _ in range(3)])
        self.assertEqual({r.numero for r in resultados}, {1})
        self.verificar(1)

    def test_tres_pacientes_compiten_por_serie(self):
        pacientes = [self.paciente, self.pacientes(1), self.pacientes(2)]
        for indice, paciente in enumerate(pacientes[1:]):
            self.recetas(paciente, f"CONCURRENTE-{indice}")
        resultados = self.competir([(p.rut, uuid.uuid4()) for p in pacientes])
        self.assertEqual({r.numero for r in resultados}, {1, 2, 3})
        self.verificar(3)

    def test_emision_compite_con_entrega_sin_consumir_otro_cupo(self):
        personal = actores()
        self.competir([
            (self.paciente.rut, uuid.uuid4()),
            lambda: registrar_entrega(personal["tecnico"], self.receta.pk, uuid.uuid4()),
        ])
        self.verificar(1)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 1)
        self.assertEqual(self.receta.entregas.count(), 1)

    def test_emision_compite_con_importacion_sin_duplicar_recetas(self):
        personal = actores()
        p, r = self.paciente, self.receta
        fila = [p.rut, p.nombres, p.apellidos, p.fecha_nacimiento.isoformat(), "0", "0", "", "",
                r.codigo, r.fecha_inicio.isoformat(), "1", "3"]
        resultados = self.competir([
            (p.rut, uuid.uuid4()), lambda: cargar(personal["qf"], [fila]),
        ])
        self.assertEqual(resultados[1].estado, "completada")
        self.verificar(1)
        self.assertEqual(Receta.objects.count(), 1)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 0)
