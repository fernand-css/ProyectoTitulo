"""Datos de presentación de la libreta: situación, casillas, vigencia y resumen del paciente."""

from datetime import date, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase

from recetasapp import presentacion
from recetasapp.services import evaluar_elegibilidad


def receta(inicio=date(2026, 1, 1), fin_exclusiva=date(2027, 1, 1), completadas=0, maximo=6, **extra):
    return SimpleNamespace(fecha_inicio=inicio, fecha_fin_exclusiva=fin_exclusiva, entregas_completadas=completadas, max_entregas=maximo, **extra)


class SituacionTests(SimpleTestCase):
    def test_cada_situacion(self):
        hoy = date(2026, 6, 1)
        casos = {
            "vigente": receta(),
            "futura": receta(inicio=date(2026, 7, 1)),
            "vencida": receta(inicio=date(2025, 1, 1), fin_exclusiva=date(2026, 1, 1)),
            "agotada": receta(completadas=6),
        }
        for clave, ejemplo in casos.items():
            with self.subTest(clave=clave):
                self.assertEqual(presentacion.situacion(ejemplo, hoy)["clave"], clave)

    def test_limites_del_calendario(self):
        ejemplo = receta(inicio=date(2026, 1, 1), fin_exclusiva=date(2026, 7, 1))
        self.assertEqual(presentacion.situacion(ejemplo, date(2025, 12, 31))["clave"], "futura")
        self.assertEqual(presentacion.situacion(ejemplo, date(2026, 1, 1))["clave"], "vigente")
        self.assertEqual(presentacion.situacion(ejemplo, date(2026, 6, 30))["clave"], "vigente")
        self.assertEqual(presentacion.situacion(ejemplo, date(2026, 7, 1))["clave"], "vencida")

    def test_vencida_tiene_prioridad_sobre_agotada(self):
        ejemplo = receta(inicio=date(2025, 1, 1), fin_exclusiva=date(2026, 1, 1), completadas=6)
        self.assertEqual(presentacion.situacion(ejemplo, date(2026, 6, 1))["clave"], "vencida")

    def test_coincide_con_la_regla_de_elegibilidad_del_servicio(self):
        """«Vigente» debe significar exactamente lo que el servicio llama elegible."""
        base = date(2025, 12, 25)
        for completadas in (0, 5, 6):
            ejemplo = receta(inicio=date(2026, 1, 1), fin_exclusiva=date(2026, 7, 1), completadas=completadas)
            for dias in range(0, 200, 7):
                hoy = base + timedelta(days=dias)
                with self.subTest(completadas=completadas, hoy=hoy):
                    self.assertEqual(
                        presentacion.situacion(ejemplo, hoy)["clave"] == "vigente",
                        evaluar_elegibilidad(ejemplo, hoy)["elegible"],
                    )

    def test_toda_situacion_tiene_icono_texto_y_clase(self):
        for situacion in presentacion.SITUACIONES.values():
            self.assertTrue(situacion["texto"])
            self.assertTrue(situacion["icono"].startswith("i-"))
            self.assertTrue(situacion["clase"].startswith("insignia-"))


class CasillasTests(SimpleTestCase):
    def test_estados_de_las_casillas(self):
        casillas = presentacion.casillas(receta(completadas=1, maximo=3))
        self.assertEqual([c["estado"] for c in casillas], ["sellada", "libre", "libre"])
        self.assertEqual([c["numero"] for c in casillas], [1, 2, 3])

    def test_la_proxima_solo_se_marca_si_se_pide(self):
        casillas = presentacion.casillas(receta(completadas=1, maximo=3), proxima=True)
        self.assertEqual([c["estado"] for c in casillas], ["sellada", "proxima", "libre"])

    def test_receta_completa_no_tiene_proxima(self):
        casillas = presentacion.casillas(receta(completadas=3, maximo=3), proxima=True)
        self.assertEqual([c["estado"] for c in casillas], ["sellada"] * 3)

    def test_la_entrega_se_asocia_a_su_numero(self):
        entrega = SimpleNamespace(numero=2)
        casillas = presentacion.casillas(receta(completadas=2, maximo=3), [entrega])
        self.assertIsNone(casillas[0]["entrega"])
        self.assertIs(casillas[1]["entrega"], entrega)

    def test_cupos_grandes_se_muestran_como_barra(self):
        self.assertEqual(len(presentacion.casillas(receta(maximo=presentacion.MAX_CASILLAS))), presentacion.MAX_CASILLAS)
        self.assertIsNone(presentacion.casillas(receta(maximo=presentacion.MAX_CASILLAS + 1)))

    def test_porcentaje_de_entregas(self):
        self.assertEqual(presentacion.porcentaje_entregas(receta(completadas=3, maximo=6)), 50)
        self.assertEqual(presentacion.porcentaje_entregas(receta(completadas=0, maximo=6)), 0)
        self.assertEqual(presentacion.porcentaje_entregas(receta(completadas=6, maximo=6)), 100)


class VigenciaTests(SimpleTestCase):
    def test_dentro_de_la_vigencia(self):
        linea = presentacion.linea_vigencia(receta(), date(2026, 7, 2))
        self.assertEqual(linea["fase"], "dentro")
        self.assertEqual(linea["porcentaje"], 50)
        self.assertEqual(linea["texto"], "Quedan 183 días de vigencia")
        self.assertEqual(linea["inicio"], date(2026, 1, 1))
        self.assertEqual(linea["ultimo_dia"], date(2026, 12, 31))

    def test_ultimo_dia_usa_singular_y_frase_propia(self):
        linea = presentacion.linea_vigencia(receta(), date(2026, 12, 31))
        self.assertEqual(linea["texto"], "Hoy es el último día de vigencia")
        self.assertEqual(linea["fase"], "dentro")

    def test_antes_de_comenzar(self):
        linea = presentacion.linea_vigencia(receta(), date(2025, 12, 31))
        self.assertEqual((linea["fase"], linea["porcentaje"], linea["texto"]), ("antes", 0, "Comienza en 1 día"))
        self.assertEqual(presentacion.linea_vigencia(receta(), date(2025, 12, 1))["texto"], "Comienza en 31 días")

    def test_despues_de_vencer(self):
        linea = presentacion.linea_vigencia(receta(), date(2027, 1, 1))
        self.assertEqual((linea["fase"], linea["porcentaje"], linea["texto"]), ("despues", 100, "Venció hace 1 día"))
        self.assertEqual(presentacion.linea_vigencia(receta(), date(2027, 1, 11))["texto"], "Venció hace 11 días")

    def test_el_porcentaje_nunca_sale_del_rango(self):
        for hoy in (date(2000, 1, 1), date(2026, 1, 1), date(2026, 12, 31), date(2099, 1, 1)):
            self.assertTrue(0 <= presentacion.linea_vigencia(receta(), hoy)["porcentaje"] <= 100)


class ResumenPacienteTests(SimpleTestCase):
    hoy = date(2026, 6, 1)

    def test_sin_recetas(self):
        resumen = presentacion.resumen_paciente([], self.hoy)
        self.assertIsNone(resumen["situacion"])
        self.assertEqual(resumen["texto"], "Sin recetas registradas")

    def test_elige_la_vigente_aunque_no_sea_la_mas_reciente(self):
        futura = receta(inicio=date(2026, 9, 1), fin_exclusiva=date(2027, 9, 1), codigo="F")
        vigente = receta(completadas=2, codigo="V")
        resumen = presentacion.resumen_paciente([futura, vigente], self.hoy)
        self.assertEqual(resumen["receta"].codigo, "V")
        self.assertEqual(resumen["situacion"]["clave"], "vigente")
        self.assertEqual(resumen["texto"], "2 de 6 entregas")
        self.assertEqual(resumen["detalle"], "Quedan 4")
        self.assertEqual(resumen["puntos"], [True, True, False, False, False, False])

    def test_sin_vigente_muestra_la_mas_reciente_y_el_motivo(self):
        casos = {
            "vencida": (receta(inicio=date(2025, 1, 1), fin_exclusiva=date(2026, 1, 1)), "La última receta está vencida"),
            "agotada": (receta(completadas=6), "La última receta agotó sus entregas"),
            "futura": (receta(inicio=date(2026, 9, 1), fin_exclusiva=date(2027, 9, 1)), "La receta aún no inicia su vigencia"),
        }
        for clave, (ejemplo, motivo) in casos.items():
            with self.subTest(clave=clave):
                resumen = presentacion.resumen_paciente([ejemplo], self.hoy)
                self.assertEqual(resumen["situacion"]["clave"], clave)
                self.assertEqual((resumen["texto"], resumen["detalle"]), ("Sin receta vigente", motivo))

    def test_cupos_sobre_el_limite_de_puntos_usan_barra(self):
        resumen = presentacion.resumen_paciente([receta(completadas=5, maximo=20)], self.hoy)
        self.assertIsNone(resumen["puntos"])
        self.assertEqual(resumen["porcentaje"], 25)
        self.assertEqual(len(presentacion.resumen_paciente([receta(maximo=presentacion.MAX_PUNTOS)], self.hoy)["puntos"]), presentacion.MAX_PUNTOS)


class ReporteDeCargaTests(SimpleTestCase):
    def test_categorias_en_orden_y_con_su_cantidad(self):
        carga = SimpleNamespace(filas_creadas=5, filas_actualizadas=4, filas_sin_cambios=3, filas_omitidas=2, filas_rechazadas=1)
        categorias = presentacion.categorias_carga(carga)
        self.assertEqual([c["cantidad"] for c in categorias], [5, 4, 3, 2, 1])
        self.assertEqual([c["clave"] for c in categorias], ["creadas", "actualizadas", "sin-cambios", "omitidas", "rechazadas"])
        self.assertTrue(all(c["texto"] and c["icono"].startswith("i-") for c in categorias))

    def test_cada_estado_de_fila_tiene_icono_y_categoria_de_la_barra(self):
        claves = {clave for clave, *_ in presentacion.CATEGORIAS_CARGA}
        for estado in ("creada", "actualizada", "sin_cambios", "omitida", "rechazada"):
            fila = presentacion.preparar_fila(SimpleNamespace(estado=estado))
            self.assertTrue(fila.icono.startswith("i-"))
            self.assertIn(fila.clase, claves)
