"""RF-04-12: 10 solicitudes por minuto por equipo (IP y sesión), contadas en la base."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as tz
from random import Random
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from unittest.mock import patch

from coreapp.models import RegistroAuditoria
from coreapp.utils.sinteticos import generar_ruts
from turnosapp.models import IntentoTotem, Turno
from turnosapp.services import ACCION_LIMITE, LIMITE_INTENTOS, MENSAJE_NEUTRO, registrar_intento_totem
from turnosapp.views import CLAVE
from . import test_servicios as preparacion
from .test_vistas import TotemVistasTests

INSTANTE = datetime(2026, 11, 2, 12, 30, 15, tzinfo=tz.utc)


class LimiteVistasTests(TestCase):
    def setUp(self):
        preparacion.EmisionTests.setUp(self)
        # Ventana fija: evita que el cambio de minuto durante la prueba reinicie el recuento.
        reloj = patch("turnosapp.services.timezone.now", return_value=INSTANTE)
        reloj.start()
        self.addCleanup(reloj.stop)

    pacientes = preparacion.EmisionTests.pacientes
    recetas = preparacion.EmisionTests.recetas
    abrir = TotemVistasTests.abrir
    enviar = TotemVistasTests.enviar

    def test_undecima_solicitud_del_minuto_queda_en_pausa_con_mensaje_neutro(self):
        self.abrir()
        for _ in range(LIMITE_INTENTOS - 1):
            self.assertEqual(self.enviar(rut="incorrecto").status_code, 400)
        error = self.enviar(rut="incorrecto")  # décima: aceptada y rechazada por formato
        self.assertNotEqual(error.context["mensaje"], MENSAJE_NEUTRO)
        bloqueada = self.enviar()  # undécima, con un RUT válido
        self.assertEqual(bloqueada.status_code, 400)
        self.assertEqual(bloqueada.templates[0].name, "turnos/totem.html")
        self.assertEqual(bloqueada.context["mensaje"], MENSAJE_NEUTRO)
        self.assertNotContains(bloqueada, self.paciente.rut, status_code=400)
        self.assertFalse(Turno.objects.exists())
        # Mismo código y estructura que otro rechazo neutro (operación ajena) desde otro equipo.
        neutro = Client(REMOTE_ADDR="10.0.0.8").post(reverse("turnosapp:totem"), {"rut": self.paciente.rut, "operacion_id": uuid.uuid4()})
        self.assertEqual((neutro.status_code, neutro.context["mensaje"]), (400, MENSAJE_NEUTRO))
        self.assertEqual(neutro.templates[0].name, bloqueada.templates[0].name)

    def test_auditoria_una_vez_por_clave_y_sin_rut(self):
        self.abrir()
        for _ in range(LIMITE_INTENTOS + 3):
            self.enviar()
        registros = RegistroAuditoria.objects.filter(accion=ACCION_LIMITE)
        self.assertEqual(registros.count(), 2)  # IP y sesión, una vez cada una
        self.assertEqual({r.objeto_tipo for r in registros}, {"turnosapp.IntentoTotem"})
        self.assertTrue(all(r.usuario_id is None for r in registros))
        for registro in registros:
            self.assertNotIn(self.paciente.rut, f"{registro.objeto_tipo}{registro.objeto_id}{registro.accion}")
        cuerpo = self.paciente.rut.split("-")[0]
        self.assertFalse(IntentoTotem.objects.filter(clave__contains=cuerpo).exists())
        self.assertEqual(Turno.objects.count(), 1)

    def test_cuenta_por_ip_aunque_cambie_la_sesion(self):
        for _ in range(LIMITE_INTENTOS):
            cliente = Client()
            self.abrir(cliente)
            self.enviar(cliente, rut="incorrecto")
        cliente = Client()
        self.abrir(cliente)
        self.assertEqual(self.enviar(cliente).context["mensaje"], MENSAJE_NEUTRO)
        otra_ip = Client(REMOTE_ADDR="10.0.0.9")
        self.abrir(otra_ip)
        self.assertEqual(self.enviar(otra_ip).status_code, 200)

    def test_ventana_siguiente_vuelve_a_aceptar_y_limpia_antiguas(self):
        claves = ["a" * 64]
        for _ in range(LIMITE_INTENTOS):
            self.assertTrue(registrar_intento_totem(claves, INSTANTE))
        self.assertFalse(registrar_intento_totem(claves, INSTANTE + timedelta(seconds=40)))
        self.assertTrue(registrar_intento_totem(claves, INSTANTE + timedelta(seconds=45)))
        self.assertEqual(IntentoTotem.objects.count(), 2)
        self.assertTrue(registrar_intento_totem(claves, INSTANTE + timedelta(minutes=12)))
        self.assertEqual(IntentoTotem.objects.count(), 1)  # las ventanas de hace más de 10 minutos se borran
        self.assertEqual(IntentoTotem.objects.get().cantidad, 1)


def _competir(tareas):
    barrera = Barrier(len(tareas))

    def ejecutar(tarea):
        close_old_connections()
        try:
            barrera.wait(timeout=10)
            return tarea()
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=len(tareas)) as pool:
        return list(pool.map(ejecutar, tareas))


class LimiteConcurrenciaTests(TransactionTestCase):
    """Hilos con conexiones propias en la misma ventana de un minuto."""

    def contar(self, claves):
        return lambda: registrar_intento_totem(claves, INSTANTE)

    def test_veinte_hilos_misma_clave_aceptan_diez(self):
        resultados = _competir([self.contar(["b" * 64]) for _ in range(20)])
        self.assertEqual(resultados.count(True), LIMITE_INTENTOS)
        self.assertEqual(IntentoTotem.objects.get().cantidad, LIMITE_INTENTOS)
        self.assertEqual(RegistroAuditoria.objects.filter(accion=ACCION_LIMITE).count(), 1)

    def test_ip_compartida_y_sesiones_distintas_nunca_pasan_de_diez(self):
        resultados = _competir([self.contar(["c" * 64, f"{indice:064d}"]) for indice in range(16)])
        self.assertEqual(resultados.count(True), LIMITE_INTENTOS)
        self.assertEqual(IntentoTotem.objects.get(clave="c" * 64).cantidad, LIMITE_INTENTOS)

    def test_claves_distintas_en_paralelo_no_se_bloquean_entre_si(self):
        resultados = _competir([self.contar([f"{indice % 2:064d}"]) for indice in range(12)])
        self.assertEqual(resultados.count(True), 12)
        self.assertEqual(sorted(IntentoTotem.objects.values_list("cantidad", flat=True)), [6, 6])


class LimiteConcurrenciaVistaTests(TransactionTestCase):
    """Doce navegadores del mismo equipo (misma IP) piden número a la vez: nunca más de 10 pasan."""

    def test_doce_solicitudes_simultaneas_del_mismo_equipo(self):
        ruts = generar_ruts(12, Random(4128))  # fuera del padrón: turnos G sin recetas
        pares = []
        for rut in ruts:
            cliente = Client()
            cliente.get(reverse("turnosapp:totem"))
            pares.append((cliente, rut, cliente.session[CLAVE]["operacion"]))

        def tarea(par):
            cliente, rut, operacion = par
            return lambda: cliente.post(reverse("turnosapp:totem"), {"rut": rut, "operacion_id": operacion})
        respuestas = _competir([tarea(par) for par in pares])
        bloqueadas = [r for r in respuestas if r.status_code == 400 and r.context["mensaje"] == MENSAJE_NEUTRO]
        aceptadas = [r for r in respuestas if r.status_code == 200]
        self.assertEqual(len(bloqueadas), 2)
        self.assertLessEqual(len(aceptadas), LIMITE_INTENTOS)
        self.assertEqual(Turno.objects.count(), len(aceptadas))
        self.assertEqual(len(set(Turno.objects.values_list("fecha", "letra", "numero"))), Turno.objects.count())
        self.assertEqual(RegistroAuditoria.objects.filter(accion=ACCION_LIMITE).count(), 1)  # solo la IP superó
