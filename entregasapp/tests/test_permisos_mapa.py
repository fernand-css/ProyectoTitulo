"""RF-09-14: matriz de permisos del 09 en el servidor, CSRF, `no-store`, URL sin datos personales y estructura accesible."""

import uuid

from django.test import Client, TestCase
from django.urls import reverse

from coreapp.roles import ENCARGADO, JEFA
from coreapp.tests.test_plantillas import DocumentoHTML
from entregasapp.models import OrdenRuta, ParadaRuta
from entregasapp.services import mover_parada
from .ayudas import cuenta, equipo, hoy, paciente, punto_km, receta, visita


class PermisosMapaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.a = visita(self.equipo, (0, 2))
        self.b = visita(self.equipo, (0, 1))
        self.persona = self.a.entrega.paciente

    def rutas_get(self):
        return {
            "mis": reverse("entregasapp:mis"),
            "mapa": reverse("entregasapp:mapa"),
            "ir_a": reverse("entregasapp:ir_a", args=[self.a.pk]),
            "rutas": reverse("entregasapp:rutas") + f"?encargado={self.encargado.pk}&fecha={hoy():%Y-%m-%d}",
        }

    def rutas_post(self):
        datos = {"intento": self.a.pk, "destino": "1", "version": 0, "operacion_id": str(uuid.uuid4())}
        return {
            "orden_mover": (reverse("entregasapp:orden_mover"), datos),
            "orden_sugerido": (reverse("entregasapp:orden_sugerido"), {"version": 0, "operacion_id": str(uuid.uuid4())}),
        }

    def estado(self):
        return list(OrdenRuta.objects.values_list("version", flat=True)), ParadaRuta.objects.count()

    def test_matriz_de_acceso_por_perfil(self):
        permitidas = {
            "encargado": {"mis", "mapa", "ir_a"},
            "encargado2": {"mis", "mapa"},  # su propia ruta; la parada ajena le da 403
            "qf": {"rutas"},
            "admin": {"rutas"},
            "tecnico": set(),
        }
        for actor, rutas in permitidas.items():
            self.client.force_login(self.equipo[actor])
            for nombre, url in self.rutas_get().items():
                with self.subTest(actor=actor, ruta=nombre):
                    respuesta = self.client.get(url)
                    self.assertEqual(respuesta.status_code, 200 if nombre in rutas else 403)
                    if respuesta.status_code == 200:  # la página 403 de Django no lleva datos
                        self.assertIn("no-store", respuesta["Cache-Control"])
                    self.assertNotIn(self.persona.rut, respuesta.request["PATH_INFO"] + respuesta.request["QUERY_STRING"])

    def test_solo_el_encargado_cambia_el_orden(self):
        antes = self.estado()
        for actor in ("qf", "admin", "tecnico"):
            self.client.force_login(self.equipo[actor])
            for nombre, (url, datos) in self.rutas_post().items():
                with self.subTest(actor=actor, post=nombre):
                    self.assertEqual(self.client.post(url, datos).status_code, 403)
        self.assertEqual(self.estado(), antes)
        self.client.force_login(self.equipo["encargado2"])
        url, datos = self.rutas_post()["orden_mover"]
        respuesta = self.client.post(url, datos, follow=True)
        self.assertContains(respuesta, "Esa visita ya no está en tu ruta de hoy")
        self.assertEqual(self.estado(), antes)
        self.client.force_login(self.encargado)
        self.client.post(url, datos)
        self.assertEqual(self.estado(), ([1], 2))

    def test_anonimo_inactiva_y_sin_perfil(self):
        antes = self.estado()
        for nombre, url in self.rutas_get().items():
            with self.subTest(anonimo=nombre):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse("usuariosapp:login"), respuesta["Location"])
        for nombre, (url, datos) in self.rutas_post().items():
            with self.subTest(anonimo_post=nombre):
                self.assertEqual(self.client.post(url, datos).status_code, 302)
        for usuario in (cuenta("inactiva_ruta", ENCARGADO, activa=False), cuenta("sin_perfil_ruta", ENCARGADO, perfil=False),
                        cuenta("qf_sin_perfil_ruta", JEFA, perfil=False)):
            self.client.force_login(usuario)
            for nombre, url in self.rutas_get().items():
                with self.subTest(usuario=usuario.username, ruta=nombre):
                    self.assertIn(self.client.get(url).status_code, (302, 403))
            for nombre, (url, datos) in self.rutas_post().items():
                with self.subTest(usuario=usuario.username, post=nombre):
                    self.assertIn(self.client.post(url, datos).status_code, (302, 403))
            self.client.logout()
        self.assertEqual(self.estado(), antes)

    def test_post_sin_csrf_se_rechaza(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.encargado)
        antes = self.estado()
        for nombre, (url, datos) in self.rutas_post().items():
            with self.subTest(post=nombre):
                self.assertEqual(cliente.post(url, datos).status_code, 403)
        self.assertEqual(self.estado(), antes)

    def test_url_de_rutas_manipulada_no_muestra_datos(self):
        self.client.force_login(self.equipo["qf"])
        for consulta in (f"?encargado={self.equipo['admin'].pk}&fecha={hoy():%Y-%m-%d}", f"?encargado={self.persona.rut}",
                         f"?encargado={self.encargado.pk}&fecha=2000-01-01", f"?encargado={self.encargado.pk}&fecha=hoy"):
            with self.subTest(consulta=consulta):
                respuesta = self.client.get(reverse("entregasapp:rutas") + consulta)
                self.assertEqual(respuesta.status_code, 400)
                self.assertNotContains(respuesta, self.persona.apellidos, status_code=400)
                self.assertNotContains(respuesta, "datos-mapa", status_code=400)


class EstructuraMapaTests(TestCase):
    """Un solo h1, ids únicos, campos con etiqueta e imágenes con texto alternativo en las pantallas del 09.

    No reemplaza la revisión con navegador, axe ni la usabilidad con cinco personas (RNF-04).
    """

    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.intentos = [visita(self.equipo, en) for en in ((0, 1), (0, 2))]
        self.sin = visita(self.equipo, None)
        mover_parada(self.encargado, self.sin.pk, "1", 0, uuid.uuid4())
        con_punto = paciente(edad=88)
        receta(con_punto)
        from entregasapp.services import guardar_domicilio
        latitud, longitud = punto_km(2, 2)
        guardar_domicilio(self.equipo["qf"], con_punto.pk, {"sector": "verde", "direccion": "Camino sintético",
                                                            "latitud": latitud, "longitud": longitud})
        self.con_punto = con_punto

    def revisar(self, html, nombre):
        documento = DocumentoHTML(html)
        self.assertEqual(sum(1 for etiqueta, _ in documento.elementos if etiqueta == "h1"), 1, nombre)
        ids = [atributos["id"] for _, atributos in documento.elementos if "id" in atributos]
        self.assertEqual(len(ids), len(set(ids)), f"ids repetidos en {nombre}")
        etiquetados = {atributos["for"] for etiqueta, atributos in documento.elementos if etiqueta == "label" and "for" in atributos}
        for etiqueta, atributos in documento.elementos:
            if etiqueta == "img":
                self.assertTrue(atributos.get("alt"), f"imagen sin texto alternativo en {nombre}")
            if etiqueta in ("input", "select", "textarea") and atributos.get("type") not in ("hidden", "submit"):
                self.assertIn(atributos.get("id"), etiquetados, f"campo sin etiqueta en {nombre}: {atributos.get('name')}")
            if etiqueta == "button":
                self.assertNotEqual(atributos.get("type"), None, f"botón sin tipo en {nombre}")

    def test_pantallas_del_encargado(self):
        self.client.force_login(self.encargado)
        paginas = {
            "mis entregas (orden manual)": reverse("entregasapp:mis"),
            "mapa": reverse("entregasapp:mapa"),
            "ir a": reverse("entregasapp:ir_a", args=[self.intentos[0].pk]),
            "domicilio con mapa": reverse("entregasapp:domicilio", args=[self.con_punto.pk]),
        }
        for nombre, url in paginas.items():
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.revisar(respuesta.content.decode(), nombre)

    def test_pantallas_de_la_qf(self):
        self.client.force_login(self.equipo["qf"])
        paginas = {
            "rutas sin filtro": reverse("entregasapp:rutas"),
            "rutas de hoy": reverse("entregasapp:rutas") + f"?encargado={self.encargado.pk}&fecha={hoy():%Y-%m-%d}",
            "domicilio con mapa": reverse("entregasapp:domicilio", args=[self.con_punto.pk]),
        }
        for nombre, url in paginas.items():
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.revisar(respuesta.content.decode(), nombre)
