"""RF-08-08 a RF-08-10: «Mis entregas» y registro de «entregada» / «no entregada» con descuento del 03."""

import uuid
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from entregasapp.consultas import mis_entregas
from entregasapp.models import Entrega, IntentoEntrega, RecetaEntrega
from entregasapp.services import programar_entrega, registrar_entregada, registrar_no_entregada
from recetasapp.models import EntregaReceta, Receta
from recetasapp.services import registrar_entrega
from .ayudas import equipo, hoy, paciente, receta


class Base(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.encargado = self.equipo["encargado"]

    def entrega(self, *recetas_previas, encargado=None, fecha=None, persona=None):
        persona = persona or paciente(edad=88)
        recetas = [receta(persona, **datos) for datos in recetas_previas] or [receta(persona)]
        entrega = programar_entrega(self.qf, persona.pk, fecha or hoy(), (encargado or self.encargado).pk, uuid.uuid4())
        return entrega, recetas, entrega.intentos.get()


class RegistroEntregadaTests(Base):
    def test_descuenta_las_validas_en_la_visita_y_deja_las_demas_no_descontadas(self):
        entrega, (vigente, vence), intento = self.entrega({}, {"fin": hoy() + timedelta(days=1)})
        Receta.objects.filter(pk=vence.pk).update(fecha_fin_exclusiva=hoy())  # venció ayer
        resultado = registrar_entregada(self.encargado, intento.pk, uuid.uuid4())
        self.assertFalse(resultado.repetido)
        intento.refresh_from_db()
        entrega.refresh_from_db()
        self.assertEqual((intento.resultado, intento.registrado_por), ("entregada", self.encargado))
        self.assertIsNotNone(intento.registrado_en)
        self.assertEqual(entrega.estado, "entregada")
        self.assertIsNotNone(entrega.cerrada_en)
        vigente.refresh_from_db()
        vence.refresh_from_db()
        self.assertEqual((vigente.entregas_completadas, vence.entregas_completadas), (1, 0))
        descontada = RecetaEntrega.objects.get(receta=vigente)
        self.assertEqual(descontada.resultado, "descontada")
        self.assertEqual((descontada.entrega_receta.numero, descontada.entrega_receta.creado_por), (1, self.encargado))
        self.assertIsNone(descontada.entrega_receta.turno_receta_id)
        no_descontada = RecetaEntrega.objects.get(receta=vence)
        self.assertEqual((no_descontada.resultado, no_descontada.causa),
                         ("no_descontada", "La receta está vencida; requiere renovación."))
        self.assertTrue(RegistroAuditoria.objects.filter(accion="intento.entregado", objeto_id=str(intento.pk)).exists())
        self.assertTrue(RegistroAuditoria.objects.filter(accion="receta.entrega", usuario=self.encargado).exists())

    def test_repetir_el_registro_devuelve_lo_mismo_sin_otro_descuento(self):
        _, (unica,), intento = self.entrega()
        operacion = uuid.uuid4()
        registrar_entregada(self.encargado, intento.pk, operacion)
        repetido = registrar_entregada(self.encargado, intento.pk, operacion)
        self.assertTrue(repetido.repetido)
        unica.refresh_from_db()
        self.assertEqual(unica.entregas_completadas, 1)
        self.assertEqual(EntregaReceta.objects.count(), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="intento.entregado").count(), 1)
        with self.assertRaisesMessage(ValidationError, "ya tiene un resultado"):
            registrar_entregada(self.encargado, intento.pk, uuid.uuid4())
        with self.assertRaisesMessage(ValidationError, "no corresponde"):
            registrar_no_entregada(self.encargado, intento.pk, "sin_receptor", "", operacion)

    def test_rechaza_intento_de_manana_de_otro_encargado_y_de_otros_perfiles(self):
        _, _, manana = self.entrega(fecha=hoy() + timedelta(days=1))
        with self.assertRaisesMessage(ValidationError, "Regístrala desde ese día"):
            registrar_entregada(self.encargado, manana.pk, uuid.uuid4())
        _, _, ajeno = self.entrega(encargado=self.equipo["encargado2"])
        for actor in (self.encargado, self.qf, self.equipo["admin"], self.equipo["tecnico"], AnonymousUser()):
            with self.subTest(actor=str(actor)), self.assertRaises(PermissionDenied):
                registrar_entregada(actor, ajeno.pk, uuid.uuid4())
        self.assertEqual(IntentoEntrega.objects.filter(resultado="pendiente").count(), 2)
        self.assertFalse(EntregaReceta.objects.exists())

    def test_se_registra_con_atraso_y_la_hora_es_la_del_servidor(self):
        _, _, intento = self.entrega()
        IntentoEntrega.objects.filter(pk=intento.pk).update(fecha_programada=hoy() - timedelta(days=2))
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4())
        intento.refresh_from_db()
        self.assertEqual(intento.resultado, "entregada")
        from django.utils import timezone
        self.assertEqual(timezone.localdate(intento.registrado_en), hoy())

    def test_cupo_agotado_justo_antes_queda_no_descontado_sin_exceder(self):
        _, (agotada,), intento = self.entrega({"maximo": 2, "completadas": 1})
        Receta.objects.filter(pk=agotada.pk).update(entregas_completadas=2)
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4())
        agotada.refresh_from_db()
        self.assertEqual(agotada.entregas_completadas, 2)
        vinculo = RecetaEntrega.objects.get()
        self.assertEqual(vinculo.resultado, "no_descontada")
        self.assertIn("agotó sus entregas", vinculo.causa)


class RegistroNoEntregadaTests(Base):
    def test_exige_motivo_y_nota_con_otro(self):
        _, _, intento = self.entrega()
        for motivo, nota in (("", ""), ("inventado", ""), ("otro", ""), ("sin_receptor", "x" * 201)):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError):
                registrar_no_entregada(self.encargado, intento.pk, motivo, nota, uuid.uuid4())
        intento.refresh_from_db()
        self.assertEqual(intento.resultado, "pendiente")

    def test_queda_pendiente_de_gestion_sin_descuento_y_con_recetas_bloqueadas(self):
        entrega, (unica,), intento = self.entrega()
        operacion = uuid.uuid4()
        registrar_no_entregada(self.encargado, intento.pk, "sin_receptor", "Vecino avisa que vuelven el lunes", operacion)
        entrega.refresh_from_db()
        intento.refresh_from_db()
        self.assertEqual(entrega.estado, "pendiente_gestion")
        self.assertIsNone(entrega.cerrada_en)
        self.assertEqual((intento.resultado, intento.motivo, intento.nota),
                         ("no_entregada", "sin_receptor", "Vecino avisa que vuelven el lunes"))
        unica.refresh_from_db()
        self.assertEqual(unica.entregas_completadas, 0)
        self.assertTrue(registrar_no_entregada(self.encargado, intento.pk, "sin_receptor", "", operacion).repetido)
        with self.assertRaisesMessage(ValidationError, "entrega a domicilio abierta"):
            registrar_entrega(self.equipo["tecnico"], unica.pk, uuid.uuid4())
        self.assertTrue(RegistroAuditoria.objects.filter(accion="intento.no_entregado").exists())
        for registro in RegistroAuditoria.objects.all():
            self.assertNotIn("Vecino", f"{registro.accion}{registro.objeto_tipo}{registro.objeto_id}")


class MisEntregasConsultaTests(Base):
    def test_hoy_atrasadas_y_proximas_solo_del_encargado(self):
        _, _, de_hoy = self.entrega()
        _, _, atrasada = self.entrega()
        IntentoEntrega.objects.filter(pk=atrasada.pk).update(fecha_programada=hoy() - timedelta(days=1))
        _, _, manana = self.entrega(fecha=hoy() + timedelta(days=1))
        _, _, ajena = self.entrega(encargado=self.equipo["encargado2"])
        _, _, registrada = self.entrega()
        registrar_no_entregada(self.encargado, registrada.pk, "camino_intransitable", "", uuid.uuid4())
        lista = mis_entregas(self.encargado)
        self.assertEqual([i.pk for i in lista.hoy], [de_hoy.pk])
        self.assertEqual([i.pk for i in lista.atrasadas], [atrasada.pk])
        self.assertEqual([i.pk for i in lista.proximas], [manana.pk])
        self.assertEqual(lista.total, 3)
        self.assertEqual([i.pk for i in mis_entregas(self.equipo["encargado2"]).hoy], [ajena.pk])
        self.assertEqual(Entrega.objects.count(), 5)
