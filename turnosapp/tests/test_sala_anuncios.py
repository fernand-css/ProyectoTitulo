"""Atomicidad e idempotencia del registro público, con datos sintéticos."""
import io
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from turnosapp.atencion import rellamar
from turnosapp.cola import procesar_pendiente, procesar_seguro
from turnosapp.models import AnuncioSala, EventoTurno, OperacionAtencion, Turno, Ventanilla
from turnosapp.sala import registrar_anuncio
from .datos_cola import DatosCola


class AnunciosSalaTests(DatosCola, TestCase):
    def llamar(self):
        ventanilla = self.activar()
        turno = self.turno()
        pendiente = self.pendiente()
        procesar_pendiente(pendiente.pk)
        return ventanilla, turno, pendiente

    def test_llamado_y_rellamado_copian_evento_y_numeros(self):
        ventanilla, turno, _ = self.llamar()
        rellamar(self.personal["tecnico"], turno.pk, uuid.uuid4())
        anuncios = list(AnuncioSala.objects.select_related("evento").order_by("id"))
        self.assertEqual([a.accion for a in anuncios], ["llamado", "rellamado"])
        for anuncio in anuncios:
            self.assertEqual(anuncio.numero, turno.numero)
            self.assertEqual(anuncio.ventanilla_numero, ventanilla.numero)
            self.assertEqual(anuncio.instante, anuncio.evento.instante)
            self.assertEqual(anuncio.fecha, self.fecha)

    def test_reproceso_y_helper_no_duplican_ni_reescriben_copia(self):
        ventanilla, turno, pendiente = self.llamar()
        anuncio = AnuncioSala.objects.get()
        Ventanilla.objects.filter(pk=ventanilla.pk).update(numero=99)
        ventanilla.refresh_from_db()
        self.assertEqual(procesar_pendiente(pendiente.pk), 0)
        self.assertEqual(registrar_anuncio(anuncio.evento, turno, ventanilla).pk, anuncio.pk)
        anuncio.refresh_from_db()
        self.assertEqual(anuncio.ventanilla_numero, 1)
        self.assertEqual(AnuncioSala.objects.count(), 1)

    def test_reenvio_post_rellamado_no_duplica(self):
        _, turno, _ = self.llamar()
        self.client.force_login(self.personal["tecnico"])
        datos = {"operacion_id": str(uuid.uuid4())}
        url = f"/turnos/{turno.pk}/rellamar/"
        for _ in range(2):
            self.assertEqual(self.client.post(url, datos).status_code, 302)
        self.assertEqual(AnuncioSala.objects.filter(accion="rellamado").count(), 1)

    def test_fallo_anuncio_revierte_seleccion_y_comando_recupera(self):
        self.activar()
        turno = self.turno()
        pendiente = self.pendiente()
        with patch("turnosapp.sala.AnuncioSala.objects.get_or_create", side_effect=RuntimeError("fallo sintético")):
            self.assertIsNone(procesar_seguro(pendiente.pk))
        turno.refresh_from_db()
        pendiente.refresh_from_db()
        self.assertEqual(turno.estado, "esperando")
        self.assertIsNone(turno.ventanilla_id)
        self.assertEqual(pendiente.estado, "pendiente")
        self.assertEqual(pendiente.codigo_fallo, "seleccion_pendiente")
        self.assertFalse(EventoTurno.objects.exists())
        self.assertFalse(AnuncioSala.objects.exists())
        self.assertFalse(OperacionAtencion.objects.exists())
        call_command("procesar_cola", stdout=io.StringIO())
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, "procesado")
        self.assertEqual(AnuncioSala.objects.count(), 1)

    def test_fallo_rellamado_revierte_y_misma_operacion_es_recuperable(self):
        _, turno, _ = self.llamar()
        turno.refresh_from_db()
        anterior = turno.ultimo_llamado
        identidad = uuid.uuid4()
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(seconds=10)):
            with patch("turnosapp.sala.AnuncioSala.objects.get_or_create", side_effect=RuntimeError("fallo sintético")):
                with self.assertRaises(RuntimeError):
                    rellamar(self.personal["tecnico"], turno.pk, identidad)
            turno.refresh_from_db()
            self.assertEqual(turno.ultimo_llamado, anterior)
            self.assertFalse(OperacionAtencion.objects.filter(pk=identidad).exists())
            self.assertFalse(EventoTurno.objects.filter(accion="rellamado").exists())
            self.assertEqual(AnuncioSala.objects.count(), 1)
            rellamar(self.personal["tecnico"], turno.pk, identidad)
            rellamar(self.personal["tecnico"], turno.pk, identidad)
        self.assertEqual(AnuncioSala.objects.count(), 2)

    def test_fecha_es_la_del_llamado_y_no_la_emision(self):
        _, turno, _ = self.llamar()
        with patch("turnosapp.atencion.timezone.now", return_value=self.ahora + timedelta(days=1)):
            rellamar(self.personal["tecnico"], turno.pk, uuid.uuid4())
        self.assertEqual(AnuncioSala.objects.get(accion="rellamado").fecha, self.fecha + timedelta(days=1))

    def test_restricciones_impiden_datos_invalidos_y_evento_duplicado(self):
        self.llamar()
        anuncio = AnuncioSala.objects.get()
        for cambios in ({"numero": 0}, {"ventanilla_numero": 0}, {"accion": "ausente"}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                AnuncioSala.objects.filter(pk=anuncio.pk).update(**cambios)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AnuncioSala.objects.create(evento=anuncio.evento, fecha=anuncio.fecha,
                numero=1, ventanilla_numero=1, accion="llamado", instante=anuncio.instante)
        with self.assertRaises(ProtectedError):
            anuncio.evento.delete()

    def test_modelo_sin_relaciones_a_paciente_turno_o_receta(self):
        relaciones = [campo.related_model for campo in AnuncioSala._meta.fields if campo.is_relation]
        self.assertEqual(relaciones, [EventoTurno])

    def test_helper_rechaza_evento_no_publico(self):
        ventanilla, turno, _ = self.llamar()
        evento = EventoTurno.objects.create(turno=turno, secuencia=2, accion="ausente", instante=self.ahora)
        with self.assertRaises(ValueError):
            registrar_anuncio(evento, turno, ventanilla)
        self.assertEqual(AnuncioSala.objects.count(), 1)
