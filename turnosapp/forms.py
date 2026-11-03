"""Entrada transitoria del tótem, sin identificadores en URL."""
from django import forms
from coreapp.utils.rut import normalizar_rut
import uuid
from recetasapp.services import evaluar_elegibilidad
from .models import Turno


class EmisionTurnoForm(forms.Form):
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)
    rut = forms.CharField(label="Tu RUT", max_length=12, widget=forms.TextInput(attrs={
        "autocomplete": "off", "spellcheck": "false", "autocapitalize": "characters",
        "aria-describedby": "rut-ayuda rut-error", "enterkeyhint": "done",
    }))

    def clean_rut(self):
        return normalizar_rut(self.cleaned_data["rut"])


class OperacionForm(forms.Form):
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("operacion_id", uuid.uuid4())


class VentanillaForm(OperacionForm):
    numero = forms.IntegerField(label="Número de ventanilla", min_value=1)
    tipos = forms.MultipleChoiceField(label="Tipos de atención admitidos", choices=Turno.TipoAtencion.choices,
        required=False, widget=forms.CheckboxSelectMultiple)
    habilitada = forms.BooleanField(label="Ventanilla habilitada", required=False)
    retirada = forms.BooleanField(label="Retirar de operación conservando su historial", required=False)
    confirmar = forms.BooleanField(label="Confirmo deshabilitar o retirar aunque haya una atención en curso", required=False)

    def __init__(self, *args, ventanilla=None, **kwargs):
        super().__init__(*args, **kwargs)
        if ventanilla:
            self.fields.pop("numero")
            if not self.is_bound:
                self.initial.update(tipos=list(ventanilla.tipos.values_list("codigo", flat=True)),
                    habilitada=ventanilla.habilitada, retirada=ventanilla.retirada)
        else:
            for nombre in ("habilitada", "retirada", "confirmar"):
                self.fields.pop(nombre)
            if not self.is_bound:
                self.initial["tipos"] = list(Turno.TipoAtencion.values)


class PesosForm(OperacionForm):
    preferencial = forms.IntegerField(label="Preferenciales por ciclo", min_value=1)
    cronicos = forms.IntegerField(label="Crónicos por ciclo", min_value=1)
    general = forms.IntegerField(label="Generales por ciclo", min_value=1)


class SeleccionRecetas(forms.CheckboxSelectMultiple):
    def __init__(self, *args, bloqueadas=(), marcadas=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.bloqueadas = {str(pk) for pk in bloqueadas}
        self.marcadas = {str(pk) for pk in marcadas}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex, attrs)
        if str(value) in self.bloqueadas:
            opcion["attrs"]["disabled"] = True
        if str(value) in self.marcadas:
            opcion["selected"] = True
            opcion["attrs"]["checked"] = True
        return opcion


class FinalizarForm(OperacionForm):
    recetas_entregadas = forms.MultipleChoiceField(label="Recetas entregadas ahora", required=False)
    motivo = forms.CharField(label="Motivo general de no entrega", required=False, max_length=500,
        help_text="Se aplica a las recetas sin motivo propio. Es obligatorio si no hubo entregas.",
        widget=forms.Textarea(attrs={"rows": 3}))
    confirmar = forms.BooleanField(label="Confirmo las entregas indicadas y el cierre de esta atención")

    def __init__(self, *args, turno, **kwargs):
        super().__init__(*args, **kwargs)
        self.vinculos = list(turno.recetas_vinculadas.select_related("receta", "entrega").order_by("receta_id"))
        self.previamente_entregadas = set()
        bloqueadas, opciones = [], []
        for vinculo in self.vinculos:
            receta = vinculo.receta
            entrega = getattr(vinculo, "entrega", None)
            estado = evaluar_elegibilidad(receta)
            sufijo = ""
            if entrega:
                self.previamente_entregadas.add(receta.pk)
                sufijo = " — Ya entregada en esta atención"
            elif not estado["elegible"]:
                sufijo = " — No disponible: " + " ".join(estado["causas"])
            if entrega or not estado["elegible"]:
                bloqueadas.append(receta.pk)
            opciones.append((str(receta.pk), receta.codigo + sufijo))
            self.fields[f"motivo_{receta.pk}"] = forms.CharField(label=f"Motivo de no entrega de {receta.codigo}",
                required=False, max_length=500, widget=forms.HiddenInput if entrega else forms.TextInput(attrs={"autocomplete": "off"}))
        # Las opciones siguen siendo válidas en un POST repetido tras el cierre;
        # bloquear la interacción HTML no impide recuperar el resultado idempotente.
        self.fields["recetas_entregadas"].choices = opciones
        self.fields["recetas_entregadas"].widget = SeleccionRecetas(bloqueadas=bloqueadas, marcadas=self.previamente_entregadas)
        self.fields["recetas_entregadas"].widget.choices = opciones

    def clean(self):
        datos = super().clean()
        seleccion = {int(pk) for pk in datos.get("recetas_entregadas", [])}
        realizadas = seleccion | self.previamente_entregadas
        if not realizadas and not datos.get("motivo", "").strip():
            self.add_error("motivo", "Indica el motivo del cierre sin entrega.")
        for vinculo in self.vinculos:
            pk = vinculo.receta_id
            campo = f"motivo_{pk}"
            if pk not in realizadas and not datos.get("motivo", "").strip() and not datos.get(campo, "").strip():
                self.add_error(campo, "Indica el motivo de no entrega de esta receta.")
        return datos

    def argumentos(self):
        return {"recetas_entregadas": [int(pk) for pk in self.cleaned_data["recetas_entregadas"]],
            "motivo": self.cleaned_data["motivo"],
            "motivos": {int(nombre.removeprefix("motivo_")): valor for nombre, valor in self.cleaned_data.items()
                if nombre.startswith("motivo_") and valor}}
