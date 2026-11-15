"""Reglas de emisión, recuperación y rollback con datos sintéticos."""

import uuid
from dataclasses import asdict
from datetime import date, timedelta
from random import Random
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.test import TestCase
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import Paciente, PreparacionReceta, Receta, EntregaReceta
from turnosapp.models import Turno, TurnoReceta, ContadorTurnosDiario, Ventanilla
from turnosapp.services import CODIGO_RECHAZO, MENSAJE_NEUTRO, emitir_turno, ErrorEmision


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
        self.assertEqual(set(asdict(resultado)), {"numero", "letra", "codigo", "fecha", "creado_en", "recuperado", "espera", "renovacion"})
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

    def limpiar(self):
        PreparacionReceta.objects.all().delete()
        TurnoReceta.objects.all().delete()
        Turno.objects.all().delete()

    def test_limites_de_edad_cronico_y_postrado(self):
        """Enmienda 2026-11-15: P desde 60, incluidos 79/80/81 y postrados; C crónico menor de 60; G el resto."""
        for edad, cronico, postrado, esperado in (
            (59, False, False, "general"), (59, True, False, "cronicos"),
            (60, True, False, "preferencial"), (60, False, False, "preferencial"),
            (79, False, False, "preferencial"), (80, False, False, "preferencial"),
            (81, True, False, "preferencial"), (30, False, True, "preferencial"), (30, True, True, "preferencial"),
        ):
            with self.subTest(edad=edad, cronico=cronico, postrado=postrado):
                self.paciente.fecha_nacimiento = self.fecha.replace(year=self.fecha.year - edad)
                self.paciente.es_cronico, self.paciente.es_postrado = cronico, postrado
                self.paciente.save()
                resultado = self.emitir()
                turno = Turno.objects.get()
                self.assertEqual(turno.tipo_atencion, esperado)
                self.assertEqual(resultado.letra, {"general": "G", "cronicos": "C", "preferencial": "P"}[esperado])
                self.assertEqual(turno.recetas_vinculadas.count(), 1)
                self.limpiar()

    def test_nunca_emite_urgencia(self):
        self.emitir()
        self.emitir(self.pacientes(1))
        emitir_turno(self.ruts[2], uuid.uuid4())
        self.assertFalse(Turno.objects.filter(letra="U").exists())
        self.assertFalse(ContadorTurnosDiario.objects.filter(letra="U").exists())

    def test_series_por_letra_independientes(self):
        cronico = self.pacientes(1)
        Paciente.objects.filter(pk=cronico.pk).update(es_cronico=True)
        mayor = self.pacientes(2)
        Paciente.objects.filter(pk=mayor.pk).update(fecha_nacimiento=date(1940, 1, 1))
        codigos = [self.emitir().codigo, self.emitir(cronico).codigo, self.emitir(mayor).codigo,
                   emitir_turno(self.ruts[5], uuid.uuid4()).codigo]
        self.assertEqual(codigos, ["G-001", "C-001", "P-001", "G-002"])
        self.assertEqual(dict(ContadorTurnosDiario.objects.values_list("letra", "ultimo_numero")), {"G": 2, "C": 1, "P": 1})

    def test_no_registrado_recibe_g_sin_recetas_ni_paciente(self):
        pacientes = Paciente.objects.count()
        resultado = emitir_turno(self.ruts[5], uuid.uuid4())
        turno = Turno.objects.get()
        self.assertEqual((resultado.letra, resultado.codigo, resultado.numero), ("G", "G-001", 1))
        self.assertFalse(resultado.renovacion)
        self.assertIsNone(turno.paciente)
        self.assertEqual(turno.rut, self.ruts[5])
        self.assertFalse(turno.recetas_vinculadas.exists())
        self.assertEqual(Paciente.objects.count(), pacientes)
        self.assertFalse(PreparacionReceta.objects.exists())
        self.assertEqual(RegistroAuditoria.objects.filter(accion="turno.emitido").count(), 1)

    def test_no_registrado_se_recupera_por_rut_con_otro_uuid(self):
        primero = emitir_turno(self.ruts[5], uuid.uuid4())
        segundo = emitir_turno(self.ruts[5], uuid.uuid4())
        self.assertTrue(segundo.recuperado)
        self.assertEqual(primero.codigo, segundo.codigo)
        self.assertEqual(Turno.objects.count(), 1)

    def test_sin_recetas_elegibles_emite_turno_sin_recetas(self):
        for codigo, cambios, renovacion in (
            ("futura", {"fecha_inicio": self.fecha + timedelta(days=1)}, False),
            ("agotada", {"entregas_completadas": 3}, True),
            ("vencida", {"fecha_inicio": self.fecha - timedelta(days=40), "fecha_fin_exclusiva": self.fecha}, True),
        ):
            with self.subTest(codigo):
                Receta.objects.filter(pk=self.receta.pk).update(
                    fecha_inicio=self.fecha, fecha_fin_exclusiva=self.fecha + timedelta(days=30), entregas_completadas=0)
                Receta.objects.filter(pk=self.receta.pk).update(**cambios)
                resultado = self.emitir()
                self.assertFalse(resultado.recuperado)
                self.assertEqual(resultado.renovacion, renovacion)
                self.assertFalse(TurnoReceta.objects.exists())
                self.limpiar()
        self.receta.delete()
        self.assertFalse(self.emitir().renovacion)
        self.assertFalse(TurnoReceta.objects.exists())

    def test_renovacion_acompana_a_un_turno_con_otras_recetas_y_se_omite_si_ya_se_renovo(self):
        vencida = self.recetas(self.paciente, "VENCIDA", fecha_inicio=self.fecha - timedelta(days=40), fecha_fin_exclusiva=self.fecha)
        operacion = uuid.uuid4()
        resultado = self.emitir(operacion=operacion)
        self.assertTrue(resultado.renovacion)
        self.assertEqual(list(TurnoReceta.objects.values_list("receta_id", flat=True)), [self.receta.pk])
        self.assertTrue(self.emitir(operacion=operacion).renovacion)  # la recuperación conserva el aviso
        self.recetas(self.paciente, "RENOVADA", receta_anterior=vencida)
        self.assertFalse(self.emitir(operacion=operacion).renovacion)

    def test_operacion_ajena_cerrada_o_invalida_da_el_mismo_mensaje_neutro(self):
        operacion = uuid.uuid4()
        self.emitir(operacion=operacion)
        otro = self.pacientes(1)
        rechazos = []
        for rut, op in ((otro.rut, operacion), (self.ruts[5], operacion), (self.paciente.rut, "incorrecto")):
            with self.assertRaises(ErrorEmision) as error:
                emitir_turno(rut, op)
            rechazos.append(error.exception)
        Turno.objects.update(estado="atendido", cerrado_en=timezone.now())
        with self.assertRaises(ErrorEmision) as error:
            emitir_turno(self.paciente.rut, operacion)
        rechazos.append(error.exception)
        self.assertEqual({(e.code, tuple(e.messages)) for e in rechazos}, {(CODIGO_RECHAZO, (MENSAJE_NEUTRO,))})
        self.assertNotIn("nueva atención", MENSAJE_NEUTRO)
        self.assertEqual(Turno.objects.count(), 1)

    def test_turno_llamado_de_ayer_no_se_recupera(self):
        ayer = self.fecha - timedelta(days=1)
        with patch("turnosapp.services.timezone.localdate", return_value=ayer):
            anterior = self.emitir()
        turno = Turno.objects.get()
        operador = get_user_model().objects.create_user(username="operador_sintetico")
        Turno.objects.filter(pk=turno.pk).update(estado="llamado", ventanilla=Ventanilla.objects.create(numero=1),
            operador=operador, ultimo_llamado=timezone.now())
        resultado = self.emitir()
        self.assertFalse(resultado.recuperado)
        self.assertEqual((resultado.fecha, resultado.numero, anterior.fecha), (self.fecha, 1, ayer))
        self.assertEqual(Turno.objects.count(), 2)
        with self.assertRaises(ErrorEmision) as error:  # su operación tampoco devuelve el turno de ayer
            self.emitir(operacion=turno.operacion_id)
        self.assertEqual(error.exception.messages, [MENSAJE_NEUTRO])

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

    def test_postracion_posterior_no_bloquea_la_recuperacion(self):
        operacion = uuid.uuid4()
        self.emitir(operacion=operacion)
        Paciente.objects.filter(pk=self.paciente.pk).update(es_postrado=True)
        self.assertTrue(self.emitir(operacion=operacion).recuperado)
        self.assertEqual(Turno.objects.get().tipo_atencion, "general")  # la recuperación conserva la letra
