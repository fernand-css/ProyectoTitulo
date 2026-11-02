"""Campos editables del perfil; los privilegios no forman parte del formulario."""

import logging

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password

from coreapp.roles import ENCARGADO, ETIQUETAS_ROLES, ROLES_INTERNOS, TECNICO, estado_acceso


logger = logging.getLogger(__name__)


class PerfilForm(forms.Form):
    first_name = forms.CharField(label="Nombres", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "given-name"}))
    last_name = forms.CharField(label="Apellidos", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "family-name"}))
    email = forms.EmailField(label="Correo electrónico", max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            for nombre in self.errors:
                if nombre in self.fields:
                    self.fields[nombre].widget.attrs.update({
                        "aria-invalid": "true", "aria-describedby": f"id_{nombre}_error",
                    })


class RecuperacionForm(PasswordResetForm):
    username = forms.CharField(label="Nombre de usuario", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "username"}))
    field_order = ("username", "email")

    def get_users(self, email):
        usuario = get_user_model().objects.filter(
            username=self.cleaned_data["username"], is_active=True,
            perfil__correo_verificado_en__isnull=False,
        ).first()
        if (usuario is not None and usuario.has_usable_password() and estado_acceso(usuario)[0]
                and usuario.email.strip().casefold() == email.strip().casefold()):
            return [usuario]
        return []

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        asunto = "".join(render_to_string(subject_template_name, context).splitlines())
        cuerpo = render_to_string(email_template_name, context)
        try:
            enviados = EmailMultiAlternatives(asunto, cuerpo, from_email, [to_email]).send()
            if enviados != 1:
                logger.error("No se pudo enviar el correo de recuperación.")
        except Exception:
            # Misma respuesta pública; no copiar excepciones con datos privados.
            logger.error("No se pudo enviar el correo de recuperación.")


class GestionEdicionForm(PerfilForm):
    rol = forms.ChoiceField(label="Rol", choices=[(rol, ETIQUETAS_ROLES[rol]) for rol in (TECNICO, ENCARGADO)])


class GestionAltaForm(GestionEdicionForm):
    username = forms.CharField(label="Nombre de usuario", max_length=150, validators=get_user_model()._meta.get_field("username").validators)
    password1 = forms.CharField(label="Contraseña inicial", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirmar contraseña", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    field_order = ("username", "first_name", "last_name", "email", "rol", "password1", "password2")

    def clean(self):
        datos = super().clean()
        if datos.get("password1") and datos.get("password2"):
            if datos["password1"] != datos["password2"]:
                self.add_error("password2", "Las contraseñas no coinciden.")
            else:
                usuario = get_user_model()(**{nombre: datos.get(nombre, "") for nombre in ("username", "first_name", "last_name", "email")})
                validate_password(datos["password1"], usuario)
        return datos


class EstadoCuentaForm(forms.Form):
    activo = forms.TypedChoiceField(choices=[("1", "Activar"), ("0", "Desactivar")], coerce=lambda valor: valor == "1")


class CuentaAdminForm(forms.ModelForm):
    rol = forms.ChoiceField(label="Rol operativo", required=False, choices=[("", "Sin rol (solo superusuario)")] + [(rol, ETIQUETAS_ROLES[rol]) for rol in ROLES_INTERNOS])
    grupos_extra = forms.ModelMultipleChoiceField(label="Otros grupos", queryset=Group.objects.none(), required=False)
    password1 = forms.CharField(label="Nueva contraseña", required=False, strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirmar contraseña", required=False, strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email", "is_active", "is_staff", "is_superuser", "user_permissions")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupos_extra"].queryset = Group.objects.exclude(name__in=ROLES_INTERNOS)
        self.fields["user_permissions"].queryset = Permission.objects.all()
        for nombre in ("first_name", "last_name", "email"):
            self.fields[nombre].required = True
        if self.instance.pk:
            if not self.instance.email and hasattr(self.instance, "perfil"):
                self.initial["email"] = self.instance.perfil.correo_pendiente
            roles = list(self.instance.groups.filter(name__in=ROLES_INTERNOS).values_list("name", flat=True))
            self.initial["rol"] = roles[0] if len(roles) == 1 else ""
            self.initial["grupos_extra"] = list(self.instance.groups.exclude(name__in=ROLES_INTERNOS).values_list("pk", flat=True))
        else:
            self.fields["password1"].required = self.fields["password2"].required = True

    def clean(self):
        datos = super().clean()
        if not datos.get("is_superuser") and not datos.get("rol"):
            self.add_error("rol", "Selecciona un único rol operativo para esta cuenta.")
        if datos.get("password1") or datos.get("password2"):
            if datos.get("password1") != datos.get("password2"):
                self.add_error("password2", "Las contraseñas no coinciden.")
            elif datos.get("password1"):
                usuario = get_user_model()(**{nombre: datos.get(nombre, "") for nombre in ("username", "first_name", "last_name", "email")})
                validate_password(datos["password1"], usuario)
        return datos
