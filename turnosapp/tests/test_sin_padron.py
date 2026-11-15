"""Compatibilidad con turnos sin paciente del padrón (enmienda 04 del 2026-11-15)."""
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from turnosapp import atencion
from turnosapp.cola import procesar_pendiente
from turnosapp.models import Turno
from turnosapp.services import clasificar_atencion
from .datos_cola import DatosCola


class SinPadronTests(DatosCola, TestCase):
    def sin_paciente(self, indice, estado="esperando", fecha=None, **extra):
        self.numero += 1
        return Turno.objects.create(paciente=None, rut=self.ruts[indice], letra="G", tipo_atencion="general",
            fecha=fecha or self.fecha, numero=self.numero, estado=estado,
            entrada_cola=self.ahora - timedelta(seconds=10 * (50 - indice)), **extra)

    def test_llamado_sin_paciente_no_detiene_la_seleccion(self):
        self.activar(1)
        self.activar(2)
        primero = self.sin_paciente(40)
        self.assertEqual(procesar_pendiente(self.pendiente().pk), 1)
        primero.refresh_from_db()
        self.assertEqual(primero.estado, "llamado")
        registrado = self.turno()
        otro = self.sin_paciente(41)
        self.assertEqual(procesar_pendiente(self.pendiente().pk), 1)
        self.assertEqual(Turno.objects.filter(estado="llamado").count(), 2)
        self.assertEqual(Turno.objects.filter(estado="llamado", pk__in=[registrado.pk, otro.pk]).count(), 1)

    def test_rut_con_llamado_se_excluye_aunque_no_tenga_paciente(self):
        v1 = self.activar(1)
        self.activar(2)
        self.sin_paciente(42, estado="llamado", fecha=self.fecha - timedelta(days=1), ventanilla=v1,
            operador=v1.operador, ultimo_llamado=self.ahora - timedelta(days=1))
        hoy = self.sin_paciente(42)
        self.assertEqual(procesar_pendiente(self.pendiente().pk), 0)
        hoy.refresh_from_db()
        self.assertEqual(hoy.estado, "esperando")

    def test_clasificar_sin_paciente_es_general(self):
        self.assertEqual(clasificar_atencion(None, self.fecha), Turno.TipoAtencion.GENERAL)

    def test_reincorporar_sin_paciente_no_confunde_a_otros_no_registrados(self):
        ausente = self.sin_paciente(43, estado="ausente", cerrado_en=self.ahora)
        self.sin_paciente(44)  # otra persona no registrada, con turno activo
        resultado = atencion.reincorporar(self.personal["tecnico"], ausente.pk, uuid.uuid4())
        self.assertEqual(resultado["estado"], "esperando")

    def test_reincorporar_sin_paciente_rechaza_otro_activo_del_mismo_rut(self):
        ausente = self.sin_paciente(45, estado="ausente", cerrado_en=self.ahora)
        v1 = self.activar(1)
        self.sin_paciente(45, estado="llamado", fecha=self.fecha - timedelta(days=1), ventanilla=v1,
            operador=v1.operador, ultimo_llamado=self.ahora - timedelta(days=1))
        with self.assertRaisesMessage(ValidationError, "otro turno activo"):
            atencion.reincorporar(self.personal["tecnico"], ausente.pk, uuid.uuid4())

    def test_vistas_privadas_muestran_codigo_y_no_registrado(self):
        self.activar(1)
        turno = self.sin_paciente(46)
        procesar_pendiente(self.pendiente().pk)
        turno.refresh_from_db()
        self.assertEqual(turno.codigo, f"G-{turno.numero:03d}")
        self.client.force_login(self.personal["tecnico"])
        html = self.client.get(reverse("turnosapp:estado")).json()["html"]
        self.assertIn(turno.codigo, html)
        self.assertIn("No registrado en el padrón", html)
        self.assertIn(f"Atendiendo el turno {turno.codigo}", html)
        self.assertNotIn("Ver ficha del paciente", html)
        for nombre in ("historial", "finalizar_atencion"):
            respuesta = self.client.get(reverse(f"turnosapp:{nombre}", kwargs={"pk": turno.pk}))
            self.assertContains(respuesta, turno.codigo)
            self.assertContains(respuesta, "No registrado en el padrón")


class CierreSinRecetasTests(DatosCola, TestCase):
    """Enmienda RF-05-13 (RF-05-07): cierre con motivo fijo, sin texto ni entregas."""

    def llamado_sin_recetas(self, paciente=False, activar=True):
        if activar:
            self.activar(1)
        if paciente:
            turno = self.turno()
        else:
            self.numero += 1
            turno = Turno.objects.create(paciente=None, rut=self.ruts[47], letra="G", tipo_atencion="general",
                fecha=self.fecha, numero=self.numero, entrada_cola=self.ahora)
        procesar_pendiente(self.pendiente().pk)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "llamado")
        return turno

    def test_servicio_cierra_con_motivo_fijo_sin_pedir_texto(self):
        from recetasapp.models import EntregaReceta
        from turnosapp.models import CierreAtencion
        for paciente in (False, True):
            with self.subTest(paciente=paciente):
                turno = self.llamado_sin_recetas(paciente, activar=not paciente)
                atencion.finalizar_atencion(self.personal["tecnico"], turno.pk, uuid.uuid4(), recetas_entregadas=[],
                    motivo="texto que se ignora")
                turno.refresh_from_db()
                cierre = CierreAtencion.objects.get(turno=turno)
                self.assertEqual(turno.estado, "cerrado_sin_entrega")
                self.assertEqual((cierre.resultado, cierre.motivo), ("sin_entrega", atencion.MOTIVO_SIN_RECETAS))
                self.assertFalse(cierre.detalles.exists())
                self.assertFalse(EntregaReceta.objects.exists())

    def test_formulario_solo_pide_confirmar(self):
        turno = self.llamado_sin_recetas()
        self.client.force_login(self.personal["tecnico"])
        url = reverse("turnosapp:finalizar_atencion", kwargs={"pk": turno.pk})
        respuesta = self.client.get(url)
        self.assertContains(respuesta, atencion.MOTIVO_SIN_RECETAS)
        self.assertNotContains(respuesta, 'name="motivo"')
        self.assertNotContains(respuesta, 'name="recetas_entregadas"')
        operacion = respuesta.context["form"]["operacion_id"].value()
        self.client.post(url, {"operacion_id": operacion, "confirmar": "on"})
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "cerrado_sin_entrega")
        from turnosapp.models import CierreAtencion
        self.assertEqual(CierreAtencion.objects.get(turno=turno).motivo, atencion.MOTIVO_SIN_RECETAS)
