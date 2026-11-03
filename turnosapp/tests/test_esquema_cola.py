"""Integridad del esquema 05 y preparación explícita, sin servicios de atención."""
import io
import uuid
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from recetasapp.models import EntregaReceta
from turnosapp.models import (
    CierreAtencion, ConfiguracionCola, DetalleCierre, EstadoColaDiaria, EventoTurno,
    OcupacionVentanilla, OperacionAtencion, PendienteSeleccion, TipoAtencionVentanilla,
    Turno, TurnoReceta, Ventanilla,
)
from . import test_servicios as preparacion


class EsquemaColaTests(TestCase):
    setUp = preparacion.EmisionTests.setUp
    pacientes = preparacion.EmisionTests.pacientes
    recetas = preparacion.EmisionTests.recetas

    def preparar(self):
        call_command("preparar_ventanillas", stdout=io.StringIO())

    def operador(self, nombre="tecnico_cola_sintetico"):
        return get_user_model().objects.create_user(username=nombre)

    def turno(self, **cambios):
        datos = dict(paciente=self.paciente, fecha=self.fecha, numero=1, tipo_atencion="general")
        datos.update(cambios)
        return Turno.objects.create(**datos)

    def rechazar_update(self, objeto, **cambios):
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(objeto).objects.filter(pk=objeto.pk).update(**cambios)

    def llamado(self, paciente=None, numero=1, fecha=None, ventanilla=None, operador=None):
        return self.turno(paciente=paciente or self.paciente, numero=numero, fecha=fecha or self.fecha,
            estado="llamado", ventanilla=ventanilla or Ventanilla.objects.create(numero=numero),
            operador=operador or self.operador(), ultimo_llamado=timezone.now())

    def test_preparacion_idempotente_no_activa_no_crea_cuentas_ni_turnos(self):
        self.preparar()
        self.assertEqual(Ventanilla.objects.count(), 4)
        self.assertEqual(TipoAtencionVentanilla.objects.count(), 3)
        self.assertTrue(all(v.tipos.count() == 3 and not v.automatico and v.operador_id is None for v in Ventanilla.objects.all()))
        config = ConfiguracionCola.objects.get()
        self.assertEqual((config.peso_preferencial, config.peso_cronicos, config.peso_general), (2, 1, 1))
        eventos = RegistroAuditoria.objects.count()
        self.preparar()
        self.assertEqual(RegistroAuditoria.objects.count(), eventos)
        self.assertFalse(RegistroAuditoria.objects.exclude(usuario=None).exists())
        for modelo in (get_user_model(), Turno, EntregaReceta, EventoTurno, PendienteSeleccion):
            self.assertFalse(modelo.objects.exists())

    def test_preparacion_conserva_pesos_y_tipos_personalizados(self):
        self.preparar()
        ventanilla = Ventanilla.objects.get(numero=1)
        ventanilla.tipos.clear()
        ventanilla.habilitada = False
        ventanilla.save()
        ConfiguracionCola.objects.update(peso_general=5)
        self.preparar()
        ventanilla.refresh_from_db()
        self.assertFalse(ventanilla.habilitada)
        self.assertEqual(ventanilla.tipos.count(), 0)
        self.assertEqual(ConfiguracionCola.objects.get().peso_general, 5)

    def test_fallo_auditoria_preparacion_revierte_dominio_y_eventos(self):
        with patch("turnosapp.management.commands.preparar_ventanillas.registrar_accion", side_effect=RuntimeError("fallo sintético")):
            with self.assertRaises(RuntimeError):
                self.preparar()
        for modelo in (Ventanilla, TipoAtencionVentanilla, ConfiguracionCola, RegistroAuditoria):
            self.assertFalse(modelo.objects.exists())

    def test_ventanilla_exige_operador_unico_y_automatismo_coherente(self):
        operador = self.operador()
        ventanilla = Ventanilla.objects.create(numero=1, operador=operador)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ventanilla.objects.create(numero=2, operador=operador)
        for cambios in ({"numero": 0}, {"automatico": True}, {"retirada": True}):
            self.rechazar_update(ventanilla, **cambios)
        Ventanilla.objects.filter(pk=ventanilla.pk).update(automatico=True, fecha_activacion=self.fecha)
        self.rechazar_update(ventanilla, habilitada=False)

    def test_ocupacion_vigente_unica_conserva_historial(self):
        tecnico = self.operador()
        otra_persona = self.operador("otro_tecnico_sintetico")
        v1, v2 = Ventanilla.objects.create(numero=1), Ventanilla.objects.create(numero=2)
        ocupacion = OcupacionVentanilla.objects.create(ventanilla=v1, tecnico=tecnico)
        for ventanilla, actor in ((v1, otra_persona), (v2, tecnico)):
            with self.assertRaises(IntegrityError), transaction.atomic():
                OcupacionVentanilla.objects.create(ventanilla=ventanilla, tecnico=actor)
        self.rechazar_update(ocupacion, cierre=ocupacion.apertura - timedelta(seconds=1))
        ocupacion.cierre = timezone.now()
        ocupacion.save()
        OcupacionVentanilla.objects.create(ventanilla=v1, tecnico=tecnico)
        self.assertEqual(OcupacionVentanilla.objects.count(), 2)

    def test_llamado_reserva_paciente_dia_y_ventanilla(self):
        llamado = self.llamado()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.turno(numero=2)
        otro = self.pacientes(1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.llamado(paciente=otro, numero=2, ventanilla=llamado.ventanilla, operador=llamado.operador)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.llamado(numero=3, fecha=self.fecha + timedelta(days=1), operador=llamado.operador)

    def test_estado_cierre_y_asignacion_coherentes(self):
        turno = self.turno()
        for cambios in ({"estado": "llamado"}, {"estado": "ausente"}, {"cerrado_en": timezone.now()}, {"estado": "desconocido"}):
            self.rechazar_update(turno, **cambios)
        for estado in ("atendido", "ausente", "cerrado_sin_entrega", "sin_atencion_cierre"):
            Turno.objects.filter(pk=turno.pk).update(estado=estado, cerrado_en=timezone.now())
            turno.refresh_from_db()
            turno.full_clean()
        self.assertEqual(turno.numero, 1)

    def test_configuracion_unica_pesos_positivos_y_estado_diario_unico(self):
        config = ConfiguracionCola.objects.create()
        for campo in ("peso_preferencial", "peso_cronicos", "peso_general"):
            self.rechazar_update(config, **{campo: 0})
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConfiguracionCola.objects.create(pk=2)
        EstadoColaDiaria.objects.create(fecha=self.fecha)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EstadoColaDiaria.objects.create(fecha=self.fecha)

    def test_eventos_secuencia_y_pendientes_durables(self):
        turno = self.turno()
        EventoTurno.objects.create(turno=turno, secuencia=1, accion="llamado")
        for secuencia in (0, 1):
            with self.assertRaises(IntegrityError), transaction.atomic():
                EventoTurno.objects.create(turno=turno, secuencia=secuencia, accion="rellamado")
        pendiente = PendienteSeleccion.objects.create(motivo="emision")
        self.rechazar_update(pendiente, estado="procesado")
        self.rechazar_update(pendiente, estado="inventado")
        PendienteSeleccion.objects.filter(pk=pendiente.pk).update(estado="procesado", procesado_en=timezone.now())
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, "procesado")

    def test_vinculo_entrega_unico_y_corresponde_a_receta(self):
        turno = self.turno()
        vinculo = TurnoReceta.objects.create(turno=turno, receta=self.receta)
        EntregaReceta.objects.create(receta=self.receta, numero=1, turno_receta=vinculo)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EntregaReceta.objects.create(receta=self.receta, numero=2, turno_receta=vinculo)
        otra = self.recetas(self.paciente, "OTRA-SINTETICA")
        invalida = EntregaReceta(receta=otra, numero=1, turno_receta=vinculo)
        with self.assertRaises(ValidationError):
            invalida.full_clean()

    def test_cierre_detalle_y_entrega_no_se_duplican_y_exigen_motivo(self):
        turno = self.turno()
        vinculo = TurnoReceta.objects.create(turno=turno, receta=self.receta)
        operacion = OperacionAtencion.objects.create(actor=self.operador(), tipo="finalizar", turno=turno, huella="a" * 64)
        cierre = CierreAtencion.objects.create(turno=turno, actor=operacion.actor, operacion=operacion, resultado="sin_entrega", motivo="No disponible")
        self.rechazar_update(cierre, motivo="")
        with self.assertRaises(IntegrityError), transaction.atomic():
            DetalleCierre.objects.create(cierre=cierre, turno_receta=vinculo)
        detalle = DetalleCierre.objects.create(cierre=cierre, turno_receta=vinculo, motivo="No disponible")
        self.rechazar_update(detalle, entregada=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DetalleCierre.objects.create(cierre=cierre, turno_receta=vinculo, motivo="Repetido")

    def test_detalle_no_puede_validar_receta_de_otro_turno(self):
        original = self.turno()
        vinculo = TurnoReceta.objects.create(turno=original, receta=self.receta)
        otro = self.turno(paciente=self.pacientes(1), numero=2)
        actor = self.operador()
        operacion = OperacionAtencion.objects.create(actor=actor, tipo="finalizar", turno=otro, huella="b" * 64)
        cierre = CierreAtencion.objects.create(turno=otro, actor=actor, operacion=operacion, resultado="sin_entrega", motivo="No disponible")
        with self.assertRaises(ValidationError):
            DetalleCierre(cierre=cierre, turno_receta=vinculo, motivo="No disponible").full_clean()
