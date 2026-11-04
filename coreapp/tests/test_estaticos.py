"""Contraste WCAG, integridad de iconos y recursos locales de la PWA."""

import json
import os
import re
import struct
import zlib

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase


def luminancia(color):
    canales = [int(color[indice:indice + 2], 16) / 255 for indice in (1, 3, 5)]
    lineales = [canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4 for canal in canales]
    return sum(canal * peso for canal, peso in zip(lineales, (0.2126, 0.7152, 0.0722)))


def contraste(color_a, color_b):
    claro, oscuro = sorted((luminancia(color_a), luminancia(color_b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


class EstaticosTests(SimpleTestCase):
    def test_sala_usa_paleta_con_contraste_y_recursos_locales(self):
        base = (settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8")
        sala = (settings.BASE_DIR / "static/css/sala.css").read_text(encoding="utf-8")
        variables = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", base))
        self.assertNotRegex(sala, r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(")
        definidas = set(re.findall(r"(--[a-z0-9-]+)\s*:", base))
        self.assertFalse(set(re.findall(r"var\((--[a-z0-9-]+)", sala)) - definidas)
        for texto, fondo in (("panel-texto", "panel-fondo"), ("suave-texto", "suave-fondo"),
            ("trigo-texto", "trigo-fondo"), ("secundario-texto", "panel-fondo"),
            ("accion-texto", "accion-fondo"), ("hover-texto", "hover-fondo")):
            with self.subTest(texto=texto, fondo=fondo):
                self.assertGreaterEqual(contraste(variables[texto], variables[fondo]), 4.5)
        for fondo in ("panel-fondo", "suave-fondo", "trigo-fondo"):
            self.assertGreaterEqual(contraste(variables["borde"], variables[fondo]), 3)
            self.assertGreaterEqual(contraste(variables["tinta"], variables[fondo]), 3)
        plantilla = (settings.BASE_DIR / "templates/turnos/sala.html").read_text(encoding="utf-8")
        for recurso in ("css/sala.css", "js/sala.js"):
            self.assertTrue(finders.find(recurso))
            self.assertIn(recurso, plantilla)

    def test_sala_respeta_movimiento_reducido_foco_zoom_y_elementos_ocultos(self):
        sala = (settings.BASE_DIR / "static/css/sala.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", sala)
        self.assertIn("animation: none !important", sala)
        self.assertNotIn("@keyframes", sala)
        self.assertIn(".boton:focus-visible", sala)
        self.assertIn("outline: 3px solid", sala)
        self.assertIn("[hidden] { display: none !important; }", sala)
        self.assertIn("font-size: clamp(5rem", sala)
        self.assertNotRegex(sala, r"(?:font-size|height|min-height|max-height):\s*\d+px")
        self.assertIn("max-width: 30rem", sala)

    def test_todas_las_parejas_de_color_cumplen_contraste_aa(self):
        css = (settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8")
        variables = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", css))
        textos = {nombre.removesuffix("-texto") for nombre in variables if nombre.endswith("-texto")}
        fondos = {nombre.removesuffix("-fondo") for nombre in variables if nombre.endswith("-fondo")}
        self.assertTrue(textos)
        self.assertEqual(textos, fondos, "Cada color de texto debe declarar su fondo.")
        pares = [(variables[nombre + "-texto"], variables[nombre + "-fondo"]) for nombre in textos]
        # Enlaces y texto secundario también aparecen sobre los fondos de acento (portada, azulejos, paneles).
        pares += [(variables["enlace-texto"], variables["pagina-fondo"]),
                  (variables["panel-texto"], variables["panel-fondo"])]
        pares += [(variables[texto], variables[fondo]) for texto in ("enlace-texto", "secundario-texto")
                  for fondo in ("trigo-fondo", "suave-fondo")]
        pares.append((variables["enlace-texto"], variables["arena-fondo"]))
        for texto, fondo in pares:
            with self.subTest(texto=texto, fondo=fondo):
                self.assertGreaterEqual(contraste(texto, fondo), 4.5)

    def test_bordes_de_campos_cumplen_contraste_de_componentes_de_interfaz(self):
        """WCAG 1.4.11: el borde que delimita un campo debe distinguirse con al menos 3:1."""
        css = (settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8")
        variables = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", css))
        self.assertGreaterEqual(contraste(variables["borde"], variables["panel-fondo"]), 3)
        # El botón principal es naranja sobre blanco (2,5:1): su borde de tinta es lo que lo delimita.
        self.assertGreaterEqual(contraste(variables["tinta"], variables["panel-fondo"]), 3)

    def test_libreta_del_padron_usa_solo_colores_de_la_paleta_y_variables_definidas(self):
        """recetas.css no declara colores propios: todo sale de base.css, donde se verifica el contraste."""
        base = (settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8")
        # El tablero (tablero.css) y el menú (menu.css) siguen la misma regla que la libreta.
        for nombre in ("recetas.css", "tablero.css", "menu.css", "noticias.css"):
            with self.subTest(hoja=nombre):
                recetas = (settings.BASE_DIR / "static/css" / nombre).read_text(encoding="utf-8")
                self.assertNotRegex(recetas, r"#[0-9a-fA-F]{3,8}\b")
                self.assertNotRegex(recetas, r"\b(?:rgb|rgba|hsl|hsla)\(")
                definidas = set(re.findall(r"(--[a-z0-9-]+)\s*:", base + recetas))
                # Las plantillas inyectan valores numéricos: porcentaje, posición de «hoy», cantidad de la barra,
                # altura de una barra del tablero y orden de aparición de un arco del anillo o de una barra.
                inyectadas = {"--p", "--hoy", "--n", "--h", "--i"}
                usadas = set(re.findall(r"var\((--[a-z0-9-]+)", recetas))
                self.assertEqual(usadas - definidas - inyectadas, set())

    def test_graficos_de_la_libreta_cumplen_contraste_de_componentes(self):
        """WCAG 1.4.11: sellos, casillas y barras se distinguen del fondo con al menos 3:1."""
        css = (settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8")
        variables = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", css))
        pares = [
            ("ladrillo", "trigo-fondo"), ("ladrillo", "suave-fondo"), ("ladrillo", "panel-fondo"),  # sello, aro y lomo
            ("borde", "suave-fondo"), ("borde", "panel-fondo"),  # casilla vacía y punto sin sellar
            ("tinta", "trigo-fondo"),  # próxima casilla
            ("exito-texto", "panel-fondo"), ("error-texto", "panel-fondo"),  # tramos de la barra de carga y del anillo
            ("tinta", "naranja"),  # el arco naranja del anillo y la barra del mes actual van delimitados por tinta
        ]
        for primero, segundo in pares:
            with self.subTest(primero=primero, segundo=segundo):
                self.assertGreaterEqual(contraste(variables[primero], variables[segundo]), 3)

    def test_menu_cumple_contraste_de_texto_y_de_componentes(self):
        """La píldora de la opción activa, la cápsula del celular y sus bordes se distinguen con al menos 3:1;
        el texto de cada combinación del menú, con al menos 4,5:1 (WCAG 1.4.3 y 1.4.11)."""
        css = (settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8")
        variables = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", css))
        componentes = [
            ("marca-fondo", "panel-fondo"), ("marca-fondo", "suave-fondo"),  # píldora activa sobre la tarjeta y la cápsula
            ("activo-fondo", "panel-fondo"), ("activo-fondo", "suave-fondo"),  # botón «Más» abierto y opción activa con el cursor
            ("borde", "panel-fondo"),  # cápsula y hoja del celular, y botón de plegar, sobre la página
            ("enlace-texto", "panel-fondo"), ("enlace-texto", "suave-fondo"), ("enlace-texto", "trigo-fondo"),  # íconos
        ]
        for primero, segundo in componentes:
            with self.subTest(primero=primero, segundo=segundo):
                self.assertGreaterEqual(contraste(variables[primero], variables[segundo]), 3)
        textos = [
            ("panel-texto", "panel-fondo"), ("suave-texto", "suave-fondo"), ("secundario-texto", "panel-fondo"),
            ("secundario-texto", "suave-fondo"), ("marca-texto", "marca-fondo"), ("activo-texto", "activo-fondo"),
            ("trigo-texto", "trigo-fondo"), ("arena-texto", "arena-fondo"),
        ]
        for texto, fondo in textos:
            with self.subTest(texto=texto, fondo=fondo):
                self.assertGreaterEqual(contraste(variables[texto], variables[fondo]), 4.5)

    def test_menu_respeta_foco_movimiento_reducido_impresion_y_tamano_de_texto(self):
        menu = (settings.BASE_DIR / "static/css/menu.css").read_text(encoding="utf-8")
        # Sin px en tamaños ni alturas (salvo el 1 px del texto solo para lectores de pantalla): todo escala
        # con el control de tamaño de texto.
        self.assertNotRegex(menu, r"(?:font-size|height|min-height|max-height|width|min-width):\s*(?!1px(?![0-9a-z]))\d+px")
        # El corte entre computador y celular es el mismo que usa menu.js.
        self.assertIn("(min-width: 70.0625rem)", menu)
        self.assertIn("(max-width: 70rem)", menu)
        self.assertIn("@media print", menu)
        self.assertIn("forced-colors: active", menu)
        # La barra inferior deja al lado del indicador de inicio de iOS el espacio que le corresponde.
        self.assertIn("env(safe-area-inset-bottom", menu)
        # El texto de la barra inferior se ajusta a cada nivel del control de tamaño de texto.
        for nivel in ("grande", "muy-grande"):
            self.assertIn(f'html[data-texto="{nivel}"] .dock-texto', menu)
        # Las animaciones nuevas solo declaran su estado de partida; con «reducir movimiento» base.css las apaga.
        linea = next(linea for linea in menu.splitlines() if linea.startswith("@keyframes subir-hoja "))
        self.assertRegex(linea, r"\{ from \{[^}]*\} \}")
        self.assertNotRegex(linea, r"\bto\b|100%")
        self.assertRegex((settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8"),
                         r"prefers-reduced-motion: reduce\)\s*\{[^}]*animation: none !important[^}]*transition: none !important")

    def test_recursos_del_padron_existen_y_estan_enlazados(self):
        base = (settings.BASE_DIR / "templates/recetas/base.html").read_text(encoding="utf-8")
        self.assertIn("css/recetas.css", base)
        self.assertTrue(finders.find("css/recetas.css"))
        enlazados = {
            "js/receta_previa.js": "templates/recetas/receta_form.html",
            "js/importacion.js": "templates/recetas/importacion_form.html",
        }
        for recurso, plantilla in enlazados.items():
            with self.subTest(recurso=recurso):
                self.assertTrue(finders.find(recurso))
                self.assertIn(recurso, (settings.BASE_DIR / plantilla).read_text(encoding="utf-8"))

    def test_urls_de_css_y_js_llevan_su_version_y_el_resto_no(self):
        """Cambiar un .css o .js cambia su URL, así el navegador no sigue usando una hoja vieja."""
        from django.templatetags.static import static

        for recurso in ("css/base.css", "css/menu.css", "css/recetas.css", "css/tablero.css", "js/menu.js"):
            with self.subTest(recurso=recurso):
                self.assertRegex(static(recurso), rf"^/static/{re.escape(recurso)}\?v=\d+$")
        # Las fuentes y los iconos conservan su URL: el CSS las pide sin versión y una URL distinta las descargaría dos veces.
        self.assertEqual(static("fonts/bitter-latin-wght-normal.woff2"), "/static/fonts/bitter-latin-wght-normal.woff2")
        self.assertEqual(static("icons/marca.svg"), "/static/icons/marca.svg")
        # Un archivo inexistente no rompe la página: se entrega sin versión.
        self.assertEqual(static("css/no-existe.css"), "/static/css/no-existe.css")

    def test_la_version_cambia_cuando_cambia_el_archivo(self):
        from django.templatetags.static import static

        ruta = finders.find("css/tablero.css")
        antes = static("css/tablero.css")
        original = os.stat(ruta).st_mtime
        try:
            os.utime(ruta, (original + 100, original + 100))
            self.assertNotEqual(static("css/tablero.css"), antes)
        finally:
            os.utime(ruta, (original, original))
        self.assertEqual(static("css/tablero.css"), antes)

    def test_tablero_y_menu_plegable_existen_y_estan_enlazados(self):
        pagina = (settings.BASE_DIR / "templates/recetas/recetas_lista.html").read_text(encoding="utf-8")
        layout = (settings.BASE_DIR / "templates/components/Layout/base.html").read_text(encoding="utf-8")
        self.assertIn("css/tablero.css", pagina)
        self.assertIn("js/menu.js", layout)
        self.assertIn("css/menu.css", layout)
        for recurso in ("css/tablero.css", "css/menu.css", "js/menu.js"):
            with self.subTest(recurso=recurso):
                self.assertTrue(finders.find(recurso))

    def test_animaciones_del_tablero_parten_de_su_estado_final_y_se_apagan_con_reducir_movimiento(self):
        """Sin animación el tablero debe verse completo: estas animaciones solo declaran el estado de partida («from»)."""
        css = (settings.BASE_DIR / "static/css/tablero.css").read_text(encoding="utf-8")
        for nombre in ("trazar", "dibujar", "velo", "subir"):
            with self.subTest(animacion=nombre):
                linea = next(linea for linea in css.splitlines() if linea.startswith(f"@keyframes {nombre} "))
                self.assertRegex(linea, r"\{ from \{[^}]*\} \}")
                self.assertNotRegex(linea, r"\bto\b|100%")
        base = (settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8")
        self.assertRegex(base, r"prefers-reduced-motion: reduce\)\s*\{[^}]*animation: none !important")

    def test_fuentes_locales_woff2_con_licencia_y_referenciadas_por_el_css(self):
        css = (settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8")
        carpeta = settings.BASE_DIR / "static/fonts"
        archivos = re.findall(r'url\("\.\./fonts/([^"]+\.woff2)"\)', css)
        self.assertEqual(len(archivos), 2)
        for nombre in archivos:
            with self.subTest(fuente=nombre):
                self.assertEqual((carpeta / nombre).read_bytes()[:4], b"wOF2")
        licencia = (carpeta / "LICENSE.md").read_text(encoding="utf-8")
        self.assertIn("SIL OPEN FONT LICENSE", licencia)
        for fuente in ("Bitter", "Atkinson Hyperlegible Next"):
            self.assertIn(fuente, licencia)

    def test_manifest_e_iconos_reales_de_los_tamanos_declarados(self):
        manifest = json.loads((settings.BASE_DIR / "static/manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual({icono["sizes"] for icono in manifest["icons"]}, {"192x192", "512x512"})
        for icono in manifest["icons"]:
            with self.subTest(icono=icono):
                ruta = icono["src"].removeprefix("/static/")
                self.assertTrue(finders.find(ruta))
                datos = (settings.BASE_DIR / "static" / ruta).read_bytes()
                self.assertEqual(datos[:8], b"\x89PNG\r\n\x1a\n")
                ancho, alto = struct.unpack(">II", datos[16:24])
                self.assertEqual(f"{ancho}x{alto}", icono["sizes"])
                posicion = 8
                pixeles_comprimidos = b""
                while posicion < len(datos):
                    largo = struct.unpack(">I", datos[posicion:posicion + 4])[0]
                    tipo = datos[posicion + 4:posicion + 8]
                    contenido = datos[posicion + 8:posicion + 8 + largo]
                    crc = struct.unpack(">I", datos[posicion + 8 + largo:posicion + 12 + largo])[0]
                    self.assertEqual(zlib.crc32(tipo + contenido) & 0xffffffff, crc)
                    if tipo == b"IDAT":
                        pixeles_comprimidos += contenido
                    posicion += largo + 12
                self.assertEqual(len(zlib.decompress(pixeles_comprimidos)), alto * (ancho * 3 + 1))

    def test_alpine_fijo_local_y_con_licencia(self):
        alpine = (settings.BASE_DIR / "static/js/alpine.min.js").read_text(encoding="utf-8")
        self.assertIn('"3.14.9"', alpine)
        self.assertGreater(len(alpine), 10000)
        self.assertIn("MIT License", (settings.BASE_DIR / "static/js/alpine.LICENSE.md").read_text(encoding="utf-8"))

    def test_service_worker_sin_cache_de_datos(self):
        worker = (settings.BASE_DIR / "templates/pwa/sw.js").read_text(encoding="utf-8")
        self.assertNotIn("caches.", worker)
        self.assertNotRegex(worker, r'addEventListener\([\s]*[\'"]fetch')

    def test_html_sin_dependencias_en_cdn(self):
        for archivo in (settings.BASE_DIR / "templates").rglob("*.html"):
            with self.subTest(archivo=archivo.name):
                self.assertNotRegex(archivo.read_text(encoding="utf-8"), r'(?:src|href)=[\'"]https?://')
