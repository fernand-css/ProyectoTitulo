"""El comando genera archivos sintéticos sin modificar el dominio."""

import io
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from recetasapp.importacion import leer_archivo
from recetasapp.models import Paciente


class ComandoTests(TestCase):
    def test_genera_ambos_formatos_no_sobrescribe_y_no_toca_base(self):
        with tempfile.TemporaryDirectory(prefix="spec03-comando-") as directorio:
            for formato in ("csv", "xlsx"):
                salida = Path(directorio) / ("padron." + formato)
                call_command("generar_padron_demo", str(salida), formato=formato, stdout=io.StringIO())
                self.assertEqual(len(leer_archivo(salida.read_bytes(), formato)), 670)
                with self.assertRaises(CommandError):
                    call_command("generar_padron_demo", str(salida), formato=formato, stdout=io.StringIO())
                call_command("generar_padron_demo", str(salida), formato=formato, sobrescribir=True, stdout=io.StringIO())
            self.assertFalse(Paciente.objects.exists())
