"""Entregas confirmadas en el panel de Indicadores: por día con promedio de 7 días, por semana y por tipo."""

import re
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from recetasapp.models import EntregaReceta
from indicadoresapp import entregas
from indicadoresapp.mermas import CRONICO, GENERAL, TODOS, Periodo
from .ayudas import equipo, hoy, instante, paciente, receta

PANEL = reverse("indicadoresapp:mermas")


class EntregasTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.cronica = receta(paciente(cronico=True))
        self.general = receta(paciente(cronico=False))
        self.numero = 0

    def entregar(self, receta_, dias_atras, cantidad=1):
        """Entregas con fecha propia: `creado_en` lo pone el servidor, así que se fija después."""
        for _ in range(cantidad):
            self.numero += 1
            fila = EntregaReceta.objects.create(receta=receta_, numero=self.numero)
            EntregaReceta.objects.filter(pk=fila.pk).update(creado_en=instante(hoy() - timedelta(days=dias_atras)))

    def periodo(self, dias, tipo=TODOS):
        return Periodo(hoy() - timedelta(days=dias - 1), hoy(), tipo)

    def test_por_dia_cuenta_con_ceros_y_filtra_por_tipo(self):
        self.entregar(self.cronica, 0, 2)
        self.entregar(self.general, 3)
        self.entregar(self.general, 30)  # fuera de 14 días
        datos = entregas.resumir(self.periodo(14))
        self.assertFalse(datos.por_semana)
        self.assertEqual(len(datos.serie), 14)
        por_dia = dict(datos.serie)
        self.assertEqual((por_dia[hoy()], por_dia[hoy() - timedelta(days=3)], por_dia[hoy() - timedelta(days=1)]), (2, 1, 0))
        self.assertEqual(datos.total, 3)
        self.assertEqual(entregas.resumir(self.periodo(14, CRONICO)).total, 2)
        self.assertEqual(entregas.resumir(self.periodo(14, GENERAL)).total, 1)

    def test_el_promedio_de_siete_dias_incluye_los_dias_anteriores_al_periodo(self):
        # Siete entregas tres días antes del período: no se dibujan, pero entran en el promedio de sus primeros días.
        self.entregar(self.general, 16, 7)
        datos = entregas.resumir(self.periodo(14))
        self.assertEqual(datos.total, 0)
        self.assertTrue(all(promedio is not None for promedio in datos.promedios))
        self.assertEqual((datos.promedios[0], datos.promedios[3], datos.promedios[4]), (1.0, 1.0, 0.0))

    def test_periodos_largos_van_por_semana_sin_promedio(self):
        self.entregar(self.general, 0)
        self.entregar(self.general, 50, 2)
        datos = entregas.resumir(self.periodo(90))
        self.assertTrue(datos.por_semana)
        self.assertEqual(datos.promedios, [])
        self.assertTrue(all(fecha.weekday() == 0 for fecha, _ in datos.serie))
        self.assertEqual(datos.total, 3)

    def test_el_panel_dibuja_la_tarjeta_con_tabla_y_sin_datos_personales(self):
        self.entregar(self.cronica, 0, 2)
        self.entregar(self.general, 1)
        self.client.force_login(self.e["qf"])
        respuesta = self.client.get(PANEL)
        self.assertContains(respuesta, "Entregas confirmadas por día")
        self.assertContains(respuesta, "3 entregas entre el")
        self.assertContains(respuesta, "Promedio de 7 días")
        self.assertContains(respuesta, '<svg class="columnas"')
        html = respuesta.content.decode()
        tarjeta = html[html.index('class="tarjeta mermas-entregas"'):html.index('class="tarjeta mermas-detalle"')]
        self.assertEqual(tarjeta.count('class="ranura"'), 30)
        self.assertNotIn(self.cronica.paciente.rut, tarjeta)
        for atributo in re.findall(r'\b(?:x|y|x1|x2|y1|y2|width|height|viewBox|d)="([^"]*)"', tarjeta):
            self.assertNotIn(",", atributo)
        # Con más de 31 días el gráfico pasa a semanas y deja el promedio.
        semanal = self.client.get(PANEL, {"desde": (hoy() - timedelta(days=89)).isoformat(), "hasta": hoy().isoformat()})
        self.assertContains(semanal, "Entregas confirmadas por semana")
        self.assertNotContains(semanal, "Promedio de 7 días")

    def test_sin_entregas_la_tarjeta_lo_explica(self):
        self.client.force_login(self.e["qf"])
        respuesta = self.client.get(PANEL)
        self.assertContains(respuesta, "No hay entregas confirmadas en este período.")
        self.assertNotContains(respuesta, '<svg class="columnas"')
