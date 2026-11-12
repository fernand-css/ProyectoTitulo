"""Formularios del reparto. Validan la forma de los datos; las reglas de negocio viven en los servicios."""

from decimal import Decimal

from django import forms
from django.utils import timezone

from .consultas import PENDIENTE, SIN_REGISTRAR, VERIFICADO, encargados_activos
from .models import Entrega, InscripcionReparto, IntentoEntrega, Sector

BUSQUEDA = {"type": "search", "autocomplete": "off", "spellcheck": "false", "enterkeyhint": "search",
            "placeholder": "RUT, nombre o apellido"}
FECHA = {"type": "date"}


class BusquedaForm(forms.Form):
    """Búsqueda por POST, como en el 07: el RUT nunca viaja en la URL."""
    buscar = forms.CharField(label="Buscar paciente", max_length=150, required=False, widget=forms.TextInput(attrs=BUSQUEDA))
    pagina = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)


class FiltroDomiciliosForm(BusquedaForm):
    sector = forms.ChoiceField(label="Sector", choices=[("", "Todos los sectores"), *Sector.choices], required=False)
    estado = forms.ChoiceField(label="Estado del domicilio", required=False, choices=[
        ("", "Todos los estados"), (SIN_REGISTRAR, "Sin registrar"), (PENDIENTE, "Pendiente de verificar"),
        (VERIFICADO, "Verificado"),
    ])


class EncargadoField(forms.ModelChoiceField):
    def label_from_instance(self, usuario):
        return usuario.get_full_name().strip() or usuario.get_username()


def _encargado(requerido=True, etiqueta="Encargado de terreno"):
    return EncargadoField(label=etiqueta, queryset=encargados_activos(), required=requerido,
                          empty_label="Elige un encargado" if requerido else "Todos los encargados")


class FiltroEntregasForm(forms.Form):
    """Filtros por GET: no llevan datos personales (motivo, sector, encargado y fechas)."""
    motivo = forms.ChoiceField(label="Motivo", choices=[("", "Todos los motivos"), *IntentoEntrega.Motivo.choices], required=False)
    sector = forms.ChoiceField(label="Sector", choices=[("", "Todos los sectores"), *Sector.choices], required=False)
    desde = forms.DateField(label="Desde", required=False, widget=forms.DateInput(attrs=FECHA, format="%Y-%m-%d"))
    hasta = forms.DateField(label="Hasta", required=False, widget=forms.DateInput(attrs=FECHA, format="%Y-%m-%d"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["encargado"] = _encargado(requerido=False, etiqueta="Encargado")
        self.order_fields(["motivo", "sector", "encargado", "desde", "hasta"])

    def clean(self):
        datos = super().clean()
        if datos.get("desde") and datos.get("hasta") and datos["desde"] > datos["hasta"]:
            raise forms.ValidationError("La fecha «Desde» debe ser anterior o igual a «Hasta».")
        return datos

    def filtros(self):
        if not self.is_valid():
            return {}
        return {clave: valor for clave, valor in self.cleaned_data.items() if valor}


class DomicilioForm(forms.Form):
    sector = forms.ChoiceField(label="Sector MAIS", choices=[("", "Sin asignar"), *Sector.choices], required=False,
                               help_text="Se necesita para marcar el domicilio como verificado.")
    localidad = forms.CharField(label="Localidad", max_length=120, required=False,
                                widget=forms.TextInput(attrs={"autocomplete": "off"}))
    direccion = forms.CharField(label="Dirección", max_length=500,
                                widget=forms.Textarea(attrs={"rows": 2, "autocomplete": "off"}))
    referencias = forms.CharField(label="Referencias para llegar", max_length=500, required=False,
                                  help_text="Por ejemplo: «portón verde junto al paradero».",
                                  widget=forms.Textarea(attrs={"rows": 3}))
    latitud = forms.DecimalField(label="Latitud", required=False, min_value=Decimal("-90"), max_value=Decimal("90"),
                                 max_digits=12, decimal_places=9, widget=forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}))
    longitud = forms.DecimalField(label="Longitud", required=False, min_value=Decimal("-180"), max_value=Decimal("180"),
                                  max_digits=12, decimal_places=9, widget=forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}))
    precision_metros = forms.IntegerField(label="Precisión (metros)", required=False, min_value=0,
                                          widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}))
    version = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)

    def clean(self):
        datos = super().clean()
        if (datos.get("latitud") is None) != (datos.get("longitud") is None):
            raise forms.ValidationError("Ingresa latitud y longitud juntas, o deja ambas vacías.")
        if datos.get("latitud") is None and datos.get("precision_metros") is not None:
            datos["precision_metros"] = None
        return datos

    @classmethod
    def desde_domicilio(cls, domicilio, paciente):
        if domicilio is None:
            return cls(initial={"direccion": paciente.direccion})
        return cls(initial={campo: getattr(domicilio, campo) for campo in (
            "sector", "localidad", "direccion", "referencias", "latitud", "longitud", "precision_metros", "version")})


class VersionForm(forms.Form):
    """Versión leída del domicilio para verificarlo; ids propios para convivir con el formulario de edición."""
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_id", "verificar_%s")
        super().__init__(*args, **kwargs)


class FotoForm(forms.Form):
    foto = forms.FileField(label="Foto del entorno", help_text="JPEG o PNG de 5 MB o menos.",
                           widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png", "capture": "environment"}))
    descripcion = forms.CharField(label="Descripción de la foto", max_length=120,
                                  help_text="Obligatoria: es el texto que lee quien no ve la imagen. Ej.: «portón verde y buzón rojo».")


class ExcepcionForm(forms.Form):
    paciente = forms.IntegerField(widget=forms.HiddenInput)
    motivo = forms.ChoiceField(label="Motivo", choices=[("", "Elige un motivo"), *InscripcionReparto.Motivo.choices])
    nota = forms.CharField(label="Nota", max_length=200, required=False, help_text="Obligatoria con el motivo «Otro». Hasta 200 caracteres.",
                           widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        datos = super().clean()
        if datos.get("motivo") == "otro" and not (datos.get("nota") or "").strip():
            self.add_error("nota", "Con el motivo «Otro», escribe una nota breve.")
        return datos


class ProgramarForm(forms.Form):
    fecha = forms.DateField(label="Fecha de la visita", widget=forms.DateInput(attrs=FECHA, format="%Y-%m-%d"),
                            help_text="Hoy o una fecha posterior.")
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["encargado"] = _encargado()
        self.order_fields(["fecha", "encargado", "operacion_id"])

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha < timezone.localdate():
            raise forms.ValidationError("La fecha debe ser hoy o posterior.")
        return fecha


class ReasignarForm(ProgramarForm):
    intento_id = forms.IntegerField(widget=forms.HiddenInput)
    resultado_visto = forms.ChoiceField(choices=IntentoEntrega.Resultado.choices, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].label = "Nueva fecha"
        self.fields["encargado"].label = "Nuevo encargado"


class AnularForm(forms.Form):
    motivo = forms.ChoiceField(label="Motivo de la anulación", choices=[("", "Elige un motivo"), *Entrega.MotivoAnulacion.choices])
    nota = forms.CharField(label="Nota", max_length=200, required=False, help_text="Obligatoria con el motivo «Otro».",
                           widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        datos = super().clean()
        if datos.get("motivo") == "otro" and not (datos.get("nota") or "").strip():
            self.add_error("nota", "Con el motivo «Otro», escribe una nota breve.")
        return datos


class EntregadaForm(forms.Form):
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)
    confirmar = forms.BooleanField(label="Entregué las recetas al paciente o a su cuidador")

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_id", "entregada_%s")  # la página también tiene el formulario de no entrega
        super().__init__(*args, **kwargs)


class NoEntregadaForm(forms.Form):
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)
    motivo = forms.ChoiceField(label="Motivo", choices=[("", "Elige el motivo"), *IntentoEntrega.Motivo.choices])
    nota = forms.CharField(label="Nota", max_length=200, required=False,
                           help_text="Obligatoria con el motivo «Otro». Hasta 200 caracteres.",
                           widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_id", "no_entregada_%s")
        super().__init__(*args, **kwargs)

    def clean(self):
        datos = super().clean()
        if datos.get("motivo") == "otro" and not (datos.get("nota") or "").strip():
            self.add_error("nota", "Con el motivo «Otro», escribe una nota breve.")
        return datos


# Orden de visita y rutas (spec 09) ---------------------------------------------------------------------------

class MoverParadaForm(forms.Form):
    """Subir, bajar o mover a una posición. La versión y la operación se fijan al dibujar la página."""
    intento = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    destino = forms.CharField(max_length=6)
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)


class RestablecerOrdenForm(forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)


class RutaForm(forms.Form):
    """«Rutas» de la Q.F.: encargado y fecha por GET (solo identificador interno y fecha, nunca datos personales)."""
    fecha = forms.DateField(label="Fecha", widget=forms.DateInput(attrs=FECHA, format="%Y-%m-%d"),
                            help_text="Hoy o una fecha posterior.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["encargado"] = _encargado()
        self.fields["encargado"].error_messages["invalid_choice"] = "Elige un encargado de terreno con cuenta activa."
        self.fields["fecha"].widget.attrs["min"] = timezone.localdate().isoformat()
        self.order_fields(["encargado", "fecha"])

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha < timezone.localdate():
            raise forms.ValidationError("Elige hoy o una fecha posterior: el orden sugerido no se guarda, así que "
                                        "no se pueden consultar rutas de días pasados.")
        return fecha
