"""RF-09-04, RF-09-06 y RF-09-14: orden manual del encargado, con versión, idempotencia, permisos y auditoría."""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from entregasapp.consultas import MANUAL, SUGERIDO, ruta_del_dia
from entregasapp.models import OrdenRuta, ParadaRuta
from entregasapp.services import MENSAJE_ORDEN_CAMBIO, mover_parada, registrar_entregada, restablecer_orden
from .ayudas import equipo, hoy, visita


def ids(ruta):
    return [parada.intento.pk for parada in ruta.paradas]


class OrdenManualTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        # Orden sugerido B (1 km), C (2 km), A (3 km); D sin coordenadas, al final.
        self.a, self.b, self.c = (visita(self.equipo, en) for en in ((0, 3), (0, 1), (0, 2)))
        self.d = visita(self.equipo, None)

    def ruta(self):
        return ruta_del_dia(self.encargado)

    def mover(self, intento, destino, version=None, operacion=None, actor=None):
        version = self.ruta().version if version is None else version
        return mover_parada(actor or self.encargado, intento.pk, destino, version, operacion or uuid.uuid4())

    def test_bajar_la_parada_1_guarda_el_orden_y_registrar_no_lo_recalcula(self):
        self.assertEqual(ids(self.ruta()), [self.b.pk, self.c.pk, self.a.pk, self.d.pk])
        orden = self.mover(self.b, "bajar")
        ruta = self.ruta()
        self.assertEqual(ruta.modo, MANUAL)
        self.assertEqual(ids(ruta), [self.c.pk, self.b.pk, self.a.pk, self.d.pk])
        self.assertEqual((ruta.version, orden.version), (1, 1))
        self.assertTrue(all(p.numerada for p in ruta.paradas))
        self.assertEqual(list(ParadaRuta.objects.filter(orden=orden).values_list("posicion", flat=True)), [1, 2, 3, 4])
        registrar_entregada(self.encargado, self.c.pk, uuid.uuid4())
        self.assertEqual(ids(self.ruta()), [self.b.pk, self.a.pk, self.d.pk])  # sin recálculo desde C

    def test_subir_y_mover_a_una_posicion(self):
        self.mover(self.a, "subir")
        self.assertEqual(ids(self.ruta()), [self.b.pk, self.a.pk, self.c.pk, self.d.pk])
        self.mover(self.c, "1")
        self.assertEqual(ids(self.ruta()), [self.c.pk, self.b.pk, self.a.pk, self.d.pk])
        self.mover(self.c, 4)
        ruta = self.ruta()
        self.assertEqual(ids(ruta), [self.b.pk, self.a.pk, self.d.pk, self.c.pk])
        self.assertEqual(ruta.version, 3)

    def test_mover_una_visita_sin_coordenadas_a_la_posicion_1(self):
        self.mover(self.d, "1")
        ruta = self.ruta()
        self.assertEqual(ids(ruta), [self.d.pk, self.b.pk, self.c.pk, self.a.pk])
        primera = ruta.paradas[0]
        self.assertEqual((primera.numero, primera.numerada, primera.punto), (1, True, None))
        self.assertEqual(ruta.sin_marcador, 1)

    def test_bordes_invalidos_se_rechazan_con_texto_y_sin_cambios(self):
        casos = ((self.b, "subir", "ya es la primera"), (self.d, "bajar", "ya es la última"),
                 (self.a, "0", "entre 1 y 4"), (self.a, "5", "entre 1 y 4"), (self.a, "arriba", "subir, bajar o una posición"))
        for intento, destino, texto in casos:
            with self.subTest(destino=destino), self.assertRaisesMessage(ValidationError, texto):
                self.mover(intento, destino)
        ajeno = visita(self.equipo, (0, 5), encargado=self.equipo["encargado2"])
        manana = visita(self.equipo, (0, 6), fecha=hoy() + timedelta(days=1))
        for intento in (ajeno, manana):
            with self.assertRaisesMessage(ValidationError, "ya no está en tu ruta"):
                self.mover(intento, "subir")
        with self.assertRaisesMessage(ValidationError, "La operación no es válida"):
            mover_parada(self.encargado, self.a.pk, "subir", 0, "no-es-uuid")
        self.assertFalse(OrdenRuta.objects.exists())
        self.assertFalse(RegistroAuditoria.objects.filter(accion="ruta.ordenada").exists())

    def test_el_mismo_post_no_mueve_dos_veces(self):
        operacion = uuid.uuid4()
        self.mover(self.a, "subir", version=0, operacion=operacion)
        primero = ids(self.ruta())
        self.mover(self.a, "subir", version=0, operacion=operacion)
        self.assertEqual(ids(self.ruta()), primero)
        self.assertEqual(self.ruta().version, 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="ruta.ordenada").count(), 1)

    def test_dos_guardados_desde_la_misma_version_uno_gana_y_el_otro_recibe_el_aviso(self):
        self.mover(self.a, "subir", version=0)
        with self.assertRaisesMessage(ValidationError, MENSAJE_ORDEN_CAMBIO):
            self.mover(self.c, "subir", version=0)  # primer guardado desde otro dispositivo
        self.mover(self.c, "subir", version=1)
        antes = ids(self.ruta())
        with self.assertRaisesMessage(ValidationError, MENSAJE_ORDEN_CAMBIO):
            self.mover(self.b, "bajar", version=1)
        with self.assertRaisesMessage(ValidationError, MENSAJE_ORDEN_CAMBIO):
            self.mover(self.b, "bajar", version="x")
        self.assertEqual(ids(self.ruta()), antes)
        self.assertEqual(self.ruta().version, 2)

    def test_al_dia_siguiente_vuelve_la_sugerencia(self):
        self.mover(self.d, "1")
        OrdenRuta.objects.update(fecha=hoy() - timedelta(days=1))
        ruta = self.ruta()
        self.assertEqual((ruta.modo, ruta.version), (SUGERIDO, 0))
        self.assertEqual(ids(ruta), [self.b.pk, self.c.pk, self.a.pk, self.d.pk])
        with self.assertRaisesMessage(ValidationError, MENSAJE_ORDEN_CAMBIO):
            self.mover(self.a, "subir", version=1)  # la página de ayer
        self.mover(self.a, "subir", version=0)
        self.assertEqual(OrdenRuta.objects.filter(fecha=hoy()).count(), 1)

    def test_volver_al_orden_sugerido(self):
        self.mover(self.d, "1")
        orden = restablecer_orden(self.encargado, 1, uuid.uuid4())
        ruta = self.ruta()
        self.assertEqual((ruta.modo, ruta.version, orden.version), (SUGERIDO, 2, 2))
        self.assertEqual(ids(ruta), [self.b.pk, self.c.pk, self.a.pk, self.d.pk])
        self.assertTrue(RegistroAuditoria.objects.filter(accion="ruta.restablecida", objeto_id=str(orden.pk)).exists())
        # Sin orden con paradas no hace nada; una versión vieja recibe el aviso.
        self.assertIsNone(restablecer_orden(self.encargado, 2, uuid.uuid4()))
        self.mover(self.a, "subir", version=2)
        with self.assertRaisesMessage(ValidationError, MENSAJE_ORDEN_CAMBIO):
            restablecer_orden(self.encargado, 2, uuid.uuid4())
        self.assertEqual(self.ruta().modo, MANUAL)

    def test_solo_el_encargado_reordena_su_ruta(self):
        self.mover(self.d, "1")
        antes = ids(self.ruta())
        for nombre in ("qf", "admin", "tecnico"):
            with self.subTest(actor=nombre):
                with self.assertRaises(PermissionDenied):
                    mover_parada(self.equipo[nombre], self.a.pk, "subir", 1, uuid.uuid4())
                with self.assertRaises(PermissionDenied):
                    restablecer_orden(self.equipo[nombre], 1, uuid.uuid4())
        # Otro encargado solo actúa sobre su propia ruta: la visita ajena no está en ella.
        with self.assertRaisesMessage(ValidationError, "ya no está en tu ruta"):
            mover_parada(self.equipo["encargado2"], self.a.pk, "subir", 0, uuid.uuid4())
        self.assertIsNone(restablecer_orden(self.equipo["encargado2"], 1, uuid.uuid4()))
        self.assertEqual(OrdenRuta.objects.count(), 1)
        self.assertEqual(ids(self.ruta()), antes)

    def test_la_auditoria_no_tiene_datos_personales_y_si_falla_se_revierte(self):
        self.mover(self.a, "subir")
        restablecer_orden(self.encargado, 1, uuid.uuid4())
        paciente = self.a.entrega.paciente
        for registro in RegistroAuditoria.objects.filter(accion__startswith="ruta."):
            texto = " ".join((registro.accion, registro.objeto_tipo, registro.objeto_id))
            self.assertEqual(registro.objeto_tipo, "entregasapp.OrdenRuta")
            for dato in (paciente.rut, paciente.nombres, paciente.apellidos, "Camino sintético", "-36.", "-72."):
                self.assertNotIn(dato, texto)
        antes = (ids(self.ruta()), self.ruta().version)
        with patch("entregasapp.services.auditar", side_effect=RuntimeError("auditoría")), self.assertRaises(RuntimeError):
            self.mover(self.b, "bajar")
        self.assertEqual((ids(self.ruta()), self.ruta().version), antes)
        self.mover(self.c, "subir")
        with patch("entregasapp.services.auditar", side_effect=RuntimeError("auditoría")), self.assertRaises(RuntimeError):
            restablecer_orden(self.encargado, self.ruta().version, uuid.uuid4())
        self.assertEqual(self.ruta().modo, MANUAL)
