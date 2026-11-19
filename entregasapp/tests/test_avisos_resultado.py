"""Avisos de reasignación y resultado de la visita (cuarta enmienda del spec 12, RF-12-19 a RF-12-23).

Los correos son sintéticos (`example.invalid`) y viven en el padrón. El aviso del día se anula para que las pruebas
no dependan de la hora.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from entregasapp import notificaciones, services
from entregasapp.models import AvisoReparto, IntentoEntrega
from recetasapp.models import Paciente
from .ayudas import equipo, hoy, visita


Estado = AvisoReparto.Estado
Tipo = AvisoReparto.Tipo


def simulado():
    return Mock(return_value=(Estado.SIMULADO, "simulado"))


class SinAvisoDelDia:
    def setUp(self):
        super().setUp()
        sin_dia = patch("entregasapp.notificaciones.encolar_del_dia")
        sin_dia.start()
        self.addCleanup(sin_dia.stop)


@override_settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=())
class AvisosResultadoTests(SinAvisoDelDia, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipo = equipo()
        cls.intento = visita(cls.equipo)
        cls.correo = "familia@example.invalid"
        Paciente.objects.filter(pk=cls.intento.entrega.paciente_id).update(correo_avisos=cls.correo)

    def reasignar(self, fecha, encargado="encargado2", operacion=None):
        ultimo = self.intento.entrega.intentos.order_by("-numero").first()
        return services.reasignar(
            self.equipo["qf"], self.intento.entrega_id, fecha=fecha, encargado_id=self.equipo[encargado].pk,
            intento_id=ultimo.pk, operacion_id=operacion or uuid4(),
        )

    def avisos(self, tipo):
        return AvisoReparto.objects.filter(tipo=tipo)

    # RF-12-19 ------------------------------------------------------------------------------------------------

    def test_reasignacion_a_otra_fecha_avisa_con_la_fecha(self):
        manana = hoy() + timedelta(days=1)
        nuevo = self.reasignar(manana)
        aviso = self.avisos(Tipo.REPROGRAMADO).get()
        self.assertEqual((aviso.intento_id, aviso.estado), (nuevo.pk, Estado.PENDIENTE))
        call_command("procesar_avisos_reparto", "--simular", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        mensaje = mail.outbox[0]
        self.assertEqual(mensaje.to, [self.correo])
        self.assertEqual(mensaje.subject, "Reparto de prueba reprogramado")
        self.assertEqual(mensaje.body, f"Tu reparto de prueba se reprogramó para el {manana:%d/%m}.")

    def test_reasignacion_el_mismo_dia_avisa_para_hoy(self):
        self.reasignar(hoy())
        enviar = simulado()
        notificaciones.procesar_avisos(enviar)
        enviar.assert_called_once_with(self.correo, Tipo.REPROGRAMADO, fecha=hoy())
        self.assertEqual(notificaciones.textos(Tipo.REPROGRAMADO, hoy())[1], "Tu reparto de prueba se reprogramó para hoy.")

    def test_repetir_la_reasignacion_no_crea_otro_aviso(self):
        operacion = uuid4()
        primero = self.reasignar(hoy(), operacion=operacion)
        segundo = services.reasignar(
            self.equipo["qf"], self.intento.entrega_id, fecha=hoy(), encargado_id=self.equipo["encargado2"].pk,
            intento_id=self.intento.pk, operacion_id=operacion,
        )
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(self.avisos(Tipo.REPROGRAMADO).count(), 1)

    # RF-12-20 y RF-12-21 -------------------------------------------------------------------------------------

    def test_entregada_avisa_una_vez(self):
        operacion = uuid4()
        services.registrar_entregada(self.equipo["encargado"], self.intento.pk, operacion)
        services.registrar_entregada(self.equipo["encargado"], self.intento.pk, operacion)
        self.assertEqual(self.avisos(Tipo.ENTREGADO).count(), 1)
        call_command("procesar_avisos_reparto", "--simular", stdout=StringIO())
        self.assertEqual([(m.to, m.subject, m.body) for m in mail.outbox], [
            ([self.correo], "Reparto de prueba entregado", "Tu reparto de prueba fue entregado."),
        ])

    def test_no_entregada_avisa_sin_motivo_ni_nota(self):
        services.registrar_no_entregada(
            self.equipo["encargado"], self.intento.pk, "sin_receptor", "Nota sintética reservada", uuid4(),
        )
        call_command("procesar_avisos_reparto", "--simular", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        mensaje = mail.outbox[0]
        self.assertEqual(mensaje.subject, "No pudimos entregar tu reparto de prueba")
        self.assertEqual(mensaje.body, "No pudimos entregar tu reparto de prueba. La farmacia coordinará una nueva visita.")
        self.assertNotIn("Nota sintética", mensaje.body)
        self.assertNotIn("receptor", mensaje.body)

    def test_no_entregada_y_luego_reasignada_envia_los_dos(self):
        services.registrar_no_entregada(self.equipo["encargado"], self.intento.pk, "sin_receptor", "", uuid4())
        self.intento.refresh_from_db()
        ultimo = self.intento
        services.reasignar(
            self.equipo["qf"], self.intento.entrega_id, fecha=hoy() + timedelta(days=2),
            encargado_id=self.equipo["encargado"].pk, intento_id=ultimo.pk, operacion_id=uuid4(),
            resultado_visto=IntentoEntrega.Resultado.NO_ENTREGADA,
        )
        enviar = simulado()
        notificaciones.procesar_avisos(enviar)
        self.assertCountEqual([llamada.args[1] for llamada in enviar.call_args_list], [Tipo.NO_ENTREGADO, Tipo.REPROGRAMADO])

    # RF-12-22 ------------------------------------------------------------------------------------------------

    def test_sin_correo_omite_y_guarda_el_registro(self):
        Paciente.objects.filter(pk=self.intento.entrega.paciente_id).update(correo_avisos="")
        services.registrar_entregada(self.equipo["encargado"], self.intento.pk, uuid4())
        aviso = self.avisos(Tipo.ENTREGADO).get()
        self.assertEqual((aviso.estado, aviso.codigo_resultado), (Estado.OMITIDO, "sin_destino"))
        self.intento.refresh_from_db()
        self.assertEqual(self.intento.resultado, IntentoEntrega.Resultado.ENTREGADA)

    def test_aviso_vence_a_las_dos_horas(self):
        services.registrar_entregada(self.equipo["encargado"], self.intento.pk, uuid4())
        aviso = self.avisos(Tipo.ENTREGADO).get()
        self.assertEqual(aviso.vence_en - aviso.creado_en, timedelta(hours=2))
        enviar = simulado()
        with patch("entregasapp.notificaciones.timezone.now", return_value=aviso.vence_en):
            notificaciones.procesar_avisos(enviar)
        enviar.assert_not_called()
        aviso.refresh_from_db()
        self.assertEqual((aviso.estado, aviso.codigo_resultado), (Estado.OBSOLETO, "aviso_vencido"))

    def test_reprogramado_ya_registrado_antes_de_enviar_queda_obsoleto(self):
        nuevo = self.reasignar(hoy(), encargado="encargado")
        services.registrar_entregada(self.equipo["encargado"], nuevo.pk, uuid4())
        enviar = simulado()
        notificaciones.procesar_avisos(enviar)
        enviar.assert_called_once_with(self.correo, Tipo.ENTREGADO)
        aviso = self.avisos(Tipo.REPROGRAMADO).get()
        self.assertEqual((aviso.estado, aviso.codigo_resultado), (Estado.OBSOLETO, "visita_cambiada"))

    def test_fallo_de_auditoria_revierte_el_registro_y_el_aviso(self):
        with patch("entregasapp.services.auditar", side_effect=RuntimeError("auditoría simulada")):
            with self.assertRaises(RuntimeError):
                services.registrar_entregada(self.equipo["encargado"], self.intento.pk, uuid4())
        self.assertFalse(AvisoReparto.objects.exists())
        self.intento.refresh_from_db()
        self.assertEqual(self.intento.resultado, IntentoEntrega.Resultado.PENDIENTE)

    def test_con_lista_de_dominios_se_respeta_el_freno(self):
        with self.settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=("prueba.cl",)):
            services.registrar_entregada(self.equipo["encargado"], self.intento.pk, uuid4())
        aviso = self.avisos(Tipo.ENTREGADO).get()
        self.assertEqual((aviso.estado, aviso.codigo_resultado), (Estado.OMITIDO, "dominio_no_permitido"))

    # RF-12-23 ------------------------------------------------------------------------------------------------

    def test_anular_no_genera_aviso(self):
        services.anular_entrega(self.equipo["qf"], self.intento.entrega_id, "retirara_farmacia")
        self.assertFalse(AvisoReparto.objects.exists())

    def test_el_mensaje_no_lleva_datos_del_paciente(self):
        self.reasignar(hoy() + timedelta(days=1))
        call_command("procesar_avisos_reparto", "--simular", stdout=StringIO())
        paciente = self.intento.entrega.paciente
        contenido = " ".join(f"{m.subject} {m.body}" for m in mail.outbox)
        for dato in (paciente.rut, paciente.nombres, paciente.apellidos, "Camino sintético", "Portón",
                     self.equipo["encargado2"].username):
            self.assertNotIn(dato, contenido)


@override_settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=())
class AvisosResultadoConcurrentesTests(SinAvisoDelDia, TransactionTestCase):
    """Un solo ganador entre operaciones simultáneas y solo su aviso."""

    def setUp(self):
        super().setUp()
        self.equipo = equipo()
        self.intento = visita(self.equipo)
        Paciente.objects.filter(pk=self.intento.entrega.paciente_id).update(correo_avisos="familia@example.invalid")

    def en_paralelo(self, *funciones):
        barrera = Barrier(len(funciones))

        def correr(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return funcion()
            except (ValidationError, Exception) as error:  # noqa: BLE001 - el perdedor puede fallar de varias formas
                return error
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(funciones)) as hilos:
            return [f.result(timeout=30) for f in [hilos.submit(correr, funcion) for funcion in funciones]]

    def reasignar(self):
        return services.reasignar(
            self.equipo["qf"], self.intento.entrega_id, fecha=hoy(), encargado_id=self.equipo["encargado2"].pk,
            intento_id=self.intento.pk, operacion_id=uuid4(), resultado_visto=IntentoEntrega.Resultado.PENDIENTE,
        )

    def test_registro_y_reasignacion_simultaneos(self):
        self.en_paralelo(
            lambda: services.registrar_entregada(self.equipo["encargado"], self.intento.pk, uuid4()),
            self.reasignar,
        )
        self.intento.refresh_from_db()
        tipos = list(AvisoReparto.objects.values_list("tipo", flat=True))
        if self.intento.resultado == IntentoEntrega.Resultado.ENTREGADA:
            self.assertEqual(tipos, [Tipo.ENTREGADO])
        else:
            self.assertEqual(self.intento.resultado, IntentoEntrega.Resultado.REASIGNADO)
            self.assertEqual(tipos, [Tipo.REPROGRAMADO])

    def test_dos_registros_simultaneos_con_la_misma_operacion(self):
        operacion = uuid4()
        self.en_paralelo(
            lambda: services.registrar_entregada(self.equipo["encargado"], self.intento.pk, operacion),
            lambda: services.registrar_entregada(self.equipo["encargado"], self.intento.pk, operacion),
        )
        self.assertEqual(AvisoReparto.objects.filter(tipo=Tipo.ENTREGADO).count(), 1)

    def test_dos_reasignaciones_simultaneas(self):
        self.en_paralelo(self.reasignar, self.reasignar)
        self.assertEqual(IntentoEntrega.objects.filter(entrega_id=self.intento.entrega_id).count(), 2)
        self.assertEqual(AvisoReparto.objects.filter(tipo=Tipo.REPROGRAMADO).count(), 1)
        enviar = simulado()
        notificaciones.procesar_avisos(enviar)
        notificaciones.procesar_avisos(enviar)
        enviar.assert_called_once()
