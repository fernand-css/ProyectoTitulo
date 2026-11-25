"""Períodos del panel (RF-13-11 y RF-13-12): ocho clases, flechas, granularidad, comparación y filtro GET."""

from datetime import date, timedelta

from django.test import SimpleTestCase

from indicadoresapp.periodos import (
    ANIO, DIA, MES, MES_SERIE, PERSONALIZADO, SEMANA, SEMESTRE, SIETE_DIAS, UN_DIA, FiltroPanelForm, Periodo,
    opciones, periodo_de, periodo_por_omision,
)

HOY = date(2026, 11, 25)  # miércoles


def filtro(**datos):
    return FiltroPanelForm({clave: valor for clave, valor in datos.items()}, hoy=HOY)


class ClasesTests(SimpleTestCase):
    def test_por_omision_es_el_mes_en_curso(self):
        periodo = periodo_por_omision(HOY)
        self.assertEqual((periodo.inicio, periodo.fin, periodo.clase, periodo.tipo), (date(2026, 11, 1), HOY, MES, "todos"))
        self.assertEqual(periodo.granularidad, DIA)
        self.assertEqual(periodo.titulo, "Noviembre de 2026, del 1 al 25")

    def test_moviles_terminan_hoy(self):
        uno, siete = periodo_de(UN_DIA, HOY), periodo_de(SIETE_DIAS, HOY)
        self.assertEqual((uno.inicio, uno.fin), (HOY, HOY))
        self.assertEqual((siete.inicio, siete.fin, siete.granularidad), (date(2026, 11, 19), HOY, DIA))
        self.assertEqual(uno.titulo, "Hoy, 25 de noviembre de 2026")
        self.assertEqual(siete.titulo, "Últimos 7 días: del 19 al 25 de noviembre de 2026")
        self.assertIsNone(siete.anterior())
        self.assertIsNone(siete.siguiente(HOY))

    def test_semestre_por_semana_con_flechas(self):
        semestre = periodo_de(SEMESTRE, HOY)
        self.assertEqual((semestre.inicio, semestre.fin, semestre.granularidad), (date(2026, 7, 1), HOY, SEMANA))
        self.assertEqual(semestre.titulo, "Segundo semestre de 2026, hasta el 25 de noviembre")
        self.assertIsNone(semestre.siguiente(HOY))
        anterior = semestre.anterior()
        self.assertEqual((anterior.inicio, anterior.fin), (date(2026, 1, 1), date(2026, 6, 30)))
        self.assertEqual(anterior.titulo, "Primer semestre de 2026")
        self.assertEqual(anterior.siguiente(HOY), semestre)
        self.assertTrue(all(clave.weekday() == 0 for clave in semestre.claves()))

    def test_anio_por_mes(self):
        anio = periodo_de(ANIO, HOY)
        self.assertEqual((anio.inicio, anio.fin, anio.granularidad), (date(2026, 1, 1), HOY, MES_SERIE))
        self.assertEqual(anio.claves(), [date(2026, m, 1) for m in range(1, 12)])
        self.assertEqual(anio.titulo, "Año 2026, hasta el 25 de noviembre")
        self.assertEqual(anio.anterior().titulo, "Año 2025")

    def test_mes_completo_y_navegacion(self):
        octubre = periodo_de(MES, HOY, ref=date(2026, 10, 15))
        self.assertEqual((octubre.inicio, octubre.fin), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(octubre.titulo, "Octubre de 2026")
        self.assertEqual(octubre.siguiente(HOY).fin, HOY)
        self.assertEqual(octubre.anterior().fin, date(2026, 9, 30))

    def test_personalizado_por_su_largo(self):
        self.assertEqual(Periodo(HOY - timedelta(days=30), HOY).granularidad, DIA)
        self.assertEqual(Periodo(HOY - timedelta(days=89), HOY).granularidad, SEMANA)
        self.assertEqual(Periodo(HOY - timedelta(days=300), HOY).granularidad, MES_SERIE)
        self.assertEqual(Periodo(date(2026, 10, 1), date(2026, 10, 31)).titulo, "Del 1 al 31 de octubre de 2026")
        self.assertEqual(Periodo(date(2025, 12, 20), date(2026, 1, 5)).titulo,
                         "Del 20 de diciembre de 2025 al 5 de enero de 2026")


class ComparacionTests(SimpleTestCase):
    def test_mes_en_curso_con_los_mismos_dias_del_anterior(self):
        anterior = periodo_por_omision(HOY).anterior_equivalente()
        self.assertEqual((anterior.inicio, anterior.fin), (date(2026, 10, 1), date(2026, 10, 25)))
        self.assertEqual(anterior.rango, "del 1 al 25 de octubre de 2026")

    def test_mes_anterior_mas_corto_se_corta_en_su_ultimo_dia(self):
        marzo = periodo_de(MES, HOY, ref=date(2026, 3, 1))
        anterior = marzo.anterior_equivalente()
        self.assertEqual((anterior.inicio, anterior.fin), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_moviles_y_personalizado_con_los_dias_inmediatamente_anteriores(self):
        siete = periodo_de(SIETE_DIAS, HOY).anterior_equivalente()
        self.assertEqual((siete.inicio, siete.fin), (date(2026, 11, 12), date(2026, 11, 18)))
        diez = Periodo(date(2026, 11, 16), HOY).anterior_equivalente()
        self.assertEqual((diez.inicio, diez.fin), (date(2026, 11, 6), date(2026, 11, 15)))


class FiltroTests(SimpleTestCase):
    def test_sin_parametros_y_enlaces_antiguos(self):
        self.assertEqual(FiltroPanelForm(hoy=HOY).elegido().clase, MES)
        antiguo = filtro(desde="2026-10-01", hasta="2026-10-31")
        self.assertTrue(antiguo.is_valid())
        self.assertEqual((antiguo.elegido().clase, antiguo.elegido().dias), (PERSONALIZADO, 31))

    def test_clase_y_referencia(self):
        periodo = filtro(periodo="mes", ref="2026-10-01", tipo="cronico").elegido()
        self.assertEqual((periodo.inicio, periodo.fin, periodo.tipo), (date(2026, 10, 1), date(2026, 10, 31), "cronico"))
        self.assertEqual(filtro(periodo="anio").elegido().inicio, date(2026, 1, 1))

    def test_rechazos_vuelven_al_mes_en_curso_con_el_tipo(self):
        casos = (
            {"periodo": "personalizado", "desde": "2026-11-25", "hasta": "2026-11-26"},
            {"periodo": "personalizado", "desde": "2026-11-25", "hasta": "2026-11-24"},
            {"periodo": "personalizado", "desde": "2025-10-01", "hasta": "2026-11-25"},
            {"periodo": "mes", "ref": "2026-12-01"},
            {"periodo": "trimestre"},
        )
        for datos in casos:
            form = filtro(tipo="general", **datos)
            self.assertFalse(form.is_valid(), datos)
            periodo = form.elegido()
            self.assertEqual((periodo.clase, periodo.inicio, periodo.tipo), (MES, date(2026, 11, 1), "general"), datos)

    def test_acepta_366_dias(self):
        form = filtro(periodo="personalizado", desde=f"{HOY - timedelta(days=365):%Y-%m-%d}", hasta=f"{HOY:%Y-%m-%d}")
        self.assertTrue(form.is_valid())
        self.assertEqual(form.elegido().dias, 366)

    def test_consulta_y_opciones(self):
        periodo = periodo_por_omision(HOY)
        self.assertEqual(periodo.consulta(), "?periodo=mes&ref=2026-11-01&tipo=todos")
        self.assertEqual(Periodo(date(2026, 10, 1), date(2026, 10, 31)).consulta(),
                         "?periodo=personalizado&desde=2026-10-01&hasta=2026-10-31&tipo=todos")
        botones = opciones(periodo, HOY)
        self.assertEqual([b["texto"] for b in botones],
                         ["1 día", "3 días", "7 días", "14 días", "Mes", "Semestre", "Año", "Personalizado"])
        self.assertEqual([b["clase"] for b in botones if b["actual"]], [MES])
        self.assertEqual(botones[2]["url"], "?periodo=7d&tipo=todos")
