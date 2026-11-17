"""RF-09-19, RF-09-21 y RF-09-22 (enmienda del 2026-11-15): tramo por camino y parada más cercana por HTTP.

La posición del encargado llega a Django por POST solo para calcular. Estas pruebas comprueban que no queda en la
base, la auditoría, la sesión, la caché ni los registros, que el destino se lee de la base y que todo responde
`no-store`. OSRM es simulado (`osrm_simulado`); ninguna prueba necesita un servidor real. Coordenadas sintéticas.
"""

import io
import json
import logging
import uuid

from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from coreapp.models import RegistroAuditoria
from entregasapp import views
from entregasapp.consultas import ruta_del_dia
from entregasapp.services import mover_parada, registrar_entregada
from .ayudas import cuenta, equipo, punto_km, visita
from .osrm_simulado import ConOsrmSimulado, haversine

# Posición sintética reconocible: si aparece en algún lado, es una fuga.
LATITUD, LONGITUD = -36.512347, -72.198761
HUELLAS = ("512347", "198761")


def cuerpo(**datos):
    return json.dumps(datos)


class CapturaRegistros(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.textos = []

    def emit(self, registro):
        self.textos.append(registro.getMessage() + " " + repr(registro.args) + " " + repr(getattr(registro, "request", "")))


class TramoTests(ConOsrmSimulado, TestCase):
    def setUp(self):
        super().setUp()
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.client.force_login(self.encargado)
        self.url = reverse("entregasapp:tramo")

    def pedir(self, datos, cliente=None, **extra):
        cliente = cliente or self.client
        return cliente.post(self.url, datos if isinstance(datos, str) else cuerpo(**datos),
                            content_type="application/json", HTTP_ACCEPT="application/json", **extra)

    def test_tramo_hasta_una_parada_de_la_ruta_con_distancia_por_camino(self):
        a, b = visita(self.equipo, (0, 1)), visita(self.equipo, (0, 4))
        respuesta = self.pedir({"intento": b.pk, "latitud": LATITUD, "longitud": LONGITUD})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        datos = respuesta.json()
        destino = tuple(float(v) for v in punto_km(0, 4))
        esperado = haversine((LATITUD, LONGITUD), destino)
        self.assertEqual((datos["intento"], datos["numero"]), (b.pk, 2))
        self.assertAlmostEqual(datos["distancia_m"], esperado, delta=1)
        self.assertEqual(datos["distancia_texto"], f"{esperado / 1000:.1f} km".replace(".", ","))
        self.assertEqual(datos["geometria"][0], [LATITUD, LONGITUD])
        self.assertEqual(datos["geometria"][-1], [round(destino[0], 6), round(destino[1], 6)])
        # La URL enviada a OSRM lleva longitud,latitud; el navegador no la conoce.
        ruta_osrm = [s for s in self.osrm.solicitudes if s.startswith("/route/")][0]
        self.assertTrue(ruta_osrm.startswith(f"/route/v1/driving/{LONGITUD:.6f},{LATITUD:.6f};{destino[1]:.6f},{destino[0]:.6f}?"))
        self.assertNotIn(self.osrm.url, respuesta.content.decode())
        self.assertNotIn("rut", json.dumps(datos).lower().replace("ruta", ""))

    def test_el_destino_se_lee_de_la_base_y_no_del_cuerpo(self):
        propia = visita(self.equipo, (0, 2))
        sin = visita(self.equipo, None)
        registrada = visita(self.equipo, (0, 3))
        registrar_entregada(self.encargado, registrada.pk, uuid.uuid4())
        ajena = visita(self.equipo, (1, 1), encargado=self.equipo["encargado2"])
        for intento in (sin, registrada, ajena):
            with self.subTest(intento=intento.pk):
                respuesta = self.pedir({"intento": intento.pk, "latitud": LATITUD, "longitud": LONGITUD})
                self.assertEqual(respuesta.status_code, 404)
                self.assertEqual(respuesta.json(), {"error": "Esa visita no está en tu ruta de hoy o no tiene coordenadas."})
        # Coordenadas del destino manipuladas en el cuerpo: se ignoran.
        self.osrm.solicitudes.clear()
        manipulado = self.pedir({"intento": propia.pk, "latitud": LATITUD, "longitud": LONGITUD,
                                 "destino_latitud": 10.0, "destino_longitud": 10.0, "lat": 10.0, "lon": 10.0})
        self.assertEqual(manipulado.status_code, 200)
        destino = punto_km(0, 2)
        self.assertEqual(manipulado.json()["geometria"][-1], [float(destino[0]), float(destino[1])])
        self.assertNotIn("10.000000", "".join(self.osrm.solicitudes))

    def test_datos_no_validos_responden_400_sin_consultar_osrm(self):
        intento = visita(self.equipo, (0, 2))
        self.osrm.solicitudes.clear()
        for datos in ("{malo", "[1, 2]", {"intento": intento.pk}, {"intento": intento.pk, "latitud": 95, "longitud": 0},
                      {"intento": intento.pk, "latitud": "NaN", "longitud": 0}, {"intento": intento.pk, "latitud": "x", "longitud": 1},
                      {"intento": "x", "latitud": LATITUD, "longitud": LONGITUD}):
            with self.subTest(datos=datos):
                respuesta = self.pedir(datos)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("no-store", respuesta["Cache-Control"])
                self.assertNotIn("95", respuesta.json()["error"])
        self.assertFalse([s for s in self.osrm.solicitudes if s.startswith("/route/")])

    def test_osrm_no_disponible_responde_503_con_texto(self):
        intento = visita(self.equipo, (0, 2))
        for modo in ("error500", "noroute", "malformado"):
            with self.subTest(modo=modo):
                cache.clear()
                self.osrm.modo = modo
                respuesta = self.pedir({"intento": intento.pk, "latitud": LATITUD, "longitud": LONGITUD})
                self.assertEqual(respuesta.status_code, 503)
                self.assertEqual(respuesta.json()["error"], views.TEXTO_SIN_OSRM)
                self.assertIn("no-store", respuesta["Cache-Control"])

    def test_limite_de_30_por_minuto_por_encargado(self):
        intento = visita(self.equipo, (0, 2))
        for _ in range(views.LIMITE_POSICION_POR_MINUTO):
            self.assertEqual(self.pedir({"intento": intento.pk, "latitud": LATITUD, "longitud": LONGITUD}).status_code, 200)
        self.osrm.solicitudes.clear()
        exceso = self.pedir({"intento": intento.pk, "latitud": LATITUD, "longitud": LONGITUD})
        self.assertEqual(exceso.status_code, 429)
        self.assertEqual(exceso.json()["error"], views.TEXTO_LIMITE)
        self.assertEqual(self.osrm.solicitudes, [])  # sobre el límite no consulta a OSRM
        # Otro encargado tiene su propio contador.
        otro = Client()
        otro.force_login(self.equipo["encargado2"])
        ajena = visita(self.equipo, (0, 3), encargado=self.equipo["encargado2"])
        self.assertEqual(self.pedir({"intento": ajena.pk, "latitud": LATITUD, "longitud": LONGITUD}, cliente=otro).status_code, 200)

    def test_permisos_csrf_y_metodo(self):
        intento = visita(self.equipo, (0, 2))
        datos = {"intento": intento.pk, "latitud": LATITUD, "longitud": LONGITUD}
        for actor in ("tecnico", "qf", "admin", "encargado2"):
            with self.subTest(actor=actor):
                cliente = Client()
                cliente.force_login(self.equipo[actor])
                respuesta = self.pedir(datos, cliente=cliente)
                if actor == "encargado2":
                    self.assertEqual(respuesta.status_code, 404)  # su ruta no tiene esa visita
                else:
                    self.assertEqual(respuesta.status_code, 403)
        anonimo = self.pedir(datos, cliente=Client())
        self.assertEqual(anonimo.status_code, 302)
        from coreapp.roles import ENCARGADO
        for nombre, opciones in (("inactiva_tramo", {"activa": False}), ("sin_perfil_tramo", {"perfil": False})):
            with self.subTest(cuenta=nombre):
                cliente = Client()
                cliente.force_login(cuenta(nombre, ENCARGADO, **opciones))
                self.assertIn(self.pedir(datos, cliente=cliente).status_code, (302, 403))
        estricto = Client(enforce_csrf_checks=True)
        estricto.force_login(self.encargado)
        self.assertEqual(self.pedir(datos, cliente=estricto).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        for nombre in ("tramo", "cercana"):
            self.assertRegex(reverse(f"entregasapp:{nombre}"), r"^/entregas/mis/[a-z]+/$")  # sin datos en la URL

    def test_la_posicion_no_queda_en_la_base_la_auditoria_la_sesion_la_cache_ni_los_registros(self):
        intento = visita(self.equipo, (0, 2))
        visita(self.equipo, (0, 5))
        auditoria = RegistroAuditoria.objects.count()
        captura = CapturaRegistros()
        raiz = logging.getLogger()
        raiz.addHandler(captura)
        nivel = raiz.level
        raiz.setLevel(logging.DEBUG)
        try:
            self.pedir({"intento": intento.pk, "latitud": LATITUD, "longitud": LONGITUD})
            self.client.post(reverse("entregasapp:cercana"), cuerpo(latitud=LATITUD, longitud=LONGITUD),
                             content_type="application/json")
            self.pedir({"intento": 999999, "latitud": LATITUD, "longitud": LONGITUD})  # 404, que Django registra
            self.osrm.modo = "error500"
            cache.clear()
            self.pedir({"intento": intento.pk, "latitud": LATITUD, "longitud": LONGITUD})  # 503
        finally:
            raiz.removeHandler(captura)
            raiz.setLevel(nivel)
        self.assertEqual(RegistroAuditoria.objects.count(), auditoria)
        volcado = io.StringIO()
        call_command("dumpdata", exclude=["contenttypes", "auth.permission"], stdout=volcado)
        sesion = self.client.session
        textos = {
            "base": volcado.getvalue(),
            "sesión": json.dumps(dict(sesion.items()), default=str),
            "caché": repr(list(getattr(cache, "_cache", {}).items())),
            "registros": " ".join(captura.textos),
        }
        for fuente, texto in textos.items():
            for huella in HUELLAS:
                with self.subTest(fuente=fuente, huella=huella):
                    self.assertNotIn(huella, texto)


class ParadaCercanaTests(ConOsrmSimulado, TestCase):
    def setUp(self):
        super().setUp()
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.client.force_login(self.encargado)
        self.url = reverse("entregasapp:cercana")

    def pedir(self, latitud, longitud):
        return self.client.post(self.url, cuerpo(latitud=latitud, longitud=longitud), content_type="application/json")

    def test_destaca_la_mas_cercana_por_camino_y_se_puede_mover_a_la_posicion_1(self):
        paradas = [visita(self.equipo, (0, k)) for k in (1, 2, 3, 4)]
        cerca_de_4 = tuple(float(v) for v in punto_km(0.05, 4))
        respuesta = self.pedir(*cerca_de_4)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        datos = respuesta.json()
        self.assertEqual((datos["intento"], datos["numero"], datos["es_primera"], datos["version"]),
                         (paradas[3].pk, 4, False, 0))
        self.assertEqual(datos["distancia_texto"], "50 m")
        consulta = [s for s in self.osrm.solicitudes if "sources=0" in s]
        self.assertEqual(len(consulta), 1)  # una consulta por solicitud, con la posición como origen
        # «Mover al siguiente lugar»: la deja primera con mover_parada y el orden queda manual.
        mover_parada(self.encargado, datos["intento"], "1", datos["version"], uuid.uuid4())
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual((ruta.paradas[0].intento.pk, ruta.manual), (paradas[3].pk, True))
        otra = self.pedir(*cerca_de_4).json()
        self.assertEqual((otra["numero"], otra["es_primera"]), (1, True))

    def test_se_mide_por_camino_aunque_en_linea_recta_gane_otra(self):
        cerca, lejos = visita(self.equipo, (0, 1)), visita(self.equipo, (0, 3))
        destino_cerca = tuple(round(float(v), 6) for v in punto_km(0, 1))
        self.osrm.distancia = lambda a, b: 9000 if abs(b[0] - destino_cerca[0]) < 1e-6 and abs(b[1] - destino_cerca[1]) < 1e-6 else haversine(a, b)
        origen = tuple(float(v) for v in punto_km(0, 0))
        datos = self.pedir(*origen).json()
        self.assertEqual(datos["intento"], lejos.pk)
        self.assertNotEqual(datos["intento"], cerca.pk)

    def test_sin_osrm_no_sugiere_nada(self):
        visita(self.equipo, (0, 1))
        self.osrm.modo = "error500"
        respuesta = self.pedir(LATITUD, LONGITUD)
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json(), {"error": views.TEXTO_SIN_OSRM_CERCANA})

    def test_sin_paradas_con_coordenadas_y_posicion_no_valida(self):
        visita(self.equipo, None)
        self.assertEqual(self.pedir(LATITUD, LONGITUD).status_code, 404)
        self.assertEqual(self.pedir(-91, 0).status_code, 400)
        tecnico = Client()
        tecnico.force_login(self.equipo["tecnico"])
        self.assertEqual(tecnico.post(self.url, cuerpo(latitud=LATITUD, longitud=LONGITUD),
                                      content_type="application/json").status_code, 403)
