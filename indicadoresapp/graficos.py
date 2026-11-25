"""Gráficos del panel de mermas: se calculan aquí y la plantilla solo los dibuja.

Son SVG o HTML sin librerías y no reciben datos personales: solo cifras agregadas.

- Calendario: la merma de cada día con su cifra escrita; el tono ámbar sube con la cantidad. Los días que aún
  no llegan del mes en curso se ven «Aún no».
- Columnas (simples o apiladas): la geometría de `recetasapp/graficos.py`, con 2 px entre partes.
- Barras: una lista de partes con su ancho relativo a la mayor y su porcentaje.
- Barra al 100 %: lo que pasó con las recetas preparadas, con textura por parte además del color.
"""

from datetime import timedelta
from math import ceil

from recetasapp.graficos import _n, _ruta_columna, escala, porcentajes

from .periodos import MES_SERIE, SEMANA

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
MESES_LARGOS = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
                "Noviembre", "Diciembre")
DIAS_PLURAL = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos")
DIAS_CORTOS = (("L", "Lunes"), ("M", "Martes"), ("M", "Miércoles"), ("J", "Jueves"), ("V", "Viernes"),
               ("S", "Sábado"), ("D", "Domingo"))


def _nivel(valor, maximo):
    return 0 if not valor else min(5, max(1, ceil(5 * valor / maximo)))


def fecha_corta(fecha):
    return f"{fecha.day} {MESES[fecha.month - 1]}"


def etiqueta(fecha, granularidad):
    """Texto de una columna: «25 nov», «Semana del 3 nov» o «Noviembre 2026»."""
    if granularidad == SEMANA:
        return f"Semana del {fecha_corta(fecha)}"
    if granularidad == MES_SERIE:
        return f"{MESES_LARGOS[fecha.month - 1]} {fecha.year}"
    return fecha_corta(fecha)


def marca(fecha, granularidad):
    """Texto corto del eje horizontal."""
    if granularidad == MES_SERIE:
        return MESES[fecha.month - 1]
    return fecha_corta(fecha)


def calendario(serie, inicio, fin, hasta=None):
    """Semanas de lunes a domingo con la merma de cada día; los días fuera del período quedan vacíos.

    Con `hasta` (el último día del mes en curso), los días entre `fin` y `hasta` se marcan «Aún no».
    """
    valores = dict(serie)
    maximo = max(valores.values(), default=0)
    ultimo_dia = hasta or fin
    primero = inicio - timedelta(days=inicio.weekday())
    ultimo = ultimo_dia + timedelta(days=6 - ultimo_dia.weekday())
    semanas, semana, dia = [], [], primero
    while dia <= ultimo:
        if inicio <= dia <= fin:
            valor = valores.get(dia, 0)
            texto = fecha_corta(dia) if dia == inicio or dia.day == 1 else str(dia.day)
            semana.append({
                "fecha": dia, "etiqueta": texto, "valor": valor, "nivel": _nivel(valor, maximo),
                "fin_de_semana": dia.weekday() >= 5, "futuro": False,
                "tip": f"{DIAS_CORTOS[dia.weekday()][1]} {fecha_corta(dia)}: {valor} receta{'s' if valor != 1 else ''}",
            })
        elif fin < dia <= ultimo_dia:
            semana.append({"fecha": dia, "etiqueta": str(dia.day), "futuro": True,
                           "tip": f"{DIAS_CORTOS[dia.weekday()][1]} {fecha_corta(dia)}: aún no"})
        else:
            semana.append(None)
        if len(semana) == 7:
            semanas.append(semana)
            semana = []
        dia += timedelta(days=1)
    dia_maximo = next((fecha for fecha, valor in serie if valor == maximo), None) if maximo else None
    return {"semanas": semanas, "dias": DIAS_CORTOS, "maximo": maximo, "dia_maximo": dia_maximo,
            "con_futuro": hasta is not None and hasta > fin}


def frase_dia_semana(por_dia_semana, merma, dias):
    """«Los lunes suman 32 de las 87 recetas.»: solo con dos semanas o más y un día que destaque sin empate."""
    if dias < 14 or not merma:
        return ""
    maximo = max(por_dia_semana)
    if por_dia_semana.count(maximo) > 1:
        return ""
    dia = DIAS_PLURAL[por_dia_semana.index(maximo)]
    return f"Los {dia} suman {maximo} de las {merma} recetas."


def porcentaje_texto(parte, total):
    """Un decimal con coma y sin «,0» sobrante: cantidades iguales muestran el mismo porcentaje (33,3 y no 34/33)."""
    if not total:
        return "0"
    texto = f"{100 * parte / total:.1f}".replace(".", ",")
    return texto[:-2] if texto.endswith(",0") else texto


def barras(partes, ordenar=False):
    """`partes` es [(clave, texto, cantidad)]; cada barra mide en porcentaje de la mayor y lleva su porcentaje del total."""
    if ordenar:
        partes = sorted(partes, key=lambda parte: -parte[2])
    maximo = max((cantidad for _, _, cantidad in partes), default=0)
    total = sum(cantidad for _, _, cantidad in partes)
    return [{"clave": clave, "texto": texto, "cantidad": cantidad, "porcentaje": porcentaje_texto(cantidad, total),
             "ancho": f"{100 * cantidad / maximo:.1f}" if maximo else "0", "tramo": i}
            for i, (clave, texto, cantidad) in enumerate(partes)]


def division(partes):
    """Barra dividida en dos o más partes, con su porcentaje entero (suman 100)."""
    cuotas = porcentajes([cantidad for _, _, cantidad in partes])
    return [{"clave": clave, "texto": texto, "cantidad": cantidad, "porcentaje": cuota}
            for (clave, texto, cantidad), cuota in zip(partes, cuotas)]


def _rectangulo(x, y, ancho, alto):
    if alto <= 0:
        return ""
    return f"M{_n(x)} {_n(y)} H{_n(x + ancho)} V{_n(y + alto)} H{_n(x)} Z"


def columnas_apiladas(serie, claves, promedios=None, ancho=640, alto=260, margen=(16, 12, 32, 36), hueco=2):
    """`serie` es [(fecha, [valor por parte])]; las partes van de abajo hacia arriba en el orden de `claves`.

    Solo la parte de arriba lleva el extremo redondeado; entre partes queda un hueco de `hueco` px. `promedios`
    (opcional) va alineado con `serie` y se dibuja como línea sobre el total.
    """
    arriba, derecha, abajo, izquierda = margen
    n = len(serie)
    totales = [sum(valores) for _, valores in serie]
    promedios = promedios if promedios is not None else [None] * n
    techo, paso = escala(max(totales + [p for p in promedios if p is not None], default=0))
    util_x, util_y = ancho - izquierda - derecha, alto - arriba - abajo
    base = arriba + util_y
    ranura = util_x / n if n else float(util_x)
    grosor = min(max(ranura - 2, 1.0), 24.0)

    def alto_de(valor):
        return util_y * valor / techo

    columnas_ = []
    for i, (fecha, valores) in enumerate(serie):
        x = izquierda + ranura * (i + 0.5) - grosor / 2
        y = base
        visibles = [j for j, valor in enumerate(valores) if valor]
        partes = []
        for j, valor in enumerate(valores):
            if not valor:
                continue
            h = alto_de(valor)
            y_parte = y - h
            arriba_del_todo = j == visibles[-1]
            h_dibujo = h if arriba_del_todo or h <= hueco else h - hueco
            ruta = (_ruta_columna(x, y_parte, grosor, h) if arriba_del_todo
                    else _rectangulo(x, y - h_dibujo, grosor, h_dibujo))
            partes.append({"clave": claves[j], "valor": valor, "ruta": ruta})
            y = y_parte
        columnas_.append({"indice": i, "fecha": fecha, "valores": valores, "total": totales[i],
                          "promedio": promedios[i], "partes": partes,
                          "ranura_x": _n(izquierda + ranura * i), "ranura_ancho": _n(ranura)})

    def y_de(valor):
        return arriba + util_y * (1 - valor / techo)

    puntos = [(izquierda + ranura * (i + 0.5), y_de(p)) for i, p in enumerate(promedios) if p is not None]
    ruta_promedio = "M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in puntos) if len(puntos) > 1 else ""
    marcas_y = [{"y": _n(y_de(paso * k)), "etiqueta": paso * k} for k in range(techo // paso + 1)]
    elegidos = list(range(n)) if n <= 6 else sorted({round(i * (n - 1) / 5) for i in range(6)})
    marcas_x = [{"x": _n(izquierda + ranura * (i + 0.5)), "fecha": serie[i][0]} for i in elegidos]
    maximo = max(totales, default=0)
    return {
        "ancho": ancho, "alto": alto, "columnas": columnas_, "ruta_promedio": ruta_promedio,
        "marcas_x": marcas_x, "marcas_y": marcas_y,
        "izquierda": _n(izquierda), "derecha": _n(ancho - derecha),
        "zona": {"x": _n(izquierda), "y": _n(arriba), "ancho": _n(util_x), "alto": _n(util_y)},
        "total": sum(totales), "maximo": maximo,
        "dia_maximo": next((fecha for (fecha, _), total in zip(serie, totales) if total == maximo), None) if maximo else None,
    }


def barra_100(partes):
    """[(clave, texto, cantidad)] como partes de una barra al 100 %, con su porcentaje entero (suman 100)."""
    cuotas = porcentajes([cantidad for _, _, cantidad in partes])
    return [{"clave": clave, "texto": texto, "cantidad": cantidad, "porcentaje": cuota, "visible": bool(cantidad),
             "orden": i + 1}
            for i, ((clave, texto, cantidad), cuota) in enumerate(zip(partes, cuotas))]

