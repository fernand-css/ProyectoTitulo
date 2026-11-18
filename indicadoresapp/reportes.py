"""Reportes descargables del panel de mermas (RF-13-05): Excel y PDF con cifras y gráficos.

Nunca llevan datos personales. Por diseño, los generadores reciben solo `DatosReporte`, que se arma con cifras
agregadas y textos fijos: ningún objeto `Paciente`, RUT, nombre ni identificador interno llega hasta aquí.
"""

from dataclasses import dataclass
from io import BytesIO

from django.utils import timezone

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def fecha_corta(fecha):
    return f"{fecha.day} {MESES[fecha.month - 1]} {fecha.year}"


def fecha_larga(fecha):
    return f"{fecha.day:02d}/{fecha.month:02d}/{fecha.year}"


@dataclass(frozen=True)
class DatosReporte:
    inicio: object
    fin: object
    tipo_texto: str
    por_semana: bool
    cifras: tuple        # ((texto, valor), ...)
    serie: tuple         # ((etiqueta, valor), ...)
    por_tipo: tuple
    por_cierre: tuple
    por_estado: tuple
    generado_en: object
    rol: str

    @property
    def nombre_base(self):
        return f"mermas_{self.inicio:%Y-%m-%d}_{self.fin:%Y-%m-%d}"

    @property
    def titulo_serie(self):
        return "Merma por semana (lunes a domingo)" if self.por_semana else "Merma por día"


def datos_desde(resumen, rol):
    """Solo cifras agregadas del resumen; el detalle por paciente se descarta aquí."""
    from .mermas import DESPACHO, EN_DESPACHO, SIN_RETIRAR, TARDE

    c = resumen.cifras
    if resumen.por_semana:
        serie = tuple((f"Semana del {fecha_corta(fecha)}", valor) for fecha, valor in resumen.serie)
    else:
        serie = tuple((fecha_corta(fecha), valor) for fecha, valor in resumen.serie)
    return DatosReporte(
        inicio=resumen.periodo.inicio, fin=resumen.periodo.fin, tipo_texto=resumen.periodo.tipo_texto,
        por_semana=resumen.por_semana,
        cifras=(
            ("Merma total (sin retirar + en despacho)", resumen.merma),
            ("Sin retirar", c[SIN_RETIRAR]),
            ("En despacho", c[EN_DESPACHO]),
            ("Retiradas tarde en farmacia", c[TARDE]),
            ("Entregadas por despacho", c[DESPACHO]),
        ),
        serie=serie,
        por_tipo=tuple((texto, valor) for _, texto, valor in resumen.por_tipo),
        por_cierre=tuple((texto, valor) for _, texto, valor in resumen.por_cierre),
        por_estado=tuple((texto, valor) for _, texto, valor in resumen.por_estado),
        generado_en=timezone.localtime(), rol=rol,
    )


def _encabezado(datos):
    return [
        ("Período", f"{fecha_larga(datos.inicio)} al {fecha_larga(datos.fin)}"),
        ("Tipo de paciente", datos.tipo_texto),
        ("Generado", f"{datos.generado_en:%d/%m/%Y %H:%M}"),
        ("Generado por", datos.rol),
        ("Fuente", "Recetas preparadas y no retiradas tras cerrar el turno; fecha de preparación."),
    ]


# Excel -------------------------------------------------------------------------------------------------------

def excel(datos):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Font

    libro = Workbook()
    resumen = libro.active
    resumen.title = "Resumen"
    hoja = libro.create_sheet("Datos")
    negrita = Font(bold=True)

    resumen["A1"] = "Panel de mermas · Farmacia CESFAM San Nicolás"
    resumen["A1"].font = Font(bold=True, size=14)
    fila = 3
    for texto, valor in _encabezado(datos):
        resumen.cell(row=fila, column=1, value=texto).font = negrita
        resumen.cell(row=fila, column=2, value=valor)
        fila += 1
    fila += 1
    resumen.cell(row=fila, column=1, value="Cifras").font = negrita
    fila += 1
    for texto, valor in datos.cifras:
        resumen.cell(row=fila, column=1, value=texto)
        resumen.cell(row=fila, column=2, value=valor)
        fila += 1
    resumen.column_dimensions["A"].width = 44
    resumen.column_dimensions["B"].width = 34

    # Cada tabla de «Datos» alimenta un gráfico nativo de la hoja «Resumen».
    tablas = (
        (datos.titulo_serie, "Período", datos.serie),
        ("Merma por tipo de paciente", "Tipo", datos.por_tipo),
        ("Merma por cómo cerró el turno", "Cierre", datos.por_cierre),
        ("Recuperadas frente a perdidas", "Estado", datos.por_estado),
    )
    columna, ancla_fila = 1, fila + 2
    for indice, (titulo, cabeza, valores) in enumerate(tablas):
        hoja.cell(row=1, column=columna, value=titulo).font = negrita
        hoja.cell(row=2, column=columna, value=cabeza).font = negrita
        hoja.cell(row=2, column=columna + 1, value="Recetas").font = negrita
        for desplazamiento, (texto, valor) in enumerate(valores, start=3):
            hoja.cell(row=desplazamiento, column=columna, value=texto)
            hoja.cell(row=desplazamiento, column=columna + 1, value=valor)
        hoja.column_dimensions[hoja.cell(row=1, column=columna).column_letter].width = 34
        if valores:
            grafico = BarChart()
            grafico.type = "col" if indice == 0 else "bar"
            grafico.title = titulo
            grafico.legend = None
            grafico.y_axis.title = "Recetas"
            grafico.add_data(Reference(hoja, min_col=columna + 1, min_row=2, max_row=len(valores) + 2), titles_from_data=True)
            grafico.set_categories(Reference(hoja, min_col=columna, min_row=3, max_row=len(valores) + 2))
            grafico.width, grafico.height = 22, 9
            resumen.add_chart(grafico, f"A{ancla_fila}")
            ancla_fila += 20
        columna += 3

    salida = BytesIO()
    libro.properties.title = f"Panel de mermas {fecha_larga(datos.inicio)} al {fecha_larga(datos.fin)}"
    libro.properties.creator = "Farmacia CESFAM San Nicolás"
    libro.save(salida)
    return salida.getvalue()


# PDF ---------------------------------------------------------------------------------------------------------

def _grafico_pdf(titulo, valores, ancho, columnas):
    from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors

    alto = 190 if columnas else max(90, 26 * len(valores) + 40)
    dibujo = Drawing(ancho, alto)
    grafico = VerticalBarChart() if columnas else HorizontalBarChart()
    grafico.x, grafico.y = (40, 40) if columnas else (190, 20)
    grafico.width = ancho - grafico.x - 20
    grafico.height = alto - grafico.y - 30
    grafico.data = [[valor for _, valor in valores] or [0]]
    etiquetas = [texto for texto, _ in valores] or [""]
    if columnas and len(etiquetas) > 12:
        paso = -(-len(etiquetas) // 8)
        etiquetas = [texto if i % paso == 0 else "" for i, texto in enumerate(etiquetas)]
    grafico.categoryAxis.categoryNames = etiquetas
    grafico.categoryAxis.labels.fontSize = 7 if columnas else 8
    if columnas:
        grafico.categoryAxis.labels.angle = 30
        grafico.categoryAxis.labels.boxAnchor = "ne"
    maximo = max([valor for _, valor in valores] + [1])
    grafico.valueAxis.valueMin = 0
    grafico.valueAxis.valueMax = maximo
    grafico.valueAxis.valueStep = max(1, -(-maximo // 4))
    grafico.valueAxis.labels.fontSize = 8
    grafico.bars[0].fillColor = colors.HexColor("#8a3b12")
    grafico.bars[0].strokeColor = None
    dibujo.add(grafico)
    dibujo.add(String(0, alto - 12, titulo, fontName="Helvetica-Bold", fontSize=10))
    return dibujo


def pdf(datos):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    salida = BytesIO()
    documento = SimpleDocTemplate(
        # Sin compresión, como el comprobante del tótem: el texto queda legible para verificar que no hay datos personales.
        salida, pagesize=letter, pageCompression=0, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title=f"Panel de mermas {fecha_larga(datos.inicio)} al {fecha_larga(datos.fin)}",
        author="Farmacia CESFAM San Nicolás", subject="Recetas preparadas y no retiradas", lang="es-CL",
    )
    estilos = getSampleStyleSheet()
    ancho = documento.width
    estilo_tabla = TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("GRID", (0, 1), (-1, -1), 0.25, colors.HexColor("#999999")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ])

    def tabla(cabeza, valores):
        filas = [list(cabeza)] + [[texto, str(valor)] for texto, valor in valores]
        t = Table(filas, colWidths=[ancho * 0.7, ancho * 0.3], repeatRows=1)
        t.setStyle(estilo_tabla)
        return t

    historia = [
        Paragraph("Panel de mermas · Farmacia CESFAM San Nicolás", estilos["Title"]),
        tabla(("Dato", "Valor"), _encabezado(datos)[:4]),
        Spacer(1, 0.3 * cm),
        Paragraph(_encabezado(datos)[4][1], estilos["Normal"]),
        Spacer(1, 0.4 * cm),
        Paragraph("Cifras", estilos["Heading2"]),
        tabla(("Cifra", "Recetas"), datos.cifras),
    ]
    graficos = (
        (datos.titulo_serie, "Período", datos.serie, True),
        ("Merma por tipo de paciente", "Tipo", datos.por_tipo, False),
        ("Merma por cómo cerró el turno", "Cierre", datos.por_cierre, False),
        ("Recuperadas frente a perdidas", "Estado", datos.por_estado, False),
    )
    for titulo, cabeza, valores, columnas in graficos:
        historia.append(Spacer(1, 0.5 * cm))
        historia.append(KeepTogether([_grafico_pdf(titulo, valores, ancho, columnas), Spacer(1, 0.2 * cm)]))
        historia.append(tabla((cabeza, "Recetas"), valores))
    documento.build(historia)
    return salida.getvalue()
