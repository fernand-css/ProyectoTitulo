"""RF-13-10: la derivación frente a otras escrituras simultáneas, con hilos y conexiones reales independientes.

Las garantías salen de la cola del día (`bloquear_cola`), de las restricciones (una entrega abierta y una excepción
vigente por paciente) y de los UPDATE condicionales; no de `select_for_update()`.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from entregasapp.models import Entrega, InscripcionReparto, RecetaEntrega
from entregasapp.services import derivar_desde_merma, programar_lote
from recetasapp.models import EntregaReceta
from recetasapp.services import retirar_preparado
from .ayudas import equipo, hoy, paciente, preparada, receta


class ConcurrenciaDerivacionTests(TransactionTestCase):
    def setUp(self):
        self.e = equipo()

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

    def derivar(self, persona, **extra):
        return lambda: derivar_desde_merma(self.e["qf"], persona.pk, hoy(), self.e["encargado"].pk, uuid.uuid4(), **extra)

    def test_1_derivaciones_simultaneas_del_mismo_paciente(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                persona = paciente(edad=60)
                preparada(persona, usuario=self.e["tecnico"])
                self.competir([self.derivar(persona, motivo="sin_red_apoyo")] * 4)
                self.assertEqual(Entrega.objects.filter(paciente=persona, estado__in=Entrega.ABIERTAS).count(), 1)
                self.assertEqual(InscripcionReparto.objects.filter(paciente=persona, retirada_en__isnull=True).count(), 1)
                self.assertEqual(RecetaEntrega.objects.filter(entrega__paciente=persona).count(), 1)

    def test_2_derivacion_frente_a_retiro_en_ventanilla(self):
        for vuelta in range(4):
            with self.subTest(vuelta=vuelta):
                persona = paciente(edad=85)
                preparacion = preparada(persona, usuario=self.e["tecnico"])
                resultados = self.competir([
                    self.derivar(persona),
                    lambda: retirar_preparado(self.e["tecnico"], preparacion.pk, uuid.uuid4()),
                ])
                retirada = EntregaReceta.objects.filter(turno_receta=preparacion.turno_receta).exists()
                en_despacho = RecetaEntrega.objects.filter(preparacion=preparacion, entrega__estado__in=Entrega.ABIERTAS).exists()
                self.assertTrue(retirada != en_despacho, resultados)  # uno solo de los dos caminos

    def test_3_derivacion_frente_a_programar_lote(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                persona = paciente(edad=85)
                preparada(persona, usuario=self.e["tecnico"])
                receta(persona)
                self.competir([
                    self.derivar(persona),
                    lambda: programar_lote(self.e["qf"], [persona.pk], hoy(), self.e["encargado"].pk, uuid.uuid4()),
                ])
                self.assertEqual(Entrega.objects.filter(paciente=persona, estado__in=Entrega.ABIERTAS).count(), 1)
                recetas = list(RecetaEntrega.objects.filter(entrega__paciente=persona).values_list("receta_id", flat=True))
                self.assertEqual(len(recetas), len(set(recetas)))
