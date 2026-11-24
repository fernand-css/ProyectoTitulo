"""Consultas puras de preparación, retiro pendiente y tiempos observados."""

import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from math import ceil

from django.db.models import Avg, Count, Exists, F, OuterRef, Q, Value
from django.db.models.functions import Lower, Replace
from django.utils import timezone

from coreapp.utils.rut import condicion_busqueda_rut
from .models import PreparacionReceta

DIAS_VENTANA_PROMEDIO = 14
MUESTRAS_MINIMAS = 5
DURACION_POR_DEFECTO_SEGUNDOS = 5 * 60
DURACION_MAXIMA_SEGUNDOS = 30 * 60


@dataclass(frozen=True)
class PromedioPreparacion:
    segundos: int
    muestras: int
    predeterminado: bool


def por_preparar(hoy=None):
    """Preparaciones de turnos activos de la jornada, en orden de llegada."""
    hoy = hoy or timezone.localdate()
    return (
        PreparacionReceta.objects.filter(
            turno_receta__turno__fecha=hoy,
            turno_receta__turno__estado__in=("esperando", "llamado"),
        )
        .select_related(
            "turno_receta__turno__paciente", "turno_receta__receta", "lista_por",
        )
        .order_by(
            "turno_receta__turno__entrada_cola",
            "turno_receta__turno__numero",
            "turno_receta_id",
        )
    )


def _normalizar_apellido(valor):
    separado = unicodedata.normalize("NFKD", valor.casefold())
    return "".join(caracter for caracter in separado if not unicodedata.combining(caracter)).strip()


def _apellidos_sin_acentos():
    expresion = Lower("turno_receta__turno__paciente__apellidos")
    for acentuada, base in (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("ü", "u"), ("ñ", "n"),
    ):
        expresion = Replace(expresion, Value(acentuada), Value(base))
    return expresion


def pendientes_retiro(buscar=None):
    """Preparaciones listas, aún no entregadas, de turnos que ya cerraron.

    `en_despacho` (spec 13): la preparación viaja en una entrega a domicilio abierta; la ventanilla no la entrega.
    """
    from entregasapp.models import Entrega, RecetaEntrega

    pendientes = PreparacionReceta.objects.annotate(en_despacho=Exists(RecetaEntrega.objects.filter(
        preparacion=OuterRef("pk"), entrega__estado__in=Entrega.ABIERTAS,
    ))).filter(
        lista_en__isnull=False,
        turno_receta__entrega__isnull=True,
        turno_receta__turno__estado__in=(
            "ausente", "sin_atencion_cierre", "atendido", "cerrado_sin_entrega",
        ),
    ).select_related(
        "turno_receta__turno__paciente", "turno_receta__receta", "lista_por",
    ).order_by("lista_en", "turno_receta__turno__fecha", "turno_receta__turno__numero")

    buscar = (buscar or "").strip()
    if not buscar:
        return pendientes
    por_rut = condicion_busqueda_rut(buscar, "turno_receta__turno__paciente__rut")
    if por_rut is not None:
        return pendientes.filter(por_rut)
    return (
        pendientes.annotate(apellidos_normalizados=_apellidos_sin_acentos())
        .filter(apellidos_normalizados__icontains=_normalizar_apellido(buscar))
    )


def promedio_preparacion(ahora=None):
    """Promedio móvil de 14 días, descartando intervalos mayores a 30 minutos."""
    ahora = ahora or timezone.now()
    datos = PreparacionReceta.objects.filter(
        lista_en__gte=ahora - timedelta(days=DIAS_VENTANA_PROMEDIO),
        lista_en__lte=ahora,
        duracion_segundos__lte=DURACION_MAXIMA_SEGUNDOS,
    ).aggregate(promedio=Avg("duracion_segundos"), muestras=Count("pk"))
    muestras = datos["muestras"]
    if muestras < MUESTRAS_MINIMAS:
        return PromedioPreparacion(DURACION_POR_DEFECTO_SEGUNDOS, muestras, True)
    return PromedioPreparacion(ceil(datos["promedio"]), muestras, False)
