"""Emisores simultáneos con conexiones reales independientes."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from entregasapp.services import programar_entrega
from entregasapp.tests.ayudas import equipo
from recetasapp.models import Paciente, Receta
from recetasapp.services import registrar_entrega
from recetasapp.tests.ayudas import actores, cargar

from coreapp.models import RegistroAuditoria
from turnosapp.models import Turno, ContadorTurnosDiario, TurnoReceta
from turnosapp.services import CODIGO_RECHAZO, MENSAJE_NEUTRO, ErrorEmision, emitir_turno
from . import test_servicios as preparacion


class ConcurrenciaTurnosTests(TransactionTestCase):
    setUp = preparacion.EmisionTests.setUp
    pacientes = preparacion.EmisionTests.pacientes
    recetas = preparacion.EmisionTests.recetas

    def competir(self, solicitudes):
        barrera = Barrier(len(solicitudes))
        def ejecutar(solicitud):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return solicitud() if callable(solicitud) else emitir_turno(*solicitud)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(solicitudes)) as pool:
            return list(pool.map(ejecutar, solicitudes))

    def verificar(self, cantidad):
        self.assertEqual(Turno.objects.count(), cantidad)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="turno.emitido").count(), cantidad)
        self.assertEqual(ContadorTurnosDiario.objects.get().ultimo_numero, cantidad)
        self.assertEqual(len(set(Turno.objects.values_list("fecha", "numero"))), cantidad)
        self.assertTrue(all(t.recetas_vinculadas.count() == 1 for t in Turno.objects.all()))

    def test_mismo_uuid_tres_emisores(self):
        operacion = uuid.uuid4()
        resultados = self.competir([(self.paciente.rut, operacion)] * 3)
        self.assertEqual({r.numero for r in resultados}, {1})
        self.verificar(1)

    def test_distintos_uuid_mismo_paciente(self):
        resultados = self.competir([(self.paciente.rut, uuid.uuid4()) for _ in range(3)])
        self.assertEqual({r.numero for r in resultados}, {1})
        self.verificar(1)

    def test_tres_pacientes_compiten_por_serie(self):
        pacientes = [self.paciente, self.pacientes(1), self.pacientes(2)]
        for indice, paciente in enumerate(pacientes[1:]):
            self.recetas(paciente, f"CONCURRENTE-{indice}")
        resultados = self.competir([(p.rut, uuid.uuid4()) for p in pacientes])
        self.assertEqual({r.numero for r in resultados}, {1, 2, 3})
        self.verificar(3)

    def test_emision_compite_con_entrega_sin_consumir_otro_cupo(self):
        personal = actores()
        self.competir([
            (self.paciente.rut, uuid.uuid4()),
            lambda: registrar_entrega(personal["tecnico"], self.receta.pk, uuid.uuid4()),
        ])
        self.verificar(1)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 1)
        self.assertEqual(self.receta.entregas.count(), 1)

    def test_emision_compite_con_importacion_sin_duplicar_recetas(self):
        personal = actores()
        p, r = self.paciente, self.receta
        fila = [p.rut, p.nombres, p.apellidos, p.fecha_nacimiento.isoformat(), "0", "0", "", "",
                r.codigo, r.fecha_inicio.isoformat(), "1", "3"]
        resultados = self.competir([
            (p.rut, uuid.uuid4()), lambda: cargar(personal["qf"], [fila]),
        ])
        self.assertEqual(resultados[1].estado, "completada")
        self.verificar(1)
        self.assertEqual(Receta.objects.count(), 1)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 0)


class ConcurrenciaEnmiendaTests(TransactionTestCase):
    """Enmienda 04 del 2026-11-15: tótem abierto, series por letra y despacho abierto."""

    setUp = preparacion.EmisionTests.setUp
    pacientes = preparacion.EmisionTests.pacientes
    recetas = preparacion.EmisionTests.recetas
    competir = ConcurrenciaTurnosTests.competir

    def capturar(self, rut, operacion=None):
        def solicitud():
            try:
                return emitir_turno(rut, operacion or uuid.uuid4())
            except ErrorEmision as error:
                return error
        return solicitud

    def sin_duplicados(self):
        claves = list(Turno.objects.values_list("fecha", "letra", "numero"))
        self.assertEqual(len(claves), len(set(claves)))
        activos = list(Turno.objects.filter(estado__in=["esperando", "llamado"]).values_list("rut", "fecha"))
        self.assertEqual(len(activos), len(set(activos)))
        for letra, ultimo in ContadorTurnosDiario.objects.values_list("letra", "ultimo_numero"):
            numeros = sorted(Turno.objects.filter(letra=letra).values_list("numero", flat=True))
            self.assertEqual(numeros, list(range(1, ultimo + 1)), letra)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="turno.emitido").count(), Turno.objects.count())

    def test_mismo_rut_fuera_del_padron_con_uuid_distintos(self):
        rut = self.ruts[7]
        resultados = self.competir([self.capturar(rut) for _ in range(5)])
        self.assertFalse([r for r in resultados if isinstance(r, Exception)])
        self.assertEqual({r.codigo for r in resultados}, {"G-001"})
        self.assertEqual(sum(not r.recuperado for r in resultados), 1)
        turno = Turno.objects.get()
        self.assertIsNone(turno.paciente_id)
        self.assertFalse(turno.recetas_vinculadas.exists())
        self.assertFalse(Paciente.objects.filter(rut=rut).exists())
        self.sin_duplicados()

    def test_letras_distintas_en_paralelo_sin_choques_por_serie(self):
        cronicos = [self.pacientes(i) for i in (1, 2, 3)]
        mayores = [self.pacientes(i) for i in (4, 5)]
        Paciente.objects.filter(pk__in=[p.pk for p in cronicos]).update(es_cronico=True)
        Paciente.objects.filter(pk__in=[p.pk for p in mayores]).update(fecha_nacimiento=date(1944, 5, 5))
        Paciente.objects.filter(pk=self.paciente.pk).update(es_postrado=True)  # P aunque tenga 56 años
        for indice, persona in enumerate(cronicos + mayores):
            self.recetas(persona, f"LETRAS-{indice}")
        ruts = [p.rut for p in cronicos + mayores + [self.paciente]] + [self.ruts[8], self.ruts[9]]
        resultados = self.competir([self.capturar(rut) for rut in ruts])
        self.assertFalse([r for r in resultados if isinstance(r, Exception)])
        por_letra = {}
        for resultado in resultados:
            por_letra.setdefault(resultado.letra, set()).add(resultado.numero)
        self.assertEqual(por_letra, {"C": {1, 2, 3}, "P": {1, 2, 3}, "G": {1, 2}})
        self.assertEqual(dict(ContadorTurnosDiario.objects.values_list("letra", "ultimo_numero")), {"C": 3, "P": 3, "G": 2})
        self.assertEqual(Turno.objects.filter(paciente__isnull=True).count(), 2)
        self.sin_duplicados()

    def test_despacho_abierto_mezclado_con_emisiones(self):
        personal = equipo()
        reparto = Paciente.objects.create(rut=self.ruts[6], nombres="Paciente sintético", apellidos="Despacho",
                                          fecha_nacimiento=date(1940, 3, 3))
        receta_reparto = self.recetas(reparto, "DESPACHO-CONC")
        programar_entrega(personal["qf"], reparto.pk, self.fecha, personal["encargado"].pk, uuid.uuid4())
        mayores = [self.pacientes(i) for i in (1, 2)]
        Paciente.objects.filter(pk__in=[p.pk for p in mayores]).update(fecha_nacimiento=date(1945, 1, 1))
        for indice, persona in enumerate(mayores):
            self.recetas(persona, f"MEZCLA-{indice}")
        solicitudes = [self.capturar(reparto.rut), self.capturar(mayores[0].rut), self.capturar(reparto.rut),
                       self.capturar(mayores[1].rut), self.capturar(self.paciente.rut), self.capturar(self.ruts[9])]
        resultados = self.competir(solicitudes)
        for indice in (0, 2):
            self.assertIsInstance(resultados[indice], ErrorEmision)
            self.assertEqual((resultados[indice].code, resultados[indice].messages), (CODIGO_RECHAZO, [MENSAJE_NEUTRO]))
        emitidos = [r for i, r in enumerate(resultados) if i not in (0, 2)]
        self.assertFalse([r for r in emitidos if isinstance(r, Exception)])
        self.assertEqual(sorted(r.codigo for r in emitidos), ["G-001", "G-002", "P-001", "P-002"])
        self.assertFalse(Turno.objects.filter(rut=reparto.rut).exists())
        self.assertFalse(TurnoReceta.objects.filter(receta=receta_reparto).exists())
        self.assertEqual(ContadorTurnosDiario.objects.get(fecha=self.fecha, letra="P").ultimo_numero, 2)
        self.sin_duplicados()
