"""Preparación sintética para pruebas del planificador, sin UI de operación."""
import io
from datetime import date, datetime, timedelta, timezone as tz
from random import Random
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.utils import timezone
from coreapp.roles import TECNICO
from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import Paciente
from recetasapp.tests.ayudas import actores
from turnosapp.models import OcupacionVentanilla, PendienteSeleccion, Turno, Ventanilla
from usuariosapp.models import Perfil


class DatosCola:
    def setUp(self):
        self.ahora = datetime(2026, 11, 2, 15, tzinfo=tz.utc)
        self.fecha = timezone.localdate(self.ahora)
        reloj = patch("turnosapp.cola.timezone.now", return_value=self.ahora)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.personal = actores()
        self.ruts = generar_ruts(50, Random(502))
        self.numero = 0
        call_command("preparar_ventanillas", stdout=io.StringIO())

    def activar(self, numero=1, tipos=("general", "preferencial", "cronicos")):
        if numero == 1:
            operador = self.personal["tecnico"]
        else:
            operador = get_user_model().objects.create_user(username=f"tecnico_cola_demo_{numero}")
            Perfil.objects.create(usuario=operador)
            operador.groups.add(Group.objects.get(name=TECNICO))
        ventanilla = Ventanilla.objects.get(numero=numero)
        ventanilla.operador = operador
        ventanilla.automatico = True
        ventanilla.fecha_activacion = self.fecha
        ventanilla.disponible_desde = self.ahora + timedelta(seconds=numero)
        ventanilla.save()
        ventanilla.tipos.set(tipos)
        OcupacionVentanilla.objects.create(ventanilla=ventanilla, tecnico=operador)
        return ventanilla

    def turno(self, tipo="general", espera=0):
        self.numero += 1
        paciente = Paciente.objects.create(rut=self.ruts[self.numero], nombres="Paciente sintético",
            apellidos="Cola", fecha_nacimiento=date(1970, 1, 1))
        return Turno.objects.create(paciente=paciente, fecha=self.fecha, numero=self.numero,
            tipo_atencion=tipo, entrada_cola=self.ahora - timedelta(seconds=espera))

    def pendiente(self):
        return PendienteSeleccion.objects.create(fecha=self.fecha, motivo="prueba_sintetica")

    def cerrar_fixture(self):
        Turno.objects.filter(estado="llamado").update(estado="atendido", cerrado_en=self.ahora,
            ventanilla=None, operador=None)
