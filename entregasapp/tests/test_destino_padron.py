"""Destino desde el padrón y freno por dominios (segunda enmienda del spec 12, RF-12-14 a RF-12-18)."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock, patch

from django.db import close_old_connections, connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from entregasapp import checks, notificaciones, services
from entregasapp.models import AvisoReparto
from recetasapp.models import Paciente
from recetasapp.services import actualizar_correo_avisos
from .ayudas import equipo, visita


Estado = AvisoReparto.Estado


class DominiosTests(SimpleTestCase):
    def errores(self, dominios):
        with self.settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=dominios):
            return [error.id for error in checks.revisar_dominios_correo()]

    def test_dominios_validos(self):
        self.assertEqual(self.errores(()), [])
        self.assertEqual(self.errores(("example.invalid", "prueba.cl")), [])

    def test_dominios_invalidos(self):
        for dominios in (("no es dominio",), ("sinpunto",), ("-malo.cl",), ("a..b.cl",)):
            self.assertEqual(self.errores(dominios), ["entregasapp.E008"], dominios)

    def test_destino(self):
        with self.settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=("example.invalid",)):
            self.assertEqual(notificaciones.destino(" a@EXAMPLE.invalid "), ("a@EXAMPLE.invalid", ""))
            self.assertEqual(notificaciones.destino(""), (None, "sin_destino"))
            self.assertEqual(notificaciones.destino("a@sub.example.invalid"), (None, "dominio_no_permitido"))
            self.assertEqual(notificaciones.destino("a@correo.cl"), (None, "dominio_no_permitido"))
        with self.settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=()):
            # Tercera enmienda: sin lista, cualquier correo.
            self.assertEqual(notificaciones.destino("a@correo.cl"), ("a@correo.cl", ""))
            self.assertEqual(notificaciones.destino(""), (None, "sin_destino"))


@override_settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=("example.invalid",))
class DestinoPadronTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipo = equipo()
        cls.intento = visita(cls.equipo)
        Paciente.objects.filter(pk=cls.intento.entrega.paciente_id).update(correo_avisos="padron@example.invalid")

    @patch("entregasapp.notificaciones.encolar_del_dia")
    def test_el_aviso_en_camino_sale_al_correo_del_padron(self, _sin_aviso_del_dia):
        with self.settings(REPARTO_BUZONES_PRUEBA_ARCHIVO="C:/no/existe/buzones.json"):  # ya no se lee
            services.iniciar_traslado(self.equipo["encargado"], self.intento.pk)
            enviar = Mock(return_value=(Estado.SIMULADO, "simulado"))
            notificaciones.procesar_avisos(enviar)
        enviar.assert_called_once_with("padron@example.invalid", AvisoReparto.Tipo.EN_CAMINO)

    @patch("entregasapp.notificaciones.encolar_del_dia")
    def test_correo_cambiado_en_la_ficha_antes_del_envio_queda_omitido(self, _sin_aviso_del_dia):
        services.iniciar_traslado(self.equipo["encargado"], self.intento.pk)
        actualizar_correo_avisos(
            self.equipo["qf"], self.intento.entrega.paciente_id, "nuevo@example.invalid", "padron@example.invalid",
        )
        enviar = Mock()
        notificaciones.procesar_avisos(enviar)
        enviar.assert_not_called()
        aviso = AvisoReparto.objects.get(intento=self.intento)
        self.assertEqual((aviso.estado, aviso.codigo_resultado), (Estado.OMITIDO, "destino_cambiado"))


@override_settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=("example.invalid",))
class DestinoConcurrenteTests(TransactionTestCase):
    """RF-12-17: el cambio de correo simultáneo con la preparación nunca envía a un tercero."""

    @patch("entregasapp.notificaciones.encolar_del_dia")
    def test_cambio_de_correo_mientras_se_prepara(self, _sin_aviso_del_dia):
        usuarios = equipo()
        firmados = []
        for _ in range(3):
            intento = visita(usuarios)
            Paciente.objects.filter(pk=intento.entrega.paciente_id).update(correo_avisos=f"p{intento.pk}@example.invalid")
            services.iniciar_traslado(usuarios["encargado"], intento.pk)
            firmados.append((intento, f"p{intento.pk}@example.invalid"))
        barrera = Barrier(2)
        enviar = Mock(return_value=(Estado.SIMULADO, "simulado"))

        def procesar():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return notificaciones.procesar_avisos(enviar)
            finally:
                connections.close_all()

        def cambiar():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                for intento, correo in firmados:
                    actualizar_correo_avisos(usuarios["qf"], intento.entrega.paciente_id, "tercero@example.invalid", correo)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as hilos:
            futuros = [hilos.submit(procesar), hilos.submit(cambiar)]
            for futuro in futuros:
                futuro.result(timeout=30)

        enviados = [llamada.args[0] for llamada in enviar.call_args_list]
        self.assertNotIn("tercero@example.invalid", enviados)
        for intento, correo in firmados:
            aviso = AvisoReparto.objects.get(intento=intento)
            if aviso.estado == Estado.SIMULADO:
                self.assertIn(correo, enviados)
            else:
                self.assertEqual((aviso.estado, aviso.codigo_resultado), (Estado.OMITIDO, "destino_cambiado"))
