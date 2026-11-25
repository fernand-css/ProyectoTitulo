"""Panel de mermas (spec 13): lectura pura, sin escrituras.

Una receta cuenta si su preparación quedó lista y su turno cerró sin que se entregara en esa atención (RF-13-01),
igual que «Pendientes de retiro» del 07. Cada una está en uno solo de cuatro estados:

- «sin_retirar»: sin entrega y sin despacho abierto;
- «en_despacho»: sin entrega, en una entrega a domicilio abierta (derivada desde «Pendientes de retiro»);
- «tarde»: entregada después en farmacia, desde «Pendientes de retiro»;
- «despacho»: entregada por el reparto, con su preparación.

La merma es «sin_retirar» + «en_despacho»; las recuperadas, las otras dos. El estado se calcula al consultar.
Las filas se agregan en Python: son pocas por día y así el cálculo es el mismo en SQLite y en PostgreSQL.
Desde la enmienda del 2026-11-25 el resumen no lleva el detalle por paciente: el panel no muestra datos personales.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from recetasapp.models import EntregaReceta, PreparacionReceta

from .periodos import (  # noqa: F401  (se reexportan para los demás módulos del panel)
    CRONICO, DIAS_MAXIMOS, DIAS_POR_DIA, GENERAL, TIPOS, TIPOS_TEXTO, TODOS, Periodo, periodo_por_omision,
)

CIERRES = ("ausente", "sin_atencion_cierre", "atendido", "cerrado_sin_entrega")

SIN_RETIRAR = "sin_retirar"
EN_DESPACHO = "en_despacho"
TARDE = "tarde"
DESPACHO = "despacho"
ESTADOS = (
    (SIN_RETIRAR, "Sin retirar"),
    (EN_DESPACHO, "En despacho"),
    (TARDE, "Retiradas tarde en farmacia"),
    (DESPACHO, "Entregadas por despacho"),
)
MERMA = (SIN_RETIRAR, EN_DESPACHO)

# Días que lleva en el estante una receta sin retirar, contados desde su preparación hasta hoy.
ESPERAS = ((0, 2, "0 a 2 días"), (3, 7, "3 a 7 días"), (8, 14, "8 a 14 días"), (15, 30, "15 a 30 días"),
           (31, None, "Más de 30 días"))
TRAMOS_MAS_DE_14 = (3, 4)  # índices de ESPERAS con más de 14 días


def limites(periodo):
    """Instantes locales [desde, hasta) del período, para filtrar campos de fecha y hora."""
    zona = timezone.get_current_timezone()
    desde = timezone.make_aware(datetime.combine(periodo.inicio, time.min), zona)
    hasta = timezone.make_aware(datetime.combine(periodo.fin + timedelta(days=1), time.min), zona)
    return desde, hasta


_limites = limites  # nombre anterior


def filtrar_tipo(consulta, periodo, campo):
    """Aplica el tipo de paciente sobre `campo` (la ruta hasta `es_cronico`)."""
    if periodo.tipo == CRONICO:
        return consulta.filter(**{campo: True})
    if periodo.tipo == GENERAL:
        return consulta.filter(**{campo: False})
    return consulta


def _listas_cerradas(periodo):
    desde, hasta = limites(periodo)
    consulta = PreparacionReceta.objects.filter(
        lista_en__isnull=False, lista_en__gte=desde, lista_en__lt=hasta,
        turno_receta__turno__estado__in=CIERRES,
    )
    return filtrar_tipo(consulta, periodo, "turno_receta__receta__paciente__es_cronico")


def preparaciones(periodo):
    """Preparaciones del período (por fecha local de preparación) que cuentan para la merma, con su estado."""
    from entregasapp.models import Entrega, RecetaEntrega

    consulta = _listas_cerradas(periodo).exclude(
        # Entregada dentro de la misma atención: no es merma ni recuperación.
        turno_receta__detalle_cierre__entregada=True,
    )
    return consulta.annotate(
        entregada=Exists(EntregaReceta.objects.filter(turno_receta=OuterRef("turno_receta"))),
        por_despacho=Exists(RecetaEntrega.objects.filter(
            preparacion=OuterRef("pk"), resultado=RecetaEntrega.Resultado.DESCONTADA,
        )),
        en_despacho=Exists(RecetaEntrega.objects.filter(preparacion=OuterRef("pk"), entrega__estado__in=Entrega.ABIERTAS)),
    )


def entregadas_en_la_atencion(periodo):
    """Preparaciones listas del período que se entregaron en su misma atención (RF-13-18)."""
    return _listas_cerradas(periodo).filter(turno_receta__detalle_cierre__entregada=True).count()


def estado_de(fila):
    if fila["por_despacho"]:
        return DESPACHO
    if fila["entregada"]:
        return TARDE
    if fila["en_despacho"]:
        return EN_DESPACHO
    return SIN_RETIRAR


@dataclass
class Resumen:
    periodo: Periodo
    cifras: dict
    merma: int
    recuperadas: int
    serie: list                      # [(clave de la serie, merma)] por día, semana o mes
    por_tipo: list                   # [(clave, texto, merma)]
    por_estado: list                 # [(clave, texto, cantidad)] los cuatro estados
    en_atencion: int = 0             # preparadas y entregadas en la misma atención
    merma_por_dia: dict = field(default_factory=dict)  # {fecha: merma} para el CSV
    espera: list = field(default_factory=list)     # [(texto, cantidad)] las «sin_retirar» por días en el estante
    por_dia_semana: list = field(default_factory=lambda: [0] * 7)  # merma por día de la semana, lunes primero

    @property
    def total(self):
        """Preparadas y no entregadas en la atención (merma + recuperadas)."""
        return self.merma + self.recuperadas

    @property
    def preparadas(self):
        """Todas las preparaciones listas del período cuyo turno cerró."""
        return self.total + self.en_atencion

    @property
    def merma_porcentaje(self):
        return 100 * self.merma / self.preparadas if self.preparadas else None

    @property
    def mas_de_14(self):
        return sum(self.espera[i][1] for i in TRAMOS_MAS_DE_14) if self.espera else 0

    @property
    def granularidad(self):
        return self.periodo.granularidad

    @property
    def por_semana(self):
        return self.periodo.por_semana


def _tramo_de_espera(dias):
    for i, (desde, hasta, _) in enumerate(ESPERAS):
        if dias >= desde and (hasta is None or dias <= hasta):
            return i
    return 0


def resumir(periodo, hoy=None):
    """Cifras y series de la merma del período, en una lectura de la base (más el conteo de lo entregado)."""
    hoy = hoy or timezone.localdate()
    filas = preparaciones(periodo).values(
        "lista_en", "turno_receta__receta__paciente__es_cronico", "entregada", "por_despacho", "en_despacho",
    )
    serie = dict.fromkeys(periodo.claves(), 0)
    merma_por_dia = dict.fromkeys(periodo.dias_del_periodo(), 0)
    cifras = dict.fromkeys((clave for clave, _ in ESTADOS), 0)
    tipos = {CRONICO: 0, GENERAL: 0}
    espera = [0] * len(ESPERAS)
    por_dia_semana = [0] * 7
    for fila in filas:
        estado = estado_de(fila)
        cifras[estado] += 1
        if estado not in MERMA:
            continue
        fecha = timezone.localtime(fila["lista_en"]).date()
        serie[periodo.clave(fecha)] += 1
        merma_por_dia[fecha] += 1
        por_dia_semana[fecha.weekday()] += 1
        if estado == SIN_RETIRAR:
            espera[_tramo_de_espera((hoy - fecha).days)] += 1
        tipos[CRONICO if fila["turno_receta__receta__paciente__es_cronico"] else GENERAL] += 1
    merma = cifras[SIN_RETIRAR] + cifras[EN_DESPACHO]
    return Resumen(
        periodo=periodo, cifras=cifras, merma=merma, recuperadas=cifras[TARDE] + cifras[DESPACHO],
        serie=list(serie.items()),
        por_tipo=[(CRONICO, "Crónico", tipos[CRONICO]), (GENERAL, "General", tipos[GENERAL])],
        por_estado=[(clave, texto, cifras[clave]) for clave, texto in ESTADOS],
        en_atencion=entregadas_en_la_atencion(periodo),
        merma_por_dia=merma_por_dia,
        espera=[(texto, espera[i]) for i, (_, _, texto) in enumerate(ESPERAS)],
        por_dia_semana=por_dia_semana,
    )
