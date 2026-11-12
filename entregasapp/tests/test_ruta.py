"""RF-09-02 y RF-09-05: algoritmo de orden en línea recta, sin base de datos (`entregasapp.ruta` es puro).

Las coordenadas son sintéticas: desplazamientos en km alrededor de un punto de prueba, sin relación con
viviendas reales.
"""

import ast
import itertools
import math
from pathlib import Path
from random import Random

from django.test import SimpleTestCase

from entregasapp import ruta
from entregasapp.ruta import LIMITE_2OPT, Punto, distancia_m, formatear_km, insertar, longitud_m, ordenar

LAT0, LON0 = -36.5, -72.2
METROS_POR_GRADO = ruta.RADIO_TIERRA_M * math.pi / 180


def km(dx, dy, clave):
    """Punto a `dx` km al este y `dy` km al norte del punto de prueba (aproximación plana, suficiente aquí)."""
    return Punto(clave, LAT0 + dy * 1000 / METROS_POR_GRADO,
                 LON0 + dx * 1000 / (METROS_POR_GRADO * math.cos(math.radians(LAT0))))


ORIGEN = km(0, 0, "origen")


def fuerza_bruta(partida, destino, paradas):
    return min(longitud_m([partida, *orden, destino]) for orden in itertools.permutations(paradas))


def vecino_mas_cercano(partida, destino, paradas):
    return ordenar(partida, destino, paradas, limite=0)  # con límite 0 nunca aplica 2-opt


def claves(orden):
    return [punto.clave for punto in orden.paradas]


def cruza(a, b, c, d):
    def giro(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return giro(a, b, c) * giro(a, b, d) < 0 and giro(c, d, a) * giro(c, d, b) < 0


def tiene_cruces(plano):
    tramos = list(zip(plano, plano[1:]))
    return any(cruza(*tramos[i], *tramos[j]) for i in range(len(tramos)) for j in range(i + 2, len(tramos))
               if not (i == 0 and j == len(tramos) - 1))


class DistanciaTests(SimpleTestCase):
    def test_un_grado_de_latitud_mide_111_19_km(self):
        self.assertAlmostEqual(distancia_m(Punto(1, 0, 0), Punto(2, 1, 0)), 111_194.93, delta=0.01)
        self.assertAlmostEqual(distancia_m(Punto(1, LAT0, LON0), Punto(2, LAT0 + 1, LON0)), 111_194.93, delta=0.01)

    def test_simetrica_y_cero_consigo_misma(self):
        a, b = km(0, 0, 1), km(3.2, -1.7, 2)
        self.assertEqual(distancia_m(a, a), 0)
        self.assertAlmostEqual(distancia_m(a, b), distancia_m(b, a), places=9)
        self.assertAlmostEqual(distancia_m(a, b), math.hypot(3.2, 1.7) * 1000, delta=5)

    def test_largo_de_un_recorrido(self):
        recorrido = [km(0, 0, 1), km(0, 1, 2), km(0, 3, 3)]
        self.assertAlmostEqual(longitud_m(recorrido), 3000, delta=0.01)
        self.assertEqual(longitud_m([recorrido[0]]), 0)

    def test_total_en_km_con_coma_decimal(self):
        self.assertEqual(formatear_km(23_400), "23,4")
        self.assertEqual(formatear_km(23_449), "23,4")
        self.assertEqual(formatear_km(850), "0,8")
        self.assertEqual(formatear_km(0), "0,0")


class OrdenarTests(SimpleTestCase):
    def test_sin_paradas_el_total_es_la_vuelta_desde_la_partida(self):
        partida = km(0, 2, "partida")
        orden = ordenar(partida, ORIGEN, [])
        self.assertEqual(orden.paradas, ())
        self.assertAlmostEqual(orden.total_m, 2000, delta=0.01)
        self.assertEqual(ordenar(ORIGEN, ORIGEN, []).total_m, 0)

    def test_una_y_dos_paradas(self):
        una = ordenar(ORIGEN, ORIGEN, [km(0, 2, 7)])
        self.assertEqual(claves(una), [7])
        self.assertAlmostEqual(una.total_m, 4000, delta=0.01)
        dos = ordenar(ORIGEN, ORIGEN, [km(0, 4, 8), km(0, 1, 9)])
        self.assertEqual(claves(dos), [9, 8])
        self.assertAlmostEqual(dos.total_m, 8000, delta=0.01)

    def test_paradas_sobre_una_linea_a_3_1_y_2_km_quedan_b_c_a(self):
        """Criterio de aceptación de RF-09-02: orden B, C, A y total igual a la ida y vuelta."""
        a, b, c = km(0, 3, "A"), km(0, 1, "B"), km(0, 2, "C")
        orden = ordenar(ORIGEN, ORIGEN, [a, b, c])
        self.assertEqual(claves(orden), ["B", "C", "A"])
        self.assertAlmostEqual(orden.total_m, 6000, delta=0.01)
        self.assertFalse(orden.limite_excedido)

    def test_el_2_opt_corrige_el_cruce_del_vecino_mas_cercano_y_llega_al_optimo(self):
        plano = {1: (2, -2), 2: (-1, -2), 3: (4, 2), 4: (-4, -3)}
        paradas = [km(x, y, clave) for clave, (x, y) in plano.items()]
        cercano = vecino_mas_cercano(ORIGEN, ORIGEN, paradas)
        self.assertEqual(claves(cercano), [2, 1, 3, 4])
        self.assertTrue(tiene_cruces([(0, 0), *[plano[c] for c in claves(cercano)], (0, 0)]))
        mejorado = ordenar(ORIGEN, ORIGEN, paradas)
        self.assertEqual(claves(mejorado), [3, 1, 2, 4])
        self.assertFalse(tiene_cruces([(0, 0), *[plano[c] for c in claves(mejorado)], (0, 0)]))
        self.assertLess(mejorado.total_m, cercano.total_m - 1000)
        self.assertAlmostEqual(mejorado.total_m, fuerza_bruta(ORIGEN, ORIGEN, paradas), places=6)

    def test_casos_construidos_coinciden_con_la_fuerza_bruta(self):
        casos = [
            {1: (2, -2), 2: (-2, -1), 3: (-4, -3), 4: (-2, 4)},
            {1: (1, 1), 2: (-1, 1), 3: (-1, -1), 4: (1, -1), 5: (0, 3)},
            {1: (5, 0), 2: (4, 1), 3: (-3, 2), 4: (-4, -1), 5: (0, -5), 6: (2, -3)},
        ]
        for plano in casos:
            with self.subTest(plano=plano):
                paradas = [km(x, y, clave) for clave, (x, y) in plano.items()]
                orden = ordenar(ORIGEN, ORIGEN, paradas)
                self.assertAlmostEqual(orden.total_m, fuerza_bruta(ORIGEN, ORIGEN, paradas), places=6)

    def test_aleatorios_reproducibles_nunca_peores_que_el_vecino_mas_cercano(self):
        for semilla in range(40):
            azar = Random(semilla)
            paradas = [km(azar.uniform(-10, 10), azar.uniform(-10, 10), clave) for clave in range(azar.randint(1, 7))]
            partida = km(azar.uniform(-3, 3), azar.uniform(-3, 3), "partida")
            with self.subTest(semilla=semilla):
                orden = ordenar(partida, ORIGEN, paradas)
                self.assertCountEqual(claves(orden), [p.clave for p in paradas])
                self.assertAlmostEqual(orden.total_m, longitud_m([partida, *orden.paradas, ORIGEN]), places=6)
                self.assertLessEqual(orden.total_m, vecino_mas_cercano(partida, ORIGEN, paradas).total_m + 1e-6)
                self.assertGreaterEqual(orden.total_m, fuerza_bruta(partida, ORIGEN, paradas) - 1e-6)

    def test_extremos_fijos_cuando_la_partida_no_es_el_destino(self):
        """Desde la última visita registrada (oeste) hasta el CESFAM (este): se avanza de oeste a este."""
        partida = km(-6, 0, "partida")
        paradas = [km(-1, 0.2, 1), km(-5, -0.1, 2), km(-3, 0.1, 3)]
        orden = ordenar(partida, ORIGEN, paradas)
        self.assertEqual(claves(orden), [2, 3, 1])
        self.assertAlmostEqual(orden.total_m, longitud_m([partida, *orden.paradas, ORIGEN]), places=6)

    def test_determinista_y_desempata_por_clave(self):
        # Dos domicilios en el mismo punto y dos equidistantes del origen.
        paradas = [km(0, 2, 30), km(0, 2, 10), km(1, 0, 21), km(-1, 0, 20)]
        primero = ordenar(ORIGEN, ORIGEN, paradas)
        for permutacion in itertools.permutations(paradas):
            self.assertEqual(claves(ordenar(ORIGEN, ORIGEN, list(permutacion))), claves(primero))
        posiciones = claves(primero)
        self.assertEqual(posiciones[0], 20)  # equidistantes: gana la clave menor
        self.assertLess(posiciones.index(10), posiciones.index(30))  # mismo punto: la clave menor va antes

    def test_limite_de_paradas_para_el_2_opt(self):
        azar = Random(200)
        paradas = [km(azar.uniform(-15, 15), azar.uniform(-15, 15), clave) for clave in range(LIMITE_2OPT + 1)]
        con_limite = ordenar(ORIGEN, ORIGEN, paradas[:LIMITE_2OPT])
        self.assertFalse(con_limite.limite_excedido)
        self.assertLessEqual(con_limite.total_m, vecino_mas_cercano(ORIGEN, ORIGEN, paradas[:LIMITE_2OPT]).total_m)
        excedido = ordenar(ORIGEN, ORIGEN, paradas)
        self.assertTrue(excedido.limite_excedido)
        self.assertEqual(claves(excedido), claves(vecino_mas_cercano(ORIGEN, ORIGEN, paradas)))
        self.assertEqual(LIMITE_2OPT, 200)


class InsertarTests(SimpleTestCase):
    def setUp(self):
        # Recorrido en cuadrado: origen → A (norte) → B (noreste) → C (este) → origen.
        self.secuencia = [km(0, 4, "A"), km(4, 4, "B"), km(4, 0, "C")]

    def test_inserta_al_inicio_en_medio_y_al_final(self):
        self.assertEqual(insertar(self.secuencia, ORIGEN, ORIGEN, km(-0.1, 2, "nueva")), 0)
        self.assertEqual(insertar(self.secuencia, ORIGEN, ORIGEN, km(2, 4.1, "nueva")), 1)
        self.assertEqual(insertar(self.secuencia, ORIGEN, ORIGEN, km(4.1, 2, "nueva")), 2)
        self.assertEqual(insertar(self.secuencia, ORIGEN, ORIGEN, km(2, -0.1, "nueva")), 3)

    def test_con_partida_distinta_del_destino(self):
        partida = km(0, 8, "partida")
        secuencia = [km(0, 6, "C"), km(0, 4, "B"), km(0, 2, "A")]
        self.assertEqual(insertar(secuencia, partida, ORIGEN, km(0, 7, "nueva")), 0)
        self.assertEqual(insertar(secuencia, partida, ORIGEN, km(0, 1, "nueva")), 3)

    def test_secuencia_vacia_y_empate_elige_el_primer_indice(self):
        self.assertEqual(insertar([], ORIGEN, ORIGEN, km(1, 1, "nueva")), 0)
        # Sobre una parada ya existente: costo 0 antes o después de ella; queda antes.
        self.assertEqual(insertar(self.secuencia, ORIGEN, ORIGEN, km(4, 4, "nueva")), 1)


class ModuloPuroTests(SimpleTestCase):
    def test_no_importa_django(self):
        arbol = ast.parse(Path(ruta.__file__).read_text(encoding="utf-8"))
        modulos = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                modulos.update(alias.name.split(".")[0] for alias in nodo.names)
            elif isinstance(nodo, ast.ImportFrom):
                modulos.add((nodo.module or "").split(".")[0])
        self.assertEqual(modulos, {"math", "dataclasses"})
