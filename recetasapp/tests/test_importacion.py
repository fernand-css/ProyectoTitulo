"""Importación parcial y repetible de datos exclusivamente sintéticos."""

import io
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from coreapp.models import RegistroAuditoria
from recetasapp.importacion import ENCABEZADOS, MAX_BYTES, filas_demo, generar_archivo, importar_padron
from recetasapp.models import Paciente, Receta
from .ayudas import actores, cargar, fila


class ImportacionTests(TestCase):
    def setUp(self):
        reloj = patch("recetasapp.services.timezone.localdate", return_value=date(2026, 11, 2))
        reloj.start()
        self.addCleanup(reloj.stop)
        self.actores = actores()
        self.qf = self.actores["qf"]

    def test_carga_670_en_ambos_formatos_y_repite_sin_duplicacion(self):
        for formato in ("csv", "xlsx"):
            with self.subTest(formato=formato):
                carga = cargar(self.qf, list(filas_demo()), formato)
                self.assertEqual(carga.estado, "completada", carga.resumen_fallo)
                self.assertEqual(carga.filas_rechazadas, 0)
                self.assertEqual(Paciente.objects.count(), 670)
                self.assertEqual(Receta.objects.count(), 670)
                repetida = cargar(self.qf, list(filas_demo()), formato)
                self.assertEqual(repetida.filas_sin_cambios, 670)
                self.assertEqual(repetida.pacientes_creados, 0)
        self.assertEqual(sum(Receta.objects.values_list("entregas_completadas", flat=True)), 0)

    def test_mixta_rechaza_datos_sin_detener_validas(self):
        malas = []
        for indice, valor in [(0, "invalido"), (3, "2999-01-01"), (4, "si"), (10, "1.5"), (11, "0")]:
            copia = fila()
            copia[indice] = valor
            carga = cargar(self.qf, [copia])
            self.assertEqual(carga.filas_rechazadas, 1)
            malas.append(carga)
        carga = cargar(self.qf, [fila(), ["faltan columnas"]])
        self.assertEqual((carga.filas_creadas, carga.filas_rechazadas), (1, 1))

    def test_duplicados_identicos_y_contradictorios_sin_depender_del_orden(self):
        base = fila()
        carga = cargar(self.qf, [base, base])
        self.assertEqual((carga.filas_creadas, carga.filas_omitidas), (1, 1))
        contradictoria = list(base)
        contradictoria[1] = "Nombre sintético contradictorio"
        for filas in ([base, contradictoria], [contradictoria, base]):
            carga = cargar(self.qf, filas)
            self.assertEqual(carga.filas_rechazadas, 2)
            self.assertEqual(Paciente.objects.get().nombres, base[1])

    def test_varias_recetas_por_paciente_y_fila_sin_receta(self):
        base, segunda = fila(), fila("OTRA")
        solo_padron = list(base[:8]) + ["", "", "", ""]
        carga = cargar(self.qf, [base, segunda, solo_padron])
        self.assertEqual(carga.filas_rechazadas, 0)
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(Receta.objects.count(), 2)

    def test_actualiza_paciente_y_receta_sin_entregas(self):
        cargar(self.qf, [fila()])
        nueva = fila()
        nueva[7], nueva[11] = "Otro sector sintético", "6"
        carga = cargar(self.qf, [nueva])
        self.assertEqual(carga.pacientes_actualizados, 1)
        self.assertEqual(carga.recetas_actualizadas, 1)
        self.assertEqual(Receta.objects.get().max_entregas, 6)

    def test_historial_protegido_y_fila_atomica(self):
        import uuid
        from recetasapp.services import registrar_entrega
        cargar(self.qf, [fila()])
        receta = Receta.objects.get()
        registrar_entrega(self.actores["tecnico"], receta.pk, uuid.uuid4())
        nueva = fila()
        nueva[7], nueva[11] = "Cambio que debe revertirse", "6"
        carga = cargar(self.qf, [nueva])
        self.assertEqual(carga.filas_rechazadas, 1)
        self.assertEqual(Paciente.objects.get().direccion, fila()[7])
        receta.refresh_from_db()
        self.assertEqual(receta.max_entregas, 12)
        self.assertEqual(receta.entregas_completadas, 1)
        self.assertEqual(receta.entregas.count(), 1)

    def test_codigo_no_pasa_a_otro_paciente(self):
        cargar(self.qf, [fila()])
        otra = list(filas_demo(cantidad=2))[1]
        otra[8] = fila()[8]
        carga = cargar(self.qf, [otra])
        self.assertEqual(carga.filas_rechazadas, 1)
        self.assertEqual(Paciente.objects.count(), 1)

    def test_errores_estructurales_no_cambian_dominio(self):
        for contenido, formato in [(b"rut,nombres\nabc,def", "csv"), (b"\xff", "csv"), (b"no es excel", "xlsx"), (b"a" * (MAX_BYTES + 1), "csv"), (generar_archivo("csv"), "csv")]:
            with self.subTest(formato=formato):
                carga = importar_padron(self.qf, io.BytesIO(contenido), formato)
                self.assertEqual(carga.estado, "fallida")
                self.assertEqual(Paciente.objects.count(), 0)

    def test_excel_formulas_no_se_evalua_y_hoja_incorrecta_se_rechaza(self):
        from openpyxl import Workbook
        libro = Workbook()
        hoja = libro.active
        hoja.title = "padron"
        hoja.append(ENCABEZADOS)
        datos = fila()
        datos[1] = '=HYPERLINK("https://example.invalid")'
        hoja.append(datos)
        hoja.append(fila("VALIDA"))
        salida = io.BytesIO()
        libro.save(salida)
        carga = importar_padron(self.qf, io.BytesIO(salida.getvalue()), "xlsx")
        self.assertEqual((carga.filas_creadas, carga.filas_rechazadas), (1, 1))
        hoja.title = "otra"
        salida = io.BytesIO()
        libro.save(salida)
        carga = importar_padron(self.qf, io.BytesIO(salida.getvalue()), "xlsx")
        self.assertEqual(carga.estado, "fallida")

    def test_fallo_auditoria_interrumpe_y_no_lo_trata_como_fila_invalida(self):
        with patch("recetasapp.services.registrar_accion", side_effect=RuntimeError("NO DEBE COPIARSE")):
            carga = cargar(self.qf, [fila()])
        self.assertEqual(carga.estado, "fallida")
        self.assertEqual(carga.filas_rechazadas, 0)
        self.assertEqual(carga.resultados.count(), 0)
        self.assertFalse(Paciente.objects.exists())
        self.assertNotIn("NO DEBE COPIARSE", carga.resumen_fallo)

    def test_error_de_validacion_de_auditoria_tambien_interrumpe(self):
        from django.core.exceptions import ValidationError
        with patch("recetasapp.services.registrar_accion", side_effect=ValidationError("Fallo interno")):
            carga = cargar(self.qf, [fila()])
        self.assertEqual(carga.estado, "fallida")
        self.assertEqual(carga.filas_rechazadas, 0)
        self.assertFalse(Paciente.objects.exists())

    def test_interrupcion_conserva_filas_previas_y_reconstruye_totales(self):
        from recetasapp.services import aplicar_fila
        datos = list(filas_demo(cantidad=2))
        def operar(actor, valores, **kwargs):
            if kwargs["numero_fila"] == 3:
                raise RuntimeError("Interrupción simulada")
            return aplicar_fila(actor, valores, **kwargs)
        with patch("recetasapp.importacion.aplicar_fila", side_effect=operar):
            carga = cargar(self.qf, datos)
        self.assertEqual(carga.estado, "fallida")
        self.assertEqual(carga.total_filas, 2)
        self.assertEqual(carga.filas_creadas, 1)
        self.assertEqual(carga.pacientes_creados, 1)
        self.assertEqual(carga.recetas_creadas, 1)
        self.assertEqual(carga.resultados.count(), 1)

    def test_limite_filas_y_receta_incompleta(self):
        with patch("recetasapp.importacion.MAX_FILAS", 1):
            carga = cargar(self.qf, [fila(), fila("OTRA")])
        self.assertEqual(carga.estado, "fallida")
        incompleta = fila()
        incompleta[9] = ""
        carga = cargar(self.qf, [incompleta])
        self.assertEqual(carga.filas_rechazadas, 1)
        self.assertFalse(Paciente.objects.exists())

    def test_auditoria_y_reporte_no_copian_datos_personales(self):
        carga = cargar(self.qf, [fila(), ["RUT RECHAZADO SECRETO"]])
        datos = str(list(RegistroAuditoria.objects.values())) + str(list(carga.resultados.values("mensaje", "codigo_motivo")))
        self.assertNotIn(fila()[0], datos)
        self.assertNotIn(fila()[1], datos)
        self.assertNotIn("RUT RECHAZADO SECRETO", datos)
