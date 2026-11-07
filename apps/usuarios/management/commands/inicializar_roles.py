"""Crear roles explícitos. Ejecutar solo sobre una base local autorizada."""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.usuarios.roles import ADMINISTRADOR, FUNCIONARIO, QF, TERRENO


class Command(BaseCommand):
    help = "Inicializa los cuatro grupos del primer incremento; no crea usuarios."

    @transaction.atomic
    def handle(self, *args, **options):
        # Cada combinación app/modelo/codename evita colisiones entre aplicaciones.
        permisos = {
            ADMINISTRADOR: [
                ("usuarios", "usuario", nombre)
                for nombre in ("add_usuario", "change_usuario", "view_usuario")
            ] + [
                ("auth", "group", nombre)
                for nombre in ("add_group", "change_group", "view_group")
            ] + [
                ("turnos", "ventanilla", nombre)
                for nombre in ("add_ventanilla", "change_ventanilla", "view_ventanilla", "configurar_ventanillas")
            ] + [
                ("turnos", "estadocola", "configurar_cola"),
                ("turnos", "turno", "cancelar_turnos"),
            ],
            FUNCIONARIO: [("turnos", "turno", "operar_turnos")],
            QF: [("turnos", "turno", "operar_turnos")],
            TERRENO: [],
        }
        for nombre, entradas in permisos.items():
            seleccionados = []
            for app, modelo, codename in entradas:
                try:
                    seleccionados.append(Permission.objects.get(
                        content_type__app_label=app,
                        content_type__model=modelo,
                        codename=codename,
                    ))
                except Permission.DoesNotExist as exc:
                    raise CommandError("Faltan permisos: primero deben aplicarse las migraciones autorizadas.") from exc
            grupo, _ = Group.objects.get_or_create(name=nombre)
            grupo.permissions.set(seleccionados)
        self.stdout.write(self.style.SUCCESS("Roles inicializados; terreno permanece sin operaciones."))
