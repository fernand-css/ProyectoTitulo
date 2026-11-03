"""Preparación idempotente del prototipo, sin cuentas ni llamados."""
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from coreapp.auditoria import registrar_accion
from turnosapp.models import TipoAtencionVentanilla, ConfiguracionCola, Turno, Ventanilla


class Command(BaseCommand):
    help = "Prepara cuatro ventanillas y pesos 2:1:1 sin activar el automatismo ni cambiar configuración existente."

    def add_arguments(self, parser):
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS, choices=tuple(connections))

    def handle(self, *args, **options):
        alias = options["database"]
        with transaction.atomic(using=alias):
            tipos = []
            for codigo, _ in Turno.TipoAtencion.choices:
                tipo, creado = TipoAtencionVentanilla.objects.using(alias).get_or_create(codigo=codigo)
                tipos.append(tipo)
                if creado:
                    registrar_accion(None, "cola.tipo_preparado", tipo, using=alias)
            config, creada = ConfiguracionCola.objects.using(alias).get_or_create(pk=1)
            if creada:
                registrar_accion(None, "cola.config_preparada", config, using=alias)
            for numero in range(1, 5):
                ventanilla, creada = Ventanilla.objects.using(alias).get_or_create(numero=numero)
                if creada:
                    ventanilla.tipos.set(tipos)
                    registrar_accion(None, "ventanilla.preparada", ventanilla, using=alias)
        self.stdout.write(self.style.SUCCESS("Ventanillas preparadas; configuración previa conservada; sin activar llamados."))
