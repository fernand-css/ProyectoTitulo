"""Spec 11, RF-11-02 y RF-11-04: paquete de la ruta para el celular y página sin conexión. Datos sintéticos."""

import json
import uuid
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from coreapp.roles import DIRECTOR
from entregasapp import consultas
from entregasapp.models import IntentoEntrega
from entregasapp.services import iniciar_traslado, registrar_entregada
from recetasapp.models import Paciente
from .ayudas import cuenta, equipo, hoy, visita

CAMPOS = {
    "intento", "numero", "seccion", "fecha_programada", "atrasada", "nombre", "direccion", "referencias", "localidad",
    "sector", "telefono", "recetas", "traslado_iniciado",
}


class PaqueteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipo = equipo()
        cls.director = cuenta("director_reparto", DIRECTOR)
        e = cls.equipo
        cls.hoy = [visita(e, (1, 0)), visita(e, (3, 1)), visita(e, None, sector="rojo", localidad="Localidad demo 2")]
        cls.atrasada = visita(e, (2, 2))
        IntentoEntrega.objects.filter(pk=cls.atrasada.pk).update(fecha_programada=hoy() - timedelta(days=1))
        cls.proxima = visita(e, (4, 0), fecha=hoy() + timedelta(days=1))
        cls.de_otro = visita(e, (1, 1), encargado=e["encargado2"])
        cls.registrada = visita(e, (5, 5))
        registrar_entregada(e["encargado"], cls.registrada.pk, uuid.uuid4())
        Paciente.objects.update(correo_avisos="familia@example.invalid")

    def paquete(self, actor="encargado"):
        self.client.force_login(self.equipo[actor])
        return self.client.get(reverse("entregasapp:paquete"))

    def test_trae_hoy_y_atrasadas_en_el_orden_de_la_ruta(self):
        respuesta = self.paquete()
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertIn("private", respuesta["Cache-Control"])
        datos = respuesta.json()
        self.assertEqual(datos["formato"], 1)
        self.assertEqual(datos["fecha"], hoy().isoformat())
        self.assertEqual(datos["cuenta"], self.equipo["encargado"].pk)
        self.assertIn(["otro", "Otro"], datos["motivos"])
        ruta = consultas.ruta_del_dia(self.equipo["encargado"], hoy=hoy())
        self.assertEqual([p["intento"] for p in datos["paradas"]], [p.intento.pk for p in ruta.paradas])
        self.assertCountEqual([p["intento"] for p in datos["paradas"]],
                              [i.pk for i in self.hoy] + [self.atrasada.pk])
        for parada in datos["paradas"]:
            self.assertEqual(set(parada), CAMPOS)

    def test_datos_de_cada_parada(self):
        paradas = {p["intento"]: p for p in self.paquete().json()["paradas"]}
        atrasada = paradas[self.atrasada.pk]
        self.assertTrue(atrasada["atrasada"])
        self.assertEqual(atrasada["fecha_programada"], (hoy() - timedelta(days=1)).isoformat())
        sin_coordenadas = paradas[self.hoy[2].pk]
        self.assertEqual((sin_coordenadas["seccion"], sin_coordenadas["numero"]), ("sin_coordenadas", None))
        self.assertEqual((sin_coordenadas["sector"], sin_coordenadas["localidad"]), ("Rojo", "Localidad demo 2"))
        primera = paradas[self.hoy[0].pk]
        self.assertEqual(primera["seccion"], "ruta")
        self.assertIsInstance(primera["numero"], int)
        self.assertEqual((primera["direccion"], primera["referencias"], primera["telefono"], primera["recetas"]),
                         ("Camino sintético km 2", "Portón sintético", "+56 9 0000 0000", 1))
        self.assertFalse(primera["traslado_iniciado"])

    def test_traslado_iniciado(self):
        iniciar_traslado(self.equipo["encargado"], self.hoy[1].pk)
        paradas = {p["intento"]: p for p in self.paquete().json()["paradas"]}
        self.assertTrue(paradas[self.hoy[1].pk]["traslado_iniciado"])

    def test_sin_rut_fotos_coordenadas_correo_ni_medicamentos(self):
        texto = self.paquete().content.decode()
        for persona in Paciente.objects.all():
            self.assertNotIn(persona.rut, texto)
        for prohibido in ("latitud", "longitud", "lat", "lon", "foto", "fotos", "correo", "correo_avisos", "codigo", "rut"):
            self.assertNotIn(f'"{prohibido}"', texto)
        self.assertNotIn("example.invalid", texto)
        self.assertNotIn("DESP-", texto)

    def test_cada_encargado_recibe_solo_lo_suyo(self):
        datos = self.paquete("encargado2").json()
        self.assertEqual([p["intento"] for p in datos["paradas"]], [self.de_otro.pk])
        self.assertEqual(datos["cuenta"], self.equipo["encargado2"].pk)

    def test_otros_roles_reciben_403_y_sin_sesion_va_a_la_entrada(self):
        for actor in ("qf", "tecnico", "admin"):
            with self.subTest(actor=actor):
                respuesta = self.paquete(actor)
                self.assertEqual(respuesta.status_code, 403)
                self.assertNotIn("paradas", respuesta.content.decode())
        self.client.force_login(self.director)
        self.assertEqual(self.client.get(reverse("entregasapp:paquete")).status_code, 403)
        self.client.logout()
        respuesta = self.client.get(reverse("entregasapp:paquete"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("usuariosapp:login"), respuesta["Location"])

    def test_solo_get(self):
        self.client.force_login(self.equipo["encargado"])
        self.assertEqual(self.client.post(reverse("entregasapp:paquete")).status_code, 405)


class PaginaSinConexionTests(TestCase):
    """RF-11-04: la página que guarda el service worker no lleva datos de la cuenta ni de pacientes."""

    @classmethod
    def setUpTestData(cls):
        cls.equipo = equipo()
        cls.intento = visita(cls.equipo, (1, 0))

    def test_sin_datos_personales_ni_formularios_del_servidor(self):
        self.client.force_login(self.equipo["encargado"])
        respuesta = self.client.get(reverse("entregasapp:sin_conexion"))
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        for texto in ('aria-live="polite"', "Sincronizar ahora", "No se pudo enviar", "Sin conexión",
                      "No hay una ruta guardada para hoy", "js/entregas/almacen.js", "js/entregas/sincronizar.js",
                      "js/entregas/sin_conexion.js", reverse("entregasapp:sincronizar")):
            self.assertIn(texto, html)
        persona = self.intento.entrega.paciente
        for prohibido in (persona.rut, persona.apellidos, "Persona Sintética", self.equipo["encargado"].username,
                          "csrfmiddlewaretoken"):
            self.assertNotIn(prohibido, html)

    def test_solo_el_encargado(self):
        for actor in ("qf", "tecnico", "admin"):
            with self.subTest(actor=actor):
                self.client.force_login(self.equipo[actor])
                self.assertEqual(self.client.get(reverse("entregasapp:sin_conexion")).status_code, 403)

    def test_mis_entregas_lleva_la_barra_de_estado_y_la_cuenta(self):
        self.client.force_login(self.equipo["encargado"])
        html = self.client.get(reverse("entregasapp:mis")).content.decode()
        for texto in ("data-reparto-estado", f'data-cuenta="{self.equipo["encargado"].pk}"',
                      reverse("entregasapp:paquete"), "Sincronizar ahora", "js/entregas/sin_conexion.js"):
            self.assertIn(texto, html)
        datos = json.dumps(self.client.get(reverse("entregasapp:paquete")).json())
        self.assertNotIn(self.intento.entrega.paciente.rut, datos)
