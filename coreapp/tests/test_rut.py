"""Casos válidos, entradas mal formadas y generación reproducible."""

from random import Random

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from coreapp.utils.rut import calcular_dv, formatear_rut, normalizar_rut, validar_rut
from coreapp.utils.sinteticos import generar_rut, generar_ruts


class RutTests(SimpleTestCase):
    def test_formatos_validos(self):
        for valor in ("12345678-5", "12.345.678-5", "123456785", " 12.345.678-5 "):
            with self.subTest(valor=valor):
                self.assertTrue(validar_rut(valor))
                self.assertEqual(normalizar_rut(valor), "12345678-5")
                self.assertEqual(formatear_rut(valor), "12.345.678-5")

    def test_digitos_k_y_cero(self):
        self.assertTrue(validar_rut("6.000.000-k"))
        self.assertEqual(normalizar_rut("6000000k"), "6000000-K")
        self.assertEqual(calcular_dv("10000004"), "0")
        self.assertTrue(validar_rut("10000004-0"))

    def test_rechaza_dv_incorrecto_y_formato_malformado(self):
        for valor in ("12345678-9", "", None, 123456785, "0-0", "00000000-0",
                      "12..345.678-5", "123.45.678-5", "12345678--5", "１２３４５６７８-5",
                      "123456789-0", "<script>", "12345678-5 extra"):
            with self.subTest(valor=valor):
                self.assertFalse(validar_rut(valor))
                with self.assertRaises(ValidationError) as error:
                    normalizar_rut(valor)
                self.assertEqual(error.exception.messages, ["Ingresa un RUT válido."])

    def test_formatear_no_oculta_dv_incorrecto(self):
        with self.assertRaises(ValidationError):
            formatear_rut("12345678-9")

    def test_sinteticos_validos_unicos_y_reproducibles(self):
        ruts = generar_ruts(670, Random(2026))
        self.assertEqual(ruts, generar_ruts(670, Random(2026)))
        self.assertEqual(len(set(ruts)), 670)
        self.assertTrue(all(validar_rut(valor) for valor in ruts))
        self.assertNotEqual(ruts, generar_ruts(670, Random(2027)))

    def test_generador_individual_y_cantidad_cero(self):
        self.assertEqual(generar_rut(Random(1)), generar_rut(Random(1)))
        self.assertTrue(validar_rut(generar_rut(Random(2))))
        self.assertEqual(generar_ruts(0, Random(1)), [])
        with self.assertRaises(ValueError):
            generar_ruts(-1, Random(1))
