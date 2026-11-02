"""Colisiones reales con conexiones independientes sobre SQLite."""

import uuid
from datetime import date
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from recetasapp.models import Receta
from recetasapp.services import registrar_entrega
from .ayudas import actores, cargar, fila


class ConcurrenciaTests(TransactionTestCase):
    def setUp(self):
        reloj = patch("recetasapp.services.timezone.localdate", return_value=date(2026, 11, 2))
        reloj.start()
        self.addCleanup(reloj.stop)
        self.actores = actores()
        cargar(self.actores["qf"], [fila()])
        self.receta = Receta.objects.get()

    def competir(self, operaciones):
        barrera = Barrier(len(operaciones))
        def ejecutar(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    return funcion()
                except ValidationError:
                    return "rechazada"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(operaciones)) as pool:
            return list(pool.map(ejecutar, operaciones))

    def test_ultimo_cupo_no_se_entrega_dos_veces(self):
        Receta.objects.filter(pk=self.receta.pk).update(max_entregas=1)
        self.competir([lambda: registrar_entrega(self.actores["tecnico"], self.receta.pk, uuid.uuid4()) for _ in range(3)])
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 1)
        self.assertEqual(self.receta.entregas.count(), 1)

    def test_doble_confirmacion_misma_operacion(self):
        operacion = uuid.uuid4()
        resultados = self.competir([lambda: registrar_entrega(self.actores["tecnico"], self.receta.pk, operacion) for _ in range(2)])
        self.assertEqual(len({r.pk for r in resultados}), 1)
        self.assertEqual(self.receta.entregas.count(), 1)

    def test_entrega_compite_con_cambio_de_cupo_importado(self):
        datos = fila()
        datos[11] = "1"
        self.competir([
            lambda: registrar_entrega(self.actores["tecnico"], self.receta.pk, uuid.uuid4()),
            lambda: cargar(self.actores["qf"], [datos]),
        ])
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, self.receta.entregas.count())
        self.assertLessEqual(self.receta.entregas_completadas, self.receta.max_entregas)

    def test_cargas_simultaneas_no_duplican_identidades(self):
        datos = list(fila("NUEVA"))
        resultados = self.competir([lambda: cargar(self.actores["qf"], [datos]) for _ in range(2)])
        self.assertEqual([r.estado for r in resultados], ["completada", "completada"])
        self.assertEqual(Receta.objects.filter(codigo="NUEVA").count(), 1)
