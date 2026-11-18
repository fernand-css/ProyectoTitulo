"""Filtros del panel de mermas (RF-13-02): por GET, sin datos personales."""

from datetime import timedelta

from django import forms
from django.utils import timezone

from .mermas import DIAS_MAXIMOS, TIPOS, TODOS, Periodo, periodo_por_omision

FECHA = {"type": "date"}


class FiltroMermasForm(forms.Form):
    desde = forms.DateField(label="Desde", required=False, widget=forms.DateInput(attrs=FECHA, format="%Y-%m-%d"))
    hasta = forms.DateField(label="Hasta", required=False, widget=forms.DateInput(attrs=FECHA, format="%Y-%m-%d"))
    tipo = forms.ChoiceField(label="Tipo de paciente", required=False, choices=TIPOS)
    pagina = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)

    def clean(self):
        datos = super().clean()
        if self.errors:
            return datos
        hoy = timezone.localdate()
        omision = periodo_por_omision(hoy)
        desde = datos.get("desde") or omision.inicio
        hasta = datos.get("hasta") or hoy
        if hasta > hoy:
            raise forms.ValidationError("La fecha «Hasta» no puede ser posterior a hoy.")
        if desde > hasta:
            raise forms.ValidationError("La fecha «Desde» debe ser anterior o igual a «Hasta».")
        if (hasta - desde).days + 1 > DIAS_MAXIMOS:
            raise forms.ValidationError(f"El período admite hasta {DIAS_MAXIMOS} días.")
        datos["desde"], datos["hasta"] = desde, hasta
        datos["tipo"] = datos.get("tipo") or TODOS
        return datos

    def periodo(self):
        """El período pedido; con datos inválidos (o sin datos), el de omisión."""
        if self.is_bound and self.is_valid():
            return Periodo(self.cleaned_data["desde"], self.cleaned_data["hasta"], self.cleaned_data["tipo"])
        return periodo_por_omision()

    def pagina(self):
        if self.is_bound and self.is_valid():
            return self.cleaned_data.get("pagina") or 1
        return 1


def atajos(hoy=None):
    """Atajos del rango: hoy, 7 días, 30 días y el mes calendario anterior completo."""
    hoy = hoy or timezone.localdate()
    primero_del_mes = hoy.replace(day=1)
    fin_anterior = primero_del_mes - timedelta(days=1)
    return [
        ("Hoy", hoy, hoy),
        ("7 días", hoy - timedelta(days=6), hoy),
        ("30 días", hoy - timedelta(days=29), hoy),
        ("Mes anterior", fin_anterior.replace(day=1), fin_anterior),
    ]
