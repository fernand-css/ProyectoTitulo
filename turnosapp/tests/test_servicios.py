"""Reglas de emisión, recuperación y rollback con datos sintéticos."""

import uuid
from dataclasses import asdict
from datetime import date, timedelta
from random import Random
from unittest.mock import patch

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import Paciente, PreparacionReceta, Receta, EntregaReceta
from turnosapp.models import Turno, TurnoReceta, ContadorTurnosDiario
from turnosapp.services import emitir_turno, ErrorEmision


class EmisionTests(TestCase):
    def setUp(self):
        self.fecha = date(2026, 11, 2)
        reloj = patch("turnosapp.services.timezone.localdate", return_value=self.fecha)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.ruts = generar_ruts(10, Random(402))
        self.paciente = self.pacientes(0)
        self.receta = self.recetas(self.paciente, "DEMO-1")

    def pacientes(self, indice):
        return Paciente.objects.create(rut=self.ruts[indice], nombres="Paciente sintético", apellidos="Demo", fecha_nacimiento=date(1970, 1, 1))

    def recetas(self, paciente, codigo, **cambios):
        datos = dict(paciente=paciente, codigo=codigo, fecha_inicio=self.fecha, fecha_fin_exclusiva=self.fecha + timedelta(days=30), vigencia_meses=1, max_entregas=3)
        datos.update(cambios)
        return Receta.objects.create(**datos)

    def emitir(self, paciente=None, operacion=None):
        return emitir_turno((paciente or self.paciente).rut, operacion or uuid.uuid4())

    def test_reune_solo_elegibles_y_no_consume_entregas(self):
        otra = self.recetas(self.paciente, "DEMO-2")
        self.recetas(self.paciente, "FUTURA", fecha_inicio=self.fecha + timedelta(days=1))
        self.recetas(self.paciente, "VENCIDA", fecha_inicio=self.fecha - timedelta(days=40), fecha_fin_exclusiva=self.fecha)
        self.recetas(self.paciente, "AGOTADA", entregas_completadas=3)
        resultado = self.emitir()
        self.assertEqual(resultado.numero, 1)
        self.assertEqual(set(TurnoReceta.objects.values_list("receta_id", flat=True)), {self.receta.pk, otra.pk})
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 0)
        self.assertFalse(EntregaReceta.objects.exists())
        self.assertEqual(set(asdict(resultado)), {"numero", "fecha", "creado_en", "recuperado", "espera"})
        self.assertIn("No podemos estimar", resultado.espera)

    def test_recupera_mismo_uuid_y_distinto_sin_modificar_seleccion(self):
        operacion = uuid.uuid4()
        self.emitir(operacion=operacion)
        self.recetas(self.paciente, "NUEVA")
        Receta.objects.filter(pk=self.receta.pk).update(entregas_completadas=3)
        self.assertTrue(self.emitir(operacion=operacion).recuperado)
        self.assertTrue(self.emitir().recuperado)
        self.assertEqual(Turno.objects.count(), 1)
        self.assertEqual(TurnoReceta.objects.count(), 1)
        self.assertEqual(ContadorTurnosDiario.objects.get().ultimo_numero, 1)
        evento = RegistroAuditoria.objects.get(accion="turno.emitido")
        self.assertIsNone(evento.usuario_id)
        self.assertEqual(evento.objeto_id, str(Turno.objects.get().pk))

    def test_limites_de_edad_cronico_y_postrado(self):
        for edad, cronico, postrado, esperado in (
            (59, False, False, "general"), (59, True, False, "cronicos"),
            (60, True, False, "preferencial"), (80, False, False, "preferencial"),
            (81, False, False, None), (30, False, True, None),
        ):
            with self.subTest(edad=edad, postrado=postrado):
                self.paciente.fecha_nacimiento = self.fecha.replace(year=self.fecha.year - edad)
                self.paciente.es_cronico, self.paciente.es_postrado = cronico, postrado
                self.paciente.save()
                if esperado:
                    self.emitir()
                    self.assertEqual(Turno.objects.get().tipo_atencion, esperado)
                    PreparacionReceta.objects.all().delete()
                    TurnoReceta.objects.all().delete()
                    Turno.objects.all().delete()
                else:
                    with self.assertRaisesMessage(ErrorEmision, "Consulta tu despacho"):
                        self.emitir()

    def test_sin_recetas_futuras_agotadas_no_consume_contador(self):
        for cambios in ({"fecha_inicio": self.fecha + timedelta(days=1)}, {"entregas_completadas": 3}):
            Receta.objects.filter(pk=self.receta.pk).update(**cambios)
            with self.assertRaises(ErrorEmision):
                self.emitir()
            self.assertFalse(ContadorTurnosDiario.objects.exists())
        self.receta.delete()
        with self.assertRaises(ErrorEmision):
            self.emitir()
        self.assertFalse(Turno.objects.exists())

    def test_uuid_ajeno_invalido_y_no_registrado(self):
        operacion = uuid.uuid4()
        self.emitir(operacion=operacion)
        otro = self.pacientes(1)
        for rut, op in ((otro.rut, operacion), (self.ruts[2], uuid.uuid4()), (self.paciente.rut, "incorrecto")):
            with self.assertRaises(ErrorEmision):
                emitir_turno(rut, op)
        self.assertEqual(Turno.objects.count(), 1)

    def test_rollback_auditoria_y_fallo_no_transitorio(self):
        with patch("turnosapp.services.registrar_accion", side_effect=RuntimeError("privado")):
            with self.assertRaisesMessage(RuntimeError, "No se pudo registrar"):
                self.emitir()
        for modelo in (Turno, TurnoReceta, ContadorTurnosDiario, RegistroAuditoria):
            self.assertFalse(modelo.objects.exists())
        with patch("turnosapp.services._emitir", side_effect=OperationalError("fallo no transitorio")) as llamada:
            with self.assertRaises(OperationalError):
                self.emitir()
            self.assertEqual(llamada.call_count, 1)

    def test_agotamiento_de_reintentos_es_recuperable(self):
        with patch("turnosapp.services._emitir", side_effect=OperationalError("locked")) as llamada, patch("turnosapp.services.time.sleep"):
            with self.assertRaisesMessage(ErrorEmision, "ocupado"):
                self.emitir()
            self.assertEqual(llamada.call_count, 12)

    def test_nuevo_dia_reinicia_serie_sin_borrar_anterior(self):
        self.emitir()
        with patch("turnosapp.services.timezone.localdate", return_value=self.fecha + timedelta(days=1)):
            self.assertEqual(self.emitir().numero, 1)
        self.assertEqual(Turno.objects.count(), 2)
        self.assertEqual(ContadorTurnosDiario.objects.count(), 2)

    def test_admin_no_expone_escrituras(self):
        for modelo in (Turno, TurnoReceta, ContadorTurnosDiario):
            self.assertFalse(admin.site.is_registered(modelo))

    def test_rut_normalizado_y_dv_invalido(self):
        cuerpo, dv = self.paciente.rut.split("-")
        formato = f"{int(cuerpo):,}-{dv.lower()}".replace(",", ".")
        self.assertEqual(emitir_turno(formato, uuid.uuid4()).numero, 1)
        with self.assertRaises(ValidationError):
            emitir_turno("incorrecto", uuid.uuid4())

    def test_bloqueo_domiciliario_prevalece_sobre_recuperacion(self):
        operacion = uuid.uuid4()
        self.emitir(operacion=operacion)
        Paciente.objects.filter(pk=self.paciente.pk).update(es_postrado=True)
        with self.assertRaisesMessage(ErrorEmision, "Consulta tu despacho"):
            self.emitir(operacion=operacion)
        self.assertEqual(Turno.objects.count(), 1)
