"""Integridad de los registros de preparación con datos sintéticos."""

from datetime import date, timedelta
from random import Random

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import Paciente, PreparacionReceta, Receta
from turnosapp.models import Turno, TurnoReceta


class PreparacionRecetaModelTests(TestCase):
    def setUp(self):
        rut = generar_ruts(1, Random(807))[0]
        self.paciente = Paciente.objects.create(
            rut=rut, nombres="Paciente sintético", apellidos="Demostración",
            fecha_nacimiento=date(1980, 1, 1),
        )
        hoy = timezone.localdate()
        self.receta = Receta.objects.create(
            paciente=self.paciente, codigo="PREP-MODELO-001", fecha_inicio=hoy,
            fecha_fin_exclusiva=hoy + timedelta(days=30), vigencia_meses=1,
            max_entregas=3,
        )
        self.turno = Turno.objects.create(
            paciente=self.paciente, fecha=hoy, numero=1, tipo_atencion="general",
        )
        self.vinculo = TurnoReceta.objects.create(turno=self.turno, receta=self.receta)

    def test_preparacion_nace_sin_marca_y_es_unica_por_vinculo(self):
        recibida = timezone.now()
        preparacion = PreparacionReceta.objects.create(
            turno_receta=self.vinculo, recibida_en=recibida,
        )
        self.assertEqual(preparacion.recibida_en, recibida)
        self.assertIsNone(preparacion.lista_en)
        self.assertIsNone(preparacion.lista_por_id)
        self.assertIsNone(preparacion.inicio_medido)
        self.assertIsNone(preparacion.duracion_segundos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PreparacionReceta.objects.create(turno_receta=self.vinculo, recibida_en=recibida)

    def test_marca_requiere_todos_los_datos_del_intervalo(self):
        usuario = get_user_model().objects.create_user(username="tecnico-preparacion")
        recibida = timezone.now()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PreparacionReceta.objects.create(
                turno_receta=self.vinculo, recibida_en=recibida, lista_en=recibida,
            )

        completa = PreparacionReceta.objects.create(
            turno_receta=self.vinculo, recibida_en=recibida, lista_en=recibida,
            lista_por=usuario, inicio_medido=recibida, duracion_segundos=0,
        )
        self.assertEqual(completa.duracion_segundos, 0)

    def test_inicio_medido_no_puede_ser_posterior_a_lista(self):
        usuario = get_user_model().objects.create_user(username="tecnico-intervalo")
        recibida = timezone.now()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PreparacionReceta.objects.create(
                turno_receta=self.vinculo, recibida_en=recibida,
                lista_en=recibida, lista_por=usuario,
                inicio_medido=recibida + timedelta(seconds=1), duracion_segundos=0,
            )
