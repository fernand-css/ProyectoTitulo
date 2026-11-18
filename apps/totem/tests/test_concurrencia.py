"""Carreras PostgreSQL preparadas, con conexiones independientes y plazos finitos."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, local
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import close_old_connections, connection, connections

from apps.totem import services
from apps.totem.credenciales import validar_credencial_dispositivo
from apps.totem.models import DispositivoTotem, EstadoActivacion
from apps.turnos.models import OperacionTurno
from .soporte import BaseTotemPostgreSQL


class TotemConcurrenciaTests(BaseTotemPostgreSQL):
    def _hilo(self, llamada, barrera=None):
        close_old_connections()
        try:
            if connection.vendor != "postgresql" or connection.settings_dict["NAME"] != "test_cesfam_desarrollo":
                raise RuntimeError("Destino de hilo no autorizado.")
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SET statement_timeout = '10s'")
            if barrera is not None:
                barrera.wait(timeout=10)
            return llamada()
        finally:
            connections.close_all()

    def _competir(self, *llamadas):
        barrera = Barrier(len(llamadas))
        with ThreadPoolExecutor(max_workers=len(llamadas)) as ejecutor:
            futuros = [ejecutor.submit(self._hilo, llamada, barrera) for llamada in llamadas]
            return [futuro.result(timeout=20) for futuro in futuros]

    def _ordenar(self, primera, segunda, distintos=False):
        """La primera retiene su bloqueo hasta que la segunda intenta adquirirlo.

        Con dispositivos distintos se exige que la segunda termine mientras la
        primera sigue bloqueada, demostrando ausencia de un bloqueo global.
        """
        retenida, intenta, terminada = Event(), Event(), Event()
        contexto = local()
        bloquear = services._bloquear

        def coordinado(dispositivo_id):
            if contexto.orden == 1:
                dispositivo = bloquear(dispositivo_id)
                retenida.set()
                if not (terminada if distintos else intenta).wait(timeout=10):
                    raise RuntimeError("No se completó la coordinación sintética.")
                return dispositivo
            intenta.set()
            return bloquear(dispositivo_id)

        def ejecutar(orden, llamada):
            contexto.orden = orden
            if orden == 2 and not retenida.wait(timeout=10):
                raise RuntimeError("La primera conexión no adquirió el bloqueo.")
            try:
                return self._hilo(llamada)
            finally:
                if orden == 2:
                    terminada.set()

        with patch("apps.totem.services._bloquear", side_effect=coordinado):
            with ThreadPoolExecutor(max_workers=2) as ejecutor:
                uno = ejecutor.submit(ejecutar, 1, primera)
                dos = ejecutor.submit(ejecutar, 2, segunda)
                return uno.result(timeout=20), dos.result(timeout=20)

    def test_doble_consumo_solo_una_activacion(self):
        generado = self.generar()
        llamada = lambda: services.consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
        resultados = self._competir(llamada, llamada)
        self.assertEqual(sorted(r.estado for r in resultados), ["activado", "rechazado"])
        self.assertEqual(sum(r.credencial is not None for r in resultados), 1)
        self.assertEqual(self.refrescar().version_credencial, 2)
        self.assertEqual(OperacionTurno.objects.filter(accion="TOTEM_ACTIVADO").count(), 1)

    def test_consumo_primero_revocacion_invalida_su_credencial(self):
        generado = self.generar()
        activado, revocado = self._ordenar(
            lambda: services.consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo),
            lambda: services.revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad"),
        )
        self.assertEqual((activado.estado, revocado.estado), ("activado", "revocado"))
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(activado.credencial)
        self.assertFalse(self.refrescar().activo)
        self.assertEqual(self.dispositivo.version_credencial, 3)

    def test_revocacion_primero_impide_consumo(self):
        generado = self.generar()
        revocado, rechazado = self._ordenar(
            lambda: services.revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad"),
            lambda: services.consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo),
        )
        self.assertEqual((revocado.estado, rechazado.estado), ("revocado", "rechazado"))
        self.assertIsNone(rechazado.credencial)
        self.assertFalse(self.refrescar().activo)

    def test_generacion_primero_impide_consumir_codigo_anterior(self):
        anterior = self.generar()
        nuevo, rechazado = self._ordenar(
            self.generar,
            lambda: services.consumir_codigo_activacion(self.dispositivo.pk, anterior.referencia, anterior.codigo),
        )
        self.assertEqual(rechazado.estado, "rechazado")
        self.assertEqual(self.refrescar().referencia_activacion, nuevo.referencia)
        self.assertEqual(self.dispositivo.intentos_fallidos, 0)

    def test_consumo_primero_y_generacion_preserva_credencial(self):
        anterior = self.generar()
        activado, nuevo = self._ordenar(
            lambda: services.consumir_codigo_activacion(self.dispositivo.pk, anterior.referencia, anterior.codigo),
            self.generar,
        )
        self.assertEqual(nuevo.estado, "generado")
        self.assertEqual(validar_credencial_dispositivo(activado.credencial).version, 2)
        self.assertEqual(self.refrescar().estado_activacion, EstadoActivacion.PENDIENTE)

    def test_generaciones_simultaneas_solo_ultima_referencia_funciona(self):
        resultados = self._competir(self.generar, self.generar)
        actual = self.refrescar().referencia_activacion
        anterior = next(r for r in resultados if r.referencia != actual)
        vigente = next(r for r in resultados if r.referencia == actual)
        self.assertEqual(services.consumir_codigo_activacion(self.dispositivo.pk, anterior.referencia, anterior.codigo).estado, "rechazado")
        self.assertEqual(services.consumir_codigo_activacion(self.dispositivo.pk, vigente.referencia, vigente.codigo).estado, "activado")
        self.assertEqual(OperacionTurno.objects.filter(accion="TOTEM_CODIGO_GENERADO").count(), 2)

    def test_fallos_concurrentes_no_superan_cinco(self):
        generado = self.generar()
        for _ in range(4):
            services.consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, "incorrecto")
        llamada = lambda: services.consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, "incorrecto")
        self._competir(llamada, llamada)
        self.assertEqual(self.refrescar().intentos_fallidos, 5)
        self.assertEqual(self.dispositivo.estado_activacion, EstadoActivacion.INVALIDADO)
        self.assertEqual(OperacionTurno.objects.filter(accion="TOTEM_CODIGO_INVALIDADO").count(), 1)

    def test_dispositivos_distintos_no_comparten_bloqueo_global(self):
        segundo = DispositivoTotem.objects.create(alias="segundo-sintetico")
        resultados = self._ordenar(
            self.generar,
            lambda: services.generar_codigo_activacion(self.usuario, segundo.pk, "prueba_sintetica"),
            distintos=True,
        )
        self.assertTrue(all(r.estado == "generado" for r in resultados))

    def test_caducidad_simultanea_se_materializa_una_sola_vez(self):
        self.generar()
        vencimiento = self.refrescar().activacion_expira_en
        llamada = lambda: services.caducar_codigo_activacion(self.usuario, self.dispositivo.pk)
        with patch("apps.totem.services.timezone.now", return_value=vencimiento):
            resultados = self._competir(llamada, llamada)
        self.assertEqual(sorted(r.estado for r in resultados), ["caducado", "sin_cambios"])
        self.assertEqual(OperacionTurno.objects.filter(accion="TOTEM_CODIGO_CADUCADO").count(), 1)
