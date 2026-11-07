"""Pruebas puras. No crean bases de datos ni ejecutan migraciones."""
import unittest

from apps.turnos.dominio import (
    ACTIVOS, GENERAL, PREFERENCIAL, TERMINALES,
    TRANSICIONES, numero_visible, seleccionar, validar_peso, validar_transicion,
)


class MotorPonderadoTests(unittest.TestCase):
    def secuencia(self, pasos, pesos=(2, 1), disponibles=(GENERAL, PREFERENCIAL)):
        siguiente, consumidos = GENERAL, 0
        resultado = []
        for _ in range(pasos):
            seleccion = seleccionar(*pesos, siguiente, consumidos, disponibles)
            resultado.append(seleccion.categoria)
            siguiente, consumidos = seleccion.siguiente_categoria, seleccion.consumidos
        return resultado

    def test_ciclo_dos_generales_un_preferencial(self):
        self.assertEqual(self.secuencia(9), [GENERAL, GENERAL, PREFERENCIAL] * 3)

    def test_pesos_configurables(self):
        self.assertEqual(self.secuencia(10, (3, 2)), [GENERAL] * 3 + [PREFERENCIAL] * 2 + [GENERAL] * 3 + [PREFERENCIAL] * 2)

    def test_uno_a_uno(self):
        self.assertEqual(self.secuencia(6, (1, 1)), [GENERAL, PREFERENCIAL] * 3)

    def test_no_se_detiene_si_falta_preferencial(self):
        self.assertEqual(self.secuencia(12, disponibles=(GENERAL,)), [GENERAL] * 12)

    def test_no_se_detiene_si_falta_general(self):
        self.assertEqual(self.secuencia(12, disponibles=(PREFERENCIAL,)), [PREFERENCIAL] * 12)

    def test_categoria_vacia_no_acumula_creditos(self):
        siguiente, consumidos = GENERAL, 0
        for _ in range(100):
            elegido = seleccionar(2, 1, siguiente, consumidos, (GENERAL,))
            siguiente, consumidos = elegido.siguiente_categoria, elegido.consumidos
        secuencia = []
        for _ in range(4):
            elegido = seleccionar(2, 1, siguiente, consumidos, (GENERAL, PREFERENCIAL))
            secuencia.append(elegido.categoria)
            siguiente, consumidos = elegido.siguiente_categoria, elegido.consumidos
        self.assertEqual(secuencia, [PREFERENCIAL, GENERAL, GENERAL, PREFERENCIAL])

    def test_se_descarta_cupo_incompleto_de_categoria_vacia(self):
        elegido = seleccionar(4, 2, GENERAL, 3, (PREFERENCIAL,))
        self.assertEqual((elegido.categoria, elegido.siguiente_categoria, elegido.consumidos), (PREFERENCIAL, PREFERENCIAL, 1))

    def test_cola_vacia_reinicia_ciclo(self):
        elegido = seleccionar(2, 1, PREFERENCIAL, 0, ())
        self.assertIsNone(elegido.categoria)
        self.assertEqual((elegido.siguiente_categoria, elegido.consumidos), (GENERAL, 0))

    def test_pesos_invalidos(self):
        for peso in (0, -1, 101, 1.5, "2", True, None):
            with self.subTest(peso=peso), self.assertRaises(ValueError):
                validar_peso(peso)

    def test_entrada_invalida_no_modifica_estado(self):
        estado = (GENERAL, 1)
        with self.assertRaises(ValueError):
            seleccionar(0, 1, *estado, (GENERAL,))
        self.assertEqual(estado, (GENERAL, 1))

    def test_estado_de_arbitraje_invalido(self):
        for categoria, consumidos in (("OTRA", 0), (GENERAL, -1), (GENERAL, 2), (GENERAL, True)):
            with self.subTest(categoria=categoria, consumidos=consumidos), self.assertRaises(ValueError):
                seleccionar(2, 1, categoria, consumidos, (GENERAL,))

    def test_categoria_disponible_invalida(self):
        with self.assertRaises(ValueError):
            seleccionar(2, 1, GENERAL, 0, ("OTRA",))


class EstadosYNumeracionTests(unittest.TestCase):
    def test_numeros_independientes_de_la_pk(self):
        self.assertEqual(numero_visible(GENERAL, 1), "G-001")
        self.assertEqual(numero_visible(PREFERENCIAL, 1), "P-001")
        self.assertEqual(numero_visible(GENERAL, 1000), "G-1000")

    def test_numero_invalido(self):
        for categoria, correlativo in (("OTRA", 1), (GENERAL, 0), (GENERAL, -1), (GENERAL, True)):
            with self.subTest(categoria=categoria, correlativo=correlativo), self.assertRaises(ValueError):
                numero_visible(categoria, correlativo)

    def test_transiciones_del_flujo_y_cierres_alternativos(self):
        for origen, destino in (
            ("PENDIENTE", "LLAMADO"), ("LLAMADO", "EN_ATENCION"),
            ("EN_ATENCION", "ATENDIDO"), ("LLAMADO", "AUSENTE"),
            ("PENDIENTE", "CANCELADO"),
        ):
            with self.subTest(origen=origen, destino=destino):
                validar_transicion(origen, destino)

    def test_todos_los_saltos_no_autorizados_se_rechazan(self):
        for origen in TRANSICIONES:
            for destino in TRANSICIONES:
                if destino not in TRANSICIONES[origen]:
                    with self.subTest(origen=origen, destino=destino), self.assertRaises(ValueError):
                        validar_transicion(origen, destino)

    def test_terminales_no_se_reabren(self):
        for estado in TERMINALES:
            self.assertFalse(TRANSICIONES[estado])
            self.assertNotIn(estado, ACTIVOS)

    def test_ausencia_solo_como_transicion_explicita(self):
        self.assertIn("AUSENTE", TRANSICIONES["LLAMADO"])
        self.assertNotIn("AUSENTE", TRANSICIONES["PENDIENTE"])
        self.assertNotIn("AUSENTE", TRANSICIONES["EN_ATENCION"])


if __name__ == "__main__":
    unittest.main()
