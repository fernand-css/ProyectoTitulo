"""Cierre, entregas, formularios anteriores y recuperación sin doble descuento."""
import uuid
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from coreapp.models import RegistroAuditoria
from recetasapp.models import EntregaReceta, Receta
from recetasapp.services import registrar_entrega
from turnosapp.atencion import finalizar_atencion
from turnosapp.cola import procesar_pendiente
from turnosapp.models import CierreAtencion, DetalleCierre, EventoTurno, OperacionAtencion, PendienteSeleccion, Turno
from .datos_cierre import DatosCierre


class CierreTests(DatosCierre, TestCase):
    def test_confirmar_todas_y_reenviar_no_descuenta_dos_veces(self):
        siguiente = self.turno()
        op = uuid.uuid4()
        primero = self.confirmar(operacion=op)
        self.assertEqual(self.confirmar(operacion=op), primero)
        self.actual.refresh_from_db()
        siguiente.refresh_from_db()
        self.assertEqual(self.actual.estado, "atendido")
        self.assertEqual(siguiente.estado, "llamado")
        self.assertEqual(EntregaReceta.objects.count(), 2)
        self.assertEqual(CierreAtencion.objects.count(), 1)
        self.assertEqual(DetalleCierre.objects.filter(entregada=True).count(), 2)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="receta.entrega").count(), 2)

    def test_parcial_y_sin_entrega_exigen_motivos(self):
        r1, r2 = self.recetas_cierre
        with self.assertRaises(ValidationError):
            self.confirmar([r1.pk])
        self.assertFalse(EntregaReceta.objects.exists())
        self.confirmar([r1.pk], motivos={r2.pk: "No disponible"})
        self.assertEqual(EntregaReceta.objects.count(), 1)
        self.assertEqual(DetalleCierre.objects.get(entregada=False).motivo, "No disponible")

    def test_cerrar_sin_entrega_no_cambia_cupos(self):
        with self.assertRaises(ValidationError):
            self.confirmar([])
        self.confirmar([], motivo="Requiere revisión de receta")
        self.actual.refresh_from_db()
        self.assertEqual(self.actual.estado, "cerrado_sin_entrega")
        self.assertFalse(EntregaReceta.objects.exists())
        self.assertEqual(DetalleCierre.objects.count(), 2)

    def test_una_seleccionada_agotada_revierte_todas_las_nuevas(self):
        Receta.objects.filter(pk=self.recetas_cierre[1].pk).update(entregas_completadas=3)
        with self.assertRaises(ValidationError):
            self.confirmar()
        self.assertFalse(EntregaReceta.objects.exists())
        self.assertFalse(CierreAtencion.objects.exists())
        self.recetas_cierre[0].refresh_from_db()
        self.assertEqual(self.recetas_cierre[0].entregas_completadas, 0)
        self.actual.refresh_from_db()
        self.assertEqual(self.actual.estado, "llamado")

    def test_entrega_del_03_se_reutiliza_con_actor_y_fecha_original(self):
        r1 = self.recetas_cierre[0]
        entrega = registrar_entrega(self.personal["admin"], r1.pk, uuid.uuid4(), turno_receta_id=self.vinculos[0].pk)
        self.confirmar()
        conservada = EntregaReceta.objects.get(pk=entrega.pk)
        self.assertEqual((conservada.creado_por_id, conservada.creado_en), (entrega.creado_por_id, entrega.creado_en))
        self.assertEqual(EntregaReceta.objects.count(), 2)
        r1.refresh_from_db()
        self.assertEqual(r1.entregas_completadas, 1)

    def test_no_se_borra_entrega_anterior_si_falla_nuevo_cierre(self):
        r1, r2 = self.recetas_cierre
        registrar_entrega(self.personal["tecnico"], r1.pk, uuid.uuid4())
        Receta.objects.filter(pk=r2.pk).update(entregas_completadas=3)
        with self.assertRaises(ValidationError):
            self.confirmar()
        self.assertEqual(EntregaReceta.objects.count(), 1)
        self.assertFalse(CierreAtencion.objects.exists())

    def test_fallo_del_llamado_siguiente_no_revierte_entregas_y_se_recupera(self):
        siguiente = self.turno()
        with patch("turnosapp.cola.registrar_accion", side_effect=RuntimeError("fallo sintético de selección")):
            resultado = self.confirmar()
        self.assertEqual(EntregaReceta.objects.count(), 2)
        self.assertEqual(CierreAtencion.objects.count(), 1)
        pendiente = PendienteSeleccion.objects.get(pk=resultado["pendiente"])
        self.assertEqual(pendiente.estado, "pendiente")
        procesar_pendiente(pendiente.pk)
        siguiente.refresh_from_db()
        self.assertEqual(siguiente.estado, "llamado")
        self.assertEqual(EntregaReceta.objects.count(), 2)

    def test_auditoria_del_cierre_fallida_revierte_entregas_y_contadores(self):
        with patch("turnosapp.atencion.registrar_accion", side_effect=RuntimeError("fallo sintético")):
            with self.assertRaises(RuntimeError):
                self.confirmar()
        self.assertFalse(EntregaReceta.objects.exists())
        self.assertFalse(CierreAtencion.objects.exists())
        self.assertFalse(RegistroAuditoria.objects.filter(accion="receta.entrega").exists())

    def test_seleccion_ajena_y_rol_ajeno_no_cierran(self):
        with self.assertRaises(ValidationError):
            self.confirmar([999999])
        for actor in (self.personal["qf"], self.personal["encargado"], self.personal["admin"]):
            with self.assertRaises(PermissionDenied):
                finalizar_atencion(actor, self.actual.pk, uuid.uuid4(), recetas_entregadas=[] , motivo="Revisión")

    def test_formulario_03_abierto_antes_del_cierre_recupera_sin_otro_descuento(self):
        receta = self.recetas_cierre[0]
        self.client.force_login(self.personal["tecnico"])
        ruta = reverse("recetasapp:entrega_confirmar", args=[receta.pk])
        formulario = self.client.get(ruta).context["form"]
        self.confirmar()
        respuesta = self.client.post(ruta, {"operacion_id": formulario.initial["operacion_id"],
            "contexto": formulario.initial["contexto"], "confirmar": "on"})
        self.assertEqual(respuesta.status_code, 302)
        receta.refresh_from_db()
        self.assertEqual(receta.entregas_completadas, 1)
        self.assertEqual(EntregaReceta.objects.count(), 2)

    def test_contexto_03_firmado_no_se_puede_alterar(self):
        receta = self.recetas_cierre[0]
        self.client.force_login(self.personal["tecnico"])
        ruta = reverse("recetasapp:entrega_confirmar", args=[receta.pk])
        formulario = self.client.get(ruta).context["form"]
        self.client.post(ruta, {"operacion_id": formulario.initial["operacion_id"],
            "contexto": formulario.initial["contexto"] + "alterado", "confirmar": "on"})
        self.assertFalse(EntregaReceta.objects.exists())

    def test_alias_de_entrega_recuperada_no_se_reutiliza_en_otra_receta(self):
        self.confirmar()
        op = uuid.uuid4()
        entrega = registrar_entrega(self.personal["tecnico"], self.recetas_cierre[0].pk, op, turno_receta_id=self.vinculos[0].pk)
        self.assertEqual(registrar_entrega(self.personal["tecnico"], self.recetas_cierre[0].pk, op).pk, entrega.pk)
        with self.assertRaises(ValidationError):
            registrar_entrega(self.personal["tecnico"], self.recetas_cierre[1].pk, op)

    def test_fallo_en_segunda_entrega_revierte_la_primera(self):
        from recetasapp import services
        auditar_real = services.auditar
        def auditar(actor, accion, objeto):
            if accion == "receta.entrega" and objeto.receta_id == self.recetas_cierre[1].pk:
                raise RuntimeError("fallo sintético de segunda entrega")
            return auditar_real(actor, accion, objeto)
        with patch("recetasapp.services.auditar", side_effect=auditar):
            with self.assertRaises(RuntimeError):
                self.confirmar()
        self.assertFalse(EntregaReceta.objects.exists())
        self.assertFalse(CierreAtencion.objects.exists())
        self.assertFalse(Receta.objects.exclude(entregas_completadas=0).exists())

    def test_uuid_de_cierre_no_admite_cambio_de_seleccion(self):
        op = uuid.uuid4()
        self.confirmar(operacion=op)
        with self.assertRaises(ValidationError):
            self.confirmar([], operacion=op, motivo="Cambio de selección")
        self.assertEqual(EntregaReceta.objects.count(), 2)

    def test_formulario_independiente_viejo_detecta_cambio_de_contador(self):
        receta = self.recetas_cierre[0]
        Turno.objects.filter(pk=self.actual.pk).update(estado="esperando", operador=None, ventanilla=None)
        self.client.force_login(self.personal["tecnico"])
        ruta = reverse("recetasapp:entrega_confirmar", args=[receta.pk])
        formulario = self.client.get(ruta).context["form"]  # Sin atención llamada en este instante.
        procesar_pendiente(self.pendiente().pk)
        self.confirmar()
        respuesta = self.client.post(ruta, {"operacion_id": formulario.initial["operacion_id"],
            "contexto": formulario.initial["contexto"], "confirmar": "on"})
        self.assertContains(respuesta, "La receta cambió")
        self.assertEqual(EntregaReceta.objects.count(), 2)

    def test_entrega_previa_no_se_puede_convertir_en_no_entregada(self):
        r1, r2 = self.recetas_cierre
        previa = registrar_entrega(self.personal["tecnico"], r1.pk, uuid.uuid4())
        self.confirmar([], motivo="No se entregó la receta restante")
        self.assertEqual(DetalleCierre.objects.get(turno_receta=self.vinculos[0]).entrega_id, previa.pk)
        self.assertEqual(EntregaReceta.objects.count(), 1)
        self.assertEqual(CierreAtencion.objects.get().resultado, "con_entrega")
