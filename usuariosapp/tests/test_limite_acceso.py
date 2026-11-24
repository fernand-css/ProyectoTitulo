"""Límite de intentos de inicio de sesión: por usuario en el equipo y por equipo, con espera y sin bloquear la cuenta."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
from threading import Barrier

from django.contrib.auth import SESSION_KEY, get_user_model
from django.db import close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from coreapp.auditoria import LOGIN_FALLIDO
from coreapp.models import RegistroAuditoria
from usuariosapp import limite_acceso
from usuariosapp.models import IntentoAcceso

CLAVE = "Clave-sintetica-solo-pruebas-2026!"
USUARIO = "admin_limite_prueba"
URL = reverse("usuariosapp:login")


def crear_cuenta():
    return get_user_model().objects.create_superuser(username=USUARIO, password=CLAVE)


class LimiteAccesoHttpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cuenta = crear_cuenta()

    def entrar(self, usuario=USUARIO, clave=CLAVE, ip="127.0.0.1", cliente=None):
        return (cliente or self.client).post(URL, {"username": usuario, "password": clave}, REMOTE_ADDR=ip)

    def fallar(self, veces, **extra):
        for _ in range(veces):
            self.assertEqual(self.entrar(clave="incorrecta", **extra).status_code, 200)

    def test_tras_cinco_fallos_espera_incluso_con_la_clave_correcta(self):
        self.fallar(limite_acceso.LIMITE_CUENTA)
        respuesta = self.entrar()
        self.assertEqual(respuesta.status_code, 429)
        self.assertContains(respuesta, "demasiados intentos fallidos", status_code=429)
        self.assertContains(respuesta, 'role="alert"', status_code=429)
        self.assertNotIn(SESSION_KEY, self.client.session)
        # La espera no comprobó la contraseña: no hay un sexto fallo registrado.
        self.assertEqual(RegistroAuditoria.objects.filter(accion=LOGIN_FALLIDO).count(), limite_acceso.LIMITE_CUENTA)

    def test_el_formulario_conserva_el_usuario_y_no_la_clave(self):
        self.fallar(limite_acceso.LIMITE_CUENTA)
        html = self.entrar().content.decode()
        self.assertIn(f'value="{USUARIO}"', html)
        self.assertNotIn(CLAVE, html)
        self.assertNotIn("incorrecta", html)

    def test_desde_otro_equipo_la_cuenta_sigue_entrando(self):
        self.fallar(limite_acceso.LIMITE_CUENTA, ip="10.0.0.9")
        self.assertRedirects(self.entrar(ip="10.0.0.20"), "/")

    def test_otro_usuario_en_el_mismo_equipo_no_espera_por_el_limite_de_la_cuenta(self):
        self.fallar(limite_acceso.LIMITE_CUENTA)
        self.assertEqual(self.entrar(usuario="otra-cuenta-sintetica", clave="incorrecta").status_code, 200)

    def test_cambiar_mayusculas_o_espacios_no_da_intentos_nuevos(self):
        self.fallar(limite_acceso.LIMITE_CUENTA)
        self.assertEqual(self.entrar(usuario=f"  {USUARIO.upper()} ", clave="incorrecta").status_code, 429)

    def test_ingreso_correcto_borra_los_fallos_de_la_cuenta_en_el_equipo(self):
        self.fallar(limite_acceso.LIMITE_CUENTA - 1)
        self.assertRedirects(self.entrar(), "/")
        self.client.logout()
        self.fallar(limite_acceso.LIMITE_CUENTA)
        self.assertEqual(self.entrar().status_code, 429)

    def test_el_equipo_espera_tras_probar_muchos_usuarios(self):
        for numero in range(limite_acceso.LIMITE_EQUIPO):
            self.assertEqual(self.entrar(usuario=f"cuenta-sintetica-{numero}", clave="incorrecta").status_code, 200)
        self.assertEqual(self.entrar().status_code, 429)
        self.assertRedirects(self.entrar(ip="10.0.0.30"), "/")

    def test_los_ingresos_correctos_no_llenan_el_cupo_del_equipo(self):
        otro = Client()
        for _ in range(limite_acceso.LIMITE_EQUIPO + 2):
            self.assertRedirects(self.entrar(cliente=otro), "/")
            otro.logout()
        fila = IntentoAcceso.objects.get(clave=limite_acceso.huellas(USUARIO, "127.0.0.1")[1])
        self.assertEqual(fila.cantidad, 0)

    def test_campos_vacios_no_consumen_intentos(self):
        for _ in range(limite_acceso.LIMITE_CUENTA + 2):
            self.client.post(URL, {"username": USUARIO, "password": ""})
            self.client.post(URL, {"username": "   ", "password": "algo"})
        self.assertFalse(IntentoAcceso.objects.exists())
        self.assertRedirects(self.entrar(), "/")

    def test_auditoria_una_vez_por_ventana_sin_usuario_ni_ip(self):
        self.fallar(limite_acceso.LIMITE_CUENTA)
        for _ in range(3):
            self.entrar()
        registros = RegistroAuditoria.objects.filter(accion=limite_acceso.ACCION_LIMITE)
        self.assertEqual(registros.count(), 1)
        registro = registros.get()
        self.assertIsNone(registro.usuario_id)
        self.assertEqual(registro.objeto_tipo, "usuariosapp.IntentoAcceso")
        for valor in IntentoAcceso.objects.values_list("clave", flat=True):
            self.assertNotIn(USUARIO, valor)
            self.assertNotIn("127.0.0.1", valor)


class LimiteAccesoServicioTests(TestCase):
    inicio = datetime(2026, 11, 24, 15, 0, tzinfo=dt_timezone.utc)

    def test_la_espera_termina_con_la_ventana(self):
        for minuto in range(limite_acceso.LIMITE_CUENTA):
            limite_acceso.reservar(USUARIO, "10.1.1.1", self.inicio + timedelta(minutes=minuto))
        with self.assertRaises(limite_acceso.LimiteSuperado) as espera:
            limite_acceso.reservar(USUARIO, "10.1.1.1", self.inicio + timedelta(minutes=10, seconds=30))
        self.assertEqual(espera.exception.minutos, 5)
        with self.assertRaises(limite_acceso.LimiteSuperado) as espera:
            limite_acceso.reservar(USUARIO, "10.1.1.1", self.inicio + timedelta(minutes=14, seconds=59))
        self.assertEqual(espera.exception.minutos, 1)
        limite_acceso.reservar(USUARIO, "10.1.1.1", self.inicio + limite_acceso.VENTANA)

    def test_una_reserva_rechazada_no_deja_cupo_tomado_en_el_otro_contador(self):
        for numero in range(limite_acceso.LIMITE_EQUIPO):
            limite_acceso.reservar(f"cuenta-{numero}", "10.1.1.2", self.inicio)
        with self.assertRaises(limite_acceso.LimiteSuperado):
            limite_acceso.reservar(USUARIO, "10.1.1.2", self.inicio)
        cuenta, _ = limite_acceso.huellas(USUARIO, "10.1.1.2")
        self.assertFalse(IntentoAcceso.objects.filter(clave=cuenta).exists())

    def test_se_borran_las_ventanas_de_mas_de_un_dia(self):
        limite_acceso.reservar(USUARIO, "10.1.1.3", self.inicio - timedelta(days=2))
        limite_acceso.reservar("otra", "10.1.1.4", self.inicio)
        self.assertFalse(IntentoAcceso.objects.filter(ventana__lt=self.inicio - timedelta(days=1)).exists())


class LimiteAccesoConcurrenciaTests(TransactionTestCase):
    def a_la_vez(self, tarea, cantidad):
        barrera = Barrier(cantidad)

        def correr(indice):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return tarea(indice)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=cantidad) as pool:
            return [futuro.result(timeout=60) for futuro in [pool.submit(correr, i) for i in range(cantidad)]]

    def test_solicitudes_simultaneas_no_comprueban_mas_claves_que_el_limite_de_la_cuenta(self):
        crear_cuenta()
        estados = self.a_la_vez(
            lambda _: Client().post(URL, {"username": USUARIO, "password": "incorrecta"}).status_code, 12)
        self.assertEqual(estados.count(200), limite_acceso.LIMITE_CUENTA)
        self.assertEqual(estados.count(429), 12 - limite_acceso.LIMITE_CUENTA)
        self.assertEqual(RegistroAuditoria.objects.filter(accion=LOGIN_FALLIDO).count(), limite_acceso.LIMITE_CUENTA)
        self.assertEqual(RegistroAuditoria.objects.filter(accion=limite_acceso.ACCION_LIMITE).count(), 1)

    def test_muchos_usuarios_a_la_vez_no_superan_el_limite_del_equipo(self):
        total = limite_acceso.LIMITE_EQUIPO + 8
        estados = self.a_la_vez(
            lambda i: Client().post(URL, {"username": f"cuenta-sintetica-{i}", "password": "incorrecta"}).status_code, total)
        self.assertEqual(estados.count(200), limite_acceso.LIMITE_EQUIPO)
        self.assertEqual(estados.count(429), 8)
        self.assertEqual(RegistroAuditoria.objects.filter(accion=LOGIN_FALLIDO).count(), limite_acceso.LIMITE_EQUIPO)

    def test_ingresos_correctos_y_fallidos_mezclados_dejan_la_cuenta_exacta(self):
        crear_cuenta()
        ip = "10.2.2.2"

        def intento(i):
            cliente = Client()
            correcto = i % 4 == 0  # Cuatro ingresos correctos: bajo el cupo de la cuenta aunque coincidan.
            respuesta = cliente.post(URL, {"username": f"cuenta-sintetica-{i}" if not correcto else USUARIO,
                                           "password": CLAVE if correcto else "incorrecta"}, REMOTE_ADDR=ip)
            return correcto, respuesta.status_code

        resultados = self.a_la_vez(intento, 16)
        self.assertTrue(all(estado == 302 for correcto, estado in resultados if correcto))
        self.assertTrue(all(estado == 200 for correcto, estado in resultados if not correcto))
        # Solo los doce fallos quedan en el cupo del equipo; los ingresos devolvieron el suyo.
        self.assertEqual(IntentoAcceso.objects.get(clave=limite_acceso.huellas(USUARIO, ip)[1]).cantidad, 12)
