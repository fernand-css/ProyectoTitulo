"""Geometría de los gráficos de Recetas: porcentajes, escala, columnas con promedio, tendencia, segmentos y calendario de calor."""

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


class EscalaTests(SimpleTestCase):
    def test_el_techo_es_el_primer_multiplo_del_paso_que_alcanza_el_maximo_con_cuatro_intervalos_o_menos(self):
        casos = {0: (1, 1), 1: (1, 1), 3: (3, 1), 4: (4, 1), 5: (6, 2), 7: (8, 2), 10: (10, 5), 17: (20, 5), 40: (40, 10), 41: (60, 20), 130: (150, 50)}
        for maximo, esperado in casos.items():
            with self.subTest(maximo=maximo):
                techo, paso = graficos.escala(maximo)
                self.assertEqual((techo, paso), esperado)
                self.assertGreaterEqual(techo, max(maximo, 1))
                self.assertLessEqual(techo // paso, 4)


class PromedioMovilTests(SimpleTestCase):
    def test_cada_dia_promedia_los_siete_que_terminan_en_el_y_los_primeros_no_tienen(self):
        valores = [7, 0, 0, 0, 0, 0, 0, 14, 7]
        promedios = graficos.promedio_movil(valores)
        self.assertEqual(promedios[:6], [None] * 6)
        self.assertEqual(promedios[6], 1.0)
        self.assertEqual(promedios[7], 2.0)
        self.assertEqual(promedios[8], 3.0)

    def test_una_serie_corta_no_tiene_promedios(self):
        self.assertEqual(graficos.promedio_movil([1, 2, 3]), [None, None, None])
        self.assertEqual(graficos.promedio_movil([]), [])


class ColumnasTests(SimpleTestCase):
    def serie(self, *valores, inicio=date(2026, 11, 1)):
        return [(inicio + timedelta(days=i), valor) for i, valor in enumerate(valores)]

    def test_una_columna_por_dia_con_ranuras_contiguas_que_cubren_toda_la_zona(self):
        grafico = graficos.columnas(self.serie(*range(30)))
        self.assertEqual(len(grafico["columnas"]), 30)
        zona_x, zona_ancho = float(grafico["zona"]["x"]), float(grafico["zona"]["ancho"])
        siguiente = zona_x
        for columna in grafico["columnas"]:
            self.assertAlmostEqual(float(columna["ranura_x"]), siguiente, delta=0.2)  # cada valor se redondea a 2 decimales
            siguiente += float(columna["ranura_ancho"])
        self.assertAlmostEqual(siguiente, zona_x + zona_ancho, delta=0.5)

    def test_las_columnas_miden_a_lo_mas_24_y_dejan_dos_de_hueco(self):
        pocas = graficos.columnas(self.serie(3, 5))
        self.assertTrue(all(c["ruta"] for c in pocas["columnas"]))
        # Con pocos datos la ranura es ancha, pero la columna se queda en 24: el ancho sale del trazado (de x a x + 24).
        ruta = pocas["columnas"][0]["ruta"]
        x_inicial = float(ruta.split()[0][1:])
        x_final = float(ruta.split("H")[1].split()[0]) + 4  # H termina 4 antes del borde derecho (radio de esquina)
        self.assertAlmostEqual(x_final - x_inicial, 24, delta=0.1)

    def test_los_dias_sin_entregas_no_dibujan_columna_pero_conservan_su_ranura(self):
        grafico = graficos.columnas(self.serie(0, 4, 0))
        self.assertEqual([bool(c["ruta"]) for c in grafico["columnas"]], [False, True, False])
        self.assertEqual(len(grafico["columnas"]), 3)

    def test_la_columna_mas_alta_llega_al_techo_y_la_base_es_recta(self):
        grafico = graficos.columnas(self.serie(0, 4, 2))
        ruta = grafico["columnas"][1]["ruta"]
        self.assertTrue(ruta.startswith("M") and ruta.endswith("Z"))
        # Esquinas redondeadas solo arriba: dos curvas Q y la base con un único cierre.
        self.assertEqual(ruta.count("Q"), 2)
        self.assertEqual(grafico["marcas_y"][-1]["etiqueta"], 4)

    def test_el_eje_va_de_cero_al_techo(self):
        marcas = graficos.columnas(self.serie(0, 6, 0, 3))["marcas_y"]
        self.assertEqual([m["etiqueta"] for m in marcas], [0, 2, 4, 6])
        ys = [float(m["y"]) for m in marcas]
        self.assertEqual(ys, sorted(ys, reverse=True))

    def test_el_promedio_se_dibuja_solo_donde_existe_y_cuenta_para_el_techo(self):
        grafico = graficos.columnas(self.serie(1, 1, 1), promedios=[None, 9.0, 1.0])
        self.assertTrue(grafico["ruta_promedio"].startswith("M"))
        self.assertEqual(grafico["ruta_promedio"].count("L"), 1)
        self.assertGreaterEqual(grafico["marcas_y"][-1]["etiqueta"], 9)
        self.assertEqual(graficos.columnas(self.serie(1, 2, 3))["ruta_promedio"], "")

    def test_etiquetas_de_fecha_incluyen_primera_y_ultima_y_no_son_mas_de_seis(self):
        for n in (1, 2, 5, 6, 7, 14, 30, 90):
            with self.subTest(n=n):
                grafico = graficos.columnas(self.serie(*([1] * n)))
                fechas = [m["fecha"] for m in grafico["marcas_x"]]
                self.assertLessEqual(len(fechas), 6)
                self.assertEqual((fechas[0], fechas[-1]), (date(2026, 11, 1), date(2026, 11, 1) + timedelta(days=n - 1)))

    def test_serie_vacia_o_sin_entregas_no_falla(self):
        vacia = graficos.columnas([])
        self.assertEqual((vacia["columnas"], vacia["total"], vacia["maximo"], vacia["dia_maximo"]), ([], 0, 0, None))
        plana = graficos.columnas(self.serie(0, 0, 0))
        self.assertEqual((plana["total"], plana["dia_maximo"]), (0, None))
        self.assertEqual(plana["marcas_y"][-1]["etiqueta"], 1)

    def test_resume_total_maximo_dia_del_maximo_y_ultimo_promedio(self):
        grafico = graficos.columnas(self.serie(1, 5, 2, 5), promedios=[None, 2.0, 3.0, 4.0])
        self.assertEqual((grafico["total"], grafico["maximo"], grafico["dia_maximo"]), (13, 5, date(2026, 11, 2)))
        self.assertEqual(grafico["ultimo_promedio"], 4.0)

    def test_coordenadas_con_punto_decimal(self):
        grafico = graficos.columnas(self.serie(1, 3, 2, 5, 4), promedios=[None, None, 2.0, 2.5, 3.5])
        textos = [grafico["ruta_promedio"], grafico["zona"]["x"], grafico["zona"]["ancho"]]
        for columna in grafico["columnas"]:
            textos += [columna["ruta"], columna["ranura_x"], columna["ranura_ancho"]]
        for marca in grafico["marcas_y"] + grafico["marcas_x"]:
            textos += [marca["y"] if "y" in marca else marca["x"]]
        self.assertTrue(all("," not in texto for texto in textos))


class TendenciaTests(SimpleTestCase):
    def test_un_punto_por_dato_dentro_del_cuadro_y_el_ultimo_marcado(self):
        tendencia = graficos.tendencia([0, 5, 2, 8, 3])
        self.assertEqual(tendencia["ruta"].count("L"), 4)
        ultimo = tendencia["ultimo"]
        self.assertTrue(0 <= float(ultimo["x"]) <= tendencia["ancho"] and 0 <= float(ultimo["y"]) <= tendencia["alto"])

    def test_sin_variacion_la_linea_es_plana_y_sin_datos_no_hay_linea(self):
        plana = graficos.tendencia([0, 0, 0, 0])
        ys = {parte.split()[1] for parte in plana["ruta"].replace("M", "").split("L")}
        self.assertEqual(len(ys), 1)
        vacia = graficos.tendencia([])
        self.assertEqual((vacia["ruta"], vacia["ultimo"]), ("", None))
        self.assertEqual(graficos.tendencia([3])["ruta"], "")


class SegmentosTests(SimpleTestCase):
    def partes(self, *cantidades):
        return [{"clave": f"c{i}", "cantidad": n} for i, n in enumerate(cantidades)]

    def test_cada_parte_trae_su_porcentaje_entero_y_suman_cien(self):
        partes = graficos.segmentos(self.partes(3, 1, 1, 1))
        self.assertEqual([p["porcentaje"] for p in partes], [50, 17, 17, 16])
        self.assertEqual(sum(p["porcentaje"] for p in partes), 100)

    def test_las_partes_en_cero_no_se_dibujan_pero_siguen_en_la_leyenda(self):
        partes = graficos.segmentos(self.partes(4, 0, 6))
        self.assertEqual([p["visible"] for p in partes], [True, False, True])
        self.assertEqual(partes[1]["porcentaje"], 0)

    def test_sin_datos_no_hay_partes_visibles(self):
        self.assertFalse(any(p["visible"] for p in graficos.segmentos(self.partes(0, 0))))


class CalorTests(SimpleTestCase):
    HOY = date(2026, 11, 4)  # miércoles; la semana empieza el lunes 2

    def test_cortes_son_cinco_o_menos_y_con_pocos_valores_son_los_propios_valores(self):
        self.assertEqual(graficos.cortes_de_calor(0), [])
        self.assertEqual(graficos.cortes_de_calor(1), [1])
        self.assertEqual(graficos.cortes_de_calor(3), [1, 2, 3])
        self.assertEqual(graficos.cortes_de_calor(5), [1, 2, 3, 4, 5])
        self.assertEqual(graficos.cortes_de_calor(10), [2, 4, 6, 8, 10])
        self.assertEqual(graficos.cortes_de_calor(7), [2, 3, 5, 6, 7])
        for maximo in range(1, 200):
            cortes = graficos.cortes_de_calor(maximo)
            self.assertLessEqual(len(cortes), 5)
            self.assertEqual(cortes[-1], maximo)
            self.assertEqual(cortes, sorted(set(cortes)))

    def test_doce_semanas_de_lunes_a_domingo_desde_la_semana_de_hoy(self):
        calor = graficos.mapa_calor({}, self.HOY)
        self.assertEqual(len(calor["semanas"]), 12)
        self.assertEqual(calor["semanas"][0]["lunes"], date(2026, 11, 2))
        self.assertEqual(calor["semanas"][1]["lunes"], date(2026, 11, 9))
        for semana in calor["semanas"]:
            self.assertEqual([d["fecha"].weekday() for d in semana["dias"]], list(range(7)))

    def test_los_dias_anteriores_a_hoy_quedan_en_blanco_aunque_haya_datos(self):
        calor = graficos.mapa_calor({date(2026, 11, 2): 9, date(2026, 11, 4): 2}, self.HOY)
        primera = calor["semanas"][0]["dias"]
        self.assertEqual([d["pasado"] for d in primera], [True, True, False, False, False, False, False])
        self.assertEqual(primera[0]["valor"], 0)
        self.assertEqual(primera[2]["valor"], 2)
        self.assertTrue(primera[2]["es_hoy"])
        self.assertEqual(calor["total"], 2)

    def test_cada_dia_cae_en_el_tono_de_su_tramo_y_la_leyenda_describe_los_tramos(self):
        conteos = {self.HOY: 1, self.HOY + timedelta(days=1): 4, self.HOY + timedelta(days=2): 10}
        calor = graficos.mapa_calor(conteos, self.HOY)
        dias = {d["fecha"]: d for semana in calor["semanas"] for d in semana["dias"]}
        self.assertEqual([dias[self.HOY + timedelta(days=i)]["tono"] for i in range(3)], [1, 2, 5])
        self.assertEqual(dias[self.HOY + timedelta(days=3)]["tono"], 0)
        self.assertEqual(calor["leyenda"], [
            {"tono": 1, "desde": 1, "hasta": 2}, {"tono": 2, "desde": 3, "hasta": 4}, {"tono": 3, "desde": 5, "hasta": 6},
            {"tono": 4, "desde": 7, "hasta": 8}, {"tono": 5, "desde": 9, "hasta": 10},
        ])

    def test_lo_que_cae_despues_de_las_doce_semanas_no_cuenta(self):
        lejos = self.HOY + timedelta(days=7 * 12)
        calor = graficos.mapa_calor({lejos: 3, self.HOY: 1}, self.HOY)
        self.assertEqual((calor["total"], calor["maximo"]), (1, 1))

    def test_sin_vencimientos_no_hay_tonos_ni_leyenda(self):
        calor = graficos.mapa_calor({}, self.HOY)
        self.assertEqual((calor["total"], calor["maximo"], calor["cortes"], calor["leyenda"]), (0, 0, [], []))
        self.assertTrue(all(d["tono"] == 0 for semana in calor["semanas"] for d in semana["dias"]))
