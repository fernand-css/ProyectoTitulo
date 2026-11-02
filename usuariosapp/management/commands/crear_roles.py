"""Preparar los grupos operativos sin asignar usuarios."""

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections

from usuariosapp.services import crear_roles


class Command(BaseCommand):
    help = "Crea idempotentemente los tres grupos operativos; no asigna roles a cuentas."

    def add_arguments(self, parser):
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS, choices=tuple(connections))

    def handle(self, *args, **options):
        crear_roles(using=options["database"])
        self.stdout.write(self.style.SUCCESS("Grupos operativos preparados; cuentas y permisos conservados."))
