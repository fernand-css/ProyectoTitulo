"""QA HTTP reproducible del 03 en SQLite temporal; nunca usa la base local.

--preview mantiene solo en localhost copias HTML sintéticas de solo lectura
para revisión visual. Ctrl+C cierra servidor y elimina la SQLite temporal.
"""

import argparse
import http.cookiejar
import io
import json
import logging
import os
import re
import secrets
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from wsgiref.simple_server import WSGIRequestHandler, make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
opciones = argparse.ArgumentParser(description=__doc__)
opciones.add_argument("--preview", action="store_true")
argumentos = opciones.parse_args()
os.environ.update(DJANGO_SETTINGS_MODULE="cesfam.settings", SECRET_KEY=secrets.token_urlsafe(48), DEBUG="True", ALLOWED_HOSTS="127.0.0.1,localhost")
from django.conf import settings

temporal = tempfile.TemporaryDirectory(prefix="cesfam-spec03-")
settings.DATABASES["default"]["NAME"] = str(Path(temporal.name) / "qa.sqlite3")
settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
import django
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.handlers.wsgi import WSGIHandler
from django.core.management import call_command
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from coreapp.roles import ENCARGADO, JEFA, TECNICO
from recetasapp.importacion import filas_demo, generar_archivo
from recetasapp.models import EntregaReceta, Paciente, Receta
from usuariosapp.models import Perfil

paginas = {}
servidor = None
hilo = None
try:
    call_command("migrate", verbosity=0, interactive=False)
    clave = "QA-" + secrets.token_urlsafe(24) + "9!"
    for nombre, rol in (("qf", JEFA), ("tecnico", TECNICO), ("encargado", ENCARGADO)):
        usuario = get_user_model().objects.create_user(username="qa_" + nombre, password=clave)
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])

    class Silencioso(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    aplicacion = StaticFilesHandler(WSGIHandler())

    def servir(environ, start_response):
        ruta = environ.get("PATH_INFO", "")
        if ruta.startswith("/qa/"):
            if environ["REQUEST_METHOD"] != "GET":
                start_response("405 Method Not Allowed", [("Content-Type", "text/plain")])
                return [b"Vista de solo lectura"]
            nombre = ruta.removeprefix("/qa/")
            if not nombre:
                cuerpo = '<!doctype html><html lang="es-CL"><meta charset="utf-8"><title>QA spec 03</title><h1>Revisión sintética del spec 03</h1><ul>' + "".join(f'<li><a href="/qa/{clave}.html">{clave}</a></li>' for clave in paginas) + "</ul></html>"
            else:
                cuerpo = paginas.get(nombre.removesuffix(".html"))
            start_response("200 OK" if cuerpo else "404 Not Found", [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")])
            return [(cuerpo or "No existe").encode()]
        return aplicacion(environ, start_response)

    logging.getLogger("django.request").setLevel(logging.CRITICAL)
    servidor = make_server("127.0.0.1", 0, servir, handler_class=Silencioso)
    base = f"http://127.0.0.1:{servidor.server_port}"
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()

    class ClienteHTTP:
        def __init__(self):
            self.jar = http.cookiejar.CookieJar()
            self.opener = build_opener(HTTPCookieProcessor(self.jar))

        def pedir(self, ruta, datos=None, archivo=None, csrf=True):
            url = urljoin(base, ruta)
            cabeceras = {"Referer": url}
            cuerpo = None
            if datos is not None:
                cabeceras["Origin"] = base
                datos = dict(datos)
                if csrf:
                    datos["csrfmiddlewaretoken"] = next((c.value for c in self.jar if c.name == "csrftoken"), "")
                if archivo:
                    frontera = "spec03-" + secrets.token_hex(12)
                    partes = []
                    for nombre, valor in datos.items():
                        partes.append(f'--{frontera}\r\nContent-Disposition: form-data; name="{nombre}"\r\n\r\n{valor}\r\n'.encode())
                    partes.append(f'--{frontera}\r\nContent-Disposition: form-data; name="archivo"; filename="padron.{archivo[0]}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + archivo[1] + b"\r\n")
                    partes.append(f"--{frontera}--\r\n".encode())
                    cuerpo = b"".join(partes)
                    cabeceras["Content-Type"] = f"multipart/form-data; boundary={frontera}"
                else:
                    cuerpo = urlencode(datos).encode()
            try:
                with self.opener.open(Request(url, data=cuerpo, headers=cabeceras), timeout=120) as respuesta:
                    return respuesta.status, respuesta.read().decode("utf-8"), urlsplit(respuesta.url).path
            except HTTPError as respuesta:
                return respuesta.code, respuesta.read().decode("utf-8"), urlsplit(respuesta.url).path

        def login(self, nombre):
            self.pedir("/usuarios/entrar/")
            estado, _, ruta = self.pedir("/usuarios/entrar/", {"username": "qa_" + nombre, "password": clave})
            assert estado == 200 and ruta == "/"

    qf, tecnico, encargado = ClienteHTTP(), ClienteHTTP(), ClienteHTTP()
    for cliente, rol in ((qf, "qf"), (tecnico, "tecnico"), (encargado, "encargado")):
        cliente.login(rol)
    importacion_ruta = "/recetas/importaciones/nueva/"
    tiempos_carga = {}
    datos_demo = list(filas_demo(inicio=timezone.localdate()))
    for formato in ("csv", "xlsx"):
        qf.pedir(importacion_ruta)
        inicio = time.perf_counter()
        estado, html, reporte = qf.pedir(importacion_ruta, {"formato": formato, "sintetico": "on"}, (formato, generar_archivo(formato, datos_demo)))
        tiempos_carga[formato] = round(time.perf_counter() - inicio, 3)
        assert estado == 200 and "Reporte de importación" in html
        assert Paciente.objects.count() == 670 and Receta.objects.count() == 670
        assert "Fallida" not in html
    receta = Receta.objects.get(codigo="DEMO-0001")
    detalle = f"/recetas/{receta.pk}/"
    entrega = detalle + "entregas/confirmar/"
    tecnico.pedir(entrega)
    operacion = str(uuid.uuid4())
    datos_entrega = {"operacion_id": operacion, "confirmar": "on"}
    assert tecnico.pedir(entrega, datos_entrega, csrf=False)[0] == 403
    assert qf.pedir(entrega, datos_entrega)[0] == 403
    assert encargado.pedir(detalle)[0] == 403
    assert tecnico.pedir(importacion_ruta)[0] == 403
    for _ in range(2):
        assert tecnico.pedir(entrega, datos_entrega)[0] == 200
    receta.refresh_from_db()
    assert receta.entregas_completadas == 1 and EntregaReceta.objects.count() == 1
    renovar = detalle + "renovar/"
    qf.pedir(renovar)
    assert qf.pedir(renovar, {"paciente": 999999, "codigo": "QA-RENOVADA", "fecha_inicio": timezone.localdate().isoformat(), "vigencia_meses": 12, "max_entregas": 6})[0] == 200
    renovada = Receta.objects.get(codigo="QA-RENOVADA")
    assert renovada.receta_anterior_id == receta.pk and renovada.entregas_completadas == 0
    cambiado = list(datos_demo[0])
    cambiado[11] = "6"
    qf.pedir(importacion_ruta)
    estado, html, reporte = qf.pedir(importacion_ruta, {"formato": "csv", "sintetico": "on"}, ("csv", generar_archivo("csv", [cambiado])))
    assert estado == 200 and "Rechazada" in html
    receta.refresh_from_db()
    assert receta.max_entregas == 12 and receta.entregas_completadas == 1
    muestras = []
    for _ in range(40):
        inicio = time.perf_counter()
        assert tecnico.pedir(detalle)[0] == 200
        muestras.append(time.perf_counter() - inicio)
    p95 = sorted(muestras)[37]
    assert p95 <= 2
    for nombre, ruta, cliente in [
        ("padron", "/recetas/pacientes/", qf),
        ("paciente", f"/recetas/pacientes/{receta.paciente_id}/", tecnico),
        ("receta", detalle, tecnico), ("nueva", "/recetas/nueva/", qf),
        ("renovar", renovar, qf), ("entrega", entrega, tecnico),
        ("importar", importacion_ruta, qf), ("cargas", "/recetas/importaciones/", qf),
        ("reporte", reporte, qf),
    ]:
        estado, cuerpo, _ = cliente.pedir(ruta)
        assert estado == 200
        paginas[nombre] = cuerpo
    paginas["error-receta"] = qf.pedir("/recetas/nueva/", {})[1]
    paginas["error-entrega"] = tecnico.pedir(entrega, {})[1]
    paginas["error-importacion"] = qf.pedir(importacion_ruta, {})[1]
    resumen = {
        "migraciones": MigrationRecorder.Migration.objects.count(), "pacientes": Paciente.objects.count(),
        "importacion_csv_y_xlsx_segundos": tiempos_carga, "recetas": Receta.objects.count(),
        "entrega_idempotente": True, "historial_protegido": True, "renovacion_vinculada": True,
        "http_y_csrf": "aprobados", "muestras_detalle": len(muestras), "detalle_p95_segundos": round(p95, 4),
        "base_local": "sin modificar", "paginas_sinteticas": len(paginas),
    }
    if argumentos.preview:
        resumen["preview_url"] = base + "/qa/"
    print(json.dumps(resumen, ensure_ascii=False), flush=True)
    if argumentos.preview:
        print("Vista sintética de solo lectura lista; Ctrl+C para cerrar.", flush=True)
        while True:
            time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    if servidor:
        servidor.shutdown()
        servidor.server_close()
    if hilo:
        hilo.join(timeout=5)
    connections.close_all()
    temporal.cleanup()
