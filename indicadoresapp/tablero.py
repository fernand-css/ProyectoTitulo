"""El dashboard de mermas y entregas (enmienda del 2026-11-25): junta las lecturas del período y arma las cifras.

`armar` devuelve un `Tablero` solo con cifras agregadas: lo usan la vista y los reportes, así que ningún
objeto de pacientes llega a las descargas. La comparación con el período anterior (RF-13-12) vuelve a leer el
período equivalente con las mismas funciones.
"""

from dataclasses import dataclass

from django.utils import timezone

from . import ausentes as ausentes_mod
from . import canales as canales_mod
from . import mermas
from .periodos import Periodo


def entero(valor):
    """10060 → «10.060»."""
    return f"{valor:,}".replace(",", ".")


def decimal(valor):
    """Un decimal con coma: 2.04 → «2,0»."""
    return f"{valor:.1f}".replace(".", ",")


@dataclass(frozen=True)
class Cifra:
    clave: str
    texto: str
    valor: str
    detalle: str
    comparacion: str
    tendencia: str     # "buena", "mala" o "" (igual o sin datos); el texto siempre lo dice con palabras
    sentido: str       # "sube", "baja" o "": solo para la flecha decorativa
    enlace: bool = False


@dataclass
class Tablero:
    periodo: Periodo
    anterior: Periodo
    resumen: mermas.Resumen
    canales: canales_mod.Canales
    ausentes: ausentes_mod.Ausentes
    cifras: list
    generado_en: object

    @property
    def tiene_datos(self):
        return bool(self.resumen.preparadas or self.resumen.total or self.canales.tiene_datos or self.ausentes.emitidos)


def _tendencia(diferencia, sube_es_bueno):
    if not diferencia:
        return "", ""
    return ("buena" if (diferencia > 0) == sube_es_bueno else "mala"), ("sube" if diferencia > 0 else "baja")


def _relativa(actual, anterior, rango, sube_es_bueno):
    if not anterior:
        if not actual:
            return f"Igual que {rango}", "", ""
        return f"{entero(actual)} más que {rango}", *_tendencia(actual, sube_es_bueno)
    cambio = 100 * (actual - anterior) / anterior
    if round(cambio, 1) == 0:
        return f"Igual que {rango}", "", ""
    return (f"{decimal(abs(cambio))} % {'más' if cambio > 0 else 'menos'} que {rango}",
            *_tendencia(cambio, sube_es_bueno))


def _puntos(actual, anterior, rango, sube_es_bueno):
    if actual is None or anterior is None:
        return "Sin datos para comparar con " + rango, "", ""
    cambio = round(actual - anterior, 1)
    if cambio == 0:
        return f"Igual que {rango}", "", ""
    palabra = "punto" if abs(cambio) == 1 else "puntos"
    return (f"{decimal(abs(cambio))} {palabra} {'más' if cambio > 0 else 'menos'} que {rango}",
            *_tendencia(cambio, sube_es_bueno))


def _absoluta(actual, anterior, rango, sube_es_bueno):
    cambio = actual - anterior
    if not cambio:
        return f"Igual que {rango}", "", ""
    return f"{entero(abs(cambio))} {'más' if cambio > 0 else 'menos'} que {rango}", *_tendencia(cambio, sube_es_bueno)


def _cifras(resumen, canales, resumen_ant, canales_ant, anterior):
    rango = anterior.rango
    hay_anterior = bool(resumen_ant.preparadas or resumen_ant.total or canales_ant.tiene_datos)
    sin_datos = ("Sin datos del período anterior", "", "")

    def comparar(funcion, actual, previo, sube_es_bueno):
        return funcion(actual, previo, rango, sube_es_bueno) if hay_anterior else sin_datos

    entregadas = comparar(_relativa, canales.entregadas, canales_ant.entregadas, True)
    merma = comparar(_puntos, resumen.merma_porcentaje, resumen_ant.merma_porcentaje, False)
    efectividad = comparar(_puntos, canales.efectividad_domicilio, canales_ant.efectividad_domicilio, True)
    estante = comparar(_absoluta, resumen.mas_de_14, resumen_ant.mas_de_14, False)
    sin_retirar = resumen.cifras[mermas.SIN_RETIRAR]
    return [
        Cifra("entregadas", "Recetas entregadas", entero(canales.entregadas),
              f"{entero(canales.farmacia_entregadas)} en farmacia y {entero(canales.domicilio_entregadas)} a domicilio",
              *entregadas),
        Cifra("merma", "Merma", entero(resumen.merma),
              (f"{decimal(resumen.merma_porcentaje)} % de {entero(resumen.preparadas)} recetas preparadas"
               if resumen.preparadas else "Sin recetas preparadas en el período"),
              *merma),
        Cifra("efectividad", "Efectividad a domicilio",
              f"{decimal(canales.efectividad_domicilio)} %" if canales.domicilio_total else "—",
              (f"{entero(canales.domicilio_entregadas)} de {entero(canales.domicilio_total)} recetas"
               if canales.domicilio_total else "Sin visitas en el período"),
              *efectividad),
        Cifra("estante", "En el estante más de 14 días", entero(resumen.mas_de_14),
              f"de {entero(sin_retirar)} receta{'s' if sin_retirar != 1 else ''} sin retirar", *estante, enlace=True),
    ]


def armar(periodo, hoy=None):
    hoy = hoy or timezone.localdate()
    anterior = periodo.anterior_equivalente()
    resumen = mermas.resumir(periodo, hoy)
    canales = canales_mod.resumir(periodo)
    resumen_ant = mermas.resumir(anterior, hoy)
    canales_ant = canales_mod.resumir(anterior)
    return Tablero(
        periodo=periodo, anterior=anterior, resumen=resumen, canales=canales,
        ausentes=ausentes_mod.resumir(periodo),
        cifras=_cifras(resumen, canales, resumen_ant, canales_ant, anterior),
        generado_en=timezone.localtime(),
    )
