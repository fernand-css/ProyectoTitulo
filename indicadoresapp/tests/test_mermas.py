"""Consulta del panel de mermas y sus filtros (RF-13-01 a RF-13-03)."""

import uuid
from datetime import timedelta

from django.test import TestCase

from entregasapp import services as reparto
from indicadoresapp import mermas
from indicadoresapp.filtros import FiltroMermasForm, atajos
from recetasapp.services import retirar_preparado
from .ayudas import entregada_en_la_atencion, equipo, hoy, paciente, preparada


class EstadosTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.periodo = mermas.periodo_por_omision()

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
        resumen = self.resumen()
        self.assertEqual(resumen.merma, 4)
        self.assertEqual([cantidad for _, _, cantidad in resumen.por_cierre], [1, 1, 1, 1])

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

    def test_serie_por_dia_y_por_semana(self):
        preparada(paciente(), dias_atras=2, usuario=self.e["tecnico"])
        corto = self.resumen(mermas.Periodo(hoy() - timedelta(days=9), hoy()))
        self.assertFalse(corto.por_semana)
        self.assertEqual(len(corto.serie), 10)
        self.assertEqual(sum(valor for _, valor in corto.serie), 1)
        largo = self.resumen(mermas.Periodo(hoy() - timedelta(days=89), hoy()))
        self.assertTrue(largo.por_semana)
        self.assertTrue(all(fecha.weekday() == 0 for fecha, _ in largo.serie))
        self.assertEqual(sum(valor for _, valor in largo.serie), 1)

    def test_detalle_por_paciente_ordenado_por_la_mas_antigua(self):
        reciente = paciente()
        antigua = paciente()
        preparada(reciente, dias_atras=1, usuario=self.e["tecnico"])
        preparada(antigua, dias_atras=5, usuario=self.e["tecnico"])
        preparada(antigua, dias_atras=2, usuario=self.e["tecnico"])
        detalle = self.resumen().pacientes
        self.assertEqual([d["paciente_id"] for d in detalle], [antigua.pk, reciente.pk])
        self.assertEqual(detalle[0]["sin_retirar"], 2)


class FiltrosTests(TestCase):
    def test_por_omision_ultimos_30_dias(self):
        periodo = FiltroMermasForm().periodo()
        self.assertEqual((periodo.fin, periodo.dias, periodo.tipo), (hoy(), 30, "todos"))

    def test_rechaza_invertido_futuro_y_demasiado_largo(self):
        casos = (
            {"desde": hoy(), "hasta": hoy() - timedelta(days=1)},
            {"desde": hoy(), "hasta": hoy() + timedelta(days=1)},
            {"desde": hoy() - timedelta(days=399), "hasta": hoy()},
        )
        for datos in casos:
            form = FiltroMermasForm({clave: f"{valor:%Y-%m-%d}" for clave, valor in datos.items()})
            self.assertFalse(form.is_valid(), datos)
            self.assertEqual(form.periodo().dias, 30)

    def test_acepta_366_dias_y_tipo(self):
        form = FiltroMermasForm({"desde": f"{hoy() - timedelta(days=365):%Y-%m-%d}", "hasta": f"{hoy():%Y-%m-%d}", "tipo": "cronico"})
        self.assertTrue(form.is_valid())
        self.assertEqual((form.periodo().dias, form.periodo().tipo), (366, "cronico"))

    def test_mes_anterior_es_el_mes_calendario_completo(self):
        _, desde, hasta = atajos(hoy())[3]
        self.assertEqual(desde.day, 1)
        self.assertEqual((hasta + timedelta(days=1)).day, 1)
        self.assertLess(hasta, hoy().replace(day=1))
