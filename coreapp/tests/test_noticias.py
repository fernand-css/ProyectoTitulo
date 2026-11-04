"""Noticias del inicio: lectura del sitio municipal (siempre con páginas sintéticas), elección y vista."""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from coreapp import noticias
from coreapp.models import NoticiaComuna


def tarjeta(id_externo, titulo, imagen="img/noticias/foto.png"):
    return (f"<div class='noticia-card'><img src='{imagen}' alt='{titulo}'><h3>{titulo}</h3>"
            f"<a href='noticia.php?id={id_externo}' class='btn-leer'>Leer más</a></div>")


def pagina_listado(*tarjetas):
    return "<html><body><div id='contenedor-noticias'>" + "".join(tarjetas) + "</div></body></html>"


def pagina_noticia(fecha="27/05/2026", parrafos=("Primera oración sintética. Segunda oración sintética.", "Segundo párrafo.")):
    cuerpo = "".join(f"<p>{p}</p>" for p in parrafos)
    return (f"<html><body><main><p>\n Publicado el {fecha} | Por Alguien\n </p><h1>Título</h1>"
            f"<div class=\"contenido-noticia\">{cuerpo}<div><p>anidado</p></div></div></main></body></html>")


class SitioFalso:
    """Reemplaza la descarga: sirve páginas sintéticas por dirección y cuenta las solicitudes."""

    def __init__(self, paginas):
        self.paginas = paginas
        self.pedidas = []

    def __call__(self, direccion):
        self.pedidas.append(direccion)
        if direccion not in self.paginas:
            raise noticias.ErrorNoticias("sin respuesta sintética")
        return self.paginas[direccion]


def detalle(id_externo):
    return f"{noticias.SITIO}noticia.php?id={id_externo}"


class LecturaTests(SimpleTestCase):
    def test_listado_extrae_numero_titulo_e_imagen_absoluta(self):
        resultado = noticias.leer_listado(pagina_listado(tarjeta(37, "Agua sintética"), tarjeta(36, "Camino sintético")))
        self.assertEqual([t.id_externo for t in resultado], [37, 36])
        self.assertEqual(resultado[0].titulo, "Agua sintética")
        self.assertEqual(resultado[0].imagen, noticias.SITIO + "img/noticias/foto.png")

    def test_listado_acepta_tarjetas_article_y_descarta_las_incompletas(self):
        html = "<article class='noticia-card'><h3>Sin enlace</h3></article>" + tarjeta(5, "Con enlace").replace("div", "article")
        self.assertEqual([t.id_externo for t in noticias.leer_listado(html)], [5])

    def test_imagen_fuera_del_sitio_o_sin_https_se_descarta(self):
        for imagen in ("http://www.municipalidadsannicolas.cl/x.png", "https://otro.example/x.png", "javascript:alert(1)", "//otro.example/x.png"):
            with self.subTest(imagen=imagen):
                self.assertEqual(noticias.leer_listado(pagina_listado(tarjeta(1, "Titulo", imagen)))[0].imagen, "")

    def test_noticia_extrae_fecha_y_primer_parrafo_del_cuerpo(self):
        fecha, resumen = noticias.leer_noticia(pagina_noticia())
        self.assertEqual(fecha, date(2026, 5, 27))
        self.assertEqual(resumen, "Primera oración sintética. Segunda oración sintética.")

    def test_noticia_sin_cuerpo_ni_fecha_no_falla(self):
        self.assertEqual(noticias.leer_noticia("<html><body><p>Nada</p></body></html>"), (None, ""))
        self.assertEqual(noticias.leer_noticia(pagina_noticia(fecha="31/02/2026"))[0], None)

    def test_resumir_corta_en_la_oracion_o_en_la_palabra(self):
        texto = "Primera oración sintética bastante larga para el corte. " + "palabra " * 60
        self.assertEqual(noticias.resumir(texto, 80), "Primera oración sintética bastante larga para el corte.")
        self.assertTrue(noticias.resumir("palabra " * 80, 50).endswith("…"))
        self.assertEqual(noticias.resumir("Corto.  Texto", 50), "Corto. Texto")

    def test_detecta_noticias_de_salud_sin_confundir_las_de_infraestructura(self):
        self.assertTrue(noticias.es_de_salud("San Nicolás lidera vacunación contra la influenza"))
        self.assertTrue(noticias.es_de_salud("Operativo en el CESFAM"))
        self.assertTrue(noticias.es_de_salud("Titulo neutro", "El Departamento de Salud informó"))
        self.assertFalse(noticias.es_de_salud("Municipalidad logra financiamiento para el APR de Curica"))
        self.assertFalse(noticias.es_de_salud("Pavimentación del camino a Curica se concretará en 2027"))

    def test_descargar_rechaza_direcciones_fuera_del_sitio_sin_salir_a_internet(self):
        with patch("coreapp.noticias.urlopen") as abrir:
            for direccion in ("http://www.municipalidadsannicolas.cl/", "https://otro.example/", "file:///etc/hosts"):
                with self.subTest(direccion=direccion), self.assertRaises(noticias.ErrorNoticias):
                    noticias.descargar(direccion)
        abrir.assert_not_called()


class ActualizarTests(TestCase):
    def sitio(self, **extra):
        paginas = {
            noticias.LISTADO: pagina_listado(tarjeta(37, "Agua sintética"), tarjeta(36, "Camino sintético")),
            noticias.CARGAR_MAS.format(desplazamiento=8): pagina_listado(tarjeta(18, "Vacunación sintética contra la influenza")),
            noticias.CARGAR_MAS.format(desplazamiento=16): "",
            detalle(37): pagina_noticia("15/10/2026", ("Resumen del agua.",)),
            detalle(36): pagina_noticia("14/10/2026", ("Resumen del camino.",)),
            detalle(18): pagina_noticia("27/05/2026", ("Resumen de la vacunación.",)),
        }
        paginas.update(extra)
        return SitioFalso(paginas)

    def test_guarda_texto_fecha_y_enlaces_de_cada_noticia(self):
        self.assertEqual(noticias.actualizar(leer=self.sitio()), (3, 0, 0))
        agua = NoticiaComuna.objects.get(id_externo=37)
        self.assertEqual((agua.titulo, agua.resumen, agua.publicada_el), ("Agua sintética", "Resumen del agua.", date(2026, 10, 15)))
        self.assertEqual(agua.url, detalle(37))
        self.assertEqual(agua.imagen_url, noticias.SITIO + "img/noticias/foto.png")
        self.assertFalse(agua.es_salud)
        self.assertTrue(NoticiaComuna.objects.get(id_externo=18).es_salud)

    def test_repetir_no_duplica_ni_vuelve_a_pedir_el_detalle(self):
        noticias.actualizar(leer=self.sitio())
        sitio = self.sitio()
        self.assertEqual(noticias.actualizar(leer=sitio), (0, 3, 0))
        self.assertEqual(NoticiaComuna.objects.count(), 3)
        self.assertFalse([d for d in sitio.pedidas if "noticia.php" in d])

    def test_respeta_el_maximo_y_no_pide_mas_paginas_de_las_necesarias(self):
        sitio = self.sitio()
        noticias.actualizar(maximo=2, leer=sitio)
        self.assertEqual(NoticiaComuna.objects.count(), 2)
        self.assertFalse([d for d in sitio.pedidas if "cargar_noticias" in d])

    def test_si_falla_el_detalle_guarda_lo_del_listado_y_lo_reintenta_despues(self):
        sitio = self.sitio()
        del sitio.paginas[detalle(36)]
        self.assertEqual(noticias.actualizar(leer=sitio), (3, 0, 1))
        self.assertIsNone(NoticiaComuna.objects.get(id_externo=36).publicada_el)
        noticias.actualizar(leer=self.sitio())
        self.assertEqual(NoticiaComuna.objects.get(id_externo=36).publicada_el, date(2026, 10, 14))

    def test_si_falla_el_listado_no_toca_lo_guardado(self):
        noticias.actualizar(leer=self.sitio())
        with self.assertRaises(noticias.ErrorNoticias):
            noticias.actualizar(leer=SitioFalso({}))
        with self.assertRaises(noticias.ErrorNoticias):
            noticias.actualizar(leer=SitioFalso({noticias.LISTADO: "<html>sin tarjetas</html>"}))
        self.assertEqual(NoticiaComuna.objects.count(), 3)

    def test_comando_informa_el_resultado_y_falla_sin_ocultar_el_error(self):
        salida = StringIO()
        with patch("coreapp.noticias.actualizar", return_value=(2, 1, 1)):
            call_command("actualizar_noticias", "--maximo", "5", stdout=salida)
        self.assertIn("2 nuevas y 1 ya conocidas", salida.getvalue())
        self.assertIn("1 sin fecha", salida.getvalue())
        with patch("coreapp.noticias.actualizar", side_effect=noticias.ErrorNoticias("sitio caído")):
            with self.assertRaisesMessage(CommandError, "sitio caído"):
                call_command("actualizar_noticias")
        with self.assertRaises(CommandError):
            call_command("actualizar_noticias", "--maximo", "0")


class SeleccionTests(TestCase):
    hoy = date(2026, 11, 4)

    def crear(self, id_externo, dias, salud=False, titulo=None):
        return NoticiaComuna.objects.create(
            id_externo=id_externo, titulo=titulo or f"Noticia {id_externo}", publicada_el=self.hoy - timedelta(days=dias),
            url=detalle(id_externo), es_salud=salud)

    def test_sin_noticias_no_hay_destacada(self):
        self.assertEqual(noticias.noticias_del_inicio(self.hoy), (None, []))

    def test_destaca_la_noticia_de_salud_vigente_aunque_haya_otras_mas_nuevas(self):
        for i, dias in enumerate((20, 21, 22, 23, 24)):
            self.crear(40 + i, dias)
        salud = self.crear(10, 160, salud=True)
        destacada, otras = noticias.noticias_del_inicio(self.hoy)
        self.assertEqual(destacada, salud)
        self.assertEqual([n.id_externo for n in otras], [40, 41, 42, 43])

    def test_una_noticia_de_salud_muy_antigua_deja_paso_a_la_mas_reciente(self):
        self.crear(10, noticias.DIAS_VIGENCIA_DESTACADA_SALUD + 1, salud=True)
        reciente = self.crear(40, 3)
        destacada, otras = noticias.noticias_del_inicio(self.hoy)
        self.assertEqual((destacada, [n.id_externo for n in otras]), (reciente, [10]))

    def test_sin_noticias_de_salud_destaca_la_mas_reciente(self):
        self.crear(41, 9)
        reciente = self.crear(40, 2)
        self.assertEqual(noticias.noticias_del_inicio(self.hoy)[0], reciente)


class InicioConNoticiasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superusuario = get_user_model().objects.create_superuser(username="admin_sintetico", password="Clave-sintetica-2026!")

    def crear(self, id_externo, titulo, dias, salud=False, imagen=True):
        return NoticiaComuna.objects.create(
            id_externo=id_externo, titulo=titulo, resumen=f"Resumen de {titulo}.",
            publicada_el=timezone.localdate() - timedelta(days=dias), url=detalle(id_externo), es_salud=salud,
            imagen_url=f"{noticias.SITIO}img/noticias/{id_externo}.png" if imagen else "")

    def abrir(self):
        self.client.force_login(self.superusuario)
        with patch("coreapp.noticias.urlopen") as red:
            respuesta = self.client.get(reverse("coreapp:inicio"))
        red.assert_not_called()  # abrir el inicio nunca sale a Internet
        return respuesta

    def test_muestra_destacada_y_lista_con_fecha_y_enlaces_seguros(self):
        self.crear(18, "Vacunación sintética", 30, salud=True)
        for i in range(5):
            self.crear(30 + i, f"Obra sintética {i}", i + 1)
        html = self.abrir().content.decode()
        self.assertIn("Noticias de San Nicolás", html)
        self.assertIn("Salud en la comuna. Municipalidad de San Nicolás", html)
        self.assertIn("Vacunación sintética", html)
        self.assertEqual(html.count('class="noticia"'), 4)
        self.assertNotIn("Obra sintética 4", html)  # la quinta no cabe en la lista
        self.assertIn('referrerpolicy="no-referrer"', html)
        self.assertIn(f'href="{detalle(18)}" target="_blank" rel="noopener noreferrer"', html)
        self.assertIn("(se abre en otra pestaña)", html)
        self.assertIn('datetime="', html)

    def test_las_fotos_son_decorativas_y_no_se_copian(self):
        self.crear(18, "Vacunación sintética", 30, salud=True)
        html = self.abrir().content.decode()
        self.assertIn(f'src="{noticias.SITIO}img/noticias/18.png" alt=""', html)

    def test_noticia_sin_foto_ni_fecha_se_ve_completa(self):
        NoticiaComuna.objects.create(id_externo=1, titulo="Noticia sin foto sintética", url=detalle(1))
        html = self.abrir().content.decode()
        self.assertIn("Noticia sin foto sintética", html)
        self.assertNotIn("destacada-foto", html)

    def test_sin_noticias_guardadas_explica_donde_leerlas(self):
        html = self.abrir().content.decode()
        self.assertIn("Todavía no hay noticias guardadas", html)
        self.assertIn(f'href="{noticias.SITIO}noticias.php"', html)

    def test_el_inicio_ya_no_ofrece_administracion_pero_el_menu_si(self):
        html = self.abrir().content.decode()
        self.assertNotIn("Cuentas, grupos y registro de auditoría", html)
        self.assertNotIn("Tu cuenta tiene acceso a la administración del sistema", html)
        self.assertIn(reverse("admin:index"), html)  # sigue en el menú lateral
        self.assertIn("Tu trabajo en la unidad", html)
        self.assertIn("Usuarios", html)
        self.assertIn("Padrón y recetas", html)
        self.assertIn("Sesión activa", html)

    def test_titulos_unicos_y_un_solo_h1(self):
        self.crear(18, "Vacunación sintética", 30, salud=True)
        html = self.abrir().content.decode()
        self.assertEqual(html.count("<h1"), 1)
        ids = [parte.split('"')[0] for parte in html.split(' id="')[1:]]
        self.assertEqual(len(ids), len(set(ids)))
