"""RF-08-15: operaciones simultáneas con hilos y conexiones reales independientes.

Cada escenario lanza solicitudes que esperan juntas en una barrera y luego compiten por la base. Las garantías
salen de las restricciones y de los UPDATE condicionales, no de `select_for_update()`.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from entregasapp.models import Domicilio, Entrega, IntentoEntrega, RecetaEntrega
from entregasapp.services import (
    guardar_domicilio, inscribir_excepcion, programar_entrega, reasignar, registrar_entregada, registrar_no_entregada,
)
from recetasapp.models import EntregaReceta, Receta
from recetasapp.services import registrar_entrega
from turnosapp.models import Turno, TurnoReceta
from turnosapp.services import ErrorEmision, emitir_turno
from .ayudas import equipo, hoy, paciente, receta

DATOS = {"sector": "rojo", "localidad": "Dadinco", "direccion": "Camino a Dadinco km 2", "referencias": "Casa roja"}


class ConcurrenciaRepartoTests(TransactionTestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.encargado = self.equipo["encargado"]

    def competir(self, operaciones):
        barrera = Barrier(len(operaciones))

        def ejecutar(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    return funcion()
                except (ValidationError, PermissionDenied) as error:
                    return error
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operaciones)) as pool:
            return list(pool.map(ejecutar, operaciones))

    def programar(self, persona, operacion=None, encargado=None):
        return programar_entrega(self.qf, persona.pk, hoy(), (encargado or self.encargado).pk, operacion or uuid.uuid4())

    def sin_receta_en_turno_y_despacho(self):
        activas = set(TurnoReceta.objects.filter(turno__estado__in=("esperando", "llamado")).values_list("receta_id", flat=True))
        abiertas = set(RecetaEntrega.objects.filter(entrega__estado__in=Entrega.ABIERTAS).values_list("receta_id", flat=True))
        self.assertFalse(activas & abiertas)

    def test_1_programaciones_simultaneas_dejan_una_sola_entrega_abierta(self):
        persona = paciente(edad=85)
        receta(persona)
        misma = uuid.uuid4()
        resultados = self.competir([lambda: self.programar(persona)] * 3 + [lambda: self.programar(persona, misma)] * 2)
        creadas = {r.pk for r in resultados if isinstance(r, Entrega)}
        self.assertEqual(len(creadas), 1)
        self.assertEqual(Entrega.objects.filter(estado__in=Entrega.ABIERTAS).count(), 1)
        self.assertEqual(IntentoEntrega.objects.count(), 1)
        self.assertEqual(RecetaEntrega.objects.count(), 1)
        rechazos = [r for r in resultados if isinstance(r, ValidationError)]
        self.assertTrue(all("entrega a domicilio abierta" in r.messages[0] for r in rechazos))

    def test_2_totem_frente_a_programacion_de_una_excepcion(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                persona = paciente(edad=60, cronico=True)
                inscribir_excepcion(self.qf, persona.pk, "sin_red_apoyo")
                receta(persona)
                receta(persona)
                resultados = self.competir([
                    lambda: emitir_turno(persona.rut, uuid.uuid4()),
                    lambda: self.programar(persona),
                    lambda: emitir_turno(persona.rut, uuid.uuid4()),
                ])
                self.sin_receta_en_turno_y_despacho()
                ganadores = [r for r in resultados if not isinstance(r, Exception)]
                self.assertTrue(ganadores)
                for resultado in resultados:
                    if isinstance(resultado, ErrorEmision):
                        self.assertEqual(resultado.code, "despacho_abierto")
                self.assertLessEqual(Turno.objects.filter(paciente=persona, estado__in=("esperando", "llamado")).count(), 1)
                self.assertLessEqual(Entrega.objects.filter(paciente=persona, estado__in=Entrega.ABIERTAS).count(), 1)

    def test_3_doble_toque_o_dos_dispositivos_registran_un_solo_resultado(self):
        persona = paciente(edad=90)
        unica = receta(persona)
        intento = self.programar(persona).intentos.get()
        misma = uuid.uuid4()
        resultados = self.competir([
            lambda: registrar_entregada(self.encargado, intento.pk, misma),
            lambda: registrar_entregada(self.encargado, intento.pk, misma),
            lambda: registrar_entregada(self.encargado, intento.pk, uuid.uuid4()),
            lambda: registrar_no_entregada(self.encargado, intento.pk, "sin_receptor", "", uuid.uuid4()),
        ])
        intento.refresh_from_db()
        unica.refresh_from_db()
        exitosos = [r for r in resultados if not isinstance(r, Exception)]
        self.assertTrue(exitosos)
        self.assertEqual(len({r.intento.operacion_id for r in exitosos}), 1)
        self.assertEqual(sum(not r.repetido for r in exitosos), 1)
        if intento.resultado == "entregada":
            self.assertEqual(unica.entregas_completadas, 1)
            self.assertEqual(EntregaReceta.objects.count(), 1)
        else:
            self.assertEqual(intento.resultado, "no_entregada")
            self.assertEqual(unica.entregas_completadas, 0)

    def test_4_entregada_frente_a_la_ventanilla_en_el_ultimo_cupo(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                persona = paciente(edad=60, cronico=True)
                inscribir_excepcion(self.qf, persona.pk, "discapacidad")
                ultima = receta(persona, maximo=3, completadas=2)
                intento = self.programar(persona).intentos.get()
                self.competir([
                    lambda: registrar_entregada(self.encargado, intento.pk, uuid.uuid4()),
                    lambda: registrar_entrega(self.equipo["tecnico"], ultima.pk, uuid.uuid4()),
                    lambda: registrar_entrega(self.equipo["tecnico"], ultima.pk, uuid.uuid4()),
                ])
                ultima.refresh_from_db()
                self.assertEqual(ultima.entregas_completadas, 3)
                self.assertEqual(ultima.entregas.count(), 1)
                self.assertEqual(ultima.entregas.get().creado_por, self.encargado)
                self.assertEqual(RecetaEntrega.objects.get(receta=ultima).resultado, "descontada")

    def test_5_reasignar_frente_a_registrar_deja_un_solo_ganador(self):
        for vuelta, registrar in enumerate((
            lambda intento: registrar_entregada(self.encargado, intento.pk, uuid.uuid4()),
            lambda intento: registrar_no_entregada(self.encargado, intento.pk, "rechazo", "", uuid.uuid4()),
            lambda intento: registrar_entregada(self.encargado, intento.pk, uuid.uuid4()),
        )):
            with self.subTest(vuelta=vuelta):
                persona = paciente(edad=90)
                unica = receta(persona)
                entrega = self.programar(persona)
                intento = entrega.intentos.get()
                resultados = self.competir([
                    lambda: registrar(intento),
                    lambda: reasignar(self.qf, entrega.pk, fecha=hoy(), encargado_id=self.equipo["encargado2"].pk,
                                      intento_id=intento.pk, operacion_id=uuid.uuid4(), resultado_visto="pendiente"),
                ])
                ganadores = [r for r in resultados if not isinstance(r, Exception)]
                perdedores = [r for r in resultados if isinstance(r, ValidationError)]
                self.assertEqual((len(ganadores), len(perdedores)), (1, 1))
                self.assertTrue(perdedores[0].messages[0])
                intento.refresh_from_db()
                unica.refresh_from_db()
                if isinstance(ganadores[0], IntentoEntrega):  # ganó la reasignación
                    self.assertEqual(intento.resultado, "reasignado")
                    self.assertEqual(unica.entregas_completadas, 0)
                    self.assertEqual(entrega.intentos.count(), 2)
                else:
                    self.assertIn(intento.resultado, ("entregada", "no_entregada"))
                    self.assertEqual(entrega.intentos.count(), 1)
                self.assertLessEqual(IntentoEntrega.objects.filter(entrega=entrega, resultado="pendiente").count(), 1)

    def test_6_dos_ediciones_del_mismo_domicilio_no_se_pierden_en_silencio(self):
        persona = paciente(edad=85)
        domicilio = guardar_domicilio(self.encargado, persona.pk, DATOS)
        resultados = self.competir([
            lambda: guardar_domicilio(self.encargado, persona.pk, {**DATOS, "referencias": "Portón azul"}, version=1),
            lambda: guardar_domicilio(self.qf, persona.pk, {**DATOS, "referencias": "Casa con parrón"}, version=1),
            lambda: guardar_domicilio(self.equipo["encargado2"], persona.pk, {**DATOS, "referencias": "Frente a la escuela"}, version=1),
        ])
        guardados = [r for r in resultados if isinstance(r, Domicilio)]
        rechazos = [r for r in resultados if isinstance(r, ValidationError)]
        self.assertEqual((len(guardados), len(rechazos)), (1, 2))
        self.assertTrue(all(r.messages == ["El domicilio cambió; revisa los datos nuevos."] for r in rechazos))
        domicilio.refresh_from_db()
        self.assertEqual((domicilio.version, domicilio.referencias), (2, guardados[0].referencias))

    def test_6b_dos_creaciones_simultaneas_del_mismo_domicilio(self):
        persona = paciente(edad=85)
        resultados = self.competir([
            lambda: guardar_domicilio(self.encargado, persona.pk, {**DATOS, "referencias": "Primera"}),
            lambda: guardar_domicilio(self.qf, persona.pk, {**DATOS, "referencias": "Segunda"}),
        ])
        self.assertEqual(Domicilio.objects.filter(paciente=persona).count(), 1)
        self.assertEqual(sum(isinstance(r, Domicilio) for r in resultados), 1)
        self.assertEqual(sum(isinstance(r, ValidationError) for r in resultados), 1)
        self.assertEqual(Receta.objects.count(), 0)
