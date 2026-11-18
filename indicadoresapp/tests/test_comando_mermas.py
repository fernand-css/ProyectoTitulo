"""Comando de demostración `generar_mermas_demo` (spec 13): solo simula sin --aplicar y no toca la jornada de hoy."""

from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from indicadoresapp import mermas
from recetasapp.models import PreparacionReceta
from turnosapp.models import Turno
from .ayudas import equipo, hoy, paciente, receta


class GenerarMermasDemoTests(TestCase):
    def setUp(self):
        self.e = equipo()
        for indice in range(30):
            receta(paciente(edad=40 + indice, cronico=indice % 2 == 0))

    def llamar(self, *argumentos):
        salida = StringIO()
        call_command("generar_mermas_demo", *argumentos, stdout=salida)
        return salida.getvalue()

    def test_sin_aplicar_solo_informa(self):
        self.assertIn("Simulación", self.llamar("--dias", "10"))
        self.assertFalse(Turno.objects.exists())

    def test_aplicar_exige_una_cuenta_qf(self):
        with self.assertRaises(CommandError):
            self.llamar("--aplicar")
        with self.assertRaises(CommandError):
            self.llamar("--aplicar", "--cuenta", self.e["tecnico"].username)

    def test_crea_historial_con_merma_y_recuperadas_sin_tocar_hoy(self):
        self.llamar("--aplicar", "--cuenta", self.e["qf"].username, "--dias", "20", "--por-dia", "6", "--recuperadas", "30")
        self.assertTrue(PreparacionReceta.objects.exists())
        self.assertFalse(Turno.objects.filter(fecha=hoy()).exists())
        self.assertFalse(Turno.objects.filter(estado__in=("esperando", "llamado")).exists())
        resumen = mermas.resumir(mermas.periodo_por_omision())
        self.assertGreater(resumen.merma, 0)
        self.assertGreater(resumen.cifras["tarde"], 0)
        self.assertEqual(resumen.merma + resumen.recuperadas, PreparacionReceta.objects.count())

    def test_repetir_numera_despues_de_los_existentes(self):
        argumentos = ("--aplicar", "--cuenta", self.e["qf"].username, "--dias", "3", "--por-dia", "5")
        self.llamar(*argumentos)
        self.llamar(*argumentos, "--semilla", "7")
        self.assertEqual(Turno.objects.count(), PreparacionReceta.objects.count())
