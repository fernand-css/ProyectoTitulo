"""Perfil propio y confirmación pública de un correo mediante enlace firmado."""

from smtplib import SMTPException

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.signals import user_login_failed
from django.contrib.auth.views import (
    INTERNAL_RESET_SESSION_TOKEN, LoginView, PasswordChangeView,
    PasswordResetConfirmView, PasswordResetView,
)
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic.edit import FormView
from django.views.generic import ListView

from coreapp.mixins import CuentaHabilitadaMixin, RolRequeridoMixin
from coreapp.roles import ETIQUETAS_ROLES, JEFA, ROLES_INTERNOS
from .forms import EstadoCuentaForm, GestionAltaForm, GestionEdicionForm, PerfilForm, RecuperacionForm
from .models import Perfil
from .services import (
    ERROR_CORREO, actualizar_perfil, confirmar_correo,
    consultar_verificacion_correo, solicitar_verificacion_correo,
    cambiar_clave, iniciar_sesion, puede_recuperar_clave, restablecer_clave,
    cambiar_estado_cuenta, cuentas_gestionables, guardar_cuenta_gestion,
)


@method_decorator(never_cache, name="dispatch")
class PerfilView(CuentaHabilitadaMixin, FormView):
    template_name = "usuarios/perfil.html"
    form_class = PerfilForm
    success_url = reverse_lazy("usuariosapp:perfil")

    def get_initial(self):
        cuenta = self.request.user
        inicial = {campo: getattr(cuenta, campo) for campo in ("first_name", "last_name", "email")}
        if not cuenta.email and hasattr(cuenta, "perfil"):
            inicial["email"] = cuenta.perfil.correo_pendiente
        return inicial

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["perfil_cuenta"] = Perfil.objects.filter(usuario=self.request.user).first()
        return contexto

    def form_valid(self, form):
        try:
            confirmar = actualizar_perfil(self.request.user, **form.cleaned_data, origen=self.request.build_absolute_uri("/"))
        except ValidationError:
            form.add_error(None, "Revisa los datos del perfil e inténtalo nuevamente.")
            return self.form_invalid(form)
        except (SMTPException, OSError):
            form.add_error(None, "No pudimos enviar la verificación. Inténtalo nuevamente; tus cambios no se guardaron.")
            return self.form_invalid(form)
        messages.success(self.request, "Tu perfil se guardó." + (" Revisa el correo para confirmar la dirección." if confirmar else ""))
        return redirect(self.success_url)


class SolicitarVerificacionView(CuentaHabilitadaMixin, View):
    http_method_names = ["post", "options"]

    def post(self, request):
        try:
            enviado = solicitar_verificacion_correo(request.user, origen=request.build_absolute_uri("/"))
        except ValidationError:
            messages.error(request, "Registra un correo válido en tu perfil para solicitar la verificación.")
        except (SMTPException, OSError):
            messages.error(request, "No pudimos enviar la verificación. Inténtalo nuevamente.")
        else:
            messages.success(request, "Revisa tu correo para confirmar la dirección." if enviado else "Tu correo ya está verificado.")
        return redirect("usuariosapp:perfil")


@method_decorator(never_cache, name="dispatch")
class VerificarCorreoView(View):
    def dispatch(self, request, *args, **kwargs):
        respuesta = super().dispatch(request, *args, **kwargs)
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        return respuesta

    def get(self, request, token):
        try:
            consultar_verificacion_correo(token)
        except ValidationError:
            return render(request, "usuarios/verificar_correo.html", {"error": ERROR_CORREO}, status=400)
        return render(request, "usuarios/verificar_correo.html", {"valido": True})

    def post(self, request, token):
        try:
            confirmar_correo(token)
        except ValidationError:
            return render(request, "usuarios/verificar_correo.html", {"error": ERROR_CORREO}, status=400)
        return render(request, "usuarios/verificar_correo.html", {"confirmado": True})


class IniciarSesionView(LoginView):
    def form_valid(self, form):
        try:
            iniciar_sesion(self.request, form.get_user())
        except PermissionDenied:
            user_login_failed.send(sender=type(self), credentials={}, request=self.request)
            form.add_error(None, form.get_invalid_login_error())
            return self.form_invalid(form)
        return HttpResponseRedirect(self.get_success_url())


@method_decorator(never_cache, name="dispatch")
class CambiarClaveView(CuentaHabilitadaMixin, PasswordChangeView):
    success_url = reverse_lazy("usuariosapp:perfil")

    def form_valid(self, form):
        try:
            cuenta = cambiar_clave(self.request.user, actual=form.cleaned_data["old_password"], nueva=form.cleaned_data["new_password1"])
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        update_session_auth_hash(self.request, cuenta)
        messages.success(self.request, "Tu contraseña se actualizó.")
        return HttpResponseRedirect(self.get_success_url())


@method_decorator(never_cache, name="dispatch")
class RecuperarClaveView(PasswordResetView):
    form_class = RecuperacionForm
    success_url = reverse_lazy("usuariosapp:recuperacion_enviada")
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"


class RestablecerClaveView(PasswordResetConfirmView):
    success_url = reverse_lazy("usuariosapp:clave_lista")

    def get_user(self, uidb64):
        usuario = super().get_user(uidb64)
        return usuario if puede_recuperar_clave(usuario) else None

    def form_valid(self, form):
        try:
            restablecer_clave(self.user, nueva=form.cleaned_data["new_password1"], token=self.request.session.get(INTERNAL_RESET_SESSION_TOKEN))
        except (ValidationError, PermissionDenied):
            self.validlink = False
            self.request.session.pop(INTERNAL_RESET_SESSION_TOKEN, None)
            return self.render_to_response(self.get_context_data())
        self.request.session.pop(INTERNAL_RESET_SESSION_TOKEN, None)
        return HttpResponseRedirect(self.get_success_url())


@method_decorator(never_cache, name="dispatch")
class GestionUsuariosView(RolRequeridoMixin, ListView):
    roles_permitidos = (JEFA,)
    template_name = "usuarios/gestion_lista.html"
    context_object_name = "cuentas"
    paginate_by = 20

    def get_queryset(self):
        return cuentas_gestionables(self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        for cuenta in contexto["cuentas"]:
            rol = cuenta.groups.filter(name__in=ROLES_INTERNOS).values_list("name", flat=True).first()
            cuenta.rol_visible = ETIQUETAS_ROLES.get(rol, "")
        return contexto


@method_decorator(never_cache, name="dispatch")
@method_decorator(sensitive_post_parameters("password1", "password2"), name="dispatch")
class GestionCuentaView(RolRequeridoMixin, FormView):
    roles_permitidos = (JEFA,)
    template_name = "usuarios/gestion_form.html"
    success_url = reverse_lazy("usuariosapp:gestion_usuarios")

    def get_cuenta(self):
        if "pk" not in self.kwargs:
            return None
        if not hasattr(self, "cuenta_objetivo"):
            self.cuenta_objetivo = get_object_or_404(cuentas_gestionables(self.request.user), pk=self.kwargs["pk"])
        return self.cuenta_objetivo

    def get_form_class(self):
        return GestionEdicionForm if self.get_cuenta() is not None else GestionAltaForm

    def get_initial(self):
        cuenta = self.get_cuenta()
        if cuenta is None:
            return {}
        inicial = {
            **{nombre: getattr(cuenta, nombre) for nombre in ("first_name", "last_name", "email")},
            "rol": cuenta.groups.filter(name__in=ROLES_INTERNOS).values_list("name", flat=True).get(),
        }
        if not cuenta.email and hasattr(cuenta, "perfil"):
            inicial["email"] = cuenta.perfil.correo_pendiente
        return inicial

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "cuenta": self.get_cuenta()}

    def form_valid(self, form):
        cuenta = self.get_cuenta()
        try:
            guardar_cuenta_gestion(
                self.request.user, pk=cuenta.pk if cuenta else None,
                origen=self.request.build_absolute_uri("/"), **form.cleaned_data,
            )
        except (ValidationError, IntegrityError):
            form.add_error(None, "No se pudo guardar la cuenta. Revisa los datos y que el nombre de usuario esté disponible.")
            return self.form_invalid(form)
        except (SMTPException, OSError):
            form.add_error(None, "No pudimos enviar la verificación. Los cambios no se guardaron; inténtalo nuevamente.")
            return self.form_invalid(form)
        messages.success(self.request, "La cuenta se guardó. Los cambios de correo requieren confirmación.")
        return redirect(self.success_url)


class EstadoCuentaView(RolRequeridoMixin, View):
    roles_permitidos = (JEFA,)
    http_method_names = ["post", "options"]

    def post(self, request, pk):
        cuenta = get_object_or_404(cuentas_gestionables(request.user), pk=pk)
        form = EstadoCuentaForm(request.POST)
        if not form.is_valid():
            return HttpResponseBadRequest("Indica activar o desactivar la cuenta.")
        cambiar_estado_cuenta(request.user, cuenta.pk, activo=form.cleaned_data["activo"])
        messages.success(request, "El estado de la cuenta se actualizó.")
        return redirect("usuariosapp:gestion_usuarios")
