"""RF-08-01: quién es elegible para el reparto, con la regla de edad compartida con el tótem del 04."""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from entregasapp.consultas import elegibles, es_elegible, limite_nacimiento
from entregasapp.models import InscripcionReparto
from turnosapp.services import ErrorEmision, clasificar_atencion
from .ayudas import cuenta, nacimiento_para, paciente


class ElegibilidadTests(TestCase):
    def setUp(self):
        self.fecha = date(2026, 11, 11)

    def test_limites_de_edad_postrado_y_cronico(self):
        """RF-08-01 (2026-11-13): 80 años cumplidos o más; el de 79 años y 364 días aún no."""
        casi_80 = paciente(nacimiento=nacimiento_para(80, self.fecha, dias_extra=1))  # 79 años y 364 días
        con_80 = paciente(nacimiento=nacimiento_para(80, self.fecha))  # 80 recién cumplidos
        con_81 = paciente(nacimiento=nacimiento_para(81, self.fecha))
        postrado = paciente(nacimiento=nacimiento_para(50, self.fecha), postrado=True)
        cronico = paciente(nacimiento=nacimiento_para(60, self.fecha), cronico=True)
        self.assertEqual(casi_80.edad_en(self.fecha), 79)
        self.assertEqual(con_80.edad_en(self.fecha), 80)
        resultado = {p.pk: es_elegible(p, self.fecha) for p in (casi_80, con_80, con_81, postrado, cronico)}
        self.assertEqual(resultado, {casi_80.pk: False, con_80.pk: True, con_81.pk: True, postrado.pk: True,
                                     cronico.pk: False})
        self.assertCountEqual(elegibles(self.fecha).values_list("pk", flat=True), [con_80.pk, con_81.pk, postrado.pk])

    def test_el_totem_bloquea_desde_los_80_y_da_preferencial_a_los_79(self):
        casi_80 = paciente(nacimiento=nacimiento_para(80, self.fecha, dias_extra=1))
        self.assertEqual(clasificar_atencion(casi_80, self.fecha), "preferencial")
        for edad in (80, 81):
            with self.subTest(edad=edad), self.assertRaises(ErrorEmision) as error:
                clasificar_atencion(paciente(nacimiento=nacimiento_para(edad, self.fecha)), self.fecha)
            self.assertEqual(error.exception.code, "domicilio")
            self.assertEqual(error.exception.message, "Consulta tu despacho con el personal.")

    def test_la_excepcion_vigente_hace_elegible_y_la_retirada_ya_no(self):
        qf = cuenta("qf_elegibilidad")
        cronico = paciente(nacimiento=nacimiento_para(60, self.fecha), cronico=True)
        inscripcion = InscripcionReparto.objects.create(paciente=cronico, motivo="sin_red_apoyo", creado_por=qf)
        self.assertTrue(es_elegible(cronico, self.fecha))
        self.assertIn(cronico.pk, elegibles(self.fecha).values_list("pk", flat=True))
        InscripcionReparto.objects.filter(pk=inscripcion.pk).update(retirada_en=timezone.now(), retirada_por=qf)
        self.assertFalse(es_elegible(cronico, self.fecha))
        self.assertNotIn(cronico.pk, elegibles(self.fecha).values_list("pk", flat=True))

    def test_la_lista_no_duplica_pacientes_con_varias_inscripciones_historicas(self):
        qf = cuenta("qf_historial_elegibilidad")
        cronico = paciente(nacimiento=nacimiento_para(60, self.fecha))
        for _ in range(2):
            InscripcionReparto.objects.create(paciente=cronico, motivo="discapacidad", retirada_en=timezone.now(), retirada_por=qf)
        InscripcionReparto.objects.create(paciente=cronico, motivo="discapacidad")
        self.assertEqual(list(elegibles(self.fecha).values_list("pk", flat=True)), [cronico.pk])

    def test_el_29_de_febrero_usa_el_28_en_anios_sin_ese_dia(self):
        fecha = date(2028, 2, 29)
        self.assertEqual(limite_nacimiento(fecha), date(1948, 2, 29))
        self.assertEqual(limite_nacimiento(date(2027, 2, 28)), date(1947, 2, 28))
        self.assertEqual(limite_nacimiento(date(2026, 2, 28)), date(1946, 2, 28))
        justo = paciente(nacimiento=date(1948, 2, 29))
        tarde = paciente(nacimiento=date(1948, 3, 1))
        self.assertTrue(es_elegible(justo, fecha))
        self.assertFalse(es_elegible(tarde, fecha))
        self.assertEqual(list(elegibles(fecha).filter(pk__in=[justo.pk, tarde.pk]).values_list("pk", flat=True)), [justo.pk])

    def test_la_regla_compartida_coincide_con_80_o_mas(self):
        """Una sola regla para el tótem y el reparto: postrado o `edad >= 80` (RF-08-01, 2026-11-13)."""
        fechas = [date(2026, 11, 11), date(2028, 2, 29), date(2027, 3, 1), date(2026, 1, 1)]
        nacimientos = [date(1945, 11, 11), date(1945, 11, 12), date(1946, 2, 28), date(1944, 2, 29),
                       date(1947, 3, 1), date(1966, 11, 11), date(1966, 11, 12), date(1990, 6, 15),
                       # Bordes del corte de 80 (2026-11-13), incluido el 29 de febrero.
                       date(1946, 11, 11), date(1946, 11, 12), date(1948, 2, 29), date(1948, 3, 1),
                       date(1947, 1, 1), date(1946, 1, 2)]
        for fecha in fechas:
            for nacimiento in nacimientos:
                for postrado in (False, True):
                    with self.subTest(fecha=fecha, nacimiento=nacimiento, postrado=postrado):
                        persona = paciente(nacimiento=nacimiento, postrado=postrado)
                        edad = fecha.year - nacimiento.year - ((fecha.month, fecha.day) < (nacimiento.month, nacimiento.day))
                        esperado = postrado or edad >= 80
                        self.assertEqual(persona.requiere_despacho_en(fecha), esperado)
                        self.assertEqual(es_elegible(persona, fecha), esperado)
                        en_lista = elegibles(fecha).filter(pk=persona.pk).exists()
                        self.assertEqual(en_lista, esperado)  # `condicion_elegible` coincide con `es_elegible`
                        if esperado:
                            with self.assertRaises(ErrorEmision) as error:
                                clasificar_atencion(persona, fecha)
                            self.assertEqual(error.exception.code, "domicilio")
                        else:
                            self.assertIn(clasificar_atencion(persona, fecha), ("preferencial", "cronicos", "general"))

    def test_la_edad_del_paciente_sigue_calculandose_a_hoy(self):
        persona = paciente(edad=70)
        self.assertEqual(persona.edad, 70)
        self.assertEqual(persona.edad, persona.edad_en(timezone.localdate()))
        self.assertEqual(persona.edad_en(timezone.localdate() + timedelta(days=366 * 2)), 72)
