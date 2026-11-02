"""Contraste WCAG, integridad de iconos y recursos locales de la PWA."""

import json
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
        recetas = (settings.BASE_DIR / "static/css/recetas.css").read_text(encoding="utf-8")
        self.assertNotRegex(recetas, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotRegex(recetas, r"\b(?:rgb|rgba|hsl|hsla)\(")
        definidas = set(re.findall(r"(--[a-z0-9-]+)\s*:", base + recetas))
        # Las plantillas inyectan estos tres valores numéricos (porcentaje, posición de «hoy» y cantidad de la barra).
        inyectadas = {"--p", "--hoy", "--n"}
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
            ("exito-texto", "panel-fondo"), ("error-texto", "panel-fondo"),  # tramos de la barra de carga
        ]
        for primero, segundo in pares:
            with self.subTest(primero=primero, segundo=segundo):
                self.assertGreaterEqual(contraste(variables[primero], variables[segundo]), 3)

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
