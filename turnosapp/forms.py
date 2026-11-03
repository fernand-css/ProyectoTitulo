"""Entrada transitoria del tótem, sin identificadores en URL."""
from django import forms
from coreapp.utils.rut import normalizar_rut


class EmisionTurnoForm(forms.Form):
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)
    rut = forms.CharField(label="Tu RUT", max_length=12, widget=forms.TextInput(attrs={
        "autocomplete": "off", "spellcheck": "false", "autocapitalize": "characters",
        "aria-describedby": "rut-ayuda rut-error", "enterkeyhint": "done",
    }))

    def clean_rut(self):
        return normalizar_rut(self.cleaned_data["rut"])
