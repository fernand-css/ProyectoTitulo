"""Arma el resumen de Recetas: cifras, gráficos y ranking, solo con lectura.

Reúne las consultas de `consultas`, la geometría de `graficos` y los textos de `presentacion`. No decide
permisos: la vista que lo usa ya lo hizo.

Cuatro formas, cada una elegida por lo que cuenta: cifras con tendencia (qué pasa ahora), columnas con
promedio móvil (entregas por día), barra segmentada (cómo se reparten las recetas) y calendario de calor
(cuándo vencen las vigentes). Los textos de cada dato salen aquí para que el tooltip, la tabla y el lector
de pantalla digan lo mismo.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import formats, timezone

from . import consultas, graficos, presentacion

PERIODOS = ((14, "14 días"), (30, "30 días"), (90, "90 días"))
PERIODO_INICIAL = 30
VENTANA_PROMEDIO = 7
SEMANAS_DEL_CALENDARIO = 12


def periodo_valido(valor):
    """Periodo del gráfico de entregas: solo los ofrecidos; cualquier otro valor vuelve al inicial."""
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return PERIODO_INICIAL
    return numero if numero in dict(PERIODOS) else PERIODO_INICIAL


def _pct(parte, total):
    return round(100 * parte / total) if total else 0


def _plural(cantidad, singular, plural):
    return singular if cantidad == 1 else plural


def _decimal(valor):
    """Un decimal con la coma de la configuración regional, sin el «,0» sobrante."""
    texto = formats.number_format(valor, decimal_pos=1)
    return texto[:-2] if texto.endswith(",0") or texto.endswith(".0") else texto


def _comparacion(esta, anterior):
    """Cómo cambió la cifra frente a los 7 días anteriores: sentido (para el ícono) y frase."""
    diferencia = esta - anterior
    if diferencia > 0:
        return "sube", f"{diferencia} más que en los 7 días anteriores"
    if diferencia < 0:
        return "baja", f"{-diferencia} menos que en los 7 días anteriores"
    return "igual", "Igual que en los 7 días anteriores"


def _entregas(hoy, periodo):
    """Columnas de entregas por día con su promedio móvil, y las cifras que acompañan al gráfico."""
    # Se pide una ventana más para que el primer día mostrado ya tenga su promedio de 7 días completo.
    largo = consultas.entregas_por_dia(periodo + VENTANA_PROMEDIO - 1, hoy)
    valores = [valor for _, valor in largo]
    promedios = graficos.promedio_movil(valores, VENTANA_PROMEDIO)
    desde = VENTANA_PROMEDIO - 1
    grafico = graficos.columnas(largo[desde:], promedios[desde:])
    for columna in grafico["columnas"]:
        fecha, valor, promedio = columna["fecha"], columna["valor"], columna["promedio"]
        columna["texto"] = formats.date_format(fecha, r"l j \d\e F")
        columna["tip"] = (
            f"{columna['texto']}: {valor} {_plural(valor, 'entrega', 'entregas')} · "
            f"promedio de {VENTANA_PROMEDIO} días: {_decimal(promedio)}"
        )
    for marca in grafico["marcas_x"]:
        marca["texto"] = formats.date_format(marca["fecha"], "j b")
    if grafico["dia_maximo"]:
        grafico["dia_maximo_texto"] = formats.date_format(grafico["dia_maximo"], r"j \d\e F")
    grafico["periodo"] = periodo
    grafico["promedio_diario"] = _decimal(grafico["total"] / periodo)
    return grafico, valores[-14:]


def _calendario(hoy):
    """Mapa de calor de las próximas semanas: cuántas recetas vigentes vencen cada día."""
    lunes = hoy - timedelta(days=hoy.weekday())
    ultimo = lunes + timedelta(days=7 * SEMANAS_DEL_CALENDARIO - 1)
    calor = graficos.mapa_calor(consultas.vencimientos_por_dia(hoy, ultimo, hoy), hoy, SEMANAS_DEL_CALENDARIO)
    con_vencimientos = []
    for semana in calor["semanas"]:
        semana["texto"] = "Esta semana" if semana["lunes"] == lunes else formats.date_format(semana["lunes"], "j b")
        for dia in semana["dias"]:
            if dia["pasado"]:
                continue
            dia["texto"] = formats.date_format(dia["fecha"], r"l j \d\e F")
            if dia["valor"]:
                dia["tip"] = f"{dia['texto']}: {dia['valor']} {_plural(dia['valor'], 'receta vence', 'recetas vencen')}"
                con_vencimientos.append(dia)
            else:
                dia["tip"] = f"{dia['texto']}: ninguna receta vence"
    for tramo in calor["leyenda"]:
        tramo["texto"] = str(tramo["desde"]) if tramo["desde"] == tramo["hasta"] else f"{tramo['desde']} a {tramo['hasta']}"
    calor["con_vencimientos"] = con_vencimientos
    calor["dias_texto"] = f"{SEMANAS_DEL_CALENDARIO} semanas"
    return calor


def armar(hoy=None, periodo=PERIODO_INICIAL):
    hoy = hoy or timezone.localdate()
    lista = reverse("recetasapp:recetas_lista")
    conteos = consultas.contar_recetas(hoy)
    total = conteos["total"]
    sin_vigente = consultas.pacientes_sin_vigente(hoy).count()

    entregas, ultimos_14 = _entregas(hoy, periodo)
    esta_semana, semana_anterior = sum(ultimos_14[7:]), sum(ultimos_14[:7])
    sentido, comparacion = _comparacion(esta_semana, semana_anterior)

    kpis = [
        {"clave": "vigentes", "titulo": "Recetas vigentes", "valor": conteos["vigente"], "icono": "i-ok",
         "nota": f"de {total} recetas ({_pct(conteos['vigente'], total)} %)", "enlace": f"{lista}?situacion=vigente"},
        {"clave": "por-vencer", "titulo": "Por vencer", "valor": conteos["por_vencer"], "icono": "i-calendario",
         "nota": f"vencen en {consultas.DIAS_POR_VENCER} días o menos", "atencion": bool(conteos["por_vencer"]),
         "enlace": f"{lista}?situacion=por_vencer"},
        {"clave": "sin-vigente", "titulo": "Pacientes sin receta vigente", "valor": sin_vigente, "icono": "i-usuarios",
         "nota": "hoy no pueden retirar", "enlace": f"{reverse('recetasapp:pacientes')}?filtro=sin_vigente"},
        {"clave": "entregas", "titulo": "Entregas en 7 días", "valor": esta_semana, "icono": "i-sello",
         "nota": comparacion, "sentido": sentido, "tendencia": graficos.tendencia(ultimos_14), "enlace": ""},
    ]

    situacion = graficos.segmentos(presentacion.segmentos_resumen(conteos))
    for parte in situacion:
        parte["enlace"] = f"{lista}?situacion={parte['clave']}"

    filas = [presentacion.preparar_por_vencer(receta, hoy) for receta in consultas.recetas_por_vencer(hoy, limite=6)]
    for receta in filas:
        receta.porcentaje = presentacion.porcentaje_entregas(receta)
        receta.puntos_resumen = f"{receta.entregas_completadas} de {receta.max_entregas}"

    carga = consultas.ultima_carga()
    if carga:
        carga.categorias = presentacion.categorias_carga(carga)

    return {
        "hoy": hoy, "total": total, "kpis": kpis, "entregas": entregas, "situacion": situacion,
        "periodo": periodo, "periodos": [{"dias": dias, "texto": texto} for dias, texto in PERIODOS],
        "calor": _calendario(hoy), "por_vencer": filas, "por_vencer_total": conteos["por_vencer"],
        "carga": carga, "dias_por_vencer": consultas.DIAS_POR_VENCER, "ventana": VENTANA_PROMEDIO,
    }
