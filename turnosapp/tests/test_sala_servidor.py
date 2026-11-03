"""Daphne/runserver real, SQLite temporal y emisor en otro proceso."""
import base64
import json
import os
import secrets
import socket
import struct
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from urllib.request import urlopen

from django.conf import settings
from django.test import SimpleTestCase


class ServidorSalaTests(SimpleTestCase):
    def test_runserver_http_estaticos_y_anuncio_desde_otro_proceso(self):
        with tempfile.TemporaryDirectory(prefix="cesfam-sala-asgi-") as carpeta:
            raiz = Path(carpeta)
            modulo = "qa_sala_asgi"
            (raiz / f"{modulo}.py").write_text(
                "from cesfam.settings import *\n"
                f"DATABASES = {{'default': {{'ENGINE': 'django.db.backends.sqlite3', 'NAME': {str(raiz / 'qa.sqlite3')!r}}}}}\n"
                "DEBUG = True\nALLOWED_HOSTS = ['127.0.0.1', 'localhost']\n",
                encoding="utf-8",
            )
            entorno = {**os.environ, "DJANGO_SETTINGS_MODULE": modulo,
                "SECRET_KEY": secrets.token_urlsafe(48), "DB_NAME": "sala_sintetica_qa",
                "PYTHONPATH": os.pathsep.join((str(raiz), str(settings.BASE_DIR))),
                "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
            comando = [sys.executable, str(settings.BASE_DIR / "manage.py")]
            opciones = {"cwd": settings.BASE_DIR, "env": entorno,
                "creationflags": subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0}

            def ejecutar(*argumentos):
                resultado = subprocess.run(comando + list(argumentos), capture_output=True,
                    text=True, encoding="utf-8", timeout=30, **opciones)
                self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)

            ejecutar("migrate", "--noinput", "--verbosity=0")
            ejecutar("shell", "-c", "\n".join([
                "from datetime import date",
                "from random import Random",
                "from django.contrib.auth import get_user_model",
                "from django.contrib.auth.models import Group",
                "from django.core.management import call_command",
                "from django.utils import timezone",
                "from coreapp.roles import TECNICO",
                "from coreapp.utils.sinteticos import generar_ruts",
                "from recetasapp.models import Paciente",
                "from usuariosapp.models import Perfil",
                "from turnosapp.models import Ventanilla, OcupacionVentanilla, Turno, PendienteSeleccion",
                "call_command('preparar_ventanillas', verbosity=0)",
                "usuario = get_user_model().objects.create_user(username='sala_asgi_sintetica')",
                "Perfil.objects.create(usuario=usuario)",
                "usuario.groups.add(Group.objects.get_or_create(name=TECNICO)[0])",
                "ventanilla = Ventanilla.objects.get(numero=1)",
                "ventanilla.operador = usuario",
                "ventanilla.automatico = True",
                "ventanilla.fecha_activacion = timezone.localdate()",
                "ventanilla.save()",
                "OcupacionVentanilla.objects.create(ventanilla=ventanilla, tecnico=usuario)",
                "paciente = Paciente.objects.create(rut=generar_ruts(1, Random(606))[0], nombres='SinteticoASGIPrivado', apellidos='Prueba', fecha_nacimiento=date(1970, 1, 1))",
                "Turno.objects.create(paciente=paciente, fecha=timezone.localdate(), numero=1, tipo_atencion='general')",
                "PendienteSeleccion.objects.create(fecha=timezone.localdate(), motivo='sala_asgi_sintetica')",
            ]))
            with closing(socket.socket()) as reserva:
                reserva.bind(("127.0.0.1", 0))
                puerto = reserva.getsockname()[1]
            base = f"http://127.0.0.1:{puerto}"
            with (raiz / "servidor.log").open("w+", encoding="utf-8") as registro:
                servidor = subprocess.Popen(comando + ["runserver", f"127.0.0.1:{puerto}", "--noreload"],
                    stdout=registro, stderr=subprocess.STDOUT, **opciones)
                try:
                    limite = time.monotonic() + 15
                    while True:
                        try:
                            with urlopen(base + "/turnos/sala/estado/", timeout=0.5) as respuesta:
                                self.assertIn("no-store", respuesta.headers["Cache-Control"])
                                self.assertIsNone(respuesta.headers.get("Set-Cookie"))
                                self.assertEqual(json.load(respuesta)["espera"]["cantidad"], 1)
                            break
                        except OSError:
                            if time.monotonic() >= limite or servidor.poll() is not None:
                                registro.seek(0)
                                self.fail("runserver no inició: " + registro.read())
                            time.sleep(0.05)
                    for ruta, marca in (("/turnos/sala/", b"sala-estado-inicial"), ("/static/css/base.css", b"--")):
                        with urlopen(base + ruta, timeout=3) as respuesta:
                            self.assertEqual(respuesta.status, 200)
                            self.assertIn(marca, respuesta.read())
                    with closing(socket.create_connection(("127.0.0.1", puerto), timeout=5)) as canal:
                        clave = base64.b64encode(secrets.token_bytes(16)).decode()
                        canal.sendall((f"GET /ws/sala/ HTTP/1.1\r\nHost: 127.0.0.1:{puerto}\r\n"
                            f"Origin: {base}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                            f"Sec-WebSocket-Key: {clave}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
                        with canal.makefile("rb") as flujo:
                            self.assertIn(b"101", flujo.readline())
                            for _ in range(32):
                                linea = flujo.readline()
                                self.assertTrue(linea, "Se cerró la negociación WebSocket")
                                if linea == b"\r\n":
                                    break
                            else:
                                self.fail("La negociación WebSocket excedió las cabeceras esperadas")

                            def recibir():
                                cabecera = flujo.read(2)
                                self.assertEqual(len(cabecera), 2)
                                self.assertEqual(cabecera[0] & 0x0f, 1)
                                largo = cabecera[1] & 0x7f
                                if largo == 126:
                                    largo = struct.unpack("!H", flujo.read(2))[0]
                                elif largo == 127:
                                    largo = struct.unpack("!Q", flujo.read(8))[0]
                                return json.loads(flujo.read(largo))

                            self.assertEqual(recibir()["tipo"], "estado")
                            ejecutar("shell", "-c", "from django.core.management import call_command; call_command('procesar_cola')")
                            anuncio = recibir()
                            self.assertEqual(anuncio["tipo"], "anuncio")
                            self.assertEqual((anuncio["numero"], anuncio["ventanilla"]), (1, 1))
                            self.assertNotIn("SinteticoASGIPrivado", json.dumps(anuncio))
                            self.assertEqual(recibir()["tipo"], "estado")
                    registro.flush()
                    registro.seek(0)
                    log = registro.read()
                    self.assertIn("ASGI/Daphne", log)
                    self.assertNotIn("SinteticoASGIPrivado", log)
                finally:
                    servidor.terminate()
                    try:
                        servidor.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        servidor.kill()
                        servidor.wait(timeout=5)
