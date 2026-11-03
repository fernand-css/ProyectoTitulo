"""Selección ponderada, compatibilidad y recuperación transaccional."""
import io
from datetime import timedelta
from unittest.mock import patch
from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from recetasapp.models import Receta
from turnosapp.cola import espera_turno, procesar_pendiente, procesar_seguro
from turnosapp.models import ConfiguracionCola, EstadoColaDiaria, EventoTurno, PendienteSeleccion, Turno, Ventanilla
from turnosapp.services import emitir_turno
from .datos_cola import DatosCola


class ColaTests(DatosCola, TestCase):
    def test_ciclo_compartido_p_p_c_g_con_orden_de_llegada(self):
        self.activar()
        for tipo in ["preferencial"] * 4 + ["cronicos"] * 2 + ["general"] * 2:
            self.turno(tipo)
        tipos, numeros = [], []
        for _ in range(8):
            self.assertEqual(procesar_pendiente(self.pendiente().pk), 1)
            actual = Turno.objects.get(estado="llamado")
            tipos.append(actual.tipo_atencion)
            numeros.append(actual.numero)
            self.cerrar_fixture()
        self.assertEqual(tipos, ["preferencial", "preferencial", "cronicos", "general"] * 2)
        self.assertEqual(numeros, [1, 2, 5, 7, 3, 4, 6, 8])

    def test_salta_vacios_y_no_gasta_cursor_sin_candidato(self):
        self.activar()
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(EstadoColaDiaria.objects.get().cursor, 0)
        general = self.turno()
        procesar_pendiente(self.pendiente().pk)
        general.refresh_from_db()
        self.assertEqual(general.estado, "llamado")
        self.assertEqual(EstadoColaDiaria.objects.get().cursor, 0)

    def test_abrir_otra_ventanilla_no_reinicia_ciclo(self):
        self.activar()
        for tipo in ["preferencial"] * 4 + ["cronicos", "general"]:
            self.turno(tipo)
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(EstadoColaDiaria.objects.get().cursor, 1)
        self.activar(2)
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(EstadoColaDiaria.objects.get().cursor, 2)
        self.cerrar_fixture()
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(set(Turno.objects.filter(estado="llamado").values_list("tipo_atencion", flat=True)), {"cronicos", "general"})

    def test_compatibilidad_y_cursor_compartido_entre_ventanillas(self):
        v1 = self.activar(1, ["preferencial"])
        v2 = self.activar(2, ["general"])
        self.turno("cronicos", espera=1000)
        preferente = self.turno("preferencial")
        general = self.turno("general")
        self.assertEqual(procesar_pendiente(self.pendiente().pk), 2)
        preferente.refresh_from_db()
        general.refresh_from_db()
        self.assertEqual(preferente.ventanilla_id, v1.pk)
        self.assertEqual(general.ventanilla_id, v2.pk)
        self.assertEqual(Turno.objects.filter(estado="esperando").get().tipo_atencion, "cronicos")

    def test_rescate_a_15_minutos_respeta_antiguedad_y_no_avanza_cursor(self):
        self.activar()
        self.turno("preferencial")
        viejo = self.turno("general", espera=901)
        self.turno("cronicos", espera=900)
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(Turno.objects.get(estado="llamado").pk, viejo.pk)
        self.assertEqual(EstadoColaDiaria.objects.get().cursor, 0)

    def test_umbrales_y_desempate_estable(self):
        for segundos, aviso, prioridad in [(719, False, False), (720, True, False), (899, True, False), (900, True, True)]:
            turno = self.turno(espera=segundos)
            self.assertEqual(espera_turno(turno, self.ahora), {"segundos": segundos, "advertencia": aviso, "prioridad": prioridad})
        self.activar()
        primero = self.turno(espera=901)
        self.turno("cronicos", espera=901)
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(Turno.objects.get(estado="llamado").pk, primero.pk)

    def test_retorno_simulado_utiliza_entrada_actual_no_emision(self):
        self.activar()
        reincorporado = self.turno(espera=2000)
        previo = self.turno(espera=100)
        Turno.objects.filter(pk=reincorporado.pk).update(entrada_cola=self.ahora)
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(Turno.objects.get(estado="llamado").pk, previo.pk)

    def test_configuracion_nueva_reinicia_cursor_sin_lista_gigante(self):
        self.activar()
        self.turno("preferencial")
        procesar_pendiente(self.pendiente().pk)
        self.cerrar_fixture()
        ConfiguracionCola.objects.update(peso_general=100000, version=2)
        preferencial = self.turno("preferencial")
        procesar_pendiente(self.pendiente().pk)
        self.assertEqual(Turno.objects.get(estado="llamado").pk, preferencial.pk)

    def test_ventanilla_inactiva_o_activada_ayer_no_llama(self):
        ventanilla = self.activar()
        self.turno()
        for cambios in ({"automatico": False}, {"automatico": True, "fecha_activacion": self.fecha - timedelta(days=1)}):
            Ventanilla.objects.filter(pk=ventanilla.pk).update(**cambios)
            self.assertEqual(procesar_pendiente(self.pendiente().pk), 0)
        self.assertFalse(EventoTurno.objects.exists())

    def test_operador_revocado_no_recibe_asignacion(self):
        self.activar()
        self.turno()
        actor = self.personal["tecnico"]
        actor.is_active = False
        actor.save()
        self.assertEqual(procesar_pendiente(self.pendiente().pk), 0)

    def test_reprocesar_pendiente_confirmado_no_duplica_evento(self):
        self.activar()
        self.turno()
        pendiente = self.pendiente()
        self.assertEqual(procesar_pendiente(pendiente.pk), 1)
        self.assertEqual(procesar_pendiente(pendiente.pk), 0)
        self.assertEqual(EventoTurno.objects.count(), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="turno.llamado").count(), 1)

    def test_fallo_auditoria_conserva_pendiente_y_comando_recupera(self):
        self.activar()
        turno = self.turno()
        pendiente = self.pendiente()
        with patch("turnosapp.cola.registrar_accion", side_effect=RuntimeError("detalle privado")):
            self.assertIsNone(procesar_seguro(pendiente.pk))
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "esperando")
        self.assertFalse(EventoTurno.objects.exists())
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.codigo_fallo, "seleccion_pendiente")
        call_command("procesar_cola", stdout=io.StringIO())
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, "procesado")
        self.assertEqual(EventoTurno.objects.count(), 1)

    def test_emision_enciende_seleccion_sin_otro_click_y_sin_consumir_entrega(self):
        self.activar()
        turno_base = self.turno()
        paciente = turno_base.paciente
        turno_base.delete()
        receta = Receta.objects.create(paciente=paciente, codigo="COLA-DEMO-RECETA", fecha_inicio=self.fecha,
            fecha_fin_exclusiva=self.fecha + timedelta(days=30), vigencia_meses=1, max_entregas=3)
        import uuid
        with self.captureOnCommitCallbacks(execute=True):
            resultado = emitir_turno(paciente.rut, uuid.uuid4())
        self.assertEqual(Turno.objects.get().estado, "llamado")
        self.assertEqual(resultado.numero, Turno.objects.get().numero)
        receta.refresh_from_db()
        self.assertEqual(receta.entregas_completadas, 0)
        self.assertTrue(emitir_turno(paciente.rut, uuid.uuid4()).recuperado)

    def test_sin_configuracion_pendiente_sigue_durable(self):
        ConfiguracionCola.objects.all().delete()
        pendiente = self.pendiente()
        self.assertIsNone(procesar_seguro(pendiente.pk))
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, "pendiente")
        self.assertEqual(pendiente.codigo_fallo, "sin_configuracion")

    def test_error_no_transitorio_no_se_reintenta(self):
        with patch("turnosapp.cola._procesar", side_effect=OperationalError("error estructural")) as llamada:
            with self.assertRaises(OperationalError):
                procesar_pendiente(self.pendiente().pk)
            self.assertEqual(llamada.call_count, 1)
