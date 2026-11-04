"""Retiro posterior, vigencia histórica, cupo e idempotencia."""

import uuid
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from recetasapp.models import EntregaReceta, PreparacionReceta, Receta
from recetasapp.services import retirar_preparado
from recetasapp.tests import test_preparacion_servicios as fixture
from recetasapp.tests.ayudas import actores
from turnosapp.models import Turno


class RetiroPreparadoTests(TestCase):
    setUp = fixture.PreparacionServiciosTests.setUp
    pacientes = fixture.PreparacionServiciosTests.pacientes
    recetas = fixture.PreparacionServiciosTests.recetas
    emitir = fixture.PreparacionServiciosTests.emitir

    def preparar_pendiente(self):
        self.recetas(self.paciente, "RECETA-PENDIENTE-2")
        self.emitir()
        self.actor = actores()
        self.preparacion = PreparacionReceta.objects.filter(
            turno_receta__turno__paciente=self.paciente,
        ).order_by("pk").first()
        marca = datetime(2026, 11, 2, 10, tzinfo=ZoneInfo("America/Santiago"))
        PreparacionReceta.objects.filter(pk=self.preparacion.pk).update(
            recibida_en=marca - timedelta(minutes=5), lista_en=marca,
            lista_por=self.actor["qf"], inicio_medido=marca - timedelta(minutes=5),
            duracion_segundos=300,
        )
        Turno.objects.filter(pk=self.preparacion.turno_receta.turno_id).update(
            estado="ausente", cerrado_en=marca + timedelta(minutes=1),
        )
        # La receta ya venció hoy, pero estaba vigente el día de preparación.
        Receta.objects.filter(pk=self.preparacion.turno_receta.receta_id).update(
            fecha_fin_exclusiva=date(2026, 11, 3),
        )
        self.preparacion.refresh_from_db()

    def test_retiro_qf_usa_fecha_de_preparacion_y_repeticion_no_duplica(self):
        self.preparar_pendiente()
        operacion = uuid.uuid4()
        primera = retirar_preparado(self.actor["qf"], self.preparacion.pk, operacion)
        repetida = retirar_preparado(self.actor["qf"], self.preparacion.pk, operacion)

        self.assertEqual(primera.pk, repetida.pk)
        self.assertEqual(primera.turno_receta_id, self.preparacion.turno_receta_id)
        self.assertEqual(primera.creado_por_id, self.actor["qf"].pk)
        self.assertEqual(EntregaReceta.objects.count(), 1)
        receta = Receta.objects.get(pk=primera.receta_id)
        self.assertEqual(receta.entregas_completadas, 1)
        turno = Turno.objects.get(pk=self.preparacion.turno_receta.turno_id)
        self.assertEqual(turno.estado, "ausente")

    def test_cupo_agotado_rechaza_y_conserva_pendiente(self):
        self.preparar_pendiente()
        Receta.objects.filter(pk=self.preparacion.turno_receta.receta_id).update(entregas_completadas=3)
        with self.assertRaisesMessage(ValidationError, "agotó sus entregas"):
            retirar_preparado(self.actor["tecnico"], self.preparacion.pk, uuid.uuid4())
        self.assertFalse(EntregaReceta.objects.exists())
        self.assertTrue(PreparacionReceta.objects.filter(pk=self.preparacion.pk, lista_en__isnull=False).exists())

    def test_actor_no_autorizado_y_preparacion_activa_se_rechazan(self):
        self.preparar_pendiente()
        with self.assertRaises(PermissionDenied):
            retirar_preparado(self.actor["encargado"], self.preparacion.pk, uuid.uuid4())
        Turno.objects.filter(pk=self.preparacion.turno_receta.turno_id).update(
            estado="esperando", cerrado_en=None,
        )
        with self.assertRaisesMessage(ValidationError, "todavía está activo"):
            retirar_preparado(self.actor["tecnico"], self.preparacion.pk, uuid.uuid4())

    def test_falla_de_auditoria_revierte_entrega_y_contador(self):
        self.preparar_pendiente()
        with patch("recetasapp.services.registrar_accion", side_effect=RuntimeError("fallo auditoría retiro")):
            with self.assertRaisesMessage(RuntimeError, "fallo auditoría retiro"):
                retirar_preparado(self.actor["tecnico"], self.preparacion.pk, uuid.uuid4())
        self.assertFalse(EntregaReceta.objects.exists())
        self.assertEqual(Receta.objects.get(pk=self.preparacion.turno_receta.receta_id).entregas_completadas, 0)
