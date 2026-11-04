"""Copia al sistema las noticias más recientes del sitio de la Municipalidad de San Nicolás."""

from django.core.management.base import BaseCommand, CommandError

from coreapp import noticias


class Command(BaseCommand):
    help = (
        "Lee las noticias públicas de municipalidadsannicolas.cl y las guarda para el inicio. "
        "Si el sitio no responde, conserva las que ya estaban guardadas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--maximo", type=int, default=noticias.MAXIMO_POR_DEFECTO,
            help=f"Cantidad de noticias a revisar (por defecto {noticias.MAXIMO_POR_DEFECTO}).",
        )

    def handle(self, *args, maximo, **opciones):
        if maximo < 1:
            raise CommandError("--maximo debe ser al menos 1.")
        try:
            nuevas, actualizadas, sin_detalle = noticias.actualizar(maximo=maximo)
        except noticias.ErrorNoticias as error:
            raise CommandError(f"No se actualizaron las noticias: {error}") from error
        self.stdout.write(self.style.SUCCESS(f"Noticias: {nuevas} nuevas y {actualizadas} ya conocidas."))
        if sin_detalle:
            self.stdout.write(self.style.WARNING(
                f"{sin_detalle} sin fecha por ahora; se reintenta en la próxima actualización."
            ))
