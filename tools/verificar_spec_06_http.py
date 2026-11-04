"""ASGI real entre procesos y latencia de 100 llamados; solo SQLite y datos de QA.

Ejecutar con el Python del venv. No lee ni migra la base del proyecto.
La recepción usa websockets (dependencia opcional de esta herramienta), sin navegador ni voz real.
"""
import asyncio
import http.cookiejar
import io
import json
import math
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import suppress
from datetime import date, timedelta
from pathlib import Path
from random import Random
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

PROYECTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROYECTO))
os.environ.update(DJANGO_SETTINGS_MODULE="cesfam.settings", SECRET_KEY=secrets.token_urlsafe(48),
    DB_NAME="qa06_sintetica", DEBUG="True", ALLOWED_HOSTS="127.0.0.1,localhost", PYTHONUNBUFFERED="1", PYTHONUTF8="1")


def preparar_django(base):
    from django.conf import settings
    settings.DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": str(base)}
    import django
    django.setup()


def resumen(valores):
    ordenados = sorted(valores)
    return {"muestras": len(valores), "p50_ms": round(ordenados[math.ceil(.5 * len(valores)) - 1] * 1000, 2),
        "p95_ms": round(ordenados[math.ceil(.95 * len(valores)) - 1] * 1000, 2),
        "maximo_ms": round(max(valores) * 1000, 2)}


def sin_datos_privados(texto):
    assert "QA06Privado" not in texto
    assert all(clave not in texto for clave in ('"paciente"', '"rut"', '"tipo_atencion"', '"evento"', '"operacion"', '"recetas"'))


class ClienteHTTP:
    def __init__(self, base):
        self.base = base
        self.cookies = http.cookiejar.CookieJar()
        self.http = build_opener(HTTPCookieProcessor(self.cookies))

    def pedir(self, ruta, datos=None):
        cuerpo = None
        if datos is not None:
            cuerpo = urlencode({**datos, "csrfmiddlewaretoken": next(c.value for c in self.cookies if c.name == "csrftoken")}).encode()
        inicio = time.perf_counter()
        with self.http.open(Request(self.base + ruta, data=cuerpo, headers={"Referer": self.base + ruta}), timeout=10) as r:
            texto = r.read().decode()
            assert r.status == 200
            return texto, time.perf_counter() - inicio, r.headers


def semilla():
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.core.management import call_command
    from django.utils import timezone
    from coreapp.roles import TECNICO
    from coreapp.utils.sinteticos import generar_ruts
    from recetasapp.models import Paciente, Receta
    from turnosapp.models import OcupacionVentanilla, Turno, TurnoReceta, Ventanilla
    from usuariosapp.models import Perfil
    call_command("migrate", interactive=False, verbosity=0)
    call_command("preparar_ventanillas", stdout=io.StringIO())
    hoy = timezone.localdate()
    pacientes = Paciente.objects.bulk_create([Paciente(rut=rut, nombres="QA06Privado", apellidos="Sintético",
        fecha_nacimiento=date(1970, 1, 1)) for rut in generar_ruts(670, Random(606))])
    recetas = Receta.objects.bulk_create([Receta(paciente=p, codigo=f"QA06-PRIVADO-{i}", fecha_inicio=hoy,
        fecha_fin_exclusiva=hoy + timedelta(days=30), vigencia_meses=1, max_entregas=3) for i, p in enumerate(pacientes)])
    turnos = Turno.objects.bulk_create([Turno(paciente=p, fecha=hoy, numero=i + 1, tipo_atencion="general")
        for i, p in enumerate(pacientes)])
    TurnoReceta.objects.bulk_create([TurnoReceta(turno=t, receta=r) for t, r in zip(turnos, recetas)])
    clave = secrets.token_urlsafe(24)
    for numero in range(1, 5):
        usuario = get_user_model().objects.create_user(username=f"qa06_tecnico_{numero}", password=clave)
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=TECNICO)[0])
        ventanilla = Ventanilla.objects.get(numero=numero)
        ventanilla.operador, ventanilla.automatico, ventanilla.fecha_activacion = usuario, True, hoy
        ventanilla.save()
        OcupacionVentanilla.objects.create(ventanilla=ventanilla, tecnico=usuario)
    return clave


async def medir(base, clave):
    from websockets.asyncio.client import connect
    from django.db import connections, transaction
    from django.utils import timezone
    from turnosapp.atencion import finalizar_atencion
    from turnosapp.cola import procesar_pendiente
    from turnosapp.models import AnuncioSala, PendienteSeleccion, Turno
    from turnosapp.sala import registrar_anuncio

    confirmaciones, cierres = {}, []
    http = {"sala_html": [], "panel_05": []}

    class Pantalla:
        def __init__(self, canal):
            self.canal = canal
            self.mensajes = asyncio.Queue()
            self.ids, self.latencias = [], {}
            self.tarea = asyncio.create_task(self.leer())

        async def leer(self):
            async for payload in self.canal:
                recibido = time.perf_counter()
                self.mensajes.put_nowait((json.loads(payload), recibido))

        async def recibir(self, esperados):
            encontrados = set()
            while encontrados != esperados:
                datos, recibido = await asyncio.wait_for(self.mensajes.get(), timeout=10)
                sin_datos_privados(json.dumps(datos))
                if datos["tipo"] == "anuncio":
                    assert set(datos) == {"tipo", "id", "numero", "ventanilla", "accion", "instante"}
                    identidad = datos["id"]
                    assert identidad in esperados and identidad not in self.latencias, "Anuncio inesperado o duplicado"
                    assert datos["accion"] == "llamado"
                    self.ids.append(identidad)
                    self.latencias[identidad] = max(0, recibido - confirmaciones[identidad])
                    encontrados.add(identidad)

    clientes, sondeos, tarea_sondeo = [], [], None

    def registrar(evento, turno, ventanilla):
        anuncio = registrar_anuncio(evento, turno, ventanilla)
        transaction.on_commit(lambda pk=anuncio.pk: confirmaciones.__setitem__(pk, time.perf_counter()))
        return anuncio

    def avanzar(primero=False):
        antes = set(confirmaciones)
        try:
            if primero:
                pendiente = PendienteSeleccion.objects.create(fecha=timezone.localdate(), motivo="qa06_latencia")
                assert procesar_pendiente(pendiente.pk) == 4
            else:
                actuales = list(Turno.objects.filter(estado="llamado").select_related("operador").order_by("ventanilla__numero"))
                assert len(actuales) == 4
                for turno in actuales:
                    inicio = time.perf_counter()
                    finalizar_atencion(turno.operador, turno.pk, uuid.uuid4(),
                        recetas_entregadas=list(turno.recetas_vinculadas.values_list("receta_id", flat=True)))
                    cierres.append(time.perf_counter() - inicio)
            nuevos = set(confirmaciones) - antes
            assert len(nuevos) == 4, "La selección no confirmó cuatro anuncios"
            return nuevos
        finally:
            connections.close_all()

    async def sondear_panel():
        while True:
            for c in sondeos:
                _, segundos, _ = await asyncio.to_thread(c.pedir, "/turnos/estado/")
                http["panel_05"].append(segundos)
            await asyncio.sleep(1)

    def cantidades_finales():
        try:
            return AnuncioSala.objects.count(), PendienteSeleccion.objects.filter(estado="pendiente").count()
        finally:
            connections.close_all()

    try:
        # Cuatro paneles privados autenticados consultan mientras se confirman llamados.
        for numero in range(1, 5):
            c = ClienteHTTP(base)
            await asyncio.to_thread(c.pedir, "/usuarios/entrar/")
            await asyncio.to_thread(c.pedir, "/usuarios/entrar/", {"username": f"qa06_tecnico_{numero}", "password": clave})
            sondeos.append(c)
        for _ in range(2):
            canal = await connect(base.replace("http:", "ws:") + "/ws/sala/", origin=base, open_timeout=5)
            pantalla = Pantalla(canal)
            clientes.append((canal, pantalla))
            inicial, _ = await asyncio.wait_for(pantalla.mensajes.get(), timeout=5)
            assert inicial["tipo"] == "estado" and not inicial["recientes"]
            sin_datos_privados(json.dumps(inicial))
        tarea_sondeo = asyncio.create_task(sondear_panel())
        with patch("turnosapp.cola.registrar_anuncio", registrar):
            for lote in range(25):
                esperados = await asyncio.to_thread(avanzar, lote == 0)
                await asyncio.gather(*(p.recibir(esperados) for _, p in clientes))
                # Cuatro consultas por lote: 100 de la página de sala.
                for _ in range(4):
                    for nombre, ruta in (("sala_html", "/turnos/sala/"),):
                        c = ClienteHTTP(base)
                        texto, segundos, cabeceras = await asyncio.to_thread(c.pedir, ruta)
                        sin_datos_privados(texto)
                        assert "no-store" in cabeceras["Cache-Control"] and not cabeceras.get("Set-Cookie")
                        http[nombre].append(segundos)
        # Deja pasar otra lectura: no debe haber un duplicado posterior al último lote.
        await asyncio.sleep(0.6)
        for _, p in clientes:
            while not p.mensajes.empty():
                datos, _ = p.mensajes.get_nowait()
                assert datos["tipo"] != "anuncio", "Entrega repetida tras el último lote"
            assert len(p.ids) == 100 and p.ids == sorted(set(p.ids))
        cantidades = await asyncio.to_thread(cantidades_finales)
        assert cantidades == (100, 0)
        por_llamado = [max(p.latencias[pk] for _, p in clientes) for pk in confirmaciones]
        informe = {
            "resultado": "aprobado", "pacientes_sinteticos": 670, "turnos_iniciales": 670,
            "ventanillas": 4, "pantallas_websocket": 2, "llamados_confirmados": 100,
            "carga": "25 lotes de 4 pacientes; 96 cierres reales del 05 con entrega y selección siguiente; cuatro paneles privados sondean durante la medición",
            "latencia_confirmacion_recepcion": resumen(por_llamado),
            "por_pantalla": [resumen(list(p.latencias.values())) for _, p in clientes],
            "http": {nombre: resumen(valores) for nombre, valores in http.items()},
            "servicio_cierre_y_seleccion_05": resumen(cierres),
            "limites": "Reloj monotónico común, callback on_commit y receptor websockets en una máquina; servidor ASGI separado y loopback. No mide dibujo, navegador, voz, red del CESFAM ni aceptación.",
        }
        assert informe["latencia_confirmacion_recepcion"]["p95_ms"] <= 2000
        assert all(m["p95_ms"] <= 2000 for m in informe["http"].values())
        assert informe["servicio_cierre_y_seleccion_05"]["p95_ms"] <= 2000
        print(json.dumps(informe, ensure_ascii=False, indent=2), flush=True)
        return informe
    finally:
        if tarea_sondeo:
            tarea_sondeo.cancel()
            with suppress(asyncio.CancelledError):
                await tarea_sondeo
        for canal, pantalla in clientes:
            await canal.close()
            await pantalla.tarea
        await asyncio.to_thread(connections.close_all)


def ejecutar(base):
    preparar_django(base)
    clave = semilla()
    with socket.socket() as reserva:
        reserva.bind(("127.0.0.1", 0))
        puerto = reserva.getsockname()[1]
    base_http = f"http://127.0.0.1:{puerto}"
    from django.db import connections
    connections.close_all()
    with (base.parent / "servidor.log").open("w+", encoding="utf-8") as registro:
        servidor = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--servidor", str(base), str(puerto)],
            cwd=PROYECTO, stdout=registro, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            limite = time.monotonic() + 15
            while True:
                try:
                    with urlopen(base_http + "/turnos/sala/", timeout=1) as respuesta:
                        assert respuesta.status == 200
                    break
                except OSError:
                    if servidor.poll() is not None or time.monotonic() > limite:
                        raise RuntimeError("El servidor ASGI de QA no inició") from None
                    time.sleep(0.1)
            asyncio.run(medir(base_http, clave))
        finally:
            servidor.terminate()
            try: servidor.wait(timeout=10)
            except subprocess.TimeoutExpired:
                servidor.kill()
                servidor.wait(timeout=5)
            connections.close_all()
            registro.seek(0)
            sin_datos_privados(registro.read())


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--servidor":
        preparar_django(Path(sys.argv[2]))
        from django.core.management import call_command
        call_command("runserver", f"127.0.0.1:{int(sys.argv[3])}", use_reloader=False, verbosity=0)
    elif len(sys.argv) == 3 and sys.argv[1] == "--medir":
        ejecutar(Path(sys.argv[2]))
    else:
        # El dueño del temporal no inicializa Django: al salir el emisor se liberan
        # también los handles SQLite de los contextos/hilos de asyncio en Windows.
        with tempfile.TemporaryDirectory(prefix="cesfam-spec06-") as temporal:
            resultado = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--medir", str(Path(temporal) / "qa.sqlite3")],
                capture_output=True, text=True, encoding="utf-8", cwd=PROYECTO,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            sys.stdout.write(resultado.stdout)
            if resultado.returncode:
                sys.stderr.write(resultado.stderr)
            resultado.check_returncode()
        print("Servidor cerrado y SQLite temporal eliminada.", flush=True)
