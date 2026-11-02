"""Administración superior; todas las escrituras pasan por servicios auditados."""

from smtplib import SMTPException
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters

from coreapp.roles import estado_acceso
from .forms import CuentaAdminForm
from .services import guardar_cuenta_admin


class SoloSuperusuarioAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return estado_acceso(request.user) == (True, "superusuario")

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if self.has_view_permission(request) else queryset.none()


class CuentaAdmin(SoloSuperusuarioAdmin):
    form = CuentaAdminForm
    actions = None
    list_display = ("username", "first_name", "last_name", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "first_name", "last_name")
    readonly_fields = ("correo_verificado", "correo_pendiente")
    fields = (
        "username", "first_name", "last_name", "email", "correo_verificado", "correo_pendiente",
        "rol", "is_active", "is_staff", "is_superuser", "grupos_extra", "user_permissions", "password1", "password2",
    )

    @admin.display(description="Correo verificado", boolean=True)
    def correo_verificado(self, obj):
        return bool(obj.pk and hasattr(obj, "perfil") and obj.perfil.correo_verificado_en)

    @admin.display(description="Correo pendiente de confirmación")
    def correo_pendiente(self, obj):
        return obj.perfil.correo_pendiente if obj.pk and hasattr(obj, "perfil") else ""

    @method_decorator(sensitive_post_parameters("password1", "password2"))
    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if not self.has_module_permission(request):
            raise PermissionDenied
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except (ValidationError, IntegrityError, SMTPException, OSError):
            messages.error(request, "No se guardaron los cambios. Revisa los datos y el envío de verificación e inténtalo nuevamente.")
            return redirect(request.path)

    def save_model(self, request, obj, form, change):
        guardado = guardar_cuenta_admin(
            request.user, pk=obj.pk if change else None, datos=form.cleaned_data,
            origen=request.build_absolute_uri("/"),
        )
        obj.__dict__.update(guardado.__dict__)

    def save_related(self, request, form, formsets, change):
        # Los servicios ya guardaron grupos/permisos dentro de su transacción.
        pass

    def log_addition(self, request, obj, message):
        # La bitácora propia ya registra la operación sin object_repr personal.
        pass

    def log_change(self, request, obj, message):
        pass

    def history_view(self, request, object_id, extra_context=None):
        if not self.has_module_permission(request):
            raise PermissionDenied
        objeto = self.get_object(request, object_id)
        if objeto is None:
            raise Http404
        parametros = urlencode({"q": str(objeto.pk), "objeto_tipo__exact": "auth.User"})
        return redirect(reverse("admin:coreapp_registroauditoria_changelist") + "?" + parametros)


class GrupoSoloLecturaAdmin(SoloSuperusuarioAdmin):
    fields = readonly_fields = ("name", "permissions")
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), CuentaAdmin)
admin.site.unregister(Group)
admin.site.register(Group, GrupoSoloLecturaAdmin)
