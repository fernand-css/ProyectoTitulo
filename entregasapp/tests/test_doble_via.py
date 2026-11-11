"""RF-08-07: una receta con entrega a domicilio abierta no se dispensa en el tótem ni en la ventanilla."""

import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase

from entregasapp.services import anular_entrega, inscribir_excepcion, programar_entrega
from recetasapp.models import EntregaReceta
from recetasapp.services import registrar_entrega
from turnosapp.atencion import reincorporar
from turnosapp.models import ContadorTurnosDiario, Turno
from turnosapp.services import ErrorEmision, emitir_turno
from turnosapp.views import CLAVE
from .ayudas import equipo, hoy, paciente, receta
from .test_programacion import turno

MENSAJE_TOTEM = "Tienes un despacho a domicilio programado. Consulta con el personal."


class DobleViaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.cronico = paciente(edad=60, cronico=True)
        inscribir_excepcion(self.qf, self.cronico.pk, "sin_red_apoyo")
        self.receta = receta(self.cronico, "DESPACHO-1")

    def programar(self):
        return programar_entrega(self.qf, self.cronico.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())

    def test_el_totem_no_emite_si_todas_las_recetas_estan_en_despacho_ni_consume_numero(self):
        self.programar()
        with self.assertRaises(ErrorEmision) as error:
            emitir_turno(self.cronico.rut, uuid.uuid4())
        self.assertEqual(error.exception.code, "despacho_abierto")
        self.assertEqual(error.exception.messages, [MENSAJE_TOTEM])
        self.assertFalse(Turno.objects.exists())
        self.assertEqual(ContadorTurnosDiario.objects.filter(ultimo_numero__gt=0).count(), 0)

    def test_el_totem_omite_las_recetas_en_despacho_y_emite_con_las_demas(self):
        self.programar()
        nueva = receta(self.cronico, "FUERA-DEL-DESPACHO")
        resultado = emitir_turno(self.cronico.rut, uuid.uuid4())
        self.assertEqual(resultado.numero, 1)
        vinculadas = list(Turno.objects.get().recetas_vinculadas.values_list("receta_id", flat=True))
        self.assertEqual(vinculadas, [nueva.pk])

    def test_mensaje_publico_del_totem_sin_datos_personales(self):
        self.programar()
        self.client.get("/turnos/totem/")
        respuesta = self.client.post("/turnos/totem/", {
            "rut": self.cronico.rut, "operacion_id": self.client.session[CLAVE]["operacion"],
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, MENSAJE_TOTEM, status_code=400)
        for dato in (self.cronico.rut, self.cronico.nombres, self.cronico.apellidos, self.receta.codigo, self.cronico.direccion):
            self.assertNotContains(respuesta, dato, status_code=400)
        self.assertFalse(Turno.objects.exists())

    def test_la_ventanilla_rechaza_y_tras_anular_vuelve_a_registrar(self):
        entrega = self.programar()
        with self.assertRaisesMessage(ValidationError, "La receta tiene una entrega a domicilio abierta."):
            registrar_entrega(self.equipo["tecnico"], self.receta.pk, uuid.uuid4())
        self.assertFalse(EntregaReceta.objects.exists())
        anular_entrega(self.qf, entrega.pk, "retirara_farmacia")
        registrar_entrega(self.equipo["tecnico"], self.receta.pk, uuid.uuid4())
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 1)
        emitir_turno(self.cronico.rut, uuid.uuid4())  # el tótem también vuelve a aceptar al paciente

    def test_no_se_reincorpora_un_turno_con_recetas_en_un_despacho_abierto(self):
        ausente, _ = turno(self.cronico, [self.receta], estado="ausente")
        entrega = self.programar()  # el turno ausente no está activo: la receta se puede programar
        self.assertEqual(list(entrega.recetas.values_list("receta_id", flat=True)), [self.receta.pk])
        with self.assertRaisesMessage(ValidationError, "entrega a domicilio abierta"):
            reincorporar(self.equipo["tecnico"], ausente.pk, uuid.uuid4())
        ausente.refresh_from_db()
        self.assertEqual(ausente.estado, "ausente")
        anular_entrega(self.qf, entrega.pk, "retirara_farmacia")
        reincorporar(self.equipo["tecnico"], ausente.pk, uuid.uuid4())
        ausente.refresh_from_db()
        self.assertEqual(ausente.estado, "esperando")
