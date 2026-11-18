"""Gráficos del panel de mermas: blíster, calendario, barras y la frase del día de la semana."""

import uuid
from datetime import date, timedelta

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from indicadoresapp import graficos, mermas
from recetasapp.services import retirar_preparado
from .ayudas import equipo, hoy, paciente, preparada


def cifras(sin_retirar=0, en_despacho=0, tarde=0, despacho=0):
    return {"sin_retirar": sin_retirar, "en_despacho": en_despacho, "tarde": tarde, "despacho": despacho}


class BlisterTests(SimpleTestCase):
    def test_un_alveolo_por_receta_en_tiras_de_diez(self):
        datos = graficos.blister(cifras(3, 1, 4, 2))
        self.assertEqual(datos["escala"], 1)
        celdas = [c for tira in datos["tiras"] for c in tira]
        self.assertEqual(celdas, ["sin_retirar"] * 3 + ["en_despacho"] + ["tarde"] * 4 + ["despacho"] * 2)
        self.assertTrue(all(len(tira) == 10 for tira in datos["tiras"]))

    def test_completa_la_ultima_tira_con_alveolos_vacios(self):
        datos = graficos.blister(cifras(13))
        self.assertEqual(datos["tiras"][-1], ["sin_retirar"] * 3 + ["vacio"] * 7)

    def test_sin_recetas_no_hay_blister(self):
        self.assertIsNone(graficos.blister(cifras()))

    def test_muchas_recetas_agrupan_y_ningun_estado_desaparece(self):
        datos = graficos.blister(cifras(900, 1, 500, 3))
        self.assertEqual(datos["escala"], 5)
        celdas = [c for tira in datos["tiras"] for c in tira if c != "vacio"]
        self.assertLessEqual(len(celdas), graficos.MAX_ALVEOLOS + 2)
        self.assertEqual({c for c in celdas}, {"sin_retirar", "en_despacho", "tarde", "despacho"})
        # La leyenda conserva las cifras exactas.
        self.assertEqual([p["cantidad"] for p in datos["leyenda"]], [900, 1, 500, 3])


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

    def test_frase_del_dia_que_destaca(self):
        self.assertEqual(graficos.frase_dia_semana([32, 10, 9, 8, 9, 0, 0], 68, 30),
                         "Los lunes suman 32 de las 68 recetas.")
        self.assertEqual(graficos.frase_dia_semana([5, 5, 0, 0, 0, 0, 0], 10, 30), "")
        self.assertEqual(graficos.frase_dia_semana([5, 1, 0, 0, 0, 0, 0], 6, 7), "")


class BarrasTests(SimpleTestCase):
    def test_ancho_relativo_y_orden(self):
        barras = graficos.barras([("a", "A", 2), ("b", "B", 8), ("c", "C", 0)], ordenar=True)
        self.assertEqual([b["clave"] for b in barras], ["b", "a", "c"])
        self.assertEqual([b["ancho"] for b in barras], ["100.0", "25.0", "0.0"])

    def test_division_suma_cien(self):
        partes = graficos.division([("cronico", "Crónico", 2), ("general", "General", 1)])
        self.assertEqual([p["porcentaje"] for p in partes], [67, 33])


class EsperaYPanelTests(TestCase):
    def setUp(self):
        self.e = equipo()

    def test_espera_cuenta_solo_las_sin_retirar_por_dias(self):
        preparada(paciente(), dias_atras=1, usuario=self.e["tecnico"])
        preparada(paciente(), dias_atras=20, usuario=self.e["tecnico"])
        tarde = preparada(paciente(), dias_atras=5, usuario=self.e["tecnico"])
        retirar_preparado(self.e["tecnico"], tarde.pk, uuid.uuid4())
        resumen = mermas.resumir(mermas.periodo_por_omision())
        self.assertEqual([c for _, c in resumen.espera], [1, 0, 0, 1, 0])
        self.assertEqual(sum(resumen.por_dia_semana), 2)
        self.assertEqual(resumen.por_dia_semana[(hoy() - timedelta(days=20)).weekday()] >= 1, True)

    def test_panel_muestra_blister_y_calendario(self):
        preparada(paciente(), dias_atras=2, usuario=self.e["tecnico"])
        self.client.force_login(self.e["qf"])
        respuesta = self.client.get(reverse("indicadoresapp:mermas"))
        self.assertContains(respuesta, "Queda 1 receta por entregar")
        self.assertContains(respuesta, "alveolo-sin_retirar")
        self.assertContains(respuesta, "calendario-celda")
        self.assertContains(respuesta, "Cuánto llevan en el estante")
        self.assertContains(respuesta, "2 días")
