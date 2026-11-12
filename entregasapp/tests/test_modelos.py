"""Restricciones de la base del reparto: cada regla de integridad tiene su prueba (T-08-01)."""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from entregasapp.models import (
    Domicilio, Entrega, FotoDomicilio, InscripcionReparto, IntentoEntrega, OrdenRuta, ParadaRuta, RecetaEntrega,
)
from recetasapp.models import EntregaReceta
from .ayudas import cuenta, hoy, paciente, receta


class RestriccionesTests(TestCase):
    def setUp(self):
        self.usuario = cuenta("modelos_reparto")
        self.paciente = paciente()
        self.receta = receta(self.paciente)

    def rechaza(self, crear):
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear()

    def domicilio(self, **datos):
        valores = {"paciente": self.paciente, "direccion": "Camino a Dadinco km 2", **datos}
        return Domicilio.objects.create(**valores)

    def entrega(self, **datos):
        return Entrega.objects.create(paciente=self.paciente, operacion_id=uuid.uuid4(), **datos)

    def test_domicilio_uno_por_paciente_y_direccion_presente(self):
        self.rechaza(lambda: self.domicilio(direccion=""))
        self.domicilio()
        self.rechaza(lambda: self.domicilio())

    def test_domicilio_coordenadas_juntas_en_rango_y_precision_solo_con_ellas(self):
        self.rechaza(lambda: self.domicilio(latitud=Decimal("-36.5")))
        self.rechaza(lambda: self.domicilio(latitud=Decimal("-91"), longitud=Decimal("-72")))
        self.rechaza(lambda: self.domicilio(latitud=Decimal("-36"), longitud=Decimal("181")))
        self.rechaza(lambda: self.domicilio(precision_metros=8))
        self.rechaza(lambda: self.domicilio(sector="gris"))
        domicilio = self.domicilio(latitud=Decimal("-36.512345"), longitud=Decimal("-72.211234"), precision_metros=8)
        domicilio.refresh_from_db()
        self.assertEqual(domicilio.latitud, Decimal("-36.512345"))

    def test_domicilio_verificacion_completa_y_con_sector(self):
        self.rechaza(lambda: self.domicilio(sector="verde", verificado_en=timezone.now()))
        self.rechaza(lambda: self.domicilio(sector="verde", verificado_por=self.usuario))
        self.rechaza(lambda: self.domicilio(verificado_en=timezone.now(), verificado_por=self.usuario))
        self.rechaza(lambda: self.domicilio(version=0))
        self.domicilio(sector="verde", verificado_en=timezone.now(), verificado_por=self.usuario)

    def test_fotos_posicion_unica_entre_1_y_3_y_descripcion_obligatoria(self):
        domicilio = self.domicilio()
        def foto(posicion, descripcion="Portón verde"):
            return FotoDomicilio.objects.create(domicilio=domicilio, posicion=posicion, archivo=f"domicilios/{uuid.uuid4().hex}.jpg",
                                                descripcion=descripcion, ancho=10, alto=10, bytes=100)
        for posicion in (1, 2, 3):
            foto(posicion)
        self.rechaza(lambda: foto(4))
        self.rechaza(lambda: foto(0))
        self.rechaza(lambda: foto(2))
        FotoDomicilio.objects.filter(posicion=3).delete()
        self.rechaza(lambda: foto(3, descripcion=""))

    def test_una_inscripcion_vigente_por_paciente_y_nota_con_otro(self):
        InscripcionReparto.objects.create(paciente=self.paciente, motivo="discapacidad")
        self.rechaza(lambda: InscripcionReparto.objects.create(paciente=self.paciente, motivo="sin_red_apoyo"))
        InscripcionReparto.objects.update(retirada_en=timezone.now(), retirada_por=self.usuario)
        self.rechaza(lambda: InscripcionReparto.objects.create(paciente=self.paciente, motivo="otro"))
        self.rechaza(lambda: InscripcionReparto.objects.create(paciente=self.paciente, motivo="inventado"))
        self.rechaza(lambda: InscripcionReparto.objects.create(paciente=self.paciente, motivo="discapacidad", retirada_en=timezone.now()))
        InscripcionReparto.objects.create(paciente=self.paciente, motivo="otro", nota="Cuidadora con turno nocturno")

    def test_una_entrega_abierta_por_paciente(self):
        primera = self.entrega()
        self.rechaza(lambda: self.entrega())
        self.rechaza(lambda: self.entrega(estado="pendiente_gestion"))
        Entrega.objects.filter(pk=primera.pk).update(estado="entregada", cerrada_en=timezone.now())
        self.entrega(estado="pendiente_gestion")

    def test_entrega_cierre_y_anulacion_coherentes(self):
        self.rechaza(lambda: self.entrega(estado="entregada"))
        self.rechaza(lambda: self.entrega(cerrada_en=timezone.now()))
        self.rechaza(lambda: self.entrega(estado="anulada", cerrada_en=timezone.now(), anulada_por=self.usuario))
        self.rechaza(lambda: self.entrega(estado="anulada", cerrada_en=timezone.now(), motivo_anulacion="otro", anulada_por=self.usuario))
        self.rechaza(lambda: self.entrega(motivo_anulacion="retirara_farmacia"))
        self.rechaza(lambda: self.entrega(estado="cancelada"))
        self.entrega(estado="anulada", cerrada_en=timezone.now(), motivo_anulacion="retirara_farmacia", anulada_por=self.usuario)

    def test_intentos_numero_unico_un_pendiente_y_registro_coherente(self):
        entrega = self.entrega()
        def intento(numero, **datos):
            return IntentoEntrega.objects.create(entrega=entrega, numero=numero, fecha_programada=hoy(), encargado=self.usuario, **datos)
        primero = intento(1)
        self.rechaza(lambda: intento(2))  # dos pendientes
        self.rechaza(lambda: intento(0, resultado="reasignado", registrado_en=timezone.now(), registrado_por=self.usuario, operacion_id=uuid.uuid4()))
        registro = {"registrado_en": timezone.now(), "registrado_por": self.usuario, "operacion_id": uuid.uuid4()}
        self.rechaza(lambda: intento(1, resultado="reasignado", **registro))  # número repetido
        self.rechaza(lambda: intento(2, resultado="no_entregada", **registro))  # sin motivo
        self.rechaza(lambda: intento(2, resultado="no_entregada", motivo="otro", **registro))  # «Otro» sin nota
        self.rechaza(lambda: intento(2, resultado="entregada", motivo="rechazo", **registro))  # motivo sin no entrega
        self.rechaza(lambda: intento(2, resultado="entregada", nota="Sin motivo", **registro))
        self.rechaza(lambda: intento(2, resultado="entregada"))  # resultado sin registro
        self.rechaza(lambda: intento(2, resultado="perdida", **registro))
        IntentoEntrega.objects.filter(pk=primero.pk).update(resultado="no_entregada", motivo="sin_receptor", **registro)
        self.rechaza(lambda: intento(2, resultado="entregada", registrado_en=timezone.now(), registrado_por=self.usuario,
                                     operacion_id=registro["operacion_id"]))  # identificador de operación repetido
        intento(2)

    def test_receta_de_entrega_descuento_causa_y_revision_coherentes(self):
        entrega = self.entrega()
        def vinculo(**datos):
            return RecetaEntrega.objects.create(entrega=entrega, receta=self.receta, **datos)
        self.rechaza(lambda: vinculo(resultado="descontada"))
        self.rechaza(lambda: vinculo(resultado="no_descontada"))
        self.rechaza(lambda: vinculo(causa="La receta está vencida; requiere renovación."))
        self.rechaza(lambda: vinculo(revisada_en=timezone.now(), revisada_por=self.usuario))
        self.rechaza(lambda: vinculo(resultado="no_descontada", causa="Vencida", revisada_en=timezone.now()))
        entrega_receta = EntregaReceta.objects.create(receta=self.receta, numero=1)
        self.rechaza(lambda: vinculo(entrega_receta=entrega_receta))
        vinculo(resultado="descontada", entrega_receta=entrega_receta)
        self.rechaza(lambda: vinculo())  # la misma receta dos veces en una entrega


class OrdenRutaRestriccionesTests(TestCase):
    """Spec 09 (T-09-03): un orden por encargado y día; cada intento y cada posición una sola vez por orden."""

    def setUp(self):
        self.encargado = cuenta("modelos_ruta")
        self.otro = cuenta("modelos_ruta_2")
        self.intentos = []
        for _ in range(2):
            entrega = Entrega.objects.create(paciente=paciente(), operacion_id=uuid.uuid4())
            self.intentos.append(IntentoEntrega.objects.create(entrega=entrega, numero=1, fecha_programada=hoy(),
                                                               encargado=self.encargado))

    def rechaza(self, crear):
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear()

    def test_un_orden_por_encargado_y_dia_con_version_positiva(self):
        OrdenRuta.objects.create(encargado=self.encargado, fecha=hoy())
        self.rechaza(lambda: OrdenRuta.objects.create(encargado=self.encargado, fecha=hoy()))
        self.rechaza(lambda: OrdenRuta.objects.create(encargado=self.otro, fecha=hoy(), version=0))
        OrdenRuta.objects.create(encargado=self.otro, fecha=hoy())
        OrdenRuta.objects.create(encargado=self.encargado, fecha=hoy() + timedelta(days=1))
        self.assertEqual(OrdenRuta.objects.count(), 3)

    def test_parada_intento_y_posicion_unicos_y_posicion_desde_1(self):
        orden = OrdenRuta.objects.create(encargado=self.encargado, fecha=hoy())
        primero, segundo = self.intentos
        ParadaRuta.objects.create(orden=orden, intento=primero, posicion=1)
        self.rechaza(lambda: ParadaRuta.objects.create(orden=orden, intento=primero, posicion=2))
        self.rechaza(lambda: ParadaRuta.objects.create(orden=orden, intento=segundo, posicion=1))
        self.rechaza(lambda: ParadaRuta.objects.create(orden=orden, intento=segundo, posicion=0))
        ParadaRuta.objects.create(orden=orden, intento=segundo, posicion=2)
        self.assertEqual([p.intento_id for p in orden.paradas.all()], [primero.pk, segundo.pk])

    def test_vaciar_el_orden_no_toca_los_intentos_y_un_intento_con_parada_no_se_borra(self):
        orden = OrdenRuta.objects.create(encargado=self.encargado, fecha=hoy())
        ParadaRuta.objects.create(orden=orden, intento=self.intentos[0], posicion=1)
        with self.assertRaises(ProtectedError):
            self.intentos[0].delete()
        orden.delete()
        self.assertEqual(ParadaRuta.objects.count(), 0)
        self.assertEqual(IntentoEntrega.objects.count(), 2)
