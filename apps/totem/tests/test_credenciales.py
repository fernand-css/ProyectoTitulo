"""Credenciales sintéticas; escenarios preparados, sin ejecución autorizada."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.utils import timezone

from apps.totem.credenciales import (
    VIGENCIA_CREDENCIAL, _firmante, validar_credencial_dispositivo,
)
from apps.totem.models import DispositivoTotem
from .soporte import BaseTotemPostgreSQL


class TotemCredencialesTests(BaseTotemPostgreSQL):
    def test_firma_valida_consulta_postgresql_en_cada_uso(self):
        resultado = self.activar()
        with self.assertNumQueries(1):
            identidad = validar_credencial_dispositivo(resultado.credencial)
        self.assertEqual(identidad.dispositivo_id, self.dispositivo.pk)
        with self.assertNumQueries(1):
            self.assertEqual(validar_credencial_dispositivo(resultado.credencial), identidad)

    def test_duracion_exacta_de_ocho_horas_sin_renovacion(self):
        resultado = self.activar()
        datos = _firmante().unsign_object(resultado.credencial)
        desde = timezone.datetime.fromisoformat(datos["emitida_en"])
        hasta = timezone.datetime.fromisoformat(datos["expira_en"])
        self.assertEqual(hasta - desde, timedelta(hours=8))
        self.assertEqual(VIGENCIA_CREDENCIAL, timedelta(hours=8))
        validar_credencial_dispositivo(resultado.credencial)
        self.assertEqual(_firmante().unsign_object(resultado.credencial), datos)

    def test_rechaza_en_el_instante_exacto_de_expiracion(self):
        resultado = self.activar()
        datos = _firmante().unsign_object(resultado.credencial)
        hasta = timezone.datetime.fromisoformat(datos["expira_en"])
        # Se congela solo el reloj de negocio; la firma aún no supera max_age.
        with patch("apps.totem.credenciales.timezone.now", return_value=hasta):
            with self.assertRaises(PermissionDenied):
                validar_credencial_dispositivo(resultado.credencial)

    def test_acepta_justo_antes_de_expirar(self):
        resultado = self.activar()
        datos = _firmante().unsign_object(resultado.credencial)
        hasta = timezone.datetime.fromisoformat(datos["expira_en"])
        with patch("apps.totem.credenciales.timezone.now", return_value=hasta - timedelta(microseconds=1)):
            self.assertEqual(validar_credencial_dispositivo(resultado.credencial).version, 2)

    def test_firma_alterada_no_consulta_base_ni_expone_token(self):
        resultado = self.activar()
        token = resultado.credencial + "alterado"
        with self.assertNumQueries(0):
            with self.assertRaises(PermissionDenied) as error:
                validar_credencial_dispositivo(token)
        self.assertNotIn(token, str(error.exception))

    def test_cambio_de_clave_externa_invalida_firma_anterior(self):
        resultado = self.activar()
        with override_settings(SECRET_KEY="otra-clave-publica-sintetica"):
            with self.assertRaises(PermissionDenied):
                validar_credencial_dispositivo(resultado.credencial)

    def test_no_acepta_claves_de_respaldo(self):
        resultado = self.activar()
        with override_settings(
            SECRET_KEY="otra-clave-publica-sintetica",
            SECRET_KEY_FALLBACKS=["clave-publica-exclusiva-de-pruebas-sinteticas-totem"],
        ):
            with self.assertRaises(PermissionDenied):
                validar_credencial_dispositivo(resultado.credencial)

    def test_proposito_y_formato_manipulados_son_rechazados(self):
        resultado = self.activar()
        datos = _firmante().unsign_object(resultado.credencial)
        for cambios in (
            {"proposito": "otro-proposito"}, {"version": True}, {"version": 0},
            {"dispositivo": "invalido"}, {"identificador": "invalido"},
            {"emitida_en": "ayer"}, {"expira_en": None}, {"extra": "campo"},
            {"emitida_en": "2026-01-01T00:00:00"},
        ):
            with self.subTest(campos=tuple(cambios)):
                token = _firmante().sign_object({**datos, **cambios})
                with self.assertRaises(PermissionDenied):
                    validar_credencial_dispositivo(token)

    def test_firma_con_salt_distinto_es_rechazada(self):
        resultado = self.activar()
        datos = _firmante().unsign_object(resultado.credencial)
        token = signing.TimestampSigner(salt="otro-proposito").sign_object(datos)
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(token)

    def test_no_admite_prolongar_vigencia_aunque_payload_este_firmado(self):
        resultado = self.activar()
        datos = _firmante().unsign_object(resultado.credencial)
        hasta = timezone.datetime.fromisoformat(datos["expira_en"])
        datos["expira_en"] = (hasta + timedelta(hours=1)).isoformat()
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(_firmante().sign_object(datos))

    def test_reloj_anterior_a_emision_rechaza(self):
        resultado = self.activar()
        datos = _firmante().unsign_object(resultado.credencial)
        desde = timezone.datetime.fromisoformat(datos["emitida_en"])
        with patch("apps.totem.credenciales.timezone.now", return_value=desde - timedelta(microseconds=1)):
            with self.assertRaises(PermissionDenied):
                validar_credencial_dispositivo(resultado.credencial)

    def test_timestamp_de_firma_tambien_limita_vigencia(self):
        resultado = self.activar()
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 8 * 3600 + 1):
            with self.assertRaises(PermissionDenied):
                validar_credencial_dispositivo(resultado.credencial)

    def test_inactivo_y_version_distinta_se_rechazan(self):
        resultado = self.activar()
        DispositivoTotem.objects.filter(pk=self.dispositivo.pk).update(activo=False)
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(resultado.credencial)
        DispositivoTotem.objects.filter(pk=self.dispositivo.pk).update(activo=True, version_credencial=3)
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(resultado.credencial)

    def test_uuid_inexistente_firmado_no_autoriza(self):
        resultado = self.activar()
        datos = _firmante().unsign_object(resultado.credencial)
        datos["dispositivo"] = str(uuid.uuid4())
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(_firmante().sign_object(datos))

    def test_entradas_invalidas_sin_consulta(self):
        for token in (None, b"sintetico", "", "x" * 2049, "no-firmado", ".comprimido"):
            with self.subTest(tipo=type(token).__name__), self.assertNumQueries(0):
                with self.assertRaises(PermissionDenied):
                    validar_credencial_dispositivo(token)
