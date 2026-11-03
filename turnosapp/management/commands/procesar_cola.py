"""Respaldo durable de la selección automática; no depende del navegador."""
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from turnosapp.cola import procesar_pendientes


class Command(BaseCommand):
    help = "Procesa pendientes una vez o con --continuo para recuperación automática."

    def add_arguments(self, parser):
        parser.add_argument("--continuo", action="store_true")
        parser.add_argument("--intervalo", type=float, default=1)
        parser.add_argument("--limite", type=int, default=100)

    def handle(self, *args, **options):
        if not 0 < options["intervalo"] <= 60 or not 1 <= options["limite"] <= 1000:
            raise CommandError("Intervalo debe estar entre 0 y 60 segundos y límite entre 1 y 1000.")
        try:
            while True:
                close_old_connections()
                cantidad = procesar_pendientes(options["limite"])
                if cantidad or not options["continuo"]:
                    self.stdout.write(f"Llamados confirmados: {cantidad}")
                if not options["continuo"]:
                    break
                time.sleep(options["intervalo"])
        except KeyboardInterrupt:
            self.stdout.write("Procesador detenido; pendientes conservados.")
