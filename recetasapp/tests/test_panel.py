"""Tablero de recetas, lista con filtros, filtro del padrón y menú separado de Padrón y Recetas."""

import re
from datetime import date, datetime
from random import Random
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import EntregaReceta, Paciente, Receta
from recetasapp.services import crear_receta
from .ayudas import actores, cargar, fila

HOY = date(2026, 11, 2)


def momento(dia, mes=11, hora=12):
    return timezone.make_aware(datetime(2026, mes, dia, hora, 0))


@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class PanelTests(TestCase):
    def setUp(self):
        reloj = patch("recetasapp.services.timezone.localdate", return_value=HOY)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.actores = actores()
        self.ruts = iter(generar_ruts(60, Random(5)))
        self.pacientes = {}
        self.recetas = {}

    def receta(self, nombre, inicio, meses=6, maximo=6, completadas=0):
        paciente = Paciente.objects.create(rut=next(self.ruts), nombres=nombre, apellidos="Sintético", fecha_nacimiento=date(1950, 1, 1))
        receta = crear_receta(self.actores["qf"], paciente_id=paciente.pk, codigo=f"P-{nombre}", fecha_inicio=inicio, vigencia_meses=meses, max_entregas=maximo)
        if completadas:
            Receta.objects.filter(pk=receta.pk).update(entregas_completadas=completadas)
        self.pacientes[nombre], self.recetas[nombre] = paciente, receta
        return receta

    def entregas(self, receta, *momentos):
        """Entregas con fecha propia: `creado_en` se fija a mano porque lo pone el servidor al crearlas."""
        for numero, cuando in enumerate(momentos, start=1):
            entrega = EntregaReceta.objects.create(receta=receta, numero=numero)
            EntregaReceta.objects.filter(pk=entrega.pk).update(creado_en=cuando)

    def escenario(self):
        self.receta("Holgada", date(2026, 1, 1), meses=12)    # último día 2026-12-31
        self.receta("Pronta", date(2026, 6, 20))              # fin 2026-12-20: 48 días
        self.receta("Urgente", date(2026, 5, 20))             # fin 2026-11-20: 18 días
        self.receta("Futura", date(2027, 1, 1))
        self.receta("Agotada", date(2026, 9, 1), completadas=6)
        self.receta("Vencida", date(2025, 1, 1))

    def entrar(self, actor="qf"):
        self.client.force_login(self.actores[actor])

    def tablero(self, **parametros):
        return self.client.get(reverse("recetasapp:recetas"), parametros).context["tablero"]

    # --- Tablero: cifras -----------------------------------------------------------------------------------
    def test_las_cifras_principales_enlazan_a_su_lista(self):
        self.escenario()
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        kpis = {k["clave"]: k for k in respuesta.context["tablero"]["kpis"]}
        self.assertEqual([kpis[c]["valor"] for c in ("vigentes", "por-vencer", "sin-vigente", "entregas")], [3, 1, 3, 0])
        lista = reverse("recetasapp:recetas")
        self.assertEqual(kpis["vigentes"]["enlace"], f"{lista}?situacion=vigente#listado")
        self.assertEqual(kpis["por-vencer"]["enlace"], f"{lista}?situacion=por_vencer#listado")
        self.assertEqual(kpis["sin-vigente"]["enlace"], f"{reverse('recetasapp:pacientes')}?filtro=sin_vigente")
        for clave in ("vigentes", "por-vencer", "sin-vigente"):
            self.assertContains(respuesta, f'href="{kpis[clave]["enlace"]}"')
        self.assertTrue(kpis["por-vencer"]["atencion"])
        self.assertEqual(respuesta["Cache-Control"].find("no-store") >= 0, True)

    def test_entregas_del_mes_comparan_con_el_mes_anterior(self):
        self.escenario()
        receta = self.recetas["Holgada"]
        self.entregas(receta, momento(1), momento(2), momento(20, mes=10), momento(31, mes=10), momento(30, mes=9))
        self.entrar()
        kpi = {k["clave"]: k for k in self.tablero()["kpis"]}["entregas"]
        self.assertEqual(kpi["valor"], 2)
        self.assertEqual(kpi["nota"], "2 el mes pasado")

    # --- Tablero: anillo -----------------------------------------------------------------------------------
    def test_el_anillo_reparte_las_recetas_y_sus_porcentajes_suman_cien(self):
        self.escenario()
        self.entrar()
        anillo = self.tablero()["anillo"]
        self.assertEqual([(p["clave"], p["cantidad"]) for p in anillo["partes"]], [("vigente", 3), ("futura", 1), ("agotada", 1), ("vencida", 1)])
        self.assertEqual(anillo["total"], 6)
        self.assertEqual(sum(p["porcentaje"] for p in anillo["partes"]), 100)
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        for clave in ("vigente", "futura", "agotada", "vencida"):
            self.assertContains(respuesta, f'href="{reverse("recetasapp:recetas")}?situacion={clave}#listado"')
        # La cifra va en texto, no solo en el dibujo.
        self.assertContains(respuesta, "<strong>3</strong>")

    def test_los_atributos_svg_usan_punto_decimal_aunque_la_configuracion_regional_use_coma(self):
        self.escenario()
        self.entrar()
        html = self.client.get(reverse("recetasapp:recetas")).content.decode()
        for atributo in re.findall(r'(?:stroke-dasharray|stroke-dashoffset|cx|cy|x1|x2|y1|y2|x|y)="([^"]*)"', html):
            self.assertNotIn(",", atributo)
        self.assertRegex(html, r'stroke-dasharray="[0-9.]+ 100"')

    # --- Tablero: entregas por día -------------------------------------------------------------------------
    def test_la_linea_cuenta_entregas_por_dia_con_ceros_y_ofrece_los_datos_en_tabla(self):
        self.escenario()
        self.entregas(self.recetas["Holgada"], momento(2), momento(2, hora=18), momento(1), momento(25, mes=10))
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        linea = respuesta.context["tablero"]["linea"]
        por_dia = {p["fecha"]: p["valor"] for p in linea["puntos"]}
        self.assertEqual(len(por_dia), 30)
        self.assertEqual((por_dia[date(2026, 11, 2)], por_dia[date(2026, 11, 1)], por_dia[date(2026, 10, 25)], por_dia[date(2026, 10, 30)]), (2, 1, 1, 0))
        self.assertEqual((linea["total"], linea["maximo"], linea["dia_maximo"]), (4, 2, date(2026, 11, 2)))
        self.assertContains(respuesta, '<svg class="linea"')
        self.assertContains(respuesta, "Ver los datos en una tabla")
        self.assertContains(respuesta, "4 entregas en 30 días")

    def test_el_periodo_se_elige_por_la_url_y_un_valor_invalido_vuelve_a_treinta_dias(self):
        self.escenario()
        self.entregas(self.recetas["Holgada"], momento(2), momento(25, mes=10))
        self.entrar()
        self.assertEqual(self.tablero(periodo=7)["periodo"], 7)
        self.assertEqual(len(self.tablero(periodo=7)["linea"]["puntos"]), 7)
        self.assertEqual(self.tablero(periodo=7)["linea"]["total"], 1)
        self.assertEqual(self.tablero(periodo=90)["linea"]["total"], 2)
        for invalido in ("999", "abc", "-7", ""):
            with self.subTest(periodo=invalido):
                self.assertEqual(self.tablero(periodo=invalido)["periodo"], 30)
        respuesta = self.client.get(reverse("recetasapp:recetas"), {"periodo": 7})
        self.assertContains(respuesta, '<a href="?periodo=7#entregas" aria-current="true">7 días</a>')

    def test_sin_entregas_el_grafico_se_reemplaza_por_una_explicacion(self):
        self.escenario()
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "Todavía no hay entregas confirmadas en este periodo.")
        self.assertNotContains(respuesta, '<svg class="linea"')

    # --- Tablero: vencimientos, ranking y carga ------------------------------------------------------------
    def test_las_barras_cuentan_vigentes_por_mes_de_su_ultimo_dia(self):
        self.escenario()
        self.entrar()
        barras = self.tablero()["barras"]
        self.assertEqual([(b["etiqueta"], b["valor"]) for b in barras["barras"]][:2], [("nov", 1), ("dic", 2)])
        self.assertEqual(barras["total"], 3)
        self.assertEqual(barras["barras"][1]["altura"], "100")
        self.assertEqual(barras["barras"][0]["altura"], "50")
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "noviembre de 2026")

    def test_el_ranking_ordena_por_la_que_vence_primero_y_cuenta_los_dias(self):
        self.escenario()
        self.receta("Cercana", date(2026, 5, 10))             # fin 2026-11-10: 8 días
        self.receta("Manana", date(2026, 5, 3))               # fin 2026-11-03: queda hoy
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        filas = respuesta.context["tablero"]["por_vencer"]
        self.assertEqual([(r.paciente.nombres, r.dias) for r in filas], [("Manana", 1), ("Cercana", 8), ("Urgente", 18)])
        self.assertContains(respuesta, "Vence mañana")
        self.assertContains(respuesta, "En 8 días")
        self.assertContains(respuesta, "Ver las 3 por vencer")

    def test_el_ranking_muestra_a_lo_sumo_seis_y_enlaza_al_resto(self):
        for i in range(8):
            self.receta(f"Cerca{i}", date(2026, 5, 10 + i))
        self.entrar()
        tablero = self.tablero()
        self.assertEqual(len(tablero["por_vencer"]), 6)
        self.assertEqual(tablero["por_vencer_total"], 8)

    def test_sin_recetas_por_vencer_el_ranking_lo_dice(self):
        self.receta("Holgada", date(2026, 1, 1), meses=12)
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "No hay recetas vigentes que venzan en los próximos 30 días.")
        self.assertNotContains(respuesta, "Ver las")

    def test_la_ultima_carga_enlaza_a_su_reporte_solo_para_quien_puede_importar(self):
        carga = cargar(self.actores["qf"], [fila()])
        reporte = reverse("recetasapp:importacion_detalle", args=[carga.referencia])
        self.entrar("qf")
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "Última carga del padrón")
        self.assertContains(respuesta, reverse("recetasapp:importacion_detalle", args=[carga.referencia]))
        self.assertContains(respuesta, reverse("recetasapp:importacion_nueva"))
        self.assertEqual(respuesta.context["tablero"]["carga"].pk, carga.pk)
        self.entrar("tecnico")
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "Última carga del padrón")
        self.assertNotContains(respuesta, reporte)
        self.assertNotContains(respuesta, reverse("recetasapp:importacion_nueva"))

    def test_sin_datos_el_tablero_explica_en_vez_de_dibujar_graficos_vacios(self):
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "Todavía no hay recetas que mostrar.")
        self.assertContains(respuesta, "Todavía no se ha cargado ningún archivo.")
        self.assertContains(respuesta, "Ninguna receta vigente vence en los próximos seis meses.")
        self.assertNotContains(respuesta, '<svg class="anillo"')

    # --- Lista de recetas ----------------------------------------------------------------------------------
    def test_lista_filtra_por_situacion_y_cada_pestana_trae_su_cantidad(self):
        self.escenario()
        self.entrar("tecnico")
        ruta = reverse("recetasapp:recetas")
        respuesta = self.client.get(ruta)
        self.assertEqual({p["clave"]: p["cantidad"] for p in respuesta.context["pestanas"]},
                         {"": 6, "vigente": 3, "por_vencer": 1, "futura": 1, "agotada": 1, "vencida": 1})
        esperadas = {"vigente": 3, "futura": 1, "agotada": 1, "vencida": 1, "por_vencer": 1}
        for clave, cantidad in esperadas.items():
            with self.subTest(clave=clave):
                por_get = self.client.get(ruta, {"situacion": clave})
                por_post = self.client.post(ruta, {"situacion": clave, "buscar": "", "pagina": 1})
                for respuesta in (por_get, por_post):
                    self.assertEqual(respuesta.context["page_obj"].paginator.count, cantidad)
                    self.assertTrue(all(r.situacion["clave"] == (clave if clave != "por_vencer" else "vigente") for r in respuesta.context["page_obj"]))

    def test_filas_traen_insignia_con_texto_y_las_entregas_que_quedan(self):
        self.escenario()
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"), {"situacion": "vigente"})
        self.assertContains(respuesta, "0 de 6 entregas")
        self.assertContains(respuesta, "Quedan 6")
        respuesta = self.client.get(reverse("recetasapp:recetas"), {"situacion": "vencida"})
        self.assertContains(respuesta, "No admite entregas")

    def test_lista_vigente_va_con_las_que_vencen_primero_arriba(self):
        self.escenario()
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"), {"situacion": "vigente"})
        self.assertEqual([r.paciente.nombres for r in respuesta.context["page_obj"]], ["Urgente", "Pronta", "Holgada"])

    def test_busqueda_por_rut_nombre_y_codigo_viaja_por_post_y_no_queda_en_la_url(self):
        self.escenario()
        self.entrar()
        ruta = reverse("recetasapp:recetas")
        rut = self.pacientes["Pronta"].rut
        for buscar, esperado in ((rut, ["Pronta"]), ("urgente", ["Urgente"]), ("P-Vencida", ["Vencida"]), ("zzzz", [])):
            with self.subTest(buscar=buscar):
                respuesta = self.client.post(ruta, {"buscar": buscar, "pagina": 1, "situacion": ""})
                self.assertEqual([r.paciente.nombres for r in respuesta.context["page_obj"]], esperado)
                self.assertNotIn(rut, respuesta.wsgi_request.get_full_path())
                self.assertEqual(respuesta["Referrer-Policy"], "same-origin")
        respuesta = self.client.post(ruta, {"buscar": "Sintético", "pagina": 1, "situacion": "futura"})
        self.assertEqual([r.paciente.nombres for r in respuesta.context["page_obj"]], ["Futura"])

    def test_situacion_desconocida_no_lista_nada_y_avisa(self):
        self.escenario()
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"), {"situacion": "inventada"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["page_obj"].paginator.count, 0)
        self.assertContains(respuesta, 'role="alert"')

    def test_el_boton_buscar_conserva_la_situacion_y_la_paginacion_la_reenvia(self):
        self.escenario()
        self.entrar()
        ruta = reverse("recetasapp:recetas")
        html = self.client.get(ruta, {"situacion": "vigente"}).content.decode()
        # «Buscar» es el primer botón de envío de la lista: Enter en el campo conserva la situación elegida.
        envios = re.findall(r'<button class="(?:boton|filtro)" type="submit" name="situacion" value="([a-z_]*)"', html)
        self.assertEqual(envios[0], "vigente")
        self.assertEqual(sum('aria-pressed="true"' in boton for boton in re.findall(r"<button class=\"filtro\"[^>]*>", html)), 1)
        for indice in range(21):
            self.receta(f"Paginada{indice:02d}", date(2026, 1, 1), meses=12)
        html = self.client.post(ruta, {"situacion": "vigente", "buscar": "Paginada", "pagina": 1}).content.decode()
        self.assertIn('<input type="hidden" name="situacion" value="vigente">', html)
        self.assertIn('<input type="hidden" name="buscar" value="Paginada">', html)
        # Tras buscar o paginar, el navegador vuelve a la lista y no al comienzo del tablero.
        self.assertIn('action="#listado"', html)

    def test_los_filtros_se_explican_y_se_pueden_quitar(self):
        self.escenario()
        self.entrar()
        ruta = reverse("recetasapp:recetas")
        sin_filtro = self.client.get(ruta).content.decode()
        self.assertIn("Mostrar:", sin_filtro)
        self.assertNotIn("Quitar filtros", sin_filtro)
        # Cada cantidad va en su propia insignia, separada del texto del botón.
        self.assertRegex(sin_filtro, r'Vigentes <span class="filtro-cantidad">3</span>')
        for filtrado in (self.client.get(ruta, {"situacion": "vencida"}), self.client.post(ruta, {"buscar": "Pronta", "pagina": 1, "situacion": ""})):
            self.assertContains(filtrado, f'<a class="quitar-filtros" href="{ruta}#listado">Quitar filtros</a>')
        padron = reverse("recetasapp:pacientes")
        self.assertNotContains(self.client.get(padron), "Quitar filtros")
        self.assertContains(self.client.get(padron, {"filtro": "sin_vigente"}), f'<a class="quitar-filtros" href="{padron}">Quitar filtros</a>')

    def test_la_pagina_ofrece_un_atajo_a_la_lista_y_las_cifras_con_enlace_lo_indican(self):
        self.escenario()
        for actor in ("qf", "tecnico"):
            with self.subTest(actor=actor):
                self.entrar(actor)
                respuesta = self.client.get(reverse("recetasapp:recetas"))
                self.assertContains(respuesta, '<a class="boton boton-secundario" href="#listado">Ir a la lista</a>')
        # Las tres cifras con enlace llevan flecha; la que no se puede pulsar no.
        html = self.client.get(reverse("recetasapp:recetas")).content.decode()
        self.assertEqual(html.count("kpi-ir"), 3)

    def test_lista_vacia_sin_datos_invita_a_importar_solo_a_quien_puede(self):
        self.entrar()
        self.assertContains(self.client.get(reverse("recetasapp:recetas")), "Todavía no hay recetas</h3>")
        self.assertContains(self.client.get(reverse("recetasapp:recetas")), reverse("recetasapp:importacion_nueva"))
        self.entrar("tecnico")
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "Pide a la Jefa de Farmacia")
        self.assertNotContains(respuesta, reverse("recetasapp:importacion_nueva"))

    def test_crear_receta_vive_en_recetas_y_ya_no_en_el_padron(self):
        self.entrar()
        nueva = reverse("recetasapp:receta_nueva")
        self.assertContains(self.client.get(reverse("recetasapp:recetas")), f'href="{nueva}"')
        self.assertNotContains(self.client.get(reverse("recetasapp:pacientes")), f'href="{nueva}"')
        self.entrar("tecnico")
        self.assertNotContains(self.client.get(reverse("recetasapp:recetas")), f'href="{nueva}"')

    # --- Padrón con filtro ---------------------------------------------------------------------------------
    def test_padron_filtra_a_los_pacientes_sin_receta_vigente(self):
        self.escenario()
        self.entrar()
        ruta = reverse("recetasapp:pacientes")
        esperados = {"Futura", "Agotada", "Vencida"}
        for respuesta in (self.client.get(ruta, {"filtro": "sin_vigente"}), self.client.post(ruta, {"filtro": "sin_vigente", "buscar": "", "pagina": 1})):
            self.assertEqual({p.nombres for p in respuesta.context["page_obj"]}, esperados)
            self.assertContains(respuesta, "sin receta vigente: hoy no pueden retirar medicamentos")
        self.assertEqual(self.client.get(ruta).context["page_obj"].paginator.count, 6)
        respuesta = self.client.post(ruta, {"filtro": "sin_vigente", "buscar": "Vencida", "pagina": 1})
        self.assertEqual([p.nombres for p in respuesta.context["page_obj"]], ["Vencida"])
        respuesta = self.client.post(ruta, {"filtro": "sin_vigente", "buscar": "Holgada", "pagina": 1})
        self.assertEqual(respuesta.context["page_obj"].paginator.count, 0)

    def test_padron_conserva_el_filtro_en_el_boton_buscar_y_en_la_paginacion(self):
        self.escenario()
        self.entrar()
        html = self.client.get(reverse("recetasapp:pacientes"), {"filtro": "sin_vigente"}).content.decode()
        self.assertIn('type="submit" name="filtro" value="sin_vigente">Buscar</button>', html)
        # El control de tamaño de texto también usa aria-pressed: solo se cuentan los botones del filtro.
        self.assertEqual(sum('aria-pressed="true"' in boton for boton in re.findall(r'<button class="filtro"[^>]*>', html)), 1)
        respuesta = self.client.get(reverse("recetasapp:pacientes"), {"filtro": "inventado"})
        self.assertEqual(respuesta.context["page_obj"].paginator.count, 0)

    def test_padron_sin_nadie_sin_vigente_lo_dice(self):
        self.receta("Holgada", date(2026, 1, 1), meses=12)
        self.entrar()
        self.assertContains(self.client.get(reverse("recetasapp:pacientes"), {"filtro": "sin_vigente"}), "Todos los pacientes tienen una receta vigente")

    # --- Menú ----------------------------------------------------------------------------------------------
    def enlaces(self, ruta):
        html = self.client.get(ruta).content.decode()
        inicio = html.index('aria-label="Navegación principal"')
        menu = html[inicio:html.index("</nav>", inicio)]
        return {m.group(1): 'aria-current="page"' in m.group(0) for m in re.finditer(r'<a class="nav-enlace" href="([^"]+)"[^>]*>', menu)}

    def test_el_menu_separa_padron_y_recetas_segun_el_rol_y_no_tiene_resumen(self):
        padron, recetas = reverse("recetasapp:pacientes"), reverse("recetasapp:recetas")
        for actor, esperado in (("qf", {padron, recetas}), ("admin", {padron, recetas}), ("tecnico", {padron, recetas}), ("encargado", set())):
            with self.subTest(actor=actor):
                self.entrar(actor)
                html = self.client.get(reverse("coreapp:inicio")).content.decode()
                self.assertEqual({h for h in self.enlaces(reverse("coreapp:inicio")) if h.startswith("/recetas/")}, esperado)
                self.assertNotIn(">Resumen<", html)

    def test_el_menu_se_pliega_con_un_boton_asociado_a_la_navegacion(self):
        self.entrar()
        html = self.client.get(reverse("coreapp:inicio")).content.decode()
        self.assertRegex(html, r'<button class="nav-toggle" type="button" aria-expanded="false" aria-controls="menu-principal" data-menu-boton>')
        self.assertIn('id="menu-principal" aria-label="Navegación principal" data-menu', html)
        self.assertIn("js/menu.js", html)
        self.client.logout()
        self.assertNotIn("nav-toggle", self.client.get(reverse("usuariosapp:login")).content.decode())

    def test_cada_pantalla_marca_una_sola_entrada_como_pagina_actual(self):
        self.escenario()
        receta = Receta.objects.first()
        carga = cargar(self.actores["qf"], [fila()])
        padron, recetas = reverse("recetasapp:pacientes"), reverse("recetasapp:recetas")
        casos = {
            padron: padron, recetas: recetas,
            reverse("recetasapp:paciente_detalle", args=[receta.paciente_id]): padron,
            reverse("recetasapp:importaciones"): padron,
            reverse("recetasapp:importacion_nueva"): padron,
            reverse("recetasapp:importacion_detalle", args=[carga.referencia]): padron,
            reverse("recetasapp:receta_detalle", args=[receta.pk]): recetas,
            reverse("recetasapp:receta_nueva"): recetas,
            reverse("recetasapp:receta_renovar", args=[receta.pk]): recetas,
        }
        self.entrar()
        for ruta, actual in casos.items():
            with self.subTest(ruta=ruta):
                marcadas = {href for href, marcada in self.enlaces(ruta).items() if marcada and href.startswith("/recetas/")}
                self.assertEqual(marcadas, {actual})
        self.entrar("tecnico")
        entrega = reverse("recetasapp:entrega_confirmar", args=[receta.pk])
        marcadas = {href for href, marcada in self.enlaces(entrega).items() if marcada and href.startswith("/recetas/")}
        self.assertEqual(marcadas, {recetas})

    def test_inicio_ofrece_recetas_y_padron_por_separado_a_quien_corresponde(self):
        for actor in ("qf", "tecnico"):
            with self.subTest(actor=actor):
                self.entrar(actor)
                html = self.client.get(reverse("coreapp:inicio")).content.decode()
                self.assertIn(f'href="{reverse("recetasapp:recetas")}">Recetas</a>', html)
                self.assertIn(f'href="{reverse("recetasapp:pacientes")}">Padrón</a>', html)
                self.assertNotIn("Abrir resumen", html)
        self.entrar("encargado")
        html = self.client.get(reverse("coreapp:inicio")).content.decode()
        self.assertNotIn(f'href="{reverse("recetasapp:recetas")}">Recetas</a>', html)
