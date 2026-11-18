"""Herramienta local; ejecutar únicamente con autorización independiente."""
import getpass
import json
import sys
import warnings

from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from apps.totem.services import (
    MOTIVOS, caducar_codigo_activacion, consultar_dispositivo,
    consumir_codigo_activacion, generar_codigo_activacion, revocar_dispositivo,
)


class Command(BaseCommand):
    help = "Gestiona dispositivos existentes; no crea dispositivos ni usuarios."
    requires_system_checks = []

    @staticmethod
    def _secreto(mensaje):
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            return getpass.getpass(mensaje)

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=("consultar", "generar", "consumir", "caducar", "revocar"))
        parser.add_argument("dispositivo", help="UUID técnico del dispositivo existente")
        parser.add_argument("--motivo", choices=MOTIVOS)

    def handle(self, *args, **options):
        # getpass puede degradar a entrada visible si no hay terminal. Rechazarlo.
        if not sys.stdin.isatty():
            raise CommandError("Se requiere una terminal interactiva para el ingreso oculto.")
        accion = options["accion"]
        dispositivo = options["dispositivo"]
        try:
            if accion == "consumir":
                referencia = input("Referencia de activación: ").strip()
                codigo = self._secreto("Código de activación (oculto): ")
                resultado = consumir_codigo_activacion(dispositivo, referencia, codigo)
                if resultado.estado != "activado":
                    raise CommandError("Activación rechazada.")
                self.stdout.write("Credencial técnica (única entrega): " + resultado.credencial)
                return
            nombre = input("Usuario administrativo local: ").strip()
            clave = self._secreto("Contraseña (oculta): ")
            usuario = authenticate(username=nombre, password=clave)
            if usuario is None or not usuario.is_active:
                raise CommandError("Autenticación administrativa rechazada.")
            if accion == "consultar":
                self.stdout.write(json.dumps(consultar_dispositivo(usuario, dispositivo), ensure_ascii=False))
                return
            if accion in ("generar", "revocar") and options["motivo"] is None:
                raise CommandError("Debe seleccionar --motivo.")
            if accion == "generar":
                resultado = generar_codigo_activacion(usuario, dispositivo, options["motivo"])
                self.stdout.write("Referencia: " + str(resultado.referencia))
                self.stdout.write("Código de activación (única entrega): " + resultado.codigo)
            elif accion == "caducar":
                resultado = caducar_codigo_activacion(usuario, dispositivo)
                self.stdout.write(resultado.estado)
            elif accion == "revocar":
                resultado = revocar_dispositivo(usuario, dispositivo, options["motivo"])
                self.stdout.write(resultado.estado)
        except (PermissionDenied, ValidationError):
            raise CommandError("Operación administrativa rechazada.") from None
        except DatabaseError:
            raise CommandError("No se pudo confirmar la operación en PostgreSQL.") from None
        except getpass.GetPassWarning:
            raise CommandError("No está disponible el ingreso oculto en esta terminal.") from None
        except (EOFError, KeyboardInterrupt):
            raise CommandError("Ingreso local cancelado.") from None
