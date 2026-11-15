"""HTTP real y recuperación entre procesos; usa exclusivamente SQLite temporal."""
import http.cookiejar
import json
import logging
import math
import os
import re
from pathlib import Path
from random import Random
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from socketserver import ThreadingMixIn
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request
from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(DJANGO_SETTINGS_MODULE="cesfam.settings", SECRET_KEY=secrets.token_urlsafe(48),
    DEBUG="True", ALLOWED_HOSTS="127.0.0.1,localhost")
from django.conf import settings


def ejecutar(base_datos, solo_procesar=False):
    settings.DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": str(base_datos)}
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.core.handlers.wsgi import WSGIHandler
    from django.core.management import call_command
    from django.db import connections
    from django.utils import timezone
    from coreapp.roles import TECNICO
    from coreapp.utils.sinteticos import generar_ruts
    from recetasapp.models import Paciente, Receta, EntregaReceta
    from turnosapp.atencion import MOTIVO_SIN_RECETAS
    from turnosapp.models import ContadorTurnosDiario, Turno, PendienteSeleccion, EventoTurno, CierreAtencion
    from usuariosapp.models import Perfil
    if solo_procesar:
        call_command("procesar_cola", verbosity=0)
        connections.close_all()
        return
    call_command("migrate", verbosity=0, interactive=False)
    # Enmienda del spec 04 (RF-04-12): el tótem acepta 10 solicitudes por minuto y equipo. Esta herramienta
    # simula muchos pacientes desde 127.0.0.1, así que se levanta el límite solo en esta base aislada.
    import turnosapp.services as _servicios_turnos
    _servicios_turnos.LIMITE_INTENTOS = 10 ** 6
    call_command("preparar_ventanillas", verbosity=0)
    hoy = timezone.localdate()
    pacientes = Paciente.objects.bulk_create([Paciente(rut=rut, nombres="Paciente sintético", apellidos="QA",
        fecha_nacimiento=date(1970, 1, 1)) for rut in generar_ruts(670, Random(505))])
    Receta.objects.bulk_create([Receta(paciente=p, codigo=f"QA05-{i}", fecha_inicio=hoy,
        fecha_fin_exclusiva=hoy + timedelta(days=30), vigencia_meses=1, max_entregas=3) for i, p in enumerate(pacientes)])
    clave = secrets.token_urlsafe(24)
    for i in range(4):
        usuario = get_user_model().objects.create_user(username=f"qa05_{i}", password=clave)
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=TECNICO)[0])
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

        def pedir(self, ruta, datos=None, csrf=True):
            cuerpo = None
            if datos is not None:
                datos = dict(datos)
                if csrf:
                    datos["csrfmiddlewaretoken"] = next((c.value for c in self.cookies if c.name == "csrftoken"), "")
                cuerpo = urlencode(datos, doseq=True).encode()
            inicio = time.perf_counter()
            try:
                respuesta = self.http.open(Request(base + ruta, data=cuerpo, headers={"Referer": base + ruta, "Origin": base}), timeout=30)
            except HTTPError as error:
                respuesta = error
            with respuesta:
                return respuesta.status, respuesta.read().decode(), time.perf_counter() - inicio

        def emitir(self, indice):
            estado, html, _ = self.pedir("/turnos/totem/")
            assert estado == 200
            operacion = re.search(r'name="operacion_id" value="([^"]+)"', html).group(1)
            return self.pedir("/turnos/totem/", {"rut": pacientes[indice].rut, "operacion_id": operacion})

    medidas = {k: [] for k in ("emision", "estado", "cierre")}
    try:
        clientes = []
        for i in range(4):
            cliente = Cliente()
            cliente.pedir("/usuarios/entrar/")
            assert cliente.pedir("/usuarios/entrar/", {"username": f"qa05_{i}", "password": clave})[0] == 200
            for accion in ("ocupar", "iniciar"):
                assert cliente.pedir(f"/turnos/ventanillas/{i+1}/{accion}/", {"operacion_id": str(uuid.uuid4())})[0] == 200
            clientes.append(cliente)
        assert clientes[0].pedir("/turnos/ventanillas/1/pausar/", {}, csrf=False)[0] == 403
        totem = Cliente()
        for i in range(100):
            estado, _, duracion = totem.emitir(i)
            assert estado == 200
            medidas["emision"].append(duracion)
        for _ in range(100):
            estado, texto, duracion = clientes[0].pedir("/turnos/estado/")
            assert estado == 200 and "html" in json.loads(texto)
            medidas["estado"].append(duracion)
        for _ in range(100):
            turno = Turno.objects.filter(estado="llamado").select_related("operador").first()
            cliente = clientes[int(turno.operador.username.rsplit("_", 1)[1])]
            datos = {"operacion_id": str(uuid.uuid4()), "confirmar": "on",
                "recetas_entregadas": list(turno.recetas_vinculadas.values_list("receta_id", flat=True))}
            estado, _, duracion = cliente.pedir(f"/turnos/{turno.pk}/finalizar/", datos)
            assert estado == 200 and CierreAtencion.objects.filter(turno=turno).exists()
            medidas["cierre"].append(duracion)
        assert EntregaReceta.objects.count() == 100
        # Dos cargas HTTP concurrentes: mismo paciente y pacientes diferentes.
        for indices in ([101, 101, 101], [102, 103, 104]):
            with ThreadPoolExecutor(max_workers=3) as pool:
                assert list(pool.map(lambda indice: Cliente().emitir(indice)[0], indices)) == [200] * 3
        assert Turno.objects.count() == 104
        # Tercer escenario: dos reenvíos HTTP del mismo cierre desde sesiones separadas.
        turno = Turno.objects.filter(estado="llamado").select_related("operador").first()
        duplicados = []
        for _ in range(2):
            c = Cliente()
            c.pedir("/usuarios/entrar/")
            assert c.pedir("/usuarios/entrar/", {"username": turno.operador.username, "password": clave})[0] == 200
            duplicados.append(c)
        datos = {"operacion_id": str(uuid.uuid4()), "confirmar": "on",
            "recetas_entregadas": list(turno.recetas_vinculadas.values_list("receta_id", flat=True))}
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(lambda c: c.pedir(f"/turnos/{turno.pk}/finalizar/", datos)[0], duplicados)) == [200, 200]
        assert EntregaReceta.objects.count() == 101
        # Pendiente persistido sin callback, recuperado por un proceso Python nuevo.
        paciente = pacientes[105]
        nuevo = Turno.objects.create(paciente=paciente, rut=paciente.rut, fecha=hoy, letra="G", numero=105, tipo_atencion="general")
        pendiente = PendienteSeleccion.objects.create(fecha=hoy, motivo="qa_reinicio")
        connections.close_all()
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--procesar", str(base_datos)], check=True, timeout=30)
        pendiente.refresh_from_db()
        nuevo.refresh_from_db()
        assert pendiente.estado == "procesado" and nuevo.estado == "llamado"
        assert EventoTurno.objects.filter(turno=nuevo, accion="llamado").count() == 1
        assert EntregaReceta.objects.count() == 101
        # Enmienda RF-05-13 por HTTP: vaciar la cola cerrando lo llamado (el turno 105 no tiene recetas).
        for _ in range(30):
            turno = Turno.objects.filter(estado="llamado").select_related("operador").first()
            if turno is None:
                break
            cliente = clientes[int(turno.operador.username.rsplit("_", 1)[1])]
            datos = {"operacion_id": str(uuid.uuid4()), "confirmar": "on",
                "recetas_entregadas": list(turno.recetas_vinculadas.values_list("receta_id", flat=True))}
            assert cliente.pedir(f"/turnos/{turno.pk}/finalizar/", datos)[0] == 200
        assert not Turno.objects.filter(estado__in=["llamado", "esperando"]).exists()
        cierre_105 = CierreAtencion.objects.get(turno=nuevo)
        assert (cierre_105.resultado, cierre_105.motivo) == ("sin_entrega", MOTIVO_SIN_RECETAS)
        entregas_previas = EntregaReceta.objects.count()
        # Solo la ventanilla 1 sigue en automático para observar el orden.
        for i in (1, 2, 3):
            assert clientes[i].pedir(f"/turnos/ventanillas/{i+1}/pausar/", {"operacion_id": str(uuid.uuid4())})[0] == 200
        padron = set(Paciente.objects.values_list("rut", flat=True))
        fuera = [rut for rut in generar_ruts(20, Random(913)) if rut not in padron][:3]
        ahora = timezone.now()
        ContadorTurnosDiario.objects.update_or_create(fecha=hoy, letra="G", defaults={"ultimo_numero": 1000})
        viejo = Turno.objects.create(rut=fuera[0], fecha=hoy, letra="G", numero=900, tipo_atencion="general",
            entrada_cola=ahora - timedelta(minutes=20))
        urgente = Turno.objects.create(rut=fuera[1], fecha=hoy, letra="U", numero=1, tipo_atencion="urgencia",
            entrada_cola=ahora)
        # La emisión del tótem de un RUT fuera del padrón dispara la selección automática.
        estado, html, _ = totem.pedir("/turnos/totem/")
        operacion = re.search(r'name="operacion_id" value="([^"]+)"', html).group(1)
        assert totem.pedir("/turnos/totem/", {"rut": fuera[2], "operacion_id": operacion})[0] == 200
        emitido = Turno.objects.get(rut=fuera[2], fecha=hoy)
        assert emitido.paciente_id is None
        orden = []
        for _ in range(3):
            for _ in range(100):
                turno = Turno.objects.filter(estado="llamado").first()
                if turno:
                    break
                time.sleep(.05)
            orden.append(turno.pk)
            assert turno.ventanilla.numero == 1
            datos = {"operacion_id": str(uuid.uuid4()), "confirmar": "on"}
            estado, html, _ = clientes[0].pedir(f"/turnos/{turno.pk}/finalizar/", datos)
            assert estado == 200
            cierre = CierreAtencion.objects.get(turno=turno)
            assert (cierre.resultado, cierre.motivo) == ("sin_entrega", MOTIVO_SIN_RECETAS)
        assert orden == [urgente.pk, viejo.pk, emitido.pk], orden
        assert EntregaReceta.objects.count() == entregas_previas
        informe = {"http": "aprobado", "pacientes_sinteticos": 670, "ventanillas": 4,
            "escenarios_concurrentes": 3, "reinicio_procesador": "proceso nuevo recupera pendiente sin duplicados",
            "enmienda_rf_05_13": "U antes que el rescate de 15 min y el ciclo; cierres sin recetas con motivo fijo y sin entregas",
            "mediciones": {k: {"muestras": len(v), "p95_ms": round(sorted(v)[math.ceil(.95 * len(v))-1]*1000, 2)} for k, v in medidas.items()},
            "limites": "WSGI loopback y carga secuencial para p95; navegador/axe/usabilidad y aceptación pendientes"}
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        assert all(m["p95_ms"] <= 2000 for m in informe["mediciones"].values())
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)
        connections.close_all()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--procesar":
        ejecutar(Path(sys.argv[2]), solo_procesar=True)
    else:
        with tempfile.TemporaryDirectory(prefix="cesfam-spec05-") as temporal:
            ejecutar(Path(temporal) / "qa.sqlite3")
        print("Servidor cerrado y SQLite temporal eliminada.")
