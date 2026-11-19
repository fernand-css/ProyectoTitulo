"""Procesa la bandeja de salida del reparto fuera de las solicitudes web."""

from time import sleep

from django.core.management.base import BaseCommand

from entregasapp import notificaciones


class Command(BaseCommand):
    help = "Procesa avisos de reparto por SMTP o con correo simulado en memoria."

    def add_arguments(self, parser):
        modos = parser.add_mutually_exclusive_group(required=True)
        modos.add_argument("--simular", action="store_true")
        modos.add_argument("--smtp", action="store_true")
        parser.add_argument("--continuo", action="store_true")

    def handle(self, *args, **opciones):
        smtp = opciones["smtp"]
        transporte = notificaciones.enviar_smtp if smtp else notificaciones.enviar_simulado
        try:
            while True:
                procesados = notificaciones.procesar_avisos(transporte)
                if procesados or not opciones["continuo"]:
                    self.stdout.write(f"Avisos procesados: {procesados}.")
                if not opciones["continuo"]:
                    return
                sleep(5)
        except KeyboardInterrupt:
            return
