"""Menú principal: qué ve cada perfil y cómo se reparte entre la columna lateral y la barra del celular."""

import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from coreapp.context_processors import menu_principal
from coreapp.navegacion import ENTRADAS, MAXIMO_EN_BARRA, PERFIL, armar_menu
from coreapp.roles import ENCARGADO, JEFA, SUPERUSUARIO, TECNICO
from usuariosapp.tests.test_gestion_usuarios import cuenta_personal

VISIBLES = {
    JEFA: ["Inicio de farmacia", "Turnos", "Pantalla de sala", "Recetas", "Padrón", "Usuarios"],
    TECNICO: ["Atención en ventanilla", "Turnos", "Pantalla de sala", "Recetas", "Padrón"],
    ENCARGADO: ["Entregas en terreno"],
    SUPERUSUARIO: ["Inicio", "Turnos", "Pantalla de sala", "Recetas", "Padrón", "Usuarios", "Administración"],
    "": ["Inicio"],
}


def etiquetas(menu):
    return [opcion.etiqueta for grupo in menu.grupos for opcion in grupo.opciones]


class MenuPorPerfilTests(TestCase):
    def test_cada_perfil_ve_solo_lo_suyo_y_en_el_mismo_orden(self):
        for rol, esperado in VISIBLES.items():
            with self.subTest(rol=rol or "sin perfil"):
                self.assertEqual(etiquetas(armar_menu(rol)), esperado)

    def test_los_grupos_tienen_titulo_y_el_inicio_va_suelto(self):
        menu = armar_menu(JEFA)
        self.assertEqual([grupo.titulo for grupo in menu.grupos], ["", "Atención", "Pacientes y recetas", "Equipo"])
        self.assertEqual([len(grupo.opciones) for grupo in menu.grupos], [1, 2, 2, 1])
        self.assertEqual([grupo.titulo for grupo in armar_menu(ENCARGADO).grupos], [""])

    def test_una_cuenta_sin_perfil_solo_ve_el_inicio_y_no_tiene_mi_perfil(self):
        menu = armar_menu("")
        self.assertEqual(etiquetas(menu), ["Inicio"])
        self.assertIsNone(menu.perfil)
        for rol in (JEFA, TECNICO, ENCARGADO, SUPERUSUARIO):
            self.assertEqual(armar_menu(rol).perfil.etiqueta, "Mi perfil")

    def test_la_barra_del_celular_lleva_el_trabajo_y_el_resto_va_en_mas_sin_perder_nada(self):
        esperado = {
            JEFA: (["inicio", "turnos", "recetas", "padron"], ["sala", "usuarios"]),
            TECNICO: (["inicio", "turnos", "recetas", "padron"], ["sala"]),
            ENCARGADO: (["inicio"], []),
            SUPERUSUARIO: (["inicio", "turnos", "recetas", "padron"], ["sala", "usuarios", "administracion"]),
        }
        for rol, (barra, mas) in esperado.items():
            with self.subTest(rol=rol):
                menu = armar_menu(rol)
                self.assertEqual([o.clave for o in menu.barra], barra)
                self.assertEqual([o.clave for o in menu.mas], mas)
                todas = [o.clave for grupo in menu.grupos for o in grupo.opciones]
                self.assertCountEqual(todas, barra + mas)
                self.assertLessEqual(len(menu.barra), MAXIMO_EN_BARRA)

    def test_la_pagina_actual_se_marca_en_una_sola_entrada(self):
        casos = (
            (("coreapp", "inicio"), "inicio"), (("turnosapp", "panel"), "turnos"), (("turnosapp", "gestion"), "turnos"),
            (("turnosapp", "historial"), "turnos"), (("recetasapp", "recetas"), "recetas"),
            (("recetasapp", "receta_detalle"), "recetas"), (("recetasapp", "entrega_confirmar"), "recetas"),
            # Preparación vive dentro de Recetas: no tiene entrada propia.
            (("recetasapp", "preparacion"), "recetas"), (("recetasapp", "preparacion_pendientes"), "recetas"),
            (("recetasapp", "pacientes"), "padron"), (("recetasapp", "paciente_detalle"), "padron"),
            (("recetasapp", "importacion_nueva"), "padron"), (("recetasapp", "plantilla"), "padron"),
            (("usuariosapp", "gestion_editar"), "usuarios"),
        )
        for (app, nombre), clave in casos:
            with self.subTest(pagina=f"{app}:{nombre}"):
                menu = armar_menu(SUPERUSUARIO, app, nombre)
                marcadas = [o.clave for g in menu.grupos for o in g.opciones if o.activa]
                self.assertEqual(marcadas, [clave])
                self.assertFalse(menu.perfil.activa)

    def test_perfil_y_pantallas_sin_entrada_no_marcan_ninguna_opcion_del_menu(self):
        for app, nombre in (("usuariosapp", "perfil"), ("usuariosapp", "cambiar_clave")):
            with self.subTest(nombre=nombre):
                menu = armar_menu(JEFA, app, nombre)
                self.assertTrue(menu.perfil.activa)
                self.assertFalse([o for g in menu.grupos for o in g.opciones if o.activa])
        self.assertFalse([o for g in armar_menu(JEFA, "", "").grupos for o in g.opciones if o.activa])

    def test_mas_se_marca_cuando_la_pagina_actual_esta_dentro_de_la_hoja(self):
        self.assertTrue(armar_menu(JEFA, "usuariosapp", "gestion_usuarios").mas_activa)
        self.assertTrue(armar_menu(JEFA, "usuariosapp", "perfil").mas_activa)
        self.assertFalse(armar_menu(JEFA, "turnosapp", "panel").mas_activa)
        self.assertFalse(armar_menu(JEFA, "coreapp", "inicio").mas_activa)

    def test_la_pantalla_de_sala_abre_otra_pestana_y_las_demas_no(self):
        menu = armar_menu(TECNICO)
        for opcion in (o for g in menu.grupos for o in g.opciones):
            self.assertEqual(opcion.otra_pestana, opcion.clave == "sala")


class EntradasTests(SimpleTestCase):
    def test_cada_entrada_tiene_destino_existente_e_icono_en_el_sprite(self):
        sprite = (settings.BASE_DIR / "templates/components/iconos.html").read_text(encoding="utf-8")
        simbolos = set(re.findall(r'<symbol id="([^"]+)"', sprite))
        for entrada in (*ENTRADAS, PERFIL):
            with self.subTest(clave=entrada.clave):
                self.assertTrue(reverse(entrada.destino))
                self.assertIn(entrada.icono, simbolos)
        for necesario in ("i-puntos", "i-chevron", "i-externo", "i-salir"):
            self.assertIn(necesario, simbolos)

    def test_los_iconos_distinguen_cada_destino(self):
        iconos = [entrada.icono for entrada in (*ENTRADAS, PERFIL)]
        self.assertEqual(len(iconos), len(set(iconos)), "Dos destinos comparten ícono.")

    def test_los_destinos_de_la_barra_inferior_caben_en_un_boton_de_un_quinto_de_pantalla(self):
        """Con cinco botones en 320 px cada texto mide como mucho 8 letras; las entradas nuevas deben respetarlo."""
        for entrada in ENTRADAS:
            if entrada.en_barra:
                with self.subTest(clave=entrada.clave):
                    self.assertLessEqual(len(entrada.corta or entrada.etiqueta), 8)

    def test_claves_unicas_y_las_etiquetas_largas_tienen_nombre_corto_para_la_columna_plegada(self):
        claves = [entrada.clave for entrada in ENTRADAS]
        self.assertEqual(len(claves), len(set(claves)))
        for entrada in (*ENTRADAS, PERFIL):
            with self.subTest(clave=entrada.clave):
                if len(entrada.etiqueta) > 10:
                    self.assertTrue(entrada.corta, "La columna plegada no admite etiquetas largas.")
                if entrada.corta:
                    self.assertLessEqual(len(entrada.corta), 8)


class ContextoMenuTests(TestCase):
    def contexto(self, usuario):
        peticion = RequestFactory().get("/")
        peticion.user = usuario
        return menu_principal(peticion)["menu_principal"]

    def test_anonimo_no_tiene_menu(self):
        self.assertIsNone(self.contexto(AnonymousUser()))

    def test_persona_con_nombre_muestra_nombre_iniciales_y_perfil(self):
        usuario = cuenta_personal("menu_tecnico_sintetico", TECNICO)
        persona = self.contexto(usuario).persona
        self.assertEqual((persona.nombre, persona.iniciales, persona.rol), ("Persona Sintética", "PS", "Técnico en Farmacia"))

    def test_persona_sin_nombre_usa_la_primera_letra_del_usuario(self):
        usuario = get_user_model().objects.create_superuser(username="root_menu_sintetico")
        persona = self.contexto(usuario).persona
        self.assertEqual((persona.nombre, persona.iniciales, persona.rol), ("root_menu_sintetico", "r", "Administración"))

    def test_la_pagina_actual_sale_de_la_ruta_resuelta(self):
        usuario = cuenta_personal("menu_qf_sintetico", JEFA)
        cliente = Client()
        cliente.force_login(usuario)
        for ruta, clave in (("/", "inicio"), (reverse("recetasapp:preparacion"), "recetas"),
                            (reverse("usuariosapp:gestion_usuarios"), "usuarios")):
            with self.subTest(ruta=ruta):
                menu = cliente.get(ruta).context["menu_principal"]
                self.assertEqual([o.clave for g in menu.grupos for o in g.opciones if o.activa], [clave])


class MenuRenderizadoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuarios = {
            JEFA: cuenta_personal("render_qf_sintetico", JEFA),
            TECNICO: cuenta_personal("render_tecnico_sintetico", TECNICO),
            ENCARGADO: cuenta_personal("render_terreno_sintetico", ENCARGADO),
            SUPERUSUARIO: get_user_model().objects.create_superuser(username="render_root_sintetico"),
        }

    def pagina(self, rol, ruta="/"):
        cliente = Client()
        cliente.force_login(self.usuarios[rol])
        return cliente.get(ruta).content.decode()

    @staticmethod
    def partes(html):
        menu = html[html.index('<div class="menu"'):html.index('<div class="app-columna">')]
        dock = html[html.index('<nav class="dock"'):html.index("</nav>", html.index('<nav class="dock"'))]
        return menu, dock

    def test_cada_perfil_recibe_los_mismos_destinos_en_el_menu_lateral_y_en_el_dock(self):
        for rol in self.usuarios:
            with self.subTest(rol=rol):
                menu, dock = self.partes(self.pagina(rol))
                lateral = re.findall(r'<a class="menu-enlace[^"]*" href="([^"]+)"', menu)
                celular = re.findall(r'<a class="(?:dock|menu)-enlace[^"]*" href="([^"]+)"', dock)
                self.assertCountEqual(set(lateral), set(celular))

    def test_el_encargado_no_recibe_enlaces_a_secciones_ajenas(self):
        menu, dock = self.partes(self.pagina(ENCARGADO))
        for ajeno in ("/turnos/", "/recetas/", "/usuarios/gestion/", "/admin/"):
            self.assertNotIn(f'href="{ajeno}', menu + dock)
        self.assertIn('href="/usuarios/perfil/"', menu)

    def test_una_sola_entrada_marcada_como_pagina_actual_en_cada_navegacion(self):
        for rol, ruta in ((JEFA, "/"), (JEFA, reverse("recetasapp:preparacion")), (TECNICO, reverse("turnosapp:panel")),
                          (SUPERUSUARIO, reverse("usuariosapp:gestion_usuarios"))):
            with self.subTest(rol=rol, ruta=ruta):
                menu, dock = self.partes(self.pagina(rol, ruta))
                self.assertEqual(menu.count('aria-current="page"'), 1)
                self.assertLessEqual(dock.count('aria-current="page"'), 1)

    def test_la_hoja_mas_incluye_la_cuenta_y_avisa_si_contiene_la_pagina_actual(self):
        _, dock = self.partes(self.pagina(JEFA))
        for texto in ("Pantalla de sala", "Usuarios", "Mi perfil", "Cerrar sesión", "Persona Sintética"):
            self.assertIn(texto, dock)
        self.assertNotIn("incluye la página actual", dock)
        _, dock = self.partes(self.pagina(JEFA, reverse("usuariosapp:gestion_usuarios")))
        self.assertIn("(incluye la página actual)", dock)
        self.assertIn("dock-mas-activa", dock)

    def test_la_pantalla_de_sala_avisa_que_abre_otra_pestana(self):
        menu, dock = self.partes(self.pagina(TECNICO))
        for parte in (menu, dock):
            enlace = re.search(r'<a class="menu-enlace[^"]*" href="/turnos/sala/"[^>]*>.*?</a>', parte, re.S).group(0)
            self.assertIn('target="_blank" rel="noopener"', enlace)
            self.assertIn("(abre en otra pestaña)", enlace)

    def test_la_columna_plegable_conserva_el_nombre_completo_para_lectores_de_pantalla(self):
        menu, _ = self.partes(self.pagina(SUPERUSUARIO))
        # Plegada solo se ve el nombre corto (aria-hidden); el nombre completo sigue en el árbol de accesibilidad.
        self.assertRegex(menu, r'<span class="menu-texto">Administración</span><span class="menu-corta" aria-hidden="true">Admin\.</span>')
        self.assertRegex(menu, r'<span class="menu-texto">Cerrar sesión</span><span class="menu-corta" aria-hidden="true">Salir</span>')

    def test_las_pantallas_publicas_conservan_la_franja_y_no_traen_menu(self):
        html = Client().get(reverse("usuariosapp:login")).content.decode()
        self.assertEqual(html.count('class="franja"'), 1)
        for ausente in ('class="menu"', 'class="dock"', "barra-superior", "app-con-menu"):
            self.assertNotIn(ausente, html)

    def test_con_menu_la_franja_va_dentro_de_la_columna_y_no_se_repite(self):
        html = self.pagina(JEFA)
        self.assertEqual(html.count('class="franja"'), 1)
        self.assertGreater(html.index('class="franja"'), html.index('<div class="app-columna">'))
