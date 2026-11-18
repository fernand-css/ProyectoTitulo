"""Entregas confirmadas por día o por semana en el período del panel: lectura pura, sin escrituras.

Cuenta cada `EntregaReceta` (en farmacia o por el reparto) por la fecha local en que se confirmó, con el mismo
filtro de tipo de paciente que la merma. Hasta `mermas.DIAS_POR_DIA` días va por día, con el promedio de los
7 días que terminan en cada uno (se leen los 6 días anteriores al período para que el primero ya lo tenga);
con más, por semana de lunes a domingo y sin promedio. Solo devuelve cifras agregadas, nunca datos personales.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from recetasapp.graficos import promedio_movil
from recetasapp.models import EntregaReceta

from .mermas import CRONICO, DIAS_POR_DIA, GENERAL, Periodo, _limites

VENTANA_PROMEDIO = 7


@dataclass(frozen=True)
class EntregasDelPeriodo:
    por_semana: bool
    serie: list       # [(fecha del día o lunes de la semana, entregas)]
    promedios: list   # alineado con `serie`; vacío por semana
    total: int


def _fechas(periodo):
    """Fecha local de confirmación de cada entrega del período (con el tipo de paciente pedido)."""
    desde, hasta = _limites(periodo)
    consulta = EntregaReceta.objects.filter(creado_en__gte=desde, creado_en__lt=hasta)
    if periodo.tipo == CRONICO:
        consulta = consulta.filter(receta__paciente__es_cronico=True)
    elif periodo.tipo == GENERAL:
        consulta = consulta.filter(receta__paciente__es_cronico=False)
    # Se agrupa en Python con la zona local: así el día es el mismo en SQLite y en PostgreSQL.
    return [timezone.localtime(momento).date() for momento in consulta.values_list("creado_en", flat=True)]


def resumir(periodo):
    if periodo.dias > DIAS_POR_DIA:
        lunes = periodo.inicio - timedelta(days=periodo.inicio.weekday())
        serie = {lunes + timedelta(days=7 * i): 0 for i in range((periodo.fin - lunes).days // 7 + 1)}
        for fecha in _fechas(periodo):
            serie[fecha - timedelta(days=fecha.weekday())] += 1
        return EntregasDelPeriodo(True, list(serie.items()), [], sum(serie.values()))

    previo = VENTANA_PROMEDIO - 1
    ampliado = Periodo(periodo.inicio - timedelta(days=previo), periodo.fin, periodo.tipo)
    largo = {ampliado.inicio + timedelta(days=i): 0 for i in range(ampliado.dias)}
    for fecha in _fechas(ampliado):
        largo[fecha] += 1
    valores = list(largo.values())
    serie = list(largo.items())[previo:]
    return EntregasDelPeriodo(False, serie, promedio_movil(valores, VENTANA_PROMEDIO)[previo:],
                              sum(valor for _, valor in serie))
