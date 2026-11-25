"""Ausentes por día de la semana y hora (RF-13-19): lectura pura, solo cifras.

Cada turno del período se ubica por la hora local de emisión del número (`Turno.creado_en`) y cuenta como
ausente si hoy está «ausente»: los reincorporados que después se atendieron no cuentan. Las filas son lunes a
viernes, más sábado y domingo solo si hubo turnos; las columnas van de 8 a 19 h (hasta las 20:00) y se
amplían si hubo turnos fuera de ese horario.
"""

from dataclasses import dataclass
from math import ceil

from django.utils import timezone

from turnosapp.models import Turno

from .mermas import filtrar_tipo

DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
HORA_INICIO, HORA_FIN = 8, 20  # columnas de 8 a 19 h


@dataclass
class Ausentes:
    filas: list           # [{"dia", "celdas": [{"hora", "emitidos", "ausentes", "porcentaje", "nivel"}]}]
    horas: list           # [8, 9, ...]
    emitidos: int
    ausentes: int
    maximo: int
    por_dia: dict         # {fecha: (emitidos, ausentes)} para el CSV

    @property
    def porcentaje(self):
        return 100 * self.ausentes / self.emitidos if self.emitidos else None


def _nivel(valor, maximo):
    return 0 if not valor else min(5, max(1, ceil(5 * valor / maximo)))


def resumir(periodo):
    consulta = Turno.objects.filter(fecha__gte=periodo.inicio, fecha__lte=periodo.fin)
    consulta = filtrar_tipo(consulta, periodo, "paciente__es_cronico")
    celdas, por_dia = {}, {fecha: [0, 0] for fecha in periodo.dias_del_periodo()}
    for fecha, creado, estado in consulta.values_list("fecha", "creado_en", "estado"):
        local = timezone.localtime(creado)
        clave = (local.weekday(), local.hour)
        dato = celdas.setdefault(clave, [0, 0])
        ausente = estado == "ausente"
        dato[0] += 1
        dato[1] += ausente
        por_dia[fecha][0] += 1
        por_dia[fecha][1] += ausente
    horas_con_turnos = {hora for _, hora in celdas}
    horas = list(range(min([HORA_INICIO, *horas_con_turnos]), max([HORA_FIN - 1, *horas_con_turnos]) + 1))
    dias = [d for d in range(7) if d < 5 or any(dia == d for dia, _ in celdas)]
    maximo = max((ausentes for _, ausentes in celdas.values()), default=0)
    filas = []
    for dia in dias:
        fila = []
        for hora in horas:
            emitidos, ausentes = celdas.get((dia, hora), (0, 0))
            fila.append({"hora": hora, "emitidos": emitidos, "ausentes": ausentes,
                         "porcentaje": round(100 * ausentes / emitidos) if emitidos else None,
                         "nivel": _nivel(ausentes, maximo)})
        filas.append({"dia": DIAS[dia], "celdas": fila})
    return Ausentes(
        filas=filas, horas=horas, emitidos=sum(e for e, _ in celdas.values()),
        ausentes=sum(a for _, a in celdas.values()), maximo=maximo,
        por_dia={fecha: tuple(valores) for fecha, valores in por_dia.items()},
    )
