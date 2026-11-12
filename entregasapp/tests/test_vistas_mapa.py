"""RF-09-01 a RF-09-11 por HTTP: «Mis entregas» numerada, mapa, «Ir a esta parada», «Rutas» y mapa del domicilio."""

import json
import re
import uuid
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from entregasapp.consultas import ruta_del_dia
from entregasapp.services import guardar_domicilio, mover_parada, registrar_entregada, registrar_no_entregada
from .ayudas import equipo, hoy, paciente, punto_km, receta, visita


def datos_json(html, ident):
    """Contenido de un json_script de la página."""
    coincidencia = re.search(rf'<script id="{ident}" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(coincidencia.group(1)) if coincidencia else None


def operaciones(html):
    return re.findall(r'name="operacion_id" value="([^"]+)"', html)


class MisEntregasRutaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.client.force_login(self.encargado)

    def visita(self, en=None, **opciones):
        return visita(self.equipo, en, **opciones)

    def test_lista_numerada_con_secciones_controles_y_guia(self):
        a, b = self.visita((0, 2)), self.visita((0, 1))
        sin = self.visita(None, sector="azul", localidad="Localidad demo 4")
        manana = self.visita((0, 3), fecha=hoy() + timedelta(days=1))
        entregada, no_entregada = self.visita((1, 1)), self.visita((1, 2))
        registrar_entregada(self.encargado, entregada.pk, uuid.uuid4())
        registrar_no_entregada(self.encargado, no_entregada.pk, "domicilio_no_encontrado", "", uuid.uuid4())
        respuesta = self.client.get(reverse("entregasapp:mis"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        html = respuesta.content.decode()
        for texto in ("Orden sugerido desde la última visita registrada, según distancia en línea recta; no considera caminos.",
                      "Por visitar (3)", "Registradas hoy (2)", "Próximas (1)", "Por visitar en orden (2)",
                      "Sin coordenadas: fuera del orden sugerido (1)", "Sector Azul · Localidad demo 4",
                      "No entregada: Domicilio no encontrado", "Recorrido aprox.:", "Mover a la posición"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        # La última registrada (no entregada, a 1 km este y 2 km norte) es la partida: desde ahí A (0, 2) queda a 1 km
        # y luego B (0, 1) camino al CESFAM. Desde el CESFAM habría sido B, A.
        self.assertLess(html.index(f'id="parada-{a.pk}"'), html.index(f'id="parada-{b.pk}"'))
        self.assertLess(html.index(f'id="parada-{b.pk}"'), html.index(f'id="parada-{sin.pk}"'))
        self.assertLess(html.index(f'id="parada-{sin.pk}"'), html.index(f'id="parada-{manana.pk}"'))
        self.assertIn(f'href="{reverse("entregasapp:ir_a", args=[a.pk])}"', html)
        self.assertNotIn(reverse("entregasapp:ir_a", args=[sin.pk]), html)  # sin coordenadas, sin guía
        self.assertNotIn(reverse("entregasapp:ir_a", args=[manana.pk]), html)
        self.assertEqual(html.count(f'action="{reverse("entregasapp:orden_mover")}"'), 6)  # dos formularios × 3 visitas
        self.assertEqual(len(set(operaciones(html))), 3)
        self.assertIn('value="subir"', html)
        self.assertNotIn("Volver al orden sugerido", html)
        # Próximas sin número ni controles.
        tarjeta_manana = html[html.index(f'id="parada-{manana.pk}"'):]
        self.assertNotIn("Parada ", tarjeta_manana[:200])

    def test_mover_por_http_guarda_el_orden_y_avisa_conflictos(self):
        a, b = self.visita((0, 2)), self.visita((0, 1))
        html = self.client.get(reverse("entregasapp:mis")).content.decode()
        datos = {"intento": b.pk, "destino": "bajar", "version": 0, "operacion_id": operaciones(html)[0]}
        respuesta = self.client.post(reverse("entregasapp:orden_mover"), datos)
        self.assertRedirects(respuesta, reverse("entregasapp:mis") + f"#parada-{b.pk}", fetch_redirect_response=False)
        pagina = self.client.get(reverse("entregasapp:mis"))
        self.assertContains(pagina, "Orden guardado. Desde ahora manda tu orden de hoy.")
        self.assertContains(pagina, "Tu orden de hoy, guardado a las")
        self.assertContains(pagina, "Volver al orden sugerido")
        self.assertEqual([p.intento.pk for p in ruta_del_dia(self.encargado).paradas], [a.pk, b.pk])
        # Reenviar el mismo formulario no mueve otra vez; otro desde la versión vieja recibe el aviso.
        self.client.post(reverse("entregasapp:orden_mover"), datos)
        self.assertEqual([p.intento.pk for p in ruta_del_dia(self.encargado).paradas], [a.pk, b.pk])
        conflicto = self.client.post(reverse("entregasapp:orden_mover"), {**datos, "operacion_id": uuid.uuid4()}, follow=True)
        self.assertContains(conflicto, "Tu orden cambió en otro dispositivo; revisa la lista.")
        mal = self.client.post(reverse("entregasapp:orden_mover"), {"intento": "x"}, follow=True)
        self.assertContains(mal, "No se pudo cambiar el orden.")
        self.assertEqual(self.client.get(reverse("entregasapp:orden_mover")).status_code, 405)

    def test_volver_al_orden_sugerido_por_http(self):
        a, b = self.visita((0, 2)), self.visita((0, 1))
        mover_parada(self.encargado, b.pk, "bajar", 0, uuid.uuid4())
        html = self.client.get(reverse("entregasapp:mis")).content.decode()
        version = re.search(r'name="version" value="(\d+)" id="id_version"', html).group(1)
        operacion = re.search(r'name="operacion_id" value="([^"]+)" id="id_operacion_id"', html).group(1)
        respuesta = self.client.post(reverse("entregasapp:orden_sugerido"), {"version": version, "operacion_id": operacion},
                                     follow=True)
        self.assertContains(respuesta, "Volviste al orden sugerido.")
        self.assertContains(respuesta, "Orden sugerido desde el CESFAM")
        self.assertEqual([p.intento.pk for p in ruta_del_dia(self.encargado).paradas], [b.pk, a.pk])

    def test_sin_entregas_lo_dice_con_texto(self):
        self.assertContains(self.client.get(reverse("entregasapp:mis")), "No tienes entregas asignadas")


class MapaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.client.force_login(self.encargado)

    def test_datos_del_mapa_coinciden_con_la_lista_y_no_traen_datos_privados(self):
        """Criterio de RF-09-08: 5 paradas (1 sin coordenadas) y 2 registradas."""
        paradas = [visita(self.equipo, en) for en in ((0, 1), (0, 2), (1, 3), (2, 1))]
        sin = visita(self.equipo, None)
        registradas = [visita(self.equipo, (3, 3)), visita(self.equipo, (3, 4))]
        registrar_entregada(self.encargado, registradas[0].pk, uuid.uuid4())
        registrar_no_entregada(self.encargado, registradas[1].pk, "sin_receptor", "Nota privada sintética", uuid.uuid4())
        respuesta = self.client.get(reverse("entregasapp:mapa"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        html = respuesta.content.decode()
        datos = datos_json(html, "datos-mapa")
        ruta = ruta_del_dia(self.encargado)
        self.assertEqual([(p["numero"], p["intento"]) for p in datos["paradas"]],
                         [(p.numero, p.intento.pk) for p in ruta.paradas if p.punto is not None])
        self.assertEqual(len(datos["paradas"]), 4)
        self.assertNotIn(sin.pk, [p["intento"] for p in datos["paradas"]])
        self.assertEqual(len(datos["registradas"]), 2)
        self.assertEqual([r["entregada"] for r in datos["registradas"]], [True, False])
        self.assertEqual(datos["registradas"][1]["motivo"], "No había nadie para recibir")
        self.assertEqual(datos["origen"]["etiqueta"], "CESFAM")
        self.assertEqual(datos["linea"][0], [datos["partida"]["lat"], datos["partida"]["lon"]])
        self.assertEqual(datos["linea"][-1], [datos["origen"]["lat"], datos["origen"]["lon"]])
        self.assertEqual(len(datos["linea"]), 6)  # partida, 4 paradas y CESFAM
        self.assertEqual(datos["total_km"], ruta.total_km)
        self.assertEqual(datos["sin_marcador"], 1)
        self.assertEqual(datos["teselas"]["atribucion"], "© colaboradores de OpenStreetMap")
        self.assertIn("{z}", datos["teselas"]["url"])
        self.assertTrue(datos["paradas"][0]["url_ir"].startswith("/entregas/mis/ir/"))
        texto = json.dumps(datos, ensure_ascii=False)
        for persona in [p.entrega.paciente for p in (*paradas, *registradas)]:
            self.assertNotIn(persona.rut, texto)
        for privado in ("+56 9", "telefono", "Nota privada", "foto"):
            self.assertNotIn(privado, texto)
        for recurso in ("vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css", "js/entregas/mapa.js"):
            self.assertIn(recurso, html)
        for texto in ("1 visita sin marcador", "Saltar el mapa e ir a la lista", "Recorrido en línea recta; no sigue los caminos",
                      'role="region"', "Paradas en orden (5)"):
            self.assertIn(texto, html)

    def test_dos_visitas_sin_marcador(self):
        visita(self.equipo, (0, 1))
        visita(self.equipo, None)
        visita(self.equipo, None, domicilio=False)
        html = self.client.get(reverse("entregasapp:mapa")).content.decode()
        self.assertIn("2 visitas sin marcador", html)
        self.assertEqual(datos_json(html, "datos-mapa")["sin_marcador"], 2)


class IrAParadaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.client.force_login(self.encargado)

    def test_pagina_de_la_guia_con_destino_enlace_geo_y_coordenadas(self):
        lejos, cerca = visita(self.equipo, (0, 3)), visita(self.equipo, (0, 1))
        respuesta = self.client.get(reverse("entregasapp:ir_a", args=[lejos.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        html = respuesta.content.decode()
        latitud, longitud = punto_km(0, 3)
        datos = datos_json(html, "datos-ir-a")
        self.assertEqual(datos["numero"], 2)
        self.assertEqual((f"{datos['lat']:.6f}", f"{datos['lon']:.6f}"), (latitud, longitud))
        for texto in ("Ir a la parada 2", "Mostrar mi posición", "Leer distancia", "Detener", 'aria-live="polite"',
                      f'href="geo:{latitud},{longitud}"', "Abrir en app de navegación", f"{latitud}, {longitud}",
                      "nunca se envía al servidor", "js/entregas/ir_a.js"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        self.assertNotIn(lejos.entrega.paciente.rut, html)
        self.assertEqual(self.client.get(reverse("entregasapp:ir_a", args=[cerca.pk])).status_code, 200)

    def test_solo_paradas_de_la_ruta_de_hoy_con_coordenadas(self):
        sin = visita(self.equipo, None)
        manana = visita(self.equipo, (0, 2), fecha=hoy() + timedelta(days=1))
        registrada = visita(self.equipo, (0, 3))
        registrar_entregada(self.encargado, registrada.pk, uuid.uuid4())
        respuesta = self.client.get(reverse("entregasapp:ir_a", args=[sin.pk]), follow=True)
        self.assertContains(respuesta, "Esta visita no tiene coordenadas")
        for intento in (manana, registrada):
            with self.subTest(intento=intento.pk):
                respuesta = self.client.get(reverse("entregasapp:ir_a", args=[intento.pk]), follow=True)
                self.assertContains(respuesta, "Esa visita ya no está en tu ruta de hoy")
        ajena = visita(self.equipo, (0, 4), encargado=self.equipo["encargado2"])
        self.assertEqual(self.client.get(reverse("entregasapp:ir_a", args=[ajena.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("entregasapp:ir_a", args=[999999])).status_code, 404)


class RutasTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.url = reverse("entregasapp:rutas")

    def ver(self, actor, **parametros):
        self.client.force_login(actor)
        return self.client.get(self.url, parametros)

    def test_hoy_igual_a_lo_que_ve_el_encargado_y_sin_acciones(self):
        a, b, c = (visita(self.equipo, en) for en in ((0, 3), (0, 1), (0, 2)))
        atrasada = visita(self.equipo, (1, 1))
        from entregasapp.models import IntentoEntrega
        IntentoEntrega.objects.filter(pk=atrasada.pk).update(fecha_programada=hoy() - timedelta(days=1))
        registrada = visita(self.equipo, (2, 2))
        registrar_entregada(self.encargado, registrada.pk, uuid.uuid4())
        mover_parada(self.encargado, c.pk, "1", 0, uuid.uuid4())
        respuesta = self.ver(self.equipo["qf"], encargado=self.encargado.pk, fecha=hoy().isoformat())
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        html = respuesta.content.decode()
        ruta = ruta_del_dia(self.encargado)
        datos = datos_json(html, "datos-mapa")
        self.assertEqual([p["intento"] for p in datos["paradas"]], [p.intento.pk for p in ruta.paradas])
        self.assertEqual(datos["consulta"], True)
        self.assertTrue(all(p["url_registrar"] == "" and p["url_ir"] == "" for p in datos["paradas"]))
        for texto in ("Orden guardado por el encargado a las", "Registradas hoy (1)", "Atrasada desde el",
                      "Ruta de Persona Sintética"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        for accion in (reverse("entregasapp:orden_mover"), "Ir a esta parada", "?resultado=entregada", "Mover a la posición"):
            with self.subTest(sin=accion):
                self.assertNotIn(accion, html)
        self.assertLess(html.index(f'id="parada-{c.pk}"'), html.index(f'id="parada-{b.pk}"'))
        self.assertIn(a.entrega.paciente.apellidos, html)

    def test_fecha_futura_sugerida_desde_el_cesfam_y_fecha_pasada_rechazada(self):
        visita(self.equipo, (0, 1))
        manana = hoy() + timedelta(days=1)
        lejos, cerca = visita(self.equipo, (0, 5), fecha=manana), visita(self.equipo, (0, 2), fecha=manana)
        respuesta = self.ver(self.equipo["admin"], encargado=self.encargado.pk, fecha=manana.isoformat())
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        datos = datos_json(html, "datos-mapa")
        self.assertEqual([p["intento"] for p in datos["paradas"]], [cerca.pk, lejos.pk])
        self.assertIsNone(datos["partida"])
        self.assertIn("Orden sugerido desde el CESFAM", html)
        self.assertIn("fecha posterior", html)
        self.assertNotIn("Registradas hoy", html)
        ayer = self.ver(self.equipo["qf"], encargado=self.encargado.pk, fecha=(hoy() - timedelta(days=1)).isoformat())
        self.assertContains(ayer, "Elige hoy o una fecha posterior", status_code=400)
        self.assertNotContains(ayer, "datos-mapa", status_code=400)

    def test_encargado_no_valido_se_rechaza_con_texto(self):
        for encargado in (self.equipo["qf"].pk, self.equipo["tecnico"].pk, 999999, "x"):
            with self.subTest(encargado=encargado):
                respuesta = self.ver(self.equipo["qf"], encargado=encargado, fecha=hoy().isoformat())
                self.assertContains(respuesta, "Elige un encargado de terreno con cuenta activa.", status_code=400)
        sin_filtro = self.ver(self.equipo["qf"])
        self.assertContains(sin_filtro, "Elige un encargado y una fecha")

    def test_el_tecnico_y_el_encargado_no_acceden(self):
        for actor in ("tecnico", "encargado"):
            with self.subTest(actor=actor):
                self.assertEqual(self.ver(self.equipo[actor], encargado=self.encargado.pk).status_code, 403)

    def test_pestanas_por_perfil(self):
        rutas, mapa = reverse("entregasapp:rutas"), reverse("entregasapp:mapa")
        for actor, ve, no_ve in (("qf", [rutas], [mapa]), ("admin", [rutas], [mapa]),
                                 ("tecnico", [], [rutas, mapa]), ("encargado", [mapa], [rutas])):
            self.client.force_login(self.equipo[actor])
            html = self.client.get(reverse("entregasapp:domicilios")).content.decode()
            pestanas = html[html.index('class="pestanas"'):html.index("</nav>", html.index('class="pestanas"'))]
            for url in ve:
                with self.subTest(actor=actor, ve=url):
                    self.assertIn(f'href="{url}"', pestanas)
            for url in no_ve:
                with self.subTest(actor=actor, no_ve=url):
                    self.assertNotIn(f'href="{url}"', pestanas)


class MapaDomicilioTests(TestCase):
    def setUp(self):
        self.equipo = equipo()

    def test_mapa_pequeno_con_coordenadas_y_texto_sin_ellas(self):
        con = paciente(edad=88)
        receta(con)
        latitud, longitud = punto_km(1, 1)
        guardar_domicilio(self.equipo["qf"], con.pk, {"sector": "rojo", "direccion": "Camino sintético", "latitud": latitud,
                                                      "longitud": longitud, "precision_metros": "12"})
        sin = paciente(edad=90)
        receta(sin)
        guardar_domicilio(self.equipo["qf"], sin.pk, {"sector": "rojo", "direccion": "Camino sintético 2"})
        for actor in ("tecnico", "encargado", "qf", "admin"):
            self.client.force_login(self.equipo[actor])
            with self.subTest(actor=actor):
                html = self.client.get(reverse("entregasapp:domicilio", args=[con.pk])).content.decode()
                datos = datos_json(html, "datos-punto")
                self.assertEqual((f"{datos['lat']:.6f}", f"{datos['lon']:.6f}", datos["precision"]), (latitud, longitud, 12))
                self.assertNotIn(con.rut, json.dumps(datos))
                self.assertIn("Ubicación en el mapa", html)
                self.assertIn("vendor/leaflet/leaflet.js", html)
                html = self.client.get(reverse("entregasapp:domicilio", args=[sin.pk])).content.decode()
                self.assertIsNone(datos_json(html, "datos-punto"))
                self.assertNotIn("vendor/leaflet/leaflet.js", html)
        self.client.force_login(self.equipo["tecnico"])
        self.assertContains(self.client.get(reverse("entregasapp:domicilio", args=[sin.pk])), "Sin coordenadas")
