"""Cuatro carreras reales con barrera, hilos y conexiones independientes."""
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.management import call_command
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from turnosapp.atencion import iniciar_automatico, rellamar
from turnosapp.cola import procesar_pendiente
from turnosapp.models import AnuncioSala, EventoTurno, Turno
from .datos_cola import DatosCola


class ConcurrenciaSalaTests(DatosCola, TransactionTestCase):
    def competir(self, funciones):
        barrera = Barrier(len(funciones))

        def ejecutar(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return funcion()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(funciones)) as pool:
            return list(pool.map(ejecutar, funciones))

    def comprobar_anuncios(self, cantidad):
        anuncios = list(AnuncioSala.objects.select_related("evento").order_by("id"))
        self.assertEqual(len(anuncios), cantidad)
        ids = [a.pk for a in anuncios]
        self.assertTrue(all(a < b for a, b in zip(ids, ids[1:])))
        self.assertEqual(len({a.evento_id for a in anuncios}), cantidad)
        self.assertSetEqual({a.evento_id for a in anuncios},
            set(EventoTurno.objects.filter(accion__in=["llamado", "rellamado"]).values_list("pk", flat=True)))
        for anuncio in anuncios:
            self.assertEqual(anuncio.numero, anuncio.evento.turno.numero)
            self.assertEqual(anuncio.ventanilla_numero, anuncio.evento.ventanilla.numero)

    def test_cuatro_ventanillas_y_cuatro_planificadores(self):
        for numero in range(1, 5):
            self.activar(numero)
            self.turno()
        pendientes = [self.pendiente().pk for _ in range(4)]
        resultados = self.competir([lambda pk=pk: procesar_pendiente(pk) for pk in pendientes])
        self.assertEqual(sum(resultados), 4)
        self.assertEqual(Turno.objects.filter(estado="llamado").values("ventanilla").distinct().count(), 4)
        self.comprobar_anuncios(4)

    def test_tres_reenvios_simultaneos_del_mismo_rellamado(self):
        self.activar()
        turno = self.turno()
        procesar_pendiente(self.pendiente().pk)
        identidad = uuid.uuid4()
        resultados = self.competir([
            lambda: rellamar(self.personal["tecnico"], turno.pk, identidad)
        ] * 3)
        self.assertTrue(all(r == resultados[0] for r in resultados))
        self.assertEqual(AnuncioSala.objects.filter(accion="rellamado").count(), 1)
        self.comprobar_anuncios(2)

    def test_lectura_concurrente_no_ve_anuncio_sin_evento_confirmado(self):
        self.activar()
        self.turno()
        pendiente = self.pendiente()

        def leer():
            return list(AnuncioSala.objects.values_list("evento__accion", "evento__turno__estado"))

        resultados = self.competir([lambda: procesar_pendiente(pendiente.pk), leer])
        self.assertIn(resultados[1], [[], [("llamado", "llamado")]])
        self.comprobar_anuncios(1)

    def test_comando_y_accion_manual_comparten_registro(self):
        ventanilla = self.activar()
        self.turno()
        self.pendiente()
        self.competir([
            lambda: call_command("procesar_cola", stdout=io.StringIO()),
            lambda: iniciar_automatico(self.personal["tecnico"], ventanilla.pk, uuid.uuid4()),
        ])
        self.comprobar_anuncios(1)
