"""Transporte simulado, vigencia y recuperación de la bandeja (spec 12)."""

import smtplib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core import mail
from django.core.management import call_command
from django.db import close_old_connections, connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone

from entregasapp import notificaciones, services
from entregasapp.models import AvisoReparto
from recetasapp.models import Paciente
from .ayudas import equipo, hoy, visita


Estado = AvisoReparto.Estado
EN_CAMINO = AvisoReparto.Tipo.EN_CAMINO


class BandejaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipo = equipo()
        cls.primero = visita(cls.equipo)
        cls.segundo = visita(cls.equipo)

    def setUp(self):
        # Estas pruebas son del aviso «en camino»; el aviso del día depende de la hora y se prueba aparte.
        sin_aviso_del_dia = patch("entregasapp.notificaciones.encolar_del_dia")
        sin_aviso_del_dia.start()
        self.addCleanup(sin_aviso_del_dia.stop)
        # Los avisos de reasignación y resultado (cuarta enmienda) se prueban en test_avisos_resultado.
        sin_resultados = patch("entregasapp.notificaciones.encolar_resultado")
        sin_resultados.start()
        self.addCleanup(sin_resultados.stop)
        opciones = self.settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=("example.invalid",))
        opciones.enable()
        self.addCleanup(opciones.disable)
        self.buzones = {
            self.primero.entrega.paciente_id: "primer-buzon@example.invalid",
            self.segundo.entrega.paciente_id: "segundo-buzon@example.invalid",
        }
        self.escribir_buzones(self.buzones)

    def escribir_buzones(self, buzones):
        # Segunda enmienda: el destino es el correo para avisos del padrón.
        for paciente_id, correo in buzones.items():
            Paciente.objects.filter(pk=paciente_id).update(correo_avisos=correo)

    def iniciar(self, intento):
        services.iniciar_traslado(self.equipo["encargado"], intento.pk)
        return AvisoReparto.objects.get(intento=intento)

    def test_simulacion_entrega_individual_sin_datos_del_paciente(self):
        avisos = [self.iniciar(intento) for intento in (self.primero, self.segundo)]
        call_command("procesar_avisos_reparto", "--simular", stdout=StringIO())
        self.assertCountEqual([mensaje.to for mensaje in mail.outbox], [[correo] for correo in self.buzones.values()])
        for mensaje in mail.outbox:
            self.assertEqual(mensaje.subject, "Reparto de prueba en camino")
            self.assertEqual(mensaje.body, "Tu reparto de prueba está en camino")
            self.assertFalse(mensaje.cc)
            self.assertFalse(mensaje.bcc)
        for aviso in avisos:
            aviso.refresh_from_db()
            self.assertEqual(aviso.estado, Estado.SIMULADO)
            self.assertNotIn("example.invalid", aviso.firma_destino)
            self.assertIsNone(aviso.aceptado_en)

    def test_sin_lista_de_dominios_se_envia_a_cualquier_correo(self):
        # Tercera enmienda: la lista vacía no restringe; --smtp funciona sin ella.
        self.escribir_buzones({self.primero.entrega.paciente_id: "cualquiera@correo.cl"})
        with self.settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=()):
            aviso = self.iniciar(self.primero)
            self.assertEqual(aviso.estado, Estado.PENDIENTE)
            with patch("entregasapp.notificaciones.enviar_smtp", return_value=(Estado.ACEPTADO_SMTP, "smtp_aceptado")) as smtp:
                call_command("procesar_avisos_reparto", "--smtp", stdout=StringIO())
            smtp.assert_called_once_with("cualquiera@correo.cl", EN_CAMINO)
        aviso.refresh_from_db()
        self.assertEqual(aviso.estado, Estado.ACEPTADO_SMTP)

    def test_dominio_no_permitido_o_sin_correo_omite_el_aviso(self):
        self.escribir_buzones({self.primero.entrega.paciente_id: "real@correo.cl", self.segundo.entrega.paciente_id: ""})
        primero, segundo = self.iniciar(self.primero), self.iniciar(self.segundo)
        self.assertEqual((primero.estado, primero.codigo_resultado), (Estado.OMITIDO, "dominio_no_permitido"))
        self.assertEqual((segundo.estado, segundo.codigo_resultado), (Estado.OMITIDO, "sin_destino"))

    def test_dominio_en_mayusculas_se_acepta_y_subdominio_no(self):
        self.escribir_buzones({
            self.primero.entrega.paciente_id: "Mayus@EXAMPLE.INVALID",
            self.segundo.entrega.paciente_id: "sub@otro.example.invalid",
        })
        self.assertEqual(self.iniciar(self.primero).estado, Estado.PENDIENTE)
        self.assertEqual(self.iniciar(self.segundo).codigo_resultado, "dominio_no_permitido")

    def test_dos_pacientes_con_el_mismo_correo_reciben_un_aviso_cada_uno(self):
        compartido = "cuidadora@example.invalid"
        self.escribir_buzones(dict.fromkeys(self.buzones, compartido))
        for intento in (self.primero, self.segundo):
            self.iniciar(intento)
        enviar = Mock(return_value=(Estado.SIMULADO, "simulado"))
        notificaciones.procesar_avisos(enviar)
        self.assertEqual(enviar.call_count, 2)
        self.assertEqual({llamada.args[0] for llamada in enviar.call_args_list}, {compartido})

    def test_borrar_correo_o_retirar_el_dominio_antes_del_envio_omite(self):
        primero, segundo = self.iniciar(self.primero), self.iniciar(self.segundo)
        self.escribir_buzones({self.primero.entrega.paciente_id: ""})
        enviar = Mock()
        with self.settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=("prueba.cl",)):
            notificaciones.procesar_avisos(enviar)
        enviar.assert_not_called()
        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual((primero.estado, primero.codigo_resultado), (Estado.OMITIDO, "destino_cambiado"))
        self.assertEqual((segundo.estado, segundo.codigo_resultado), (Estado.OMITIDO, "dominio_no_permitido"))

    def test_cambiar_destino_omite_el_aviso_original(self):
        aviso = self.iniciar(self.primero)
        self.buzones[self.primero.entrega.paciente_id] = "otro@example.invalid"
        self.escribir_buzones(self.buzones)
        enviar = Mock()
        notificaciones.procesar_avisos(enviar)
        enviar.assert_not_called()
        aviso.refresh_from_db()
        self.assertEqual(aviso.estado, Estado.OMITIDO)

    def test_aviso_caduca_a_los_treinta_minutos(self):
        vigencia = [self.iniciar(intento) for intento in (self.primero, self.segundo)]
        cuenta = Mock(return_value=(Estado.SIMULADO, "simulado"))
        antes = vigencia[0].vence_en - timedelta(seconds=1)
        AvisoReparto.objects.filter(pk=vigencia[1].pk).update(vence_en=antes)
        with patch("entregasapp.notificaciones.timezone.now", return_value=antes):
            notificaciones.procesar_avisos(cuenta)
        cuenta.assert_called_once_with(self.buzones[self.primero.entrega.paciente_id], EN_CAMINO)
        vigencia[1].refresh_from_db()
        self.assertEqual(vigencia[1].estado, Estado.OBSOLETO)

    def test_reasignar_y_registrar_resultado_invalidan_avisos(self):
        anterior = self.iniciar(self.primero)
        entregado = self.iniciar(self.segundo)
        nuevo = services.reasignar(
            self.equipo["qf"], self.primero.entrega_id, fecha=hoy(),
            encargado_id=self.equipo["encargado2"].pk, intento_id=self.primero.pk, operacion_id=uuid4(),
        )
        services.registrar_entregada(self.equipo["encargado"], self.segundo.pk, uuid4())
        services.iniciar_traslado(self.equipo["encargado2"], nuevo.pk)
        enviar = Mock(return_value=(Estado.SIMULADO, "simulado"))
        notificaciones.procesar_avisos(enviar)
        enviar.assert_called_once_with(self.buzones[nuevo.entrega.paciente_id], EN_CAMINO)
        for aviso in (anterior, entregado):
            aviso.refresh_from_db()
            self.assertEqual(aviso.estado, Estado.OBSOLETO)

    def test_no_entrega_y_anulacion_invalidan_avisos(self):
        avisos = [self.iniciar(intento) for intento in (self.primero, self.segundo)]
        services.registrar_no_entregada(self.equipo["encargado"], self.primero.pk, "sin_receptor", "", uuid4())
        services.anular_entrega(self.equipo["qf"], self.segundo.entrega_id, "retirara_farmacia")
        enviar = Mock()
        notificaciones.procesar_avisos(enviar)
        enviar.assert_not_called()
        self.assertEqual(AvisoReparto.objects.filter(pk__in=[aviso.pk for aviso in avisos], estado=Estado.OBSOLETO).count(), 2)

    def test_reserva_vencida_previa_se_recupera_pero_envio_incierto_no_se_reenvia(self):
        reserva_previa = self.iniciar(self.primero)
        envio = self.iniciar(self.segundo)
        ahora = timezone.now()
        AvisoReparto.objects.filter(pk=reserva_previa.pk).update(
            estado=Estado.RESERVADO, reserva=uuid4(), reserva_hasta=ahora,
        )
        token_envio = uuid4()
        AvisoReparto.objects.filter(pk=envio.pk).update(
            estado=Estado.EN_ENVIO, reserva=token_envio, reserva_hasta=ahora, intentos_envio=1,
        )
        enviar = Mock(return_value=(Estado.SIMULADO, "simulado"))
        notificaciones.procesar_avisos(enviar)
        enviar.assert_called_once_with(self.buzones[self.primero.entrega.paciente_id], EN_CAMINO)
        envio.refresh_from_db()
        self.assertEqual(envio.estado, Estado.INCIERTO)
        notificaciones._registrar(envio.pk, token_envio, Estado.ACEPTADO_SMTP, "smtp_aceptado")
        envio.refresh_from_db()
        self.assertEqual(envio.estado, Estado.ACEPTADO_SMTP)
        self.assertIsNotNone(envio.aceptado_en)

    def test_rechazo_temporal_reintenta_tres_veces_como_maximo(self):
        aviso = self.iniciar(self.primero)
        enviar = Mock(return_value=(notificaciones.REINTENTAR, "smtp_450"))
        for segundos in (0, 60, 180, 181):
            instante = aviso.creado_en + timedelta(seconds=segundos)
            with patch("entregasapp.notificaciones.timezone.now", return_value=instante):
                notificaciones.procesar_avisos(enviar)
        aviso.refresh_from_db()
        self.assertEqual(enviar.call_count, 3)
        self.assertEqual(aviso.intentos_envio, 3)
        self.assertEqual(aviso.estado, Estado.FALLIDO)

    def test_respuesta_perdida_mantiene_resultado_incierto(self):
        aviso = self.iniciar(self.primero)
        enviar = Mock(return_value=(Estado.INCIERTO, "smtp_respuesta_perdida"))
        for _ in range(2):
            notificaciones.procesar_avisos(enviar)
        enviar.assert_called_once()
        aviso.refresh_from_db()
        self.assertEqual(aviso.estado, Estado.INCIERTO)


class ProcesadoresConcurrentesTests(TransactionTestCase):
    @patch("entregasapp.notificaciones.encolar_del_dia")
    def test_dos_procesadores_solo_envian_una_vez(self, _sin_aviso_del_dia):
        usuarios = equipo()
        intento = visita(usuarios)
        buzon = "autorizado@example.invalid"
        barrera = Barrier(2)
        enviar = Mock(return_value=(Estado.SIMULADO, "simulado"))

        def procesar():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return notificaciones.procesar_avisos(enviar)
            finally:
                connections.close_all()

        Paciente.objects.filter(pk=intento.entrega.paciente_id).update(correo_avisos=buzon)
        with self.settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=("example.invalid",)):
            services.iniciar_traslado(usuarios["encargado"], intento.pk)
            with ThreadPoolExecutor(max_workers=2) as hilos:
                procesos = [hilos.submit(procesar) for _ in range(2)]
                self.assertEqual(sum(p.result(timeout=15) for p in procesos), 1)

        enviar.assert_called_once_with(buzon, EN_CAMINO)
        self.assertEqual(AvisoReparto.objects.get(intento=intento).estado, Estado.SIMULADO)


class SMTPTests(SimpleTestCase):
    @patch("entregasapp.notificaciones.get_connection")
    def test_aceptar_y_luego_perder_la_conexion_no_duplica_el_envio(self, crear):
        smtp = crear.return_value
        smtp.send_messages.return_value = 1
        smtp.close.side_effect = smtplib.SMTPServerDisconnected()
        resultado = notificaciones.enviar_smtp("autorizado@example.invalid")
        self.assertEqual(resultado, (Estado.ACEPTADO_SMTP, "smtp_aceptado"))
        self.assertEqual(smtp.send_messages.call_args.args[0][0].to, ["autorizado@example.invalid"])

    @patch("entregasapp.notificaciones.get_connection")
    def test_solo_se_reintenta_un_fallo_sin_aceptacion_posible(self, crear):
        smtp = crear.return_value
        smtp.open.side_effect = TimeoutError
        self.assertEqual(notificaciones.enviar_smtp("autorizado@example.invalid")[0], notificaciones.REINTENTAR)
        smtp.send_messages.assert_not_called()

        smtp.open.side_effect = None
        smtp.send_messages.side_effect = smtplib.SMTPDataError(451, b"respuesta simulada")
        self.assertEqual(notificaciones.enviar_smtp("autorizado@example.invalid"), (notificaciones.REINTENTAR, "smtp_451"))
        smtp.send_messages.side_effect = smtplib.SMTPDataError(550, b"respuesta simulada")
        self.assertEqual(notificaciones.enviar_smtp("autorizado@example.invalid"), (Estado.FALLIDO, "smtp_550"))
        smtp.send_messages.side_effect = TimeoutError
        self.assertEqual(
            notificaciones.enviar_smtp("autorizado@example.invalid"), (Estado.INCIERTO, "smtp_respuesta_perdida"),
        )
