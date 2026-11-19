"""Correo para avisos en el padrón (enmienda del 03, 2026-11-18; RF-03-12 a RF-03-15).

Todos los correos son sintéticos (`example.invalid`), nunca de personas reales.
"""

import io
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from coreapp.models import RegistroAuditoria
from recetasapp.importacion import ENCABEZADOS_CON_CORREO, generar_archivo, importar_padron
from recetasapp.models import Paciente, ResultadoFilaImportacion, normalizar_correo
from recetasapp.services import CorreoCambiado, actualizar_correo_avisos
from .ayudas import actores, cargar, fila


def con_correo(correo, codigo="DEMO-0001", rut=None):
    datos = fila(codigo)
    if rut:
        datos[0] = rut
    return datos + [correo]


def cargar13(actor, filas, formato="csv"):
    contenido = generar_archivo(formato, filas, encabezados=ENCABEZADOS_CON_CORREO)
    return importar_padron(actor, io.BytesIO(contenido), formato)


class ConReloj:
    def setUp(self):
        reloj = patch("recetasapp.services.timezone.localdate", return_value=date(2026, 11, 2))
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()


class ModeloCorreoTests(TestCase):
    def test_normaliza_espacios_y_dominio(self):
        self.assertEqual(normalizar_correo("  Ana.Cuidadora@EXAMPLE.Invalid "), "Ana.Cuidadora@example.invalid")
        self.assertEqual(normalizar_correo(""), "")
        self.assertEqual(normalizar_correo(None), "")


class ImportacionCorreoTests(ConReloj, TestCase):
    def setUp(self):
        super().setUp()
        self.qf = actores()["qf"]

    def paciente(self):
        return Paciente.objects.get()

    def test_doce_y_trece_columnas_en_ambos_formatos(self):
        for formato, rut, codigo in (("csv", "11111111-1", "CSV-1"), ("xlsx", "22222222-2", "XLSX-1")):
            with self.subTest(formato=formato):
                filas = [con_correo(" Cuidadora@EXAMPLE.INVALID ", codigo, rut)]
                carga = cargar13(self.qf, filas, formato)
                self.assertEqual(carga.estado, "completada", carga.resumen_fallo)
                self.assertEqual(carga.filas_rechazadas, 0)
                paciente = Paciente.objects.get(rut=rut)
                self.assertEqual(paciente.correo_avisos, "Cuidadora@example.invalid")
                # Un archivo de doce columnas conserva el correo guardado.
                carga = cargar(self.qf, [filas[0][:-1]], formato)
                self.assertEqual(carga.filas_rechazadas, 0)
                paciente.refresh_from_db()
                self.assertEqual(paciente.correo_avisos, "Cuidadora@example.invalid")

    def test_celda_vacia_conserva_y_correo_presente_reemplaza(self):
        cargar13(self.qf, [con_correo("primero@example.invalid")])
        cargar13(self.qf, [con_correo("")])
        self.assertEqual(self.paciente().correo_avisos, "primero@example.invalid")
        carga = cargar13(self.qf, [con_correo("segundo@example.invalid")])
        self.assertEqual(carga.pacientes_actualizados, 1)
        self.assertEqual(self.paciente().correo_avisos, "segundo@example.invalid")

    def test_excel_con_ultima_celda_vacia_conserva(self):
        cargar13(self.qf, [con_correo("primero@example.invalid")], "xlsx")
        carga = cargar13(self.qf, [fila()], "xlsx")  # fila de doce celdas bajo un encabezado de trece
        self.assertEqual(carga.filas_rechazadas, 0, carga.resumen_fallo)
        self.assertEqual(self.paciente().correo_avisos, "primero@example.invalid")

    def test_correo_invalido_rechaza_solo_su_fila(self):
        otra = fila("DEMO-0002")
        otra[0] = "11111111-1"
        carga = cargar13(self.qf, [con_correo("no-es-correo"), otra + [""]])
        self.assertEqual((carga.filas_creadas, carga.filas_rechazadas), (1, 1))
        rechazo = ResultadoFilaImportacion.objects.get(importacion=carga, estado="rechazada")
        self.assertEqual((rechazo.codigo_motivo, rechazo.mensaje), ("correo_invalido", "El correo no es válido."))
        self.assertNotIn("no-es-correo", rechazo.mensaje)
        self.assertFalse(Paciente.objects.filter(rut=fila()[0]).exists())

    def test_encabezado_de_trece_con_otro_nombre_rechaza_el_archivo(self):
        encabezados = ENCABEZADOS_CON_CORREO[:-1] + ("email",)
        contenido = generar_archivo("csv", [con_correo("a@example.invalid")], encabezados=encabezados)
        carga = importar_padron(self.qf, io.BytesIO(contenido), "csv")
        self.assertEqual(carga.estado, "fallida")
        self.assertFalse(Paciente.objects.exists())

    def test_correos_distintos_del_mismo_rut_se_contradicen(self):
        uno, otro = con_correo("uno@example.invalid"), con_correo("otro@example.invalid")
        carga = cargar13(self.qf, [uno, otro])
        self.assertEqual(carga.filas_rechazadas, 2)
        self.assertFalse(Paciente.objects.exists())

    def test_correo_y_celda_vacia_del_mismo_rut_no_se_contradicen(self):
        for rut, codigo, primero_vacio in (("11111111-1", "A-1", False), ("22222222-2", "B-1", True)):
            filas = [con_correo("uno@example.invalid", codigo, rut), con_correo("", codigo, rut)]
            if primero_vacio:
                filas.reverse()
            carga = cargar13(self.qf, filas)
            self.assertEqual(carga.filas_rechazadas, 0)
            self.assertEqual(Paciente.objects.get(rut=rut).correo_avisos, "uno@example.invalid")

    def test_dos_pacientes_pueden_compartir_correo(self):
        otra = fila("DEMO-0002")
        otra[0] = "11111111-1"
        carga = cargar13(self.qf, [con_correo("cuidadora@example.invalid"), otra + ["cuidadora@example.invalid"]])
        self.assertEqual(carga.filas_creadas, 2)
        self.assertEqual(Paciente.objects.filter(correo_avisos="cuidadora@example.invalid").count(), 2)

    def test_auditoria_y_reporte_no_copian_correos(self):
        cargar13(self.qf, [con_correo("visible@example.invalid"), con_correo("otro-invalido")])
        volcado = str(list(RegistroAuditoria.objects.values())) + str(list(ResultadoFilaImportacion.objects.values()))
        self.assertNotIn("visible@example.invalid", volcado)
        self.assertNotIn("otro-invalido", volcado)


class EdicionCorreoTests(ConReloj, TestCase):
    def setUp(self):
        super().setUp()
        self.actores = actores()
        cargar(self.actores["qf"], [fila()])
        self.paciente = Paciente.objects.get()
        self.url = reverse("recetasapp:correo_avisos", args=[self.paciente.pk])
        self.ficha = reverse("recetasapp:paciente_detalle", args=[self.paciente.pk]) + "?pestana=datos"

    def guardar(self, correo, leido="", usuario=None):
        self.client.force_login(usuario or self.actores["qf"])
        return self.client.post(self.url, {"correo": correo, "leido": leido}, follow=True)

    def test_qf_guarda_corrige_y_borra_con_auditoria_sin_el_correo(self):
        respuesta = self.guardar("Cuidadora@EXAMPLE.invalid")
        self.assertContains(respuesta, "Correo para avisos guardado.")
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.correo_avisos, "Cuidadora@example.invalid")
        self.assertContains(self.guardar("nuevo@example.invalid", "Cuidadora@example.invalid"), "Correo para avisos guardado.")
        self.assertContains(self.guardar("", "nuevo@example.invalid"), "Correo para avisos borrado.")
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.correo_avisos, "")
        registros = RegistroAuditoria.objects.filter(accion="paciente.correo_actualizado")
        self.assertEqual(registros.count(), 3)
        self.assertNotIn("example.invalid", str(list(registros.values())))

    def test_ficha_muestra_el_dato_y_solo_la_qf_ve_el_formulario(self):
        Paciente.objects.filter(pk=self.paciente.pk).update(correo_avisos="visible@example.invalid")
        self.client.force_login(self.actores["qf"])
        respuesta = self.client.get(self.ficha)
        self.assertContains(respuesta, "visible@example.invalid")
        self.assertContains(respuesta, self.url)
        self.assertContains(respuesta, 'for="id_correo"')
        self.client.force_login(self.actores["tecnico"])
        respuesta = self.client.get(self.ficha)
        self.assertContains(respuesta, "visible@example.invalid")
        self.assertNotContains(respuesta, self.url)

    def test_tecnico_recibe_403_y_get_no_esta_permitido(self):
        self.client.force_login(self.actores["tecnico"])
        self.assertEqual(self.client.post(self.url, {"correo": "x@example.invalid", "leido": ""}).status_code, 403)
        self.client.force_login(self.actores["qf"])
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.correo_avisos, "")

    def test_sin_csrf_no_hay_cambios(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.actores["qf"])
        self.assertEqual(cliente.post(self.url, {"correo": "x@example.invalid", "leido": ""}).status_code, 403)
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.correo_avisos, "")

    def test_correo_invalido_muestra_error_junto_al_campo(self):
        self.client.force_login(self.actores["qf"])
        respuesta = self.client.post(self.url, {"correo": "no-es-correo", "leido": ""})
        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "campo-error", status_code=400)
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.correo_avisos, "")

    def test_valor_cambiado_no_se_sobrescribe(self):
        Paciente.objects.filter(pk=self.paciente.pk).update(correo_avisos="importado@example.invalid")
        respuesta = self.guardar("mio@example.invalid", leido="")
        self.assertContains(respuesta, "El correo cambió mientras lo editabas. Revisa el valor actual.")
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.correo_avisos, "importado@example.invalid")

    def test_servicio_exige_qf_y_revierte_si_falla_la_auditoria(self):
        with self.assertRaises(PermissionDenied):
            actualizar_correo_avisos(self.actores["tecnico"], self.paciente.pk, "x@example.invalid", "")
        with self.assertRaises(ValidationError):
            actualizar_correo_avisos(self.actores["qf"], self.paciente.pk, "no-es-correo", "")
        with patch("recetasapp.services.registrar_accion", side_effect=ValidationError("falla")):
            with self.assertRaises(RuntimeError):
                actualizar_correo_avisos(self.actores["qf"], self.paciente.pk, "x@example.invalid", "")
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.correo_avisos, "")
        self.assertIsNone(actualizar_correo_avisos(self.actores["qf"], self.paciente.pk, "", ""))
        self.assertEqual(actualizar_correo_avisos(self.actores["admin"], self.paciente.pk, "a@example.invalid", ""), "guardado")

    def test_vistas_publicas_no_muestran_el_correo(self):
        Paciente.objects.filter(pk=self.paciente.pk).update(correo_avisos="secreto@example.invalid")
        self.client.logout()
        for nombre in ("turnosapp:totem", "turnosapp:sala"):
            respuesta = self.client.get(reverse(nombre))
            self.assertNotContains(respuesta, "secreto@example.invalid")


class CorreoConcurrenteTests(ConReloj, TransactionTestCase):
    """RF-03-15 con hilos: un solo ganador cuando dos cambios parten del mismo valor leído."""

    def setUp(self):
        super().setUp()
        self.actores = actores()
        cargar(self.actores["qf"], [fila()])
        self.paciente = Paciente.objects.get()

    def en_paralelo(self, *funciones):
        barrera = Barrier(len(funciones))

        def correr(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return funcion()
            except CorreoCambiado:
                return "conflicto"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(funciones)) as hilos:
            return [futuro.result(timeout=30) for futuro in [hilos.submit(correr, f) for f in funciones]]

    def test_dos_ediciones_desde_el_mismo_valor(self):
        qf, admin = self.actores["qf"], self.actores["admin"]
        resultados = self.en_paralelo(
            lambda: actualizar_correo_avisos(qf, self.paciente.pk, "uno@example.invalid", ""),
            lambda: actualizar_correo_avisos(admin, self.paciente.pk, "dos@example.invalid", ""),
        )
        self.assertCountEqual(resultados, ["guardado", "conflicto"])
        self.paciente.refresh_from_db()
        self.assertIn(self.paciente.correo_avisos, ("uno@example.invalid", "dos@example.invalid"))
        self.assertEqual(RegistroAuditoria.objects.filter(accion="paciente.correo_actualizado").count(), 1)

    def test_edicion_simultanea_con_una_importacion(self):
        qf = self.actores["qf"]
        resultados = self.en_paralelo(
            lambda: actualizar_correo_avisos(qf, self.paciente.pk, "ficha@example.invalid", ""),
            lambda: cargar13(qf, [con_correo("archivo@example.invalid")]).estado,
        )
        self.paciente.refresh_from_db()
        if "conflicto" in resultados:
            self.assertEqual(self.paciente.correo_avisos, "archivo@example.invalid")
        else:
            # La edición ganó primero y la importación, que no compara el correo leído, lo reemplazó después.
            self.assertIn(self.paciente.correo_avisos, ("ficha@example.invalid", "archivo@example.invalid"))
        self.assertIn("completada", resultados)

    def test_tres_ediciones_concurrentes(self):
        qf = self.actores["qf"]
        resultados = self.en_paralelo(*[
            (lambda n=n: actualizar_correo_avisos(qf, self.paciente.pk, f"c{n}@example.invalid", ""))
            for n in range(3)
        ])
        self.assertEqual(resultados.count("guardado"), 1)
        self.assertEqual(resultados.count("conflicto"), 2)


class MigracionCorreoTests(TransactionTestCase):
    def test_migrar_desde_0004_y_volver(self):
        anterior = [("recetasapp", "0004_preparacionreceta")]
        executor = MigrationExecutor(connection)
        actual = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(anterior)
            columnas = [c.name for c in connection.introspection.get_table_description(
                connection.cursor(), Paciente._meta.db_table,
            )]
            self.assertNotIn("correo_avisos", columnas)
            MigrationExecutor(connection).migrate(actual)
            columnas = [c.name for c in connection.introspection.get_table_description(
                connection.cursor(), Paciente._meta.db_table,
            )]
            self.assertIn("correo_avisos", columnas)
        finally:
            MigrationExecutor(connection).migrate(actual)
