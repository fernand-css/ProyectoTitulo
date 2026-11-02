"""Entradas de farmacia; el servicio vuelve a comprobar permisos y reglas."""

from django import forms
from django.utils import timezone

from .importacion import MAX_BYTES
from .models import ImportacionPadron, Paciente


class BusquedaPacienteForm(forms.Form):
    buscar = forms.CharField(label="Buscar por RUT o nombre", max_length=150, required=False)
    pagina = forms.IntegerField(min_value=1, initial=1, widget=forms.HiddenInput, required=False)


class RecetaForm(forms.Form):
    paciente = forms.ModelChoiceField(label="Paciente del padrón", queryset=Paciente.objects.none())
    codigo = forms.CharField(label="Código único de receta", max_length=64)
    fecha_inicio = forms.DateField(label="Fecha de inicio", initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    vigencia_meses = forms.IntegerField(label="Vigencia en meses", min_value=1)
    max_entregas = forms.IntegerField(label="Máximo de entregas", min_value=1)

    def __init__(self, *args, paciente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paciente"].queryset = Paciente.objects.filter(pk=paciente.pk) if paciente else Paciente.objects.order_by("apellidos", "nombres", "pk")
        self.fields["paciente"].label_from_instance = lambda p: f"{p.nombres} {p.apellidos} · {p.rut}"
        if paciente:
            self.fields["paciente"].initial = paciente
            self.fields["paciente"].disabled = True


class EntregaForm(forms.Form):
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)
    confirmar = forms.BooleanField(label="Confirmo que esta entrega del ciclo fue completada")


class ImportacionForm(forms.Form):
    formato = forms.ChoiceField(label="Formato del archivo", choices=ImportacionPadron.Formato.choices)
    archivo = forms.FileField(label="Archivo sintético", help_text="CSV UTF-8 o Excel .xlsx. Máximo 5 MiB y 10.000 filas; usa una plantilla descargable.")
    sintetico = forms.BooleanField(label="Confirmo que el archivo contiene exclusivamente datos sintéticos")

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if archivo.size > MAX_BYTES:
            raise forms.ValidationError("El archivo supera el límite de 5 MiB.")
        return archivo
