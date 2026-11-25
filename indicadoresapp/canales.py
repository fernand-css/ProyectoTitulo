"""Entregas por canal, motivos de no entrega y entregas por día (RF-13-14, RF-13-16 y RF-13-17): lectura pura.

La unidad es la receta en los dos canales; los motivos de domicilio cuentan visitas, porque el motivo se
registra por visita. Cada cifra usa su fecha:

- farmacia: las recetas de los turnos del período (fecha del turno) que ya cerraron; entregadas en esa atención
  o no. Se suman a las entregadas las confirmadas desde la ficha sin turno, por su fecha. Las retiradas después
  desde «Pendientes de retiro» se cuentan por la fecha del retiro en el gráfico diario;
- domicilio: las recetas de las visitas registradas en el período (fecha local del registro) como «Entregada» o
  «No entregada».

Todo se agrega en Python por fecha local, igual en SQLite y en PostgreSQL. Solo salen cifras, nunca datos
personales ni el texto libre de los motivos.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from recetasapp.models import EntregaReceta
from turnosapp.models import CausaNoEntrega, TurnoReceta

from .mermas import CIERRES, filtrar_tipo, limites
from .periodos import Periodo

ACTIVOS = ("esperando", "llamado")

# Motivos de farmacia (RF-13-16): los dos cierres del turno que no pasan por el formulario y las causas del RF-05-14.
MOTIVOS_FARMACIA = (
    ("ausente", "Paciente ausente"),
    ("sin_atencion_cierre", "Sin atención al cierre"),
    *CausaNoEntrega.choices,
)
# Encabezados del CSV: sin tildes y en minúsculas (RF-13-21; plan, «Columnas del CSV»).
COLUMNA_FARMACIA = {
    "ausente": "farmacia_paciente_ausente", "sin_atencion_cierre": "farmacia_sin_atencion_al_cierre",
    "sin_stock": "farmacia_sin_stock", "no_la_pide": "farmacia_paciente_no_la_pide",
    "no_vigente": "farmacia_receta_no_vigente", "cambio_indicacion": "farmacia_cambio_de_indicacion",
    "otro": "farmacia_otro",
}


def _motivos_domicilio():
    from entregasapp.models import IntentoEntrega
    return tuple(IntentoEntrega.Motivo.choices)


def _columna_domicilio(clave):
    return {"sin_receptor": "domicilio_sin_receptor", "domicilio_no_encontrado": "domicilio_domicilio_no_encontrado",
            "camino_intransitable": "domicilio_camino_intransitable", "rechazo": "domicilio_rechazo",
            "paciente_ausente": "domicilio_paciente_ausente", "otro": "domicilio_otro"}[clave]


@dataclass
class Dia:
    """Cifras de un día para el CSV, la hoja «Por día» y los gráficos diarios."""

    farmacia_atencion_o_ficha: int = 0
    farmacia_retiradas_despues: int = 0
    farmacia_no_entregadas: int = 0
    domicilio_entregadas: int = 0
    domicilio_no_entregadas: int = 0
    motivos_farmacia: dict = field(default_factory=dict)
    motivos_domicilio: dict = field(default_factory=dict)


@dataclass
class Canales:
    periodo: Periodo
    farmacia_entregadas: int
    farmacia_no_entregadas: int
    farmacia_retiradas_despues: int
    farmacia_en_espera: int            # recetas de turnos del período aún activos (nota de RF-13-14)
    domicilio_entregadas: int
    domicilio_no_entregadas: int
    domicilio_no_descontadas: int      # recetas no descontadas en visitas entregadas (frase de RF-13-16)
    motivos_farmacia: list             # [(clave, texto, cantidad)] en recetas
    motivos_domicilio: list            # [(clave, texto, cantidad)] en visitas
    por_dia: dict                      # {fecha: Dia} todos los días del período

    @property
    def farmacia_total(self):
        return self.farmacia_entregadas + self.farmacia_no_entregadas

    @property
    def domicilio_total(self):
        return self.domicilio_entregadas + self.domicilio_no_entregadas

    @property
    def entregadas(self):
        return self.farmacia_entregadas + self.domicilio_entregadas

    @property
    def no_entregadas(self):
        return self.farmacia_no_entregadas + self.domicilio_no_entregadas

    @property
    def total(self):
        return self.farmacia_total + self.domicilio_total

    @property
    def efectividad_domicilio(self):
        return 100 * self.domicilio_entregadas / self.domicilio_total if self.domicilio_total else None

    @property
    def visitas_fallidas(self):
        return sum(cantidad for _, _, cantidad in self.motivos_domicilio)

    @property
    def tiene_datos(self):
        return bool(self.total or self.farmacia_en_espera)


def _local(momento):
    return timezone.localtime(momento).date()


def _desde_ficha(periodo):
    """Entregas confirmadas desde la ficha de la receta, sin turno ni despacho, por fecha local."""
    from entregasapp.models import RecetaEntrega

    desde, hasta = limites(periodo)
    consulta = EntregaReceta.objects.filter(turno_receta__isnull=True, creado_en__gte=desde, creado_en__lt=hasta).exclude(
        Exists(RecetaEntrega.objects.filter(entrega_receta=OuterRef("pk"))))
    consulta = filtrar_tipo(consulta, periodo, "receta__paciente__es_cronico")
    return [_local(momento) for momento in consulta.values_list("creado_en", flat=True)]


def _retiros_posteriores(periodo):
    """Retiros desde «Pendientes de retiro» (entrega ligada al turno, fuera de su atención y sin despacho)."""
    from entregasapp.models import RecetaEntrega

    desde, hasta = limites(periodo)
    consulta = EntregaReceta.objects.filter(turno_receta__isnull=False, creado_en__gte=desde, creado_en__lt=hasta).exclude(
        detalle_cierre__entregada=True).exclude(Exists(RecetaEntrega.objects.filter(entrega_receta=OuterRef("pk"))))
    consulta = filtrar_tipo(consulta, periodo, "receta__paciente__es_cronico")
    return [_local(momento) for momento in consulta.values_list("creado_en", flat=True)]


def _vinculos(periodo):
    """Recetas de los turnos del período (fecha del turno), con su cierre y si se retiraron después."""
    from entregasapp.models import RecetaEntrega

    consulta = TurnoReceta.objects.filter(turno__fecha__gte=periodo.inicio, turno__fecha__lte=periodo.fin)
    consulta = filtrar_tipo(consulta, periodo, "turno__paciente__es_cronico")
    return consulta.annotate(
        con_entrega=Exists(EntregaReceta.objects.filter(turno_receta=OuterRef("pk"))),
        por_despacho=Exists(RecetaEntrega.objects.filter(
            entrega_receta__turno_receta=OuterRef("pk"), resultado=RecetaEntrega.Resultado.DESCONTADA)),
    ).values("turno__fecha", "turno__estado", "detalle_cierre__entregada", "detalle_cierre__causa",
             "con_entrega", "por_despacho")


def _visitas(periodo):
    """Visitas registradas en el período como «Entregada» o «No entregada», con las recetas que llevaban."""
    from entregasapp.models import IntentoEntrega, RecetaEntrega

    desde, hasta = limites(periodo)
    intentos = IntentoEntrega.objects.filter(
        registrado_en__gte=desde, registrado_en__lt=hasta,
        resultado__in=(IntentoEntrega.Resultado.ENTREGADA, IntentoEntrega.Resultado.NO_ENTREGADA))
    intentos = list(filtrar_tipo(intentos, periodo, "entrega__paciente__es_cronico").values(
        "entrega_id", "registrado_en", "resultado", "motivo"))
    recetas = {}
    for fila in RecetaEntrega.objects.filter(entrega_id__in={i["entrega_id"] for i in intentos}).values(
            "entrega_id", "resultado"):
        recetas.setdefault(fila["entrega_id"], []).append(fila["resultado"])
    return intentos, recetas


def farmacia_por_dia(periodo):
    """{fecha: entregas de farmacia} (en la atención o desde la ficha, más los retiros posteriores) del período.

    Se usa también para los 6 días anteriores, que completan el promedio de 7 días del primer día.
    """
    totales = dict.fromkeys(periodo.dias_del_periodo(), 0)
    for fila in _vinculos(periodo):
        if fila["detalle_cierre__entregada"]:
            totales[fila["turno__fecha"]] += 1
    for fecha in _desde_ficha(periodo) + _retiros_posteriores(periodo):
        totales[fecha] += 1
    return totales


def resumir(periodo):
    from entregasapp.models import IntentoEntrega, RecetaEntrega

    dias = {fecha: Dia() for fecha in periodo.dias_del_periodo()}
    motivos_f = dict.fromkeys((clave for clave, _ in MOTIVOS_FARMACIA), 0)
    f_entregadas = f_no = f_despues = f_espera = 0
    for fila in _vinculos(periodo):
        estado, fecha = fila["turno__estado"], fila["turno__fecha"]
        if estado in ACTIVOS:
            f_espera += 1
            continue
        if estado not in CIERRES:
            continue
        if fila["detalle_cierre__entregada"]:
            f_entregadas += 1
            dias[fecha].farmacia_atencion_o_ficha += 1
            continue
        f_no += 1
        dias[fecha].farmacia_no_entregadas += 1
        if fila["con_entrega"] and not fila["por_despacho"]:
            f_despues += 1
        if estado in ("ausente", "sin_atencion_cierre"):
            motivo = estado
        else:
            # RF-05-14: los cierres anteriores a la enmienda no tienen causa y cuentan como «Otro».
            motivo = fila["detalle_cierre__causa"] or CausaNoEntrega.OTRO.value
        motivos_f[motivo] += 1
        dias[fecha].motivos_farmacia[motivo] = dias[fecha].motivos_farmacia.get(motivo, 0) + 1
    for fecha in _desde_ficha(periodo):
        f_entregadas += 1
        dias[fecha].farmacia_atencion_o_ficha += 1
    for fecha in _retiros_posteriores(periodo):
        dias[fecha].farmacia_retiradas_despues += 1

    intentos, recetas = _visitas(periodo)
    motivos_d = dict.fromkeys((clave for clave, _ in _motivos_domicilio()), 0)
    d_entregadas = d_no = d_no_descontadas = 0
    for intento in intentos:
        fecha = _local(intento["registrado_en"])
        resultados = recetas.get(intento["entrega_id"], [])
        if intento["resultado"] == IntentoEntrega.Resultado.ENTREGADA:
            buenas = sum(1 for r in resultados if r == RecetaEntrega.Resultado.DESCONTADA)
            malas = sum(1 for r in resultados if r == RecetaEntrega.Resultado.NO_DESCONTADA)
            d_no_descontadas += malas
        else:
            buenas, malas = 0, len(resultados)
            motivo = intento["motivo"] or IntentoEntrega.Motivo.OTRO.value
            motivos_d[motivo] += 1
            dias[fecha].motivos_domicilio[motivo] = dias[fecha].motivos_domicilio.get(motivo, 0) + 1
        d_entregadas += buenas
        d_no += malas
        dias[fecha].domicilio_entregadas += buenas
        dias[fecha].domicilio_no_entregadas += malas

    return Canales(
        periodo=periodo, farmacia_entregadas=f_entregadas, farmacia_no_entregadas=f_no,
        farmacia_retiradas_despues=f_despues, farmacia_en_espera=f_espera,
        domicilio_entregadas=d_entregadas, domicilio_no_entregadas=d_no, domicilio_no_descontadas=d_no_descontadas,
        motivos_farmacia=[(clave, texto, motivos_f[clave]) for clave, texto in MOTIVOS_FARMACIA],
        motivos_domicilio=[(clave, texto, motivos_d[clave]) for clave, texto in _motivos_domicilio()],
        por_dia=dias,
    )


def promedios_farmacia(periodo, canales, ventana=7):
    """Promedio de `ventana` días de las entregas de farmacia, alineado con los días del período (RF-13-17)."""
    previo = Periodo(periodo.inicio - timedelta(days=ventana - 1), periodo.inicio - timedelta(days=1), periodo.tipo)
    anteriores = list(farmacia_por_dia(previo).values())
    del_periodo = [dia.farmacia_atencion_o_ficha + dia.farmacia_retiradas_despues for dia in canales.por_dia.values()]
    valores = anteriores + del_periodo
    return [sum(valores[i:i + ventana]) / ventana for i in range(len(del_periodo))]


def columnas_csv():
    """Encabezados del CSV y de la hoja «Por día», en el orden del plan."""
    return [
        "fecha", "farmacia_entregadas_atencion_o_ficha", "farmacia_retiradas_despues", "farmacia_no_entregadas",
        "domicilio_entregadas", "domicilio_no_entregadas", "merma", "turnos_emitidos", "turnos_ausentes",
        *(COLUMNA_FARMACIA[clave] for clave, _ in MOTIVOS_FARMACIA),
        *(_columna_domicilio(clave) for clave, _ in _motivos_domicilio()),
    ]


def fila_csv(fecha, dia, merma, emitidos, ausentes):
    return [
        f"{fecha:%Y-%m-%d}", dia.farmacia_atencion_o_ficha, dia.farmacia_retiradas_despues, dia.farmacia_no_entregadas,
        dia.domicilio_entregadas, dia.domicilio_no_entregadas, merma, emitidos, ausentes,
        *(dia.motivos_farmacia.get(clave, 0) for clave, _ in MOTIVOS_FARMACIA),
        *(dia.motivos_domicilio.get(clave, 0) for clave, _ in _motivos_domicilio()),
    ]
