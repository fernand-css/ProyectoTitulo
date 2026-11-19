"""Spec 11 por HTTP real: paquete de la ruta y sincronización de registros hechos sin conexión.

Solo SQLite temporal y datos sintéticos (670 pacientes, 3 encargados con 40 visitas cada uno). OSRM desactivado: la
ruta usa el respaldo en línea recta, como en el 09 cuando OSRM no responde. Mide:

- RNF-05: p95 del paquete (GET /entregas/mis/paquete/) y de los lotes de sincronización de un celular a la vez
  (≤ 2 s), con 670 pacientes y rutas de 40 visitas;
- NS05 / RNF-03: 100 registros guardados sin conexión en tres celulares que recuperan la señal a la vez (uno, además,
  desde dos «pestañas»), en lotes de hasta 50 con CSRF por cabecera; tiempo total ≤ 5 min y 0 duplicados (reenviar
  todo da `ya_aplicado`). El p95 de esos lotes simultáneos se informa aparte, sin exigirle los 2 s: SQLite (y, en
  PostgreSQL, la fila de la cola del día que toman los servicios del 08) atiende de a una escritura.

    python tools/verificar_spec_11_http.py
"""
import http.cookiejar
import json
import logging
import math
import os
import secrets
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
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
    DEBUG="True", ALLOWED_HOSTS="127.0.0.1,localhost", OSRM_URL="", REPARTO_AVISOS_AUTOMATICOS="no")
from django.conf import settings

VISITAS_POR_ENCARGADO = 40
REGISTROS = 100
LOTE = 50


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
    from coreapp.roles import ENCARGADO, JEFA
    from coreapp.utils.sinteticos import generar_ruts
    from entregasapp.models import IntentoEntrega, RecetaEntrega
    from entregasapp.services import guardar_domicilio, programar_entrega
    from recetasapp.models import EntregaReceta, Paciente, Receta
    from usuariosapp.models import Perfil

    call_command("migrate", verbosity=0, interactive=False)
    hoy = timezone.localdate()
    azar = Random(1111)
    pacientes = Paciente.objects.bulk_create([
        Paciente(rut=rut, nombres="QA11Privado", apellidos=f"Sintético{indice}", telefono="+56 9 0000 0000",
                 fecha_nacimiento=date(1940, 1, 1) if indice < 300 else date(1975, 1, 1), direccion="Camino sintético")
        for indice, rut in enumerate(generar_ruts(670, Random(1111)))
    ])
    Receta.objects.bulk_create([
        Receta(paciente=p, codigo=f"QA11-{i}", fecha_inicio=hoy - timedelta(days=30), fecha_fin_exclusiva=hoy + timedelta(days=150),
               vigencia_meses=6, max_entregas=6)
        for i, p in enumerate(pacientes)
    ])
    clave = secrets.token_urlsafe(24)
    cuentas = {}
    for nombre, rol in (("qa11_qf", JEFA), *((f"qa11_enc_{letra}", ENCARGADO) for letra in "abcdef")):
        usuario = get_user_model().objects.create_user(username=nombre, password=clave)
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
        cuentas[nombre] = usuario
    encargados = [f"qa11_enc_{letra}" for letra in "abcdef"]
    simultaneos, de_a_uno = encargados[:3], encargados[3:]
    origen = (settings.REPARTO_ORIGEN_LATITUD, settings.REPARTO_ORIGEN_LONGITUD)
    visitas = {nombre: [] for nombre in encargados}
    for indice, persona in enumerate(pacientes[:VISITAS_POR_ENCARGADO * len(encargados)]):
        guardar_domicilio(cuentas["qa11_qf"], persona.pk, {
            "sector": "verde", "localidad": "Localidad demo", "direccion": f"Camino sintético km {indice}",
            "referencias": "Portón sintético",
            "latitud": f"{origen[0] + azar.uniform(-0.08, 0.08):.6f}", "longitud": f"{origen[1] + azar.uniform(-0.08, 0.08):.6f}",
        })
        nombre = encargados[indice % len(encargados)]
        entrega = programar_entrega(cuentas["qa11_qf"], persona.pk, hoy, cuentas[nombre].pk, uuid.uuid4())
        visitas[nombre].append(entrega.intentos.get().pk)

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

        def token(self):
            return next((c.value for c in self.cookies if c.name == "csrftoken"), "")

        def pedir(self, ruta, datos=None, json_cuerpo=None):
            cabeceras = {"Referer": base + ruta, "Origin": base}
            cuerpo = None
            if datos is not None:
                cuerpo = urlencode(dict(datos, csrfmiddlewaretoken=self.token())).encode()
            if json_cuerpo is not None:
                cuerpo = json.dumps(json_cuerpo).encode()
                cabeceras.update({"Content-Type": "application/json", "Accept": "application/json", "X-CSRFToken": self.token()})
            inicio = time.perf_counter()
            try:
                respuesta = self.http.open(Request(base + ruta, data=cuerpo, headers=cabeceras), timeout=60)
            except HTTPError as error:
                respuesta = error
            with respuesta:
                return respuesta.status, respuesta.read(), time.perf_counter() - inicio

        def entrar(self, usuario):
            self.pedir("/usuarios/entrar/")
            assert self.pedir("/usuarios/entrar/", {"username": usuario, "password": clave})[0] == 200

    def p95(valores):
        return round(sorted(valores)[math.ceil(.95 * len(valores)) - 1] * 1000, 2)

    medidas = {"paquete": [], "lote_un_celular_a_la_vez": [], "lote_reenvio": []}
    informativas = {"lote_simultaneo_ns05": []}
    try:
        clientes = {}
        for nombre in encargados:
            clientes[nombre] = Cliente()
            clientes[nombre].entrar(nombre)
            assert clientes[nombre].pedir("/entregas/mis/")[0] == 200  # «Mis entregas» deja la cookie CSRF
        # RF-11-02 y RNF-05: paquete de 40 visitas, sin RUT; 20 descargas por encargado.
        ruts = [p.rut.encode() for p in pacientes[:VISITAS_POR_ENCARGADO * len(encargados)]]
        for nombre in encargados:
            for _ in range(20):
                estado, cuerpo, segundos = clientes[nombre].pedir("/entregas/mis/paquete/")
                assert estado == 200
                medidas["paquete"].append(segundos)
            datos = json.loads(cuerpo)
            assert len(datos["paradas"]) == VISITAS_POR_ENCARGADO and datos["cuenta"] == cuentas[nombre].pk
            assert not any(rut in cuerpo for rut in ruts)
        qf = Cliente()
        qf.entrar("qa11_qf")
        assert qf.pedir("/entregas/mis/paquete/")[0] == 403

        # NS05: 100 registros hechos sin conexión (40 + 40 + 20), mitad entregada y mitad no entregada.
        ahora = timezone.now()
        colas = {}
        cantidades = {"qa11_enc_a": 40, "qa11_enc_b": 40, "qa11_enc_c": 20, "qa11_enc_d": 40, "qa11_enc_e": 40, "qa11_enc_f": 40}
        for nombre, cantidad in cantidades.items():
            colas[nombre] = [{
                "operacion_id": str(uuid.uuid4()), "intento": intento, "resultado": "entregada" if n % 2 == 0 else "no_entregada",
                "motivo": "" if n % 2 == 0 else "sin_receptor", "nota": "",
                "registrado_en": (ahora - timedelta(minutes=90 - n)).isoformat(), "cuenta": cuentas[nombre].pk,
            } for n, intento in enumerate(visitas[nombre][:cantidad])]
        assert sum(len(colas[nombre]) for nombre in simultaneos) == REGISTROS

        reintentos = []

        def enviar_cola(nombre, clave_medida):
            """Como sincronizar.js: lotes de hasta 50; lo que vuelve «reintentar» queda en la cola y se reenvía."""
            estados = []
            cola = list(colas[nombre])
            for vuelta in range(10):
                if not cola:
                    break
                if vuelta:
                    reintentos.append(len(cola))
                    time.sleep(0.2)
                quedan = []
                for inicio in range(0, len(cola), LOTE):
                    lote = cola[inicio:inicio + LOTE]
                    estado, cuerpo, segundos = clientes[nombre].pedir("/entregas/mis/sincronizar/", json_cuerpo={"registros": lote})
                    assert estado == 200, (estado, cuerpo[:200])
                    (informativas if clave_medida in informativas else medidas)[clave_medida].append(segundos)
                    for registro, resultado in zip(lote, json.loads(cuerpo)["resultados"]):
                        assert resultado["operacion_id"] == registro["operacion_id"]
                        if resultado["estado"] == "reintentar":
                            quedan.append(registro)
                        else:
                            estados.append(resultado["estado"])
                cola = quedan
            assert not cola, "quedaron registros sin respuesta definitiva"
            return estados

        # «Vuelve la señal»: los tres celulares envían a la vez; el encargado A, desde dos pestañas a la vez.
        inicio = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as pool:
            tareas = [pool.submit(enviar_cola, nombre, "lote_simultaneo_ns05") for nombre in simultaneos]
            tareas.append(pool.submit(enviar_cola, "qa11_enc_a", "lote_simultaneo_ns05"))
            estados = [t.result() for t in tareas]
        total_segundos = time.perf_counter() - inicio
        planos = [e for lista in estados for e in lista]
        assert planos.count("aplicado") == REGISTROS, planos.count("aplicado")
        assert set(planos) <= {"aplicado", "ya_aplicado"}, set(planos)
        # 0 duplicados: cada registro aplicado una vez; cada entregada descontó su receta una vez.
        aplicados = IntentoEntrega.objects.filter(sincronizado_en__isnull=False)
        assert aplicados.count() == REGISTROS
        entregadas = entregadas_ns05 = aplicados.filter(resultado="entregada").count()
        assert EntregaReceta.objects.count() == entregadas == REGISTROS // 2
        assert RecetaEntrega.objects.filter(resultado="descontada").count() == entregadas
        assert not Receta.objects.filter(entregas_completadas__gt=1).exists()
        # RNF-05: otros tres celulares recuperan la señal en momentos distintos (40 registros cada uno, un lote).
        for nombre in de_a_uno:
            assert set(enviar_cola(nombre, "lote_un_celular_a_la_vez")) == {"aplicado"}
        entregadas = IntentoEntrega.objects.filter(sincronizado_en__isnull=False, resultado="entregada").count()
        assert EntregaReceta.objects.count() == entregadas
        # Reenviar todo (como un celular que no recibió la respuesta) da ya_aplicado, sin cambios; 5 vueltas.
        for _ in range(5):
            for nombre in encargados:
                assert set(enviar_cola(nombre, "lote_reenvio")) == {"ya_aplicado"}
        assert EntregaReceta.objects.count() == entregadas
        informe = {
            "http": "aprobado", "pacientes_sinteticos": 670, "encargados": len(encargados), "visitas_por_encargado": VISITAS_POR_ENCARGADO,
            "registros_aplicados_en_total": IntentoEntrega.objects.filter(sincronizado_en__isnull=False).count(),
            "ns05": {"registros": REGISTROS, "segundos_hasta_sincronizar_todo": round(total_segundos, 3),
                     "limite_segundos": 300, "duplicados": 0, "entregadas_descontadas_una_vez": entregadas_ns05,
                     "vueltas_con_reintentar": len(reintentos), "registros_reenviados_por_reintentar": sum(reintentos)},
            "mediciones": {k: {"muestras": len(v), "p95_ms": p95(v)} for k, v in medidas.items()},
            "informativas_sin_limite": {k: {"muestras": len(v), "p95_ms": p95(v), "maximo_ms": round(max(v) * 1000, 2)}
                                        for k, v in informativas.items()},
            "limites": ("WSGI en loopback, SQLite, sin OSRM ni navegador: no mide Service Worker, IndexedDB, red móvil ni "
                        "celular real. Los lotes simultáneos del NS05 se informan sin exigirles 2 s"),
        }
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        assert total_segundos <= 300
        assert all(m["p95_ms"] <= 2000 for m in informe["mediciones"].values())
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)
        connections.close_all()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="cesfam-spec11-") as temporal:
        ejecutar(Path(temporal) / "qa.sqlite3")
    print("Servidor cerrado y SQLite temporal eliminada.")
