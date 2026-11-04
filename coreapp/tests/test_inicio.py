"""Inicio después de iniciar sesión: accesos por perfil, administración solo en el menú y las cifras de lo que espera hoy."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from coreapp.roles import ENCARGADO, JEFA, TECNICO
from usuariosapp.models import Perfil


class InicioGeneralTests(TestCase):
    """El inicio no repite la administración (sigue en el menú) y mantiene una estructura de títulos limpia."""

    @classmethod
    def setUpTestData(cls):
        cls.superusuario = get_user_model().objects.create_superuser(username="admin_sintetico", password="Clave-sintetica-2026!")

    def abrir(self):
        self.client.force_login(self.superusuario)
        return self.client.get(reverse("coreapp:inicio"))

    def test_el_inicio_ya_no_ofrece_administracion_pero_el_menu_si(self):
        html = self.abrir().content.decode()
        self.assertNotIn("Cuentas, grupos y registro de auditoría", html)
        self.assertNotIn("Tu cuenta tiene acceso a la administración del sistema", html)
        self.assertIn(reverse("admin:index"), html)  # sigue en el menú lateral
        self.assertIn("Tu trabajo en la unidad", html)
        self.assertIn("Crea y administra las cuentas del equipo.", html)
        self.assertIn("Recetas y pacientes", html)
        self.assertIn("Sesión activa", html)

    def test_titulos_unicos_y_un_solo_h1(self):
        html = self.abrir().content.decode()
        self.assertEqual(html.count("<h1"), 1)
        ids = [parte.split('"')[0] for parte in html.split(' id="')[1:]]
        self.assertEqual(len(ids), len(set(ids)))


class InicioPorPerfilTests(TestCase):
    """Los accesos y paneles de cada perfil."""

    def entrar(self, rol=None, superusuario=False):
        usuarios = get_user_model().objects
        if superusuario:
            usuario = usuarios.create_superuser(username="super_sintetico", password="Clave-sintetica-2026!")
        else:
            usuario = usuarios.create_user(username="persona_sintetica", password="Clave-sintetica-2026!")
            if rol:
                Perfil.objects.create(usuario=usuario)
                usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
        self.client.force_login(usuario)
        return self.client.get(reverse("coreapp:inicio")).content.decode()

    def test_jefa_ve_recetas_y_pacientes_la_supervision_de_la_atencion_y_usuarios(self):
        html = self.entrar(JEFA)
        for texto in ("Recetas y pacientes", "Mira la fila de espera", "Crea y administra las cuentas del equipo.", "Mi perfil", "Sesión activa"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        self.assertNotIn("Abrir atención y cola", html)

    def test_tecnico_ve_su_atencion_y_pacientes_pero_no_usuarios(self):
        html = self.entrar(TECNICO)
        self.assertIn("Abrir atención y cola", html)
        self.assertIn("Busca a una persona por RUT o apellido", html)
        self.assertNotIn("Recetas y pacientes", html)
        self.assertNotIn("Crea y administra las cuentas del equipo.", html)
        self.assertNotIn("Mira la fila de espera", html)

    def test_encargado_ve_su_panel_sin_atencion_pacientes_ni_usuarios(self):
        html = self.entrar(ENCARGADO)
        self.assertIn("herramientas de entrega en terreno", html)
        for ausente in ("Recetas y pacientes", "Abrir atención y cola", "Crea y administra las cuentas del equipo.", "hoy-lista"):
            with self.subTest(ausente=ausente):
                self.assertNotIn(ausente, html)

    def test_cuenta_sin_perfil_no_llega_al_inicio(self):
        """La cuenta sin perfil recibe la página de acceso pendiente, sin accesos."""
        usuario = get_user_model().objects.create_user(username="sin_perfil_sintetico", password="Clave-sintetica-2026!")
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("coreapp:inicio"))
        self.assertEqual(respuesta.status_code, 403)

    def test_superusuario_no_tiene_panel_de_perfil_ni_acceso_de_administracion_en_el_inicio(self):
        html = self.entrar(superusuario=True)
        self.assertIn("Recetas y pacientes", html)
        self.assertIn("Crea y administra las cuentas del equipo.", html)
        self.assertNotIn('id="titulo-perfil"', html)


class InicioLoQueEsperaHoyTests(TestCase):
    """Las dos cifras de «lo que espera hoy» y su enlace a la pantalla donde se atienden."""

    def pagina(self, rol, cantidades):
        usuario = get_user_model().objects.create_user(username=f"hoy_{rol[:3].lower()}_sintetico", password="Clave-sintetica-2026!")
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
        self.client.force_login(usuario)
        with patch("coreapp.context_processors.contadores_del_menu", return_value=cantidades) as contar:
            html = self.client.get(reverse("coreapp:inicio")).content.decode()
        return html, contar

    def test_el_personal_ve_la_fila_y_las_recetas_por_preparar_con_enlace(self):
        for rol in (JEFA, TECNICO):
            with self.subTest(rol=rol):
                html, contar = self.pagina(rol, {"fila": 4, "por_preparar": 1})
                self.assertIn('<strong class="hoy-numero">4</strong>', html)
                self.assertIn("personas esperan", html)
                self.assertIn('<strong class="hoy-numero">1</strong>', html)
                self.assertIn("receta por preparar", html)
                self.assertIn(f'href="{reverse("turnosapp:panel")}"', html)
                self.assertIn(f'href="{reverse("recetasapp:preparacion")}"', html)
                self.assertEqual(contar.call_count, 1)  # el menú y el inicio comparten la misma consulta

    def test_con_una_persona_en_espera_el_texto_va_en_singular(self):
        html, _ = self.pagina(TECNICO, {"fila": 1, "por_preparar": 0})
        self.assertIn("persona espera", html)
        self.assertIn("recetas por preparar", html)  # cero va en plural

    def test_el_encargado_no_ve_cifras_de_atencion(self):
        html, _ = self.pagina(ENCARGADO, {})
        self.assertNotIn("hoy-lista", html)
