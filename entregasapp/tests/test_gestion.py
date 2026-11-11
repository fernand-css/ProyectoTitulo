"""RF-08-11 y RF-08-12: pendientes de gestión, reasignar, anular y revisar recetas no descontadas."""

import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from entregasapp.consultas import mis_entregas, no_descontadas, pendientes_gestion, programadas
from entregasapp.models import Domicilio, Entrega, IntentoEntrega, RecetaEntrega
from entregasapp.services import (
    anular_entrega, marcar_revisada, programar_entrega, reasignar, registrar_entregada, registrar_no_entregada,
)
from recetasapp.models import Receta
from recetasapp.services import registrar_entrega
from .ayudas import equipo, hoy, paciente, receta


class Base(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.encargado = self.equipo["encargado"]
        self.encargado2 = self.equipo["encargado2"]

    def entrega(self, *, sector="", encargado=None, fecha=None):
        persona = paciente(edad=88)
        receta(persona)
        if sector:
            Domicilio.objects.create(paciente=persona, sector=sector, direccion="Camino sintético", direccion_padron=persona.direccion)
        entrega = programar_entrega(self.qf, persona.pk, fecha or hoy(), (encargado or self.encargado).pk, uuid.uuid4())
        return entrega, entrega.intentos.get()

    def no_entregada(self, motivo="domicilio_no_encontrado", **datos):
        entrega, intento = self.entrega(**datos)
        registrar_no_entregada(intento.encargado, intento.pk, motivo, "", uuid.uuid4())
        entrega.refresh_from_db()
        intento.refresh_from_db()
        return entrega, intento

    def reasignar(self, entrega, intento, *, fecha=None, encargado=None, operacion=None, actor=None):
        return reasignar(actor or self.qf, entrega.pk, fecha=fecha or hoy() + timedelta(days=1),
                         encargado_id=(encargado or self.encargado2).pk, intento_id=intento.pk,
                         operacion_id=operacion or uuid.uuid4())


class PendientesYReasignacionTests(Base):
    def test_filtros_por_motivo_sector_encargado_y_fechas(self):
        buscada, _ = self.no_entregada("domicilio_no_encontrado", sector="verde")
        self.no_entregada("domicilio_no_encontrado", sector="azul")
        self.no_entregada("sin_receptor", sector="verde")
        otro_encargado, _ = self.no_entregada("domicilio_no_encontrado", sector="verde", encargado=self.encargado2)
        self.entrega(sector="verde")  # programada: no está pendiente de gestión
        self.assertEqual(pendientes_gestion().count(), 4)
        filtrada = pendientes_gestion(motivo="domicilio_no_encontrado", sector="verde")
        self.assertCountEqual(filtrada.values_list("pk", flat=True), [buscada.pk, otro_encargado.pk])
        self.assertEqual(list(pendientes_gestion(motivo="domicilio_no_encontrado", sector="verde", encargado=self.encargado)
                              .values_list("pk", flat=True)), [buscada.pk])
        self.assertEqual(pendientes_gestion(desde=hoy() + timedelta(days=1)).count(), 0)
        self.assertEqual(pendientes_gestion(desde=hoy(), hasta=hoy()).count(), 4)
        fila = pendientes_gestion(motivo="sin_receptor").get()
        self.assertEqual((fila.ultimo_numero, fila.ultimo_motivo, fila.ultimo_encargado, fila.recetas_cantidad),
                         (1, "sin_receptor", self.encargado.pk, 1))

    def test_las_listas_usan_un_numero_constante_de_consultas(self):
        self.no_entregada()
        with self.assertNumQueries(1):
            len(list(pendientes_gestion(sector="verde", motivo="sin_receptor")))
        for _ in range(4):
            self.no_entregada()
            self.entrega()
        with self.assertNumQueries(1):
            self.assertEqual(len(list(pendientes_gestion())), 5)
        with self.assertNumQueries(1):
            self.assertEqual(len(list(programadas())), 4)

    def test_reasignar_conserva_el_intento_anterior_y_aparece_al_nuevo_encargado(self):
        entrega, intento = self.no_entregada("domicilio_no_encontrado", sector="verde")
        antes = IntentoEntrega.objects.values().get(pk=intento.pk)
        nuevo = self.reasignar(entrega, intento)
        self.assertEqual(IntentoEntrega.objects.values().get(pk=intento.pk), antes)
        self.assertEqual((nuevo.numero, nuevo.encargado, nuevo.resultado, nuevo.fecha_programada),
                         (2, self.encargado2, "pendiente", hoy() + timedelta(days=1)))
        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, "programada")
        self.assertEqual([i.pk for i in mis_entregas(self.encargado2).proximas], [nuevo.pk])
        self.assertEqual(mis_entregas(self.encargado).total, 0)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="entrega.reasignada", objeto_id=str(nuevo.pk)).exists())

    def test_reasignar_un_intento_programado_lo_cierra_como_reasignado(self):
        entrega, intento = self.entrega()
        nuevo = self.reasignar(entrega, intento, fecha=hoy())
        intento.refresh_from_db()
        self.assertEqual((intento.resultado, intento.registrado_por), ("reasignado", self.qf))
        self.assertEqual((nuevo.numero, nuevo.resultado), (2, "pendiente"))
        with self.assertRaisesMessage(ValidationError, "reasignada"):
            registrar_entregada(self.encargado, intento.pk, uuid.uuid4())

    def test_el_resultado_visto_debe_seguir_igual(self):
        entrega, intento = self.entrega()
        registrar_no_entregada(self.encargado, intento.pk, "rechazo", "", uuid.uuid4())
        with self.assertRaisesMessage(ValidationError, "Revisa su último intento"):
            reasignar(self.qf, entrega.pk, fecha=hoy(), encargado_id=self.encargado2.pk, intento_id=intento.pk,
                      operacion_id=uuid.uuid4(), resultado_visto="pendiente")
        nuevo = reasignar(self.qf, entrega.pk, fecha=hoy(), encargado_id=self.encargado2.pk, intento_id=intento.pk,
                          operacion_id=uuid.uuid4(), resultado_visto="no_entregada")
        self.assertEqual(nuevo.numero, 2)

    def test_reenvio_idempotente_e_intento_desactualizado(self):
        entrega, intento = self.no_entregada()
        operacion = uuid.uuid4()
        nuevo = self.reasignar(entrega, intento, operacion=operacion)
        self.assertEqual(self.reasignar(entrega, intento, operacion=operacion).pk, nuevo.pk)
        with self.assertRaisesMessage(ValidationError, "Revisa su último intento"):
            self.reasignar(entrega, intento)
        self.assertEqual(entrega.intentos.count(), 2)

    def test_rechazos_de_reasignacion(self):
        entrega, intento = self.no_entregada()
        for nombre, datos, mensaje in (
            ("fecha pasada", {"fecha": hoy() - timedelta(days=1)}, "hoy o posterior"),
            ("técnico como encargado", {"encargado": self.equipo["tecnico"]}, "encargado de terreno"),
        ):
            with self.subTest(nombre), self.assertRaisesMessage(ValidationError, mensaje):
                self.reasignar(entrega, intento, **datos)
        for actor in ("tecnico", "encargado"):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                self.reasignar(entrega, intento, actor=self.equipo[actor])
        cerrada, intento_cerrado = self.entrega()
        registrar_entregada(self.encargado, intento_cerrado.pk, uuid.uuid4())
        with self.assertRaisesMessage(ValidationError, "ya está cerrada"):
            self.reasignar(cerrada, intento_cerrado)
        self.assertEqual(IntentoEntrega.objects.filter(entrega=entrega).count(), 1)


class AnulacionTests(Base):
    def test_anular_cierra_el_intento_pendiente_y_libera_las_recetas(self):
        entrega, intento = self.entrega()
        anulada = anular_entrega(self.qf, entrega.pk, "retirara_farmacia")
        intento.refresh_from_db()
        self.assertEqual((anulada.estado, anulada.motivo_anulacion, anulada.anulada_por), ("anulada", "retirara_farmacia", self.qf))
        self.assertEqual(intento.resultado, "anulado")
        receta_id = entrega.recetas.get().receta_id
        registrar_entrega(self.equipo["tecnico"], receta_id, uuid.uuid4())
        self.assertEqual(Receta.objects.get(pk=receta_id).entregas_completadas, 1)
        self.assertEqual(anular_entrega(self.qf, entrega.pk, "retirara_farmacia").pk, entrega.pk)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="entrega.anulada").count(), 1)
        with self.assertRaisesMessage(ValidationError, "anulada"):
            registrar_no_entregada(self.encargado, intento.pk, "sin_receptor", "", uuid.uuid4())

    def test_anular_pendiente_de_gestion_y_rechazos(self):
        entrega, _ = self.no_entregada()
        with self.assertRaisesMessage(ValidationError, "«Otro»"):
            anular_entrega(self.qf, entrega.pk, "otro", "")
        with self.assertRaises(ValidationError):
            anular_entrega(self.qf, entrega.pk, "inventado")
        with self.assertRaises(PermissionDenied):
            anular_entrega(self.equipo["tecnico"], entrega.pk, "retirara_farmacia")
        anular_entrega(self.equipo["admin"], entrega.pk, "otro", "Familia retira en farmacia")
        entrega.refresh_from_db()
        self.assertEqual((entrega.estado, entrega.nota_anulacion), ("anulada", "Familia retira en farmacia"))
        entregada, intento = self.entrega()
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4())
        with self.assertRaisesMessage(ValidationError, "no se puede anular"):
            anular_entrega(self.qf, entregada.pk, "retirara_farmacia")


class RecetasNoDescontadasTests(Base):
    def test_marcar_revisada_saca_de_la_lista_con_autor_y_fecha(self):
        entrega, intento = self.entrega()
        Receta.objects.filter(pk=entrega.recetas.get().receta_id).update(fecha_fin_exclusiva=hoy())
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4())
        pendiente = no_descontadas().get()
        self.assertEqual(pendiente.causa, "La receta está vencida; requiere renovación.")
        revisada = marcar_revisada(self.qf, pendiente.pk)
        self.assertEqual(revisada.revisada_por, self.qf)
        self.assertIsNotNone(revisada.revisada_en)
        self.assertFalse(no_descontadas().exists())
        self.assertEqual(marcar_revisada(self.qf, pendiente.pk).revisada_en, revisada.revisada_en)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="despacho.receta_revisada").count(), 1)
        with self.assertRaises(PermissionDenied):
            marcar_revisada(self.equipo["tecnico"], pendiente.pk)

    def test_solo_se_revisan_las_no_descontadas(self):
        entrega, intento = self.entrega()
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4())
        with self.assertRaisesMessage(ValidationError, "sin descontar"):
            marcar_revisada(self.qf, RecetaEntrega.objects.get().pk)
        self.assertEqual(Entrega.objects.get().estado, "entregada")
