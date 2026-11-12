"""Domicilios sintéticos con coordenadas para la demostración del mapa (spec 09, RF-09-13).

Solo para la base de demostración: crea, mediante el servicio auditado del 08 (`guardar_domicilio`), un domicilio
con coordenadas aleatorias dentro de un radio alrededor del origen (el CESFAM) para cada paciente elegible que aún
no tiene uno. Ninguna coordenada representa una vivienda real; las localidades y direcciones se rotulan como de
demostración. No verifica domicilios, no modifica los existentes y no programa entregas. Sin `--aplicar` solo
informa lo que haría.
"""

import math
from random import Random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from coreapp.mixins import tiene_rol
from coreapp.roles import JEFA
from entregasapp.consultas import elegibles
from entregasapp.ruta import Punto
from entregasapp.services import guardar_domicilio

METROS_POR_GRADO = 6_371_000 * math.pi / 180
SECTORES = ("verde", "azul", "rojo")
COLORES = ("roja", "azul", "verde", "blanca", "amarilla")
LOCALIDADES = 12


def datos_sinteticos(paciente_id, semilla, radio_km, origen):
    """Domicilio reproducible de un paciente: depende solo de la semilla y del identificador interno."""
    azar = Random(f"domicilio-demo:{semilla}:{paciente_id}")
    distancia = radio_km * 1000 * math.sqrt(azar.random())  # uniforme en el círculo
    angulo = azar.random() * 2 * math.pi
    norte, este = distancia * math.cos(angulo), distancia * math.sin(angulo)
    latitud = origen.latitud + norte / METROS_POR_GRADO
    longitud = origen.longitud + este / (METROS_POR_GRADO * math.cos(math.radians(origen.latitud)))
    numero = azar.randint(1, LOCALIDADES)
    return {
        "sector": azar.choice(SECTORES),
        "localidad": f"Localidad demo {numero}",
        "direccion": f"Camino demo {numero}, km {azar.randint(1, 15)} (dirección de demostración)",
        "referencias": f"Casa {azar.choice(COLORES)}, portón {azar.choice(COLORES)} (referencia de demostración)",
        "latitud": f"{latitud:.6f}",
        "longitud": f"{longitud:.6f}",
        "precision_metros": str(azar.randint(5, 30)),
    }


class Command(BaseCommand):
    help = ("SOLO PARA LA BASE DE DEMOSTRACIÓN. Crea domicilios sintéticos con coordenadas aleatorias para los "
            "pacientes elegibles al reparto que aún no tienen uno, mediante el servicio auditado. Sin --aplicar "
            "solo informa lo que haría. No verifica, no modifica domicilios existentes ni programa entregas.")

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Escribe en la base. Sin esta opción, solo simula.")
        parser.add_argument("--cuenta", help="Usuario de una cuenta Q.F. o superusuario activa; queda en la auditoría.")
        parser.add_argument("--semilla", type=int, default=909, help="Semilla de las coordenadas (reproducibles).")
        parser.add_argument("--radio-km", type=float, default=15.0, help="Radio alrededor del origen, en km (por defecto 15).")

    def handle(self, *args, **opciones):
        radio = opciones["radio_km"]
        if not (0 < radio <= 100):
            raise CommandError("El radio debe estar entre 0 y 100 km.")
        actor = self.cuenta(opciones["cuenta"], opciones["aplicar"])
        origen = Punto("origen", float(settings.REPARTO_ORIGEN_LATITUD), float(settings.REPARTO_ORIGEN_LONGITUD))
        pendientes = list(elegibles(timezone.localdate()).filter(domicilio__isnull=True).values_list("pk", flat=True))
        if not opciones["aplicar"]:
            self.stdout.write(
                f"Simulación: se crearían {len(pendientes)} domicilios sintéticos, sin verificar, dentro de {radio:g} km "
                "del origen. La base no fue modificada. Usa --aplicar --cuenta <usuario Q.F.> para crearlos."
            )
            return
        creados, omitidos = 0, 0
        for paciente_id in pendientes:
            datos = datos_sinteticos(paciente_id, opciones["semilla"], radio, origen)
            try:
                guardar_domicilio(actor, paciente_id, datos)
            except ValidationError:
                omitidos += 1  # ya tiene domicilio (creado en paralelo) o dejó de ser elegible
            else:
                creados += 1
        self.stdout.write(self.style.SUCCESS(
            f"Domicilios sintéticos creados: {creados}; omitidos: {omitidos}. Quedaron sin verificar y auditados a nombre "
            f"de la cuenta indicada. Radio: {radio:g} km del origen."
        ))

    def cuenta(self, usuario, aplicar):
        if not usuario:
            if aplicar:
                raise CommandError("Con --aplicar indica --cuenta con el usuario de una cuenta Q.F. o superusuario.")
            return None
        actor = get_user_model().objects.filter(username=usuario).first()
        if actor is None or not tiene_rol(actor, JEFA):
            raise CommandError("La cuenta indicada no existe o no es una cuenta Q.F. o superusuario activa.")
        return actor

