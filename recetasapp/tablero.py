"""Arma el tablero de la página de recetas: cifras, gráficos y ranking, solo con lectura.

Reúne las consultas de `consultas`, la geometría de `graficos` y los textos de `presentacion`. No decide
permisos: la vista que lo usa ya lo hizo.
"""

from django.urls import reverse
from django.utils import formats, timezone

from . import consultas, graficos, presentacion

PERIODOS = ((7, "7 días"), (30, "30 días"), (90, "90 días"))
PERIODO_INICIAL = 30


def periodo_valido(valor):
    """Periodo del gráfico de entregas: solo los ofrecidos; cualquier otro valor vuelve al inicial."""
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return PERIODO_INICIAL
    return numero if numero in dict(PERIODOS) else PERIODO_INICIAL


def _pct(parte, total):
    return round(100 * parte / total) if total else 0


def armar(hoy=None, periodo=PERIODO_INICIAL):
    hoy = hoy or timezone.localdate()
    lista = reverse("recetasapp:recetas")
    conteos = consultas.contar_recetas(hoy)
    sin_vigente = consultas.pacientes_sin_vigente(hoy).count()
    mes = consultas.entregas_del_mes(hoy)
    total = conteos["total"]

    kpis = [
        {"clave": "vigentes", "titulo": "Recetas vigentes", "valor": conteos["vigente"], "icono": "i-ok",
         "nota": f"de {total} recetas ({_pct(conteos['vigente'], total)} %)", "enlace": f"{lista}?situacion=vigente#listado"},
        {"clave": "por-vencer", "titulo": "Por vencer", "valor": conteos["por_vencer"], "icono": "i-calendario",
         "nota": f"vencen en {consultas.DIAS_POR_VENCER} días o menos", "atencion": bool(conteos["por_vencer"]),
         "enlace": f"{lista}?situacion=por_vencer#listado"},
        {"clave": "sin-vigente", "titulo": "Pacientes sin receta vigente", "valor": sin_vigente, "icono": "i-usuarios",
         "nota": "hoy no pueden retirar", "enlace": f"{reverse('recetasapp:pacientes')}?filtro=sin_vigente"},
        {"clave": "entregas", "titulo": "Entregas este mes", "valor": mes["este"], "icono": "i-sello",
         "nota": f"{mes['anterior']} el mes pasado", "enlace": ""},
    ]

    partes = presentacion.segmentos_resumen(conteos)
    anillo = graficos.anillo(partes)
    for parte in anillo["partes"]:
        parte["enlace"] = f"{lista}?situacion={parte['clave']}#listado"

    serie = consultas.entregas_por_dia(periodo, hoy)
    linea = graficos.linea(serie)
    for punto in linea["puntos"]:
        punto["texto"] = formats.date_format(punto["fecha"], "j \d\e F")
    for marca in linea["marcas_x"]:
        marca["texto"] = formats.date_format(marca["fecha"], "j b")
    if linea["dia_maximo"]:
        linea["dia_maximo_texto"] = formats.date_format(linea["dia_maximo"], "j \d\e F")

    vencimientos = consultas.vencimientos_por_mes(hoy)
    barras = graficos.barras([(formats.date_format(mes_, "b"), cantidad) for mes_, cantidad in vencimientos])
    barras["meses"] = [formats.date_format(mes_, "F \d\e Y") for mes_, _ in vencimientos]
    for barra, nombre in zip(barras["barras"], barras["meses"]):
        barra["mes_largo"] = nombre

    filas = [presentacion.preparar_por_vencer(receta, hoy) for receta in consultas.recetas_por_vencer(hoy, limite=6)]
    for receta in filas:
        receta.porcentaje = presentacion.porcentaje_entregas(receta)
        receta.puntos_resumen = f"{receta.entregas_completadas} de {receta.max_entregas}"

    carga = consultas.ultima_carga()
    if carga:
        carga.categorias = presentacion.categorias_carga(carga)

    return {
        "hoy": hoy, "total": total, "kpis": kpis, "anillo": anillo, "linea": linea,
        "periodo": periodo, "periodos": [{"dias": dias, "texto": texto} for dias, texto in PERIODOS],
        "barras": barras, "por_vencer": filas, "por_vencer_total": conteos["por_vencer"],
        "carga": carga, "dias_por_vencer": consultas.DIAS_POR_VENCER,
    }
