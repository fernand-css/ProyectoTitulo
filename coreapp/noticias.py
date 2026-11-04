"""Noticias de San Nicolás para el inicio: lectura del sitio municipal y elección de qué mostrar.

El sitio de la Municipalidad no ofrece API ni RSS, así que `actualizar` lee sus páginas públicas
(`noticias.php`, `cargar_noticias.php` y `noticia.php`) y guarda texto y enlaces en `NoticiaComuna`.
Solo se usa desde el comando `actualizar_noticias`: el inicio lee la base y nunca sale a Internet.
No tiene relación con Rayén ni con datos de pacientes.
"""

import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from django.utils import timezone

from .models import NoticiaComuna

SITIO = "https://www.municipalidadsannicolas.cl/"
LISTADO = SITIO + "noticias.php"
CARGAR_MAS = SITIO + "cargar_noticias.php?offset={desplazamiento}"
POR_PAGINA = 8
MAXIMO_POR_DEFECTO = 24
TIEMPO_LIMITE = 10          # segundos por solicitud
PAUSA_ENTRE_SOLICITUDES = 0.5  # segundos entre las páginas de detalle
TAMANO_MAXIMO = 1_500_000   # bytes por página; una noticia pesa unos 20 000
USUARIO = "Prototipo-CESFAM-San-Nicolas (lectura de noticias publicas)"

# Una noticia de salud se destaca mientras tenga a lo más estos días; después manda la más reciente.
DIAS_VIGENCIA_DESTACADA_SALUD = 180
NOTICIAS_EN_LISTA = 4

_PALABRAS_SALUD = ("salud", "cesfam", "vacun", "influenza", "hospital", "posta ", "medic", "farmacia", "paciente", "sanitaria")


class ErrorNoticias(Exception):
    """No se pudo leer el sitio municipal; las noticias ya guardadas siguen mostrándose."""


@dataclass
class Tarjeta:
    id_externo: int
    titulo: str
    imagen: str


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def es_de_salud(titulo, resumen=""):
    texto = " " + _sin_tildes(f"{titulo} {resumen}")
    return any(_sin_tildes(palabra) in texto for palabra in _PALABRAS_SALUD)


def resumir(texto, limite=240):
    """Primer tramo del texto que quepa en `limite`, cortado donde termina una oración o una palabra."""
    texto = " ".join(texto.split())
    if len(texto) <= limite:
        return texto
    corte = texto.rfind(". ", 0, limite)
    if corte >= limite // 2:
        return texto[: corte + 1]
    return texto[:limite].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _direccion_del_sitio(ruta):
    """Dirección absoluta dentro del sitio municipal por https; cualquier otra cosa se descarta."""
    if not ruta:
        return ""
    absoluta = urljoin(SITIO, ruta.strip())
    partes = urlsplit(absoluta)
    if partes.scheme != "https" or partes.netloc != urlsplit(SITIO).netloc:
        return ""
    return absoluta


class _LectorListado(HTMLParser):
    """Tarjetas `noticia-card` del listado: imagen, título y número de la noticia."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tarjetas = []
        self._actual = None
        self._en_titulo = False

    def handle_starttag(self, etiqueta, atributos):
        datos = dict(atributos)
        clases = (datos.get("class") or "").split()
        if etiqueta in ("div", "article") and "noticia-card" in clases:
            self._actual = {"id": None, "titulo": "", "imagen": ""}
            self.tarjetas.append(self._actual)
        elif self._actual is None:
            return
        elif etiqueta == "img" and not self._actual["imagen"]:
            self._actual["imagen"] = datos.get("src") or ""
        elif etiqueta == "h3":
            self._en_titulo = True
        elif etiqueta == "a" and self._actual["id"] is None:
            encontrada = re.search(r"noticia\.php\?id=(\d+)", datos.get("href") or "")
            if encontrada:
                self._actual["id"] = int(encontrada.group(1))

    def handle_endtag(self, etiqueta):
        if etiqueta == "h3":
            self._en_titulo = False

    def handle_data(self, datos):
        if self._actual is not None and self._en_titulo:
            self._actual["titulo"] += datos


def leer_listado(html):
    lector = _LectorListado()
    lector.feed(html)
    resultado = []
    for tarjeta in lector.tarjetas:
        titulo = " ".join(tarjeta["titulo"].split())
        if tarjeta["id"] is not None and titulo:
            resultado.append(Tarjeta(tarjeta["id"], titulo, _direccion_del_sitio(tarjeta["imagen"])))
    return resultado


class _LectorNoticia(HTMLParser):
    """Fecha («Publicado el 27/05/2026») y primer párrafo del cuerpo de una noticia."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texto_previo = []
        self.parrafos = []
        self._en_cuerpo = False
        self._profundidad = 0
        self._en_parrafo = False

    def handle_starttag(self, etiqueta, atributos):
        clases = (dict(atributos).get("class") or "").split()
        if etiqueta == "div":
            if self._en_cuerpo:
                self._profundidad += 1
            elif "contenido-noticia" in clases:
                self._en_cuerpo, self._profundidad = True, 1
        elif etiqueta == "p" and self._en_cuerpo and not self.parrafos:
            self._en_parrafo = True
            self.parrafos.append("")

    def handle_endtag(self, etiqueta):
        if etiqueta == "p":
            self._en_parrafo = False
        elif etiqueta == "div" and self._en_cuerpo:
            self._profundidad -= 1
            self._en_cuerpo = self._profundidad > 0

    def handle_data(self, datos):
        if self._en_parrafo:
            self.parrafos[-1] += datos
        elif not self._en_cuerpo and len(self.texto_previo) < 400:
            self.texto_previo.append(datos)


def leer_noticia(html):
    """(fecha, resumen) de una noticia; lo que no aparezca queda vacío (None o '')."""
    lector = _LectorNoticia()
    lector.feed(html)
    fecha = None
    encontrada = re.search(r"Publicado el\s+(\d{1,2})/(\d{1,2})/(\d{4})", " ".join(lector.texto_previo))
    if encontrada:
        try:
            fecha = date(int(encontrada.group(3)), int(encontrada.group(2)), int(encontrada.group(1)))
        except ValueError:
            fecha = None
    resumen = resumir(lector.parrafos[0]) if lector.parrafos else ""
    return fecha, resumen


def descargar(direccion):
    """Texto de una página del sitio municipal; `ErrorNoticias` si no responde bien."""
    if not _direccion_del_sitio(direccion):
        raise ErrorNoticias("Dirección fuera del sitio municipal.")
    solicitud = Request(direccion, headers={"User-Agent": USUARIO, "Accept": "text/html"})
    try:
        with urlopen(solicitud, timeout=TIEMPO_LIMITE) as respuesta:  # noqa: S310 (https, sitio fijo)
            contenido = respuesta.read(TAMANO_MAXIMO + 1)
    except (URLError, OSError, ValueError) as error:
        raise ErrorNoticias(f"No se pudo leer {direccion}: {error}") from error
    if len(contenido) > TAMANO_MAXIMO:
        raise ErrorNoticias(f"La página {direccion} es demasiado grande.")
    return contenido.decode("utf-8", errors="replace")


def actualizar(maximo=MAXIMO_POR_DEFECTO, leer=descargar):
    """Trae las noticias más recientes y las guarda. Devuelve (nuevas, actualizadas, sin_detalle).

    La lista inicial es obligatoria: si falla se lanza `ErrorNoticias` y no se toca lo guardado. El
    detalle (fecha y resumen) solo se pide de las noticias que aún no lo tienen; si falla, se guarda
    lo que trae la lista y se reintenta en la siguiente actualización.
    """
    tarjetas = leer_listado(leer(LISTADO))
    if not tarjetas:
        raise ErrorNoticias("El listado de noticias no tiene el formato esperado.")
    desplazamiento = POR_PAGINA
    while len(tarjetas) < maximo:
        try:
            pagina = leer_listado(leer(CARGAR_MAS.format(desplazamiento=desplazamiento)))
        except ErrorNoticias:
            break
        if not pagina:
            break
        tarjetas.extend(pagina)
        desplazamiento += POR_PAGINA
    vistos, unicas = set(), []
    for tarjeta in tarjetas:
        if tarjeta.id_externo not in vistos:
            vistos.add(tarjeta.id_externo)
            unicas.append(tarjeta)
    unicas = unicas[:maximo]

    guardadas = {n.id_externo: n for n in NoticiaComuna.objects.filter(id_externo__in=vistos)}
    nuevas = actualizadas = sin_detalle = 0
    for tarjeta in unicas:
        existente = guardadas.get(tarjeta.id_externo)
        direccion = f"{SITIO}noticia.php?id={tarjeta.id_externo}"
        fecha = existente.publicada_el if existente else None
        resumen = existente.resumen if existente else ""
        if fecha is None or not resumen:
            if leer is descargar:
                time.sleep(PAUSA_ENTRE_SOLICITUDES)  # el sitio es pequeño: no se le piden 24 páginas de golpe
            try:
                fecha_leida, resumen_leido = leer_noticia(leer(direccion))
                fecha, resumen = fecha_leida or fecha, resumen_leido or resumen
            except ErrorNoticias:
                pass
        if fecha is None:
            sin_detalle += 1
        valores = {
            "titulo": tarjeta.titulo[:300],
            "resumen": resumen,
            "publicada_el": fecha,
            "url": direccion,
            "imagen_url": tarjeta.imagen,
            "es_salud": es_de_salud(tarjeta.titulo, resumen),
        }
        _, creada = NoticiaComuna.objects.update_or_create(id_externo=tarjeta.id_externo, defaults=valores)
        if creada:
            nuevas += 1
        else:
            actualizadas += 1
    return nuevas, actualizadas, sin_detalle


def noticias_del_inicio(hoy=None):
    """(destacada, otras): la noticia de salud vigente más reciente, o la más reciente de todas, y las siguientes."""
    hoy = hoy or timezone.localdate()
    recientes = list(NoticiaComuna.objects.all()[:40])
    if not recientes:
        return None, []
    limite = hoy - timedelta(days=DIAS_VIGENCIA_DESTACADA_SALUD)
    destacada = next((n for n in recientes if n.es_salud and n.publicada_el and n.publicada_el >= limite), recientes[0])
    otras = [n for n in recientes if n.pk != destacada.pk][:NOTICIAS_EN_LISTA]
    return destacada, otras


def ultima_actualizacion():
    ultima = NoticiaComuna.objects.order_by("-obtenida_en").values_list("obtenida_en", flat=True).first()
    return timezone.localtime(ultima) if isinstance(ultima, datetime) else None
