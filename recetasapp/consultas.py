"""Consultas de solo lectura para el resumen y la lista de recetas.

Expresa en SQL la misma regla que `presentacion.situacion` (vencida, luego agotada, luego aún no
inicia y, si ninguna aplica, vigente), de modo que la lista filtrada y el contador del resumen
coincidan con la insignia que se muestra en cada fila. Solo usa el ORM.
"""

from datetime import timedelta

from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from .graficos import sumar_meses
from .models import EntregaReceta, ImportacionPadron, Paciente, Receta

DIAS_POR_VENCER = 30

# (clave, texto de la pestaña) en el orden en que se ofrecen. «Por vencer» es una parte de «Vigentes».
FILTROS_RECETA = (
    ("vigente", "Vigentes"),
    ("por_vencer", "Por vencer"),
    ("futura", "Aún no inician"),
    ("agotada", "Agotadas"),
    ("vencida", "Vencidas"),
)
FILTROS_PACIENTE = (("sin_vigente", "Sin receta vigente"),)


def condiciones(hoy=None):
    """Condiciones de situación por clave. Las cuatro primeras son excluyentes entre sí."""
    hoy = hoy or timezone.localdate()
    vencida = Q(fecha_fin_exclusiva__lte=hoy)
    sin_cupo = Q(entregas_completadas__gte=F("max_entregas"))
    no_inicia = Q(fecha_inicio__gt=hoy)
    vigente = ~vencida & ~sin_cupo & ~no_inicia
    return {
        "vencida": vencida,
        "agotada": ~vencida & sin_cupo,
        "futura": ~vencida & ~sin_cupo & no_inicia,
        "vigente": vigente,
        "por_vencer": vigente & Q(fecha_fin_exclusiva__lte=hoy + timedelta(days=DIAS_POR_VENCER)),
    }


def filtrar_recetas(recetas, clave, hoy=None):
    """Recetas en la situación pedida; una clave vacía las devuelve todas."""
    if not clave:
        return recetas
    return recetas.filter(condiciones(hoy)[clave])


def contar_recetas(hoy=None):
    """Total y recetas por situación, en una sola consulta."""
    por_clave = condiciones(hoy)
    datos = Receta.objects.aggregate(
        total=Count("pk"), **{clave: Count("pk", filter=condicion) for clave, condicion in por_clave.items()},
    )
    return datos


def recetas_por_vencer(hoy=None, limite=8):
    """Las vigentes que vencen primero, con la que está más cerca arriba."""
    return filtrar_recetas(Receta.objects.select_related("paciente"), "por_vencer", hoy).order_by("fecha_fin_exclusiva", "pk")[:limite]


def pacientes_sin_vigente(hoy=None):
    """Pacientes del padrón que hoy no tienen ninguna receta que admita entregas."""
    vigentes = Receta.objects.filter(condiciones(hoy)["vigente"]).values("paciente_id")
    return Paciente.objects.exclude(pk__in=vigentes)


def ultima_carga():
    return ImportacionPadron.objects.select_related("creado_por").first()


def entregas_por_dia(dias, hoy=None):
    """Entregas confirmadas por día durante los últimos `dias` días (hoy incluido), con ceros donde no hubo."""
    hoy = hoy or timezone.localdate()
    desde = hoy - timedelta(days=dias - 1)
    cuentas = {
        fila["dia"]: fila["n"]
        for fila in EntregaReceta.objects.filter(creado_en__date__gte=desde, creado_en__date__lte=hoy)
        .annotate(dia=TruncDate("creado_en")).values("dia").annotate(n=Count("pk"))
    }
    return [(desde + timedelta(days=i), cuentas.get(desde + timedelta(days=i), 0)) for i in range(dias)]


def entregas_del_mes(hoy=None):
    """Entregas confirmadas en el mes de `hoy` y en el mes anterior."""
    hoy = hoy or timezone.localdate()
    este, anterior = hoy.replace(day=1), sumar_meses(hoy.replace(day=1), -1)
    return EntregaReceta.objects.aggregate(
        este=Count("pk", filter=Q(creado_en__date__gte=este, creado_en__date__lte=hoy)),
        anterior=Count("pk", filter=Q(creado_en__date__gte=anterior, creado_en__date__lt=este)),
    )


def vencimientos_por_mes(hoy=None, meses=6):
    """Recetas vigentes cuyo último día válido cae en cada uno de los próximos `meses` meses, desde el actual.

    El último día válido es el anterior a `fecha_fin_exclusiva`, así que un mes cuenta las recetas cuya fecha de
    fin exclusiva está entre el día 2 de ese mes y el día 1 del siguiente.
    """
    hoy = hoy or timezone.localdate()
    primeros = [sumar_meses(hoy.replace(day=1), i) for i in range(meses + 1)]
    uno = timedelta(days=1)
    cuentas = Receta.objects.filter(condiciones(hoy)["vigente"]).aggregate(**{
        f"m{i}": Count("pk", filter=Q(fecha_fin_exclusiva__gte=primeros[i] + uno, fecha_fin_exclusiva__lt=primeros[i + 1] + uno))
        for i in range(meses)
    })
    return [(primeros[i], cuentas[f"m{i}"]) for i in range(meses)]
