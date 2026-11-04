"""Geometría de los gráficos del tablero: porcentajes, anillo, línea, barras y meses."""

from datetime import date, timedelta

from django.test import SimpleTestCase

from recetasapp import graficos


class PorcentajesTests(SimpleTestCase):
    def test_suman_cien_con_el_metodo_del_mayor_resto(self):
        for cantidades in ([1, 1, 1], [3, 1, 1, 1], [36, 2, 3, 4], [7, 7, 7, 7, 7, 7, 7], [1, 99], [5]):
            with self.subTest(cantidades=cantidades):
                self.assertEqual(sum(graficos.porcentajes(cantidades)), 100)

    def test_sin_datos_todo_es_cero_y_los_ceros_siguen_en_cero(self):
        self.assertEqual(graficos.porcentajes([0, 0, 0]), [0, 0, 0])
        self.assertEqual(graficos.porcentajes([]), [])
        self.assertEqual(graficos.porcentajes([4, 0, 6]), [40, 0, 60])


class AnilloTests(SimpleTestCase):
    def partes(self, *cantidades):
        return [{"clave": f"c{i}", "texto": f"Parte {i}", "cantidad": n} for i, n in enumerate(cantidades)]

    def test_los_arcos_son_consecutivos_y_cubren_el_anillo_menos_los_huecos(self):
        anillo = graficos.anillo(self.partes(3, 1, 1, 1))
        self.assertEqual(anillo["total"], 6)
        arcos = anillo["partes"]
        self.assertEqual([a["inicio"] for a in arcos], ["0", "50", "66.67", "83.33"])
        self.assertEqual([a["trazo"] for a in arcos], ["49.2", "15.87", "15.87", "15.87"])
        self.assertEqual([a["indice"] for a in arcos], [0, 1, 2, 3])

    def test_una_parte_unica_cierra_el_anillo_sin_hueco(self):
        arco = graficos.anillo(self.partes(5, 0, 0))["partes"][0]
        self.assertEqual((arco["inicio"], arco["trazo"]), ("0", "100"))

    def test_las_partes_en_cero_no_se_dibujan_pero_siguen_en_la_leyenda(self):
        anillo = graficos.anillo(self.partes(4, 0, 6))
        self.assertEqual([a["visible"] for a in anillo["partes"]], [True, False, True])
        self.assertEqual([a["porcentaje"] for a in anillo["partes"]], [40, 0, 60])
        # El índice de la animación solo cuenta los arcos visibles, así no queda un retraso vacío.
        self.assertEqual([a["indice"] for a in anillo["partes"] if a["visible"]], [0, 1])

    def test_sin_datos_no_hay_arcos_visibles(self):
        anillo = graficos.anillo(self.partes(0, 0))
        self.assertEqual(anillo["total"], 0)
        self.assertFalse(any(a["visible"] for a in anillo["partes"]))

    def test_los_numeros_salen_como_texto_con_punto(self):
        for arco in graficos.anillo(self.partes(1, 1, 1))["partes"]:
            self.assertIsInstance(arco["trazo"], str)
            self.assertNotIn(",", arco["trazo"] + arco["inicio"])


class LineaTests(SimpleTestCase):
    def serie(self, *valores):
        return [(date(2026, 11, 1) + timedelta(days=i), v) for i, v in enumerate(valores)]

    def test_el_techo_es_un_valor_redondo_con_cuatro_marcas(self):
        for maximo, techo in ((0, 4), (1, 4), (4, 4), (5, 8), (7, 8), (8, 8), (9, 20), (30, 40), (160, 200)):
            with self.subTest(maximo=maximo):
                self.assertEqual(graficos._techo(maximo)[0], techo)
                self.assertGreaterEqual(graficos._techo(maximo)[0], maximo)

    def test_un_punto_por_dato_y_la_curva_no_sale_del_rango(self):
        linea = graficos.linea(self.serie(0, 6, 0, 3))
        self.assertEqual(len(linea["puntos"]), 4)
        self.assertEqual((linea["total"], linea["maximo"]), (9, 6))
        self.assertEqual(linea["dia_maximo"], date(2026, 11, 2))
        ys = [float(p["y"]) for p in linea["puntos"]]
        # Mayor valor = más arriba (y menor); y ningún punto cae fuera del área del gráfico.
        self.assertEqual(ys.index(min(ys)), 1)
        self.assertTrue(all(0 <= y <= linea["alto"] for y in ys))
        self.assertTrue(linea["ruta"].startswith("M"))
        self.assertTrue(linea["area"].endswith("Z"))

    def test_las_marcas_del_eje_van_de_cero_al_techo(self):
        marcas = graficos.linea(self.serie(0, 6, 0, 3))["marcas_y"]
        self.assertEqual([m["etiqueta"] for m in marcas], [0, 2, 4, 6, 8])
        ys = [float(m["y"]) for m in marcas]
        self.assertEqual(ys, sorted(ys, reverse=True))

    def test_etiquetas_de_fecha_incluyen_primera_y_ultima_y_no_son_mas_de_seis(self):
        for n in (1, 5, 7, 30, 90):
            with self.subTest(dias=n):
                linea = graficos.linea(self.serie(*([1] * n)))
                self.assertLessEqual(len(linea["marcas_x"]), 6)
                self.assertEqual(linea["marcas_x"][0]["fecha"], date(2026, 11, 1))
                self.assertEqual(linea["marcas_x"][-1]["fecha"], date(2026, 11, 1) + timedelta(days=n - 1))

    def test_serie_vacia_o_sin_entregas_no_falla(self):
        vacia = graficos.linea([])
        self.assertEqual((vacia["ruta"], vacia["puntos"], vacia["ultimo"], vacia["total"]), ("", [], None, 0))
        plana = graficos.linea(self.serie(0, 0, 0))
        self.assertEqual((plana["total"], plana["dia_maximo"]), (0, None))

    def test_coordenadas_con_punto_decimal(self):
        linea = graficos.linea(self.serie(1, 3, 2, 5, 4))
        self.assertNotIn(",", linea["ruta"] + linea["area"])
        for punto in linea["puntos"]:
            self.assertNotIn(",", punto["x"] + punto["y"])


class BarrasTests(SimpleTestCase):
    def test_la_altura_es_proporcional_al_mayor(self):
        barras = graficos.barras([("nov", 4), ("dic", 2), ("ene", 0), ("feb", 8)])
        self.assertEqual([b["altura"] for b in barras["barras"]], ["50", "25", "0", "100"])
        self.assertEqual((barras["maximo"], barras["total"]), (8, 14))
        self.assertEqual([b["indice"] for b in barras["barras"]], [0, 1, 2, 3])

    def test_sin_datos_todas_miden_cero(self):
        barras = graficos.barras([("nov", 0), ("dic", 0)])
        self.assertEqual([b["altura"] for b in barras["barras"]], ["0", "0"])
        self.assertEqual(barras["total"], 0)


class MesesTests(SimpleTestCase):
    def test_sumar_meses_cruza_anios_en_ambos_sentidos(self):
        self.assertEqual(graficos.sumar_meses(date(2026, 11, 1), 0), date(2026, 11, 1))
        self.assertEqual(graficos.sumar_meses(date(2026, 11, 1), 2), date(2027, 1, 1))
        self.assertEqual(graficos.sumar_meses(date(2026, 11, 1), 14), date(2028, 1, 1))
        self.assertEqual(graficos.sumar_meses(date(2026, 1, 1), -1), date(2025, 12, 1))
        self.assertEqual(graficos.sumar_meses(date(2026, 3, 1), -15), date(2024, 12, 1))
