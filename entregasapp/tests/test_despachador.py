"""Despachador de avisos en el servidor web (quinta enmienda del spec 12, RF-12-24 a RF-12-28)."""

import time
from io import StringIO
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core import mail
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from entregasapp import checks, despachador as modulo, services
from entregasapp.despachador import Despachador, ciclo
from entregasapp.models import AvisoReparto
from recetasapp.models import Paciente
from .ayudas import equipo, visita


Estado = AvisoReparto.Estado


def esperar(condicion, segundos=10):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.05)
    return False


class ConfiguracionDespachadorTests(SimpleTestCase):
    def test_modos_validos_e_invalido(self):
        for modo in ("smtp", "simular", "no"):
            with self.settings(REPARTO_AVISOS_AUTOMATICOS=modo):
                self.assertEqual(checks.revisar_envio_automatico(), [])
        with self.settings(REPARTO_AVISOS_AUTOMATICOS="siempre"):
            self.assertEqual([e.id for e in checks.revisar_envio_automatico()], ["entregasapp.E009"])

    def test_desactivado_no_inicia_el_hilo(self):
        instancia = Despachador()
        with self.settings(REPARTO_AVISOS_AUTOMATICOS="no"):
            self.assertFalse(instancia.iniciar())
        self.assertFalse(instancia.activo)

    def test_el_ejecutor_de_pruebas_lo_desactiva(self):
        from django.conf import settings

        self.assertEqual(settings.REPARTO_AVISOS_AUTOMATICOS, "no")

    def test_los_comandos_no_lo_inician(self):
        self.assertFalse(modulo.despachador.activo)

    def test_ciclo_sobrevive_a_un_fallo_sin_registrar_datos(self):
        with patch("entregasapp.notificaciones.procesar_avisos", side_effect=RuntimeError("smtp a@example.invalid")):
            with self.assertLogs("entregasapp.despachador", level="WARNING") as registro:
                self.assertEqual(ciclo(Mock()), 0)
        self.assertNotIn("example.invalid", " ".join(registro.output))
        self.assertIn("RuntimeError", " ".join(registro.output))


@override_settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=())
class DespertarAlConfirmarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipo = equipo()
        cls.intento = visita(cls.equipo)
        cls.sin_correo = visita(cls.equipo)
        Paciente.objects.filter(pk=cls.intento.entrega.paciente_id).update(correo_avisos="familia@example.invalid")

    def test_aviso_pendiente_despierta_al_confirmar(self):
        with patch.object(modulo.despachador, "avisar") as avisar:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                services.iniciar_traslado(self.equipo["encargado"], self.intento.pk)
            self.assertEqual(len(callbacks), 1)
            avisar.assert_called_once_with()

    def test_aviso_omitido_no_despierta(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            services.iniciar_traslado(self.equipo["encargado"], self.sin_correo.pk)
        self.assertEqual(callbacks, [])

    def test_registro_repetido_no_despierta_dos_veces(self):
        operacion = uuid4()
        with self.captureOnCommitCallbacks(execute=False) as primero:
            services.registrar_entregada(self.equipo["encargado"], self.intento.pk, operacion)
        with self.captureOnCommitCallbacks(execute=False) as segundo:
            services.registrar_entregada(self.equipo["encargado"], self.intento.pk, operacion)
        self.assertEqual((len(primero), len(segundo)), (1, 0))

    def test_ciclo_envia_lo_pendiente(self):
        services.iniciar_traslado(self.equipo["encargado"], self.intento.pk)
        enviar = Mock(return_value=(Estado.SIMULADO, "simulado"))
        with patch("entregasapp.notificaciones.encolar_del_dia"):
            self.assertEqual(ciclo(enviar), 1)
        enviar.assert_called_once_with("familia@example.invalid", AvisoReparto.Tipo.EN_CAMINO)


@override_settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=(), REPARTO_AVISOS_AUTOMATICOS="simular")
class DespachadorEnSegundoPlanoTests(TransactionTestCase):
    """El hilo real envía sin comando, apenas se confirma el clic, y convive con el comando manual."""

    def setUp(self):
        sin_dia = patch("entregasapp.notificaciones.encolar_del_dia")
        sin_dia.start()
        self.addCleanup(sin_dia.stop)
        self.usuarios = equipo()
        self.intento = visita(self.usuarios)
        Paciente.objects.filter(pk=self.intento.entrega.paciente_id).update(correo_avisos="familia@example.invalid")
        self.hilo = Despachador()
        patron = patch.object(modulo, "despachador", self.hilo)
        patron.start()
        self.addCleanup(patron.stop)
        self.addCleanup(self.hilo.detener)

    def estado(self, tipo):
        return AvisoReparto.objects.filter(tipo=tipo).values_list("estado", flat=True).first()

    def test_el_clic_se_envia_sin_comando(self):
        self.assertTrue(self.hilo.iniciar())
        services.iniciar_traslado(self.usuarios["encargado"], self.intento.pk)
        self.assertTrue(esperar(lambda: self.estado(AvisoReparto.Tipo.EN_CAMINO) == Estado.SIMULADO))
        self.assertEqual([m.subject for m in mail.outbox], ["Reparto de prueba en camino"])

    def test_registro_entregado_se_envia_sin_comando(self):
        self.assertTrue(self.hilo.iniciar())
        services.registrar_entregada(self.usuarios["encargado"], self.intento.pk, uuid4())
        self.assertTrue(esperar(lambda: self.estado(AvisoReparto.Tipo.ENTREGADO) == Estado.SIMULADO))

    def test_pendiente_previo_sale_al_arrancar(self):
        services.iniciar_traslado(self.usuarios["encargado"], self.intento.pk)  # sin hilo: queda pendiente
        self.assertEqual(self.estado(AvisoReparto.Tipo.EN_CAMINO), Estado.PENDIENTE)
        self.assertTrue(self.hilo.iniciar())
        self.assertTrue(esperar(lambda: self.estado(AvisoReparto.Tipo.EN_CAMINO) == Estado.SIMULADO))

    def test_hilo_y_comando_a_la_vez_envian_una_sola_vez(self):
        services.iniciar_traslado(self.usuarios["encargado"], self.intento.pk)
        self.assertTrue(self.hilo.iniciar())
        call_command("procesar_avisos_reparto", "--simular", stdout=StringIO())
        self.assertTrue(esperar(lambda: self.estado(AvisoReparto.Tipo.EN_CAMINO) == Estado.SIMULADO))
        time.sleep(0.3)
        self.assertEqual(len(mail.outbox), 1)

    def test_el_hilo_sigue_vivo_tras_un_fallo(self):
        llamadas = []
        original = modulo.ciclo

        def ciclo_con_fallo(transporte):
            llamadas.append(1)
            if len(llamadas) == 1:
                with patch("entregasapp.notificaciones.procesar_avisos", side_effect=RuntimeError("falla")):
                    return original(transporte)
            return original(transporte)

        with patch.object(modulo, "ciclo", ciclo_con_fallo):
            self.assertTrue(self.hilo.iniciar())
            self.assertTrue(esperar(lambda: len(llamadas) >= 1))
            services.iniciar_traslado(self.usuarios["encargado"], self.intento.pk)
            self.assertTrue(esperar(lambda: self.estado(AvisoReparto.Tipo.EN_CAMINO) == Estado.SIMULADO))
        self.assertTrue(self.hilo.activo)
