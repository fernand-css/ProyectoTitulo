"""Spec 13 por HTTP real: dashboard de mermas y entregas, descargas y derivación. Solo SQLite temporal y datos sintéticos.

Desde la enmienda del 2026-11-25 genera 366 días: turnos cerrados con su receta preparada (con hora de emisión
repartida en la jornada y causa de no entrega en los cierres con atención) y visitas a domicilio registradas, y
mide el panel en cada clase de período y las tres descargas (Excel, CSV y PDF) del mes y del año.
"""
import http.cookiejar
import logging
import math
import os
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

DIAS = 366
POR_DIA = 40
VISITAS_POR_DIA = 10
CIERRES = ("ausente", "sin_atencion_cierre", "atendido", "cerrado_sin_entrega")
CAUSAS = ("sin_stock", "no_la_pide", "no_vigente", "cambio_indicacion", "otro")
MOTIVOS_VISITA = ("sin_receptor", "domicilio_no_encontrado", "camino_intransitable", "rechazo", "paciente_ausente")


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
    from django.db.models import F
    from django.utils import timezone
    from coreapp.roles import DIRECTOR, ENCARGADO, JEFA
    from coreapp.utils.sinteticos import generar_ruts
    from entregasapp.models import Entrega, IntentoEntrega, RecetaEntrega
    from recetasapp.models import Paciente, PreparacionReceta, Receta
    from turnosapp.models import CierreAtencion, DetalleCierre, OperacionAtencion, Turno, TurnoReceta
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
    qf_cuenta, encargado = cuentas["qa13_qf"], cuentas["qa13_encargado"]

    # 366 días de turnos cerrados con su receta preparada y sin retirar (40 por día), emitidos entre las 8 y las 19 h.
    zona = timezone.get_current_timezone()
    for dias_atras in range(DIAS):
        fecha = hoy - timedelta(days=dias_atras)
        inicio_dia = timezone.make_aware(datetime.combine(fecha, hora(8)), zona)
        elegidos = azar.sample(range(len(pacientes)), POR_DIA)
        turnos = Turno.objects.bulk_create([
            Turno(paciente=pacientes[i], rut=pacientes[i].rut, fecha=fecha, letra="G", numero=n + 1,
                  tipo_atencion="general", estado=CIERRES[n % 4],
                  entrada_cola=inicio_dia + timedelta(hours=n % 12, minutes=(7 * n) % 60),
                  cerrado_en=inicio_dia + timedelta(hours=n % 12 + 1))
            for n, i in enumerate(elegidos)
        ])
        vinculos = TurnoReceta.objects.bulk_create([TurnoReceta(turno=t, receta=recetas[i]) for t, i in zip(turnos, elegidos)])
        PreparacionReceta.objects.bulk_create([
            PreparacionReceta(turno_receta=v, recibida_en=t.entrada_cola, lista_en=t.entrada_cola + timedelta(minutes=12),
                              lista_por=qf_cuenta, inicio_medido=t.entrada_cola, duracion_segundos=720)
            for t, v in zip(turnos, vinculos)
        ])
        con_atencion = [(t, v) for t, v in zip(turnos, vinculos) if t.estado in ("atendido", "cerrado_sin_entrega")]
        operaciones = OperacionAtencion.objects.bulk_create([
            OperacionAtencion(actor=qf_cuenta, tipo="finalizar", turno=t, huella="q" * 64, resultado={})
            for t, _ in con_atencion
        ])
        cierres = CierreAtencion.objects.bulk_create([
            CierreAtencion(turno=t, actor=qf_cuenta, operacion=o, instante=t.cerrado_en, resultado="sin_entrega",
                           causa=CAUSAS[n % 5], motivo="Causa sintética")
            for n, ((t, _), o) in enumerate(zip(con_atencion, operaciones))
        ])
        DetalleCierre.objects.bulk_create([
            DetalleCierre(cierre=c, turno_receta=v, entregada=False, causa=c.causa, motivo="Causa sintética")
            for c, (_, v) in zip(cierres, con_atencion)
        ])
        # Visitas a domicilio registradas ese día: 7 entregadas al primer intento y 3 tras una visita fallida.
        visitados = azar.sample(range(len(pacientes)), VISITAS_POR_DIA)
        registro = inicio_dia + timedelta(hours=3)
        entregas = Entrega.objects.bulk_create([
            Entrega(paciente=pacientes[i], estado="entregada", operacion_id=uuid.uuid4(), cerrada_en=registro)
            for i in visitados
        ])
        RecetaEntrega.objects.bulk_create([
            RecetaEntrega(entrega=e, receta=recetas[i], resultado="no_descontada", causa="Causa sintética")
            for e, i in zip(entregas, visitados)
        ])
        intentos = []
        for n, entrega in enumerate(entregas):
            if n % 10 < 3:
                intentos.append(IntentoEntrega(entrega=entrega, numero=1, fecha_programada=fecha, encargado=encargado,
                                               resultado="no_entregada", motivo=MOTIVOS_VISITA[n % 5],
                                               registrado_en=registro, registrado_por=encargado, operacion_id=uuid.uuid4()))
            intentos.append(IntentoEntrega(entrega=entrega, numero=2 if n % 10 < 3 else 1, fecha_programada=fecha,
                                           encargado=encargado, resultado="entregada",
                                           registrado_en=registro + timedelta(hours=1), registrado_por=encargado,
                                           operacion_id=uuid.uuid4()))
        IntentoEntrega.objects.bulk_create(intentos)
    # `creado_en` es la hora de emisión (auto_now_add): se iguala a la llegada a la cola, repartida en la jornada.
    Turno.objects.update(creado_en=F("entrada_cola"))

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

    periodos = {
        "1_dia": "?periodo=1d", "7_dias": "?periodo=7d", "mes": "?periodo=mes", "semestre": "?periodo=semestre",
        "anio": "?periodo=anio",
        "366_dias": f"?periodo=personalizado&desde={hoy - timedelta(days=365):%Y-%m-%d}&hasta={hoy:%Y-%m-%d}",
    }
    medidas = {}
    try:
        qf, director = Cliente(), Cliente()
        qf.entrar("qa13_qf")
        director.entrar("qa13_director")
        ruts = [p.rut.encode() for p in pacientes]
        # Acceso del Director: su inicio es el dashboard, sin datos personales ni derivación; el resto responde 403.
        estado, html, _, _ = director.pedir("/")
        assert estado == 200 and "Mermas y entregas".encode() in html and "Derivar a domicilio".encode() not in html
        assert not any(rut in html for rut in ruts)
        for ruta in ("/recetas/", "/recetas/preparacion/pendientes/", "/turnos/panel/", "/entregas/", "/usuarios/gestion/"):
            assert director.pedir(ruta)[0] == 403, ruta
        for nombre, consulta in periodos.items():
            for cliente in (qf, director):
                for _ in range(10):
                    estado, html, segundos, _ = cliente.pedir("/indicadores/mermas/" + consulta)
                    assert estado == 200 and not any(rut in html for rut in ruts[:200]), nombre
                    medidas.setdefault(f"panel_{nombre}", []).append(segundos)
        for nombre in ("mes", "anio"):
            for cliente, quien in ((qf, "qf"), (director, "director")):
                for formato in ("xlsx", "csv", "pdf"):
                    for _ in range(5):
                        estado, contenido, segundos, _ = cliente.pedir(f"/indicadores/mermas/reporte.{formato}" + periodos[nombre])
                        assert estado == 200 and len(contenido) > 500, (formato, estado)
                        assert not any(rut in contenido for rut in ruts[:200]), (formato, quien)
                        if formato == "pdf":
                            assert contenido.startswith(b"%PDF")
                        if formato == "csv":
                            assert contenido.startswith("﻿".encode("utf-8"))
                        medidas.setdefault(f"reporte_{formato}_{nombre}", []).append(segundos)
        # Derivación por HTTP desde «Pendientes de retiro» de 20 pacientes de 80 años o más con recetas sin retirar.
        estado, html, _, _ = qf.pedir("/recetas/preparacion/pendientes/")
        assert estado == 200 and "Derivar a domicilio".encode() in html
        elegibles = [p for p in pacientes if p.fecha_nacimiento.year == 1940]
        abiertas_antes = Entrega.objects.filter(estado__in=Entrega.ABIERTAS).count()
        derivados = 0
        for persona in elegibles:
            if derivados >= 20:
                break
            ruta = f"/indicadores/mermas/derivar/{persona.pk}/"
            estado, html, _, _ = qf.pedir(ruta)
            if "Programar entrega a domicilio".encode() not in html:
                continue
            assert "/recetas/preparacion/pendientes/".encode() in html  # «Volver» a Pendientes de retiro
            datos = {"fecha": f"{hoy:%Y-%m-%d}", "encargado": encargado.pk, "operacion_id": str(uuid.uuid4())}
            estado, _, segundos, url = qf.pedir(ruta, datos)
            assert estado == 200 and "/entregas/" in url, (estado, url)
            medidas.setdefault("derivar", []).append(segundos)
            derivados += 1
        assert derivados >= 10, derivados
        assert Entrega.objects.filter(estado__in=Entrega.ABIERTAS).count() - abiertas_antes == derivados
        informe = {
            "http": "aprobado", "pacientes_sinteticos": 670, "dias": DIAS,
            "preparaciones_sinteticas": DIAS * POR_DIA, "visitas_sinteticas": int(DIAS * VISITAS_POR_DIA * 1.3),
            "director": "inicio con el dashboard, sin RUT ni «Derivar a domicilio»; 403 en Recetas, Pendientes de retiro, Atención, Entregas y Usuarios",
            "descargas": "Excel, CSV (con BOM) y PDF del mes y del año para la Q.F. y el Director, sin ninguno de 200 RUT sintéticos",
            "derivaciones_desde_pendientes": derivados,
            "mediciones": {k: {"muestras": len(v), "p95_ms": p95(v)} for k, v in medidas.items()},
            "limites": "WSGI en loopback, carga secuencial y SQLite; sin navegador, axe, visor de PDF ni Excel reales ni usabilidad",
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
