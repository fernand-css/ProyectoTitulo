"""Gráficos del panel de mermas: calendario, barras, columnas apiladas, barra al 100 % y la frase del día."""

import uuid
from datetime import date, timedelta

from django.test import SimpleTestCase, TestCase

from indicadoresapp import graficos, mermas
from recetasapp.services import retirar_preparado
from .ayudas import equipo, hoy, paciente, preparada


class CalendarioTests(SimpleTestCase):
    def test_semanas_de_lunes_a_domingo_con_niveles(self):
        inicio, fin = date(2026, 10, 21), date(2026, 11, 3)  # miércoles a martes
        serie = [(inicio + timedelta(days=i), 0) for i in range((fin - inicio).days + 1)]
        serie[0] = (inicio, 8)
        serie[1] = (inicio + timedelta(days=1), 1)
        datos = graficos.calendario(serie, inicio, fin)
        self.assertTrue(all(len(semana) == 7 for semana in datos["semanas"]))
        primera = datos["semanas"][0]
        self.assertEqual(primera[:2], [None, None])
        self.assertEqual((primera[2]["valor"], primera[2]["nivel"], primera[2]["etiqueta"]), (8, 5, "21 oct"))
        self.assertEqual(primera[3]["nivel"], 1)
        self.assertTrue(primera[5]["fin_de_semana"])
        noviembre = [c for semana in datos["semanas"] for c in semana if c and c["fecha"] == date(2026, 11, 1)][0]
        self.assertEqual(noviembre["etiqueta"], "1 nov")
        self.assertEqual(datos["semanas"][-1][-1], None)
        self.assertFalse(datos["con_futuro"])

    def test_mes_en_curso_marca_los_dias_que_aun_no_llegan(self):
        inicio, fin, ultimo = date(2026, 11, 1), date(2026, 11, 25), date(2026, 11, 30)
        serie = [(inicio + timedelta(days=i), 1) for i in range(25)]
        datos = graficos.calendario(serie, inicio, fin, ultimo)
        celdas = [c for semana in datos["semanas"] for c in semana if c]
        futuros = [c["fecha"].day for c in celdas if c["futuro"]]
        self.assertEqual(futuros, [26, 27, 28, 29, 30])
        self.assertTrue(datos["con_futuro"])
        self.assertIn("aún no", [c for c in celdas if c["futuro"]][0]["tip"])

    def test_frase_del_dia_que_destaca(self):
        self.assertEqual(graficos.frase_dia_semana([32, 10, 9, 8, 9, 0, 0], 68, 30),
                         "Los lunes suman 32 de las 68 recetas.")
        self.assertEqual(graficos.frase_dia_semana([5, 5, 0, 0, 0, 0, 0], 10, 30), "")
        self.assertEqual(graficos.frase_dia_semana([5, 1, 0, 0, 0, 0, 0], 6, 7), "")


class BarrasTests(SimpleTestCase):
    def test_ancho_relativo_orden_y_porcentaje(self):
        barras = graficos.barras([("a", "A", 2), ("b", "B", 8), ("c", "C", 0)], ordenar=True)
        self.assertEqual([b["clave"] for b in barras], ["b", "a", "c"])
        self.assertEqual([b["ancho"] for b in barras], ["100.0", "25.0", "0.0"])
        self.assertEqual([b["porcentaje"] for b in barras], ["80", "20", "0"])
        iguales = graficos.barras([("a", "A", 3), ("b", "B", 3), ("c", "C", 3)])
        self.assertEqual([b["porcentaje"] for b in iguales], ["33,3", "33,3", "33,3"])

    def test_division_suma_cien(self):
        partes = graficos.division([("cronico", "Crónico", 2), ("general", "General", 1)])
        self.assertEqual([p["porcentaje"] for p in partes], [67, 33])

    def test_barra_al_100_suma_cien_y_marca_las_vacias(self):
        partes = graficos.barra_100([("a", "A", 5), ("b", "B", 1), ("c", "C", 0), ("d", "D", 1), ("e", "E", 1)])
        self.assertEqual(sum(p["porcentaje"] for p in partes), 100)
        self.assertEqual([p["visible"] for p in partes], [True, True, False, True, True])
        self.assertEqual([p["orden"] for p in partes], [1, 2, 3, 4, 5])


class ColumnasApiladasTests(SimpleTestCase):
    def test_partes_de_abajo_hacia_arriba_con_extremo_redondeado_solo_arriba(self):
        serie = [(date(2026, 11, 1), [3, 1]), (date(2026, 11, 2), [0, 2]), (date(2026, 11, 3), [0, 0])]
        datos = graficos.columnas_apiladas(serie, ("atencion", "despues"))
        primera, segunda, tercera = datos["columnas"]
        self.assertEqual([p["clave"] for p in primera["partes"]], ["atencion", "despues"])
        self.assertIn("Q", primera["partes"][1]["ruta"])      # la de arriba, redondeada
        self.assertNotIn("Q", primera["partes"][0]["ruta"])   # la de abajo, recta
        self.assertEqual([p["clave"] for p in segunda["partes"]], ["despues"])
        self.assertEqual(tercera["partes"], [])
        self.assertEqual((datos["total"], datos["maximo"], datos["dia_maximo"]), (6, 4, date(2026, 11, 1)))
        self.assertEqual(datos["ruta_promedio"], "")

    def test_promedio_como_linea(self):
        serie = [(date(2026, 11, d), [d, 0]) for d in range(1, 4)]
        datos = graficos.columnas_apiladas(serie, ("a", "b"), [1.0, 1.5, 2.0])
        self.assertTrue(datos["ruta_promedio"].startswith("M"))

    def test_etiquetas_por_granularidad(self):
        fecha = date(2026, 11, 2)
        self.assertEqual(graficos.etiqueta(fecha, "dia"), "2 nov")
        self.assertEqual(graficos.etiqueta(fecha, "semana"), "Semana del 2 nov")
        self.assertEqual(graficos.etiqueta(fecha.replace(day=1), "mes"), "Noviembre 2026")
        self.assertEqual(graficos.marca(fecha.replace(day=1), "mes"), "nov")


class EsperaTests(TestCase):
    def setUp(self):
        self.e = equipo()

    def test_espera_cuenta_solo_las_sin_retirar_por_dias(self):
        preparada(paciente(), dias_atras=1, usuario=self.e["tecnico"])
        preparada(paciente(), dias_atras=20, usuario=self.e["tecnico"])
        tarde = preparada(paciente(), dias_atras=5, usuario=self.e["tecnico"])
        retirar_preparado(self.e["tecnico"], tarde.pk, uuid.uuid4())
        resumen = mermas.resumir(mermas.Periodo(hoy() - timedelta(days=29), hoy()))
        self.assertEqual([c for _, c in resumen.espera], [1, 0, 0, 1, 0])
        self.assertEqual(resumen.mas_de_14, 1)
        self.assertEqual(sum(resumen.por_dia_semana), 2)
        self.assertGreaterEqual(resumen.por_dia_semana[(hoy() - timedelta(days=20)).weekday()], 1)
