"""Contexto de rol, filtros y contratos de las plantillas compartidas."""

from datetime import timedelta
from html.parser import HTMLParser

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.messages import constants as niveles
from django.contrib.messages.storage.base import Message
from django.core.paginator import Paginator
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from coreapp.context_processors import rol_actual
from coreapp.roles import ENCARGADO, ETIQUETAS_ROLES, JEFA, TECNICO
from coreapp.templatetags.core_tags import minutos, rut
from usuariosapp.models import Perfil


class ContextoRolTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.usuario = get_user_model().objects.create_user(username="cuenta_sintetica")
        Perfil.objects.create(usuario=self.usuario)

    def contexto(self, usuario):
        self.request.user = usuario
        return rol_actual(self.request)

    def test_anonimo_sin_rol(self):
        self.assertEqual(self.contexto(AnonymousUser()), {"rol": "", "nombre_rol": ""})

    def test_cuenta_sin_grupos(self):
        self.assertEqual(self.contexto(self.usuario)["nombre_rol"], "Acceso pendiente de regularización")

    def test_muestra_cada_rol_reconocido(self):
        for nombre in (JEFA, TECNICO, ENCARGADO):
            with self.subTest(rol=nombre):
                self.usuario.groups.set([Group.objects.get_or_create(name=nombre)[0]])
                self.assertEqual(self.contexto(self.usuario), {"rol": nombre, "nombre_rol": ETIQUETAS_ROLES[nombre]})

    def test_varios_roles_operativos_no_eligen_un_privilegio_por_prioridad(self):
        self.usuario.groups.set(Group.objects.create(name=nombre) for nombre in (ENCARGADO, JEFA, TECNICO, "Grupo sintético"))
        self.assertEqual(self.contexto(self.usuario)["rol"], "")

    def test_grupo_ajeno_no_cambia_el_rol_operativo_unico(self):
        self.usuario.groups.set(Group.objects.create(name=nombre) for nombre in (TECNICO, "Grupo sintético"))
        self.assertEqual(self.contexto(self.usuario)["rol"], TECNICO)

    def test_superusuario_muestra_administracion(self):
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=["is_superuser"])
        self.assertEqual(self.contexto(self.usuario), {"rol": "superusuario", "nombre_rol": "Administración"})


class FiltrosTests(SimpleTestCase):
    def test_rut_formateado_y_entrada_invalida(self):
        self.assertEqual(rut("12345678-5"), "12.345.678-5")
        self.assertEqual(rut(None), "")
        self.assertEqual(rut("<script>"), "")
        self.assertEqual(rut("12345678-9"), "")

    def test_minutos_redondean_hacia_arriba(self):
        for entrada, esperado in ((0, "0 min"), (1, "1 min"), (60, "1 min"),
                                  (61, "2 min"), (-3, "0 min"), (timedelta(seconds=90), "2 min")):
            with self.subTest(entrada=entrada):
                self.assertEqual(minutos(entrada), esperado)

    def test_minutos_invalidos_no_rompen_la_plantilla(self):
        for entrada in (None, "texto", float("inf"), float("nan")):
            with self.subTest(entrada=entrada):
                self.assertEqual(minutos(entrada), "—")

    def test_filtros_se_cargan_desde_el_motor_django(self):
        plantilla = Template('{% load core_tags %}{{ identificador|rut }} / {{ segundos|minutos }}')
        self.assertEqual(plantilla.render(Context({"identificador": "12345678-5", "segundos": 61})), "12.345.678-5 / 2 min")


class DocumentoHTML(HTMLParser):
    def __init__(self, contenido):
        super().__init__()
        self.elementos = []
        self.feed(contenido)

    def handle_starttag(self, etiqueta, atributos):
        self.elementos.append((etiqueta, dict(atributos)))


class PlantillasTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/", {"buscar": "sintetico", "page": "2"})
        self.usuario = get_user_model().objects.create_user(username="cuenta_plantillas_sintetica")
        Perfil.objects.create(usuario=self.usuario)
        self.request.user = self.usuario

    def renderizar(self, nombre, **contexto):
        return render_to_string(nombre, contexto, request=self.request)

    def test_todas_las_plantillas_renderizan(self):
        contexto = {
            "form": AuthenticationForm(self.request),
            "page_obj": Paginator(range(6), 2).page(2),
            "messages": [Message(niveles.ERROR, "Aviso sintético")],
        }
        for archivo in (settings.BASE_DIR / "templates").rglob("*"):
            if archivo.is_file():
                nombre = archivo.relative_to(settings.BASE_DIR / "templates").as_posix()
                with self.subTest(plantilla=nombre):
                    datos = {**contexto, "page_obj": Paginator([], 20).page(1)} if nombre.startswith("recetas/") else contexto
                    self.assertTrue(self.renderizar(nombre, **datos).strip())

    def test_layouts_con_idioma_salto_y_un_solo_main(self):
        for nombre in ("components/Layout/base.html", "components/Layout/base_publica.html", "components/Layout/base_acceso.html",
                       "index.html", "403.html", "404.html", "500.html", "registration/login.html"):
            with self.subTest(plantilla=nombre):
                html = self.renderizar(nombre, form=AuthenticationForm(self.request))
                documento = DocumentoHTML(html)
                self.assertIn(("html", {"lang": "es-CL"}), documento.elementos)
                principales = [atributos for etiqueta, atributos in documento.elementos if etiqueta == "main"]
                self.assertEqual(len(principales), 1)
                self.assertEqual(principales[0]["id"], "contenido")
                self.assertIn('href="#contenido"', html)
                self.assertIn("Saltar al contenido", html)
                ids = [atributos["id"] for _, atributos in documento.elementos if "id" in atributos]
                self.assertEqual(len(ids), len(set(ids)))

    def test_navegacion_por_perfil_sin_enlaces_a_vistas_futuras(self):
        for rol, texto in ((JEFA, "Ventanillas y pesos"), (TECNICO, "Atención"), (ENCARGADO, "Entregas en terreno")):
            with self.subTest(rol=rol):
                self.usuario.groups.set([Group.objects.create(name=rol)])
                html = self.renderizar("components/navbar.html")
                self.assertIn(texto, html)
                self.assertNotIn('href="/admin/"', html)
                self.assertIn('action="/usuarios/salir/" method="post"', html)

    def test_mensajes_son_alertas_y_escapan_html(self):
        html = self.renderizar("components/mensajes.html", messages=[Message(niveles.ERROR, "<script>dato sintético</script>")])
        self.assertIn('role="alert"', html)
        self.assertIn("message-error", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_paginacion_conserva_filtros_y_no_duplica_interrogacion(self):
        html = self.renderizar("components/paginator.html", page_obj=Paginator(range(6), 2).page(2))
        enlaces = [atributos["href"] for etiqueta, atributos in DocumentoHTML(html).elementos if etiqueta == "a"]
        self.assertEqual(enlaces, ["?buscar=sintetico&page=1", "?buscar=sintetico&page=3"])

    def test_paginacion_no_aparece_para_una_pagina(self):
        self.assertEqual(self.renderizar("components/paginator.html", page_obj=Paginator(range(2), 2).page(1)).strip(), "")

    def test_500_no_depende_de_una_plantilla_padre(self):
        self.assertNotRegex((settings.BASE_DIR / "templates/500.html").read_text(encoding="utf-8"), r"{%\s*extends\b")


class AccesoConTarjetaTests(TestCase):
    """Inicio de sesión y pantallas de acceso: una tarjeta con el formulario a la izquierda y la ilustración a la derecha."""

    def pagina(self, nombre):
        return self.client.get(reverse(nombre)).content.decode()

    def test_login_y_recuperacion_ponen_el_formulario_antes_que_la_ilustracion(self):
        for nombre in ("usuariosapp:login", "usuariosapp:recuperar_clave"):
            with self.subTest(pagina=nombre):
                html = self.pagina(nombre)
                self.assertIn('class="entrada-tarjeta"', html)
                self.assertLess(html.index('class="entrada-formulario"'), html.index('<main id="contenido"'))
                self.assertLess(html.index('<main id="contenido"'), html.index('class="entrada-arte"'))
                self.assertEqual(html.count("<main"), 1)
                self.assertNotIn('class="acceso"', html)

    def test_la_ilustracion_es_decorativa_la_direccion_se_lee_y_la_marca_enlaza_al_inicio(self):
        html = self.pagina("usuariosapp:login")
        self.assertRegex(html, r'<svg class="entrada-ilustracion"[^>]*aria-hidden="true"')
        self.assertIn("Departamento de Salud Municipal", html)
        self.assertEqual(html.count('class="marca"'), 1)
        self.assertIn(f'<a class="marca" href="{reverse("coreapp:inicio")}">', html)

    def test_el_login_conserva_sus_campos_el_boton_de_mostrar_clave_y_la_ayuda(self):
        html = self.pagina("usuariosapp:login")
        for texto in ("Inicia sesión", "Nombre de usuario", "Contraseña", "Entrar", "¿Olvidaste tu contraseña?", "¿No puedes entrar?"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        self.assertIn('class="campo-clave-ver"', html)
        self.assertIn('aria-label="Mostrar contraseña"', html)

    def test_el_totem_conserva_su_propio_layout(self):
        html = self.pagina("turnosapp:totem")
        self.assertIn('class="acceso"', html)
        self.assertNotIn("entrada-tarjeta", html)

    def test_los_avisos_comparten_la_tarjeta_y_el_500_la_trae_sin_depender_de_otra_plantilla(self):
        for nombre in ("403.html", "404.html", "500.html"):
            with self.subTest(plantilla=nombre):
                html = render_to_string(nombre)
                self.assertIn('class="entrada-tarjeta"', html)
                self.assertEqual(html.count("<main"), 1)

    def test_la_tarjeta_pasa_a_una_columna_sin_depender_del_ancho_de_la_ventana(self):
        """Con texto muy ampliado las dos columnas no caben: la rejilla las apila sola, sin un corte fijo."""
        css = (settings.BASE_DIR / "static/css/base.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.entrada-tarjeta \{[^}]*grid-template-columns: repeat\(auto-fit, minmax\(min\(100%, 24rem\), 1fr\)\)")
