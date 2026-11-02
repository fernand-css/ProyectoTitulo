"""Vigencia, permisos, idempotencia y conservación transaccional."""

import uuid
from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from recetasapp.models import EntregaReceta, Paciente, Receta
from recetasapp.services import calcular_fin, crear_receta, evaluar_elegibilidad, registrar_entrega
from .ayudas import actores, cargar, fila


class ServiciosTests(TestCase):
    def setUp(self):
        reloj = patch("recetasapp.services.timezone.localdate", return_value=date(2026, 11, 2))
        reloj.start()
        self.addCleanup(reloj.stop)
        self.actores = actores()
        cargar(self.actores["qf"], [fila()])
        self.receta = Receta.objects.get()

    def test_calendario_meses_cortos_bisiestos_y_overflow(self):
        for inicio, meses, fin in [(date(2026, 1, 31), 1, date(2026, 2, 28)), (date(2024, 1, 31), 1, date(2024, 2, 29)), (date(2024, 2, 29), 12, date(2025, 2, 28)), (date(2026, 12, 1), 2, date(2027, 2, 1))]:
            with self.subTest(inicio=inicio):
                self.assertEqual(calcular_fin(inicio, meses), fin)
        for meses in (0, -1, True, 99999999):
            with self.assertRaises(ValidationError):
                calcular_fin(date(2026, 1, 1), meses)

    def test_elegibilidad_en_limites_y_causas_simultaneas(self):
        for fecha, esperado in [(date(2025, 12, 31), False), (date(2026, 1, 1), True), (date(2026, 12, 31), True), (date(2027, 1, 1), False)]:
            self.assertEqual(evaluar_elegibilidad(self.receta, fecha)["elegible"], esperado)
        self.receta.entregas_completadas = self.receta.max_entregas
        self.assertEqual(len(evaluar_elegibilidad(self.receta, date(2027, 1, 1))["causas"]), 2)

    def test_renovar_conserva_historial_y_no_admite_otro_paciente(self):
        registrar_entrega(self.actores["tecnico"], self.receta.pk, uuid.uuid4())
        nueva = crear_receta(self.actores["qf"], paciente_id=self.receta.paciente_id, codigo="RENOVADA", fecha_inicio=date(2027, 1, 1), vigencia_meses=6, max_entregas=6, anterior_id=self.receta.pk)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 1)
        self.assertEqual(nueva.receta_anterior, self.receta)
        self.assertEqual(nueva.entregas_completadas, 0)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="receta.renovada").count(), 1)

    def test_entrega_repetida_cuenta_una_vez_y_rechaza_actor_o_destino_distinto(self):
        operacion = uuid.uuid4()
        primera = registrar_entrega(self.actores["tecnico"], self.receta.pk, operacion)
        segunda = registrar_entrega(self.actores["tecnico"], self.receta.pk, operacion)
        self.assertEqual(primera.pk, segunda.pk)
        for actor, destino in [(self.actores["admin"], self.receta.pk), (self.actores["tecnico"], 99999)]:
            with self.assertRaises(ValidationError):
                registrar_entrega(actor, destino, operacion)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, self.receta.entregas.count())
        self.assertEqual(self.receta.entregas_completadas, 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="receta.entrega").count(), 1)

    def test_roles_no_pueden_intercambiar_funciones(self):
        for nombre in ("qf", "encargado"):
            with self.assertRaises(PermissionDenied):
                registrar_entrega(self.actores[nombre], self.receta.pk, uuid.uuid4())
        for nombre in ("tecnico", "encargado"):
            with self.assertRaises(PermissionDenied):
                crear_receta(self.actores[nombre], paciente_id=self.receta.paciente_id, codigo="DENEGADA", fecha_inicio=date(2026, 1, 1), vigencia_meses=1, max_entregas=1)

    def test_inactividad_y_perfil_ausente_se_revisan_en_servidor(self):
        actor = self.actores["tecnico"]
        actor.is_active = False
        actor.save()
        with self.assertRaises(PermissionDenied):
            registrar_entrega(actor, self.receta.pk, uuid.uuid4())
        actor.is_active = True
        actor.save()
        actor.perfil.delete()
        with self.assertRaises(PermissionDenied):
            registrar_entrega(actor, self.receta.pk, uuid.uuid4())

    def test_no_entrega_con_receta_futura_vencida_o_agotada(self):
        hoy = timezone.localdate()
        for valores in ({"fecha_inicio": hoy + timedelta(days=1), "fecha_fin_exclusiva": hoy + timedelta(days=50)}, {"fecha_fin_exclusiva": hoy}, {"entregas_completadas": self.receta.max_entregas}):
            with self.subTest(valores=valores):
                Receta.objects.filter(pk=self.receta.pk).update(**valores)
                with self.assertRaises(ValidationError):
                    registrar_entrega(self.actores["tecnico"], self.receta.pk, uuid.uuid4())
                Receta.objects.filter(pk=self.receta.pk).update(fecha_inicio=date(2026, 1, 1), fecha_fin_exclusiva=date(2027, 1, 1), entregas_completadas=0)
        self.assertEqual(EntregaReceta.objects.count(), 0)

    def test_fallo_auditoria_revierte_entrega_y_receta(self):
        with patch("recetasapp.services.registrar_accion", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                registrar_entrega(self.actores["tecnico"], self.receta.pk, uuid.uuid4())
            with self.assertRaises(RuntimeError):
                crear_receta(self.actores["qf"], paciente_id=self.receta.paciente_id, codigo="FALLO", fecha_inicio=date(2026, 1, 1), vigencia_meses=1, max_entregas=1)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 0)
        self.assertFalse(EntregaReceta.objects.exists())
        self.assertFalse(Receta.objects.filter(codigo="FALLO").exists())
