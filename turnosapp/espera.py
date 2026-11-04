"""Estimación aproximada de la espera de preparación para pacientes y personal."""

from dataclasses import dataclass
from math import ceil

from django.utils import timezone

from recetasapp.preparacion import por_preparar, promedio_preparacion
from .models import Ventanilla


@dataclass(frozen=True)
class EstimacionEspera:
    minutos: int | None
    frase: str
    pendientes: int
    ventanillas: int
    promedio_segundos: int
    muestras: int
    usa_valor_predeterminado: bool


def estimar_espera(ahora=None):
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    pendientes = por_preparar(hoy).filter(lista_en__isnull=True).count()
    promedio = promedio_preparacion(ahora)
    ventanillas = Ventanilla.objects.filter(
        habilitada=True, retirada=False, operador__isnull=False,
        automatico=True, fecha_activacion=hoy,
    ).count()
    if ventanillas == 0:
        return EstimacionEspera(
            None, "No podemos estimar el tiempo de espera. Consulta con el personal.",
            pendientes, 0, promedio.segundos, promedio.muestras, promedio.predeterminado,
        )
    minutos_sin_redondear = pendientes * promedio.segundos / ventanillas / 60
    if minutos_sin_redondear < 5:
        frase = "Tiempo aproximado de espera: menos de 5 minutos."
        minutos = 0
    else:
        minutos = ceil(minutos_sin_redondear / 5) * 5
        frase = f"Tiempo aproximado de espera: unos {minutos} minutos."
    return EstimacionEspera(
        minutos, frase, pendientes, ventanillas, promedio.segundos,
        promedio.muestras, promedio.predeterminado,
    )
