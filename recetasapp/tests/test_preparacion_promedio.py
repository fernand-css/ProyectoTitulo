"""Reglas de ventana, mínimo de muestras y duración máxima."""

from datetime import datetime, timedelta
from random import Random
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase

from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import Paciente, PreparacionReceta, Receta
from recetasapp.preparacion import promedio_preparacion
from turnosapp.models import Turno, TurnoReceta


class PromedioPreparacionTests(TestCase):
    def setUp(self):
        self.ahora = datetime(2026, 11, 3, 12, tzinfo=ZoneInfo("America/Santiago"))
        self.usuario = get_user_model().objects.create_user(username="promedio-sintetico")
        self.paciente = Paciente.objects.create(
            rut=generar_ruts(1, Random(871))[0], nombres="Paciente sintético",
            apellidos="Demostración", fecha_nacimiento=datetime(1980, 1, 1).date(),
        )
        self.turno = Turno.objects.create(
            paciente=self.paciente, fecha=self.ahora.date(), numero=1, tipo_atencion="general",
        )
        self.indice = 0

    def muestra(self, dias, segundos):
        self.indice += 1
        receta = Receta.objects.create(
            paciente=self.paciente, codigo=f"PROMEDIO-{self.indice}",
            fecha_inicio=self.ahora.date(), fecha_fin_exclusiva=self.ahora.date() + timedelta(days=30),
            vigencia_meses=1, max_entregas=2,
        )
        vinculo = TurnoReceta.objects.create(turno=self.turno, receta=receta)
        lista = self.ahora - timedelta(days=dias)
        PreparacionReceta.objects.create(
            turno_receta=vinculo, recibida_en=lista - timedelta(minutes=10),
            lista_en=lista, lista_por=self.usuario,
            inicio_medido=lista - timedelta(seconds=segundos), duracion_segundos=segundos,
        )

    def test_menos_de_cinco_muestras_usa_cinco_minutos(self):
        for _ in range(4):
            self.muestra(1, 120)
        promedio = promedio_preparacion(self.ahora)
        self.assertEqual((promedio.segundos, promedio.muestras, promedio.predeterminado), (300, 4, True))

    def test_quinta_muestra_activa_el_promedio_y_descarta_intervalo_largo(self):
        for _ in range(4):
            self.muestra(1, 120)
        self.muestra(1, 240)
        self.muestra(1, 1860)
        promedio = promedio_preparacion(self.ahora)
        self.assertEqual((promedio.segundos, promedio.muestras, promedio.predeterminado), (144, 5, False))

    def test_ventana_de_catorce_dias_incluye_hasta_el_limite(self):
        for dia in (13, 14, 15, 1, 2):
            self.muestra(dia, 300)
        promedio = promedio_preparacion(self.ahora)
        self.assertEqual(promedio.muestras, 4)
        self.assertTrue(promedio.predeterminado)
