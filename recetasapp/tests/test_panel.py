"""Resumen de recetas con sus gráficos, pestañas de la sección, lista con filtros, filtro de pacientes y menú."""

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

    # --- Resumen: cifras ----------------------------------------------------------------------------------
    def test_las_cifras_principales_enlazan_a_su_lista(self):
        self.escenario()
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        kpis = {k["clave"]: k for k in respuesta.context["tablero"]["kpis"]}
        self.assertEqual([kpis[c]["valor"] for c in ("vigentes", "por-vencer", "sin-vigente", "entregas")], [3, 1, 3, 0])
        lista = reverse("recetasapp:recetas_lista")
        self.assertEqual(kpis["vigentes"]["enlace"], f"{lista}?situacion=vigente")
        self.assertEqual(kpis["por-vencer"]["enlace"], f"{lista}?situacion=por_vencer")
        self.assertEqual(kpis["sin-vigente"]["enlace"], f"{reverse('recetasapp:pacientes')}?filtro=sin_vigente")
        self.assertEqual(kpis["entregas"]["enlace"], "")
        for clave in ("vigentes", "por-vencer", "sin-vigente"):
            self.assertContains(respuesta, f'href="{kpis[clave]["enlace"]}"')
        self.assertTrue(kpis["por-vencer"]["atencion"])
        self.assertEqual(respuesta["Cache-Control"].find("no-store") >= 0, True)
        # Las tres cifras con enlace llevan flecha; la que no se puede pulsar no.
        self.assertEqual(respuesta.content.decode().count("kpi-ir"), 3)

    def test_las_entregas_de_la_semana_se_comparan_con_los_siete_dias_anteriores(self):
        self.escenario()
        receta = self.recetas["Holgada"]
        # Esta semana (27 oct a 2 nov): tres. La anterior (20 a 26 oct): una. Fuera de las dos: no cuentan.
        self.entregas(receta, momento(2), momento(1), momento(27, mes=10), momento(26, mes=10), momento(19, mes=10))
        self.entrar()
        kpi = {k["clave"]: k for k in self.tablero()["kpis"]}["entregas"]
        self.assertEqual((kpi["valor"], kpi["sentido"]), (3, "sube"))
        self.assertEqual(kpi["nota"], "2 más que en los 7 días anteriores")
        self.assertEqual(len(kpi["tendencia"]["ruta"].split("L")), 14)  # una línea de 14 días
        html = self.client.get(reverse("recetasapp:recetas")).content.decode()
        self.assertIn("▲", html)  # el sentido se ve en un símbolo y se lee en la frase, no solo en el color

    def test_la_comparacion_dice_si_baja_o_si_es_igual(self):
        self.escenario()
        receta = self.recetas["Holgada"]
        self.entregas(receta, momento(2), momento(26, mes=10), momento(25, mes=10))
        self.entrar()
        kpi = {k["clave"]: k for k in self.tablero()["kpis"]}["entregas"]
        self.assertEqual((kpi["sentido"], kpi["nota"]), ("baja", "1 menos que en los 7 días anteriores"))
        EntregaReceta.objects.all().delete()
        self.entregas(receta, momento(2), momento(26, mes=10))
        kpi = {k["clave"]: k for k in self.tablero()["kpis"]}["entregas"]
        self.assertEqual((kpi["sentido"], kpi["nota"]), ("igual", "Igual que en los 7 días anteriores"))

    # --- Resumen: situación (barra segmentada) --------------------------------------------------------------
    def test_la_barra_reparte_las_recetas_y_sus_porcentajes_suman_cien(self):
        self.escenario()
        self.entrar()
        partes = self.tablero()["situacion"]
        self.assertEqual([(p["clave"], p["cantidad"]) for p in partes], [("vigente", 3), ("futura", 1), ("agotada", 1), ("vencida", 1)])
        self.assertEqual(sum(p["porcentaje"] for p in partes), 100)
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        for clave in ("vigente", "futura", "agotada", "vencida"):
            self.assertContains(respuesta, f'href="{reverse("recetasapp:recetas_lista")}?situacion={clave}"')
        # La cifra va en texto (leyenda y tooltip), no solo en el dibujo.
        self.assertContains(respuesta, "<strong>3</strong>")
        self.assertContains(respuesta, 'data-tip="Vigentes: 3 (50 %)"')
        self.assertContains(respuesta, 'class="segmentos"')

    def test_la_barra_no_dibuja_las_partes_en_cero_pero_la_leyenda_las_nombra(self):
        self.receta("Holgada", date(2026, 1, 1), meses=12)
        self.entrar()
        html = self.client.get(reverse("recetasapp:recetas")).content.decode()
        self.assertEqual(html.count('class="segmento '), 1)
        self.assertIn("Vencidas", html)
        self.assertIn("<strong>0</strong>", html)

    def test_cada_numero_de_un_atributo_svg_usa_punto_decimal_aunque_la_configuracion_regional_use_coma(self):
        self.escenario()
        self.entregas(self.recetas["Holgada"], momento(2), momento(2, hora=18), momento(1), momento(25, mes=10))
        self.entrar()
        html = self.client.get(reverse("recetasapp:recetas")).content.decode()
        html = html[html.index('class="tablero"'):]  # el resto de la página trae íconos ajenos a esta regla
        for atributo in re.findall(r'\b(?:x|y|x1|x2|y1|y2|cx|cy|width|height|viewBox|d)="([^"]*)"', html):
            self.assertNotIn(",", atributo)
        self.assertRegex(html, r'<path class="columna" d="M[0-9. ]+V')

    # --- Resumen: entregas por día (columnas con promedio) --------------------------------------------------
    def test_las_columnas_cuentan_entregas_por_dia_con_ceros_y_ofrecen_los_datos_en_tabla(self):
        self.escenario()
        self.entregas(self.recetas["Holgada"], momento(2), momento(2, hora=18), momento(1), momento(25, mes=10))
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        grafico = respuesta.context["tablero"]["entregas"]
        por_dia = {c["fecha"]: c["valor"] for c in grafico["columnas"]}
        self.assertEqual(len(por_dia), 30)
        self.assertEqual((por_dia[date(2026, 11, 2)], por_dia[date(2026, 11, 1)], por_dia[date(2026, 10, 25)], por_dia[date(2026, 10, 30)]), (2, 1, 1, 0))
        self.assertEqual((grafico["total"], grafico["maximo"], grafico["dia_maximo"]), (4, 2, date(2026, 11, 2)))
        self.assertContains(respuesta, '<svg class="columnas"')
        self.assertContains(respuesta, "Ver los datos en una tabla")
        self.assertContains(respuesta, "4 entregas en 30 días")
        # Hay una ranura con el texto del dato por cada día, y la leyenda nombra las dos marcas.
        self.assertEqual(respuesta.content.decode().count('class="ranura"'), 30)
        self.assertContains(respuesta, "Entregas del día")
        self.assertContains(respuesta, "Promedio de 7 días")
        self.assertContains(respuesta, 'data-tip="lunes 2 de noviembre: 2 entregas · promedio de 7 días: ')

    def test_el_promedio_de_siete_dias_incluye_los_dias_anteriores_al_periodo(self):
        self.escenario()
        # Con 14 días se muestra del 20 de octubre al 2 de noviembre; el 17 de octubre queda fuera del gráfico
        # pero entra en el promedio de los siete días que terminan el 20 y el 23.
        self.entregas(self.recetas["Holgada"], *([momento(17, mes=10)] * 7))
        self.entrar()
        grafico = self.tablero(periodo=14)["entregas"]
        self.assertEqual((grafico["n"], grafico["total"]), (14, 0))
        self.assertTrue(all(c["promedio"] is not None for c in grafico["columnas"]))
        por_dia = {c["fecha"]: c["promedio"] for c in grafico["columnas"]}
        self.assertEqual((por_dia[date(2026, 10, 20)], por_dia[date(2026, 10, 23)], por_dia[date(2026, 10, 24)]), (1.0, 1.0, 0.0))

    def test_el_periodo_se_elige_por_la_url_y_un_valor_invalido_vuelve_a_treinta_dias(self):
        self.escenario()
        self.entregas(self.recetas["Holgada"], momento(2), momento(25, mes=10), momento(10, mes=9))
        self.entrar()
        self.assertEqual(self.tablero(periodo=14)["periodo"], 14)
        self.assertEqual(len(self.tablero(periodo=14)["entregas"]["columnas"]), 14)
        self.assertEqual(self.tablero(periodo=14)["entregas"]["total"], 2)
        self.assertEqual(self.tablero(periodo=90)["entregas"]["total"], 3)
        for invalido in ("999", "abc", "-7", "7", ""):
            with self.subTest(periodo=invalido):
                self.assertEqual(self.tablero(periodo=invalido)["periodo"], 30)
        respuesta = self.client.get(reverse("recetasapp:recetas"), {"periodo": 14})
        self.assertContains(respuesta, '<a href="?periodo=14#entregas" aria-current="true">14 días</a>')

    def test_con_noventa_dias_hay_una_ranura_por_dia(self):
        self.escenario()
        self.entregas(self.recetas["Holgada"], momento(2))
        self.entrar()
        html = self.client.get(reverse("recetasapp:recetas"), {"periodo": 90}).content.decode()
        self.assertEqual(html.count('class="ranura"'), 90)

    def test_sin_entregas_el_grafico_se_reemplaza_por_una_explicacion(self):
        self.escenario()
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "Todavía no hay entregas confirmadas en este periodo.")
        self.assertNotContains(respuesta, '<svg class="columnas"')

    # --- Resumen: calendario de vencimientos, ranking y carga -----------------------------------------------
    def test_el_calendario_cuenta_vigentes_por_su_ultimo_dia_valido(self):
        self.escenario()
        self.entrar()
        calor = self.tablero()["calor"]
        dias = {d["fecha"]: d["valor"] for semana in calor["semanas"] for d in semana["dias"] if d["valor"]}
        # Urgente termina el 19 nov, Pronta el 19 dic y Holgada el 31 dic; las demás no son vigentes.
        self.assertEqual(dias, {date(2026, 11, 19): 1, date(2026, 12, 19): 1, date(2026, 12, 31): 1})
        self.assertEqual(calor["total"], 3)
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "Cuándo vencen las vigentes")
        self.assertContains(respuesta, 'data-tip="jueves 19 de noviembre: 1 receta vence"')
        self.assertContains(respuesta, 'data-tip="viernes 20 de noviembre: ninguna receta vence"')
        # La tabla alternativa solo lista los días con vencimientos.
        self.assertContains(respuesta, "Ver los días con vencimientos en una tabla")
        self.assertEqual(len(calor["con_vencimientos"]), 3)

    def test_el_calendario_marca_hoy_y_deja_en_blanco_lo_anterior_a_hoy(self):
        self.escenario()
        self.entrar()
        primera = self.tablero()["calor"]["semanas"][0]
        self.assertEqual(primera["texto"], "Esta semana")
        self.assertEqual([d["es_hoy"] for d in primera["dias"]], [True] + [False] * 6)  # hoy es lunes
        html = self.client.get(reverse("recetasapp:recetas")).content.decode()
        self.assertEqual(html.count("calor-hoy"), 1)
        # Con hoy a mitad de semana, lo anterior queda sin número ni texto de ayuda.
        from recetasapp import graficos
        calor = graficos.mapa_calor({}, date(2026, 11, 4))
        self.assertEqual([d["pasado"] for d in calor["semanas"][0]["dias"]], [True, True] + [False] * 5)

    def test_el_calendario_se_reemplaza_por_una_explicacion_si_nada_vence(self):
        self.receta("Futura", date(2027, 1, 1))
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "Ninguna receta vigente vence en las próximas 12 semanas.")
        self.assertNotContains(respuesta, 'class="calor"')

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
        self.assertContains(respuesta, f'href="{reverse("recetasapp:recetas_lista")}?situacion=por_vencer">Ver las 3 por vencer</a>')

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

    def test_sin_datos_el_resumen_explica_en_vez_de_dibujar_graficos_vacios(self):
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas"))
        self.assertContains(respuesta, "Todavía no hay recetas que mostrar.")
        self.assertContains(respuesta, "Todavía no se ha cargado ningún archivo.")
        self.assertContains(respuesta, "Ninguna receta vigente vence en las próximas 12 semanas.")
        self.assertNotContains(respuesta, '<ol class="segmentos"')

    def test_el_resumen_carga_el_script_de_ayuda_y_la_lista_no(self):
        self.entrar()
        html = self.client.get(reverse("recetasapp:recetas")).content.decode()
        self.assertIn("js/graficos.js", html)
        self.assertIn("css/tablero.css", html)
        self.assertNotIn("js/graficos.js", self.client.get(reverse("recetasapp:recetas_lista")).content.decode())

    # --- Pestañas de la sección -----------------------------------------------------------------------------
    def pestanas(self, ruta):
        html = self.client.get(ruta).content.decode()
        inicio = html.index('aria-label="Secciones de Recetas"')
        bloque = html[inicio:html.index("</nav>", inicio)]
        return [(m.group(1), 'aria-current="page"' in m.group(0)) for m in re.finditer(r'<a href="([^"]+)"[^>]*>', bloque)], bloque

    def test_las_cuatro_pantallas_de_recetas_comparten_pestanas_y_marcan_la_abierta(self):
        self.escenario()
        resumen, lista = reverse("recetasapp:recetas"), reverse("recetasapp:recetas_lista")
        preparar, retiro = reverse("recetasapp:preparacion"), reverse("recetasapp:preparacion_pendientes")
        self.entrar()
        for ruta in (resumen, lista, preparar, retiro):
            with self.subTest(ruta=ruta):
                enlaces, _ = self.pestanas(ruta)
                self.assertEqual([href for href, _ in enlaces], [resumen, lista, preparar, retiro])
                self.assertEqual([href for href, actual in enlaces if actual], [ruta])

    def test_las_pestanas_traen_las_cantidades_que_ayudan_a_decidir(self):
        self.escenario()
        self.entrar()
        _, bloque = self.pestanas(reverse("recetasapp:recetas"))
        self.assertRegex(bloque, r'Todas las recetas <span class="pestana-cantidad">6</span>')
        self.assertRegex(bloque, r'Por preparar <span class="pestana-cantidad">0</span>')
        self.assertRegex(bloque, r'Pendientes de retiro <span class="pestana-cantidad">0</span>')
        self.assertNotRegex(bloque, r'Resumen <span')

    def test_el_tecnico_ve_las_cuatro_pantallas_y_el_encargado_ninguna(self):
        nombres = ("recetas", "recetas_lista", "preparacion", "preparacion_pendientes")
        self.entrar("tecnico")
        for nombre in nombres:
            self.assertEqual(self.client.get(reverse(f"recetasapp:{nombre}")).status_code, 200)
        self.entrar("encargado")
        for nombre in nombres:
            self.assertEqual(self.client.get(reverse(f"recetasapp:{nombre}")).status_code, 403)

    def test_el_resumen_ya_no_acepta_busquedas_por_post(self):
        self.entrar()
        self.assertEqual(self.client.post(reverse("recetasapp:recetas"), {"buscar": "x"}).status_code, 405)

    # --- Lista de recetas ----------------------------------------------------------------------------------
    def test_lista_filtra_por_situacion_y_cada_filtro_trae_su_cantidad(self):
        self.escenario()
        self.entrar("tecnico")
        ruta = reverse("recetasapp:recetas_lista")
        respuesta = self.client.get(ruta)
        self.assertEqual({f["clave"]: f["cantidad"] for f in respuesta.context["filtros"]},
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
        respuesta = self.client.get(reverse("recetasapp:recetas_lista"), {"situacion": "vigente"})
        self.assertContains(respuesta, "0 de 6 entregas")
        self.assertContains(respuesta, "Quedan 6")
        respuesta = self.client.get(reverse("recetasapp:recetas_lista"), {"situacion": "vencida"})
        self.assertContains(respuesta, "No admite entregas")

    def test_lista_vigente_va_con_las_que_vencen_primero_arriba(self):
        self.escenario()
        self.entrar()
        respuesta = self.client.get(reverse("recetasapp:recetas_lista"), {"situacion": "vigente"})
        self.assertEqual([r.paciente.nombres for r in respuesta.context["page_obj"]], ["Urgente", "Pronta", "Holgada"])

    def test_busqueda_por_rut_nombre_y_codigo_viaja_por_post_y_no_queda_en_la_url(self):
        self.escenario()
        self.entrar()
        ruta = reverse("recetasapp:recetas_lista")
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
        respuesta = self.client.get(reverse("recetasapp:recetas_lista"), {"situacion": "inventada"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["page_obj"].paginator.count, 0)
        self.assertContains(respuesta, 'role="alert"')

    def test_el_boton_buscar_conserva_la_situacion_y_la_paginacion_la_reenvia(self):
        self.escenario()
        self.entrar()
        ruta = reverse("recetasapp:recetas_lista")
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

    def test_los_filtros_se_explican_y_se_pueden_quitar(self):
        self.escenario()
        self.entrar()
        ruta = reverse("recetasapp:recetas_lista")
        sin_filtro = self.client.get(ruta).content.decode()
        self.assertIn("Mostrar:", sin_filtro)
        self.assertNotIn("Quitar filtros", sin_filtro)
        # Cada cantidad va en su propia insignia, separada del texto del botón.
        self.assertRegex(sin_filtro, r'Vigentes <span class="filtro-cantidad">3</span>')
        for filtrado in (self.client.get(ruta, {"situacion": "vencida"}), self.client.post(ruta, {"buscar": "Pronta", "pagina": 1, "situacion": ""})):
            self.assertContains(filtrado, f'<a class="quitar-filtros" href="{ruta}">Quitar filtros</a>')
        padron = reverse("recetasapp:pacientes")
        self.assertNotContains(self.client.get(padron), "Quitar filtros")
        self.assertContains(self.client.get(padron, {"filtro": "sin_vigente"}), f'<a class="quitar-filtros" href="{padron}">Quitar filtros</a>')

    def test_lista_vacia_sin_datos_invita_a_importar_solo_a_quien_puede(self):
        self.entrar()
        self.assertContains(self.client.get(reverse("recetasapp:recetas_lista")), "Todavía no hay recetas</h3>")
        self.assertContains(self.client.get(reverse("recetasapp:recetas_lista")), reverse("recetasapp:importacion_nueva"))
        self.entrar("tecnico")
        respuesta = self.client.get(reverse("recetasapp:recetas_lista"))
        self.assertContains(respuesta, "Pide a la Jefa de Farmacia")
        self.assertNotContains(respuesta, reverse("recetasapp:importacion_nueva"))

    def test_crear_receta_vive_en_recetas_y_ya_no_en_pacientes(self):
        self.entrar()
        nueva = reverse("recetasapp:receta_nueva")
        for nombre in ("recetas", "recetas_lista", "preparacion", "preparacion_pendientes"):
            self.assertContains(self.client.get(reverse(f"recetasapp:{nombre}")), f'href="{nueva}"')
        self.assertNotContains(self.client.get(reverse("recetasapp:pacientes")), f'href="{nueva}"')
        self.entrar("tecnico")
        self.assertNotContains(self.client.get(reverse("recetasapp:recetas")), f'href="{nueva}"')

    # --- Pacientes: lista con filtro -----------------------------------------------------------------------
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
        return {m.group(1): 'aria-current="page"' in m.group(0) for m in re.finditer(r'<a class="menu-enlace[^"]*" href="([^"]+)"[^>]*>', menu)}

    def test_el_menu_separa_padron_y_recetas_segun_el_rol_y_no_tiene_resumen(self):
        padron, recetas = reverse("recetasapp:pacientes"), reverse("recetasapp:recetas")
        for actor, esperado in (("qf", {padron, recetas}), ("admin", {padron, recetas}), ("tecnico", {padron, recetas}), ("encargado", set())):
            with self.subTest(actor=actor):
                self.entrar(actor)
                html = self.client.get(reverse("coreapp:inicio")).content.decode()
                self.assertEqual({h for h in self.enlaces(reverse("coreapp:inicio")) if h.startswith("/recetas/")}, esperado)
                self.assertNotIn(">Resumen<", html)

    def test_el_menu_lateral_se_pliega_y_el_celular_tiene_su_dock_con_hoja_mas(self):
        self.entrar()
        html = self.client.get(reverse("coreapp:inicio")).content.decode()
        # Computador: el botón de plegar controla la navegación y parte desplegado.
        self.assertIn('<button class="menu-plegar" type="button" aria-expanded="true" aria-controls="menu-principal" aria-label="Plegar el menú" data-menu-plegar>', html)
        self.assertIn('id="menu-principal" aria-label="Navegación principal"', html)
        # Celular: dock con la hoja «Más» (un <details>: abre y cierra aunque falle JavaScript).
        self.assertIn('<nav class="dock" id="dock-principal" aria-label="Navegación principal">', html)
        self.assertRegex(html, r'<details class="dock-mas[^"]*" data-mas>\s*<summary class="dock-enlace">')
        self.assertIn("css/menu.css", html)
        self.assertIn("js/menu.js", html)
        self.client.logout()
        login = self.client.get(reverse("usuariosapp:login")).content.decode()
        for ausente in ("menu-plegar", "dock-principal", "barra-superior", "app-con-menu"):
            self.assertNotIn(ausente, login)

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
            # Preparación vive dentro de Recetas: no tiene entrada propia, así que marca Recetas.
            reverse("recetasapp:preparacion"): recetas,
            reverse("recetasapp:preparacion_pendientes"): recetas,
            reverse("recetasapp:recetas_lista"): recetas,
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

    def test_inicio_ofrece_recetas_y_pacientes_a_quien_corresponde(self):
        recetas, pacientes = reverse("recetasapp:recetas"), reverse("recetasapp:pacientes")
        for actor in ("qf", "tecnico"):
            with self.subTest(actor=actor):
                self.entrar(actor)
                html = self.client.get(reverse("coreapp:inicio")).content.decode()
                self.assertIn(f'href="{recetas}">Recetas</a>', html)
                # La Jefa lo tiene en su bloque principal; el Técnico, como acceso propio.
                self.assertIn(f'href="{pacientes}">Pacientes</a>' if actor == "qf" else f'href="{pacientes}"', html)
                self.assertNotIn("Abrir resumen", html)
        self.entrar("encargado")
        html = self.client.get(reverse("coreapp:inicio")).content.decode()
        self.assertNotIn(f'href="{recetas}">Recetas</a>', html)
