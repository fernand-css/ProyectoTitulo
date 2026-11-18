"""Spec 13 por HTTP real: panel de mermas, reportes y derivación al reparto. Solo SQLite temporal y datos sintéticos."""
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
from datetime import date, datetime, timedelta
from datetime import time as hora
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

DIAS = 90
POR_DIA = 40
CIERRES = ("ausente", "sin_atencion_cierre", "atendido", "cerrado_sin_entrega")


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
    from coreapp.roles import DIRECTOR, ENCARGADO, JEFA
    from coreapp.utils.sinteticos import generar_ruts
    from entregasapp.models import Entrega
    from recetasapp.models import Paciente, PreparacionReceta, Receta
    from turnosapp.models import Turno, TurnoReceta
    from usuariosapp.models import Perfil

    call_command("migrate", verbosity=0, interactive=False)
    hoy = timezone.localdate()
    azar = Random(1313)
    pacientes = Paciente.objects.bulk_create([
        Paciente(rut=rut, nombres="QA13Privado", apellidos=f"Sintético{indice}", es_cronico=indice % 3 == 0,
                 fecha_nacimiento=date(1940, 1, 1) if indice % 3 == 0 else date(1975, 1, 1))
        for indice, rut in enumerate(generar_ruts(670, Random(1313)))
    ])
    recetas = Receta.objects.bulk_create([
        Receta(paciente=p, codigo=f"QA13-{i}", fecha_inicio=hoy - timedelta(days=DIAS + 5),
               fecha_fin_exclusiva=hoy + timedelta(days=60), vigencia_meses=6, max_entregas=12)
        for i, p in enumerate(pacientes)
    ])
    clave = secrets.token_urlsafe(24)
    cuentas = {}
    for nombre, rol in (("qa13_qf", JEFA), ("qa13_director", DIRECTOR), ("qa13_encargado", ENCARGADO)):
        usuario = get_user_model().objects.create_user(username=nombre, password=clave)
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
        cuentas[nombre] = usuario

    # 90 días de turnos cerrados con su receta preparada y sin retirar (40 por día).
    zona = timezone.get_current_timezone()
    for dias_atras in range(DIAS):
        fecha = hoy - timedelta(days=dias_atras)
        momento = timezone.make_aware(datetime.combine(fecha, hora(9)), zona)
        elegidos = azar.sample(range(len(pacientes)), POR_DIA)
        turnos = Turno.objects.bulk_create([
            Turno(paciente=pacientes[i], rut=pacientes[i].rut, fecha=fecha, letra="G", numero=n + 1,
                  tipo_atencion="general", estado=CIERRES[n % 4], entrada_cola=momento, cerrado_en=momento + timedelta(hours=1))
            for n, i in enumerate(elegidos)
        ])
        vinculos = TurnoReceta.objects.bulk_create([TurnoReceta(turno=t, receta=recetas[i]) for t, i in zip(turnos, elegidos)])
        PreparacionReceta.objects.bulk_create([
            PreparacionReceta(turno_receta=v, recibida_en=momento, lista_en=momento + timedelta(minutes=12),
                              lista_por=cuentas["qa13_qf"], inicio_medido=momento, duracion_segundos=720)
            for v in vinculos
        ])

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
                respuesta = self.http.open(Request(base + ruta, data=cuerpo, headers={"Referer": base + ruta, "Origin": base}), timeout=60)
            except HTTPError as error:
                respuesta = error
            with respuesta:
                return respuesta.status, respuesta.read(), time.perf_counter() - inicio, respuesta.geturl()

        def entrar(self, usuario):
            self.pedir("/usuarios/entrar/")
            assert self.pedir("/usuarios/entrar/", {"username": usuario, "password": clave})[0] == 200

    def p95(valores):
        return round(sorted(valores)[math.ceil(.95 * len(valores)) - 1] * 1000, 2)

    rangos = {
        "30_dias": "",
        "90_dias": f"?desde={hoy - timedelta(days=DIAS - 1):%Y-%m-%d}&hasta={hoy:%Y-%m-%d}",
        "366_dias": f"?desde={hoy - timedelta(days=365):%Y-%m-%d}&hasta={hoy:%Y-%m-%d}",
    }
    medidas = {}
    try:
        qf, director = Cliente(), Cliente()
        qf.entrar("qa13_qf")
        director.entrar("qa13_director")
        # Acceso del Director: su inicio es el panel; el resto de las secciones privadas responde 403.
        estado, html, _, _ = director.pedir("/")
        assert estado == 200 and "Detalle por paciente".encode() in html and "Derivar a domicilio".encode() not in html
        for ruta in ("/recetas/", "/turnos/panel/", "/entregas/", "/usuarios/gestion/"):
            assert director.pedir(ruta)[0] == 403, ruta
        ruts = [p.rut.encode() for p in pacientes]
        for nombre, consulta in rangos.items():
            for cliente, quien in ((qf, "qf"), (director, "director")):
                clave_panel = f"panel_{nombre}"
                for _ in range(10):
                    estado, html, segundos, _ = cliente.pedir("/indicadores/mermas/" + consulta)
                    assert estado == 200
                    medidas.setdefault(clave_panel, []).append(segundos)
                for formato in ("xlsx", "pdf"):
                    for _ in range(5):
                        estado, contenido, segundos, _ = cliente.pedir(f"/indicadores/mermas/reporte.{formato}" + consulta)
                        assert estado == 200 and len(contenido) > 1000, (formato, estado)
                        if formato == "pdf":
                            assert contenido.startswith(b"%PDF") and not any(rut in contenido for rut in ruts[:200]), quien
                        medidas.setdefault(f"reporte_{formato}_{nombre}", []).append(segundos)
        # Derivación por HTTP de 20 pacientes elegibles (80 años o más) con recetas sin retirar.
        elegibles = [p for p in pacientes if p.fecha_nacimiento.year == 1940][:20]
        derivados = 0
        for persona in elegibles:
            ruta = f"/indicadores/mermas/derivar/{persona.pk}/"
            estado, html, _, _ = qf.pedir(ruta)
            if "Programar entrega a domicilio".encode() not in html:
                continue
            datos = {"fecha": f"{hoy:%Y-%m-%d}", "encargado": cuentas["qa13_encargado"].pk, "operacion_id": str(uuid.uuid4())}
            estado, _, segundos, url = qf.pedir(ruta, datos)
            assert estado == 200 and "/entregas/" in url, (estado, url)
            medidas.setdefault("derivar", []).append(segundos)
            derivados += 1
        assert derivados >= 10, derivados
        assert Entrega.objects.filter(estado__in=Entrega.ABIERTAS).count() == derivados
        estado, html, _, _ = qf.pedir("/indicadores/mermas/" + rangos["90_dias"])
        assert estado == 200
        informe = {
            "http": "aprobado", "pacientes_sinteticos": 670, "preparaciones_sinteticas": DIAS * POR_DIA, "dias": DIAS,
            "director": "inicio con el panel, sin «Derivar a domicilio»; 403 en Recetas, Atención, Entregas y Usuarios",
            "reportes": "Excel y PDF válidos para la Q.F. y el Director; el PDF no contiene ninguno de 200 RUT sintéticos",
            "derivaciones": derivados,
            "mediciones": {k: {"muestras": len(v), "p95_ms": p95(v)} for k, v in medidas.items()},
            "limites": "WSGI en loopback, carga secuencial y SQLite; sin navegador, axe, visor de PDF real ni usabilidad",
        }
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        assert all(m["p95_ms"] <= 2000 for m in informe["mediciones"].values())
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)
        connections.close_all()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="cesfam-spec13-") as temporal:
        ejecutar(Path(temporal) / "qa.sqlite3")
    print("Servidor cerrado y SQLite temporal eliminada.")
