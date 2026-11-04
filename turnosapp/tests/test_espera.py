"""Cálculo de espera aproximada con datos de preparación sintéticos."""

from datetime import date, datetime, timedelta
from random import Random
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase

from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import Paciente, PreparacionReceta, Receta
from turnosapp.espera import estimar_espera
from turnosapp.models import TipoAtencionVentanilla, Turno, TurnoReceta, Ventanilla


class EstimarEsperaTests(TestCase):
    def setUp(self):
        self.hoy = date(2026, 11, 3)
        self.ahora = datetime(2026, 11, 3, 9, tzinfo=ZoneInfo("America/Santiago"))
        self.ruts = generar_ruts(12, Random(873))
        self.usuario = get_user_model().objects.create_user(username="ventanilla-espera")
        self.paciente_numero = 0

    def agregar_turno(self, numero, *, lista_en=None, duracion=None):
        self.paciente_numero += 1
        paciente = Paciente.objects.create(
            rut=self.ruts[self.paciente_numero - 1], nombres="Paciente sintético",
            apellidos="Demostración", fecha_nacimiento=date(1980, 1, 1),
        )
        turno = Turno.objects.create(
            paciente=paciente, fecha=self.hoy, numero=numero, tipo_atencion="general",
        )
        receta = Receta.objects.create(
            paciente=paciente, codigo=f"ESPERA-{numero}", fecha_inicio=self.hoy,
            fecha_fin_exclusiva=self.hoy + timedelta(days=30), vigencia_meses=1, max_entregas=2,
        )
        vinculo = TurnoReceta.objects.create(turno=turno, receta=receta)
        if lista_en is None:
            PreparacionReceta.objects.create(turno_receta=vinculo, recibida_en=self.ahora)
        else:
            PreparacionReceta.objects.create(
                turno_receta=vinculo, recibida_en=self.ahora, lista_en=lista_en,
                lista_por=self.usuario, inicio_medido=lista_en - timedelta(seconds=duracion),
                duracion_segundos=duracion,
            )

    def ventana(self, numero):
        tipos = [TipoAtencionVentanilla.objects.get_or_create(codigo="general")[0]]
        ventanilla = Ventanilla.objects.create(
            numero=numero, operador=self.usuario, automatico=True, fecha_activacion=self.hoy,
        )
        ventanilla.tipos.set(tipos)
        return ventanilla

    def test_seis_pendientes_promedio_cuatro_minutos_y_dos_ventanillas_redondea_a_quince(self):
        for i in range(5):
            self.agregar_turno(100 + i, lista_en=self.ahora - timedelta(days=i + 1), duracion=240)
        for i in range(6):
            self.agregar_turno(i + 1)
        self.ventana(1)
        # La unicidad del operador exige un usuario distinto en cada puesto.
        segundo = get_user_model().objects.create_user(username="ventanilla-espera-dos")
        puesto = Ventanilla.objects.create(
            numero=2, operador=segundo, automatico=True, fecha_activacion=self.hoy,
        )
        puesto.tipos.set([TipoAtencionVentanilla.objects.get(codigo="general")])

        estimacion = estimar_espera(self.ahora)

        self.assertEqual((estimacion.pendientes, estimacion.ventanillas, estimacion.promedio_segundos), (6, 2, 240))
        self.assertEqual(estimacion.frase, "Tiempo aproximado de espera: unos 15 minutos.")

    def test_sin_ventanillas_y_menos_de_cinco_minutos(self):
        self.agregar_turno(1)
        sin_puesto = estimar_espera(self.ahora)
        self.assertIsNone(sin_puesto.minutos)
        self.assertEqual(sin_puesto.frase, "No podemos estimar el tiempo de espera. Consulta con el personal.")

        for i in range(5):
            self.agregar_turno(10 + i, lista_en=self.ahora - timedelta(days=i + 1), duracion=60)
        self.ventana(1)
        menos_de_cinco = estimar_espera(self.ahora)
        self.assertEqual(menos_de_cinco.minutos, 0)
        self.assertEqual(menos_de_cinco.frase, "Tiempo aproximado de espera: menos de 5 minutos.")
