"""Derivación al reparto con lo ya preparado (RF-13-06 y RF-13-07)."""

import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from entregasapp import services as reparto
from entregasapp.models import Entrega, InscripcionReparto, RecetaEntrega
from indicadoresapp import mermas
from recetasapp.preparacion import pendientes_retiro
from recetasapp.services import retirar_preparado
from .ayudas import equipo, hoy, paciente, preparada, receta


class DerivacionTests(TestCase):
    def setUp(self):
        self.e = equipo()

    def derivar(self, persona, **extra):
        return reparto.derivar_desde_merma(self.e["qf"], persona.pk, extra.pop("fecha", hoy()),
                                           self.e["encargado"].pk, extra.pop("operacion", uuid.uuid4()), **extra)

    def test_lleva_lo_preparado_y_las_demas_elegibles(self):
        persona = paciente(edad=85)
        p1 = preparada(persona, usuario=self.e["tecnico"])
        p2 = preparada(persona, dias_atras=1, usuario=self.e["tecnico"])
        otra = receta(persona)
        entrega = self.derivar(persona)
        vinculos = {v.receta_id: v.preparacion_id for v in entrega.recetas.all()}
        self.assertEqual(vinculos, {
            p1.turno_receta.receta_id: p1.pk, p2.turno_receta.receta_id: p2.pk, otra.pk: None,
        })
        en_despacho = {p.pk: p.en_despacho for p in pendientes_retiro()}
        self.assertEqual(en_despacho, {p1.pk: True, p2.pk: True})
        self.assertTrue(RegistroAuditoria.objects.filter(accion="entrega.derivada_merma", objeto_id=str(entrega.pk)).exists())

    def test_no_elegible_exige_motivo_y_crea_excepcion_junto_a_la_entrega(self):
        persona = paciente(edad=60)
        preparada(persona, usuario=self.e["tecnico"])
        with self.assertRaises(ValidationError):
            self.derivar(persona)
        self.assertFalse(Entrega.objects.exists())
        self.assertFalse(InscripcionReparto.objects.exists())
        entrega = self.derivar(persona, motivo="sin_red_apoyo")
        self.assertEqual(InscripcionReparto.objects.get(paciente=persona, retirada_en__isnull=True).motivo, "sin_red_apoyo")
        self.assertEqual(entrega.paciente_id, persona.pk)

    def test_falla_de_la_entrega_revierte_la_excepcion(self):
        persona = paciente(edad=60)
        preparada(persona, usuario=self.e["tecnico"])
        with self.assertRaises(ValidationError):
            reparto.derivar_desde_merma(self.e["qf"], persona.pk, hoy(), self.e["tecnico"].pk, uuid.uuid4(),
                                        motivo="otro", nota="Nota sintética")
        self.assertFalse(InscripcionReparto.objects.exists())

    def test_entrega_abierta_avisa_sin_cambios(self):
        persona = paciente(edad=85)
        receta(persona)
        abierta = reparto.programar_entrega(self.e["qf"], persona.pk, hoy(), self.e["encargado"].pk, uuid.uuid4())
        preparada(persona, usuario=self.e["tecnico"])
        with self.assertRaises(reparto.EntregaAbiertaExistente) as error:
            self.derivar(persona)
        self.assertEqual(error.exception.entrega_id, abierta.pk)
        self.assertEqual(Entrega.objects.count(), 1)

    def test_sin_preparadas_rechaza(self):
        persona = paciente(edad=85)
        preparacion = preparada(persona, usuario=self.e["tecnico"])
        retirar_preparado(self.e["tecnico"], preparacion.pk, uuid.uuid4())
        with self.assertRaises(ValidationError):
            self.derivar(persona)

    def test_idempotente_por_operacion(self):
        persona = paciente(edad=85)
        preparada(persona, usuario=self.e["tecnico"])
        operacion = uuid.uuid4()
        primera = self.derivar(persona, operacion=operacion)
        self.assertEqual(self.derivar(persona, operacion=operacion), primera)
        self.assertEqual(Entrega.objects.count(), 1)

    def test_solo_la_qf_o_el_superusuario(self):
        persona = paciente(edad=85)
        preparada(persona, usuario=self.e["tecnico"])
        for rol in ("tecnico", "encargado"):
            with self.assertRaises(PermissionDenied):
                reparto.derivar_desde_merma(self.e[rol], persona.pk, hoy(), self.e["encargado"].pk, uuid.uuid4())
        self.assertTrue(reparto.derivar_desde_merma(self.e["admin"], persona.pk, hoy(), self.e["encargado"].pk, uuid.uuid4()))


class DespachoDeLoPreparadoTests(TestCase):
    def setUp(self):
        self.e = equipo()

    def derivar(self, persona):
        entrega = reparto.derivar_desde_merma(self.e["qf"], persona.pk, hoy(), self.e["encargado"].pk, uuid.uuid4())
        return entrega, entrega.intentos.get()

    def test_ventanilla_no_entrega_lo_que_esta_en_despacho(self):
        persona = paciente(edad=85)
        preparacion = preparada(persona, usuario=self.e["tecnico"])
        self.derivar(persona)
        with self.assertRaises(ValidationError):
            retirar_preparado(self.e["tecnico"], preparacion.pk, uuid.uuid4())

    def test_entregada_se_evalua_a_la_fecha_de_preparacion_y_sale_de_pendientes(self):
        persona = paciente(edad=85)
        inicio = hoy() - timedelta(days=30)
        vence = receta(persona, inicio=inicio, fin=hoy() - timedelta(days=1))  # vigente hace 3 días, vencida hoy
        preparacion = preparada(persona, dias_atras=3, receta_=vence, usuario=self.e["tecnico"])
        _, intento = self.derivar(persona)
        reparto.registrar_entregada(self.e["encargado"], intento.pk, uuid.uuid4())
        vinculo = RecetaEntrega.objects.get(preparacion=preparacion)
        self.assertEqual(vinculo.resultado, "descontada")
        self.assertEqual(vinculo.entrega_receta.turno_receta_id, preparacion.turno_receta_id)
        self.assertFalse(pendientes_retiro().filter(pk=preparacion.pk).exists())
        vence.refresh_from_db()
        self.assertEqual(vence.entregas_completadas, 1)
        resumen = mermas.resumir(mermas.periodo_por_omision())
        self.assertEqual((resumen.cifras["despacho"], resumen.merma), (1, 0))

    def test_no_descontada_vuelve_a_sin_retirar(self):
        persona = paciente(edad=85)
        agotada = receta(persona, maximo=1, completadas=1)
        preparacion = preparada(persona, receta_=agotada, usuario=self.e["tecnico"])
        _, intento = self.derivar(persona)
        reparto.registrar_entregada(self.e["encargado"], intento.pk, uuid.uuid4())
        self.assertEqual(RecetaEntrega.objects.get(preparacion=preparacion).resultado, "no_descontada")
        resumen = mermas.resumir(mermas.periodo_por_omision())
        self.assertEqual(resumen.cifras["sin_retirar"], 1)
        self.assertFalse(pendientes_retiro().get(pk=preparacion.pk).en_despacho)

    def test_anulada_vuelve_a_sin_retirar(self):
        persona = paciente(edad=85)
        preparacion = preparada(persona, usuario=self.e["tecnico"])
        entrega, _ = self.derivar(persona)
        reparto.anular_entrega(self.e["qf"], entrega.pk, "retirara_farmacia")
        self.assertFalse(pendientes_retiro().get(pk=preparacion.pk).en_despacho)
        retirar_preparado(self.e["tecnico"], preparacion.pk, uuid.uuid4())
        resumen = mermas.resumir(mermas.periodo_por_omision())
        self.assertEqual((resumen.cifras["tarde"], resumen.merma), (1, 0))

    def test_recetas_no_preparadas_siguen_la_regla_del_dia_de_la_visita(self):
        persona = paciente(edad=85)
        preparada(persona, usuario=self.e["tecnico"])
        comun = receta(persona)
        _, intento = self.derivar(persona)
        reparto.registrar_entregada(self.e["encargado"], intento.pk, uuid.uuid4())
        vinculo = RecetaEntrega.objects.get(receta=comun)
        self.assertEqual(vinculo.resultado, "descontada")
        self.assertIsNone(vinculo.entrega_receta.turno_receta_id)
