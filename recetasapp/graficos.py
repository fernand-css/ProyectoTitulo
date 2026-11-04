"""Geometría de los gráficos del tablero: se calcula aquí y las plantillas solo la dibujan.

Los gráficos son SVG y HTML sin librerías (el sistema no puede depender de un CDN). Todo número que
termina en un atributo SVG sale ya formateado como texto con punto decimal: con la configuración
regional es-cl, Django escribiría la coma y el atributo quedaría inválido.
"""

from datetime import date


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


def anillo(partes):
    """Arcos de un anillo medidos sobre un círculo de longitud 100 (`pathLength="100"`).

    `partes` es una lista de dicts con `clave`, `texto` y `cantidad`. Cada arco lleva `trazo` (su largo),
    `inicio` (dónde empieza) y `indice` (para escalonar la animación). Las partes en cero no se dibujan,
    pero siguen en la leyenda con 0 %.
    """
    cantidades = [parte["cantidad"] for parte in partes]
    total = sum(cantidades)
    enteros = porcentajes(cantidades)
    resultado, acumulado, indice = [], 0.0, 0
    visibles = sum(1 for cantidad in cantidades if cantidad)
    for parte, entero in zip(partes, enteros):
        largo = 100 * parte["cantidad"] / total if total else 0
        # Un pequeño hueco separa los arcos; con un único arco el anillo se cierra completo.
        hueco = 0.8 if visibles > 1 else 0
        dibujo = max(largo - hueco, 0.0)
        resultado.append({
            **parte, "porcentaje": entero,
            "trazo": _n(dibujo), "inicio": _n(acumulado), "indice": indice,
            "visible": bool(parte["cantidad"]),
        })
        if parte["cantidad"]:
            indice += 1
        acumulado += largo
    return {"total": total, "partes": resultado}


def _techo(maximo):
    """Valor redondo, igual o mayor que el máximo, y su paso (de 1, 2 o 5 por potencia de 10), con 4 marcas como máximo."""
    maximo = max(maximo, 1)
    paso = 1
    while True:
        for factor in (1, 2, 5):
            candidato = factor * paso
            if candidato * 4 >= maximo:
                return candidato * 4, candidato
        paso *= 10


def linea(serie, ancho=640, alto=330, margen=(14, 14, 30, 38)):
    """Serie de `(fecha, valor)` como línea suave con área, marcas de ejes y un punto por dato.

    `margen` es (arriba, derecha, abajo, izquierda). La curva usa tangentes horizontales en cada dato:
    no se pasa de los valores reales, así que nunca baja de cero ni sube más que el máximo.
    """
    arriba, derecha, abajo, izquierda = margen
    n = len(serie)
    valores = [valor for _, valor in serie]
    techo, paso = _techo(max(valores, default=0))
    util_x, util_y = ancho - izquierda - derecha, alto - arriba - abajo

    def x_de(i):
        return izquierda + (util_x * i / (n - 1) if n > 1 else util_x / 2)

    def y_de(valor):
        return arriba + util_y * (1 - valor / techo)

    puntos = [{
        "x": _n(x_de(i)), "y": _n(y_de(valor)), "valor": valor, "fecha": fecha, "indice": i,
    } for i, (fecha, valor) in enumerate(serie)]
    base_y = arriba + util_y

    if n == 0:
        ruta = area = ""
    else:
        trozos = [f"M{_n(x_de(0))} {_n(y_de(valores[0]))}"]
        for i in range(1, n):
            x0, x1 = x_de(i - 1), x_de(i)
            medio = (x0 + x1) / 2
            trozos.append(f"C{_n(medio)} {_n(y_de(valores[i - 1]))} {_n(medio)} {_n(y_de(valores[i]))} {_n(x1)} {_n(y_de(valores[i]))}")
        ruta = " ".join(trozos)
        area = f"{ruta} L{_n(x_de(n - 1))} {_n(base_y)} L{_n(x_de(0))} {_n(base_y)} Z"

    marcas_y = [{"y": _n(y_de(paso * k)), "etiqueta": paso * k} for k in range(0, 5)]
    # Entre 4 y 6 etiquetas de fecha, siempre con la primera y la última.
    if n <= 6:
        elegidos = list(range(n))
    else:
        saltos = 5
        elegidos = sorted({round(i * (n - 1) / saltos) for i in range(saltos + 1)})
    marcas_x = [{"x": _n(x_de(i)), "fecha": serie[i][0]} for i in elegidos]
    return {
        "ancho": ancho, "alto": alto, "ruta": ruta, "area": area, "puntos": puntos,
        "marcas_x": marcas_x, "marcas_y": marcas_y,
        "izquierda": _n(izquierda), "derecha": _n(ancho - derecha),
        "total": sum(valores), "maximo": max(valores, default=0),
        "dia_maximo": next((fecha for fecha, valor in serie if valor == max(valores)), None) if valores and max(valores) else None,
        "ultimo": puntos[-1] if puntos else None,
    }


def barras(serie):
    """Serie de `(etiqueta, valor)` con la altura de cada barra como porcentaje del mayor."""
    maximo = max((valor for _, valor in serie), default=0)
    return {
        "barras": [
            {"etiqueta": etiqueta, "valor": valor, "altura": _n(100 * valor / maximo) if maximo else "0", "indice": i}
            for i, (etiqueta, valor) in enumerate(serie)
        ],
        "maximo": maximo, "total": sum(valor for _, valor in serie),
    }


def sumar_meses(primero, meses):
    """Primer día del mes que está `meses` meses después (o antes) del mes de `primero`."""
    indice = primero.year * 12 + (primero.month - 1) + meses
    return date(indice // 12, indice % 12 + 1, 1)
