"""RF-05-14 (segunda enmienda del 05): causa de no entrega en lista cerrada al cerrar la atención."""
import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from coreapp.models import RegistroAuditoria
from recetasapp.models import EntregaReceta
from turnosapp.models import CausaNoEntrega, CierreAtencion, DetalleCierre, OperacionAtencion
from .datos_cierre import DatosCierre


class CausaServicioTests(DatosCierre, TestCase):
    def test_receta_no_entregada_guarda_codigo_y_texto_legible(self):
        r1, r2 = self.recetas_cierre
        self.confirmar([r1.pk], causas={r2.pk: "sin_stock"})
        detalle = DetalleCierre.objects.get(entregada=False)
        self.assertEqual((detalle.causa, detalle.motivo), ("sin_stock", "Sin stock"))
        self.assertEqual(DetalleCierre.objects.get(entregada=True).causa, "")
        self.client.force_login(self.personal["tecnico"])
        respuesta = self.client.get(reverse("turnosapp:historial", kwargs={"pk": self.actual.pk}))
        self.assertContains(respuesta, "No entregada — Sin stock")

    def test_otro_exige_detalle_y_se_guarda_con_prefijo(self):
        r1, r2 = self.recetas_cierre
        with self.assertRaises(ValidationError):
            self.confirmar([r1.pk], causas={r2.pk: "otro"})
        self.assertFalse(CierreAtencion.objects.exists())
        self.assertFalse(EntregaReceta.objects.exists())
        self.confirmar([r1.pk], causas={r2.pk: "otro"}, motivos={r2.pk: "Paciente pide cambiar de horario"})
        detalle = DetalleCierre.objects.get(entregada=False)
        self.assertEqual((detalle.causa, detalle.motivo), ("otro", "Otro: Paciente pide cambiar de horario"))

    def test_causa_general_se_aplica_a_las_recetas_sin_causa_propia(self):
        r1, r2 = self.recetas_cierre
        self.confirmar([], causa="no_la_pide", causas={r1.pk: "no_vigente"})
        cierre = CierreAtencion.objects.get()
        self.assertEqual((cierre.resultado, cierre.causa, cierre.motivo), ("sin_entrega", "no_la_pide", "Paciente no la pide"))
        causas = dict(DetalleCierre.objects.values_list("turno_receta__receta_id", "causa"))
        self.assertEqual(causas, {r1.pk: "no_vigente", r2.pk: "no_la_pide"})
        self.actual.refresh_from_db()
        self.assertEqual(self.actual.estado, "cerrado_sin_entrega")

    def test_sin_entregas_exige_causa_general(self):
        r1, r2 = self.recetas_cierre
        with self.assertRaises(ValidationError):
            self.confirmar([], causas={r1.pk: "sin_stock", r2.pk: "sin_stock"})
        self.assertFalse(CierreAtencion.objects.exists())

    def test_codigo_invalido_y_detalle_largo_se_rechazan(self):
        r1, r2 = self.recetas_cierre
        with self.assertRaises(ValidationError):
            self.confirmar([r1.pk], causas={r2.pk: "inventada"})
        with self.assertRaises(ValidationError):
            self.confirmar([r1.pk], causa="otro", motivo="x" * 201)
        self.assertFalse(OperacionAtencion.objects.filter(tipo="finalizar").exists())

    def test_texto_libre_sin_codigo_se_guarda_como_otro(self):
        r1, r2 = self.recetas_cierre
        self.confirmar([r1.pk], motivos={r2.pk: "No disponible"})
        detalle = DetalleCierre.objects.get(entregada=False)
        self.assertEqual((detalle.causa, detalle.motivo), ("otro", "No disponible"))

    def test_entregada_con_causa_otro_sin_detalle_no_bloquea(self):
        self.confirmar(causas={self.recetas_cierre[0].pk: "otro"})
        self.assertEqual(DetalleCierre.objects.filter(entregada=True).count(), 2)

    def test_auditoria_no_guarda_el_detalle_de_otro(self):
        r1, r2 = self.recetas_cierre
        self.confirmar([r1.pk], causas={r2.pk: "otro"}, motivos={r2.pk: "Detalle privado sintético"})
        for registro in RegistroAuditoria.objects.all():
            self.assertNotIn("Detalle privado sintético", str(registro.__dict__))

    def test_lista_de_causas(self):
        self.assertEqual(CausaNoEntrega.values, ["sin_stock", "no_la_pide", "no_vigente", "cambio_indicacion", "otro"])


class CausaFormularioTests(DatosCierre, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.personal["tecnico"])
        self.url = reverse("turnosapp:finalizar_atencion", kwargs={"pk": self.actual.pk})

    def datos(self, **extra):
        return {"operacion_id": str(uuid.uuid4()), "confirmar": "on", **extra}

    def test_formulario_muestra_listas_sin_preseleccion(self):
        respuesta = self.client.get(self.url)
        r1 = self.recetas_cierre[0]
        self.assertContains(respuesta, f'name="causa_{r1.pk}"')
        self.assertContains(respuesta, 'name="causa"')
        self.assertContains(respuesta, '<option value="" selected>Elige una causa</option>', count=3, html=False)
        self.assertContains(respuesta, "Receta no vigente o sin cupo")

    def test_otro_sin_detalle_muestra_error_y_no_cierra(self):
        r1, r2 = self.recetas_cierre
        respuesta = self.client.post(self.url, self.datos(recetas_entregadas=[str(r1.pk)], **{f"causa_{r2.pk}": "otro"}))
        self.assertContains(respuesta, "Escribe el detalle de la causa «Otro».")
        self.assertFalse(CierreAtencion.objects.exists())

    def test_receta_sin_causa_muestra_error(self):
        r1, r2 = self.recetas_cierre
        respuesta = self.client.post(self.url, self.datos(recetas_entregadas=[str(r1.pk)]))
        self.assertContains(respuesta, "Indica la causa de no entrega de esta receta.")
        self.assertFalse(CierreAtencion.objects.exists())

    def test_cierre_con_causa_por_receta(self):
        r1, r2 = self.recetas_cierre
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(self.url, self.datos(recetas_entregadas=[str(r1.pk)], **{f"causa_{r2.pk}": "cambio_indicacion"}))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(DetalleCierre.objects.get(entregada=False).causa, "cambio_indicacion")

    def test_cierre_sin_entregas_con_causa_general(self):
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(self.url, self.datos(causa="no_la_pide"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(set(DetalleCierre.objects.values_list("causa", flat=True)), {"no_la_pide"})
