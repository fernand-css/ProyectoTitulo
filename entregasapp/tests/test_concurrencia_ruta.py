"""RF-09-15: orden de visita con hilos y conexiones reales independientes (spec 09).

Las garantías salen de la restricción `orden_ruta_unico`, del UPDATE condicional por versión y de cruzar siempre
el orden guardado con la ruta vigente al leer; no de `select_for_update()`.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from entregasapp.consultas import ruta_del_dia
from entregasapp.models import IntentoEntrega, OrdenRuta, ParadaRuta
from entregasapp.services import MENSAJE_ORDEN_CAMBIO, mover_parada, reasignar, registrar_entregada
from .ayudas import equipo, hoy, visita


class ConcurrenciaRutaTests(TransactionTestCase):
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

    def avisos(self, resultados):
        return [r for r in resultados if isinstance(r, ValidationError)]

    def aplicadas(self, resultados):
        return [r for r in resultados if isinstance(r, OrdenRuta)]

    def test_1_primeras_ediciones_simultaneas_dejan_un_orden_y_una_edicion(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                OrdenRuta.objects.filter(encargado=self.encargado).delete()
                intentos = [visita(self.equipo, (vuelta, k)) for k in (1, 2, 3)]
                misma = uuid.uuid4()
                resultados = self.competir(
                    [lambda i=i: mover_parada(self.encargado, i.pk, "1", 0, uuid.uuid4()) for i in intentos]
                    + [lambda: mover_parada(self.encargado, intentos[2].pk, "subir", 0, misma)] * 2
                )
                self.assertEqual(OrdenRuta.objects.filter(encargado=self.encargado, fecha=hoy()).count(), 1)
                orden = OrdenRuta.objects.get(encargado=self.encargado)
                self.assertEqual(orden.version, 1)
                self.assertEqual({r.pk for r in self.aplicadas(resultados)}, {orden.pk})
                avisos = self.avisos(resultados)
                self.assertTrue(all(MENSAJE_ORDEN_CAMBIO in r.messages for r in avisos))
                # Una sola edición aplicada (o su reenvío idempotente con la misma operación).
                aplicadas = len(resultados) - len(avisos)
                self.assertIn(aplicadas, (1, 2))
                if aplicadas == 2:
                    self.assertEqual(orden.ultima_operacion, misma)
                vigentes = set(IntentoEntrega.objects.filter(encargado=self.encargado, resultado="pendiente")
                               .values_list("pk", flat=True))
                self.assertEqual(set(ParadaRuta.objects.filter(orden=orden).values_list("intento_id", flat=True)), vigentes)

    def test_2_tres_ediciones_desde_la_misma_version_una_gana(self):
        intentos = [visita(self.equipo, (0, k)) for k in (1, 2, 3, 4)]
        mover_parada(self.encargado, intentos[0].pk, "bajar", 0, uuid.uuid4())
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                version = ruta_del_dia(self.encargado).version
                resultados = self.competir([
                    lambda: mover_parada(self.encargado, intentos[3].pk, "1", version, uuid.uuid4()),
                    lambda: mover_parada(self.encargado, intentos[1].pk, "bajar", version, uuid.uuid4()),
                    lambda: mover_parada(self.encargado, intentos[2].pk, "subir", version, uuid.uuid4()),
                ])
                self.assertEqual(len(self.aplicadas(resultados)), 1)
                avisos = self.avisos(resultados)
                self.assertEqual(len(avisos), 2)
                self.assertTrue(all(r.messages == [MENSAJE_ORDEN_CAMBIO] for r in avisos))
                ruta = ruta_del_dia(self.encargado)
                self.assertEqual(ruta.version, version + 1)
                self.assertCountEqual([p.intento.pk for p in ruta.paradas], [i.pk for i in intentos])
                self.assertEqual(ParadaRuta.objects.filter(orden__encargado=self.encargado).count(), 4)

    def test_3_reordenar_mientras_se_registra_y_se_reasigna_no_duplica_ni_pierde_visitas(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                intentos = [visita(self.equipo, (vuelta + 1, k)) for k in (1, 2, 3, 4, 5)]
                version = ruta_del_dia(self.encargado).version
                registrada, reasignada, movida = intentos[1], intentos[2], intentos[4]
                destino = self.encargado if vuelta == 1 else self.equipo["encargado2"]
                resultados = self.competir([
                    lambda: mover_parada(self.encargado, movida.pk, "1", version, uuid.uuid4()),
                    lambda: registrar_entregada(self.encargado, registrada.pk, uuid.uuid4()),
                    lambda: reasignar(self.equipo["qf"], reasignada.entrega_id, fecha=hoy(), encargado_id=destino.pk,
                                      intento_id=reasignada.pk, operacion_id=uuid.uuid4(), resultado_visto="pendiente"),
                ])
                self.assertFalse([r for r in resultados if isinstance(r, Exception)], resultados)
                vigentes = list(IntentoEntrega.objects.filter(encargado=self.encargado, resultado="pendiente",
                                                              fecha_programada__lte=hoy()).values_list("pk", flat=True))
                ruta = ruta_del_dia(self.encargado)
                mostrados = [p.intento.pk for p in ruta.paradas]
                self.assertEqual(len(mostrados), len(set(mostrados)))  # ninguna duplicada
                self.assertCountEqual(mostrados, vigentes)  # ninguna perdida
                self.assertNotIn(registrada.pk, mostrados)
                self.assertNotIn(reasignada.pk, mostrados)
                # La movida queda primera entre las guardadas; una nueva puede entrar antes por inserción más barata.
                self.assertEqual(next(p for p in ruta.paradas if not p.nueva).intento.pk, movida.pk)
                guardadas = list(ParadaRuta.objects.filter(orden__encargado=self.encargado).values_list("intento_id", flat=True))
                self.assertEqual(len(guardadas), len(set(guardadas)))
                if vuelta == 1:  # reasignada al mismo encargado: aparece como nueva, una sola vez
                    nueva = IntentoEntrega.objects.get(entrega_id=reasignada.entrega_id, resultado="pendiente")
                    self.assertIn(nueva.pk, mostrados)
                IntentoEntrega.objects.filter(encargado=self.encargado, resultado="pendiente").update(encargado=self.equipo["encargado2"])
