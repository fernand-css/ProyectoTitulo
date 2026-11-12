"""RF-09-01 a RF-09-03, RF-09-05 y RF-09-07: la ruta del día se arma en cada consulta, sin escribir nada."""

import uuid
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from entregasapp.consultas import MANUAL, SUGERIDO, partida_del_dia, registradas_hoy, ruta_del_dia
from entregasapp.models import IntentoEntrega, OrdenRuta, ParadaRuta
from entregasapp.services import anular_entrega, reasignar, registrar_entregada, registrar_no_entregada
from .ayudas import equipo, hoy, visita


def ids(paradas):
    return [parada.intento.pk for parada in paradas]


def atrasar(intento, dias=1):
    IntentoEntrega.objects.filter(pk=intento.pk).update(fecha_programada=hoy() - timedelta(days=dias))
    intento.refresh_from_db()
    return intento


class RutaDelDiaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]

    def visita(self, en=None, **opciones):
        return visita(self.equipo, en, **opciones)

    def guardar_orden(self, *intentos):
        orden = OrdenRuta.objects.create(encargado=self.encargado, fecha=hoy(), creado_por=self.encargado,
                                         modificado_por=self.encargado)
        ParadaRuta.objects.bulk_create([ParadaRuta(orden=orden, intento=i, posicion=n) for n, i in enumerate(intentos, 1)])
        return orden

    def test_hoy_y_atrasadas_en_la_ruta_proximas_aparte_y_sin_las_de_otro_encargado(self):
        de_hoy = [self.visita((0, k)) for k in (1, 2, 3)]
        ayer = atrasar(self.visita((0, 4)))
        manana = self.visita((0, 5), fecha=hoy() + timedelta(days=1))
        otro = self.equipo["encargado2"]
        ajenas = [self.visita((1, 1), encargado=otro), self.visita((1, 2), encargado=otro)]
        ruta = ruta_del_dia(self.encargado, incluir_proximas=True)
        self.assertEqual(ruta.modo, SUGERIDO)
        self.assertCountEqual(ids(ruta.paradas), [*[i.pk for i in de_hoy], ayer.pk])
        self.assertEqual([p.numero for p in ruta.paradas], [1, 2, 3, 4])
        self.assertTrue(ruta.parada_de(ayer.pk).atrasada)
        self.assertFalse(any(ruta.parada_de(i.pk).atrasada for i in de_hoy))
        self.assertEqual([i.pk for i in ruta.proximas], [manana.pk])
        self.assertFalse({i.pk for i in ajenas} & set(ids(ruta.paradas)))
        self.assertEqual(ruta_del_dia(self.encargado).proximas, [])  # la consulta de la Q.F. no las trae

    def test_sin_intentos_reasignados_ni_anulados(self):
        reasignada, anulada, vigente = self.visita((0, 1)), self.visita((0, 2)), self.visita((0, 3))
        reasignar(self.equipo["qf"], reasignada.entrega_id, fecha=hoy(), encargado_id=self.equipo["encargado2"].pk,
                  intento_id=reasignada.pk, operacion_id=uuid.uuid4(), resultado_visto="pendiente")
        anular_entrega(self.equipo["qf"], anulada.entrega_id, "retirara_farmacia")
        self.assertEqual(ids(ruta_del_dia(self.encargado).paradas), [vigente.pk])
        self.assertEqual(len(ruta_del_dia(self.equipo["encargado2"]).paradas), 1)

    def test_paradas_sobre_una_linea_se_ordenan_b_c_a_y_se_recalculan_desde_la_ultima_registrada(self):
        a, b, c = self.visita((0, 3)), self.visita((0, 1)), self.visita((0, 2))
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual(ids(ruta.paradas), [b.pk, c.pk, a.pk])
        self.assertTrue(ruta.parte_del_origen)
        self.assertAlmostEqual(ruta.total_m, 6000, delta=2)
        self.assertEqual(ruta.total_km, "6,0")
        for _ in range(3):
            self.assertEqual(ids(ruta_del_dia(self.encargado).paradas), [b.pk, c.pk, a.pk])
        registrar_entregada(self.encargado, b.pk, uuid.uuid4())
        despues = ruta_del_dia(self.encargado)
        self.assertEqual(ids(despues.paradas), [c.pk, a.pk])
        self.assertEqual(despues.partida_intento.pk, b.pk)
        self.assertAlmostEqual(despues.total_m, 5000, delta=2)  # B → C → A → CESFAM

    def test_la_partida_ignora_registradas_sin_coordenadas(self):
        con, sin = self.visita((0, 2)), self.visita(None)
        self.visita((0, 4))
        registrar_entregada(self.encargado, con.pk, uuid.uuid4())
        registrar_no_entregada(self.encargado, sin.pk, "sin_receptor", "", uuid.uuid4())
        punto, intento = partida_del_dia(self.encargado)
        self.assertEqual(intento.pk, con.pk)
        self.assertEqual(punto.clave, con.pk)
        # Sin registradas con coordenadas, parte del CESFAM.
        punto, intento = partida_del_dia(self.equipo["encargado2"])
        self.assertIsNone(intento)
        self.assertEqual(punto.clave, "origen")

    def test_visitas_sin_coordenadas_al_final_agrupadas_y_sin_numero(self):
        con = [self.visita((0, 1)), self.visita((0, 2))]
        sin_coordenadas = self.visita(None, sector="rojo", localidad="Localidad demo 2")
        sin_domicilio = self.visita(None, domicilio=False)
        azul = self.visita(None, sector="azul", localidad="Localidad demo 9")
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual(ids(ruta.numeradas), [i.pk for i in con])
        # Por sector y localidad (azul, rojo) y al final la que no tiene domicilio ni sector.
        self.assertEqual(ids(ruta.sin_coordenadas), [azul.pk, sin_coordenadas.pk, sin_domicilio.pk])
        self.assertEqual(ruta.sin_marcador, 3)
        self.assertTrue(all(p.punto is None and not p.numerada for p in ruta.sin_coordenadas))
        self.assertAlmostEqual(ruta.total_m, 4000, delta=2)

    def test_registradas_hoy_con_resultado_y_sin_las_de_ayer(self):
        entregada, no_entregada, de_ayer = self.visita((0, 1)), self.visita((0, 2)), self.visita((0, 3))
        self.visita((0, 4))
        registrar_entregada(self.encargado, entregada.pk, uuid.uuid4())
        registrar_no_entregada(self.encargado, no_entregada.pk, "domicilio_no_encontrado", "", uuid.uuid4())
        registrar_entregada(self.encargado, de_ayer.pk, uuid.uuid4())
        IntentoEntrega.objects.filter(pk=de_ayer.pk).update(registrado_en=timezone.now() - timedelta(days=1))
        self.assertEqual([i.pk for i in registradas_hoy(self.encargado)], [entregada.pk, no_entregada.pk])
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual([i.pk for i in ruta.registradas], [entregada.pk, no_entregada.pk])
        self.assertEqual(ruta.registradas[1].get_motivo_display(), "Domicilio no encontrado")
        self.assertEqual(len(ruta.paradas), 1)

    def test_orden_guardado_manda_y_las_registradas_salen_sin_alterar_el_resto(self):
        a, b, c = self.visita((0, 3)), self.visita((0, 1)), self.visita((0, 2))
        sin = self.visita(None)
        self.guardar_orden(sin, a, c, b)
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual(ruta.modo, MANUAL)
        self.assertEqual(ids(ruta.paradas), [sin.pk, a.pk, c.pk, b.pk])
        self.assertEqual([p.numero for p in ruta.paradas], [1, 2, 3, 4])
        self.assertTrue(all(p.numerada for p in ruta.paradas))
        self.assertIsNone(ruta.paradas[0].punto)  # numerada y sin marcador
        self.assertEqual(ruta.version, 1)
        self.assertIsNotNone(ruta.guardado_en)
        registrar_entregada(self.encargado, a.pk, uuid.uuid4())
        self.assertEqual(ids(ruta_del_dia(self.encargado).paradas), [sin.pk, c.pk, b.pk])

    def test_visitas_nuevas_entran_donde_menos_alargan_y_las_que_salen_desaparecen(self):
        """Criterio de RF-09-05: A, B, C guardado; D entre A y B; E sin coordenadas; anular B."""
        a, b, c = self.visita((1, 2)), self.visita((1, 6)), self.visita((-1, 4))
        self.guardar_orden(a, b, c)
        d = self.visita((1, 4), encargado=self.equipo["encargado2"])
        reasignar(self.equipo["qf"], d.entrega_id, fecha=hoy(), encargado_id=self.encargado.pk, intento_id=d.pk,
                  operacion_id=uuid.uuid4(), resultado_visto="pendiente")
        nueva_d = IntentoEntrega.objects.get(entrega_id=d.entrega_id, resultado="pendiente")
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual(ids(ruta.paradas), [a.pk, nueva_d.pk, b.pk, c.pk])
        self.assertEqual([p.nueva for p in ruta.paradas], [False, True, False, False])
        e = self.visita(None)
        self.assertEqual(ids(ruta_del_dia(self.encargado).paradas), [a.pk, nueva_d.pk, b.pk, c.pk, e.pk])
        anular_entrega(self.equipo["qf"], b.entrega_id, "retirara_farmacia")
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual(ids(ruta.paradas), [a.pk, nueva_d.pk, c.pk, e.pk])
        self.assertEqual([p.nueva for p in ruta.paradas], [False, True, False, True])
        self.assertEqual([p.numero for p in ruta.paradas], [1, 2, 3, 4])

    def test_nueva_al_final_o_sin_paradas_con_coordenadas(self):
        sin = self.visita(None)
        self.guardar_orden(sin)
        lejos = self.visita((0, 9))
        self.assertEqual(ids(ruta_del_dia(self.encargado).paradas), [sin.pk, lejos.pk])

    def test_orden_vacio_vale_la_sugerencia_y_otro_dia_no_aplica(self):
        a, b = self.visita((0, 2)), self.visita((0, 1))
        orden = self.guardar_orden(a, b)
        self.assertEqual(ids(ruta_del_dia(self.encargado).paradas), [a.pk, b.pk])
        orden.paradas.all().delete()
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual((ruta.modo, ids(ruta.paradas), ruta.version), (SUGERIDO, [b.pk, a.pk], 1))
        # El orden de ayer no vale hoy.
        OrdenRuta.objects.filter(pk=orden.pk).update(fecha=hoy() - timedelta(days=1))
        ParadaRuta.objects.create(orden=orden, intento=a, posicion=1)
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual((ruta.modo, ruta.version), (SUGERIDO, 0))

    def test_fecha_futura_solo_esa_fecha_sugerida_desde_el_cesfam(self):
        a = self.visita((0, 2))
        registrar_entregada(self.encargado, a.pk, uuid.uuid4())
        self.visita((0, 3))
        manana = hoy() + timedelta(days=1)
        lejos, cerca = self.visita((0, 6), fecha=manana), self.visita((0, 1), fecha=manana)
        self.visita((0, 8), fecha=manana + timedelta(days=1))
        self.guardar_orden(*[p.intento for p in ruta_del_dia(self.encargado).paradas])
        ruta = ruta_del_dia(self.encargado, manana)
        self.assertEqual(ruta.modo, SUGERIDO)
        self.assertEqual(ids(ruta.paradas), [cerca.pk, lejos.pk])
        self.assertTrue(ruta.parte_del_origen)
        self.assertEqual((ruta.registradas, ruta.proximas), ([], []))
        self.assertAlmostEqual(ruta.total_m, 12000, delta=3)

    def test_numero_de_consultas_constante(self):
        def contar(**opciones):
            with CaptureQueriesContext(connection) as consultas:
                ruta_del_dia(self.encargado, **opciones)
            return len(consultas)

        for k in (1, 2):
            self.visita((0, k))
        registrar_entregada(self.encargado, ruta_del_dia(self.encargado).paradas[0].intento.pk, uuid.uuid4())
        pocas = contar(incluir_proximas=True)
        for k in range(3, 10):
            self.visita((k % 3, k), fecha=hoy() + timedelta(days=k % 2))
        self.visita(None)
        registrar_entregada(self.encargado, ruta_del_dia(self.encargado).paradas[0].intento.pk, uuid.uuid4())
        self.assertEqual(contar(incluir_proximas=True), pocas)
        self.guardar_orden(*[p.intento for p in ruta_del_dia(self.encargado).paradas])
        manual = contar(incluir_proximas=True)
        self.visita((2, 2))
        self.visita((2, 3))
        self.assertEqual(contar(incluir_proximas=True), manual)
        self.assertLessEqual(manual, 8)
