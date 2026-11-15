"""Spec 10 por HTTP real: término de turno, cambio de fila, urgencia y comprobante. Solo SQLite temporal."""
import http.cookiejar
import logging
import math
import os
import re
import secrets
import sys
import tempfile
import threading
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from random import Random
from socketserver import ThreadingMixIn
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(DJANGO_SETTINGS_MODULE="cesfam.settings", SECRET_KEY=secrets.token_urlsafe(48),
    DEBUG="True", ALLOWED_HOSTS="127.0.0.1,localhost")
from django.conf import settings


def ejecutar(base_datos):
    settings.DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": str(base_datos)}
    import django
    django.setup()
    import json
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.core.handlers.wsgi import WSGIHandler
    from django.core.management import call_command
    from django.db import connections
    from django.utils import timezone
    from coreapp.roles import JEFA, TECNICO
    from coreapp.utils.sinteticos import generar_ruts
    from recetasapp.models import Paciente, Receta
    from turnosapp.models import AnuncioSala, ContadorTurnosDiario, EventoTurno, Turno, Ventanilla
    from usuariosapp.models import Perfil

    call_command("migrate", verbosity=0, interactive=False)
    import turnosapp.services as servicios_turnos
    servicios_turnos.LIMITE_INTENTOS = 10 ** 6  # Muchos pacientes desde 127.0.0.1, solo en esta base aislada.
    call_command("preparar_ventanillas", verbosity=0)
    hoy = timezone.localdate()
    pacientes = Paciente.objects.bulk_create([Paciente(rut=rut, nombres="QA10Privado", apellidos="Sintético",
        fecha_nacimiento=date(1970, 1, 1)) for rut in generar_ruts(670, Random(1010))])
    Receta.objects.bulk_create([Receta(paciente=p, codigo=f"QA10-{i}", fecha_inicio=hoy,
        fecha_fin_exclusiva=hoy + timedelta(days=30), vigencia_meses=1, max_entregas=3) for i, p in enumerate(pacientes)])
    clave = secrets.token_urlsafe(24)
    for nombre, rol in [(f"qa10_tecnico_{i}", TECNICO) for i in range(4)] + [("qa10_qf", JEFA)]:
        usuario = get_user_model().objects.create_user(username=nombre, password=clave)
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])

    class Silencioso(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    class Concurrente(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    logging.getLogger("django.request").setLevel(logging.CRITICAL)
    servidor = make_server("127.0.0.1", 0, WSGIHandler(), server_class=Concurrente, handler_class=Silencioso)
    base = f"http://127.0.0.1:{servidor.server_port}"
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()

    class Cliente:
        def __init__(self):
            self.cookies = http.cookiejar.CookieJar()
            self.http = build_opener(HTTPCookieProcessor(self.cookies))

        def pedir(self, ruta, datos=None):
            cuerpo = None
            if datos is not None:
                datos = dict(datos, csrfmiddlewaretoken=next((c.value for c in self.cookies if c.name == "csrftoken"), ""))
                cuerpo = urlencode(datos, doseq=True).encode()
            inicio = time.perf_counter()
            try:
                respuesta = self.http.open(Request(base + ruta, data=cuerpo, headers={"Referer": base + ruta, "Origin": base}), timeout=30)
            except HTTPError as error:
                respuesta = error
            with respuesta:
                return respuesta.status, respuesta.read(), time.perf_counter() - inicio, respuesta.geturl()

        def entrar(self, usuario):
            self.pedir("/usuarios/entrar/")
            assert self.pedir("/usuarios/entrar/", {"username": usuario, "password": clave})[0] == 200

    def p95(valores):
        return round(sorted(valores)[math.ceil(.95 * len(valores)) - 1] * 1000, 2)

    medidas = {k: [] for k in ("urgencia", "reclasificar", "comprobante_pdf", "termino_turno")}
    try:
        tecnicos = []
        for i in range(4):
            cliente = Cliente()
            cliente.entrar(f"qa10_tecnico_{i}")
            for accion in ("ocupar", "iniciar"):
                assert cliente.pedir(f"/turnos/ventanillas/{i + 1}/{accion}/", {"operacion_id": str(uuid.uuid4())})[0] == 200
            tecnicos.append(cliente)
        qf = Cliente()
        qf.entrar("qa10_qf")
        totem = Cliente()
        for indice in range(80):
            _, html, _, _ = totem.pedir("/turnos/totem/")
            operacion = re.search(rb'name="operacion_id" value="([^"]+)"', html).group(1).decode()
            assert totem.pedir("/turnos/totem/", {"rut": pacientes[indice].rut, "operacion_id": operacion})[0] == 200
        # Pausar tres ventanillas deja la fila quieta para medir los cambios sobre turnos en espera.
        for i in (1, 2, 3):
            assert tecnicos[i].pedir(f"/turnos/ventanillas/{i + 1}/pausar/", {"operacion_id": str(uuid.uuid4())})[0] == 200
        assert tecnicos[0].pedir("/turnos/ventanillas/1/pausar/", {"operacion_id": str(uuid.uuid4())})[0] == 200
        # Pausar conserva la atención en curso: se cierran esos llamados para empezar con las ventanillas libres.
        for turno in Turno.objects.filter(estado="llamado").select_related("operador"):
            cliente = tecnicos[int(turno.operador.username.rsplit("_", 1)[1])]
            datos = {"operacion_id": str(uuid.uuid4()), "confirmar": "on",
                "recetas_entregadas": list(turno.recetas_vinculadas.values_list("receta_id", flat=True))}
            assert cliente.pedir(f"/turnos/{turno.pk}/finalizar/", datos)[0] == 200
        assert not Turno.objects.filter(estado="llamado").exists()
        esperando = list(Turno.objects.filter(estado="esperando").order_by("entrada_cola", "pk"))
        assert len(esperando) >= 60, len(esperando)
        for turno in esperando[:30]:
            estado, _, segundos, url = qf.pedir(f"/turnos/{turno.pk}/urgencia/", {"operacion_id": str(uuid.uuid4())})
            assert estado == 200 and url.endswith(f"/turnos/{turno.pk}/comprobante/"), (estado, url)
            medidas["urgencia"].append(segundos)
            estado, pdf, segundos, _ = qf.pedir(f"/turnos/{turno.pk}/comprobante/pdf/")
            assert estado == 200 and pdf.startswith(b"%PDF") and b"Reemplaza a tu n" in pdf and turno.rut.encode() not in pdf
            medidas["comprobante_pdf"].append(segundos)
        for turno in esperando[30:60]:
            turno.refresh_from_db()
            destino = "P" if turno.letra != "P" else "G"
            estado, _, segundos, url = tecnicos[0].pedir(f"/turnos/{turno.pk}/reclasificar/", {"operacion_id": str(uuid.uuid4()), "letra": destino})
            assert estado == 200 and url.endswith("/comprobante/"), (estado, url)
            medidas["reclasificar"].append(segundos)
        urgentes = sorted(Turno.objects.filter(letra="U").values_list("numero", flat=True))
        assert urgentes == list(range(1, 31)), urgentes
        assert ContadorTurnosDiario.objects.get(fecha=hoy, letra="U").ultimo_numero == 30
        assert not AnuncioSala.objects.filter(evento__accion__in=["urgencia", "reclasificado"]).exists()
        # Reanudar la ventanilla 1: la fila U va primero (RF-05-13).
        assert tecnicos[0].pedir("/turnos/ventanillas/1/iniciar/", {"operacion_id": str(uuid.uuid4())})[0] == 200
        for _ in range(100):
            llamado = Turno.objects.filter(ventanilla__numero=1, estado="llamado").first()
            if llamado and llamado.letra == "U":
                break
            time.sleep(.05)
        assert llamado and llamado.letra == "U", llamado
        # Término de turno de la Q.F. con paciente llamado: vuelve a la fila con su antigüedad.
        entrada = llamado.entrada_cola
        estado, html, segundos, _ = qf.pedir("/turnos/ventanillas/1/terminar/", {"operacion_id": str(uuid.uuid4())})
        assert estado == 400 and "Confirma el término de turno".encode() in html
        estado, _, segundos, url = qf.pedir("/turnos/ventanillas/1/terminar/", {"operacion_id": str(uuid.uuid4()), "confirmar": "on"})
        assert estado == 200 and url.endswith("/turnos/gestion/")
        medidas["termino_turno"].append(segundos)
        llamado.refresh_from_db()
        assert llamado.estado in ("esperando", "llamado") and llamado.entrada_cola == entrada
        assert not Ventanilla.objects.get(numero=1).habilitada
        assert EventoTurno.objects.filter(turno=llamado, accion="devuelto_a_cola").count() == 1
        for i in (1, 2, 3):
            estado, _, segundos, url = qf.pedir(f"/turnos/ventanillas/{i + 1}/terminar/", {"operacion_id": str(uuid.uuid4()), "confirmar": "on"})
            assert estado == 200
            medidas["termino_turno"].append(segundos)
        assert not Ventanilla.objects.filter(habilitada=True).exists()
        assert not Turno.objects.filter(estado="llamado").exists()
        informe = {"http": "aprobado", "pacientes_sinteticos": 670, "ventanillas": 4, "turnos_emitidos": 80,
            "urgencias": "30 urgencias con U-001 a U-030 consecutivos; la fila U se llamó primero al reanudar",
            "reclasificaciones": 30, "sala": "sin anuncios por reclasificación ni urgencia",
            "termino_turno": "4 ventanillas terminadas por la Q.F.; el llamado volvió a la fila con su entrada original",
            "mediciones": {k: {"muestras": len(v), "p95_ms": p95(v)} for k, v in medidas.items()},
            "limites": "WSGI en loopback y carga secuencial; sin navegador, visor de PDF real, axe ni usabilidad"}
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        assert all(m["p95_ms"] <= 2000 for m in informe["mediciones"].values())
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)
        connections.close_all()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="cesfam-spec10-") as temporal:
        ejecutar(Path(temporal) / "qa.sqlite3")
    print("Servidor cerrado y SQLite temporal eliminada.")
