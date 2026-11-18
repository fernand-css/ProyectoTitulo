"""Escenarios sintéticos preparados; no ejecutados en la etapa de persistencia."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from apps.totem.models import DispositivoTotem, EstadoActivacion


class DispositivoTotemModeloTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        if connection.vendor != "postgresql" or connection.settings_dict["NAME"] != "test_cesfam_desarrollo":
            raise RuntimeError("Estas pruebas requieren PostgreSQL y test_cesfam_desarrollo.")
        super().setUpClass()

    def setUp(self):
        self.ahora = timezone.now()
        self.indice = 0

    def crear(self, **cambios):
        self.indice += 1
        datos = {"alias": f"totem-sintetico-{self.indice}", "creado_en": self.ahora - timedelta(days=1)}
        datos.update(cambios)
        return DispositivoTotem.objects.create(**datos)

    def datos_codigo(self, estado=EstadoActivacion.PENDIENTE):
        emitido = self.ahora - timedelta(minutes=2)
        datos = {
            "estado_activacion": estado,
            "referencia_activacion": uuid.uuid4(),
            # No es un hash utilizable ni procede de una credencial real.
            "hash_activacion": "hash-sintetico-no-utilizable",
            "activacion_emitida_en": emitido,
            "activacion_expira_en": emitido + timedelta(minutes=5),
        }
        if estado != EstadoActivacion.PENDIENTE:
            datos["hash_activacion"] = ""
            datos["activacion_cerrada_en"] = self.ahora - timedelta(minutes=1)
        if estado == EstadoActivacion.UTILIZADO:
            datos["activado_en"] = datos["activacion_cerrada_en"]
        if estado == EstadoActivacion.CADUCADO:
            datos["activacion_emitida_en"] = self.ahora - timedelta(minutes=10)
            datos["activacion_expira_en"] = self.ahora - timedelta(minutes=5)
        return datos

    def con_cuota(self, **cambios):
        datos = {
            "ventana_minuto": self.ahora.replace(second=0, microsecond=0),
            "ventana_hora": self.ahora.replace(minute=0, second=0, microsecond=0),
        }
        datos.update(cambios)
        return self.crear(**datos)

    def rechazar_actualizacion(self, dispositivo, **cambios):
        anterior = DispositivoTotem.objects.values().get(pk=dispositivo.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DispositivoTotem.objects.filter(pk=dispositivo.pk).update(**cambios)
        self.assertEqual(DispositivoTotem.objects.values().get(pk=dispositivo.pk), anterior)

    def test_alta_inactiva_sin_codigo_ni_consumo(self):
        dispositivo = self.crear()
        self.assertFalse(dispositivo.activo)
        self.assertEqual(dispositivo.version_credencial, 1)
        self.assertEqual(dispositivo.estado_activacion_actual, EstadoActivacion.SIN_CODIGO)
        self.assertIsNone(dispositivo.referencia_activacion)
        self.assertEqual(dispositivo.hash_activacion, "")
        self.assertIsNone(dispositivo.activado_en)
        self.assertIsNone(dispositivo.ventana_minuto)
        self.assertIsNone(dispositivo.ventana_hora)
        self.assertEqual((dispositivo.solicitudes_minuto, dispositivo.solicitudes_hora), (0, 0))
        self.assertEqual((dispositivo.limite_minuto, dispositivo.limite_hora), (10, 100))
        dispositivo.full_clean()

    def test_uuid_independientes_y_alias_sin_exponer_hash(self):
        primero = self.crear(**self.datos_codigo())
        segundo = self.crear()
        self.assertIsInstance(primero.pk, uuid.UUID)
        self.assertNotEqual(primero.pk, segundo.pk)
        self.assertEqual(str(primero), primero.alias)
        self.assertNotIn(primero.hash_activacion, str(primero))

    def test_uuid_duplicado_es_rechazado(self):
        primero = self.crear()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear(id=primero.pk)

    def test_alias_duplicado_es_rechazado(self):
        primero = self.crear()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear(alias=primero.alias)

    def test_alias_tecnico_rechaza_vacio_y_espacios_en_base(self):
        dispositivo = self.crear()
        for alias in ("", "  ", "totem ficticio"):
            with self.subTest(alias=alias):
                self.rechazar_actualizacion(dispositivo, alias=alias)

    def test_validacion_django_rechaza_alias_excesivo(self):
        dispositivo = self.crear()
        dispositivo.alias = "a" * 65
        with self.assertRaises(ValidationError):
            dispositivo.full_clean()

    def test_version_de_credencial_debe_ser_positiva(self):
        dispositivo = self.crear()
        for version in (0, -1):
            with self.subTest(version=version):
                self.rechazar_actualizacion(dispositivo, version_credencial=version)

    def test_limites_de_cuota_deben_ser_positivos(self):
        dispositivo = self.crear()
        for campo in ("limite_minuto", "limite_hora"):
            for valor in (0, -1):
                with self.subTest(campo=campo, valor=valor):
                    self.rechazar_actualizacion(dispositivo, **{campo: valor})

    def test_consumos_no_pueden_ser_negativos(self):
        dispositivo = self.con_cuota()
        for campo in ("solicitudes_minuto", "solicitudes_hora"):
            with self.subTest(campo=campo):
                self.rechazar_actualizacion(dispositivo, **{campo: -1})

    def test_consumo_admite_limites_exactos(self):
        dispositivo = self.con_cuota(solicitudes_minuto=10, solicitudes_hora=100)
        dispositivo.full_clean()
        self.assertEqual((dispositivo.solicitudes_minuto, dispositivo.solicitudes_hora), (10, 100))

    def test_consumo_no_supera_limite_minuto(self):
        dispositivo = self.con_cuota(solicitudes_hora=20)
        self.rechazar_actualizacion(dispositivo, solicitudes_minuto=11)

    def test_consumo_no_supera_limite_hora(self):
        dispositivo = self.con_cuota()
        self.rechazar_actualizacion(dispositivo, solicitudes_hora=101)

    def test_consumo_del_minuto_no_supera_el_de_su_hora(self):
        dispositivo = self.con_cuota(solicitudes_hora=2)
        self.rechazar_actualizacion(dispositivo, solicitudes_minuto=3)

    def test_sin_ventanas_no_puede_existir_consumo(self):
        dispositivo = self.crear()
        self.rechazar_actualizacion(dispositivo, solicitudes_minuto=1, solicitudes_hora=1)

    def test_ventanas_deben_establecerse_juntas(self):
        dispositivo = self.crear()
        for campo in ("ventana_minuto", "ventana_hora"):
            with self.subTest(campo=campo):
                self.rechazar_actualizacion(dispositivo, **{campo: self.ahora})

    def test_minuto_debe_pertenecer_a_la_ventana_horaria(self):
        dispositivo = self.con_cuota()
        for ventana in (dispositivo.ventana_hora - timedelta(minutes=1),
                        dispositivo.ventana_hora + timedelta(hours=1)):
            with self.subTest(ventana=ventana):
                self.rechazar_actualizacion(dispositivo, ventana_minuto=ventana)

    def test_pendiente_valido_no_genera_credencial(self):
        dispositivo = self.crear(**self.datos_codigo())
        dispositivo.full_clean()
        self.assertEqual(dispositivo.estado_activacion_actual, EstadoActivacion.PENDIENTE)
        self.assertFalse(dispositivo.activo)

    def test_caducidad_efectiva_en_el_instante_limite_sin_escrituras(self):
        dispositivo = self.crear(**self.datos_codigo())
        anterior = DispositivoTotem.objects.values().get(pk=dispositivo.pk)
        for momento, estado in (
            (dispositivo.activacion_expira_en - timedelta(microseconds=1), EstadoActivacion.PENDIENTE),
            (dispositivo.activacion_expira_en, EstadoActivacion.CADUCADO),
            (dispositivo.activacion_expira_en + timedelta(days=1), EstadoActivacion.CADUCADO),
        ):
            with self.subTest(momento=momento), patch("apps.totem.models.timezone.now", return_value=momento):
                with self.assertNumQueries(0):
                    self.assertEqual(dispositivo.estado_activacion_actual, estado)
        self.assertEqual(DispositivoTotem.objects.values().get(pk=dispositivo.pk), anterior)

    def test_sin_codigo_no_admite_referencia_hash_fechas_o_intentos(self):
        dispositivo = self.crear()
        for cambio in (
            {"referencia_activacion": uuid.uuid4()}, {"hash_activacion": "hash-sintetico"},
            {"activacion_emitida_en": self.ahora}, {"activacion_expira_en": self.ahora},
            {"activacion_cerrada_en": self.ahora}, {"intentos_fallidos": 1},
        ):
            with self.subTest(cambio=cambio):
                self.rechazar_actualizacion(dispositivo, **cambio)

    def test_pendiente_requiere_referencia_hash_y_fechas(self):
        dispositivo = self.crear(**self.datos_codigo())
        for campo, valor in (
            ("referencia_activacion", None), ("hash_activacion", ""),
            ("activacion_emitida_en", None), ("activacion_expira_en", None),
        ):
            with self.subTest(campo=campo):
                self.rechazar_actualizacion(dispositivo, **{campo: valor})

    def test_pendiente_no_admite_cierre_ni_cinco_fallos(self):
        dispositivo = self.crear(**self.datos_codigo())
        self.rechazar_actualizacion(dispositivo, activacion_cerrada_en=self.ahora)
        self.rechazar_actualizacion(dispositivo, intentos_fallidos=5)

    def test_pendiente_admite_hasta_cuatro_fallos(self):
        datos = self.datos_codigo()
        datos["intentos_fallidos"] = 4
        dispositivo = self.crear(**datos)
        dispositivo.full_clean()

    def test_referencia_activacion_debe_ser_unica(self):
        datos = self.datos_codigo()
        self.crear(**datos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear(**datos)

    def test_estado_desconocido_es_rechazado(self):
        self.rechazar_actualizacion(self.crear(), estado_activacion="OTRO")

    def test_terminales_conservan_referencia_y_eliminan_hash(self):
        for estado in (EstadoActivacion.UTILIZADO, EstadoActivacion.CADUCADO, EstadoActivacion.INVALIDADO):
            with self.subTest(estado=estado):
                dispositivo = self.crear(**self.datos_codigo(estado))
                dispositivo.full_clean()
                self.assertIsNotNone(dispositivo.referencia_activacion)
                self.assertEqual(dispositivo.hash_activacion, "")
                self.rechazar_actualizacion(dispositivo, hash_activacion="hash-sintetico")
                self.rechazar_actualizacion(dispositivo, activacion_cerrada_en=None)

    def test_utilizado_requiere_fecha_de_activacion(self):
        dispositivo = self.crear(**self.datos_codigo(EstadoActivacion.UTILIZADO))
        self.rechazar_actualizacion(dispositivo, activado_en=None)

    def test_utilizado_no_puede_consumirse_al_vencer_o_despues(self):
        dispositivo = self.crear(**self.datos_codigo(EstadoActivacion.UTILIZADO))
        for cierre in (dispositivo.activacion_expira_en, dispositivo.activacion_expira_en + timedelta(seconds=1)):
            with self.subTest(cierre=cierre):
                # Aislar la vigencia respecto de las otras restricciones temporales.
                self.rechazar_actualizacion(
                    dispositivo, activacion_cerrada_en=cierre, activado_en=cierre,
                    actualizado_en=cierre + timedelta(seconds=1),
                )

    def test_caducado_materializado_no_cierra_antes_del_vencimiento(self):
        dispositivo = self.crear(**self.datos_codigo(EstadoActivacion.CADUCADO))
        self.rechazar_actualizacion(
            dispositivo, activacion_cerrada_en=dispositivo.activacion_expira_en - timedelta(seconds=1),
        )

    def test_invalidado_admite_cinco_fallos_y_hash_borrado(self):
        datos = self.datos_codigo(EstadoActivacion.INVALIDADO)
        datos["intentos_fallidos"] = 5
        dispositivo = self.crear(**datos)
        dispositivo.full_clean()
        self.assertEqual(dispositivo.estado_activacion_actual, EstadoActivacion.INVALIDADO)

    def test_intentos_no_admiten_negativos_ni_mas_de_cinco(self):
        dispositivo = self.crear(**self.datos_codigo(EstadoActivacion.INVALIDADO))
        for intentos in (-1, 6):
            with self.subTest(intentos=intentos):
                self.rechazar_actualizacion(dispositivo, intentos_fallidos=intentos)

    def test_codigo_expira_despues_de_emitirse(self):
        dispositivo = self.crear(**self.datos_codigo())
        self.rechazar_actualizacion(dispositivo, activacion_expira_en=dispositivo.activacion_emitida_en)

    def test_cierre_no_puede_preceder_a_emision(self):
        dispositivo = self.crear(**self.datos_codigo(EstadoActivacion.INVALIDADO))
        self.rechazar_actualizacion(
            dispositivo, activacion_cerrada_en=dispositivo.activacion_emitida_en - timedelta(seconds=1),
        )

    def test_activo_requiere_fecha_de_activacion(self):
        dispositivo = self.crear()
        self.rechazar_actualizacion(dispositivo, activo=True)

    def test_orden_de_fechas_tecnicas(self):
        dispositivo = self.crear(**self.datos_codigo())
        for cambio in (
            {"actualizado_en": dispositivo.creado_en - timedelta(seconds=1)},
            {"activado_en": dispositivo.creado_en - timedelta(seconds=1)},
            {"activado_en": dispositivo.actualizado_en + timedelta(days=1)},
            {"activacion_emitida_en": dispositivo.creado_en - timedelta(seconds=1)},
        ):
            with self.subTest(cambio=cambio):
                self.rechazar_actualizacion(dispositivo, **cambio)

    def test_codigo_pendiente_o_caducado_no_revoca_activacion_anterior(self):
        for estado in (EstadoActivacion.PENDIENTE, EstadoActivacion.CADUCADO):
            with self.subTest(estado=estado):
                datos = self.datos_codigo(estado)
                datos.update(activo=True, activado_en=self.ahora - timedelta(hours=1), version_credencial=2)
                dispositivo = self.crear(**datos)
                dispositivo.full_clean()
                self.assertTrue(dispositivo.activo)
                self.assertEqual(dispositivo.version_credencial, 2)

    def test_terminales_no_se_reabren_por_paso_del_tiempo(self):
        for estado in (EstadoActivacion.UTILIZADO, EstadoActivacion.CADUCADO, EstadoActivacion.INVALIDADO):
            dispositivo = self.crear(**self.datos_codigo(estado))
            with self.subTest(estado=estado), patch(
                "apps.totem.models.timezone.now", return_value=self.ahora + timedelta(days=30),
            ):
                self.assertEqual(dispositivo.estado_activacion_actual, estado)

    def test_rollback_no_conserva_alta_de_dispositivo(self):
        with self.assertRaises(RuntimeError), transaction.atomic():
            self.crear()
            raise RuntimeError("Rollback sintético")
        self.assertFalse(DispositivoTotem.objects.exists())
