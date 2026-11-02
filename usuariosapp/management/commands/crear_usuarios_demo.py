"""Crear cuentas sintéticas con clave introducida fuera del historial del shell."""

import getpass
import os

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections

from usuariosapp.services import crear_cuentas_demo, faltan_cuentas_demo


class Command(BaseCommand):
    help = "Crea demo_qf, demo_tecnico y demo_terreno sin modificar cuentas existentes."

    def add_arguments(self, parser):
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS, choices=tuple(connections))
        parser.add_argument("--noinput", "--no-input", action="store_true")

    def handle(self, *args, **options):
        alias = options["database"]
        clave = None
        if faltan_cuentas_demo(using=alias):
            clave = os.environ.get("CESFAM_DEMO_PASSWORD")
            if not clave:
                if options["noinput"]:
                    raise CommandError("Define CESFAM_DEMO_PASSWORD para las nuevas cuentas sintéticas.")
                try:
                    clave = getpass.getpass("Contraseña inicial de las cuentas de demostración: ")
                    confirmacion = getpass.getpass("Confirma la contraseña: ")
                except (EOFError, KeyboardInterrupt):
                    raise CommandError("Preparación cancelada; no se crearon cuentas.") from None
                if clave != confirmacion:
                    raise CommandError("Las contraseñas no coinciden; no se crearon cuentas.")
        try:
            creadas, conservadas = crear_cuentas_demo(clave, using=alias)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from None
        self.stdout.write(self.style.SUCCESS(
            f"Cuentas sintéticas creadas: {len(creadas)}. Cuentas existentes conservadas: {len(conservadas)}."
        ))
        if conservadas:
            self.stdout.write("Las cuentas existentes no se modificaron; revisa su habilitación si procede.")
