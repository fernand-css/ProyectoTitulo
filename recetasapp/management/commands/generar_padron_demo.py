"""Genera archivos sintéticos explícitos sin tocar la base de datos."""

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from recetasapp.importacion import filas_demo, generar_archivo


class Command(BaseCommand):
    help = "Genera un padrón sintético reproducible; no importa ni modifica pacientes."

    def add_arguments(self, parser):
        parser.add_argument("salida", type=Path)
        parser.add_argument("--formato", choices=["csv", "xlsx"], required=True)
        parser.add_argument("--semilla", type=int, default=3)
        parser.add_argument("--inicio", type=date.fromisoformat, default=date(2026, 1, 1))
        parser.add_argument("--sobrescribir", action="store_true")

    def handle(self, *args, **opciones):
        salida = opciones["salida"]
        contenido = generar_archivo(opciones["formato"], filas_demo(semilla=opciones["semilla"], inicio=opciones["inicio"]))
        try:
            with salida.open("wb" if opciones["sobrescribir"] else "xb") as archivo:
                archivo.write(contenido)
        except OSError:
            raise CommandError("No se pudo escribir la salida. Si ya existe, usa --sobrescribir explícitamente.") from None
        self.stdout.write(self.style.SUCCESS("Archivo sintético generado: 670 pacientes; la base no fue modificada."))
