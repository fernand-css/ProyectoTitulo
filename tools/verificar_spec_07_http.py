"""Recorrido HTTP de preparación y p95 con SQLite temporal y datos sintéticos.

Ejecutar con el Python del venv. No usa ni migra la base PostgreSQL del proyecto.
"""
import http.cookiejar
import json
import logging
import math
import os
import re
import secrets
import sys
import tempfile
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from random import Random
from socketserver import ThreadingMixIn
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
import threading

PROYECTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROYECTO))
os.environ.update(
    DJANGO_SETTINGS_MODULE="cesfam.settings",
    SECRET_KEY=secrets.token_urlsafe(48),
    DB_NAME="qa07_sintetica",
    DEBUG="True",
    ALLOWED_HOSTS="127.0.0.1,localhost",
    PYTHONUNBUFFERED="1",
    PYTHONUTF8="1",
)

from django.conf import settings


def resumen(valores):
    ordenados = sorted(valores)
    return {
        "muestras": len(valores),
        "p50_ms": round(ordenados[math.ceil(.5 * len(valores)) - 1] * 1000, 2),
        "p95_ms": round(ordenados[math.ceil(.95 * len(valores)) - 1] * 1000, 2),
        "maximo_ms": round(max(valores) * 1000, 2),
    }


class ClienteHTTP:
    def __init__(self, base):
        self.base = base
        self.cookies = http.cookiejar.CookieJar()
        self.http = build_opener(HTTPCookieProcessor(self.cookies))

    def pedir(self, ruta, datos=None):
        cuerpo = None
        if datos is not None:
            valores = dict(datos)
            valores["csrfmiddlewaretoken"] = next(
                (cookie.value for cookie in self.cookies if cookie.name == "csrftoken"), ""
            )
            cuerpo = urlencode(valores, doseq=True).encode()
        inicio = time.perf_counter()
        solicitud = Request(
            self.base + ruta,
            data=cuerpo,
            headers={"Referer": self.base + ruta, "Origin": self.base},
        )
        try:
            respuesta = self.http.open(solicitud, timeout=20)
        except HTTPError as error:
            respuesta = error
        with respuesta:
            return respuesta.status, respuesta.read().decode(), respuesta.headers, time.perf_counter() - inicio

    def entrar(self, nombre, clave):
        estado, _, _, _ = self.pedir("/usuarios/entrar/")
        assert estado == 200
        estado, _, _, _ = self.pedir("/usuarios/entrar/", {"username": nombre, "password": clave})
        assert estado == 200, f"No se pudo autenticar {nombre}"


def ejecutar(base_datos):
    settings.DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": str(base_datos)}
    import django
    django.setup()

    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.core.handlers.wsgi import WSGIHandler
    from django.core.management import call_command
    from django.db import connections
    from django.utils import timezone
    from coreapp.roles import JEFA, TECNICO
    from coreapp.utils.sinteticos import generar_ruts
    from recetasapp.models import EntregaReceta, Paciente, PreparacionReceta, Receta
    from turnosapp.models import OcupacionVentanilla, Turno, Ventanilla
    from usuariosapp.models import Perfil

    call_command("migrate", verbosity=0, interactive=False)
    call_command("preparar_ventanillas", verbosity=0)
    hoy = timezone.localdate()
    pacientes = Paciente.objects.bulk_create([
        Paciente(
            rut=rut,
            nombres="QA07Privado",
            apellidos=f"Sintetico {indice:03d}",
            fecha_nacimiento=date(1970, 1, 1),
        )
        for indice, rut in enumerate(generar_ruts(670, Random(707)))
    ])
    Receta.objects.bulk_create([
        Receta(
            paciente=paciente,
            codigo=f"QA07-{indice:03d}",
            fecha_inicio=hoy,
            fecha_fin_exclusiva=hoy + timedelta(days=30),
            vigencia_meses=1,
            max_entregas=3,
        )
        for indice, paciente in enumerate(pacientes)
    ])

    clave = secrets.token_urlsafe(24)
    tecnicos = {}
    for numero in range(1, 5):
        usuario = get_user_model().objects.create_user(username=f"qa07_tecnico_{numero}", password=clave)
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=TECNICO)[0])
        ventanilla = Ventanilla.objects.get(numero=numero)
        ventanilla.operador = usuario
        ventanilla.automatico = True
        ventanilla.fecha_activacion = hoy
        ventanilla.disponible_desde = timezone.now()
        ventanilla.save()
        OcupacionVentanilla.objects.create(ventanilla=ventanilla, tecnico=usuario)
        tecnicos[usuario.username] = usuario
    qf = get_user_model().objects.create_user(username="qa07_qf", password=clave)
    Perfil.objects.create(usuario=qf)
    qf.groups.add(Group.objects.get_or_create(name=JEFA)[0])

    class Silencioso(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    class ServidorConcurrente(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    logging.getLogger("django.request").setLevel(logging.CRITICAL)
    servidor = make_server(
        "127.0.0.1", 0, WSGIHandler(), server_class=ServidorConcurrente, handler_class=Silencioso
    )
    base = f"http://127.0.0.1:{servidor.server_port}"
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()

    personal = {nombre: ClienteHTTP(base) for nombre in tecnicos}
    for nombre, cliente in personal.items():
        cliente.entrar(nombre, clave)
    farmacia = ClienteHTTP(base)
    farmacia.entrar("qa07_qf", clave)
    totem = ClienteHTTP(base)

    mediciones = {
        nombre: [] for nombre in (
            "emision_con_estimacion", "lista_preparacion", "marcar_lista",
            "ausente", "pendientes_retiro", "retirar_preparado", "panel_05",
        )
    }
    try:
        for indice in range(100):
            estado, formulario, _, _ = totem.pedir("/turnos/totem/")
            assert estado == 200
            operacion = re.search(r'name="operacion_id" value="([^"]+)"', formulario).group(1)
            estado, html, cabeceras, duracion = totem.pedir("/turnos/totem/", {
                "rut": pacientes[indice].rut,
                "operacion_id": operacion,
            })
            assert estado == 200 and "Tiempo aproximado de espera:" in html
            assert "QA07Privado" not in html and pacientes[indice].rut not in html
            assert "no-store" in cabeceras.get("Cache-Control", "")
            mediciones["emision_con_estimacion"].append(duracion)

        assert Turno.objects.filter(fecha=hoy, estado="llamado").count() == 4
        assert PreparacionReceta.objects.filter(turno_receta__turno__fecha=hoy, lista_en__isnull=True).count() == 100

        for _ in range(100):
            turno = Turno.objects.filter(fecha=hoy, estado="llamado").select_related("operador").order_by(
                "ultimo_llamado", "pk"
            ).first()
            assert turno is not None and turno.operador_id
            preparacion = PreparacionReceta.objects.get(turno_receta__turno=turno)

            estado, html, cabeceras, duracion = farmacia.pedir("/recetas/preparacion/")
            assert estado == 200 and "no-store" in cabeceras.get("Cache-Control", "")
            assert re.search(rf'action="/recetas/preparacion/{preparacion.pk}/lista/"', html)
            mediciones["lista_preparacion"].append(duracion)

            estado, _, cabeceras, duracion = farmacia.pedir(
                f"/recetas/preparacion/{preparacion.pk}/lista/", {}
            )
            assert estado == 200 and "no-store" in cabeceras.get("Cache-Control", "")
            mediciones["marcar_lista"].append(duracion)
            preparacion.refresh_from_db()
            assert preparacion.lista_en is not None

            # Se satisface el minuto de espera del flujo de ausencia sin dormir la medición.
            Turno.objects.filter(pk=turno.pk).update(ultimo_llamado=timezone.now() - timedelta(minutes=2))
            cliente_tecnico = personal[turno.operador.username]
            estado, _, cabeceras, duracion = cliente_tecnico.pedir(
                f"/turnos/{turno.pk}/ausente/", {"operacion_id": str(uuid.uuid4())}
            )
            assert estado == 200 and "no-store" in cabeceras.get("Cache-Control", "")
            mediciones["ausente"].append(duracion)
            turno.refresh_from_db()
            assert turno.estado == "ausente"

            estado, pendientes, cabeceras, duracion = farmacia.pedir("/recetas/preparacion/pendientes/")
            assert estado == 200 and "no-store" in cabeceras.get("Cache-Control", "")
            assert "QA07Privado" in pendientes
            assert re.search(rf'action="/recetas/preparacion/{preparacion.pk}/retirar/"', pendientes)
            operacion_retiro = re.search(
                rf'<form method="post" action="/recetas/preparacion/{preparacion.pk}/retirar/">'
                rf'.*?name="operacion_id" value="([^"]+)"',
                pendientes,
                re.S,
            ).group(1)
            mediciones["pendientes_retiro"].append(duracion)

            estado, _, cabeceras, duracion = farmacia.pedir(
                f"/recetas/preparacion/{preparacion.pk}/retirar/",
                {"operacion_id": operacion_retiro},
            )
            assert estado == 200 and "no-store" in cabeceras.get("Cache-Control", "")
            mediciones["retirar_preparado"].append(duracion)
            assert EntregaReceta.objects.filter(turno_receta=preparacion.turno_receta).exists()

        for _ in range(100):
            estado, datos, cabeceras, duracion = farmacia.pedir("/turnos/estado/")
            assert estado == 200 and "no-store" in cabeceras.get("Cache-Control", "")
            panel = json.loads(datos)["html"]
            assert "preparar" in panel.lower() and "Tiempo aproximado de espera:" in panel
            mediciones["panel_05"].append(duracion)

        assert Turno.objects.filter(fecha=hoy).count() == 100
        assert Turno.objects.filter(fecha=hoy, estado="ausente").count() == 100
        assert PreparacionReceta.objects.filter(turno_receta__turno__fecha=hoy, lista_en__isnull=False).count() == 100
        assert EntregaReceta.objects.count() == 100
        informe = {
            "resultado": "aprobado",
            "pacientes_sinteticos": 670,
            "turnos_emitidos_y_retirados": 100,
            "ventanillas_activas": 4,
            "recorrido": "emision y estimacion -> marcado como lista -> ausencia -> lista de pendientes -> retiro del preparado -> panel del 05",
            "mediciones_http": {nombre: resumen(valores) for nombre, valores in mediciones.items()},
            "limites": "Loopback HTTP con servidor WSGI en SQLite temporal; el minuto previo a marcar ausente se representa adelantando ultimo_llamado en los datos sintéticos. No mide navegador, red CESFAM, impresora, aceptación ni pruebas de usabilidad.",
        }
        print(json.dumps(informe, ensure_ascii=False, indent=2), flush=True)
        assert all(valor["p95_ms"] <= 2000 for valor in informe["mediciones_http"].values())
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)
        connections.close_all()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="cesfam-spec07-") as temporal:
        ejecutar(Path(temporal) / "qa.sqlite3")
    print("Servidor cerrado y SQLite temporal eliminada.", flush=True)
