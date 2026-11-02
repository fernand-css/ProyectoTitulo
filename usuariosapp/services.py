"""Operaciones transaccionales de cuentas, perfil y verificación de correo."""

import sqlite3
import time
import uuid
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import mail, signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import DEFAULT_DB_ALIAS, OperationalError, connections, transaction
from django.db.models import Count, F, Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from coreapp.auditoria import ROL_CAMBIADO, USUARIO_CREADO, registrar_evento
from coreapp.roles import ENCARGADO, JEFA, ROLES_INTERNOS, TECNICO, estado_acceso
from .forms import PerfilForm
from .models import Perfil


CUENTAS_DEMO = (
    ("demo_qf", JEFA, "QF"),
    ("demo_tecnico", TECNICO, "Técnico"),
    ("demo_terreno", ENCARGADO, "Terreno"),
)


def crear_roles(*, using=DEFAULT_DB_ALIAS):
    """Crear solo los grupos operativos; no cambiar permisos existentes."""
    with transaction.atomic(using=using):
        return {
            nombre: Group.objects.using(using).get_or_create(name=nombre)[0]
            for nombre in ROLES_INTERNOS
        }


def faltan_cuentas_demo(*, using=DEFAULT_DB_ALIAS):
    existentes = set(get_user_model().objects.using(using).filter(
        username__in=[nombre for nombre, _, _ in CUENTAS_DEMO],
    ).values_list("username", flat=True))
    return any(nombre not in existentes for nombre, _, _ in CUENTAS_DEMO)


def crear_cuentas_demo(clave=None, *, using=DEFAULT_DB_ALIAS):
    """Crear cuentas nuevas; conservar íntegramente cualquier cuenta existente.

    Servicio de preparación para el comando administrativo, no un alta pública.
    """
    Usuario = get_user_model()
    creadas, conservadas = [], []
    with transaction.atomic(using=using):
        roles = crear_roles(using=using)
        for nombre, rol, apellido in CUENTAS_DEMO:
            if Usuario.objects.using(using).filter(username=nombre).exists():
                conservadas.append(nombre)
                continue
            if not clave:
                raise ValidationError("Falta la contraseña inicial de las nuevas cuentas sintéticas.")
            usuario = Usuario(
                username=nombre, first_name="Demostración", last_name=apellido,
                email=f"{nombre}@example.invalid",
            )
            validate_password(clave, usuario)
            usuario.set_password(clave)
            usuario.full_clean()
            usuario.save(using=using)
            Perfil.objects.using(using).create(usuario=usuario)
            usuario.groups.add(roles[rol])
            registrar_evento(None, USUARIO_CREADO, objeto=usuario, using=using)
            registrar_evento(None, ROL_CAMBIADO, objeto=usuario, using=using)
            creadas.append(nombre)
    return creadas, conservadas


SALT_CORREO = "usuariosapp.verificacion_correo"
ERROR_CORREO = "El enlace de verificación no es válido o ya caducó. Solicita uno nuevo desde tu perfil."


def normalizar_correo(correo):
    return correo.strip().casefold()


def _reintentar_sqlite(operacion, using):
    """Repetir transacciones breves ante contención real, nunca otros errores."""
    for intento in range(6):
        try:
            return operacion()
        except OperationalError as error:
            codigo = getattr(error.__cause__, "sqlite_errorcode", 0) & 255
            if (connections[using].vendor != "sqlite" or connections[using].in_atomic_block
                    or codigo not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or intento == 5):
                raise
            time.sleep(0.02 * 2**intento)


def _cuenta_propia_bloqueada(usuario, using):
    """La primera escritura serializa la edición antes de consultar sus datos."""
    if not usuario.is_authenticated or usuario.pk is None:
        raise PermissionDenied
    Usuario = get_user_model()
    if not Usuario.objects.using(using).filter(pk=usuario.pk, is_active=True).update(last_name=F("last_name")):
        raise PermissionDenied
    cuenta = Usuario.objects.using(using).get(pk=usuario.pk)
    if not estado_acceso(cuenta)[0]:
        raise PermissionDenied
    return cuenta


def _preparar_correo(cuenta, perfil, correo, origen):
    correo = normalizar_correo(correo)
    validate_email(correo)
    perfil.correo_pendiente = correo
    perfil.solicitud_correo = uuid.uuid4()
    perfil.save(update_fields=["correo_pendiente", "solicitud_correo"])
    token = signing.dumps({
        "usuario": cuenta.pk, "correo": correo, "solicitud": perfil.solicitud_correo.hex,
    }, salt=SALT_CORREO)
    enlace = urljoin(origen, reverse("usuariosapp:verificar_correo", kwargs={"token": token}))
    return correo, render_to_string("registration/verificar_correo_email.txt", {"enlace": enlace})


def _enviar_correo(destino, cuerpo):
    enviados = mail.send_mail(
        "Confirma tu correo · Farmacia CESFAM San Nicolás", cuerpo,
        settings.DEFAULT_FROM_EMAIL, [destino], fail_silently=False,
    )
    if enviados != 1:
        raise OSError("No se pudo entregar el mensaje al backend de correo.")


def actualizar_perfil(usuario, *, first_name, last_name, email, origen):
    formulario = PerfilForm({"first_name": first_name, "last_name": last_name, "email": email})
    if not formulario.is_valid():
        raise ValidationError(dict(formulario.errors))
    datos = formulario.cleaned_data
    using = usuario._state.db or DEFAULT_DB_ALIAS

    def operacion():
        with transaction.atomic(using=using):
            cuenta = _cuenta_propia_bloqueada(usuario, using)
            perfil, _ = Perfil.objects.using(using).get_or_create(usuario=cuenta)
            cambio = (cuenta.first_name, cuenta.last_name) != (datos["first_name"], datos["last_name"])
            cuenta.first_name, cuenta.last_name = datos["first_name"], datos["last_name"]
            cuenta.save(using=using, update_fields=["first_name", "last_name"])
            correo = normalizar_correo(datos["email"])
            requiere_confirmacion = correo != normalizar_correo(cuenta.email) or perfil.correo_verificado_en is None
            mensaje = _preparar_correo(cuenta, perfil, correo, origen) if requiere_confirmacion else None
            if cambio or mensaje:
                registrar_evento(cuenta, "perfil.editado", objeto=cuenta, using=using)
            if mensaje:
                _enviar_correo(*mensaje)
            return requiere_confirmacion

    return _reintentar_sqlite(operacion, using)


def solicitar_verificacion_correo(usuario, *, origen):
    using = usuario._state.db or DEFAULT_DB_ALIAS

    def operacion():
        with transaction.atomic(using=using):
            cuenta = _cuenta_propia_bloqueada(usuario, using)
            perfil, _ = Perfil.objects.using(using).get_or_create(usuario=cuenta)
            if not perfil.correo_pendiente and perfil.correo_verificado_en is not None:
                return False
            mensaje = _preparar_correo(cuenta, perfil, perfil.correo_pendiente or cuenta.email, origen)
            registrar_evento(cuenta, "perfil.editado", objeto=cuenta, using=using)
            _enviar_correo(*mensaje)
            return True

    return _reintentar_sqlite(operacion, using)


def _datos_token_correo(token):
    try:
        datos = signing.loads(token, salt=SALT_CORREO, max_age=settings.PASSWORD_RESET_TIMEOUT)
        if (not isinstance(datos, dict) or set(datos) != {"usuario", "correo", "solicitud"}
                or type(datos["usuario"]) is not int or not isinstance(datos["correo"], str)):
            raise ValueError
        validate_email(datos["correo"])
        datos["solicitud"] = uuid.UUID(datos["solicitud"])
        return datos
    except (signing.BadSignature, ValueError, TypeError, AttributeError, ValidationError):
        raise ValidationError(ERROR_CORREO) from None


def consultar_verificacion_correo(token, *, using=DEFAULT_DB_ALIAS):
    datos = _datos_token_correo(token)
    perfil = Perfil.objects.using(using).select_related("usuario").filter(
        usuario_id=datos["usuario"], correo_pendiente=datos["correo"], solicitud_correo=datos["solicitud"],
    ).first()
    if perfil is None or not estado_acceso(perfil.usuario)[0]:
        raise ValidationError(ERROR_CORREO)
    return datos


def confirmar_correo(token, *, using=DEFAULT_DB_ALIAS):
    datos = _datos_token_correo(token)

    def operacion():
        with transaction.atomic(using=using):
            # Primera operación SQL: un UPDATE condicional, también en SQLite.
            consumidos = Perfil.objects.using(using).filter(
                usuario_id=datos["usuario"], correo_pendiente=datos["correo"],
                solicitud_correo=datos["solicitud"], usuario__is_active=True,
            ).update(correo_pendiente="", solicitud_correo=None, correo_verificado_en=timezone.now())
            if consumidos != 1:
                raise ValidationError(ERROR_CORREO)
            cuenta = get_user_model().objects.using(using).get(pk=datos["usuario"])
            if not estado_acceso(cuenta)[0]:
                raise ValidationError(ERROR_CORREO)
            cuenta.email = datos["correo"]
            cuenta.save(using=using, update_fields=["email"])
            registrar_evento(cuenta, "correo.confirmado", objeto=cuenta, using=using)

    return _reintentar_sqlite(operacion, using)


def iniciar_sesion(request, usuario):
    using = usuario._state.db or DEFAULT_DB_ALIAS
    with transaction.atomic(using=using):
        cuenta = _cuenta_propia_bloqueada(usuario, using)
        if cuenta.password != usuario.password:
            raise PermissionDenied
        auth_login(request, cuenta, backend=getattr(usuario, "backend", None))


def _guardar_clave(cuenta, nueva, accion, using, *, actor=None):
    validate_password(nueva, cuenta)
    if cuenta.check_password(nueva):
        raise ValidationError("Elige una contraseña distinta de la actual.")
    cuenta.set_password(nueva)
    cuenta.save(using=using, update_fields=["password"])
    registrar_evento(actor or cuenta, accion, objeto=cuenta, using=using)
    return cuenta


def cambiar_clave(usuario, *, actual, nueva):
    using = usuario._state.db or DEFAULT_DB_ALIAS

    def operacion():
        with transaction.atomic(using=using):
            cuenta = _cuenta_propia_bloqueada(usuario, using)
            if not cuenta.check_password(actual):
                raise ValidationError("La contraseña actual no es correcta.")
            return _guardar_clave(cuenta, nueva, "clave.cambiada", using)

    return _reintentar_sqlite(operacion, using)


def puede_recuperar_clave(usuario):
    return (usuario is not None and estado_acceso(usuario)[0] and usuario.has_usable_password()
            and Perfil.objects.using(usuario._state.db).filter(usuario=usuario, correo_verificado_en__isnull=False).exists())


def restablecer_clave(usuario, *, nueva, token):
    using = usuario._state.db or DEFAULT_DB_ALIAS

    def operacion():
        with transaction.atomic(using=using):
            cuenta = _cuenta_propia_bloqueada(usuario, using)
            if not puede_recuperar_clave(cuenta) or not default_token_generator.check_token(cuenta, token):
                raise ValidationError("El enlace de recuperación ya no es válido.")
            return _guardar_clave(cuenta, nueva, "clave.restablecida", using)

    return _reintentar_sqlite(operacion, using)


def cuentas_gestionables(actor):
    habilitada, rol = estado_acceso(actor)
    if not habilitada or rol not in (JEFA, "superusuario"):
        raise PermissionDenied
    return get_user_model().objects.using(actor._state.db).annotate(
        numero_roles=Count("groups", filter=Q(groups__name__in=ROLES_INTERNOS), distinct=True),
    ).filter(is_staff=False, is_superuser=False, numero_roles=1, groups__name__in=(TECNICO, ENCARGADO)).exclude(
        groups__name=JEFA,
    ).exclude(pk=actor.pk).distinct().order_by("username")


def _gestor_bloqueado(actor, using, *, superior=False):
    gestor = _cuenta_propia_bloqueada(actor, using)
    if superior:
        if not gestor.is_superuser:
            raise PermissionDenied
    elif not gestor.is_superuser and not tiene_rol_gestor(gestor):
        raise PermissionDenied
    return gestor


def tiene_rol_gestor(usuario):
    return estado_acceso(usuario) == (True, JEFA)


def _objetivo_bloqueado(pk, using):
    Usuario = get_user_model()
    if not Usuario.objects.using(using).filter(pk=pk).update(last_name=F("last_name")):
        raise PermissionDenied
    return Usuario.objects.using(using).get(pk=pk)


def _exigir_objetivo_operativo(gestor, cuenta):
    roles = list(cuenta.groups.filter(name__in=ROLES_INTERNOS).values_list("name", flat=True))
    if cuenta.pk == gestor.pk or cuenta.is_staff or cuenta.is_superuser or len(roles) != 1 or roles[0] not in (TECNICO, ENCARGADO):
        raise PermissionDenied


def guardar_cuenta_gestion(actor, *, first_name, last_name, email, rol, origen, pk=None, username=None, password1=None, password2=None):
    if rol not in (TECNICO, ENCARGADO):
        raise PermissionDenied
    if pk is not None and (username is not None or password1 is not None or password2 is not None):
        raise PermissionDenied
    if pk is None and (not password1 or password1 != password2):
        raise ValidationError("Confirma una contraseña inicial válida.")
    datos = dict(first_name=first_name, last_name=last_name, email=email, rol=rol, username=username, password1=password1)
    return _guardar_cuenta(actor, pk, datos, origen, superior=False)


def guardar_cuenta_admin(actor, *, pk=None, datos, origen):
    return _guardar_cuenta(actor, pk, datos, origen, superior=True)


def _guardar_cuenta(actor, pk, datos, origen, *, superior):
    if not getattr(actor, "is_authenticated", False) or actor.pk is None:
        raise PermissionDenied
    using = actor._state.db or DEFAULT_DB_ALIAS

    def operacion():
        with transaction.atomic(using=using):
            gestor = _gestor_bloqueado(actor, using, superior=superior)
            nueva = pk is None
            cuenta = get_user_model()() if nueva else _objetivo_bloqueado(pk, using)
            if not superior and not nueva:
                _exigir_objetivo_operativo(gestor, cuenta)
            formulario = PerfilForm({nombre: datos.get(nombre) for nombre in ("first_name", "last_name", "email")})
            if not formulario.is_valid():
                raise ValidationError(dict(formulario.errors))
            personal = formulario.cleaned_data
            roles_antes = set() if nueva else set(cuenta.groups.filter(name__in=ROLES_INTERNOS).values_list("name", flat=True))
            extras_antes = set() if nueva else set(cuenta.groups.exclude(name__in=ROLES_INTERNOS).values_list("pk", flat=True))
            permisos_antes = set() if nueva else set(cuenta.user_permissions.values_list("pk", flat=True))
            activo_antes = cuenta.is_active
            privilegios_antes = (cuenta.is_staff, cuenta.is_superuser, extras_antes, permisos_antes)
            basicos_antes = (cuenta.username, cuenta.first_name, cuenta.last_name)
            if nueva or superior:
                cuenta.username = datos.get("username")
            cuenta.first_name, cuenta.last_name = personal["first_name"], personal["last_name"]
            extras, permisos = extras_antes, permisos_antes
            if superior:
                for bandera in ("is_active", "is_staff", "is_superuser"):
                    valor = datos.get(bandera, getattr(cuenta, bandera))
                    if type(valor) is not bool:
                        raise ValidationError("Estado o privilegios no válidos.")
                    setattr(cuenta, bandera, valor)
                extras = {getattr(valor, "pk", valor) for valor in datos.get("grupos_extra", [])}
                permisos = {getattr(valor, "pk", valor) for valor in datos.get("user_permissions", [])}
                if set(Group.objects.using(using).exclude(name__in=ROLES_INTERNOS).filter(pk__in=extras).values_list("pk", flat=True)) != extras:
                    raise ValidationError("Los grupos adicionales no son válidos.")
                if set(Permission.objects.using(using).filter(pk__in=permisos).values_list("pk", flat=True)) != permisos:
                    raise ValidationError("Los permisos no son válidos.")
            rol = datos.get("rol") or ""
            if rol not in ROLES_INTERNOS and not (superior and cuenta.is_superuser and not rol):
                raise ValidationError("Selecciona un único rol operativo válido.")
            clave = datos.get("password1")
            if superior and clave and datos.get("password2") != clave:
                raise ValidationError("Las contraseñas no coinciden.")
            if nueva:
                if not clave:
                    raise ValidationError("Se requiere una contraseña inicial.")
                validate_password(clave, cuenta)
                cuenta.set_password(clave)
            cuenta.full_clean()
            cuenta.save(using=using)
            perfil, _ = Perfil.objects.using(using).get_or_create(usuario=cuenta)
            grupos = list(Group.objects.using(using).filter(pk__in=extras))
            if rol:
                grupos.append(crear_roles(using=using)[rol])
            cuenta.groups.set(grupos)
            cuenta.user_permissions.set(permisos)
            destino = normalizar_correo(personal["email"])
            mensaje = _preparar_correo(cuenta, perfil, destino, origen) if destino != normalizar_correo(cuenta.email) or perfil.correo_verificado_en is None else None
            if nueva:
                registrar_evento(gestor, USUARIO_CREADO, objeto=cuenta, using=using)
            elif basicos_antes != (cuenta.username, cuenta.first_name, cuenta.last_name) or mensaje:
                registrar_evento(gestor, "usuario.editado", objeto=cuenta, using=using)
            if roles_antes != ({rol} if rol else set()):
                registrar_evento(gestor, ROL_CAMBIADO, objeto=cuenta, using=using)
            if not nueva and activo_antes != cuenta.is_active:
                registrar_evento(gestor, "usuario.activado" if cuenta.is_active else "usuario.desactivado", objeto=cuenta, using=using)
            if privilegios_antes != (cuenta.is_staff, cuenta.is_superuser, extras, permisos):
                registrar_evento(gestor, "usuario.privilegios_cambiados", objeto=cuenta, using=using)
            if not nueva and clave:
                cuenta = _guardar_clave(cuenta, clave, "clave.cambiada", using, actor=gestor)
            if mensaje:
                _enviar_correo(*mensaje)
            return cuenta

    return _reintentar_sqlite(operacion, using)


def cambiar_estado_cuenta(actor, pk, *, activo):
    if not getattr(actor, "is_authenticated", False) or actor.pk is None:
        raise PermissionDenied
    if type(activo) is not bool:
        raise ValidationError("Indica el estado deseado de la cuenta.")
    using = actor._state.db or DEFAULT_DB_ALIAS

    def operacion():
        with transaction.atomic(using=using):
            gestor = _gestor_bloqueado(actor, using)
            cuenta = _objetivo_bloqueado(pk, using)
            _exigir_objetivo_operativo(gestor, cuenta)
            if cuenta.is_active != activo:
                cuenta.is_active = activo
                cuenta.save(using=using, update_fields=["is_active"])
                registrar_evento(gestor, "usuario.activado" if activo else "usuario.desactivado", objeto=cuenta, using=using)
            return cuenta

    return _reintentar_sqlite(operacion, using)
