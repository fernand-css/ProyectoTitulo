"""Spec 11, RNF-02, RF-11-07 y RF-11-09: sincronización concurrente con hilos y conexiones reales independientes.

Tres escenarios: el mismo lote enviado a la vez (dos pestañas, la página y Background Sync), sincronización frente a
la reasignación de la Q.F. y frente a la anulación. Gana exactamente una operación y ninguna receta se descuenta dos
veces. Las garantías salen de los servicios del 08 (cola del día, UPDATE condicional y `operacion_id` único).
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone

from entregasapp import sin_conexion
from entregasapp.models import Entrega, IntentoEntrega
from entregasapp.services import anular_entrega, reasignar
from recetasapp.models import EntregaReceta, Receta
from .ayudas import equipo, hoy, visita


class ConcurrenciaSinConexionTests(TransactionTestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]

    def competir(self, operaciones):
        barrera = Barrier(len(operaciones))

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

        with ThreadPoolExecutor(max_workers=len(operaciones)) as pool:
            return list(pool.map(ejecutar, operaciones))

    def registro(self, intento, resultado="entregada"):
        return {
            "operacion_id": str(uuid.uuid4()), "intento": intento.pk, "resultado": resultado,
            "motivo": "sin_receptor" if resultado == "no_entregada" else "", "nota": "",
            "registrado_en": (timezone.now() - timedelta(minutes=15)).isoformat(), "cuenta": self.encargado.pk,
        }

    def sincronizar(self, lote):
        return lambda: sin_conexion.sincronizar(self.encargado, lote)

    def test_1_mismo_lote_en_paralelo_se_aplica_una_vez(self):
        intentos = [visita(self.equipo, (dx, 0)) for dx in (1, 2, 3)]
        lote = [self.registro(intentos[0]), self.registro(intentos[1], "no_entregada"), self.registro(intentos[2])]
        respuestas = self.competir([self.sincronizar(lote)] * 4)
        for indice, registro in enumerate(lote):
            estados = [respuesta[indice]["estado"] for respuesta in respuestas]
            with self.subTest(registro=indice):
                self.assertEqual(estados.count("aplicado"), 1, estados)
                self.assertTrue(set(estados) <= {"aplicado", "ya_aplicado", "reintentar"}, estados)
        self.assertEqual(IntentoEntrega.objects.filter(resultado="pendiente").count(), 0)
        self.assertEqual(EntregaReceta.objects.count(), 2)  # dos entregadas, una receta cada una
        self.assertEqual(sorted(Receta.objects.values_list("entregas_completadas", flat=True)), [0, 1, 1])

    def test_2_sincronizacion_frente_a_reasignacion(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                intento = visita(self.equipo, (vuelta + 1, 1))
                lote = [self.registro(intento)]
                resultados = self.competir([
                    self.sincronizar(lote),
                    lambda: reasignar(self.equipo["qf"], intento.entrega_id, fecha=hoy(),
                                      encargado_id=self.equipo["encargado2"].pk, intento_id=intento.pk,
                                      operacion_id=uuid.uuid4(), resultado_visto="pendiente"),
                ])
                (respuesta,), reasignacion = resultados
                intento.refresh_from_db()
                if respuesta["estado"] == "aplicado":
                    self.assertIsInstance(reasignacion, ValidationError)
                    self.assertEqual(intento.resultado, "entregada")
                    self.assertEqual(Entrega.objects.get(pk=intento.entrega_id).estado, "entregada")
                else:
                    self.assertEqual((respuesta["estado"], respuesta["codigo"]), ("rechazado", "reasignada"))
                    self.assertIsInstance(reasignacion, IntentoEntrega)
                    self.assertEqual(intento.resultado, "reasignado")
                    self.assertEqual(reasignacion.resultado, "pendiente")
                    self.assertEqual(EntregaReceta.objects.filter(receta__paciente=intento.entrega.paciente).count(), 0)
                self.assertLessEqual(IntentoEntrega.objects.filter(entrega_id=intento.entrega_id, resultado="pendiente").count(), 1)

    def test_3_sincronizacion_frente_a_anulacion(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                intento = visita(self.equipo, (vuelta + 1, 2))
                lote = [self.registro(intento)]
                resultados = self.competir([
                    self.sincronizar(lote),
                    lambda: anular_entrega(self.equipo["qf"], intento.entrega_id, "otro", "Nota sintética"),
                ])
                (respuesta,), anulacion = resultados
                entrega = Entrega.objects.get(pk=intento.entrega_id)
                descontadas = EntregaReceta.objects.filter(receta__paciente=entrega.paciente).count()
                if respuesta["estado"] == "aplicado":
                    self.assertIsInstance(anulacion, ValidationError)
                    self.assertEqual((entrega.estado, descontadas), ("entregada", 1))
                else:
                    self.assertEqual((respuesta["estado"], respuesta["codigo"]), ("rechazado", "anulada"))
                    self.assertEqual((entrega.estado, descontadas), ("anulada", 0))
