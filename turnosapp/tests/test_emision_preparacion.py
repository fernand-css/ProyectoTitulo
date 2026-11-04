"""Creación transaccional de preparaciones al emitir turnos."""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase

from recetasapp.models import PreparacionReceta
from turnosapp.models import ContadorTurnosDiario, Turno, TurnoReceta
from turnosapp.tests import test_servicios as servicios


class EmisionPreparacionTests(TestCase):
    setUp = servicios.EmisionTests.setUp
    pacientes = servicios.EmisionTests.pacientes
    recetas = servicios.EmisionTests.recetas
    emitir = servicios.EmisionTests.emitir

    def test_crea_una_preparacion_por_receta_en_el_instante_de_emision(self):
        segunda = self.recetas(self.paciente, "DEMO-PREP-2")
        self.recetas(
            self.paciente, "FUTURA-PREP",
            fecha_inicio=self.fecha + timedelta(days=1),
        )

        resultado = self.emitir()

        turno = Turno.objects.get(numero=resultado.numero)
        preparaciones = list(
            PreparacionReceta.objects.filter(turno_receta__turno=turno)
            .select_related("turno_receta")
        )
        self.assertEqual(len(preparaciones), 2)
        self.assertEqual(
            {p.turno_receta.receta_id for p in preparaciones},
            {self.receta.pk, segunda.pk},
        )
        self.assertTrue(all(p.recibida_en == turno.creado_en for p in preparaciones))
        self.assertTrue(all(p.lista_en is None for p in preparaciones))

    def test_falla_al_crear_preparacion_revierte_turno_y_correlativo(self):
        with patch(
            "turnosapp.services.PreparacionReceta.objects.create",
            side_effect=RuntimeError("fallo sintético de preparación"),
        ):
            with self.assertRaisesMessage(RuntimeError, "fallo sintético"):
                self.emitir()

        self.assertFalse(Turno.objects.exists())
        self.assertFalse(TurnoReceta.objects.exists())
        self.assertFalse(PreparacionReceta.objects.exists())
        self.assertFalse(ContadorTurnosDiario.objects.exists())

    def test_recuperacion_idempotente_no_duplica_preparaciones(self):
        operacion = uuid.uuid4()
        self.emitir(operacion=operacion)

        recuperado = self.emitir(operacion=operacion)

        self.assertTrue(recuperado.recuperado)
        self.assertEqual(Turno.objects.count(), 1)
        self.assertEqual(TurnoReceta.objects.count(), 1)
        self.assertEqual(PreparacionReceta.objects.count(), 1)
        self.assertEqual(ContadorTurnosDiario.objects.get().ultimo_numero, 1)
