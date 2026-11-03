"""Acciones del personal, retorno y control de jornada sin cierre de entregas."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from coreapp.models import RegistroAuditoria
from recetasapp.models import EntregaReceta, Receta
from turnosapp.atencion import (
    ocupar_ventanilla, iniciar_automatico, pausar_ventanilla, liberar_ventanilla,
    configurar_ventanilla, configurar_pesos, crear_ventanilla, rellamar, marcar_ausente, reincorporar,
)
from turnosapp.cola import cerrar_jornada_anterior, procesar_pendiente
from turnosapp.models import ConfiguracionCola, ContadorTurnosDiario, EventoTurno, OcupacionVentanilla, OperacionAtencion, Turno, Ventanilla
from turnosapp.services import emitir_turno
from .datos_cola import DatosCola


class AtencionTests(DatosCola, TestCase):
    def hacer(self, funcion, *args, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return funcion(*args, **kwargs)

    def abrir(self):
        vent = Ventanilla.objects.get(numero=1)
        self.hacer(ocupar_ventanilla, self.personal["tecnico"], vent.pk, uuid.uuid4())
        return vent

    def llamar(self):
        vent = self.abrir()
        turno = self.turno()
        self.hacer(iniciar_automatico, self.personal["tecnico"], vent.pk, uuid.uuid4())
        turno.refresh_from_db()
        return vent, turno

    def test_ocupar_idempotente_libera_y_conserva_historial(self):
        vent = Ventanilla.objects.get(numero=1)
        op = uuid.uuid4()
        primero = ocupar_ventanilla(self.personal["tecnico"], vent.pk, op)
        self.assertEqual(ocupar_ventanilla(self.personal["tecnico"], vent.pk, op), primero)
        self.assertEqual(OcupacionVentanilla.objects.count(), 1)
        liberar_ventanilla(self.personal["tecnico"], vent.pk, uuid.uuid4())
        vent.refresh_from_db()
        self.assertIsNone(vent.operador_id)
        self.assertIsNotNone(OcupacionVentanilla.objects.get().cierre)

    def test_un_tecnico_no_ocupa_dos_ni_ventanilla_de_otro(self):
        self.abrir()
        with self.assertRaises(ValidationError):
            ocupar_ventanilla(self.personal["tecnico"], Ventanilla.objects.get(numero=2).pk, uuid.uuid4())
        with self.assertRaises(ValidationError):
            ocupar_ventanilla(self.personal["admin"], Ventanilla.objects.get(numero=1).pk, uuid.uuid4())
        with self.assertRaises(PermissionDenied):
            pausar_ventanilla(self.personal["admin"], Ventanilla.objects.get(numero=1).pk, uuid.uuid4())

    def test_iniciar_llama_y_pausa_conserva_atencion_actual(self):
        vent, turno = self.llamar()
        self.assertEqual(turno.estado, "llamado")
        self.hacer(pausar_ventanilla, self.personal["tecnico"], vent.pk, uuid.uuid4())
        vent.refresh_from_db()
        turno.refresh_from_db()
        self.assertFalse(vent.automatico)
        self.assertEqual(turno.ventanilla_id, vent.pk)
        with self.assertRaises(ValidationError):
            liberar_ventanilla(self.personal["tecnico"], vent.pk, uuid.uuid4())

    def test_ausente_minuto_y_rellamado_reinicia_reloj(self):
        vent, turno = self.llamar()
        actor = self.personal["tecnico"]
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(seconds=59)):
            with self.assertRaises(ValidationError):
                marcar_ausente(actor, turno.pk, uuid.uuid4())
        identidad = uuid.uuid4()
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(seconds=60)):
            rellamar(actor, turno.pk, identidad)
            rellamar(actor, turno.pk, identidad)
            with self.assertRaises(ValidationError):
                marcar_ausente(actor, turno.pk, uuid.uuid4())
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(seconds=120)):
            self.hacer(marcar_ausente, actor, turno.pk, uuid.uuid4())
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "ausente")
        self.assertEqual(turno.eventos.filter(accion="rellamado").count(), 1)
        self.assertFalse(EntregaReceta.objects.exists())

    def test_ausentar_llama_otro_y_reenvio_no_toca_al_nuevo(self):
        vent, turno = self.llamar()
        siguiente = self.turno()
        op = uuid.uuid4()
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(seconds=60)):
            resultado = self.hacer(marcar_ausente, self.personal["tecnico"], turno.pk, op)
            self.assertEqual(marcar_ausente(self.personal["tecnico"], turno.pk, op), resultado)
        siguiente.refresh_from_db()
        self.assertEqual(siguiente.estado, "llamado")
        self.assertEqual(turno.eventos.filter(accion="ausente").count(), 1)

    def test_pausar_impide_llamado_despues_de_ausencia(self):
        vent, turno = self.llamar()
        siguiente = self.turno()
        pausar_ventanilla(self.personal["tecnico"], vent.pk, uuid.uuid4())
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(seconds=60)):
            self.hacer(marcar_ausente, self.personal["tecnico"], turno.pk, uuid.uuid4())
        siguiente.refresh_from_db()
        self.assertEqual(siguiente.estado, "esperando")

    def test_qf_confirma_deshabilitacion_y_no_reactiva_silenciosamente(self):
        vent, turno = self.llamar()
        with self.assertRaises(ValidationError):
            configurar_ventanilla(self.personal["qf"], vent.pk, uuid.uuid4(), habilitada=False)
        self.hacer(configurar_ventanilla, self.personal["qf"], vent.pk, uuid.uuid4(), habilitada=False, confirmar=True)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "llamado")
        self.hacer(configurar_ventanilla, self.personal["qf"], vent.pk, uuid.uuid4(), habilitada=True)
        vent.refresh_from_db()
        self.assertFalse(vent.automatico)

    def test_roles_no_permiten_operar_ni_configurar_fuera_de_matriz(self):
        vent = Ventanilla.objects.get(numero=1)
        for actor in (self.personal["qf"], self.personal["encargado"]):
            with self.assertRaises(PermissionDenied):
                ocupar_ventanilla(actor, vent.pk, uuid.uuid4())
        with self.assertRaises(PermissionDenied):
            configurar_ventanilla(self.personal["tecnico"], vent.pk, uuid.uuid4(), habilitada=False)
        actor = self.personal["tecnico"]
        actor.is_active = False
        actor.save()
        with self.assertRaises(PermissionDenied):
            ocupar_ventanilla(actor, vent.pk, uuid.uuid4())

    def test_uuid_no_se_reutiliza_para_otro_destino_o_payload(self):
        vent = Ventanilla.objects.get(numero=1)
        identidad = uuid.uuid4()
        configurar_ventanilla(self.personal["qf"], vent.pk, identidad, habilitada=False)
        for pk, estado in ((vent.pk, True), (Ventanilla.objects.get(numero=2).pk, False)):
            with self.assertRaises(ValidationError):
                configurar_ventanilla(self.personal["qf"], pk, identidad, habilitada=estado)

    def test_auditoria_fallida_revierte_ocupacion_operacion_y_ventanilla(self):
        vent = Ventanilla.objects.get(numero=1)
        with patch("turnosapp.atencion.registrar_accion", side_effect=RuntimeError("fallo sintético")):
            with self.assertRaises(RuntimeError):
                ocupar_ventanilla(self.personal["tecnico"], vent.pk, uuid.uuid4())
        vent.refresh_from_db()
        self.assertIsNone(vent.operador_id)
        self.assertFalse(OcupacionVentanilla.objects.exists())
        self.assertFalse(OperacionAtencion.objects.exists())

    def test_retorno_al_final_con_mismo_numero_y_sin_prioridad_anterior(self):
        vent, turno = self.llamar()
        pausar_ventanilla(self.personal["tecnico"], vent.pk, uuid.uuid4())
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(seconds=60)):
            self.hacer(marcar_ausente, self.personal["tecnico"], turno.pk, uuid.uuid4())
        anterior = self.turno()
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(seconds=120)):
            self.hacer(reincorporar, self.personal["tecnico"], turno.pk, uuid.uuid4())
        turno.refresh_from_db()
        self.assertEqual((turno.numero, turno.estado), (1, "esperando"))
        self.assertGreater(turno.entrada_cola, anterior.entrada_cola)
        self.assertEqual(turno.eventos.filter(accion="reincorporado").count(), 1)

    def test_nueva_emision_tras_ausente_bloquea_reincorporacion_anterior(self):
        vent, turno = self.llamar()
        pausar_ventanilla(self.personal["tecnico"], vent.pk, uuid.uuid4())
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(seconds=60)):
            self.hacer(marcar_ausente, self.personal["tecnico"], turno.pk, uuid.uuid4())
        ContadorTurnosDiario.objects.create(fecha=self.fecha, ultimo_numero=turno.numero)
        Receta.objects.create(paciente=turno.paciente, codigo="REEMISION-AUSENTE-DEMO", fecha_inicio=self.fecha,
            fecha_fin_exclusiva=self.fecha + timedelta(days=30), vigencia_meses=1, max_entregas=3)
        nuevo = emitir_turno(turno.paciente.rut, uuid.uuid4())
        self.assertEqual(nuevo.numero, 2)
        with self.assertRaises(ValidationError):
            reincorporar(self.personal["tecnico"], turno.pk, uuid.uuid4())

    def test_configuracion_pesos_y_creacion_solo_por_qf(self):
        configurar_pesos(self.personal["qf"], uuid.uuid4(), preferencial=3, cronicos=2, general=1)
        self.assertEqual(ConfiguracionCola.objects.get().version, 2)
        creado = crear_ventanilla(self.personal["qf"], uuid.uuid4(), numero=5, tipos=["general"])
        self.assertEqual(Ventanilla.objects.get(pk=creado["ventanilla"]).tipos.count(), 1)
        with self.assertRaises(ValidationError):
            configurar_pesos(self.personal["qf"], uuid.uuid4(), preferencial=0, cronicos=1, general=1)


class JornadaTests(DatosCola, TestCase):
    def test_cierra_esperando_anterior_sin_ausencia_ni_entrega(self):
        turno = self.turno()
        Turno.objects.filter(pk=turno.pk).update(fecha=self.fecha - timedelta(days=1))
        self.assertEqual(cerrar_jornada_anterior(), 1)
        self.assertEqual(cerrar_jornada_anterior(), 0)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "sin_atencion_cierre")
        self.assertEqual(turno.eventos.count(), 1)
        self.assertFalse(EntregaReceta.objects.exists())

    def test_llamado_anterior_se_conserva_y_no_emite_otro(self):
        vent = self.activar()
        turno = self.turno()
        Turno.objects.filter(pk=turno.pk).update(fecha=self.fecha - timedelta(days=1), estado="llamado",
            ventanilla=vent, operador=vent.operador, ultimo_llamado=self.ahora - timedelta(minutes=10))
        self.assertEqual(cerrar_jornada_anterior(), 0)
        resultado = emitir_turno(turno.paciente.rut, uuid.uuid4())
        self.assertTrue(resultado.recuperado)
        self.assertEqual(Turno.objects.count(), 1)
        self.assertEqual(resultado.fecha, self.fecha - timedelta(days=1))

    def test_activar_nueva_jornada_es_explicito(self):
        vent = self.activar()
        Ventanilla.objects.filter(pk=vent.pk).update(fecha_activacion=self.fecha - timedelta(days=1))
        turno = self.turno()
        procesar_pendiente(self.pendiente().pk)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "esperando")
        with self.captureOnCommitCallbacks(execute=True):
            iniciar_automatico(self.personal["tecnico"], vent.pk, uuid.uuid4())
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "llamado")

    def test_uuid_terminal_no_reabre_turno_ni_inventa_nueva_llegada(self):
        turno = self.turno()
        Turno.objects.filter(pk=turno.pk).update(estado="atendido", cerrado_en=self.ahora)
        with self.assertRaisesMessage(ValidationError, "cerrada"):
            emitir_turno(turno.paciente.rut, turno.operacion_id)
