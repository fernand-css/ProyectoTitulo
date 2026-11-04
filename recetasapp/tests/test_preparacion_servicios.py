"""Marcado, corrección, permisos y auditoría de preparaciones."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from recetasapp.models import EntregaReceta, PreparacionReceta
from recetasapp.services import deshacer_lista, marcar_lista
from recetasapp.tests.ayudas import actores
from turnosapp.tests import test_servicios as emision
from turnosapp.models import Turno


class PreparacionServiciosTests(TestCase):
    setUp = emision.EmisionTests.setUp
    pacientes = emision.EmisionTests.pacientes
    recetas = emision.EmisionTests.recetas
    emitir = emision.EmisionTests.emitir

    def preparar(self):
        self.recetas(self.paciente, "PREPARACION-SEGUNDA")
        self.emitir()
        self.actor = actores()
        self.preparaciones = list(
            PreparacionReceta.objects.filter(turno_receta__turno__paciente=self.paciente)
            .order_by("pk")
        )
        PreparacionReceta.objects.filter(pk__in=[p.pk for p in self.preparaciones]).update(
            recibida_en=self.instante(9, 55),
        )

    @staticmethod
    def instante(hora, minuto=0):
        return datetime(2026, 11, 2, hora, minuto, tzinfo=ZoneInfo("America/Santiago"))

    def test_marca_idempotente_y_mide_desde_recepcion_y_marca_anterior(self):
        self.preparar()
        primera, segunda = self.preparaciones
        PreparacionReceta.objects.filter(pk=primera.pk).update(recibida_en=self.instante(9, 55))
        PreparacionReceta.objects.filter(pk=segunda.pk).update(recibida_en=self.instante(9, 50))

        with patch("recetasapp.services.timezone.now", return_value=self.instante(10)):
            marcada = marcar_lista(self.actor["tecnico"], primera.pk)
        self.assertEqual(marcada.inicio_medido, self.instante(9, 55))
        self.assertEqual(marcada.duracion_segundos, 300)

        with patch("recetasapp.services.timezone.now", return_value=self.instante(10, 12)):
            segunda_marcada = marcar_lista(self.actor["tecnico"], segunda.pk)
        self.assertEqual(segunda_marcada.inicio_medido, self.instante(10))
        self.assertEqual(segunda_marcada.duracion_segundos, 720)

        auditorias = RegistroAuditoria.objects.filter(accion="preparacion.lista")
        self.assertEqual(auditorias.count(), 2)
        self.assertTrue(all(a.objeto_id not in (self.paciente.rut, self.paciente.nombres) for a in auditorias))

    def test_repite_marca_y_conserva_intervalo_original(self):
        self.preparar()
        preparacion = self.preparaciones[0]
        PreparacionReceta.objects.filter(pk=preparacion.pk).update(recibida_en=self.instante(9, 55))
        with patch("recetasapp.services.timezone.now", return_value=self.instante(10)):
            original = marcar_lista(self.actor["tecnico"], preparacion.pk)
        with patch("recetasapp.services.timezone.now", return_value=self.instante(10, 10)):
            repetida = marcar_lista(self.actor["tecnico"], preparacion.pk)
        self.assertEqual(repetida.lista_en, original.lista_en)
        self.assertEqual(repetida.duracion_segundos, 300)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="preparacion.lista").count(), 1)

    def test_corregir_descarta_intervalo_y_audita(self):
        self.preparar()
        preparacion = self.preparaciones[0]
        with patch("recetasapp.services.timezone.now", return_value=self.instante(10)):
            marcar_lista(self.actor["qf"], preparacion.pk)
        corregida = deshacer_lista(self.actor["tecnico"], preparacion.pk)
        self.assertIsNone(corregida.lista_en)
        self.assertIsNone(corregida.lista_por_id)
        self.assertIsNone(corregida.inicio_medido)
        self.assertIsNone(corregida.duracion_segundos)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="preparacion.marca_corregida").exists())

    def test_rechaza_turno_inactivo_encargado_y_correccion_ya_entregada(self):
        self.preparar()
        preparacion = self.preparaciones[0]
        with patch("recetasapp.services.timezone.now", return_value=self.instante(10)):
            marcar_lista(self.actor["tecnico"], preparacion.pk)
        EntregaReceta.objects.create(
            turno_receta=preparacion.turno_receta, receta=preparacion.turno_receta.receta,
            numero=1,
        )
        with self.assertRaisesMessage(ValidationError, "ya se entregó"):
            deshacer_lista(self.actor["tecnico"], preparacion.pk)
        with self.assertRaises(PermissionDenied):
            marcar_lista(self.actor["encargado"], self.preparaciones[1].pk)

        Turno.objects.filter(pk=preparacion.turno_receta.turno_id).update(
            estado="ausente", cerrado_en=self.instante(11),
        )
        with self.assertRaisesMessage(ValidationError, "ya no está activa"):
            deshacer_lista(self.actor["tecnico"], preparacion.pk)

    def test_falla_de_auditoria_revierte_la_marca(self):
        self.preparar()
        with patch("recetasapp.services.registrar_accion", side_effect=RuntimeError("fallo de auditoría")):
            with self.assertRaisesMessage(RuntimeError, "fallo de auditoría"):
                marcar_lista(self.actor["tecnico"], self.preparaciones[0].pk)
        preparacion = PreparacionReceta.objects.get(pk=self.preparaciones[0].pk)
        self.assertIsNone(preparacion.lista_en)
