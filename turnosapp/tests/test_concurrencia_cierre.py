"""Cierres y registro de recetas simultáneos con conexiones independientes."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from recetasapp.models import EntregaReceta, Receta
from recetasapp.services import registrar_entrega
from turnosapp.atencion import finalizar_atencion
from turnosapp.models import CierreAtencion, DetalleCierre, Turno
from .datos_cierre import DatosCierre


class ConcurrenciaCierreTests(DatosCierre, TransactionTestCase):
    def competir(self, funciones):
        barrera = Barrier(len(funciones))
        def ejecutar(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    return funcion()
                except ValidationError:
                    return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(funciones)) as pool:
            return list(pool.map(ejecutar, funciones))

    def cerrar(self, op):
        return finalizar_atencion(self.personal["tecnico"], self.actual.pk, op,
            recetas_entregadas=[r.pk for r in self.recetas_cierre])

    def verificar(self):
        self.assertEqual(EntregaReceta.objects.count(), 2)
        self.assertEqual(CierreAtencion.objects.count(), 1)
        self.assertEqual(DetalleCierre.objects.filter(entregada=True).count(), 2)
        self.assertFalse(Receta.objects.exclude(entregas_completadas=1).exists())

    def test_tres_reenvios_del_mismo_cierre_solo_confirman_una_vez(self):
        op = uuid.uuid4()
        resultados = self.competir([lambda: self.cerrar(op)] * 3)
        self.assertTrue(all(r == resultados[0] and r is not None for r in resultados))
        self.verificar()

    def test_dos_uuid_de_cierre_disputan_la_misma_atencion(self):
        resultados = self.competir([lambda: self.cerrar(uuid.uuid4()) for _ in range(2)])
        self.assertEqual(sum(r is not None for r in resultados), 1)
        self.verificar()

    def test_pantallas_03_y_05_compiten_sin_doble_descuento(self):
        r1 = self.recetas_cierre[0]
        resultados = self.competir([
            lambda: self.cerrar(uuid.uuid4()),
            lambda: registrar_entrega(self.personal["tecnico"], r1.pk, uuid.uuid4(), turno_receta_id=self.vinculos[0].pk),
        ])
        self.assertTrue(all(r is not None for r in resultados))
        self.verificar()

    def test_ultimo_cupo_en_03_se_reutiliza_al_cerrar(self):
        Receta.objects.update(max_entregas=1)
        r1 = self.recetas_cierre[0]
        resultados = self.competir([
            lambda: registrar_entrega(self.personal["tecnico"], r1.pk, uuid.uuid4(), turno_receta_id=self.vinculos[0].pk)
            for _ in range(3)
        ])
        self.assertTrue(all(r is not None for r in resultados))
        self.assertEqual(len({r.pk for r in resultados}), 1)
        self.cerrar(uuid.uuid4())
        self.verificar()
