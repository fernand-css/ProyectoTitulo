"""Consulta de la merma (RF-13-01), lo entregado en la atención (RF-13-18) y la serie por granularidad (RF-13-15)."""

import uuid
from datetime import timedelta

from django.test import TestCase

from entregasapp import services as reparto
from indicadoresapp import mermas
from indicadoresapp.periodos import periodo_de
from recetasapp.services import retirar_preparado
from .ayudas import entregada_en_la_atencion, equipo, hoy, paciente, preparada


class EstadosTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.periodo = mermas.Periodo(hoy() - timedelta(days=29), hoy())

    def resumen(self, periodo=None):
        return mermas.resumir(periodo or self.periodo)

    def test_cuatro_estados_merma_y_recuperadas(self):
        sin_retirar = preparada(paciente(), usuario=self.e["tecnico"])
        tarde = preparada(paciente(), usuario=self.e["tecnico"])
        retirar_preparado(self.e["tecnico"], tarde.pk, uuid.uuid4())
        derivada = preparada(paciente(edad=85), usuario=self.e["tecnico"])
        reparto.derivar_desde_merma(self.e["qf"], derivada.turno_receta.receta.paciente_id, hoy(),
                                    self.e["encargado"].pk, uuid.uuid4())
        resumen = self.resumen()
        self.assertEqual(resumen.cifras, {"sin_retirar": 1, "en_despacho": 1, "tarde": 1, "despacho": 0})
        self.assertEqual((resumen.merma, resumen.recuperadas), (2, 1))
        self.assertTrue(sin_retirar)

    def test_no_preparada_activa_o_entregada_en_la_atencion_no_cuentan(self):
        preparada(paciente(), usuario=self.e["tecnico"], lista=False)
        preparada(paciente(), estado="esperando", usuario=self.e["tecnico"])
        entregada_en_la_atencion(preparada(paciente(), estado="atendido", usuario=self.e["tecnico"]), self.e["tecnico"])
        resumen = self.resumen()
        self.assertEqual((resumen.merma, resumen.recuperadas), (0, 0))

    def test_cuenta_los_cuatro_cierres(self):
        for estado in mermas.CIERRES:
            preparada(paciente(), estado=estado, usuario=self.e["tecnico"])
        self.assertEqual(self.resumen().merma, 4)

    def test_preparadas_incluyen_las_entregadas_en_la_atencion(self):
        preparada(paciente(), usuario=self.e["tecnico"])
        for _ in range(3):
            entregada_en_la_atencion(preparada(paciente(), estado="atendido", usuario=self.e["tecnico"]), self.e["tecnico"])
        resumen = self.resumen()
        self.assertEqual((resumen.en_atencion, resumen.preparadas, resumen.merma), (3, 4, 1))
        self.assertEqual(resumen.merma_porcentaje, 25)
        self.assertEqual(sum(resumen.merma_por_dia.values()), 1)

    def test_filtro_por_tipo_usa_la_marca_cronico(self):
        preparada(paciente(cronico=True), usuario=self.e["tecnico"])
        preparada(paciente(cronico=False), usuario=self.e["tecnico"])
        preparada(paciente(cronico=False), usuario=self.e["tecnico"])
        base = self.periodo
        self.assertEqual(self.resumen(mermas.Periodo(base.inicio, base.fin, mermas.CRONICO)).merma, 1)
        self.assertEqual(self.resumen(mermas.Periodo(base.inicio, base.fin, mermas.GENERAL)).merma, 2)
        self.assertEqual([c for _, _, c in self.resumen().por_tipo], [1, 2])

    def test_rango_por_fecha_de_preparacion(self):
        preparada(paciente(), dias_atras=40, usuario=self.e["tecnico"])
        preparada(paciente(), dias_atras=3, usuario=self.e["tecnico"])
        self.assertEqual(self.resumen().merma, 1)
        largo = mermas.Periodo(hoy() - timedelta(days=89), hoy())
        self.assertEqual(self.resumen(largo).merma, 2)

    def test_serie_por_dia_semana_y_mes(self):
        preparada(paciente(), dias_atras=2, usuario=self.e["tecnico"])
        corto = self.resumen(mermas.Periodo(hoy() - timedelta(days=9), hoy()))
        self.assertFalse(corto.por_semana)
        self.assertEqual(len(corto.serie), 10)
        self.assertEqual(sum(valor for _, valor in corto.serie), 1)
        largo = self.resumen(mermas.Periodo(hoy() - timedelta(days=89), hoy()))
        self.assertTrue(largo.por_semana)
        self.assertTrue(all(fecha.weekday() == 0 for fecha, _ in largo.serie))
        self.assertEqual(sum(valor for _, valor in largo.serie), 1)
        anio = self.resumen(periodo_de("anio", hoy()))
        self.assertEqual(anio.granularidad, "mes")
        self.assertTrue(all(fecha.day == 1 for fecha, _ in anio.serie))
