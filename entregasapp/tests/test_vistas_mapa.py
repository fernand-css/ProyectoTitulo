"""RF-09-01 a RF-09-11 y RF-09-16 a RF-09-25 por HTTP: «Mis entregas» con tarjetas compactas, mapa, «Ir a esta
parada», «Rutas» y mapa del domicilio. Un OSRM simulado (distancia = línea recta) da el orden «por camino»."""

import json
import re
import uuid
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from entregasapp.consultas import ruta_del_dia
from entregasapp.services import guardar_domicilio, mover_parada, registrar_entregada, registrar_no_entregada
from .ayudas import equipo, hoy, paciente, punto_km, receta, visita
from .osrm_simulado import ConOsrmSimulado


def datos_json(html, ident):
    """Contenido de un json_script de la página."""
    coincidencia = re.search(rf'<script id="{ident}" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(coincidencia.group(1)) if coincidencia else None


def operaciones(html):
    return re.findall(r'name="operacion_id" value="([^"]+)"', html)


class MisEntregasRutaTests(ConOsrmSimulado, TestCase):
    def setUp(self):
        super().setUp()
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
        for texto in ("Orden sugerido según distancia por camino, desde la última visita registrada.",
                      "Por visitar (3)", "Registradas hoy (2)", "Próximas (1)",
                      "Por visitar en orden (<span data-ruta-cantidad>2</span>)",
                      "Sin coordenadas: fuera del orden sugerido (<span data-ruta-sin-cantidad>1</span>)",
                      "Sector Azul · Localidad demo 4", 'data-grupo="Sector Azul · Localidad demo 4"',
                      "No entregada: Domicilio no encontrado", "Recorrido aprox. por camino:"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        # 2026-11-22: bajo el rótulo solo queda el total; las cantidades se retiraron del resumen del encargado.
        resumen = re.search(r"<p[^>]*data-ruta-resumen[^>]*>(.*?)</p>", html, re.S).group(1)
        self.assertNotIn("Por visitar (", resumen)
        self.assertNotIn("Registradas hoy (", resumen)
        # Los textos de ayuda quedan detrás de un botón informativo que los muestra 3 segundos (ayuda_breve.js).
        for ayuda in ('aria-controls="ayuda-orden"', 'id="ayuda-orden" data-ayuda-texto>Cambia el orden',
                      'aria-controls="ayuda-sin-coordenadas"',
                      'id="ayuda-sin-coordenadas" data-ayuda-texto>No entran al cálculo', "js/entregas/ayuda_breve.js"):
            with self.subTest(ayuda=ayuda):
                self.assertIn(ayuda, html)
        self.assertEqual(html.count("data-ayuda-boton hidden"), 2)
        # La barra de estado sin conexión trae la X para cerrarla (sin_conexion.js la muestra).
        self.assertIn("data-cerrable hidden>", html)
        self.assertIn('data-cerrar-estado hidden><svg class="icono" aria-hidden="true" focusable="false"><use href="#i-cerrar"/></svg>'
                      '<span class="sr-only">Cerrar el aviso de conexión</span>', html)
        for retirado in ("Mover a la posición", "no considera caminos", "orden-mover"):  # RF-09-17 y RF-09-20
            with self.subTest(retirado=retirado):
                self.assertNotIn(retirado, html)
        # La última registrada (no entregada, a 1 km este y 2 km norte) es la partida: desde ahí A (0, 2) queda a 1 km
        # y luego B (0, 1) camino al CESFAM. Desde el CESFAM habría sido B, A.
        self.assertLess(html.index(f'id="parada-{a.pk}"'), html.index(f'id="parada-{b.pk}"'))
        self.assertLess(html.index(f'id="parada-{b.pk}"'), html.index(f'id="parada-{sin.pk}"'))
        self.assertLess(html.index(f'id="parada-{sin.pk}"'), html.index(f'id="parada-{manana.pk}"'))
        self.assertIn(f'href="{reverse("entregasapp:ir_a", args=[a.pk])}"', html)
        self.assertNotIn(reverse("entregasapp:ir_a", args=[sin.pk]), html)  # sin coordenadas, sin guía
        self.assertNotIn(reverse("entregasapp:ir_a", args=[manana.pk]), html)
        self.assertEqual(html.count(f'action="{reverse("entregasapp:orden_mover")}"'), 3)  # flechas × 3 visitas
        self.assertEqual(len(set(operaciones(html))), 4)  # una por tarjeta y la de «Volver al orden sugerido»
        self.assertIn('value="subir"', html)
        self.assertEqual(html.count('class="visita-franja"'), 3)
        # «Volver al orden sugerido» existe oculto: orden.js lo muestra al guardar el primer orden propio.
        self.assertIn('<details class="panel restablecer-orden" data-restablecer hidden>', html)
        # Próximas sin número ni controles.
        tarjeta_manana = html[html.index(f'id="parada-{manana.pk}"'):]
        self.assertNotIn("Parada ", tarjeta_manana[:200])

    def test_tarjetas_compactas_con_expandir_mapa_al_expandir_y_proximas_con_fecha(self):
        """RF-09-16 y RF-09-18: compactas con número, rótulos, nombre, dirección y botones; detalle aparte."""
        a = self.visita((0, 2))
        sin = self.visita(None, sector="azul", localidad="Localidad demo 4")
        manana = self.visita((0, 3), fecha=hoy() + timedelta(days=1))
        html = self.client.get(reverse("entregasapp:mis")).content.decode()

        def tarjeta(intento):
            inicio = html.index(f'id="parada-{intento.pk}"')
            return html[inicio:html.index("</article>", inicio)]

        de_a = tarjeta(a)
        nombre = f"{a.entrega.paciente.nombres} {a.entrega.paciente.apellidos}"
        for texto in ("Parada 1", nombre, 'class="visita-direccion"', "Entregar<span", "No entregada<span",
                      f'aria-expanded="false" aria-controls="detalle-{a.pk}" data-expandir hidden', f'id="detalle-{a.pk}"',
                      "data-mapa-tarjeta", 'data-latitud="', "Ir a esta parada", "Detalles del domicilio",
                      f"Bajar parada 1: {nombre}"):
            with self.subTest(texto=texto):
                self.assertIn(texto, de_a)
        self.assertNotIn(a.entrega.paciente.rut, de_a)
        # La flecha que no aplica va oculta (se muestra al reordenar con JavaScript).
        self.assertIn('data-flecha="subir" hidden', de_a)
        self.assertIn("Domicilio sin coordenadas", tarjeta(sin))
        self.assertNotIn("data-mapa-tarjeta", tarjeta(sin))
        proxima = tarjeta(manana)
        self.assertIn(f"Programada para el {manana.fecha_programada:%d/%m/%Y}", proxima)
        self.assertNotIn("?resultado=entregada", proxima)
        self.assertIn("data-expandir", proxima)
        self.assertNotIn("data-franja", proxima)
        for recurso in ("js/entregas/tarjetas.js", "js/entregas/orden.js", "vendor/leaflet/leaflet.js", 'id="datos-teselas"'):
            self.assertIn(recurso, html)

    def test_mover_con_javascript_responde_el_orden_en_json(self):
        """RF-09-17: flechas y arrastre por fetch; el servidor manda el orden, la versión, el rótulo y el total."""
        a, b, c = self.visita((0, 3)), self.visita((0, 1)), self.visita((0, 2))
        url = reverse("entregasapp:orden_mover")
        cabecera = {"HTTP_ACCEPT": "application/json"}
        respuesta = self.client.post(url, {"intento": a.pk, "destino": "1", "version": 0, "operacion_id": uuid.uuid4()},
                                     **cabecera)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        datos = respuesta.json()
        self.assertEqual((datos["ok"], datos["version"], datos["manual"]), (True, 1, True))
        self.assertEqual([p["intento"] for p in datos["orden"]], [a.pk, b.pk, c.pk])
        self.assertEqual([p["numero"] for p in datos["orden"]], [1, 2, 3])
        self.assertIn("Tu orden de hoy, guardado a las", datos["rotulo"])
        self.assertIn("Recorrido aprox. por camino:", datos["resumen"])
        self.assertNotIn("Por visitar (", datos["resumen"])
        self.assertNotIn(a.entrega.paciente.rut, respuesta.content.decode())
        # Arrastre de la parada 3 a la posición 1 desde la versión nueva.
        arrastre = self.client.post(url, {"intento": c.pk, "destino": "1", "version": 1, "operacion_id": uuid.uuid4()},
                                    **cabecera)
        self.assertEqual([p["intento"] for p in arrastre.json()["orden"]], [c.pk, a.pk, b.pk])
        # Desde una versión vieja: conflicto con el aviso y sin cambios.
        choque = self.client.post(url, {"intento": b.pk, "destino": "1", "version": 1, "operacion_id": uuid.uuid4()},
                                  **cabecera)
        self.assertEqual(choque.status_code, 409)
        self.assertEqual(choque.json(), {"ok": False, "error": "Tu orden cambió en otro dispositivo; revisa la lista."})
        self.assertEqual([p.intento.pk for p in ruta_del_dia(self.encargado).paradas], [c.pk, a.pk, b.pk])
        borde = self.client.post(url, {"intento": c.pk, "destino": "subir", "version": 2, "operacion_id": uuid.uuid4()},
                                 **cabecera)
        self.assertEqual(borde.status_code, 400)
        self.assertEqual(self.client.post(url, {"intento": "x"}, **cabecera).status_code, 400)

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
        self.assertContains(respuesta, "Orden sugerido según distancia por camino, desde el CESFAM.")
        self.assertEqual([p.intento.pk for p in ruta_del_dia(self.encargado).paradas], [b.pk, a.pk])

    def test_sin_entregas_lo_dice_con_texto(self):
        self.assertContains(self.client.get(reverse("entregasapp:mis")), "No tienes entregas asignadas")


class MapaTests(ConOsrmSimulado, TestCase):
    def setUp(self):
        super().setUp()
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
        self.assertNotIn("linea", datos)  # RF-09-21: sin línea del recorrido completo
        self.assertEqual(datos["distancia"], "camino")
        self.assertEqual(datos["total_km"], ruta.total_km)
        self.assertIsNotNone(datos["total_km"])
        self.assertEqual((datos["url_tramo"], datos["url_cercana"], datos["url_mover"]),
                         (reverse("entregasapp:tramo"), reverse("entregasapp:cercana"), reverse("entregasapp:orden_mover")))
        self.assertEqual(datos["version"], 0)
        self.assertEqual(datos["sin_marcador"], 1)
        self.assertEqual(datos["teselas"]["atribucion"], "© colaboradores de OpenStreetMap")
        self.assertIn("{z}", datos["teselas"]["url"])
        self.assertTrue(datos["paradas"][0]["url_ir"].startswith("/entregas/mis/ir/"))
        texto = json.dumps(datos, ensure_ascii=False)
        for persona in [p.entrega.paciente for p in (*paradas, *registradas)]:
            self.assertNotIn(persona.rut, texto)
        for privado in ("+56 9", "telefono", "Nota privada", "foto"):
            self.assertNotIn(privado, texto)
        for recurso in ("vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css", "js/entregas/mapa.js", "js/entregas/tramo.js"):
            self.assertIn(recurso, html)
        # 2026-11-22: mapa a pantalla completa; lista y símbolos en paneles desplegables, controles compactos.
        for texto in ("1 visita sin marcador", "Recorrido aprox. por camino:", '<body class="pagina-mapa">',
                      'role="region"', '<span class="mapa-panel-texto">Paradas (5)</span></summary>',
                      '<span class="mapa-panel-texto">Símbolos</span></summary>', 'aria-label="Mostrar mi posición"',
                      # 2026-11-22: auto en «Mi posición», pestañas tras el botón de tres barras y X del mensaje.
                      '<use href="#i-auto"/></svg><span>Mi posición</span>', 'aria-controls="mapa-pestanas" aria-label="Secciones de Entregas" data-mapa-menu-boton hidden',
                      'id="mapa-guia-cerrar" hidden', "Cerrar el mensaje",
                      "<span>Mi posición</span>", 'aria-label="Sugerir parada más cercana"', "<span>Más cercana</span>",
                      "Detener", "Mover al siguiente lugar", "Trazar tramo hasta aquí", 'aria-live="polite"',
                      "csrfmiddlewaretoken", "Necesita señal"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        for retirado in ("línea recta", "linea-recorrido", "punteado"):
            with self.subTest(retirado=retirado):
                self.assertNotIn(retirado, html)

    def test_con_osrm_caido_hay_marcadores_sin_total_y_con_aviso(self):
        visita(self.equipo, (0, 1))
        visita(self.equipo, (0, 2))
        self.osrm.modo = "error500"
        html = self.client.get(reverse("entregasapp:mapa")).content.decode()
        datos = datos_json(html, "datos-mapa")
        self.assertEqual((datos["distancia"], datos["total_km"]), ("recta", None))
        self.assertEqual(len(datos["paradas"]), 2)
        self.assertIn("Orden aproximado en línea recta: el servidor de rutas no respondió.", html)
        self.assertIn("Sin total del recorrido: el servidor de rutas no respondió.", html)
        self.assertNotIn("Recorrido aprox. por camino", html)

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
        self.assertEqual((datos["intento"], datos["url_tramo"]), (lejos.pk, reverse("entregasapp:tramo")))
        for texto in ("Ir a la parada 2", "Guía por camino", "Mostrar mi posición", "Leer distancia", "Detener",
                      'aria-live="polite"', f'href="geo:{latitud},{longitud}"', "Abrir en app de navegación",
                      f"{latitud}, {longitud}", "solo para calcular el tramo por camino", "no se guarda",
                      "js/entregas/tramo.js", "js/entregas/ir_a.js", "csrfmiddlewaretoken"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        for retirado in ("línea recta", "dirección en", "rumbo"):  # RF-09-23
            with self.subTest(retirado=retirado):
                self.assertNotIn(retirado, html)
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


class RutasTests(ConOsrmSimulado, TestCase):
    def setUp(self):
        super().setUp()
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
        for accion in (reverse("entregasapp:orden_mover"), "Ir a esta parada", "?resultado=entregada", "Mover a la posición",
                       "data-franja", "data-flecha", "data-fotos-abrir", "Mostrar mi posición", "Sugerir parada más cercana",
                       "Trazar tramo", reverse("entregasapp:tramo"), reverse("entregasapp:cercana")):
            with self.subTest(sin=accion):
                self.assertNotIn(accion, html)
        # RF-09-24: tarjetas compactas expandibles en modo consulta, con mapa pequeño; mapa sin línea ni posición.
        self.assertEqual(html.count("data-compacta"), len(ruta.paradas))
        self.assertIn(f'aria-controls="detalle-{a.pk}" data-expandir hidden', html)
        self.assertIn("data-mapa-tarjeta", html)
        for recurso in ("js/entregas/tarjetas.js", 'id="datos-teselas"'):
            self.assertIn(recurso, html)
        self.assertNotIn("js/entregas/tramo.js", html)
        self.assertNotIn("linea", datos)
        self.assertEqual((datos["url_tramo"], datos["url_cercana"], datos["url_mover"], datos["version"]), ("", "", "", None))
        self.assertFalse({"posicion", "yo", "encargado_lat"} & set(datos))
        self.assertEqual(datos["distancia"], "camino")
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
        self.assertIn("Orden sugerido según distancia por camino, desde el CESFAM.", html)
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
                self.assertNotIn('id="mapa-domicilio"', html)
                # Sin coordenadas no hay mapa pequeño; quien edita carga Leaflet solo para «Usar mapa» (RF-09-25).
                if actor == "tecnico":
                    self.assertNotIn("vendor/leaflet/leaflet.js", html)
        self.client.force_login(self.equipo["tecnico"])
        self.assertContains(self.client.get(reverse("entregasapp:domicilio", args=[sin.pk])), "Sin coordenadas")


class UsarMapaTests(TestCase):
    """RF-09-25: «Usar mapa» en el formulario del domicilio (el comportamiento del diálogo, en usar_mapa.test.cjs)."""

    def setUp(self):
        self.equipo = equipo()
        self.persona = paciente(edad=88)
        receta(self.persona)
        self.url = reverse("entregasapp:domicilio", args=[self.persona.pk])

    def test_el_boton_y_el_dialogo_son_para_quien_edita_y_sin_datos_del_paciente(self):
        for actor in ("qf", "encargado", "admin"):
            with self.subTest(actor=actor):
                self.client.force_login(self.equipo[actor])
                html = self.client.get(self.url).content.decode()
                for texto in ('data-usar-mapa-abrir="dialogo-usar-mapa" hidden', "Usar mapa", "Marcar el centro del mapa",
                              "Usar este punto", "Cancelar", 'aria-live="polite"', "js/entregas/usar_mapa.js",
                              "vendor/leaflet/leaflet.js", "Usar mi ubicación actual"):
                    self.assertIn(texto, html)
                datos = datos_json(html, "datos-usar-mapa")
                self.assertEqual(set(datos), {"origen", "teselas"})
                self.assertNotIn(self.persona.rut, json.dumps(datos))
        self.client.force_login(self.equipo["tecnico"])
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("data-usar-mapa-abrir", html)
        self.assertIsNone(datos_json(html, "datos-usar-mapa"))

    def test_guardar_las_coordenadas_del_mapa_deja_el_domicilio_pendiente_de_verificar(self):
        from entregasapp.services import verificar_domicilio
        latitud, longitud = punto_km(1, 1)
        domicilio = guardar_domicilio(self.equipo["qf"], self.persona.pk, {"sector": "rojo", "direccion": "Camino sintético",
                                                                          "latitud": latitud, "longitud": longitud,
                                                                          "precision_metros": "12"})
        domicilio = verificar_domicilio(self.equipo["encargado"], domicilio.pk, domicilio.version)
        self.assertIsNotNone(domicilio.verificado_en)
        nueva_latitud, nueva_longitud = punto_km(1.3, 0.8)
        self.client.force_login(self.equipo["qf"])
        respuesta = self.client.post(self.url, {"sector": "rojo", "localidad": "", "direccion": "Camino sintético",
                                                "referencias": "", "latitud": nueva_latitud, "longitud": nueva_longitud,
                                                "precision_metros": "", "version": domicilio.version})
        self.assertRedirects(respuesta, self.url, fetch_redirect_response=False)
        domicilio.refresh_from_db()
        self.assertEqual((f"{domicilio.latitud}", f"{domicilio.longitud}"), (nueva_latitud, nueva_longitud))
        self.assertIsNone(domicilio.precision_metros)
        self.assertIsNone(domicilio.verificado_en)
