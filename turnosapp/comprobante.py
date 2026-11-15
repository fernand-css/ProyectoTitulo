"""Comprobante del número en PDF vertical (1080x1920 pt), generado al momento y sin guardarse.

RF-04-08 (enmienda del 2026-11-15). Recibe solo los datos visibles del número: código, letra,
fecha, hora, frase de espera y aviso de renovación. Nunca recibe ni dibuja RUT, nombre, recetas ni
el motivo de la preferencia.

Fuentes: las del proyecto están en woff2, formato que ReportLab no lee; se usan Helvetica y
Helvetica-Bold (fuentes estándar del PDF, sin incrustar). ReportLab no genera PDF etiquetado: el
texto accesible queda en el HTML que rodea al comprobante.
"""
from io import BytesIO

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen.canvas import Canvas

ANCHO, ALTO = 1080, 1920
MARGEN = 60

FONDO = HexColor("#f3efe6")
TINTA = HexColor("#182c42")
LOGO = HexColor("#244bc3")
CAJA_ESPERA = HexColor("#eef2f8")
AVISO_FONDO = HexColor("#fff4d6")
AVISO_BORDE = HexColor("#8a5a00")
COLINAS = (HexColor("#d9e3cf"), HexColor("#a9bf96"), HexColor("#6f8f5c"))

# Blanco sobre cada color supera 4,5:1 (P 7,1; G 6,7; C 5,5; U 6,6).
LETRAS = {
    "P": (HexColor("#6d28d9"), "P · Preferencial"),
    "G": (HexColor("#1d4ed8"), "G · General"),
    "C": (HexColor("#0f766e"), "C · Crónicos"),
    "U": (HexColor("#b42318"), "U · Urgencia"),
}

PASOS = (
    "Toma asiento en la sala de espera.",
    "Te llamaremos por tu número, en la pantalla y por voz.",
    "Acércate a la ventanilla que indique la pantalla.",
)
# Número nuevo de urgencia: pasos propios, con el código que se anunciará.
PASOS_URGENCIA = (
    "Quédate cerca de las ventanillas.",
    "Te llamaremos antes que a los demás números.",
    "Escucha y mira la pantalla: dirá {codigo} y la ventanilla.",
)
NORMAL, NEGRITA = "Helvetica", "Helvetica-Bold"
ACENTO = HexColor("#244bc3")


def _texto(lienzo, x, y, texto, fuente, tamano, color=TINTA):
    lienzo.setFillColor(color)
    lienzo.setFont(fuente, tamano)
    lienzo.drawString(x, y, texto)


def _centrado(lienzo, y, texto, fuente, tamano, color=TINTA):
    lienzo.setFillColor(color)
    lienzo.setFont(fuente, tamano)
    lienzo.drawCentredString(ANCHO / 2, y, texto)


def _colinas(lienzo):
    for color, (base, alto1, alto2) in zip(COLINAS, ((250, 320, 200), (170, 120, 230), (90, 150, 60))):
        trazo = lienzo.beginPath()
        trazo.moveTo(0, 0)
        trazo.lineTo(0, base)
        trazo.curveTo(ANCHO * 0.3, alto1, ANCHO * 0.6, alto2, ANCHO, base - 20)
        trazo.lineTo(ANCHO, 0)
        trazo.close()
        lienzo.setFillColor(color)
        lienzo.drawPath(trazo, stroke=0, fill=1)


def _encabezado(lienzo):
    alto = 210
    lienzo.setFillColor(TINTA)
    lienzo.rect(0, ALTO - alto, ANCHO, alto, stroke=0, fill=1)
    lado, x, y = 120, MARGEN, ALTO - 165
    lienzo.setFillColor(LOGO)
    lienzo.roundRect(x, y, lado, lado, 26, stroke=0, fill=1)
    lienzo.setFillColor(white)
    grosor, largo = 30, 76
    lienzo.rect(x + (lado - grosor) / 2, y + (lado - largo) / 2, grosor, largo, stroke=0, fill=1)
    lienzo.rect(x + (lado - largo) / 2, y + (lado - grosor) / 2, largo, grosor, stroke=0, fill=1)
    _texto(lienzo, x + lado + 40, ALTO - 95, "CESFAM San Nicolás", NEGRITA, 58, white)
    _texto(lienzo, x + lado + 40, ALTO - 150, "Unidad de Farmacia", NORMAL, 40, white)


def _alto_parrafo(texto, fuente, tamano, ancho, interlinea):
    return len(simpleSplit(texto, fuente, tamano, ancho)) * interlinea


def _parrafo(lienzo, x, y, texto, fuente, tamano, ancho, interlinea, color=TINTA):
    """Dibuja desde la línea base `y` hacia abajo y devuelve la `y` siguiente."""
    for linea in simpleSplit(texto, fuente, tamano, ancho):
        _texto(lienzo, x, y, linea, fuente, tamano, color)
        y -= interlinea
    return y


def generar_comprobante(datos):
    """Devuelve los bytes del PDF. `datos`: codigo, letra, fecha, hora, espera, renovacion y, opcional,
    `reemplaza` (código anterior, spec 10: el personal reclasificó el turno o lo marcó urgente)."""
    color, categoria = LETRAS.get(datos["letra"], LETRAS["G"])
    salida = BytesIO()
    # Sin compresión de página: el PDF es liviano y permite comprobar su texto en las pruebas.
    lienzo = Canvas(salida, pagesize=(ANCHO, ALTO), pageCompression=0)
    lienzo.setTitle("Tu número de atención")
    lienzo.setAuthor("")
    lienzo.setSubject("")
    lienzo.setCreator("")

    lienzo.setFillColor(FONDO)
    lienzo.rect(0, 0, ANCHO, ALTO, stroke=0, fill=1)
    _colinas(lienzo)
    _encabezado(lienzo)

    interior = ANCHO - 2 * MARGEN - 80  # ancho útil dentro de la tarjeta
    x_texto = MARGEN + 40
    reemplaza = datos.get("reemplaza")
    # Número nuevo: el recuadro de espera pasa a decir a qué número reemplaza.
    texto_caja = f"Reemplaza a tu número anterior, {reemplaza}." if reemplaza else datos["espera"]
    pasos = (tuple(paso.format(codigo=datos["codigo"]) for paso in PASOS_URGENCIA)
             if reemplaza and datos["letra"] == "U" else PASOS)
    alto_espera = _alto_parrafo(texto_caja, NEGRITA, 36, interior - 140, 46) + 56
    alto_aviso = 180 if datos.get("renovacion") else 0
    alto_pasos = sum(_alto_parrafo(paso, NORMAL, 34, interior - 90, 42) + 36 for paso in pasos)
    superior = 420
    alto_tarjeta = superior + 40 + 180 + alto_espera + 30 + alto_aviso + (30 if alto_aviso else 0) + 80 + alto_pasos + 90
    tope = ALTO - 250
    base = tope - alto_tarjeta

    # Tarjeta: sombra suave, cuerpo blanco y parte superior con el color de la letra.
    lienzo.setFillColor(HexColor("#e2dccd"))
    lienzo.roundRect(MARGEN + 6, base - 10, ANCHO - 2 * MARGEN, alto_tarjeta, 40, stroke=0, fill=1)
    lienzo.setFillColor(white)
    lienzo.roundRect(MARGEN, base, ANCHO - 2 * MARGEN, alto_tarjeta, 40, stroke=0, fill=1)
    lienzo.setFillColor(color)
    lienzo.roundRect(MARGEN, tope - superior, ANCHO - 2 * MARGEN, superior, 40, stroke=0, fill=1)
    lienzo.rect(MARGEN, tope - superior, ANCHO - 2 * MARGEN, 50, stroke=0, fill=1)

    _centrado(lienzo, tope - 85, "Tu nuevo número" if reemplaza else "Tu número de atención", NEGRITA, 48, white)
    tamano = 210
    while lienzo.stringWidth(datos["codigo"], NEGRITA, tamano) > interior and tamano > 120:
        tamano -= 10
    _centrado(lienzo, tope - 275, datos["codigo"], NEGRITA, tamano, white)
    ancho_pastilla = lienzo.stringWidth(categoria, NEGRITA, 44) + 80
    lienzo.setFillColor(white)
    lienzo.roundRect((ANCHO - ancho_pastilla) / 2, tope - 380, ancho_pastilla, 76, 38, stroke=0, fill=1)
    _centrado(lienzo, tope - 357, categoria, NEGRITA, 44, color)

    # Línea punteada tipo boleto, con muescas a los lados.
    y = tope - superior - 40
    lienzo.setStrokeColor(TINTA)
    lienzo.setLineWidth(4)
    lienzo.setDash(18, 14)
    lienzo.line(MARGEN + 40, y, ANCHO - MARGEN - 40, y)
    lienzo.setDash()
    lienzo.setFillColor(FONDO)
    lienzo.circle(MARGEN, y, 24, stroke=0, fill=1)
    lienzo.circle(ANCHO - MARGEN, y, 24, stroke=0, fill=1)

    # Fecha y hora de llegada.
    y -= 70
    mitad = ANCHO / 2 + 20
    _texto(lienzo, x_texto, y, "Fecha", NORMAL, 34)
    _texto(lienzo, mitad, y, "Hora del cambio" if reemplaza else "Hora de llegada", NORMAL, 34)
    y -= 66
    _texto(lienzo, x_texto, y, datos["fecha"], NEGRITA, 56)
    _texto(lienzo, mitad, y, datos["hora"], NEGRITA, 56)

    # Frase de espera (spec 07).
    y -= 44
    lienzo.setFillColor(CAJA_ESPERA)
    lienzo.roundRect(x_texto, y - alto_espera, interior, alto_espera, 24, stroke=0, fill=1)
    centro_icono = (x_texto + 58, y - alto_espera / 2)
    (_icono_flecha if reemplaza else _icono_reloj)(lienzo, *centro_icono)
    lineas = len(simpleSplit(texto_caja, NEGRITA, 36, interior - 140))
    _parrafo(lienzo, x_texto + 110, y - (alto_espera - lineas * 46) / 2 - 33, texto_caja, NEGRITA, 36, interior - 140, 46)
    y -= alto_espera + 30

    if alto_aviso:
        lienzo.setFillColor(AVISO_FONDO)
        lienzo.setStrokeColor(AVISO_BORDE)
        lienzo.setLineWidth(5)
        lienzo.roundRect(x_texto, y - alto_aviso, interior, alto_aviso, 24, stroke=1, fill=1)
        # Ícono de aviso: no depende solo del color.
        cx, cy = x_texto + 62, y - 64
        lienzo.setFillColor(AVISO_BORDE)
        lienzo.circle(cx, cy, 32, stroke=0, fill=1)
        _texto(lienzo, cx - 7, cy - 17, "!", NEGRITA, 50, white)
        _texto(lienzo, x_texto + 115, y - 80, "Necesitas renovar tu receta", NEGRITA, 44)
        _parrafo(lienzo, x_texto + 115, y - 126,
                 "Te atenderemos igual en la ventanilla. Allí te dirán cómo pedir la renovación.",
                 NORMAL, 30, interior - 145, 38)
        y -= alto_aviso + 30

    # Qué hacer ahora.
    y -= 50
    _texto(lienzo, x_texto, y, "Qué hacer ahora", NEGRITA, 46)
    y -= 30
    for numero, paso in enumerate(pasos, start=1):
        y -= 36 + 6
        lienzo.setFillColor(TINTA)
        lienzo.circle(x_texto + 28, y + 12, 28, stroke=0, fill=1)
        _centrado_en(lienzo, x_texto + 28, y, str(numero))
        y = _parrafo(lienzo, x_texto + 90, y, paso, NORMAL, 34, interior - 90, 42) + 6
    y -= 20
    if not reemplaza:
        _texto(lienzo, x_texto, y - 20, "Si quieres recordarlo, sácale una foto a esta pantalla.", NORMAL, 32)

    lienzo.showPage()
    lienzo.save()
    return salida.getvalue()


def _centrado_en(lienzo, x, y, texto):
    lienzo.setFillColor(white)
    lienzo.setFont(NEGRITA, 34)
    lienzo.drawCentredString(x, y, texto)


def _icono_reloj(lienzo, x, y):
    """Reloj de trazo, decorativo: el texto del recuadro dice lo mismo."""
    lienzo.setStrokeColor(ACENTO)
    lienzo.setLineWidth(5)
    lienzo.circle(x, y, 26, stroke=1, fill=0)
    lienzo.line(x, y, x, y + 15)
    lienzo.line(x, y, x + 11, y - 8)


def _icono_flecha(lienzo, x, y):
    lienzo.setStrokeColor(ACENTO)
    lienzo.setLineWidth(6)
    lienzo.setLineCap(1)
    lienzo.line(x - 24, y, x + 20, y)
    lienzo.line(x + 4, y + 16, x + 20, y)
    lienzo.line(x + 4, y - 16, x + 20, y)
    lienzo.setLineCap(0)
