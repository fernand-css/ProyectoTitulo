"""Búsqueda instantánea de las listas con buscador (coreapp/busqueda.py y static/js/busqueda_en_vivo.js).

Con la cabecera `X-Busqueda-En-Vivo: 1`, el POST de cada buscador responde solo las zonas de la página; sin ella,
la página completa, como siempre. Ambos caminos dibujan las zonas con las mismas plantillas y el mismo contexto.
Datos sintéticos de entregasapp.tests.ayudas.
"""

from html.parser import HTMLParser

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from coreapp.busqueda import CABECERA, PLANTILLA, es_en_vivo, plantilla_y_contexto
from entregasapp.tests.ayudas import equipo, paciente, receta

EN_VIVO = {"HTTP_X_BUSQUEDA_EN_VIVO": "1"}
VACIOS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Zonas(HTMLParser):
    """Texto visible de cada elemento [data-zona], para comparar la página completa con el fragmento."""

    def __init__(self):
        super().__init__()
        self.zonas, self.abiertas = {}, []

    def handle_starttag(self, etiqueta, atributos):
        if etiqueta in VACIOS:
            return
        for zona in self.abiertas:
            zona[1] += 1
        nombre = dict(atributos).get("data-zona")
        if nombre is not None:
            self.zonas[nombre] = []
            self.abiertas.append([nombre, 1])

    def handle_endtag(self, etiqueta):
        if etiqueta in VACIOS:
            return
        for zona in self.abiertas:
            zona[1] -= 1
        self.abiertas = [zona for zona in self.abiertas if zona[1] > 0]

    def handle_data(self, datos):
        for nombre, _profundidad in self.abiertas:
            self.zonas[nombre].append(datos)


def zonas(html):
    lector = _Zonas()
    lector.feed(html)
    return {nombre: " ".join("".join(partes).split()) for nombre, partes in lector.zonas.items()}


class DeteccionTests(SimpleTestCase):
    def test_solo_un_post_con_la_cabecera_pide_el_fragmento(self):
        fabrica = RequestFactory()
        self.assertTrue(es_en_vivo(fabrica.post("/", **EN_VIVO)))
        self.assertFalse(es_en_vivo(fabrica.post("/")))
        self.assertFalse(es_en_vivo(fabrica.get("/", **EN_VIVO)), "un GET siempre recibe la página")
        self.assertFalse(es_en_vivo(fabrica.post("/", HTTP_X_BUSQUEDA_EN_VIVO="0")))
        self.assertEqual(CABECERA, "X-Busqueda-En-Vivo")

    def test_sin_zonas_responde_la_pagina_completa(self):
        solicitud = RequestFactory().post("/", **EN_VIVO)
        self.assertEqual(plantilla_y_contexto(solicitud, "x.html", {"a": 1}, []), ("x.html", {"a": 1}))
        self.assertEqual(plantilla_y_contexto(solicitud, "x.html", {"a": 1}, ["z.html"]),
                         (PLANTILLA, {"a": 1, "zonas": ["z.html"]}))


class BuscadoresEnVivoTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.client.force_login(self.equipo["qf"])
        self.buscada = paciente(edad=86)
        receta(self.buscada, "VIVO-0001")
        self.otra = paciente(edad=90)
        receta(self.otra, "VIVO-0002")

    def comparar(self, url, datos, nombres):
        """La página completa y el fragmento muestran lo mismo en cada zona; el fragmento no trae nada más."""
        pagina = self.client.post(url, datos)
        fragmento = self.client.post(url, datos, **EN_VIVO)
        for respuesta in (pagina, fragmento):
            self.assertEqual(respuesta.status_code, 200)
            self.assertIn("no-store", respuesta["Cache-Control"])
            self.assertEqual(respuesta["Referrer-Policy"], "same-origin")
        html_pagina, html_fragmento = pagina.content.decode(), fragmento.content.decode()
        self.assertIn('data-en-vivo="busqueda"', html_pagina)
        self.assertIn("js/busqueda_en_vivo.js", html_pagina)
        self.assertNotIn("se actualiza mientras escribes", html_pagina, "sin ayuda sobre la búsqueda en vivo")
        self.assertTemplateUsed(fragmento, PLANTILLA)
        self.assertNotIn("<html", html_fragmento)
        self.assertNotIn('data-en-vivo="busqueda"', html_fragmento, "el campo donde se escribe no se reemplaza")
        self.assertEqual(set(zonas(html_fragmento)), set(nombres))
        self.assertEqual({n: t for n, t in zonas(html_pagina).items() if n in nombres}, zonas(html_fragmento))
        return html_fragmento

    def test_pacientes(self):
        url = reverse("recetasapp:pacientes")
        html = self.comparar(url, {"buscar": self.buscada.rut, "filtro": ""}, ["filtros", "resultados"])
        self.assertIn(self.buscada.apellidos, html)
        self.assertNotIn(self.otra.apellidos, html)
        self.assertRegex(html, r'<p class="padron-resumen" data-anuncio>\s*<strong>1</strong> paciente coincide')
        filtrada = self.comparar(url, {"buscar": "", "filtro": "sin_vigente"}, ["filtros", "resultados"])
        self.assertIn('value="sin_vigente" aria-pressed="true"', filtrada)
        self.assertIn('class="quitar-filtros"', filtrada)
        vacia = self.comparar(url, {"buscar": "zzzz", "filtro": ""}, ["filtros", "resultados"])
        self.assertIn("<h2 data-anuncio>No encontramos pacientes con «zzzz»</h2>", vacia)

    def test_pacientes_paginacion_por_post_marcada_para_la_busqueda_en_vivo(self):
        for _ in range(20):
            paciente(edad=81)
        url = reverse("recetasapp:pacientes")
        pagina = self.client.get(url).content.decode()
        self.assertEqual(pagina.count('<form method="post" data-en-vivo="pagina">'), 1)
        segunda = self.comparar(url, {"buscar": "", "filtro": "", "pagina": 2}, ["filtros", "resultados"])
        self.assertIn("Página 2 de 2", segunda)
        self.assertIn('<form method="post" data-en-vivo="pagina">', segunda)
        self.assertNotIn(self.buscada.rut, self.client.post(url, {"buscar": self.buscada.rut}, **EN_VIVO)
                         .wsgi_request.get_full_path())

    def test_recetas(self):
        url = reverse("recetasapp:recetas_lista")
        html = self.comparar(url, {"buscar": "VIVO-0001", "situacion": ""}, ["filtros", "resultados"])
        self.assertIn("Receta VIVO-0001", html)
        self.assertNotIn("Receta VIVO-0002", html)
        self.assertIn("data-anuncio", html)
        vigentes = self.comparar(url, {"buscar": "", "situacion": "vigente"}, ["filtros", "resultados"])
        self.assertIn('value="vigente" aria-pressed="true"', vigentes)

    def test_pendientes_de_retiro(self):
        url = reverse("recetasapp:preparacion_pendientes")
        html = self.comparar(url, {"buscar": "Reparto"}, ["quitar", "resultados"])
        self.assertIn("No encontramos pendientes con esa búsqueda", html)
        self.assertIn(">Limpiar</a>", html)
        sin_busqueda = self.comparar(url, {"buscar": ""}, ["quitar", "resultados"])
        self.assertNotIn(">Limpiar</a>", sin_busqueda)

    def test_domicilios(self):
        url = reverse("entregasapp:domicilios")
        html = self.comparar(url, {"buscar": self.buscada.rut, "sector": "", "estado": ""}, ["quitar", "resultados"])
        self.assertIn(self.buscada.apellidos, html)
        self.assertNotIn(self.otra.apellidos, html)
        self.assertIn("<caption data-anuncio>1 paciente del reparto</caption>", html)
        self.assertIn(">Quitar filtros</a>", html)
        todos = self.comparar(url, {"buscar": "", "sector": "", "estado": ""}, ["quitar", "resultados"])
        self.assertNotIn(">Quitar filtros</a>", todos)
        self.client.force_login(self.equipo["encargado"])  # también la usa el encargado en terreno
        self.comparar(url, {"buscar": self.buscada.rut}, ["quitar", "resultados"])

    def test_excepciones(self):
        url = reverse("entregasapp:excepciones")
        cronico = paciente(edad=62, cronico=True)
        html = self.comparar(url, {"accion": "buscar", "buscar": cronico.rut}, ["resultados"])
        self.assertIn("Inscribir excepción", html)
        self.assertIn('<p class="suave" data-anuncio>Encontramos 1 paciente.</p>', html)
        sin_texto = self.comparar(url, {"accion": "buscar", "buscar": ""}, ["resultados"])
        self.assertEqual(zonas(sin_texto), {"resultados": ""}, "sin texto la zona queda vacía, sin «No encontramos»")
        nada = self.comparar(url, {"accion": "buscar", "buscar": "zzzz"}, ["resultados"])
        self.assertIn("<p data-anuncio>No encontramos pacientes con esa búsqueda.</p>", nada)

    def test_el_fragmento_respeta_los_permisos_y_la_sesion(self):
        excepciones = reverse("entregasapp:excepciones")
        self.client.force_login(self.equipo["tecnico"])
        self.assertEqual(self.client.post(excepciones, {"accion": "buscar", "buscar": "a"}, **EN_VIVO).status_code, 403)
        self.client.force_login(self.equipo["encargado"])
        self.assertEqual(self.client.post(reverse("recetasapp:pacientes"), {"buscar": "a"}, **EN_VIVO).status_code, 403)
        self.client.logout()
        salida = self.client.post(reverse("recetasapp:pacientes"), {"buscar": "a"}, **EN_VIVO)
        self.assertEqual(salida.status_code, 302, "el script sigue la redirección al inicio de sesión")

    def test_un_get_con_la_cabecera_recibe_la_pagina_completa(self):
        respuesta = self.client.get(reverse("recetasapp:pacientes"), **EN_VIVO)
        self.assertTemplateUsed(respuesta, "recetas/pacientes_lista.html")
        self.assertTemplateNotUsed(respuesta, PLANTILLA)
