"""Servicios preparados para ejecución PostgreSQL autorizada por separado."""
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.totem.credenciales import validar_credencial_dispositivo
from apps.totem.models import EstadoActivacion
from apps.totem.services import (
    caducar_codigo_activacion, consultar_dispositivo, consumir_codigo_activacion,
    generar_codigo_activacion, revocar_dispositivo,
)
from apps.turnos.models import OperacionTurno
from .soporte import BaseTotemPostgreSQL


class TotemServiciosTests(BaseTotemPostgreSQL):
    def test_generar_no_activa_ni_cambia_version_o_cuotas(self):
        with patch("apps.totem.services.secrets.token_urlsafe", return_value="secreto-sintetico") as token:
            resultado = self.generar()
        token.assert_called_once_with(32)
        d = self.refrescar()
        self.assertFalse(d.activo)
        self.assertEqual(d.version_credencial, 1)
        self.assertEqual((d.solicitudes_minuto, d.solicitudes_hora), (0, 0))
        self.assertIsNone(d.ventana_minuto)
        self.assertEqual(d.activacion_expira_en - d.activacion_emitida_en, timedelta(minutes=5))
        self.assertNotEqual(d.hash_activacion, resultado.codigo)
        self.assertTrue(check_password(resultado.codigo, d.hash_activacion))
        self.assertNotIn(resultado.codigo, repr(resultado))

    def test_consumo_correcto_activa_incrementa_y_borra_hash(self):
        generado = self.generar()
        resultado = consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
        d = self.refrescar()
        self.assertEqual(resultado.estado, "activado")
        self.assertTrue(d.activo)
        self.assertEqual(d.version_credencial, 2)
        self.assertEqual(d.hash_activacion, "")
        self.assertEqual(d.estado_activacion, EstadoActivacion.UTILIZADO)
        self.assertEqual(d.activado_en, d.activacion_cerrada_en)
        self.assertIsNotNone(resultado.credencial)
        self.assertNotIn(resultado.credencial, repr(resultado))

    def test_replay_no_entrega_otra_credencial(self):
        generado = self.generar()
        consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
        resultado = consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
        self.assertEqual(resultado.estado, "rechazado")
        self.assertIsNone(resultado.credencial)
        self.assertEqual(self.refrescar().version_credencial, 2)
        self.assertEqual(OperacionTurno.objects.filter(accion="TOTEM_ACTIVADO").count(), 1)

    def test_cinco_fallos_persisten_y_no_superan_limite(self):
        generado = self.generar()
        for numero in range(1, 7):
            resultado = consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, "incorrecto-sintetico")
            self.assertEqual(resultado.estado, "rechazado")
            d = self.refrescar()
            self.assertEqual(d.intentos_fallidos, min(numero, 5))
            self.assertEqual(d.estado_activacion, EstadoActivacion.PENDIENTE if numero < 5 else EstadoActivacion.INVALIDADO)
        self.assertEqual(d.hash_activacion, "")
        self.assertEqual(OperacionTurno.objects.filter(accion="TOTEM_INTENTO_FALLIDO").count(), 5)
        self.assertEqual(OperacionTurno.objects.filter(accion="TOTEM_CODIGO_INVALIDADO").count(), 1)

    def test_cuatro_fallos_permiten_consumo_valido(self):
        generado = self.generar()
        for _ in range(4):
            consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, "incorrecto")
        resultado = consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
        self.assertEqual(resultado.estado, "activado")
        self.assertEqual(self.refrescar().intentos_fallidos, 4)

    def test_sustitucion_cierra_referencia_anterior_y_no_penaliza_nueva(self):
        anterior = self.generar()
        nuevo = self.generar()
        self.assertNotEqual(anterior.referencia, nuevo.referencia)
        self.assertEqual(consumir_codigo_activacion(self.dispositivo.pk, anterior.referencia, anterior.codigo).estado, "rechazado")
        self.assertEqual(self.refrescar().intentos_fallidos, 0)
        cierre = OperacionTurno.objects.get(accion="TOTEM_CODIGO_INVALIDADO")
        self.assertEqual(cierre.detalles["anteriores"]["referencia"], str(anterior.referencia))
        self.assertEqual(consumir_codigo_activacion(self.dispositivo.pk, nuevo.referencia, nuevo.codigo).estado, "activado")

    def test_vencido_en_limite_materializa_sin_sumar_fallos(self):
        generado = self.generar()
        vencimiento = self.refrescar().activacion_expira_en
        with patch("apps.totem.services.timezone.now", return_value=vencimiento):
            resultado = consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
        d = self.refrescar()
        self.assertEqual(resultado.estado, "rechazado")
        self.assertEqual(d.estado_activacion, EstadoActivacion.CADUCADO)
        self.assertEqual((d.hash_activacion, d.intentos_fallidos), ("", 0))
        self.assertEqual(d.activacion_cerrada_en, vencimiento)
        self.assertEqual(OperacionTurno.objects.filter(accion="TOTEM_CODIGO_CADUCADO").count(), 1)

    def test_expiracion_durante_comparacion_no_activa(self):
        generado = self.generar()
        vencimiento = self.refrescar().activacion_expira_en
        with patch("apps.totem.services._ahora", side_effect=[vencimiento - timedelta(microseconds=1), vencimiento]), patch(
            "apps.totem.services.timezone.now", return_value=vencimiento,
        ):
            resultado = consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
        self.assertEqual(resultado.estado, "rechazado")
        self.assertFalse(self.refrescar().activo)

    def test_caducar_es_idempotente_y_conserva_credencial_previa(self):
        activado = self.activar()
        self.generar()
        vencimiento = self.refrescar().activacion_expira_en
        with patch("apps.totem.services.timezone.now", return_value=vencimiento):
            self.assertEqual(caducar_codigo_activacion(self.usuario, self.dispositivo.pk).estado, "caducado")
            self.assertEqual(caducar_codigo_activacion(self.usuario, self.dispositivo.pk).estado, "sin_cambios")
        self.assertTrue(self.refrescar().activo)
        self.assertEqual(validar_credencial_dispositivo(activado.credencial).version, 2)

    def test_caducar_antes_del_vencimiento_no_modifica(self):
        self.generar()
        cantidad = OperacionTurno.objects.count()
        self.assertEqual(caducar_codigo_activacion(self.usuario, self.dispositivo.pk).estado, "sin_cambios")
        self.assertEqual(OperacionTurno.objects.count(), cantidad)
        self.assertEqual(self.refrescar().estado_activacion, EstadoActivacion.PENDIENTE)

    def test_revocar_invalida_credencial_y_repetir_no_incrementa(self):
        activado = self.activar()
        self.assertEqual(revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad").estado, "revocado")
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(activado.credencial)
        self.assertEqual(self.refrescar().version_credencial, 3)
        self.assertEqual(revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad").estado, "sin_cambios")
        self.assertEqual(self.refrescar().version_credencial, 3)
        self.assertEqual(self.dispositivo.estado_activacion, EstadoActivacion.UTILIZADO)

    def test_revocar_pendiente_lo_invalida_sin_activarlo(self):
        generado = self.generar()
        revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")
        d = self.refrescar()
        self.assertEqual(d.estado_activacion, EstadoActivacion.INVALIDADO)
        self.assertFalse(d.activo)
        self.assertEqual((d.hash_activacion, d.version_credencial), ("", 2))
        self.assertEqual(consumir_codigo_activacion(d.pk, generado.referencia, generado.codigo).estado, "rechazado")

    def test_reactivar_exige_otro_codigo_y_version_nueva(self):
        anterior = self.activar()
        revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")
        nuevo = self.activar()
        self.assertEqual(nuevo.version, 4)
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(anterior.credencial)
        self.assertEqual(validar_credencial_dispositivo(nuevo.credencial).version, 4)

    def test_nueva_activacion_sustituye_credencial_sin_revocacion_previa(self):
        anterior = self.activar()
        nuevo = self.activar()
        self.assertEqual(nuevo.version, 3)
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(anterior.credencial)

    def test_fallo_de_auditoria_revierte_generacion(self):
        with patch("apps.totem.services.OperacionTurno.objects.create", side_effect=RuntimeError("fallo sintetico")):
            with self.assertRaises(RuntimeError):
                self.generar()
        self.assertEqual(self.refrescar().estado_activacion, EstadoActivacion.SIN_CODIGO)
        self.assertEqual(OperacionTurno.objects.count(), 0)

    def test_fallo_de_auditoria_revierte_intento(self):
        generado = self.generar()
        with patch("apps.totem.services.OperacionTurno.objects.create", side_effect=RuntimeError("fallo sintetico")):
            with self.assertRaises(RuntimeError):
                consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, "incorrecto")
        self.assertEqual(self.refrescar().intentos_fallidos, 0)

    def test_fallo_de_firma_revierte_activacion(self):
        generado = self.generar()
        with patch("apps.totem.services._firmar_credencial", side_effect=RuntimeError("fallo sintetico")):
            with self.assertRaises(RuntimeError):
                consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
        d = self.refrescar()
        self.assertFalse(d.activo)
        self.assertEqual((d.estado_activacion, d.version_credencial), (EstadoActivacion.PENDIENTE, 1))
        self.assertFalse(OperacionTurno.objects.filter(accion="TOTEM_ACTIVADO").exists())

    def test_servicios_rechazan_transaccion_exterior(self):
        generado = self.generar()
        llamadas = [
            lambda: self.generar(),
            lambda: consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo),
            lambda: revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad"),
            lambda: caducar_codigo_activacion(self.usuario, self.dispositivo.pk),
        ]
        with transaction.atomic():
            for llamada in llamadas:
                with self.assertRaises(RuntimeError):
                    llamada()

    def test_fallo_de_commit_no_devuelve_codigo_ni_conserva_fila(self):
        # Simula fallo de confirmación real, no un fallo posterior al retorno.
        from django.db import connection, OperationalError
        with patch.object(connection, "commit", side_effect=OperationalError("commit sintetico")):
            with self.assertRaises(OperationalError):
                self.generar()
        self.assertEqual(self.refrescar().estado_activacion, EstadoActivacion.SIN_CODIGO)
        self.assertEqual(OperacionTurno.objects.count(), 0)

    def test_fallo_de_commit_no_devuelve_credencial_y_revierte_consumo(self):
        from django.db import connection, OperationalError
        generado = self.generar()
        with patch.object(connection, "commit", side_effect=OperationalError("commit sintetico")):
            with self.assertRaises(OperationalError):
                consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
        d = self.refrescar()
        self.assertEqual(d.estado_activacion, EstadoActivacion.PENDIENTE)
        self.assertFalse(d.activo)
        self.assertEqual(d.version_credencial, 1)
        self.assertFalse(OperacionTurno.objects.filter(accion="TOTEM_ACTIVADO").exists())

    def test_fallo_auditoria_de_sustitucion_conserva_codigo_anterior(self):
        anterior = self.generar()
        with patch("apps.totem.services.OperacionTurno.objects.create", side_effect=RuntimeError("fallo sintetico")):
            with self.assertRaises(RuntimeError):
                self.generar()
        self.assertEqual(self.refrescar().referencia_activacion, anterior.referencia)
        self.assertEqual(consumir_codigo_activacion(self.dispositivo.pk, anterior.referencia, anterior.codigo).estado, "activado")

    def test_generar_sobre_vencido_audita_caducidad_antes_de_reemplazar(self):
        self.generar()
        vencimiento = self.refrescar().activacion_expira_en
        with patch("apps.totem.services.timezone.now", return_value=vencimiento):
            nuevo = self.generar()
        self.assertEqual(self.refrescar().referencia_activacion, nuevo.referencia)
        self.assertEqual(list(OperacionTurno.objects.order_by("id").values_list("accion", flat=True)), [
            "TOTEM_CODIGO_GENERADO", "TOTEM_CODIGO_CADUCADO", "TOTEM_CODIGO_GENERADO",
        ])

    def test_revocar_con_pendiente_y_activo_cierra_ambos(self):
        anterior = self.activar()
        pendiente = self.generar()
        revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")
        d = self.refrescar()
        self.assertFalse(d.activo)
        self.assertEqual(d.estado_activacion, EstadoActivacion.INVALIDADO)
        self.assertEqual(d.version_credencial, 3)
        self.assertEqual(consumir_codigo_activacion(d.pk, pendiente.referencia, pendiente.codigo).estado, "rechazado")
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(anterior.credencial)

    def test_cada_operacion_administrativa_exige_su_permiso(self):
        otro = get_user_model().objects.create_user(username="sin-permisos-sintetico")
        llamadas = [
            lambda: consultar_dispositivo(otro, self.dispositivo.pk),
            lambda: generar_codigo_activacion(otro, self.dispositivo.pk, "alta"),
            lambda: caducar_codigo_activacion(otro, self.dispositivo.pk),
            lambda: revocar_dispositivo(otro, self.dispositivo.pk, "seguridad"),
        ]
        for llamada in llamadas:
            with self.assertRaises(PermissionDenied):
                llamada()
        self.assertEqual(OperacionTurno.objects.count(), 0)

    def test_auditoria_no_expone_secretos_ni_publica_websocket(self):
        with patch("apps.turnos.notificaciones.publicar") as publicar:
            generado = self.generar()
            hash_codigo = self.refrescar().hash_activacion
            activado = consumir_codigo_activacion(self.dispositivo.pk, generado.referencia, generado.codigo)
            revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")
        publicar.assert_not_called()
        texto = json.dumps(list(OperacionTurno.objects.values("accion", "detalles")))
        for secreto in (generado.codigo, hash_codigo, activado.credencial):
            self.assertNotIn(secreto, texto)
        for evento in OperacionTurno.objects.all():
            self.assertIsNone(evento.turno_id)
            self.assertLessEqual(len(evento.accion), 30)
            self.assertEqual(evento.usuario_id, None if evento.accion == "TOTEM_ACTIVADO" else self.usuario.pk)

    def test_permiso_fresco_no_acepta_cache_anterior(self):
        self.assertTrue(self.usuario.has_perm("totem.generar_codigos_activacion"))
        self.usuario.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            self.generar()

    def test_usuario_inactivo_o_sin_permiso_no_opera(self):
        otro = get_user_model().objects.create_user(username="otro-sintetico")
        for usuario in (None, otro):
            with self.assertRaises(PermissionDenied):
                generar_codigo_activacion(usuario, self.dispositivo.pk, "alta")
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.generar()

    def test_motivo_libre_es_rechazado_sin_auditar(self):
        with self.assertRaises(ValidationError):
            generar_codigo_activacion(self.usuario, self.dispositivo.pk, "texto no permitido")
        self.assertEqual(OperacionTurno.objects.count(), 0)

    def test_entradas_invalidas_y_desconocidas_no_mutan(self):
        self.generar()
        self.refrescar()
        for identificador, referencia, codigo in (
            ("invalido", uuid.uuid4(), "sintetico"),
            (uuid.uuid4(), uuid.uuid4(), "sintetico"),
            (self.dispositivo.pk, uuid.uuid4(), "sintetico"),
            (self.dispositivo.pk, self.dispositivo.referencia_activacion, "x" * 129),
        ):
            self.assertEqual(consumir_codigo_activacion(identificador, referencia, codigo).estado, "rechazado")
        self.assertEqual(self.refrescar().intentos_fallidos, 0)

    def test_consulta_no_expone_hash_o_modelo(self):
        generado = self.generar()
        consulta = consultar_dispositivo(self.usuario, self.dispositivo.pk)
        self.assertNotIn("hash_activacion", consulta)
        self.assertNotIn(generado.codigo, json.dumps(consulta))

    def test_reloj_retrocedido_no_repara_historia(self):
        self.generar()
        anterior = self.refrescar().actualizado_en - timedelta(seconds=1)
        with patch("apps.totem.services.timezone.now", return_value=anterior):
            with self.assertRaises(ValidationError):
                self.generar()

    def test_hash_externo_no_reconocido_requiere_revision(self):
        self.generar()
        type(self.dispositivo).objects.filter(pk=self.dispositivo.pk).update(hash_activacion="hash-sintetico-no-utilizable")
        with self.assertRaises(ValidationError):
            revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")

    def activar_en_version_maxima(self):
        self.dispositivo.version_credencial = 2147483646
        self.dispositivo.save(update_fields=["version_credencial"])
        resultado = self.activar()
        self.assertEqual(resultado.version, 2147483647)
        return resultado

    def preparar_pendiente_en_version_maxima(self, activo):
        # Estado sintético válido, posible con códigos generados por código previo.
        pendiente = self.generar()
        dispositivo = self.refrescar()
        dispositivo.version_credencial = 2147483647
        dispositivo.activo = activo
        if activo:
            dispositivo.activado_en = timezone.now()
        dispositivo.save()
        return pendiente

    def test_revocar_version_maxima_desactiva_y_rechaza_credencial(self):
        activado = self.activar_en_version_maxima()
        self.assertEqual(validar_credencial_dispositivo(activado.credencial).version, 2147483647)

        resultado = revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")

        dispositivo = self.refrescar()
        self.assertEqual((resultado.estado, resultado.version), ("revocado", 2147483647))
        self.assertFalse(dispositivo.activo)
        self.assertEqual(dispositivo.version_credencial, 2147483647)
        with self.assertRaises(PermissionDenied):
            validar_credencial_dispositivo(activado.credencial)
        evento = OperacionTurno.objects.get(accion="TOTEM_REVOCADO")
        self.assertEqual(evento.usuario_id, self.usuario.pk)
        self.assertTrue(evento.detalles["anteriores"]["activo"])
        self.assertFalse(evento.detalles["nuevos"]["activo"])
        self.assertEqual(evento.detalles["anteriores"]["version"], 2147483647)
        self.assertEqual(evento.detalles["nuevos"]["version"], 2147483647)

    def test_revocar_version_maxima_cierra_pendiente_y_activo(self):
        pendiente = self.preparar_pendiente_en_version_maxima(activo=True)

        revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")

        dispositivo = self.refrescar()
        self.assertFalse(dispositivo.activo)
        self.assertEqual(dispositivo.version_credencial, 2147483647)
        self.assertEqual(dispositivo.estado_activacion, EstadoActivacion.INVALIDADO)
        self.assertEqual(dispositivo.hash_activacion, "")
        self.assertIsNotNone(dispositivo.activacion_cerrada_en)
        self.assertEqual(list(OperacionTurno.objects.order_by("id").values_list("accion", flat=True)), [
            "TOTEM_CODIGO_GENERADO", "TOTEM_CODIGO_INVALIDADO", "TOTEM_REVOCADO",
        ])
        resultado = consumir_codigo_activacion(dispositivo.pk, pendiente.referencia, pendiente.codigo)
        self.assertEqual(resultado.estado, "rechazado")
        self.assertIsNone(resultado.credencial)

    def test_revocar_version_maxima_cierra_pendiente_inactivo(self):
        self.preparar_pendiente_en_version_maxima(activo=False)

        resultado = revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")

        dispositivo = self.refrescar()
        self.assertEqual(resultado.estado, "revocado")
        self.assertFalse(dispositivo.activo)
        self.assertEqual(dispositivo.version_credencial, 2147483647)
        self.assertEqual(dispositivo.estado_activacion, EstadoActivacion.INVALIDADO)
        self.assertEqual(dispositivo.hash_activacion, "")
        self.assertIsNotNone(dispositivo.activacion_cerrada_en)

    def test_revocar_version_maxima_es_idempotente(self):
        self.preparar_pendiente_en_version_maxima(activo=True)
        revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")
        anterior = type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk)
        eventos = OperacionTurno.objects.count()

        resultado = revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")

        self.assertEqual((resultado.estado, resultado.version), ("sin_cambios", 2147483647))
        self.assertEqual(type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk), anterior)
        self.assertEqual(OperacionTurno.objects.count(), eventos)

    def test_version_maxima_impide_generar_codigo_antes_y_despues_de_revocar(self):
        self.activar_en_version_maxima()
        for revocado in (False, True):
            with self.subTest(revocado=revocado):
                if revocado:
                    revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")
                anterior = type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk)
                eventos = OperacionTurno.objects.count()
                with patch("apps.totem.services.secrets.token_urlsafe") as generar:
                    with self.assertRaises(ValidationError):
                        self.generar()
                generar.assert_not_called()
                self.assertEqual(type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk), anterior)
                self.assertEqual(OperacionTurno.objects.count(), eventos)

    def test_version_maxima_rechaza_consumir_codigo_preexistente_sin_reactivar(self):
        pendiente = self.preparar_pendiente_en_version_maxima(activo=False)
        anterior = type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk)
        eventos = OperacionTurno.objects.count()

        with patch("apps.totem.services._firmar_credencial") as firmar:
            resultado = consumir_codigo_activacion(self.dispositivo.pk, pendiente.referencia, pendiente.codigo)

        self.assertEqual(resultado.estado, "rechazado")
        self.assertIsNone(resultado.credencial)
        firmar.assert_not_called()
        self.assertEqual(type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk), anterior)
        self.assertEqual(OperacionTurno.objects.count(), eventos)

    def test_fallo_auditoria_revocacion_maxima_conserva_activo_y_credencial(self):
        activado = self.activar_en_version_maxima()
        anterior = type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk)
        eventos = OperacionTurno.objects.count()

        with patch("apps.totem.services.OperacionTurno.objects.create", side_effect=RuntimeError("fallo sintetico")):
            with self.assertRaises(RuntimeError):
                revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")

        self.assertEqual(type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk), anterior)
        self.assertEqual(OperacionTurno.objects.count(), eventos)
        self.assertEqual(validar_credencial_dispositivo(activado.credencial).version, 2147483647)

    def test_fallo_auditoria_final_revocacion_maxima_revierte_cierre_pendiente(self):
        pendiente = self.preparar_pendiente_en_version_maxima(activo=True)
        anterior = type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk)
        eventos = OperacionTurno.objects.count()
        crear = OperacionTurno.objects.create

        def fallar_revocacion(*args, **kwargs):
            if kwargs.get("accion") == "TOTEM_REVOCADO":
                raise RuntimeError("fallo sintetico")
            return crear(*args, **kwargs)

        with patch("apps.totem.services.OperacionTurno.objects.create", side_effect=fallar_revocacion) as auditar:
            with self.assertRaises(RuntimeError):
                revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")

        self.assertEqual([llamada.kwargs["accion"] for llamada in auditar.call_args_list], [
            "TOTEM_CODIGO_INVALIDADO", "TOTEM_REVOCADO",
        ])
        self.assertEqual(type(self.dispositivo).objects.values().get(pk=self.dispositivo.pk), anterior)
        self.assertEqual(OperacionTurno.objects.count(), eventos)
        dispositivo = self.refrescar()
        self.assertTrue(dispositivo.activo)
        self.assertEqual(dispositivo.estado_activacion, EstadoActivacion.PENDIENTE)
        self.assertEqual(dispositivo.referencia_activacion, pendiente.referencia)
        self.assertTrue(check_password(pendiente.codigo, dispositivo.hash_activacion))

    def test_revocar_penultima_version_incrementa_hasta_maximo(self):
        self.activar()
        self.dispositivo.version_credencial = 2147483646
        self.dispositivo.save(update_fields=["version_credencial"])

        resultado = revocar_dispositivo(self.usuario, self.dispositivo.pk, "seguridad")

        self.assertEqual((resultado.estado, resultado.version), ("revocado", 2147483647))
        self.assertFalse(self.refrescar().activo)
        self.assertEqual(self.dispositivo.version_credencial, 2147483647)
