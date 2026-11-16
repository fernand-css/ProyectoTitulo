"""RF-08-15: operaciones simultáneas con hilos y conexiones reales independientes.

Cada escenario lanza solicitudes que esperan juntas en una barrera y luego compiten por la base. Las garantías
salen de las restricciones y de los UPDATE condicionales, no de `select_for_update()`.
"""

import uuid
from pathlib import PurePosixPath as Path_
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from entregasapp.models import Domicilio, Entrega, FotoDomicilio, IntentoEntrega, RecetaEntrega
from coreapp.roles import JEFA
from entregasapp.services import (
    MENSAJE_FOTOS_CAMBIARON, FotoNueva, gestionar_fotos,
    OMITIDO_ABIERTA, OMITIDO_SIN_RECETAS, guardar_domicilio, inscribir_excepcion, programar_entrega, programar_lote,
    reasignar, registrar_entregada, registrar_no_entregada,
)
from recetasapp.models import EntregaReceta, Receta
from recetasapp.services import registrar_entrega
from turnosapp.models import Turno, TurnoReceta
from turnosapp.services import CODIGO_RECHAZO, ErrorEmision, emitir_turno
from .ayudas import archivo, cuenta, equipo, hoy, imagen, paciente, receta

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
                        self.assertEqual(resultado.code, CODIGO_RECHAZO)
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

    # Programación de varios (RF-08-17, ampliación del 2026-11-13) --------------------------------------------------

    def lote(self, ids, lote_id=None, actor=None, encargado=None):
        return programar_lote(actor or self.qf, ids, hoy(), (encargado or self.encargado).pk, lote_id or uuid.uuid4())

    def una_abierta_por_paciente(self, personas):
        for persona in personas:
            self.assertEqual(Entrega.objects.filter(paciente=persona, estado__in=Entrega.ABIERTAS).count(), 1)
            self.assertEqual(IntentoEntrega.objects.filter(entrega__paciente=persona).count(), 1)

    def test_7_dos_lotes_con_pacientes_en_comun_al_mismo_tiempo(self):
        otra_qf = cuenta("otra_qf_concurrencia", JEFA)
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                personas = [paciente(edad=85) for _ in range(6)]
                for persona in personas:
                    receta(persona)
                primero, segundo = [p.pk for p in personas[:4]], [p.pk for p in reversed(personas[2:])]
                resultados = self.competir([
                    lambda: self.lote(primero),
                    lambda: self.lote(segundo, actor=otra_qf, encargado=self.equipo["encargado2"]),
                ])
                self.una_abierta_por_paciente(personas)
                for comun in (personas[2].pk, personas[3].pk):
                    estados = [next(r for r in resultado if r.paciente_id == comun) for resultado in resultados]
                    self.assertEqual(sorted(r.programado for r in estados), [False, True])
                    self.assertEqual([r.motivo for r in estados if not r.programado], [OMITIDO_ABIERTA])

    def test_8_el_mismo_tramo_enviado_dos_veces_a_la_vez(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                personas = [paciente(edad=85) for _ in range(5)]
                for persona in personas:
                    receta(persona)
                ids, lote_id = [p.pk for p in personas], uuid.uuid4()
                resultados = self.competir([lambda: self.lote(ids, lote_id)] * 2)
                self.una_abierta_por_paciente(personas)
                for resultado in resultados:
                    self.assertTrue(all(r.programado for r in resultado), resultado)
                self.assertEqual([r.entrega_id for r in resultados[0]], [r.entrega_id for r in resultados[1]])

    def test_9_lote_frente_al_totem_de_una_excepcion_del_lote(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                excepcion = paciente(edad=60, cronico=True)
                inscribir_excepcion(self.qf, excepcion.pk, "sin_red_apoyo")
                receta(excepcion)
                receta(excepcion)
                otros = [paciente(edad=85) for _ in range(3)]
                for persona in otros:
                    receta(persona)
                ids = [otros[0].pk, excepcion.pk, otros[1].pk, otros[2].pk]
                resultados = self.competir([
                    lambda: self.lote(ids),
                    lambda: emitir_turno(excepcion.rut, uuid.uuid4()),
                ])
                self.sin_receta_en_turno_y_despacho()
                self.una_abierta_por_paciente(otros)
                resultado_excepcion = next(r for r in resultados[0] if r.paciente_id == excepcion.pk)
                if isinstance(resultados[1], ErrorEmision):
                    self.assertEqual(resultados[1].code, CODIGO_RECHAZO)
                    self.assertTrue(resultado_excepcion.programado)
                else:  # el tótem ganó: el lote la omite porque no le quedan recetas disponibles
                    self.assertFalse(resultado_excepcion.programado)
                    self.assertEqual(resultado_excepcion.motivo, OMITIDO_SIN_RECETAS)

    def test_10_lote_frente_a_la_programacion_individual_del_mismo_paciente(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                personas = [paciente(edad=85) for _ in range(4)]
                for persona in personas:
                    receta(persona)
                objetivo = personas[2]
                resultados = self.competir([
                    lambda: self.lote([p.pk for p in personas]),
                    lambda: self.programar(objetivo, encargado=self.equipo["encargado2"]),
                ])
                self.una_abierta_por_paciente(personas)
                del_lote = next(r for r in resultados[0] if r.paciente_id == objetivo.pk)
                individual_gano = isinstance(resultados[1], Entrega)
                self.assertNotEqual(del_lote.programado, individual_gano)
                if not individual_gano:
                    self.assertIsInstance(resultados[1], ValidationError)
                    self.assertIn("entrega a domicilio abierta", resultados[1].messages[0])


class ConcurrenciaFotosTests(TransactionTestCase):
    """RF-08-18: guardados simultáneos de fotos del mismo domicilio. Uno gana, nunca más de 3, sin huérfanos."""

    competir = ConcurrenciaRepartoTests.competir

    def setUp(self):
        import shutil
        import tempfile
        from pathlib import Path

        from django.test import override_settings

        self.carpeta = Path(tempfile.mkdtemp(prefix="cesfam-fotos-"))
        ajuste = override_settings(ARCHIVOS_PRIVADOS_ROOT=self.carpeta)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.addCleanup(shutil.rmtree, self.carpeta, True)
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]

    def preparar(self, cantidad):
        domicilio = guardar_domicilio(self.encargado, paciente(edad=85).pk, DATOS)
        for numero in range(cantidad):
            gestionar_fotos(self.encargado, domicilio.pk, mostradas=self.ids(domicilio),
                            nuevas=[FotoNueva(1, archivo(imagen(), "foto.jpg"), f"Vista {numero + 1}")])
        return domicilio

    def ids(self, domicilio):
        return list(FotoDomicilio.objects.filter(domicilio=domicilio).values_list("pk", flat=True))

    def guardado(self, domicilio, mostradas, *, borrar=(), nuevas=1, actor=None):
        def ejecutar():
            fotos_nuevas = [FotoNueva(n + 1, archivo(imagen(), "foto.jpg"), f"Nueva {n + 1}") for n in range(nuevas)]
            return gestionar_fotos(actor or self.encargado, domicilio.pk, mostradas=mostradas, borrar=borrar,
                                   nuevas=fotos_nuevas)
        return ejecutar

    def comprobar(self, domicilio, resultados):
        ganadores = [r for r in resultados if isinstance(r, list)]
        rechazos = [r for r in resultados if isinstance(r, ValidationError)]
        self.assertEqual(len(ganadores), 1, resultados)
        self.assertEqual(len(rechazos), len(resultados) - 1, resultados)
        self.assertTrue(all(r.messages[0] == MENSAJE_FOTOS_CAMBIARON for r in rechazos), resultados)
        self.assertLessEqual(FotoDomicilio.objects.filter(domicilio=domicilio).count(), FotoDomicilio.MAXIMO)
        guardados = sorted(Path_(n).name for n in FotoDomicilio.objects.values_list("archivo", flat=True))
        en_disco = sorted(p.name for p in self.carpeta.rglob("*") if p.is_file())
        self.assertEqual(en_disco, guardados)
        return ganadores[0]

    def test_11_dos_dispositivos_guardan_desde_el_mismo_estado(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                domicilio = self.preparar(1)
                mostradas = self.ids(domicilio)
                resultados = self.competir([self.guardado(domicilio, mostradas),
                                            self.guardado(domicilio, mostradas, actor=self.equipo["qf"])])
                self.assertEqual(len(self.comprobar(domicilio, resultados)), 2)

    def test_12_uno_guarda_mientras_el_otro_borra(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                domicilio = self.preparar(2)
                mostradas = self.ids(domicilio)
                resultados = self.competir([self.guardado(domicilio, mostradas),
                                            self.guardado(domicilio, mostradas, borrar=mostradas[:1], nuevas=0)])
                ganador = self.comprobar(domicilio, resultados)
                self.assertIn(len(ganador), (1, 3))

    def test_13_dos_agregan_con_dos_fotos_ya_guardadas(self):
        for vuelta in range(3):
            with self.subTest(vuelta=vuelta):
                domicilio = self.preparar(2)
                mostradas = self.ids(domicilio)
                resultados = self.competir([self.guardado(domicilio, mostradas) for _ in range(3)])
                self.assertEqual(len(self.comprobar(domicilio, resultados)), 3)
