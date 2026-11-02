"""Integridad del padrón sintético y migración desde la base anterior."""

import uuid
from datetime import date, timedelta
from random import Random
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import (
    EntregaReceta, ImportacionPadron, Paciente, Receta, ResultadoFilaImportacion,
)
from usuariosapp.models import Perfil


class ModelosTests(TestCase):
    def setUp(self):
        self.ruts = generar_ruts(3, Random(3))
        self.paciente = Paciente.objects.create(
            rut=self.ruts[0], nombres="Paciente sintético", apellidos="Demostración",
            fecha_nacimiento=date(1950, 6, 15),
        )
        self.receta = Receta.objects.create(
            paciente=self.paciente, codigo="DEMO-001", fecha_inicio=date(2026, 1, 1),
            fecha_fin_exclusiva=date(2026, 7, 1), vigencia_meses=6, max_entregas=6,
        )

    def carga(self):
        return ImportacionPadron.objects.create(archivo_sha256="a" * 64, formato="csv")

    def test_rut_se_normaliza_y_no_admite_identidad_duplicada(self):
        cuerpo, dv = self.ruts[0].split("-")
        formato = f"{int(cuerpo):,}-{dv}".replace(",", ".")
        otro = Paciente(rut=formato, nombres="Sintético", apellidos="Duplicado", fecha_nacimiento=date(1960, 1, 1))
        with self.assertRaises(IntegrityError), transaction.atomic():
            otro.save()
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.rut, self.ruts[0])

    def test_rechaza_dv_invalido_sin_repetir_dato(self):
        self.paciente.rut = "dato-invalido"
        with self.assertRaises(ValidationError) as error:
            self.paciente.full_clean()
        self.assertNotIn("dato-invalido", str(error.exception))

    def test_rechaza_nacimiento_futuro_y_nombres_vacios(self):
        self.paciente.fecha_nacimiento = timezone.localdate() + timedelta(days=1)
        self.paciente.nombres = "   "
        with self.assertRaises(ValidationError) as error:
            self.paciente.full_clean()
        self.assertIn("fecha_nacimiento", error.exception.message_dict)
        self.assertIn("nombres", error.exception.message_dict)

    def test_edad_se_calcula_antes_y_despues_del_cumpleanos(self):
        for hoy, esperado in [(date(2026, 6, 14), 75), (date(2026, 6, 15), 76)]:
            with self.subTest(hoy=hoy), patch("recetasapp.models.timezone.localdate", return_value=hoy):
                self.assertEqual(self.paciente.edad, esperado)
        self.assertNotIn("edad", [f.name for f in Paciente._meta.fields])

    def test_indicadores_son_independientes_y_contacto_opcional(self):
        self.paciente.es_postrado = True
        self.paciente.full_clean()
        self.paciente.save()
        self.assertFalse(self.paciente.es_cronico)
        self.assertEqual(self.paciente.telefono, "")
        self.assertEqual(self.paciente.direccion, "")

    def test_base_rechaza_contadores_vigencia_y_fechas_invalidos(self):
        cambios = [
            {"max_entregas": 0}, {"vigencia_meses": 0},
            {"entregas_completadas": 7}, {"entregas_completadas": -1},
            {"fecha_fin_exclusiva": date(2026, 1, 1)},
            {"receta_anterior_id": self.receta.pk},
        ]
        for cambio in cambios:
            with self.subTest(cambio=cambio):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Receta.objects.filter(pk=self.receta.pk).update(**cambio)

    def test_codigo_es_unico_y_no_se_acepta_vacio(self):
        self.receta.codigo = "   "
        with self.assertRaises(ValidationError):
            self.receta.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Receta.objects.create(
                paciente=self.paciente, codigo="DEMO-001", fecha_inicio=date(2026, 1, 1),
                fecha_fin_exclusiva=date(2026, 2, 1), vigencia_meses=1, max_entregas=1,
            )

    def test_renovacion_debe_ser_del_mismo_paciente(self):
        otro = Paciente.objects.create(rut=self.ruts[1], nombres="Otro", apellidos="Sintético", fecha_nacimiento=date(1960, 1, 1))
        nueva = Receta(
            paciente=otro, codigo="DEMO-002", fecha_inicio=date(2026, 7, 1),
            fecha_fin_exclusiva=date(2027, 1, 1), vigencia_meses=6, max_entregas=6,
            receta_anterior=self.receta,
        )
        with self.assertRaises(ValidationError):
            nueva.full_clean()
        nueva.paciente = self.paciente
        nueva.full_clean()
        nueva.save()
        self.assertEqual(nueva.entregas_completadas, 0)
        with self.assertRaises(ProtectedError):
            self.receta.delete()

    def test_entrega_exige_ordinal_y_operacion_unicos(self):
        operacion = uuid.uuid4()
        EntregaReceta.objects.create(receta=self.receta, numero=1, operacion_id=operacion)
        for numero, identificador in [(1, uuid.uuid4()), (2, operacion), (0, uuid.uuid4())]:
            with self.subTest(numero=numero):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    EntregaReceta.objects.create(receta=self.receta, numero=numero, operacion_id=identificador)

    def test_historial_protege_paciente_receta_y_carga(self):
        with self.assertRaises(ProtectedError):
            self.paciente.delete()
        EntregaReceta.objects.create(receta=self.receta, numero=1)
        with self.assertRaises(ProtectedError):
            self.receta.delete()
        carga = self.carga()
        ResultadoFilaImportacion.objects.create(importacion=carga, numero_fila=2, estado="creada", paciente=self.paciente, receta=self.receta)
        with self.assertRaises(ProtectedError):
            carga.delete()

    def test_fila_es_unica_y_no_admite_encabezado_como_dato(self):
        carga = self.carga()
        ResultadoFilaImportacion.objects.create(importacion=carga, numero_fila=2, estado="rechazada")
        for numero in (1, 2):
            with self.assertRaises(IntegrityError), transaction.atomic():
                ResultadoFilaImportacion.objects.create(importacion=carga, numero_fila=numero, estado="omitida")

    def test_fila_no_relaciona_receta_con_otro_paciente(self):
        fila = ResultadoFilaImportacion(importacion=self.carga(), numero_fila=2, estado="creada", receta=self.receta)
        with self.assertRaises(ValidationError):
            fila.full_clean()

    def test_base_rechaza_estados_y_formatos_desconocidos(self):
        carga = self.carga()
        for cambio in ({"formato": "xls"}, {"estado": "inventado"}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                ImportacionPadron.objects.filter(pk=carga.pk).update(**cambio)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ResultadoFilaImportacion.objects.create(importacion=carga, numero_fila=2, estado="inventado")

    def test_referencias_de_texto_no_exponen_datos_del_paciente(self):
        self.assertNotIn(self.paciente.rut, str(self.paciente))
        self.assertNotIn(self.paciente.nombres, str(self.paciente))
        self.assertNotIn(self.receta.codigo, str(self.receta))
        campos = {f.name for f in ResultadoFilaImportacion._meta.fields}
        self.assertFalse({"rut", "nombres", "contenido", "archivo"} & campos)


class MigracionInicialTests(TransactionTestCase):
    def test_actualiza_base_anterior_sin_perder_cuentas_grupos_o_auditoria(self):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        anteriores = [nodo for nodo in finales if nodo[0] != "recetasapp"] + [("recetasapp", None)]
        try:
            executor.migrate(anteriores)
            usuario = get_user_model().objects.create_user(username="migracion_sintetica")
            perfil = Perfil.objects.create(usuario=usuario)
            clave_previa = usuario.password
            grupo = Group.objects.create(name="Grupo sintético de migración")
            usuario.groups.add(grupo)
            registro = RegistroAuditoria.objects.create(usuario=usuario, accion="prueba.migracion", objeto_tipo="auth.User", objeto_id=str(usuario.pk))
            identificador = usuario.pk
            MigrationExecutor(connection).migrate(finales)
            self.assertTrue(get_user_model().objects.filter(pk=identificador, groups=grupo).exists())
            self.assertEqual(get_user_model().objects.get(pk=identificador).password, clave_previa)
            self.assertTrue(Perfil.objects.filter(pk=perfil.pk, usuario_id=identificador).exists())
            self.assertTrue(RegistroAuditoria.objects.filter(pk=registro.pk, usuario_id=identificador).exists())
            self.assertEqual(Paciente.objects.count(), 0)
            self.assertEqual(Receta.objects.count(), 0)
            self.assertEqual(ImportacionPadron.objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(finales)
