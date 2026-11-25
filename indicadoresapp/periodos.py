"""Períodos del panel de mermas (RF-13-11 y RF-13-12): ocho clases, flechas, granularidad y comparación.

Lectura pura, sin datos personales: el período viaja por GET con su clase, una fecha de referencia o el rango
propio y el tipo de paciente. 1, 3, 7 y 14 días terminan hoy; Mes, Semestre y Año son de calendario y se
recorren con «‹» y «›»; Personalizado es un rango de hasta 366 días.
"""

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date, timedelta

from django import forms
from django.utils import timezone

TODOS = "todos"
CRONICO = "cronico"
GENERAL = "general"
TIPOS = ((TODOS, "Todos"), (CRONICO, "Crónico"), (GENERAL, "General"))
TIPOS_TEXTO = dict(TIPOS)

UN_DIA, TRES_DIAS, SIETE_DIAS, CATORCE_DIAS = "1d", "3d", "7d", "14d"
MES, SEMESTRE, ANIO, PERSONALIZADO = "mes", "semestre", "anio", "personalizado"
MOVILES = {UN_DIA: 1, TRES_DIAS: 3, SIETE_DIAS: 7, CATORCE_DIAS: 14}
CALENDARIO = (MES, SEMESTRE, ANIO)
CLASES = (
    (UN_DIA, "1 día"), (TRES_DIAS, "3 días"), (SIETE_DIAS, "7 días"), (CATORCE_DIAS, "14 días"),
    (MES, "Mes"), (SEMESTRE, "Semestre"), (ANIO, "Año"), (PERSONALIZADO, "Personalizado"),
)
CLASE_POR_OMISION = MES
DIAS_MAXIMOS = 366
DIAS_POR_DIA = 31      # hasta este largo, la serie va por día
DIAS_POR_SEMANA = 186  # hasta este largo, por semana; con más, por mes

DIA, SEMANA, MES_SERIE = "dia", "semana", "mes"

MESES_LARGOS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                "octubre", "noviembre", "diciembre")


def _fin_de_mes(fecha):
    return fecha.replace(day=monthrange(fecha.year, fecha.month)[1])


def _sumar_meses(fecha, meses):
    total = fecha.year * 12 + fecha.month - 1 + meses
    return date(total // 12, total % 12 + 1, 1)


def _inicio_de(clase, fecha):
    if clase == MES:
        return fecha.replace(day=1)
    if clase == SEMESTRE:
        return date(fecha.year, 1 if fecha.month <= 6 else 7, 1)
    return date(fecha.year, 1, 1)


def _meses_de(clase):
    return {MES: 1, SEMESTRE: 6, ANIO: 12}[clase]


def _fin_natural(clase, inicio):
    """Último día del mes, semestre o año que empieza en `inicio`."""
    return _sumar_meses(inicio, _meses_de(clase)) - timedelta(days=1)


def fecha_texto(fecha, con_anio=True):
    texto = f"{fecha.day} de {MESES_LARGOS[fecha.month - 1]}"
    return f"{texto} de {fecha.year}" if con_anio else texto


def rango_texto(inicio, fin):
    """«del 1 al 25 de noviembre de 2026», «del 28 de octubre al 3 de noviembre de 2026» o con dos años."""
    if inicio == fin:
        return f"el {fecha_texto(inicio)}"
    if inicio.year != fin.year:
        return f"del {fecha_texto(inicio)} al {fecha_texto(fin)}"
    if inicio.month != fin.month:
        return f"del {fecha_texto(inicio, con_anio=False)} al {fecha_texto(fin)}"
    return f"del {inicio.day} al {fecha_texto(fin)}"


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fin: date
    tipo: str = TODOS
    clase: str = PERSONALIZADO

    @property
    def dias(self):
        return (self.fin - self.inicio).days + 1

    @property
    def tipo_texto(self):
        return TIPOS_TEXTO[self.tipo]

    @property
    def clase_texto(self):
        return dict(CLASES)[self.clase]

    @property
    def granularidad(self):
        """Mes va por día, Semestre por semana y Año por mes; el resto, según su largo."""
        if self.clase == MES:
            return DIA
        if self.clase == SEMESTRE:
            return SEMANA
        if self.clase == ANIO:
            return MES_SERIE
        if self.dias <= DIAS_POR_DIA:
            return DIA
        return SEMANA if self.dias <= DIAS_POR_SEMANA else MES_SERIE

    @property
    def por_semana(self):
        return self.granularidad == SEMANA

    def clave(self, fecha):
        """Fecha que representa a `fecha` en la serie: el día, el lunes de su semana o el 1 de su mes."""
        if self.granularidad == SEMANA:
            return fecha - timedelta(days=fecha.weekday())
        if self.granularidad == MES_SERIE:
            return fecha.replace(day=1)
        return fecha

    def claves(self):
        """Todas las claves de la serie del período, en orden y sin huecos."""
        claves, actual = [], self.clave(self.inicio)
        while actual <= self.fin:
            claves.append(actual)
            if self.granularidad == SEMANA:
                actual += timedelta(days=7)
            elif self.granularidad == MES_SERIE:
                actual = _sumar_meses(actual, 1)
            else:
                actual += timedelta(days=1)
        return claves

    def dias_del_periodo(self):
        return [self.inicio + timedelta(days=i) for i in range(self.dias)]

    # Navegación (solo Mes, Semestre y Año) ---------------------------------------------------------------

    def anterior(self):
        if self.clase not in CALENDARIO:
            return None
        inicio = _sumar_meses(self.inicio, -_meses_de(self.clase))
        return replace(self, inicio=inicio, fin=_fin_natural(self.clase, inicio))

    def siguiente(self, hoy=None):
        if self.clase not in CALENDARIO:
            return None
        hoy = hoy or timezone.localdate()
        inicio = _sumar_meses(self.inicio, _meses_de(self.clase))
        if inicio > hoy:
            return None
        return replace(self, inicio=inicio, fin=min(_fin_natural(self.clase, inicio), hoy))

    def anterior_equivalente(self):
        """RF-13-12: los N días anteriores, o los mismos días desde el inicio del mes, semestre o año anterior."""
        if self.clase in CALENDARIO:
            inicio = _sumar_meses(self.inicio, -_meses_de(self.clase))
            fin = min(inicio + timedelta(days=self.dias - 1), _fin_natural(self.clase, inicio))
            return replace(self, inicio=inicio, fin=fin)
        fin = self.inicio - timedelta(days=1)
        return replace(self, inicio=fin - timedelta(days=self.dias - 1), fin=fin)

    # Textos ----------------------------------------------------------------------------------------------

    @property
    def completo(self):
        """Si el mes, semestre o año llega hasta su último día (no está cortado en hoy)."""
        return self.clase in CALENDARIO and self.fin == _fin_natural(self.clase, self.inicio)

    @property
    def titulo(self):
        if self.clase == UN_DIA:
            return f"Hoy, {fecha_texto(self.fin)}"
        if self.clase in MOVILES:
            return f"Últimos {self.dias} días: {rango_texto(self.inicio, self.fin)}"
        if self.clase == MES:
            nombre = f"{MESES_LARGOS[self.inicio.month - 1].capitalize()} de {self.inicio.year}"
            return nombre if self.completo else f"{nombre}, del 1 al {self.fin.day}"
        if self.clase == SEMESTRE:
            nombre = f"{'Primer' if self.inicio.month == 1 else 'Segundo'} semestre de {self.inicio.year}"
        elif self.clase == ANIO:
            nombre = f"Año {self.inicio.year}"
        else:
            texto = rango_texto(self.inicio, self.fin)
            return texto[0].upper() + texto[1:]
        return nombre if self.completo else f"{nombre}, hasta el {fecha_texto(self.fin, con_anio=False)}"

    @property
    def rango(self):
        return rango_texto(self.inicio, self.fin)

    # GET -------------------------------------------------------------------------------------------------

    def parametros(self):
        """Parámetros GET del período (sin datos personales), en un orden fijo."""
        partes = [("periodo", self.clase)]
        if self.clase in CALENDARIO:
            partes.append(("ref", f"{self.inicio:%Y-%m-%d}"))
        elif self.clase == PERSONALIZADO:
            partes += [("desde", f"{self.inicio:%Y-%m-%d}"), ("hasta", f"{self.fin:%Y-%m-%d}")]
        partes.append(("tipo", self.tipo))
        return partes

    def consulta(self, extra=None):
        partes = self.parametros() + list((extra or {}).items())
        return "?" + "&".join(f"{clave}={valor}" for clave, valor in partes)


def periodo_de(clase, hoy=None, tipo=TODOS, ref=None):
    """El período de una clase: el que contiene hoy (o `ref`), cortado en hoy."""
    hoy = hoy or timezone.localdate()
    if clase in MOVILES:
        return Periodo(hoy - timedelta(days=MOVILES[clase] - 1), hoy, tipo, clase)
    if clase in CALENDARIO:
        inicio = _inicio_de(clase, ref or hoy)
        return Periodo(inicio, min(_fin_natural(clase, inicio), hoy), tipo, clase)
    raise ValueError(clase)


def periodo_por_omision(hoy=None, tipo=TODOS):
    """El mes en curso, cortado en hoy, y todos los pacientes."""
    return periodo_de(CLASE_POR_OMISION, hoy, tipo)


FECHA = {"type": "date"}


class FiltroPanelForm(forms.Form):
    periodo = forms.ChoiceField(label="Período", required=False, choices=CLASES)
    ref = forms.DateField(required=False, widget=forms.HiddenInput)
    desde = forms.DateField(label="Desde", required=False, widget=forms.DateInput(attrs=FECHA, format="%Y-%m-%d"))
    hasta = forms.DateField(label="Hasta", required=False, widget=forms.DateInput(attrs=FECHA, format="%Y-%m-%d"))
    tipo = forms.ChoiceField(label="Tipo de paciente", required=False, choices=TIPOS)

    def __init__(self, *args, hoy=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hoy = hoy or timezone.localdate()

    def clean(self):
        datos = super().clean()
        if self.errors:
            return datos
        hoy = self.hoy
        tipo = datos.get("tipo") or TODOS
        clase = datos.get("periodo") or ""
        desde, hasta = datos.get("desde"), datos.get("hasta")
        if not clase:
            # Enlaces anteriores a la enmienda: `desde` y `hasta` sin clase abren como «Personalizado».
            clase = PERSONALIZADO if (desde or hasta) else CLASE_POR_OMISION
        if clase == PERSONALIZADO:
            hasta = hasta or hoy
            desde = desde or hasta - timedelta(days=29)
            if hasta > hoy:
                raise forms.ValidationError("La fecha «Hasta» no puede ser posterior a hoy.")
            if desde > hasta:
                raise forms.ValidationError("La fecha «Desde» debe ser anterior o igual a «Hasta».")
            if (hasta - desde).days + 1 > DIAS_MAXIMOS:
                raise forms.ValidationError(f"El período admite hasta {DIAS_MAXIMOS} días.")
            datos["resultado"] = Periodo(desde, hasta, tipo, PERSONALIZADO)
            return datos
        ref = datos.get("ref")
        if clase in CALENDARIO and ref and _inicio_de(clase, ref) > hoy:
            raise forms.ValidationError("Ese período todavía no comienza.")
        datos["resultado"] = periodo_de(clase, hoy, tipo, ref if clase in CALENDARIO else None)
        return datos

    def elegido(self):
        """El período pedido (el método no se llama `periodo` para no tapar el campo); con datos inválidos (o sin datos), el «Mes» en curso con el tipo pedido si es válido."""
        if self.is_bound and self.is_valid():
            return self.cleaned_data["resultado"]
        tipo = self.data.get("tipo") if self.is_bound and self.data.get("tipo") in TIPOS_TEXTO else TODOS
        return periodo_por_omision(self.hoy, tipo)


def opciones(periodo, hoy=None):
    """Los ocho botones de período, con su enlace (mismo tipo) y si es el elegido."""
    hoy = hoy or timezone.localdate()
    botones = []
    for clase, texto in CLASES:
        if clase == PERSONALIZADO:
            destino = periodo if periodo.clase == PERSONALIZADO else Periodo(
                hoy - timedelta(days=29), hoy, periodo.tipo, PERSONALIZADO)
        else:
            destino = periodo_de(clase, hoy, periodo.tipo)
        botones.append({"clase": clase, "texto": texto, "url": destino.consulta(), "actual": clase == periodo.clase})
    return botones
