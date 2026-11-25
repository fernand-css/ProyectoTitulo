"""Entrada transitoria del tótem, sin identificadores en URL."""
from django import forms
from coreapp.utils.rut import normalizar_rut
import uuid
from recetasapp.services import evaluar_elegibilidad
from .models import TIPOS_VENTANILLA, CausaNoEntrega

# RF-05-14: lista cerrada de causas de no entrega, sin opción preseleccionada.
OPCIONES_CAUSA = [("", "Elige una causa"), *CausaNoEntrega.choices]
AYUDA_DETALLE = "Solo con «Otro». Hasta 200 caracteres."


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
    tipos = forms.MultipleChoiceField(label="Tipos de atención admitidos", choices=TIPOS_VENTANILLA,
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
                self.initial["tipos"] = [codigo for codigo, _ in TIPOS_VENTANILLA]


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
    # RF-05-14: causa general en lista cerrada; `motivo` es el detalle de «Otro».
    causa = forms.ChoiceField(label="Causa general de no entrega", required=False, choices=OPCIONES_CAUSA,
        help_text="Se aplica a las recetas sin causa propia. Es obligatoria si no hubo entregas.")
    motivo = forms.CharField(label="Detalle de la causa general «Otro»", required=False, max_length=200,
        help_text=AYUDA_DETALLE, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    confirmar = forms.BooleanField(label="Confirmo las entregas indicadas y el cierre de esta atención")

    def __init__(self, *args, turno, **kwargs):
        super().__init__(*args, **kwargs)
        self.vinculos = list(turno.recetas_vinculadas.select_related("receta", "entrega").order_by("receta_id"))
        self.previamente_entregadas = set()
        self.sin_recetas = not self.vinculos
        if self.sin_recetas:
            from .atencion import MOTIVO_SIN_RECETAS
            self.motivo_fijo = MOTIVO_SIN_RECETAS
            # Enmienda RF-05-13: el servicio pone el motivo fijo; solo se confirma el cierre.
            self.fields.pop("recetas_entregadas")
            self.fields.pop("causa")
            self.fields.pop("motivo")
            self.fields["confirmar"].label = "Confirmo el cierre de esta atención sin entrega de recetas"
            return
        bloqueadas, opciones, orden = [], [], ["recetas_entregadas"]
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
            if not entrega:
                self.fields[f"causa_{receta.pk}"] = forms.ChoiceField(label=f"Causa de no entrega de {receta.codigo}",
                    required=False, choices=OPCIONES_CAUSA)
                orden.append(f"causa_{receta.pk}")
            self.fields[f"motivo_{receta.pk}"] = forms.CharField(
                label=f"Detalle de «Otro» para {receta.codigo}", required=False, max_length=200,
                help_text="" if entrega else AYUDA_DETALLE,
                widget=forms.HiddenInput if entrega else forms.TextInput(attrs={"autocomplete": "off"}))
            orden.append(f"motivo_{receta.pk}")
        # Las opciones siguen siendo válidas en un POST repetido tras el cierre;
        # bloquear la interacción HTML no impide recuperar el resultado idempotente.
        self.fields["recetas_entregadas"].choices = opciones
        self.fields["recetas_entregadas"].widget = SeleccionRecetas(bloqueadas=bloqueadas, marcadas=self.previamente_entregadas)
        self.fields["recetas_entregadas"].widget.choices = opciones
        self.order_fields([*orden, "causa", "motivo", "confirmar"])

    def clean(self):
        datos = super().clean()
        if self.sin_recetas:
            return datos
        seleccion = {int(pk) for pk in datos.get("recetas_entregadas", [])}
        realizadas = seleccion | self.previamente_entregadas
        general = datos.get("causa") or ("otro" if datos.get("motivo", "").strip() else "")
        if datos.get("causa") == "otro" and not datos.get("motivo", "").strip():
            self.add_error("motivo", "Escribe el detalle de la causa «Otro».")
        if not realizadas and not general:
            self.add_error("causa", "Indica la causa del cierre sin entrega.")
        for vinculo in self.vinculos:
            pk = vinculo.receta_id
            if pk in realizadas:
                continue
            causa, detalle = datos.get(f"causa_{pk}", ""), datos.get(f"motivo_{pk}", "").strip()
            if causa == "otro" and not detalle:
                self.add_error(f"motivo_{pk}", "Escribe el detalle de la causa «Otro».")
            elif not causa and not detalle and not general:
                self.add_error(f"causa_{pk}", "Indica la causa de no entrega de esta receta.")
        return datos

    def argumentos(self):
        if self.sin_recetas:
            return {"recetas_entregadas": [], "motivo": "", "motivos": {}}
        datos = self.cleaned_data
        motivos = {int(nombre.removeprefix("motivo_")): valor for nombre, valor in datos.items()
                   if nombre.startswith("motivo_") and valor}
        causas = {int(nombre.removeprefix("causa_")): valor for nombre, valor in datos.items()
                  if nombre.startswith("causa_") and valor}
        argumentos = {"recetas_entregadas": [int(pk) for pk in datos["recetas_entregadas"]],
                      "motivo": datos["motivo"], "motivos": motivos}
        if datos.get("causa") or causas:
            argumentos.update(causa=datos.get("causa", ""), causas=causas)
        return argumentos


class TerminarTurnoForm(OperacionForm):
    """Spec 10, RF-10-01: la confirmación se exige en el servicio solo si hay un paciente llamado."""
    confirmar = forms.BooleanField(label="Confirmo el término de turno: el paciente llamado vuelve a la fila de espera",
        required=False)


class ReclasificarForm(OperacionForm):
    """Spec 10, RF-10-04: entre P, G y C; la urgencia tiene su propia acción."""
    letra = forms.ChoiceField(label="Nueva fila", choices=[
        ("P", "P · Preferencial"), ("G", "G · General"), ("C", "C · Crónicos")])
