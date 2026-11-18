"""Arma el resumen de Recetas: cifras, situación, las que vencen primero y la última carga, solo con lectura.

Reúne las consultas de `consultas`, la geometría de `graficos` y los textos de `presentacion`. No decide
permisos: la vista que lo usa ya lo hizo.

El resumen se queda con lo que sirve para trabajar: cifras que llevan a su lista, la barra de situación
(cada tramo abre la lista filtrada) y la tabla de las que vencen primero. Las tendencias en el tiempo, como
las entregas por día, están en el panel de Indicadores.
"""

from django.urls import reverse
from django.utils import timezone

from . import consultas, graficos, presentacion


def _pct(parte, total):
    return round(100 * parte / total) if total else 0


def _comparacion(esta, anterior):
    """Cómo cambió la cifra frente a los 7 días anteriores: sentido (para el ícono) y frase."""
    diferencia = esta - anterior
    if diferencia > 0:
        return "sube", f"{diferencia} más que en los 7 días anteriores"
    if diferencia < 0:
        return "baja", f"{-diferencia} menos que en los 7 días anteriores"
    return "igual", "Igual que en los 7 días anteriores"


def armar(hoy=None):
    hoy = hoy or timezone.localdate()
    lista = reverse("recetasapp:recetas_lista")
    conteos = consultas.contar_recetas(hoy)
    total = conteos["total"]
    sin_vigente = consultas.pacientes_sin_vigente(hoy).count()

    ultimos_14 = [valor for _, valor in consultas.entregas_por_dia(14, hoy)]
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
        "hoy": hoy, "total": total, "kpis": kpis, "situacion": situacion,
        "por_vencer": filas, "por_vencer_total": conteos["por_vencer"],
        "carga": carga, "dias_por_vencer": consultas.DIAS_POR_VENCER,
    }
