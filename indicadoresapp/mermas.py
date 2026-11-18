"""Panel de mermas (spec 13): lectura pura, sin escrituras.

Una receta cuenta si su preparación quedó lista y su turno cerró sin que se entregara en esa atención (RF-13-01),
igual que «Pendientes de retiro» del 07. Cada una está en uno solo de cuatro estados:

- «sin_retirar»: sin entrega y sin despacho abierto;
- «en_despacho»: sin entrega, en una entrega a domicilio abierta (derivada desde este panel);
- «tarde»: entregada después en farmacia, desde «Pendientes de retiro»;
- «despacho»: entregada por el reparto, con su preparación.

La merma es «sin_retirar» + «en_despacho»; las recuperadas, las otras dos. El estado se calcula al consultar.
Las filas se agregan en Python: son pocas por día y así el cálculo es el mismo en SQLite y en PostgreSQL.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from recetasapp.models import EntregaReceta, Paciente, PreparacionReceta

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

CIERRES_TEXTO = (
    ("ausente", "Paciente ausente"),
    ("atendido", "Atendido, sin entregar esa receta"),
    ("cerrado_sin_entrega", "Cerrado sin entrega"),
    ("sin_atencion_cierre", "Sin atención al cierre"),
)

TODOS = "todos"
CRONICO = "cronico"
GENERAL = "general"
TIPOS = ((TODOS, "Todos"), (CRONICO, "Crónico"), (GENERAL, "General"))
TIPOS_TEXTO = dict(TIPOS)

DIAS_POR_OMISION = 30
DIAS_MAXIMOS = 366
DIAS_POR_DIA = 31  # hasta este largo la evolución va por día; con más, por semana (lunes a domingo)
POR_PAGINA = 50

# Días que lleva en el estante una receta sin retirar, contados desde su preparación hasta hoy.
ESPERAS = ((0, 2, "0 a 2 días"), (3, 7, "3 a 7 días"), (8, 14, "8 a 14 días"), (15, 30, "15 a 30 días"),
           (31, None, "Más de 30 días"))


@dataclass(frozen=True)
class Periodo:
    inicio: object
    fin: object
    tipo: str = TODOS

    @property
    def dias(self):
        return (self.fin - self.inicio).days + 1

    @property
    def tipo_texto(self):
        return TIPOS_TEXTO[self.tipo]


def periodo_por_omision(hoy=None):
    """Los últimos 30 días, hoy incluido, y todos los pacientes."""
    hoy = hoy or timezone.localdate()
    return Periodo(hoy - timedelta(days=DIAS_POR_OMISION - 1), hoy, TODOS)


def _limites(periodo):
    zona = timezone.get_current_timezone()
    desde = timezone.make_aware(datetime.combine(periodo.inicio, time.min), zona)
    hasta = timezone.make_aware(datetime.combine(periodo.fin + timedelta(days=1), time.min), zona)
    return desde, hasta


def preparaciones(periodo):
    """Preparaciones del período (por fecha local de preparación) que cuentan para el panel, con su estado."""
    from entregasapp.models import Entrega, RecetaEntrega

    desde, hasta = _limites(periodo)
    consulta = PreparacionReceta.objects.filter(
        lista_en__isnull=False, lista_en__gte=desde, lista_en__lt=hasta,
        turno_receta__turno__estado__in=CIERRES,
    ).exclude(
        # Entregada dentro de la misma atención: no es merma ni recuperación.
        turno_receta__detalle_cierre__entregada=True,
    )
    if periodo.tipo == CRONICO:
        consulta = consulta.filter(turno_receta__receta__paciente__es_cronico=True)
    elif periodo.tipo == GENERAL:
        consulta = consulta.filter(turno_receta__receta__paciente__es_cronico=False)
    return consulta.annotate(
        entregada=Exists(EntregaReceta.objects.filter(turno_receta=OuterRef("turno_receta"))),
        por_despacho=Exists(RecetaEntrega.objects.filter(
            preparacion=OuterRef("pk"), resultado=RecetaEntrega.Resultado.DESCONTADA,
        )),
        en_despacho=Exists(RecetaEntrega.objects.filter(preparacion=OuterRef("pk"), entrega__estado__in=Entrega.ABIERTAS)),
    )


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
    por_semana: bool
    serie: list                      # [(fecha del día o lunes de la semana, merma)]
    por_tipo: list                   # [(clave, texto, merma)]
    por_cierre: list                 # [(clave, texto, merma)]
    por_estado: list                 # [(clave, texto, cantidad)] los cuatro estados
    pacientes: list = field(default_factory=list)  # [{paciente_id, sin_retirar, en_despacho, mas_antigua}]
    espera: list = field(default_factory=list)     # [(texto, cantidad)] las «sin_retirar» por días en el estante
    por_dia_semana: list = field(default_factory=lambda: [0] * 7)  # merma por día de la semana, lunes primero

    @property
    def total(self):
        return self.merma + self.recuperadas


def _clave_serie(fecha, por_semana):
    if not por_semana:
        return fecha
    return fecha - timedelta(days=fecha.weekday())


def _tramo_de_espera(dias):
    for i, (desde, hasta, _) in enumerate(ESPERAS):
        if dias >= desde and (hasta is None or dias <= hasta):
            return i
    return 0


def resumir(periodo, hoy=None):
    """Cifras, series y detalle por paciente del período, en una sola lectura de la base."""
    hoy = hoy or timezone.localdate()
    filas = preparaciones(periodo).values(
        "lista_en", "turno_receta__turno__estado", "turno_receta__receta__paciente_id",
        "turno_receta__receta__paciente__es_cronico", "entregada", "por_despacho", "en_despacho",
    )
    por_semana = periodo.dias > DIAS_POR_DIA
    if por_semana:
        primero = periodo.inicio - timedelta(days=periodo.inicio.weekday())
        claves = []
        actual = primero
        while actual <= periodo.fin:
            claves.append(actual)
            actual += timedelta(days=7)
    else:
        claves = [periodo.inicio + timedelta(days=i) for i in range(periodo.dias)]
    serie = dict.fromkeys(claves, 0)
    cifras = dict.fromkeys((clave for clave, _ in ESTADOS), 0)
    tipos = {CRONICO: 0, GENERAL: 0}
    cierres = dict.fromkeys((clave for clave, _ in CIERRES_TEXTO), 0)
    pacientes = {}
    espera = [0] * len(ESPERAS)
    por_dia_semana = [0] * 7
    for fila in filas:
        estado = estado_de(fila)
        cifras[estado] += 1
        if estado not in MERMA:
            continue
        fecha = timezone.localtime(fila["lista_en"]).date()
        serie[_clave_serie(fecha, por_semana)] += 1
        por_dia_semana[fecha.weekday()] += 1
        if estado == SIN_RETIRAR:
            espera[_tramo_de_espera((hoy - fecha).days)] += 1
        tipos[CRONICO if fila["turno_receta__receta__paciente__es_cronico"] else GENERAL] += 1
        cierres[fila["turno_receta__turno__estado"]] += 1
        paciente_id = fila["turno_receta__receta__paciente_id"]
        dato = pacientes.setdefault(paciente_id, {
            "paciente_id": paciente_id, SIN_RETIRAR: 0, EN_DESPACHO: 0, "mas_antigua": fecha,
        })
        dato[estado] += 1
        dato["mas_antigua"] = min(dato["mas_antigua"], fecha)
    merma = cifras[SIN_RETIRAR] + cifras[EN_DESPACHO]
    return Resumen(
        periodo=periodo, cifras=cifras, merma=merma, recuperadas=cifras[TARDE] + cifras[DESPACHO],
        por_semana=por_semana, serie=list(serie.items()),
        por_tipo=[(CRONICO, "Crónico", tipos[CRONICO]), (GENERAL, "General", tipos[GENERAL])],
        por_cierre=[(clave, texto, cierres[clave]) for clave, texto in CIERRES_TEXTO],
        por_estado=[(clave, texto, cifras[clave]) for clave, texto in ESTADOS],
        pacientes=sorted(pacientes.values(), key=lambda dato: (dato["mas_antigua"], dato["paciente_id"])),
        espera=[(texto, espera[i]) for i, (_, _, texto) in enumerate(ESPERAS)],
        por_dia_semana=por_dia_semana,
    )


def pacientes_de_la_pagina(datos):
    """Completa una página del detalle con su paciente y si es elegible para el reparto (RF-13-04)."""
    from entregasapp.consultas import motivos_de

    hoy = timezone.localdate()
    por_id = Paciente.objects.in_bulk([dato["paciente_id"] for dato in datos])
    filas = []
    for dato in datos:
        paciente = por_id.get(dato["paciente_id"])
        if paciente is None:
            continue
        motivos = motivos_de(paciente, hoy)
        filas.append({
            **dato, "paciente": paciente, "motivos": motivos, "dias": (hoy - dato["mas_antigua"]).days,
            "elegible": ", ".join(motivos) if motivos else "No elegible",
        })
    return filas
