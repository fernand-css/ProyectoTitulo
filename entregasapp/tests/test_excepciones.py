"""RF-08-02: excepciones de reparto inscritas por la Q.F."""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from entregasapp.consultas import es_elegible
from entregasapp.models import Entrega, InscripcionReparto
from entregasapp.services import inscribir_excepcion, programar_entrega, retirar_excepcion
from .ayudas import equipo, hoy, paciente, receta


class ExcepcionesTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.cronico = paciente(edad=60, cronico=True)

    def test_inscribir_una_vez_y_rechazar_duplicado_y_ya_elegible(self):
        inscripcion = inscribir_excepcion(self.qf, self.cronico.pk, "sin_red_apoyo", "Vive sola")
        self.assertEqual((inscripcion.motivo, inscripcion.nota, inscripcion.creado_por), ("sin_red_apoyo", "Vive sola", self.qf))
        self.assertTrue(es_elegible(self.cronico))
        with self.assertRaisesMessage(ValidationError, "ya tiene una excepción"):
            inscribir_excepcion(self.qf, self.cronico.pk, "discapacidad")
        con_81 = paciente(edad=81)
        with self.assertRaisesMessage(ValidationError, "ya es elegible"):
            inscribir_excepcion(self.qf, con_81.pk, "discapacidad")
        postrado = paciente(edad=50, postrado=True)
        with self.assertRaisesMessage(ValidationError, "ya es elegible"):
            inscribir_excepcion(self.qf, postrado.pk, "discapacidad")
        self.assertEqual(InscripcionReparto.objects.count(), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="reparto.excepcion_inscrita").count(), 1)

    def test_motivo_de_catalogo_y_nota_obligatoria_con_otro(self):
        for motivo, nota in (("inventado", ""), ("otro", ""), ("otro", "   "), ("discapacidad", "x" * 201)):
            with self.subTest(motivo=motivo, nota=len(nota)), self.assertRaises(ValidationError):
                inscribir_excepcion(self.qf, self.cronico.pk, motivo, nota)
        inscribir_excepcion(self.qf, self.cronico.pk, "otro", "Cuidadora con turno nocturno")

    def test_solo_la_qf_y_el_superusuario_inscriben_y_retiran(self):
        for actor in ("tecnico", "encargado"):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                inscribir_excepcion(self.equipo[actor], self.cronico.pk, "discapacidad")
        inscripcion = inscribir_excepcion(self.equipo["admin"], self.cronico.pk, "discapacidad")
        with self.assertRaises(PermissionDenied):
            retirar_excepcion(self.equipo["encargado"], inscripcion.pk)
        retirar_excepcion(self.equipo["admin"], inscripcion.pk)

    def test_retirar_conserva_el_registro_y_no_cierra_la_entrega_abierta(self):
        inscripcion = inscribir_excepcion(self.qf, self.cronico.pk, "sin_red_apoyo")
        receta(self.cronico)
        entrega = programar_entrega(self.qf, self.cronico.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        retirada = retirar_excepcion(self.qf, inscripcion.pk)
        self.assertEqual(retirada.retirada_por, self.qf)
        self.assertIsNotNone(retirada.retirada_en)
        self.assertFalse(es_elegible(self.cronico))
        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, Entrega.Estado.PROGRAMADA)
        with self.assertRaisesMessage(ValidationError, "ya fue retirada"):
            retirar_excepcion(self.qf, inscripcion.pk)
        # Se puede inscribir de nuevo: la anterior queda como historial.
        inscribir_excepcion(self.qf, self.cronico.pk, "indicacion_clinica")
        self.assertEqual(InscripcionReparto.objects.filter(paciente=self.cronico).count(), 2)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="reparto.excepcion_retirada", objeto_id=str(inscripcion.pk)).exists())
