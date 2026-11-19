"""Aviso del día por correo (enmienda del 2026-11-18 del spec 12, RF-12-07 a RF-12-13).

El reloj se simula con `timezone.now`, siempre en la fecha de hoy (o mañana), porque las visitas se programan para
hoy. Los buzones son sintéticos (`example.invalid`) y, desde la segunda enmienda, son el correo para avisos del padrón.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core import mail
from django.core.management import call_command
from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone

from entregasapp import checks, notificaciones, services
from entregasapp.models import AvisoReparto, IntentoEntrega
from recetasapp.models import Paciente
from .ayudas import equipo, hoy, visita


Estado = AvisoReparto.Estado
DEL_DIA = AvisoReparto.Tipo.DEL_DIA
ASUNTO_DIA = "Hoy llega tu reparto de prueba"
CUERPO_DIA = "Tu reparto de prueba está programado para hoy. Te avisaremos cuando vaya en camino."


def a_las(horas, minutos=0, *, dias=0):
    return timezone.make_aware(datetime.combine(hoy() + timedelta(days=dias), time(horas, minutos)))


@contextmanager
def reloj(instante):
    with patch("entregasapp.notificaciones.timezone.now", return_value=instante):
        yield


def simulado():
    return Mock(return_value=(Estado.SIMULADO, "simulado"))


class ConBuzones:
    """Guarda los correos para avisos en el padrón y permite el dominio de prueba."""

    def preparar_buzones(self, buzones):
        opciones = self.settings(
            REPARTO_CORREO_DOMINIOS_PERMITIDOS=("example.invalid",),
            REPARTO_AVISO_DIA_HORA="08:00", REPARTO_AVISO_DIA_LIMITE="18:00",
        )
        opciones.enable()
        self.addCleanup(opciones.disable)
        # Los avisos de reasignación y resultado (cuarta enmienda) se prueban en test_avisos_resultado.
        sin_resultados = patch("entregasapp.notificaciones.encolar_resultado")
        sin_resultados.start()
        self.addCleanup(sin_resultados.stop)
        self.escribir_buzones(buzones)

    def escribir_buzones(self, buzones):
        for paciente_id, correo in buzones.items():
            Paciente.objects.filter(pk=paciente_id).update(correo_avisos=correo)


class AvisoDelDiaTests(ConBuzones, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipo = equipo()
        cls.primero = visita(cls.equipo)
        cls.segundo = visita(cls.equipo)
        cls.sin_buzon = visita(cls.equipo)

    def setUp(self):
        self.buzones = {
            self.primero.entrega.paciente_id: "primer-buzon@example.invalid",
            self.segundo.entrega.paciente_id: "segundo-buzon@example.invalid",
        }
        self.preparar_buzones(self.buzones)

    def del_dia(self, **filtros):
        return AvisoReparto.objects.filter(tipo=DEL_DIA, **filtros)

    def encolar(self, instante):
        with reloj(instante):
            return notificaciones.encolar_del_dia(instante)

    def procesar(self, instante, transporte):
        with reloj(instante):
            return notificaciones.procesar_avisos(transporte)

    # RF-12-07 ------------------------------------------------------------------------------------------------

    def test_franja_crea_un_aviso_por_paciente_con_buzon(self):
        self.assertEqual(self.encolar(a_las(7, 59)), 0)
        self.assertFalse(self.del_dia().exists())

        self.assertEqual(self.encolar(a_las(8, 0)), 2)
        self.assertEqual(self.encolar(a_las(17, 59)), 0)
        avisos = self.del_dia()
        self.assertCountEqual(
            avisos.values_list("entrega_id", flat=True), [self.primero.entrega_id, self.segundo.entrega_id],
        )
        for aviso in avisos:
            self.assertEqual(aviso.estado, Estado.PENDIENTE)
            self.assertEqual(aviso.fecha, hoy())
            self.assertEqual(aviso.vence_en, a_las(18, 0))
            self.assertNotIn("example.invalid", aviso.firma_destino)
        self.assertFalse(self.del_dia(entrega_id=self.sin_buzon.entrega_id).exists())

    def test_fuera_de_franja_no_crea_avisos(self):
        for instante in (a_las(0, 0), a_las(7, 59), a_las(18, 0), a_las(23, 59)):
            self.assertEqual(self.encolar(instante), 0)
        self.assertFalse(self.del_dia().exists())

    def test_franja_configurable(self):
        with self.settings(REPARTO_AVISO_DIA_HORA="06:30", REPARTO_AVISO_DIA_LIMITE="07:00"):
            self.assertEqual(self.encolar(a_las(6, 29)), 0)
            self.assertEqual(self.encolar(a_las(6, 30)), 2)
            self.assertEqual(self.del_dia().first().vence_en, a_las(7, 0))

    # RF-12-08, RF-12-11 y RF-12-12: envío con el texto del día -------------------------------------------------

    def test_simulacion_envia_el_texto_del_dia_a_cada_buzon(self):
        with reloj(a_las(10, 0)):  # el procesador se encendió tarde, dentro de la franja
            call_command("procesar_avisos_reparto", "--simular", stdout=StringIO())
        self.assertCountEqual([m.to for m in mail.outbox], [[correo] for correo in self.buzones.values()])
        for mensaje in mail.outbox:
            self.assertEqual(mensaje.subject, ASUNTO_DIA)
            self.assertEqual(mensaje.body, CUERPO_DIA)
            self.assertFalse(mensaje.cc)
            self.assertFalse(mensaje.bcc)
        self.assertEqual(self.del_dia(estado=Estado.SIMULADO).count(), 2)

    def test_programada_durante_el_dia_recibe_su_aviso(self):
        enviar = simulado()
        self.procesar(a_las(8, 0), enviar)
        self.assertEqual(enviar.call_count, 2)
        with reloj(a_las(11, 0)):
            tarde = visita(self.equipo)
        self.buzones[tarde.entrega.paciente_id] = "tercer-buzon@example.invalid"
        self.escribir_buzones(self.buzones)
        self.procesar(a_las(11, 0), enviar)
        self.assertEqual(enviar.call_count, 3)
        enviar.assert_called_with("tercer-buzon@example.invalid", DEL_DIA)
        self.assertEqual(self.del_dia(entrega_id=tarde.entrega_id).get().estado, Estado.SIMULADO)

    def test_buzon_asignado_a_mediodia_recibe_su_aviso(self):
        self.procesar(a_las(9, 0), simulado())
        self.buzones[self.sin_buzon.entrega.paciente_id] = "tardio@example.invalid"
        self.escribir_buzones(self.buzones)
        enviar = simulado()
        self.procesar(a_las(12, 0), enviar)
        enviar.assert_called_once_with("tardio@example.invalid", DEL_DIA)

    def test_doble_ejecucion_no_repite_envios(self):
        enviar = simulado()
        for instante in (a_las(8, 0), a_las(8, 0), a_las(12, 0), a_las(17, 59)):
            self.procesar(instante, enviar)
        self.assertEqual(enviar.call_count, 2)
        self.assertEqual(self.del_dia().count(), 2)

    # RF-12-09: uno por entrega y día ---------------------------------------------------------------------------

    def test_reasignada_el_mismo_dia_no_genera_otro_aviso_y_se_envia_igual(self):
        self.encolar(a_las(8, 0))
        with reloj(a_las(9, 0)):
            services.reasignar(
                self.equipo["qf"], self.primero.entrega_id, fecha=hoy(),
                encargado_id=self.equipo["encargado2"].pk, intento_id=self.primero.pk, operacion_id=uuid4(),
            )
        enviar = simulado()
        self.procesar(a_las(9, 0), enviar)
        self.procesar(a_las(9, 30), enviar)
        self.assertEqual(self.del_dia(entrega_id=self.primero.entrega_id).count(), 1)
        self.assertEqual(self.del_dia(entrega_id=self.primero.entrega_id).get().estado, Estado.SIMULADO)
        self.assertEqual(enviar.call_count, 2)

    def test_reasignada_a_manana_recibe_el_aviso_ese_dia(self):
        self.encolar(a_las(8, 0))
        with reloj(a_las(9, 0)):
            services.reasignar(
                self.equipo["qf"], self.primero.entrega_id, fecha=hoy() + timedelta(days=1),
                encargado_id=self.equipo["encargado2"].pk, intento_id=self.primero.pk, operacion_id=uuid4(),
            )
        enviar = simulado()
        self.procesar(a_las(9, 0), enviar)
        enviar.assert_called_once_with(self.buzones[self.segundo.entrega.paciente_id], DEL_DIA)
        hoy_primero = self.del_dia(entrega_id=self.primero.entrega_id, fecha=hoy()).get()
        self.assertEqual(hoy_primero.estado, Estado.OBSOLETO)
        self.assertEqual(hoy_primero.codigo_resultado, "visita_cambiada")

        manana = simulado()
        self.procesar(a_las(8, 0, dias=1), manana)
        manana.assert_called_once_with(self.buzones[self.primero.entrega.paciente_id], DEL_DIA)
        self.assertEqual(self.del_dia(entrega_id=self.primero.entrega_id).count(), 2)

    # RF-12-10: sin atrasadas -----------------------------------------------------------------------------------

    def test_visita_atrasada_no_recibe_aviso_del_dia(self):
        IntentoEntrega.objects.filter(pk=self.primero.pk).update(fecha_programada=hoy() - timedelta(days=1))
        enviar = simulado()
        self.procesar(a_las(9, 0), enviar)
        enviar.assert_called_once_with(self.buzones[self.segundo.entrega.paciente_id], DEL_DIA)
        self.assertFalse(self.del_dia(entrega_id=self.primero.entrega_id).exists())

    # RF-12-11: vigencia ----------------------------------------------------------------------------------------

    def test_aviso_pendiente_caduca_a_la_hora_limite(self):
        self.encolar(a_las(17, 0))
        enviar = simulado()
        self.procesar(a_las(18, 0), enviar)
        enviar.assert_not_called()
        self.assertEqual(self.del_dia(estado=Estado.OBSOLETO, codigo_resultado="aviso_vencido").count(), 2)

    def test_entrega_registrada_o_anulada_antes_de_preparar_queda_obsoleta(self):
        self.encolar(a_las(8, 0))
        with reloj(a_las(9, 0)):
            services.registrar_entregada(self.equipo["encargado"], self.primero.pk, uuid4())
            services.anular_entrega(self.equipo["qf"], self.segundo.entrega_id, "retirara_farmacia")
        enviar = simulado()
        self.procesar(a_las(9, 0), enviar)
        enviar.assert_not_called()
        self.assertEqual(self.del_dia(estado=Estado.OBSOLETO, codigo_resultado="visita_cambiada").count(), 2)

    def test_no_entregada_antes_de_preparar_queda_obsoleta(self):
        self.encolar(a_las(8, 0))
        with reloj(a_las(9, 0)):
            services.registrar_no_entregada(self.equipo["encargado"], self.primero.pk, "sin_receptor", "", uuid4())
        enviar = simulado()
        self.procesar(a_las(9, 0), enviar)
        enviar.assert_called_once_with(self.buzones[self.segundo.entrega.paciente_id], DEL_DIA)
        self.assertEqual(self.del_dia(entrega_id=self.primero.entrega_id).get().estado, Estado.OBSOLETO)

    # RF-12-12: destino ----------------------------------------------------------------------------------------

    def test_buzon_cambiado_antes_del_envio_queda_omitido(self):
        self.encolar(a_las(8, 0))
        self.buzones[self.primero.entrega.paciente_id] = "otro@example.invalid"
        self.escribir_buzones(self.buzones)
        enviar = simulado()
        self.procesar(a_las(8, 1), enviar)
        enviar.assert_called_once_with(self.buzones[self.segundo.entrega.paciente_id], DEL_DIA)
        aviso = self.del_dia(entrega_id=self.primero.entrega_id).get()
        self.assertEqual((aviso.estado, aviso.codigo_resultado), (Estado.OMITIDO, "destino_cambiado"))

    def test_los_dos_avisos_conviven_con_su_propio_texto(self):
        with reloj(a_las(8, 0)):
            call_command("procesar_avisos_reparto", "--simular", stdout=StringIO())
            services.iniciar_traslado(self.equipo["encargado"], self.primero.pk)
            call_command("procesar_avisos_reparto", "--simular", stdout=StringIO())
        al_primero = [m for m in mail.outbox if m.to == [self.buzones[self.primero.entrega.paciente_id]]]
        self.assertEqual([m.subject for m in al_primero], [ASUNTO_DIA, "Reparto de prueba en camino"])
        self.assertEqual(len(mail.outbox), 3)

    def test_el_aviso_del_dia_no_lleva_datos_del_paciente(self):
        self.procesar(a_las(9, 0), notificaciones.enviar_simulado)
        paciente = self.primero.entrega.paciente
        for mensaje in mail.outbox:
            contenido = f"{mensaje.subject} {mensaje.body}"
            for dato in (paciente.rut, paciente.nombres, paciente.apellidos, "Camino sintético", "Portón"):
                self.assertNotIn(dato, contenido)


class ConfiguracionAvisoDelDiaTests(SimpleTestCase):
    def errores(self, hora, limite):
        with self.settings(REPARTO_AVISO_DIA_HORA=hora, REPARTO_AVISO_DIA_LIMITE=limite):
            return [error.id for error in checks.revisar_aviso_dia()]

    def test_valores_validos(self):
        self.assertEqual(self.errores("08:00", "18:00"), [])
        self.assertEqual(self.errores("00:00", "23:59"), [])

    def test_formato_invalido(self):
        for hora, limite in (("8", "18:00"), ("25:00", "18:00"), ("08:00", "18:60"), ("08:00", ""), ("8:00", "18:00")):
            self.assertEqual(self.errores(hora, limite), ["entregasapp.E006"], (hora, limite))

    def test_hora_del_aviso_no_anterior_a_la_limite(self):
        self.assertEqual(self.errores("18:00", "08:00"), ["entregasapp.E007"])
        self.assertEqual(self.errores("08:00", "08:00"), ["entregasapp.E007"])

    def test_vacias_usan_los_valores_por_omision(self):
        from django.conf import settings

        self.assertIsNotNone(checks.leer_hora(settings.REPARTO_AVISO_DIA_HORA))
        self.assertIsNotNone(checks.leer_hora(settings.REPARTO_AVISO_DIA_LIMITE))


class AvisoDelDiaConcurrenteTests(ConBuzones, TransactionTestCase):
    """RF-12-09 con hilos: tres escenarios de carga sin avisos ni envíos duplicados."""

    def setUp(self):
        self.equipo = equipo()
        self.intentos = [visita(self.equipo) for _ in range(4)]
        self.buzones = {
            intento.entrega.paciente_id: f"buzon-{numero}@example.invalid"
            for numero, intento in enumerate(self.intentos, start=1)
        }
        self.preparar_buzones(self.buzones)

    def en_paralelo(self, *funciones):
        barrera = Barrier(len(funciones))

        def correr(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return funcion()
            finally:
                connections.close_all()

        with reloj(a_las(9, 0)), ThreadPoolExecutor(max_workers=len(funciones)) as hilos:
            futuros = [hilos.submit(correr, funcion) for funcion in funciones]
            return [futuro.result(timeout=30) for futuro in futuros]

    def test_dos_procesadores_encolan_a_la_vez(self):
        def encolar():
            return notificaciones.encolar_del_dia(a_las(9, 0))

        creados = self.en_paralelo(encolar, encolar)
        self.assertEqual(sum(creados), 4)
        self.assertEqual(AvisoReparto.objects.filter(tipo=DEL_DIA).count(), 4)

    def test_dos_procesadores_procesan_el_mismo_lote(self):
        enviar = simulado()
        self.en_paralelo(lambda: notificaciones.procesar_avisos(enviar), lambda: notificaciones.procesar_avisos(enviar))
        self.assertEqual(enviar.call_count, 4)
        self.assertCountEqual([llamada.args[0] for llamada in enviar.call_args_list], self.buzones.values())
        self.assertEqual(AvisoReparto.objects.filter(tipo=DEL_DIA, estado=Estado.SIMULADO).count(), 4)

    def test_encolar_mientras_se_reasigna_el_mismo_dia(self):
        primero = self.intentos[0]

        def reasignar():
            return services.reasignar(
                self.equipo["qf"], primero.entrega_id, fecha=hoy(),
                encargado_id=self.equipo["encargado2"].pk, intento_id=primero.pk, operacion_id=uuid4(),
            )

        def encolar():
            return notificaciones.encolar_del_dia(a_las(9, 0))

        self.en_paralelo(reasignar, encolar, encolar)
        self.assertEqual(AvisoReparto.objects.filter(tipo=DEL_DIA, entrega_id=primero.entrega_id).count(), 1)
        enviar = simulado()
        with reloj(a_las(9, 1)):
            notificaciones.procesar_avisos(enviar)
            notificaciones.procesar_avisos(enviar)
        self.assertEqual(enviar.call_count, 4)
        self.assertEqual(AvisoReparto.objects.filter(tipo=DEL_DIA, estado=Estado.SIMULADO).count(), 4)


class MigracionAvisoDelDiaTests(TransactionTestCase):
    def test_migrar_desde_0004_y_volver(self):
        anterior = [("entregasapp", "0004_avisoreparto_traslado")]
        executor = MigrationExecutor(connection)
        actual = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(anterior)
            columnas = [c.name for c in connection.introspection.get_table_description(
                connection.cursor(), AvisoReparto._meta.db_table,
            )]
            self.assertNotIn("fecha", columnas)
            MigrationExecutor(connection).migrate(actual)
            columnas = [c.name for c in connection.introspection.get_table_description(
                connection.cursor(), AvisoReparto._meta.db_table,
            )]
            self.assertIn("fecha", columnas)
            self.assertIn("entrega_id", columnas)
        finally:
            MigrationExecutor(connection).migrate(actual)
