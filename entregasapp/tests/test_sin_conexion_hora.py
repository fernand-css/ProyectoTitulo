"""Spec 11, RF-11-08 y RF-11-15: hora del registro tomada del celular, con límites, y hora de llegada.

Datos sintéticos. Las horas se fijan relativas a la hora real del servidor (sin simular el reloj), así que cada
caso vale a cualquier hora en que corra la suite.
"""

import uuid
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from entregasapp.models import Entrega, IntentoEntrega, RecetaEntrega
from entregasapp.services import (
    FUERA_DE_PLAZO, HORA_INVALIDA, derivar_desde_merma, programar_entrega, registrar_entregada, registrar_no_entregada,
)
from recetasapp.models import Receta
from .ayudas import equipo, hoy, paciente, receta


def local(fecha, hora, minuto):
    return timezone.make_aware(datetime.combine(fecha, time(hora, minuto)))


def codigo(error):
    return error.exception.error_list[0].code


class HoraDelRegistroTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.encargado = self.equipo["encargado"]

    def visita(self, *, programada=None, fin=None):
        """Intento pendiente del encargado; `programada` puede ser anterior a hoy (atrasada)."""
        persona = paciente(edad=88)
        fijada = receta(persona)
        entrega = programar_entrega(self.qf, persona.pk, hoy(), self.encargado.pk, uuid.uuid4())
        if fin is not None:  # la vigencia cambia después de programar (programar exige recetas vigentes hoy)
            Receta.objects.filter(pk=fijada.pk).update(fecha_fin_exclusiva=fin)
        intento = entrega.intentos.get()
        if programada is not None:
            IntentoEntrega.objects.filter(pk=intento.pk).update(fecha_programada=programada)
            intento.refresh_from_db()
        return intento

    def test_guarda_la_hora_del_celular_y_la_de_llegada(self):
        intento = self.visita(programada=hoy() - timedelta(days=1))
        hecho = timezone.now() - timedelta(minutes=50)
        antes = timezone.now()
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4(), registrado_en=hecho)
        intento.refresh_from_db()
        self.assertEqual(intento.registrado_en, hecho)
        self.assertGreaterEqual(intento.sincronizado_en, antes)
        self.assertEqual(intento.registrado_por, self.encargado)
        self.assertEqual(Entrega.objects.get(pk=intento.entrega_id).cerrada_en, hecho)

    def test_sin_el_parametro_todo_sigue_como_en_el_08(self):
        intento = self.visita()
        antes = timezone.now()
        registrar_no_entregada(self.encargado, intento.pk, "sin_receptor", "", uuid.uuid4())
        intento.refresh_from_db()
        self.assertGreaterEqual(intento.registrado_en, antes)
        self.assertIsNone(intento.sincronizado_en)

    def test_hora_futura_mas_alla_de_la_tolerancia_se_rechaza(self):
        intento = self.visita()
        with self.assertRaises(ValidationError) as error:
            registrar_entregada(self.encargado, intento.pk, uuid.uuid4(),
                                registrado_en=timezone.now() + timedelta(minutes=10))
        self.assertEqual(codigo(error), HORA_INVALIDA)
        intento.refresh_from_db()
        self.assertEqual(intento.resultado, "pendiente")

    def test_hora_dentro_de_la_tolerancia_se_acepta(self):
        intento = self.visita()
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4(), registrado_en=timezone.now() + timedelta(minutes=4))
        intento.refresh_from_db()
        self.assertEqual(intento.resultado, "entregada")

    def test_hora_sin_zona_se_rechaza(self):
        intento = self.visita()
        with self.assertRaises(ValidationError) as error:
            registrar_entregada(self.encargado, intento.pk, uuid.uuid4(), registrado_en=datetime(2026, 1, 1, 10, 0))
        self.assertEqual(codigo(error), HORA_INVALIDA)

    def test_fecha_anterior_a_la_programada_se_rechaza(self):
        intento = self.visita()  # programada hoy
        with self.assertRaises(ValidationError) as error:
            registrar_no_entregada(self.encargado, intento.pk, "sin_receptor", "", uuid.uuid4(),
                                   registrado_en=local(hoy() - timedelta(days=1), 18, 0))
        self.assertEqual(codigo(error), HORA_INVALIDA)

    def test_registro_de_hace_tres_dias_queda_fuera_de_plazo(self):
        hace_tres = hoy() - timedelta(days=3)
        intento = self.visita(programada=hace_tres)
        with self.assertRaises(ValidationError) as error:
            registrar_entregada(self.encargado, intento.pk, uuid.uuid4(), registrado_en=local(hace_tres, 12, 0))
        self.assertEqual(codigo(error), FUERA_DE_PLAZO)

    def test_registro_de_hace_dos_dias_aun_se_acepta(self):
        hace_dos = hoy() - timedelta(days=2)
        intento = self.visita(programada=hace_dos)
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4(), registrado_en=local(hace_dos, 12, 0))
        intento.refresh_from_db()
        self.assertEqual(intento.resultado, "entregada")

    def test_cruce_de_medianoche_evalua_la_vigencia_a_la_fecha_del_registro(self):
        ayer = hoy() - timedelta(days=1)
        intento = self.visita(programada=ayer, fin=hoy())  # vigente ayer, vencida hoy
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4(), registrado_en=local(ayer, 19, 50))
        intento.refresh_from_db()
        self.assertEqual(timezone.localtime(intento.registrado_en), local(ayer, 19, 50))
        vinculo = RecetaEntrega.objects.get(entrega_id=intento.entrega_id)
        self.assertEqual(vinculo.resultado, "descontada")
        self.assertEqual(Receta.objects.get(pk=vinculo.receta_id).entregas_completadas, 1)

    def test_con_senal_la_misma_receta_vencida_hoy_no_se_descuenta(self):
        intento = self.visita(fin=hoy())
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4())
        self.assertEqual(RecetaEntrega.objects.get(entrega_id=intento.entrega_id).resultado, "no_descontada")

    def test_reenvio_tardio_de_un_registro_aplicado_no_se_rechaza(self):
        intento = self.visita()
        operacion = uuid.uuid4()
        hecho = timezone.now() - timedelta(minutes=5)
        registrar_entregada(self.encargado, intento.pk, operacion, registrado_en=hecho)
        repetido = registrar_entregada(self.encargado, intento.pk, operacion,
                                       registrado_en=timezone.now() + timedelta(hours=1))
        self.assertTrue(repetido.repetido)
        self.assertEqual(Receta.objects.filter(entregas_completadas=1).count(), 1)

    def test_lo_preparado_se_evalua_a_su_fecha_de_preparacion(self):
        from indicadoresapp.tests.ayudas import preparada

        persona = paciente(edad=85)
        ayer = hoy() - timedelta(days=1)
        # Vigente hace 3 días (preparación), vencida ayer (registro): se descuenta por la regla del 13.
        vence = receta(persona, inicio=hoy() - timedelta(days=60), fin=ayer)
        preparacion = preparada(persona, dias_atras=3, receta_=vence, usuario=self.equipo["tecnico"])
        entrega = derivar_desde_merma(self.qf, persona.pk, hoy(), self.encargado.pk, uuid.uuid4())
        intento = entrega.intentos.get()
        IntentoEntrega.objects.filter(pk=intento.pk).update(fecha_programada=ayer)
        registrar_entregada(self.encargado, intento.pk, uuid.uuid4(), registrado_en=local(ayer, 17, 0))
        vinculo = RecetaEntrega.objects.get(entrega=entrega, preparacion=preparacion)
        self.assertEqual(vinculo.resultado, "descontada")


class DetalleConDosHorasTests(TestCase):
    """RF-11-15: la Q.F. ve la hora del registro y la de llegada."""

    def setUp(self):
        self.equipo = equipo()
        persona = paciente(edad=88)
        receta(persona)
        entrega = programar_entrega(self.equipo["qf"], persona.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        self.intento = entrega.intentos.get()

    def test_detalle_y_pendientes_muestran_las_dos_horas(self):
        hecho = timezone.now() - timedelta(minutes=30)
        registrar_no_entregada(self.equipo["encargado"], self.intento.pk, "sin_receptor", "", uuid.uuid4(),
                               registrado_en=hecho)
        self.intento.refresh_from_db()
        registrado = f"{timezone.localtime(hecho):%H:%M}</time> · recibida a las"
        llegada = f"{timezone.localtime(self.intento.sincronizado_en):%H:%M}</time>"
        self.client.force_login(self.equipo["qf"])
        for url in (reverse("entregasapp:detalle", args=[self.intento.entrega_id]), reverse("entregasapp:pendientes")):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn("Registrada sin conexión a las", html)
                self.assertIn(registrado, html)
                self.assertIn(llegada, html)

    def test_con_senal_no_aparece_el_texto(self):
        registrar_no_entregada(self.equipo["encargado"], self.intento.pk, "sin_receptor", "", uuid.uuid4())
        self.client.force_login(self.equipo["qf"])
        html = self.client.get(reverse("entregasapp:detalle", args=[self.intento.entrega_id])).content.decode()
        self.assertNotIn("Registrada sin conexión", html)
