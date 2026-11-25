"""Descargas del panel de mermas (RF-13-21): Excel, CSV y PDF con las cifras del dashboard.

Nunca llevan datos personales ni el texto libre de los motivos. Por diseño, los generadores reciben solo
`DatosReporte`, que se arma desde el `Tablero` con cifras agregadas y textos fijos: ningún objeto `Paciente`,
RUT, nombre ni identificador interno llega hasta aquí.
"""

import csv
from dataclasses import dataclass
from io import BytesIO, StringIO

from . import canales as canales_mod
from . import graficos
from .tablero import decimal

ENCABEZADOS_LEGIBLES = {
    "fecha": "Fecha",
    "farmacia_entregadas_atencion_o_ficha": "Farmacia: entregadas en la atención o desde la ficha",
    "farmacia_retiradas_despues": "Farmacia: retiradas después",
    "farmacia_no_entregadas": "Farmacia: no entregadas (fecha del turno)",
    "domicilio_entregadas": "Domicilio: entregadas",
    "domicilio_no_entregadas": "Domicilio: no entregadas",
    "merma": "Merma (fecha de preparación)",
    "turnos_emitidos": "Turnos emitidos",
    "turnos_ausentes": "Turnos ausentes",
}


def fecha_larga(fecha):
    return f"{fecha.day:02d}/{fecha.month:02d}/{fecha.year}"


def _legible(columna):
    if columna in ENCABEZADOS_LEGIBLES:
        return ENCABEZADOS_LEGIBLES[columna]
    canal, _, resto = columna.partition("_")
    return f"{canal.capitalize()}, motivo: {resto.replace('_', ' ')}"


@dataclass(frozen=True)
class DatosReporte:
    inicio: object
    fin: object
    titulo_periodo: str
    tipo_texto: str
    generado_en: object
    rol: str
    cifras: tuple          # ((texto, valor, detalle, comparación), ...)
    canales: tuple         # ((canal, entregadas, no entregadas, total, % entregado), ...) con la subfila
    motivos_farmacia: tuple
    motivos_domicilio: tuple
    preparadas: tuple      # ((texto, cantidad, porcentaje), ...)
    titulo_serie: str
    serie: tuple           # ((etiqueta, merma), ...)
    por_tipo: tuple
    espera: tuple
    columnas: tuple        # encabezados del CSV
    dias: tuple            # filas del CSV
    horas: tuple
    ausentes: tuple        # ((día, ((emitidos, ausentes), ...)), ...)

    @property
    def nombre_base(self):
        return f"mermas_{self.inicio:%Y-%m-%d}_{self.fin:%Y-%m-%d}"


def _porcentaje(parte, total):
    return f"{decimal(100 * parte / total)} %" if total else "—"


def datos_desde(tablero, rol):
    """Solo cifras agregadas del tablero; ni pacientes ni texto libre."""
    from . import mermas

    periodo, resumen, canales, ausentes = tablero.periodo, tablero.resumen, tablero.canales, tablero.ausentes
    filas_canal = (
        ("Farmacia", canales.farmacia_entregadas, canales.farmacia_no_entregadas, canales.farmacia_total,
         _porcentaje(canales.farmacia_entregadas, canales.farmacia_total)),
        ("  de ellas, retiradas después", "", canales.farmacia_retiradas_despues, "", ""),
        ("Domicilio", canales.domicilio_entregadas, canales.domicilio_no_entregadas, canales.domicilio_total,
         _porcentaje(canales.domicilio_entregadas, canales.domicilio_total)),
        ("Total", canales.entregadas, canales.no_entregadas, canales.total,
         _porcentaje(canales.entregadas, canales.total)),
    )
    preparadas = graficos.barra_100(partes_preparadas(resumen))
    columnas = canales_mod.columnas_csv()
    dias = tuple(
        tuple(canales_mod.fila_csv(fecha, dia, resumen.merma_por_dia.get(fecha, 0), *ausentes.por_dia.get(fecha, (0, 0))))
        for fecha, dia in canales.por_dia.items()
    )
    granularidad = periodo.granularidad
    titulo_serie = {"dia": "Merma por día", "semana": "Merma por semana (lunes a domingo)", "mes": "Merma por mes"}[granularidad]
    return DatosReporte(
        inicio=periodo.inicio, fin=periodo.fin, titulo_periodo=periodo.titulo, tipo_texto=periodo.tipo_texto,
        generado_en=tablero.generado_en, rol=rol,
        cifras=tuple((c.texto, c.valor, c.detalle, c.comparacion) for c in tablero.cifras),
        canales=filas_canal,
        motivos_farmacia=tuple((texto, cantidad) for _, texto, cantidad in canales.motivos_farmacia),
        motivos_domicilio=tuple((texto, cantidad) for _, texto, cantidad in canales.motivos_domicilio),
        preparadas=tuple((p["texto"], p["cantidad"], p["porcentaje"]) for p in preparadas),
        titulo_serie=titulo_serie,
        serie=tuple((graficos.etiqueta(fecha, granularidad), valor) for fecha, valor in resumen.serie),
        por_tipo=tuple((texto, valor) for _, texto, valor in resumen.por_tipo),
        espera=tuple(resumen.espera) if resumen.cifras[mermas.SIN_RETIRAR] else (),
        columnas=tuple(columnas), dias=dias, horas=tuple(ausentes.horas),
        ausentes=tuple((fila["dia"], tuple((c["emitidos"], c["ausentes"]) for c in fila["celdas"]))
                       for fila in ausentes.filas),
    )


def partes_preparadas(resumen):
    """RF-13-18: las cinco partes de lo que pasó con las recetas preparadas, en su orden."""
    from . import mermas

    c = resumen.cifras
    return [
        ("en_atencion", "Entregadas en la atención", resumen.en_atencion),
        (mermas.TARDE, "Retiradas después", c[mermas.TARDE]),
        (mermas.DESPACHO, "Entregadas por despacho", c[mermas.DESPACHO]),
        (mermas.EN_DESPACHO, "En despacho", c[mermas.EN_DESPACHO]),
        (mermas.SIN_RETIRAR, "Sin retirar", c[mermas.SIN_RETIRAR]),
    ]


def _encabezado(datos):
    return [
        ("Período", f"{datos.titulo_periodo} ({fecha_larga(datos.inicio)} al {fecha_larga(datos.fin)})"),
        ("Tipo de paciente", datos.tipo_texto),
        ("Generado", f"{datos.generado_en:%d/%m/%Y %H:%M}"),
        ("Generado por", datos.rol),
    ]


NOTA_FECHAS = ("Fechas: farmacia por fecha del turno (no entregadas) o de la entrega; domicilio por fecha de la visita; "
               "merma por fecha de preparación. Motivos de domicilio en visitas; el resto, en recetas.")


# CSV ---------------------------------------------------------------------------------------------------------

def csv_por_dia(datos):
    """Una fila por día, «;» y UTF-8 con BOM, para que Excel en español lo abra en columnas y con tildes."""
    salida = StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(datos.columnas)
    escritor.writerows(datos.dias)
    return ("﻿" + salida.getvalue()).encode("utf-8")


# Excel -------------------------------------------------------------------------------------------------------

def excel(datos):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Font

    libro = Workbook()
    resumen = libro.active
    resumen.title = "Resumen"
    datos_hoja = libro.create_sheet("Datos de gráficos")
    por_dia = libro.create_sheet("Por día")
    ausentes = libro.create_sheet("Ausentes por hora")
    negrita = Font(bold=True)

    resumen["A1"] = "Mermas y entregas · Farmacia CESFAM San Nicolás"
    resumen["A1"].font = Font(bold=True, size=14)
    fila = 3
    for texto, valor in _encabezado(datos):
        resumen.cell(row=fila, column=1, value=texto).font = negrita
        resumen.cell(row=fila, column=2, value=valor)
        fila += 1
    resumen.cell(row=fila, column=1, value=NOTA_FECHAS)
    fila += 2

    def tabla(titulo, cabeza, filas):
        nonlocal fila
        resumen.cell(row=fila, column=1, value=titulo).font = negrita
        fila += 1
        for columna, texto in enumerate(cabeza, start=1):
            resumen.cell(row=fila, column=columna, value=texto).font = negrita
        fila += 1
        for valores in filas:
            for columna, valor in enumerate(valores, start=1):
                resumen.cell(row=fila, column=columna, value=valor)
            fila += 1
        fila += 1

    tabla("Cifras clave", ("Cifra", "Valor", "Detalle", "Comparación"), datos.cifras)
    tabla("Entregas por canal (recetas)", ("Canal", "Entregadas", "No entregadas", "Total", "% entregado"), datos.canales)
    for columna, ancho in zip("ABCDE", (40, 16, 44, 44, 14)):
        resumen.column_dimensions[columna].width = ancho

    # Cada tabla de «Datos de gráficos» alimenta un gráfico nativo de la hoja «Resumen».
    graficos_ = (
        ("Motivos de no entrega en farmacia (recetas)", "Motivo", datos.motivos_farmacia, "bar"),
        ("Motivos de no entrega a domicilio (visitas)", "Motivo", datos.motivos_domicilio, "bar"),
        ("Qué pasó con las recetas preparadas", "Parte", tuple((t, c) for t, c, _ in datos.preparadas), "bar"),
        (datos.titulo_serie, "Período", datos.serie, "col"),
        ("Merma por tipo de paciente", "Tipo", datos.por_tipo, "bar"),
    )
    columna, ancla = 1, fila + 1
    for titulo, cabeza, valores, forma in graficos_:
        datos_hoja.cell(row=1, column=columna, value=titulo).font = negrita
        datos_hoja.cell(row=2, column=columna, value=cabeza).font = negrita
        datos_hoja.cell(row=2, column=columna + 1, value="Cantidad").font = negrita
        for desplazamiento, (texto, valor) in enumerate(valores, start=3):
            datos_hoja.cell(row=desplazamiento, column=columna, value=texto)
            datos_hoja.cell(row=desplazamiento, column=columna + 1, value=valor)
        datos_hoja.column_dimensions[datos_hoja.cell(row=1, column=columna).column_letter].width = 40
        if valores:
            grafico = BarChart()
            grafico.type = forma
            grafico.title = titulo
            grafico.legend = None
            grafico.add_data(Reference(datos_hoja, min_col=columna + 1, min_row=2, max_row=len(valores) + 2),
                             titles_from_data=True)
            grafico.set_categories(Reference(datos_hoja, min_col=columna, min_row=3, max_row=len(valores) + 2))
            grafico.width, grafico.height = 22, 9
            resumen.add_chart(grafico, f"A{ancla}")
            ancla += 20
        columna += 3

    for columna, nombre in enumerate(datos.columnas, start=1):
        celda = por_dia.cell(row=1, column=columna, value=_legible(nombre))
        celda.font = negrita
        por_dia.column_dimensions[celda.column_letter].width = 18
    for numero, valores in enumerate(datos.dias, start=2):
        for columna, valor in enumerate(valores, start=1):
            por_dia.cell(row=numero, column=columna, value=valor)

    ausentes.cell(row=1, column=1, value="Turnos ausentes por día y hora de emisión (ausentes de emitidos)").font = negrita
    ausentes.cell(row=2, column=1, value="Día").font = negrita
    for columna, hora in enumerate(datos.horas, start=2):
        ausentes.cell(row=2, column=columna, value=f"{hora}:00").font = negrita
    for numero, (dia, celdas) in enumerate(datos.ausentes, start=3):
        ausentes.cell(row=numero, column=1, value=dia)
        for columna, (emitidos, cuantos) in enumerate(celdas, start=2):
            ausentes.cell(row=numero, column=columna, value=f"{cuantos} de {emitidos}" if emitidos else "")

    salida = BytesIO()
    libro.properties.title = f"Mermas y entregas {fecha_larga(datos.inicio)} al {fecha_larga(datos.fin)}"
    libro.properties.creator = "Farmacia CESFAM San Nicolás"
    libro.save(salida)
    return salida.getvalue()


# PDF ---------------------------------------------------------------------------------------------------------

def _grafico_pdf(titulo, valores, ancho, columnas):
    from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors

    alto = 190 if columnas else max(90, 22 * len(valores) + 40)
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
        salida, pagesize=letter, pageCompression=0, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
        bottomMargin=1.8 * cm, title=f"Mermas y entregas {fecha_larga(datos.inicio)} al {fecha_larga(datos.fin)}",
        author="Farmacia CESFAM San Nicolás", subject="Mermas, entregas por canal y motivos", lang="es-CL",
    )
    estilos = getSampleStyleSheet()
    ancho = documento.width
    estilo_tabla = TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("GRID", (0, 1), (-1, -1), 0.25, colors.HexColor("#999999")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])

    def tabla(cabeza, filas, anchos):
        celdas = [list(cabeza)] + [[str(valor) for valor in fila] for fila in filas]
        t = Table(celdas, colWidths=[ancho * a for a in anchos], repeatRows=1)
        t.setStyle(estilo_tabla)
        return t

    normal = estilos["Normal"]
    historia = [
        Paragraph("Mermas y entregas · Farmacia CESFAM San Nicolás", estilos["Title"]),
        tabla(("Dato", "Valor"), _encabezado(datos), (0.3, 0.7)),
        Spacer(1, 0.2 * cm), Paragraph(NOTA_FECHAS, normal), Spacer(1, 0.3 * cm),
        Paragraph("Cifras clave", estilos["Heading2"]),
        Table([[Paragraph(f"<b>{t}</b>", normal), Paragraph(v, normal), Paragraph(d, normal), Paragraph(c, normal)]
               for t, v, d, c in datos.cifras], colWidths=[ancho * 0.24, ancho * 0.12, ancho * 0.32, ancho * 0.32],
              style=TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#999999")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP")])),
        Paragraph("Entregas por canal (recetas)", estilos["Heading2"]),
        tabla(("Canal", "Entregadas", "No entregadas", "Total", "% entregado"), datos.canales,
              (0.36, 0.16, 0.16, 0.16, 0.16)),
    ]
    graficos_ = (
        ("Motivos de no entrega en farmacia (recetas)", "Motivo", datos.motivos_farmacia, False),
        ("Motivos de no entrega a domicilio (visitas)", "Motivo", datos.motivos_domicilio, False),
        (datos.titulo_serie, "Período", datos.serie, True),
        ("Qué pasó con las recetas preparadas", "Parte", tuple((t, c) for t, c, _ in datos.preparadas), False),
    )
    for titulo, cabeza, valores, columnas in graficos_:
        historia.append(Spacer(1, 0.4 * cm))
        historia.append(KeepTogether([_grafico_pdf(titulo, valores, ancho, columnas), Spacer(1, 0.2 * cm)]))
        if titulo == "Qué pasó con las recetas preparadas":
            historia.append(tabla((cabeza, "Recetas", "%"), [(t, c, f"{p} %") for t, c, p in datos.preparadas],
                                  (0.6, 0.2, 0.2)))
        else:
            historia.append(tabla((cabeza, "Cantidad"), valores, (0.7, 0.3)))
    documento.build(historia)
    return salida.getvalue()

