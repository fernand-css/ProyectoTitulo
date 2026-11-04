"""Geometría de los gráficos de Recetas: se calcula aquí y las plantillas solo la dibujan.

Los gráficos son SVG y HTML sin librerías (el sistema no puede depender de un CDN). Todo número que
termina en un atributo SVG sale ya formateado como texto con punto decimal: con la configuración
regional es-cl, Django escribiría la coma y el atributo quedaría inválido.

Formas: columnas con promedio móvil (entregas por día), tendencia mínima para las cifras, barra
segmentada (situación de las recetas) y mapa de calor de calendario (vencimientos).
"""

from datetime import timedelta
from math import ceil


def _n(valor):
    """Número para un atributo SVG: punto decimal y sin ceros sobrantes."""
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return texto or "0"


def porcentajes(cantidades):
    """Porcentajes enteros que suman 100 (método del mayor resto); todo cero si no hay nada."""
    total = sum(cantidades)
    if total <= 0:
        return [0] * len(cantidades)
    brutos = [100 * cantidad / total for cantidad in cantidades]
    base = [int(bruto) for bruto in brutos]
    faltan = 100 - sum(base)
    por_resto = sorted(range(len(brutos)), key=lambda i: (brutos[i] - base[i], -i), reverse=True)
    for i in por_resto[:faltan]:
        base[i] += 1
    return base


def escala(maximo):
    """Eje vertical: `(techo, paso)` con paso de 1, 2 o 5 por potencia de 10.

    Elige el paso más chico con el que bastan cuatro intervalos, y el techo es el primer múltiplo del paso
    que alcanza el máximo: con máximo 1 el eje llega a 1 y no a 4, así que la columna no queda enana.
    """
    maximo = max(int(maximo), 1)
    potencia = 1
    while True:
        for factor in (1, 2, 5):
            paso = factor * potencia
            if ceil(maximo / paso) <= 4:
                return paso * ceil(maximo / paso), paso
        potencia *= 10


def promedio_movil(valores, ventana=7):
    """Promedio de cada día con los `ventana` días que terminan en él; los primeros días no tienen (`None`)."""
    resultado = [None] * min(ventana - 1, len(valores))
    for i in range(ventana - 1, len(valores)):
        resultado.append(sum(valores[i - ventana + 1:i + 1]) / ventana)
    return resultado


def _ruta_columna(x, y, ancho, alto, radio=4.0):
    """Columna con el extremo del dato redondeado (4 px) y la base recta, anclada al eje."""
    if alto <= 0:
        return ""
    r = min(radio, ancho / 2, alto)
    base = y + alto
    return (f"M{_n(x)} {_n(base)} V{_n(y + r)} Q{_n(x)} {_n(y)} {_n(x + r)} {_n(y)} H{_n(x + ancho - r)} "
            f"Q{_n(x + ancho)} {_n(y)} {_n(x + ancho)} {_n(y + r)} V{_n(base)} Z")


def columnas(serie, promedios=None, ancho=640, alto=300, margen=(16, 12, 32, 36)):
    """Serie de `(fecha, valor)` como columnas de hasta 24 px con 2 px de hueco, y su promedio móvil como línea.

    `promedios` va alineado con `serie` (un número o `None` por día). `margen` es (arriba, derecha, abajo,
    izquierda). Cada columna lleva su ranura completa (`ranura_x`, `ranura_ancho`) para detectar el cursor
    aunque la columna mida 4 px, y `zona` es el área del gráfico donde se mide el puntero.
    """
    arriba, derecha, abajo, izquierda = margen
    n = len(serie)
    valores = [valor for _, valor in serie]
    promedios = promedios if promedios is not None else [None] * n
    techo, paso = escala(max(valores + [p for p in promedios if p is not None], default=0))
    util_x, util_y = ancho - izquierda - derecha, alto - arriba - abajo
    base = arriba + util_y
    ranura = util_x / n if n else float(util_x)
    grosor = min(max(ranura - 2, 1.0), 24.0)

    def y_de(valor):
        return arriba + util_y * (1 - valor / techo)

    columnas_ = []
    for i, (fecha, valor) in enumerate(serie):
        centro = izquierda + ranura * (i + 0.5)
        x, y = centro - grosor / 2, y_de(valor)
        columnas_.append({
            "indice": i, "fecha": fecha, "valor": valor, "promedio": promedios[i],
            "ruta": _ruta_columna(x, y, grosor, base - y),
            "ranura_x": _n(izquierda + ranura * i), "ranura_ancho": _n(ranura),
        })

    puntos = [(izquierda + ranura * (i + 0.5), y_de(p)) for i, p in enumerate(promedios) if p is not None]
    ruta_promedio = "M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in puntos) if len(puntos) > 1 else ""

    marcas_y = [{"y": _n(y_de(paso * k)), "etiqueta": paso * k} for k in range(techo // paso + 1)]
    # Entre 3 y 6 fechas en el eje, siempre la primera y la última.
    elegidos = list(range(n)) if n <= 6 else sorted({round(i * (n - 1) / 5) for i in range(6)})
    marcas_x = [{"x": _n(izquierda + ranura * (i + 0.5)), "fecha": serie[i][0]} for i in elegidos]
    maximo = max(valores, default=0)
    return {
        "ancho": ancho, "alto": alto, "columnas": columnas_, "ruta_promedio": ruta_promedio,
        "marcas_x": marcas_x, "marcas_y": marcas_y,
        "izquierda": _n(izquierda), "derecha": _n(ancho - derecha),
        "zona": {"x": _n(izquierda), "y": _n(arriba), "ancho": _n(util_x), "alto": _n(util_y)},
        "total": sum(valores), "maximo": maximo,
        "dia_maximo": next((fecha for fecha, valor in serie if valor == maximo), None) if maximo else None,
        "ultimo_promedio": next((p for p in reversed(promedios) if p is not None), None),
        "n": n,
    }


def tendencia(valores, ancho=96, alto=32, margen=4):
    """Línea mínima de una serie corta (sin ejes ni etiquetas) y su último punto, para acompañar una cifra."""
    n = len(valores)
    techo = max(max(valores, default=0), 1)
    util_x, util_y = ancho - 2 * margen, alto - 2 * margen
    puntos = [
        (margen + (util_x * i / (n - 1) if n > 1 else util_x / 2), margen + util_y * (1 - valor / techo))
        for i, valor in enumerate(valores)
    ]
    ruta = "M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in puntos) if len(puntos) > 1 else ""
    ultimo = {"x": _n(puntos[-1][0]), "y": _n(puntos[-1][1])} if puntos else None
    return {"ancho": ancho, "alto": alto, "ruta": ruta, "ultimo": ultimo}


def segmentos(partes):
    """Partes de una barra segmentada: cada una con su porcentaje entero (suman 100) y si se dibuja.

    `partes` es una lista de dicts con al menos `cantidad`. El ancho lo reparte el navegador a razón de la
    cantidad (`flex-grow`); las partes en cero no se dibujan, pero siguen en la leyenda con 0 %.
    """
    enteros = porcentajes([parte["cantidad"] for parte in partes])
    return [{**parte, "porcentaje": entero, "visible": bool(parte["cantidad"])} for parte, entero in zip(partes, enteros)]


def cortes_de_calor(maximo):
    """Límite superior de cada uno de los (hasta) cinco tonos del mapa de calor, de menor a mayor."""
    if maximo <= 0:
        return []
    if maximo <= 5:
        return list(range(1, maximo + 1))
    return sorted({ceil(maximo * k / 5) for k in range(1, 6)})


def mapa_calor(conteos, hoy, semanas=12):
    """Calendario de `semanas` filas (lunes a domingo) desde la semana de `hoy`, con un tono por día.

    `conteos` es un dict `{fecha: cantidad}`. Los días anteriores a `hoy` quedan como `pasado` y no pintan.
    Devuelve las semanas, los límites de cada tono y la leyenda (`tono`, `desde`, `hasta`).
    """
    lunes = hoy - timedelta(days=hoy.weekday())
    ultimo = lunes + timedelta(days=7 * semanas - 1)
    visibles = {dia: cantidad for dia, cantidad in conteos.items() if hoy <= dia <= ultimo and cantidad > 0}
    maximo = max(visibles.values(), default=0)
    cortes = cortes_de_calor(maximo)

    def tono(cantidad):
        if cantidad <= 0:
            return 0
        return next(i for i, corte in enumerate(cortes, start=1) if cantidad <= corte)

    filas = []
    for semana in range(semanas):
        primer_dia = lunes + timedelta(days=7 * semana)
        dias = []
        for desplazamiento in range(7):
            fecha = primer_dia + timedelta(days=desplazamiento)
            pasado = fecha < hoy
            cantidad = 0 if pasado else visibles.get(fecha, 0)
            dias.append({"fecha": fecha, "valor": cantidad, "tono": tono(cantidad), "pasado": pasado, "es_hoy": fecha == hoy})
        filas.append({"lunes": primer_dia, "dias": dias})

    leyenda, desde = [], 1
    for i, corte in enumerate(cortes, start=1):
        leyenda.append({"tono": i, "desde": desde, "hasta": corte})
        desde = corte + 1
    return {"semanas": filas, "cortes": cortes, "leyenda": leyenda, "maximo": maximo, "total": sum(visibles.values())}
