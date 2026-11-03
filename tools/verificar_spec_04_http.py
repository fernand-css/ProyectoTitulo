"""QA HTTP del tótem y p95 con 670 pacientes sintéticos en SQLite temporal.

No usa la base local, no envía mensajes ni configura impresoras.
"""
import http.cookiejar
import json
import logging
import math
import os
import platform
import re
import secrets
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from random import Random
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request
from wsgiref.simple_server import make_server, WSGIRequestHandler
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# HTTP exclusivamente en loopback, como la herramienta del 03. DEBUG permite
# cookies de desarrollo sin HTTPS; no modifica settings.py ni el entorno padre.
os.environ.update(DJANGO_SETTINGS_MODULE="cesfam.settings", SECRET_KEY=secrets.token_urlsafe(48), DEBUG="True", ALLOWED_HOSTS="127.0.0.1,localhost")
from django.conf import settings


def main():
    with tempfile.TemporaryDirectory(prefix="cesfam-spec04-") as temporal:
        settings.DATABASES["default"]["NAME"] = str(Path(temporal) / "qa.sqlite3")
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        import django
        django.setup()
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.core.handlers.wsgi import WSGIHandler
        from django.core.management import call_command
        from django.db import connections
        from django.db.migrations.recorder import MigrationRecorder
        from django.utils import timezone
        from coreapp.utils.sinteticos import generar_ruts
        from coreapp.models import RegistroAuditoria
        from recetasapp.models import Paciente, Receta, EntregaReceta
        from turnosapp.models import Turno

        servidor = hilo = None
        try:
            call_command("migrate", verbosity=0, interactive=False)
            hoy = timezone.localdate()
            for indice, rut in enumerate(generar_ruts(670, Random(4040))):
                paciente = Paciente.objects.create(
                    rut=rut, nombres="Paciente sintético", apellidos=f"Demostración {indice}",
                    fecha_nacimiento=date(1940 if 570 <= indice < 620 else (1950 if indice % 3 == 0 else 1970), 1, 1),
                    es_cronico=indice % 2 == 0, es_postrado=indice >= 620,
                )
                Receta.objects.create(paciente=paciente, codigo=f"HTTP-DEMO-{indice}", fecha_inicio=hoy,
                    fecha_fin_exclusiva=hoy + timedelta(days=30), vigencia_meses=1, max_entregas=3)

            class Silencioso(WSGIRequestHandler):
                def log_message(self, *args):
                    pass

            class ServidorConcurrente(ThreadingMixIn, WSGIServer):
                daemon_threads = True

            logging.getLogger("django.request").setLevel(logging.CRITICAL)
            servidor = make_server("127.0.0.1", 0, StaticFilesHandler(WSGIHandler()),
                server_class=ServidorConcurrente, handler_class=Silencioso)
            base = f"http://127.0.0.1:{servidor.server_port}"
            hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
            hilo.start()

            class Cliente:
                def __init__(self):
                    self.cookies = http.cookiejar.CookieJar()
                    self.http = build_opener(HTTPCookieProcessor(self.cookies))

                def pedir(self, ruta="/turnos/totem/", datos=None, csrf=True):
                    cabeceras = {"Referer": base + ruta, "Origin": base}
                    cuerpo = None
                    if datos is not None:
                        datos = dict(datos)
                        if csrf:
                            datos["csrfmiddlewaretoken"] = next((c.value for c in self.cookies if c.name == "csrftoken"), "")
                        cuerpo = urlencode(datos).encode()
                    inicio = time.perf_counter()
                    try:
                        respuesta = self.http.open(Request(base + ruta, data=cuerpo, headers=cabeceras), timeout=30)
                    except HTTPError as error:
                        respuesta = error
                    with respuesta:
                        texto = respuesta.read().decode()
                        return respuesta.status, texto, time.perf_counter() - inicio, respuesta.headers

                def abrir(self):
                    estado, html, _, cabeceras = self.pedir()
                    assert estado == 200 and "no-store" in cabeceras["Cache-Control"]
                    return re.search(r'name="operacion_id" value="([^"]+)"', html).group(1)

            pacientes = list(Paciente.objects.order_by("pk"))
            cliente = Cliente()
            op = cliente.abrir()
            datos = {"rut": pacientes[0].rut, "operacion_id": op}
            assert cliente.pedir(datos=datos, csrf=False)[0] == 403
            estado, html, _, _ = cliente.pedir(datos=datos)
            assert estado == 200 and 'class="comprobante"' in html, f"Primera emisión HTTP: estado {estado}"
            assert pacientes[0].rut not in html and pacientes[0].nombres not in html
            assert cliente.pedir(datos=datos)[0] == 200 and Turno.objects.count() == 1
            ajeno = Cliente()
            ajeno.abrir()
            assert ajeno.pedir(datos=datos)[0] == 400
            assert cliente.pedir("/turnos/totem/continuar/", {"operacion_id": op})[0] == 200
            assert cliente.pedir("/turnos/totem/finalizar/", {"operacion_id": op})[0] == 200
            assert cliente.pedir(datos=datos)[0] == 400
            for ruta in ("/static/css/turnos.css", "/static/js/totem.js"):
                assert cliente.pedir(ruta)[0] == 200

            medidas = {}
            for escenario in ("emision", "recuperacion", "rechazo_domicilio"):
                duraciones = []
                for indice in range(100):
                    op = cliente.abrir()
                    paciente = pacientes[indice + 1] if escenario == "emision" else pacientes[0 if escenario == "recuperacion" else 620]
                    estado, html, duracion, _ = cliente.pedir(datos={"rut": paciente.rut, "operacion_id": op})
                    assert estado == (400 if escenario == "rechazo_domicilio" else 200)
                    assert paciente.rut not in html
                    duraciones.append(duracion)
                medidas[escenario] = {"muestras": 100, "solicitudes_simultaneas": 1,
                    "p95_ms": round(sorted(duraciones)[math.ceil(.95 * len(duraciones)) - 1] * 1000, 2)}

            def emitir_independiente(indice):
                propio = Cliente()
                operacion = propio.abrir()
                return propio.pedir(datos={"rut": pacientes[indice].rut, "operacion_id": operacion})[0]

            for indices in ([110, 110, 110], [111, 112, 113]):
                with ThreadPoolExecutor(max_workers=3) as pool:
                    assert list(pool.map(emitir_independiente, indices)) == [200] * 3
            assert Turno.objects.count() == 105
            assert len(set(Turno.objects.values_list("fecha", "numero"))) == 105
            assert RegistroAuditoria.objects.filter(accion="turno.emitido").count() == 105
            assert not EntregaReceta.objects.exists()
            assert not Receta.objects.exclude(entregas_completadas=0).exists()
            informe = {"fecha": hoy.isoformat(), "python": platform.python_version(), "django": django.get_version(),
                "sistema": platform.platform(), "migraciones": MigrationRecorder.Migration.objects.count(),
                "pacientes_sinteticos": 670, "turnos": 105, "http": "aprobado", "mediciones": medidas,
                "limites": ["Equipo local, WSGI de prueba y carga secuencial; no prueba de producción", "Sin navegador ni impresora física"]}
            print(json.dumps(informe, ensure_ascii=False, indent=2), flush=True)
            assert all(m["p95_ms"] <= 2000 for m in medidas.values()), "p95 excede RNF-05 en el entorno medido"
        finally:
            if servidor:
                servidor.shutdown()
                servidor.server_close()
            if hilo:
                hilo.join(timeout=5)
            connections.close_all()
    print("Servidor cerrado y SQLite temporal de QA eliminada.", flush=True)


if __name__ == "__main__":
    main()
