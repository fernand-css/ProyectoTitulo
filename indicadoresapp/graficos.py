"""Gráficos del panel de mermas: se calculan aquí y la plantilla solo los dibuja.

Son HTML sin librerías y no reciben datos personales: solo cifras agregadas del resumen.

- Blíster: cada alvéolo es una receta (o un grupo fijo de recetas en períodos con muchas), lleno si sigue sin
  entregar y vacío si se recuperó. El relleno y la textura distinguen los cuatro estados además del color.
- Calendario: la merma de cada día con su cifra escrita; el tono ámbar sube con la cantidad.
- Barras: una lista de partes con su ancho relativo a la mayor.
"""

from datetime import timedelta
from math import ceil

from recetasapp.graficos import porcentajes

from . import mermas

MAX_ALVEOLOS = 300
POR_TIRA = 10
ESCALAS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
DIAS_PLURAL = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos")
DIAS_CORTOS = (("L", "Lunes"), ("M", "Martes"), ("M", "Miércoles"), ("J", "Jueves"), ("V", "Viernes"),
               ("S", "Sábado"), ("D", "Domingo"))


def _repartir(cantidades, total):
    """Reparte `total` alvéolos en proporción a `cantidades` (mayor resto) y deja al menos uno a cada parte no vacía."""
    suma = sum(cantidades)
    brutos = [total * c / suma for c in cantidades]
    base = [max(int(b), 1 if c else 0) for b, c in zip(brutos, cantidades)]
    restos = sorted(range(len(brutos)), key=lambda i: (brutos[i] - int(brutos[i]), -i), reverse=True)
    for i in restos:
        if sum(base) >= total:
            break
        if cantidades[i]:
            base[i] += 1
    return base


def blister(cifras):
    """Tiras de diez alvéolos en el orden de los estados; `escala` es cuántas recetas vale cada alvéolo."""
    cantidades = [cifras[clave] for clave, _ in mermas.ESTADOS]
    total = sum(cantidades)
    if not total:
        return None
    escala = next(e for e in ESCALAS if ceil(total / e) <= MAX_ALVEOLOS)
    alveolos = _repartir(cantidades, ceil(total / escala)) if escala > 1 else cantidades
    celdas = [clave for (clave, _), n in zip(mermas.ESTADOS, alveolos) for _ in range(n)]
    celdas += ["vacio"] * (-len(celdas) % POR_TIRA)
    return {
        "escala": escala,
        "tiras": [celdas[i:i + POR_TIRA] for i in range(0, len(celdas), POR_TIRA)],
        "leyenda": [{"clave": clave, "texto": texto, "cantidad": cifras[clave]} for clave, texto in mermas.ESTADOS],
    }


def _nivel(valor, maximo):
    return 0 if not valor else min(5, max(1, ceil(5 * valor / maximo)))


def fecha_corta(fecha):
    return f"{fecha.day} {MESES[fecha.month - 1]}"


def calendario(serie, inicio, fin):
    """Semanas de lunes a domingo con la merma de cada día; los días fuera del período quedan vacíos."""
    valores = dict(serie)
    maximo = max(valores.values(), default=0)
    primero = inicio - timedelta(days=inicio.weekday())
    ultimo = fin + timedelta(days=6 - fin.weekday())
    semanas, semana, dia = [], [], primero
    while dia <= ultimo:
        if inicio <= dia <= fin:
            valor = valores.get(dia, 0)
            etiqueta = fecha_corta(dia) if dia == inicio or dia.day == 1 else str(dia.day)
            semana.append({
                "fecha": dia, "etiqueta": etiqueta, "valor": valor, "nivel": _nivel(valor, maximo),
                "fin_de_semana": dia.weekday() >= 5,
                "tip": f"{DIAS_CORTOS[dia.weekday()][1]} {fecha_corta(dia)}: {valor} receta{'s' if valor != 1 else ''}",
            })
        else:
            semana.append(None)
        if len(semana) == 7:
            semanas.append(semana)
            semana = []
        dia += timedelta(days=1)
    dia_maximo = next((fecha for fecha, valor in serie if valor == maximo), None) if maximo else None
    return {"semanas": semanas, "dias": DIAS_CORTOS, "maximo": maximo, "dia_maximo": dia_maximo}


def frase_dia_semana(por_dia_semana, merma, dias):
    """«Los lunes suman 32 de las 87 recetas.»: solo con dos semanas o más y un día que destaque sin empate."""
    if dias < 14 or not merma:
        return ""
    maximo = max(por_dia_semana)
    if por_dia_semana.count(maximo) > 1:
        return ""
    dia = DIAS_PLURAL[por_dia_semana.index(maximo)]
    return f"Los {dia} suman {maximo} de las {merma} recetas."


def barras(partes, ordenar=False):
    """`partes` es [(clave, texto, cantidad)]; cada barra mide en porcentaje de la mayor."""
    if ordenar:
        partes = sorted(partes, key=lambda parte: -parte[2])
    maximo = max((cantidad for _, _, cantidad in partes), default=0)
    return [{"clave": clave, "texto": texto, "cantidad": cantidad,
             "ancho": f"{100 * cantidad / maximo:.1f}" if maximo else "0", "tramo": i}
            for i, (clave, texto, cantidad) in enumerate(partes)]


def division(partes):
    """Barra dividida en dos o más partes, con su porcentaje entero (suman 100)."""
    cuotas = porcentajes([cantidad for _, _, cantidad in partes])
    return [{"clave": clave, "texto": texto, "cantidad": cantidad, "porcentaje": cuota}
            for (clave, texto, cantidad), cuota in zip(partes, cuotas)]
