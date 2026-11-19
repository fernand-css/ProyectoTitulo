"""Permisos, persistencia y migración del inicio de traslado (spec 12)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from coreapp.models import RegistroAuditoria
from entregasapp import services
from entregasapp.models import AvisoReparto, IntentoEntrega
from .ayudas import equipo, hoy, visita


@override_settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=())
class InicioTrasladoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipo = equipo()
        cls.encargado = cls.equipo["encargado"]
        cls.intento = visita(cls.equipo, domicilio=False)

    def test_inicio_explicito_en_tarjeta_sin_coordenadas_y_idempotente(self):
        self.client.force_login(self.encargado)
        mis_entregas = reverse("entregasapp:mis")
        url = reverse("entregasapp:iniciar_traslado", args=[self.intento.pk])
        consulta = self.client.get(mis_entregas)
        self.assertContains(consulta, "Iniciar traslado")
        self.assertContains(consulta, url)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertFalse(AvisoReparto.objects.exists())

        for _ in range(2):
            self.assertRedirects(self.client.post(url), mis_entregas)
        siguiente = self.client.get(mis_entregas)
        self.assertContains(siguiente, "Traslado iniciado")
        self.assertNotContains(siguiente, "Iniciar traslado")
        self.intento.refresh_from_db()
        self.assertEqual(self.intento.traslado_iniciado_por_id, self.encargado.pk)
        self.assertEqual(self.intento.resultado, IntentoEntrega.Resultado.PENDIENTE)
        self.assertIsNone(self.intento.operacion_id)
        aviso = AvisoReparto.objects.get()
        self.assertEqual(aviso.estado, AvisoReparto.Estado.OMITIDO)
        self.assertEqual(aviso.codigo_resultado, "sin_destino")
        self.assertEqual(RegistroAuditoria.objects.filter(accion="intento.traslado_iniciado").count(), 1)

    def test_solicitud_sin_csrf_y_roles_no_autorizados(self):
        url = reverse("entregasapp:iniciar_traslado", args=[self.intento.pk])
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.encargado)
        self.assertEqual(cliente.post(url).status_code, 403)

        for rol in ("encargado2", "qf", "tecnico", "admin"):
            with self.subTest(rol=rol):
                self.client.force_login(self.equipo[rol])
                self.assertEqual(self.client.post(url).status_code, 403)
                with self.assertRaises(PermissionDenied):
                    services.iniciar_traslado(self.equipo[rol], self.intento.pk)
        self.assertFalse(AvisoReparto.objects.exists())

    def test_rechaza_visita_futura_y_resultado_sin_exigir_inicio(self):
        futuro = visita(self.equipo, fecha=hoy() + timedelta(days=1))
        with self.assertRaises(ValidationError):
            services.iniciar_traslado(self.encargado, futuro.pk)
        services.registrar_entregada(self.encargado, self.intento.pk, uuid4())
        with self.assertRaises(ValidationError):
            services.iniciar_traslado(self.encargado, self.intento.pk)
        # «Entregada» crea su propio aviso (cuarta enmienda); lo que no debe existir es un «en camino».
        self.assertFalse(AvisoReparto.objects.filter(tipo=AvisoReparto.Tipo.EN_CAMINO).exists())

    def test_revierte_inicio_cuando_falla_bandeja_o_auditoria(self):
        for simbolo in ("notificaciones.encolar_salida", "auditar"):
            with self.subTest(simbolo=simbolo):
                with patch(f"entregasapp.services.{simbolo}", side_effect=IntegrityError("prueba")):
                    with self.assertRaises(IntegrityError):
                        services.iniciar_traslado(self.encargado, self.intento.pk)
                self.intento.refresh_from_db()
                self.assertIsNone(self.intento.traslado_iniciado_en)
                self.assertFalse(AvisoReparto.objects.exists())


@override_settings(REPARTO_CORREO_DOMINIOS_PERMITIDOS=())
class InicioConcurrenteTests(TransactionTestCase):
    def test_dos_dispositivos_registran_un_solo_inicio(self):
        usuarios = equipo()
        intento = visita(usuarios)
        barrera = Barrier(2)

        def iniciar():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return services.iniciar_traslado(usuarios["encargado"], intento.pk)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as hilos:
            primero, segundo = hilos.submit(iniciar), hilos.submit(iniciar)
            self.assertCountEqual([primero.result(timeout=15), segundo.result(timeout=15)], [False, True])
        self.assertEqual(AvisoReparto.objects.filter(intento=intento).count(), 1)


class MigracionAvisoTests(TransactionTestCase):
    def test_migrar_desde_0003_no_infiere_inicios_ni_eventos(self):
        anterior = [("entregasapp", "0003_recetaentrega_preparacion")]
        executor = MigrationExecutor(connection)
        actual = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(anterior)
            apps = executor.loader.project_state(anterior).apps
            usuario = apps.get_model("auth", "User").objects.create(username="encargado_migracion")
            paciente = apps.get_model("recetasapp", "Paciente").objects.create(
                rut="12345678-5", nombres="Paciente", apellidos="Sintético", fecha_nacimiento=date(1930, 1, 1),
            )
            entrega = apps.get_model("entregasapp", "Entrega").objects.create(paciente=paciente, operacion_id=uuid4())
            previo = apps.get_model("entregasapp", "IntentoEntrega").objects.create(
                entrega=entrega, encargado=usuario, numero=1, fecha_programada=hoy(),
            )
            MigrationExecutor(connection).migrate(actual)
            intento = IntentoEntrega.objects.get(pk=previo.pk)
            self.assertIsNone(intento.traslado_iniciado_en)
            self.assertIsNone(intento.traslado_iniciado_por_id)
            self.assertFalse(AvisoReparto.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(actual)
