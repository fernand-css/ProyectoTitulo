"""Spec 10: término de turno, desactivación de cuentas, cambio de fila y urgencia (datos sintéticos)."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from coreapp.models import RegistroAuditoria
from turnosapp import atencion
from turnosapp.cola import procesar_pendiente
from turnosapp.models import AnuncioSala, ContadorTurnosDiario, EventoTurno, OcupacionVentanilla, Turno, Ventanilla
from usuariosapp.services import cambiar_estado_cuenta
from .datos_cola import DatosCola

TODOS = ("preferencial", "general", "cronicos", "urgencia")


class DatosPersonal(DatosCola):
    def activar(self, numero=1, tipos=("general", "preferencial", "cronicos")):
        ventanilla = super().activar(numero, tipos)
        # `apertura` toma el reloj real por defecto; el término usa el reloj fijo de estas pruebas.
        OcupacionVentanilla.objects.filter(ventanilla=ventanilla).update(apertura=self.ahora - timedelta(hours=1))
        return ventanilla


class TerminoTurnoTests(DatosPersonal, TestCase):
    def llamado(self, numero=1, tipo="general"):
        ventanilla = self.activar(numero, TODOS)
        turno = self.turno(tipo, espera=180)
        procesar_pendiente(self.pendiente().pk)
        turno.refresh_from_db()
        self.assertEqual((turno.estado, turno.ventanilla_id), ("llamado", ventanilla.pk))
        return ventanilla, turno

    def test_qf_termina_con_llamado_y_vuelve_a_la_cola_con_antiguedad(self):
        ventanilla, turno = self.llamado()
        entrada = turno.entrada_cola
        with self.assertRaisesMessage(ValidationError, "Confirma el término de turno"):
            atencion.terminar_turno_ventanilla(self.personal["qf"], ventanilla.pk, uuid.uuid4())
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "llamado")
        resultado = atencion.terminar_turno_ventanilla(self.personal["qf"], ventanilla.pk, uuid.uuid4(), confirmar=True)
        self.assertEqual(resultado["estado"], "esperando")
        ventanilla.refresh_from_db()
        turno.refresh_from_db()
        self.assertEqual((ventanilla.habilitada, ventanilla.operador_id, ventanilla.automatico), (False, None, False))
        ocupacion = OcupacionVentanilla.objects.get(ventanilla=ventanilla)
        self.assertEqual((ocupacion.cierre, ocupacion.motivo), (self.ahora, "termino_turno"))
        self.assertEqual((turno.estado, turno.ventanilla_id, turno.operador_id, turno.ultimo_llamado), ("esperando", None, None, None))
        self.assertEqual(turno.entrada_cola, entrada)
        evento = turno.eventos.order_by("-secuencia").first()
        self.assertEqual((evento.accion, evento.actor_id, evento.ventanilla_id), ("devuelto_a_cola", self.personal["qf"].pk, ventanilla.pk))
        self.assertTrue(RegistroAuditoria.objects.filter(accion="ventanilla.terminar_turno", usuario=self.personal["qf"]).exists())
        # Otra ventanilla compatible lo llama sin otro clic.
        otra = self.activar(2, TODOS)
        procesar_pendiente(self.pendiente().pk)
        turno.refresh_from_db()
        self.assertEqual((turno.estado, turno.ventanilla_id), ("llamado", otra.pk))

    def test_tecnico_termina_la_propia_pero_no_una_ajena(self):
        propia = self.activar(1, TODOS)
        ajena = self.activar(2, TODOS)
        with self.assertRaises(PermissionDenied):
            atencion.terminar_turno_ventanilla(self.personal["tecnico"], ajena.pk, uuid.uuid4(), confirmar=True)
        ajena.refresh_from_db()
        self.assertTrue(ajena.habilitada and ajena.operador_id)
        atencion.terminar_turno_ventanilla(self.personal["tecnico"], propia.pk, uuid.uuid4())
        propia.refresh_from_db()
        self.assertEqual((propia.habilitada, propia.operador_id), (False, None))

    def test_encargado_no_termina_ni_cambia_turnos(self):
        ventanilla, turno = self.llamado()
        for operacion in (
            lambda: atencion.terminar_turno_ventanilla(self.personal["encargado"], ventanilla.pk, uuid.uuid4(), confirmar=True),
            lambda: atencion.marcar_urgencia(self.personal["encargado"], turno.pk, uuid.uuid4()),
            lambda: atencion.reclasificar_turno(self.personal["encargado"], turno.pk, uuid.uuid4(), letra="P"),
        ):
            with self.assertRaises(PermissionDenied):
                operacion()

    def test_llamado_de_un_dia_anterior_se_cierra_sin_volver_a_la_cola(self):
        ventanilla, turno = self.llamado()
        Turno.objects.filter(pk=turno.pk).update(fecha=self.fecha - timedelta(days=1))
        resultado = atencion.terminar_turno_ventanilla(self.personal["qf"], ventanilla.pk, uuid.uuid4(), confirmar=True)
        turno.refresh_from_db()
        self.assertEqual(resultado["estado"], "sin_atencion_cierre")
        self.assertEqual((turno.estado, turno.cerrado_en, turno.ventanilla_id), ("sin_atencion_cierre", self.ahora, None))
        self.assertEqual(turno.eventos.order_by("-secuencia").first().accion, "sin_atencion_cierre")

    def test_repetir_la_misma_operacion_no_duplica_efectos(self):
        ventanilla, turno = self.llamado()
        operacion = uuid.uuid4()
        primero = atencion.terminar_turno_ventanilla(self.personal["qf"], ventanilla.pk, operacion, confirmar=True)
        segundo = atencion.terminar_turno_ventanilla(self.personal["qf"], ventanilla.pk, operacion, confirmar=True)
        self.assertEqual(primero, segundo)
        self.assertEqual(EventoTurno.objects.filter(turno=turno, accion="devuelto_a_cola").count(), 1)
        with self.assertRaisesMessage(ValidationError, "ya está deshabilitada"):
            atencion.terminar_turno_ventanilla(self.personal["qf"], ventanilla.pk, uuid.uuid4(), confirmar=True)


class DesactivacionCuentaTests(DatosPersonal, TestCase):
    def test_desactivar_tecnico_termina_su_ventanilla_y_devuelve_el_llamado(self):
        ventanilla = self.activar(1, TODOS)
        turno = self.turno()
        procesar_pendiente(self.pendiente().pk)
        cambiar_estado_cuenta(self.personal["qf"], self.personal["tecnico"].pk, activo=False)
        self.personal["tecnico"].refresh_from_db()
        ventanilla.refresh_from_db()
        turno.refresh_from_db()
        self.assertFalse(self.personal["tecnico"].is_active)
        self.assertEqual((ventanilla.habilitada, ventanilla.operador_id), (False, None))
        self.assertEqual(turno.estado, "esperando")

    def test_si_falla_el_termino_no_se_desactiva_la_cuenta(self):
        ventanilla = self.activar(1, TODOS)
        with patch("turnosapp.atencion.terminar_turno_ventanilla", side_effect=ValidationError("fallo sintético")):
            with self.assertRaises(ValidationError):
                cambiar_estado_cuenta(self.personal["qf"], self.personal["tecnico"].pk, activo=False)
        self.personal["tecnico"].refresh_from_db()
        ventanilla.refresh_from_db()
        self.assertTrue(self.personal["tecnico"].is_active)
        self.assertEqual(ventanilla.operador_id, self.personal["tecnico"].pk)

    def test_desactivar_sin_ventanilla_no_toca_turnos(self):
        cambiar_estado_cuenta(self.personal["qf"], self.personal["tecnico"].pk, activo=False)
        self.assertFalse(EventoTurno.objects.exists())


class CambioFilaTests(DatosPersonal, TestCase):
    def test_reclasificar_c_a_p_da_el_siguiente_p_y_conserva_antiguedad(self):
        ContadorTurnosDiario.objects.create(fecha=self.fecha, letra="P", ultimo_numero=13)
        turno = self.turno("cronicos", espera=300)
        anterior, entrada = turno.codigo, turno.entrada_cola
        resultado = atencion.reclasificar_turno(self.personal["tecnico"], turno.pk, uuid.uuid4(), letra="P")
        turno.refresh_from_db()
        self.assertEqual((turno.letra, turno.numero, turno.tipo_atencion), ("P", 14, "preferencial"))
        self.assertEqual((resultado["codigo"], turno.entrada_cola), ("P-014", entrada))
        evento = turno.eventos.get(accion="reclasificado")
        self.assertEqual(f"{evento.letra_anterior}-{evento.numero_anterior:03d}", anterior)
        self.assertFalse(AnuncioSala.objects.exists())  # la sala no anuncia reclasificaciones

    def test_rechaza_llamado_misma_letra_y_urgencia(self):
        turno = self.turno("cronicos")
        with self.assertRaisesMessage(ValidationError, "ya está en esa fila"):
            atencion.reclasificar_turno(self.personal["qf"], turno.pk, uuid.uuid4(), letra="C")
        with self.assertRaises(ValidationError):
            atencion.reclasificar_turno(self.personal["qf"], turno.pk, uuid.uuid4(), letra="U")
        self.activar(1, TODOS)
        procesar_pendiente(self.pendiente().pk)
        with self.assertRaisesMessage(ValidationError, "sigue esperando"):
            atencion.reclasificar_turno(self.personal["qf"], turno.pk, uuid.uuid4(), letra="P")
        turno.refresh_from_db()
        self.assertEqual((turno.letra, turno.estado), ("C", "llamado"))

    def test_urgencia_da_u_001_y_es_el_proximo_llamado(self):
        for tipo in ("preferencial", "cronicos"):
            self.turno(tipo, espera=2000)
        urgente = self.turno("general")
        resultado = atencion.marcar_urgencia(self.personal["qf"], urgente.pk, uuid.uuid4())
        self.assertEqual(resultado["codigo"], "U-001")
        self.assertEqual(ContadorTurnosDiario.objects.get(fecha=self.fecha, letra="U").ultimo_numero, 1)
        evento = urgente.eventos.get(accion="urgencia")
        self.assertEqual((evento.letra_anterior, evento.actor_id), ("G", self.personal["qf"].pk))
        self.activar(1, TODOS)
        procesar_pendiente(self.pendiente().pk)
        urgente.refresh_from_db()
        self.assertEqual((urgente.estado, urgente.codigo), ("llamado", "U-001"))
        Turno.objects.filter(pk=urgente.pk).update(estado="esperando", ventanilla=None, operador=None)
        with self.assertRaisesMessage(ValidationError, "no se puede quitar"):
            atencion.reclasificar_turno(self.personal["qf"], urgente.pk, uuid.uuid4(), letra="G")

    def test_auditoria_sin_datos_personales(self):
        turno = self.turno("general")
        atencion.marcar_urgencia(self.personal["tecnico"], turno.pk, uuid.uuid4())
        for registro in RegistroAuditoria.objects.all():
            for valor in (registro.accion, registro.objeto_tipo, registro.objeto_id):
                self.assertNotIn(turno.rut, valor)
                self.assertNotIn("Paciente sintético", valor)


class VistasPersonalTests(DatosPersonal, TestCase):
    def test_qf_termina_desde_la_pantalla_con_confirmacion(self):
        ventanilla = self.activar(1, TODOS)
        turno = self.turno()
        procesar_pendiente(self.pendiente().pk)
        self.client.force_login(self.personal["qf"])
        url = reverse("turnosapp:terminar_turno", kwargs={"pk": ventanilla.pk})
        respuesta = self.client.get(url)
        self.assertContains(respuesta, f"turno {turno.codigo}")
        self.assertContains(respuesta, 'name="confirmar"')
        operacion = respuesta.context["form"]["operacion_id"].value()
        sin_confirmar = self.client.post(url, {"operacion_id": operacion})
        self.assertContains(sin_confirmar, "Confirma el término de turno", status_code=400)
        respuesta = self.client.post(url, {"operacion_id": uuid.uuid4(), "confirmar": "on"}, follow=True)
        self.assertRedirects(respuesta, reverse("turnosapp:gestion"))
        self.assertContains(respuesta, "volvió a la fila")
        self.assertContains(self.client.get(reverse("turnosapp:gestion")), "Término de turno de la ventanilla")

    def test_tecnico_no_abre_termino_de_ventanilla_ajena(self):
        propia = self.activar(1, TODOS)
        ajena = self.activar(2, TODOS)
        self.client.force_login(self.personal["tecnico"])
        self.assertEqual(self.client.get(reverse("turnosapp:terminar_turno", kwargs={"pk": ajena.pk})).status_code, 403)
        panel = self.client.get(reverse("turnosapp:panel"))
        self.assertContains(panel, reverse("turnosapp:terminar_turno", kwargs={"pk": propia.pk}))

    def test_urgencia_desde_historial_abre_comprobante_pdf_solo_para_quien_la_marco(self):
        turno = self.turno("general")
        anterior = turno.codigo
        self.client.force_login(self.personal["tecnico"])
        historial = self.client.get(reverse("turnosapp:historial", kwargs={"pk": turno.pk}))
        self.assertContains(historial, "Marcar urgencia")
        self.assertContains(historial, "Cambiar de fila")
        respuesta = self.client.post(reverse("turnosapp:urgencia", kwargs={"pk": turno.pk}), {"operacion_id": uuid.uuid4()})
        self.assertRedirects(respuesta, reverse("turnosapp:comprobante_personal", kwargs={"pk": turno.pk}))
        pagina = self.client.get(respuesta.url)
        self.assertContains(pagina, "U-001")
        self.assertContains(pagina, "Reemplaza a su número anterior " + anterior)
        self.assertContains(pagina, "Listo, volver al panel")
        self.assertNotContains(pagina, turno.rut)
        self.assertNotIn("window.print", pagina.content.decode())
        pdf = self.client.get(reverse("turnosapp:comprobante_personal_pdf", kwargs={"pk": turno.pk}))
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertIn("no-store", pdf["Cache-Control"])
        self.assertIn(b"U-001", pdf.content)
        self.assertIn(b"Reemplaza a tu n", pdf.content)
        self.assertNotIn(turno.rut.encode(), pdf.content)
        # Otro integrante del personal no abre el comprobante ajeno.
        self.client.force_login(self.personal["qf"])
        self.assertEqual(self.client.get(respuesta.url).status_code, 404)
        self.assertEqual(self.client.get(reverse("turnosapp:comprobante_personal_pdf", kwargs={"pk": turno.pk})).status_code, 404)

    def test_reclasificar_desde_historial_y_errores_sin_cambios(self):
        turno = self.turno("cronicos")
        self.client.force_login(self.personal["qf"])
        url = reverse("turnosapp:reclasificar", kwargs={"pk": turno.pk})
        respuesta = self.client.post(url, {"operacion_id": uuid.uuid4(), "letra": "C"}, follow=True)
        self.assertContains(respuesta, "ya está en esa fila")
        respuesta = self.client.post(url, {"operacion_id": uuid.uuid4(), "letra": "G"})
        self.assertRedirects(respuesta, reverse("turnosapp:comprobante_personal", kwargs={"pk": turno.pk}))
        turno.refresh_from_db()
        self.assertEqual(turno.letra, "G")
        historial = self.client.get(reverse("turnosapp:historial", kwargs={"pk": turno.pk}))
        self.assertContains(historial, f"Cambio de fila (antes C-{turno.eventos.get(accion='reclasificado').numero_anterior:03d})")

    def test_post_exige_csrf_y_get_no_cambia(self):
        turno = self.turno("general")
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.personal["qf"])
        self.assertEqual(cliente.post(reverse("turnosapp:urgencia", kwargs={"pk": turno.pk}), {"operacion_id": uuid.uuid4()}).status_code, 403)
        self.assertEqual(cliente.get(reverse("turnosapp:urgencia", kwargs={"pk": turno.pk})).status_code, 405)
        turno.refresh_from_db()
        self.assertEqual(turno.letra, "G")
