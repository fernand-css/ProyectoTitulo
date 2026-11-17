"""Recorrido HTTP del mapa y el orden de visita (spec 09) y p95 por escenario, con datos sintéticos.

Crea una SQLite temporal; no usa ni migra la base PostgreSQL del proyecto. Padrón sintético de 670 pacientes
(600 mayores de 80 y 70 postrados), domicilios generados con `generar_domicilios_demo --aplicar` (coordenadas
aleatorias alrededor del origen, que no representan viviendas reales) más 10 domicilios sin coordenadas, y
4 encargados con 50 visitas cada uno programadas con el servicio del 08. Mide «Mis entregas», «Mapa», «Ir a esta
parada», «Rutas», mover y volver al orden sugerido, y aparte el cálculo del orden con 200 paradas.

Enmienda del 2026-11-15: levanta un OSRM simulado en 127.0.0.1 (puerto libre, sin registros) para el orden y el
total por camino, y mide además el tramo y la parada más cercana (POST JSON con la posición, que no se guarda).
Comprueba el respaldo en línea recta con OSRM caído y el límite de 30 solicitudes por minuto; después lo levanta
solo en este proceso aislado para medir. Con `--osrm-real` mide también, contra el OSRM local
(`OSRM_REAL_URL`, por defecto http://127.0.0.1:5000), la matriz de 52 y de 202 puntos y un tramo. Ejecutar con el
Python del venv:

    python tools/verificar_spec_09_http.py
    python tools/verificar_spec_09_http.py --osrm-real
"""
import http.cookiejar
import io
import json
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

PROYECTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROYECTO))
os.environ.update(
    DJANGO_SETTINGS_MODULE="cesfam.settings",
    SECRET_KEY=secrets.token_urlsafe(48),
    DB_NAME="qa09_sintetica",
    DEBUG="True",
    ALLOWED_HOSTS="127.0.0.1,localhost",
    PYTHONUNBUFFERED="1",
    PYTHONUTF8="1",
)

from django.conf import settings  # noqa: E402

MARCA = "QA09Privado"
VISITAS_POR_ENCARGADO = 50


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

    def token(self):
        return next((cookie.value for cookie in self.cookies if cookie.name == "csrftoken"), "")

    def pedir(self, ruta, datos=None):
        cabeceras = {"Referer": self.base + ruta, "Origin": self.base}
        cuerpo = None
        if datos is not None:
            cuerpo = urlencode({**datos, "csrfmiddlewaretoken": self.token()}, doseq=True).encode()
        inicio = time.perf_counter()
        try:
            respuesta = self.http.open(Request(self.base + ruta, data=cuerpo, headers=cabeceras), timeout=30)
        except HTTPError as error:
            respuesta = error
        with respuesta:
            contenido = respuesta.read()
            duracion = time.perf_counter() - inicio
            return respuesta.status, contenido.decode(), respuesta.headers, duracion

    def pedir_json(self, ruta, datos, aceptar_json=True):
        cabeceras = {"Referer": self.base + ruta, "Origin": self.base, "X-CSRFToken": self.token(),
                     "Content-Type": "application/json", "Accept": "application/json"}
        inicio = time.perf_counter()
        try:
            respuesta = self.http.open(Request(self.base + ruta, data=json.dumps(datos).encode(), headers=cabeceras), timeout=30)
        except HTTPError as error:
            respuesta = error
        with respuesta:
            contenido = respuesta.read()
            return respuesta.status, json.loads(contenido.decode()), respuesta.headers, time.perf_counter() - inicio

    def mover_json(self, datos):
        cabeceras = {"Referer": self.base + "/entregas/mis/", "Origin": self.base, "Accept": "application/json"}
        cuerpo = urlencode({**datos, "csrfmiddlewaretoken": self.token()}).encode()
        inicio = time.perf_counter()
        try:
            respuesta = self.http.open(Request(self.base + "/entregas/mis/orden/mover/", data=cuerpo, headers=cabeceras), timeout=30)
        except HTTPError as error:
            respuesta = error
        with respuesta:
            return respuesta.status, json.loads(respuesta.read().decode()), respuesta.headers, time.perf_counter() - inicio

    def entrar(self, nombre, clave):
        estado, _, _, _ = self.pedir("/usuarios/entrar/")
        assert estado == 200
        estado, _, _, _ = self.pedir("/usuarios/entrar/", {"username": nombre, "password": clave})
        assert estado == 200, f"No se pudo autenticar {nombre}"


def sin_cache(cabeceras):
    return "no-store" in cabeceras.get("Cache-Control", "")


def datos_json(html, ident):
    return json.loads(re.search(rf'<script id="{ident}" type="application/json">(.*?)</script>', html, re.S).group(1))


def controles(html, intento):
    """version y operacion_id del formulario de una parada en «Mis entregas»."""
    bloque = html[html.index(f'id="parada-{intento}"'):]
    version = re.search(r'name="version" value="(\d+)"', bloque).group(1)
    operacion = re.search(r'name="operacion_id" value="([^"]+)"', bloque).group(1)
    return version, operacion


def ejecutar(base_datos, osrm_simulado, osrm_real):
    settings.DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": str(base_datos)}
    import django
    django.setup()

    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.core.handlers.wsgi import WSGIHandler
    from django.core.management import call_command
    from django.db import connections
    from django.utils import timezone
    from coreapp.models import RegistroAuditoria
    from coreapp.roles import ENCARGADO, JEFA, TECNICO
    from coreapp.utils.sinteticos import generar_ruts
    from django.core.cache import cache
    from entregasapp import osrm, views
    from entregasapp.consultas import ruta_del_dia
    from entregasapp.models import Domicilio, IntentoEntrega, OrdenRuta
    from entregasapp.ruta import Punto, ordenar
    from entregasapp.services import guardar_domicilio, programar_entrega
    from recetasapp.models import Paciente, Receta
    from usuariosapp.models import Perfil

    call_command("migrate", verbosity=0, interactive=False)
    hoy = timezone.localdate()
    ruts = generar_ruts(670, Random(909))
    pacientes = Paciente.objects.bulk_create([
        Paciente(
            rut=rut, nombres=MARCA, apellidos=f"Sintetico {indice:03d}",
            fecha_nacimiento=date(hoy.year - 86, 6, 15) if indice < 600 else date(hoy.year - 56, 3, 1),
            es_cronico=True, es_postrado=indice >= 600, telefono="+56 9 0000 0000",
            direccion=f"Camino sintético {indice}, km {indice % 9 + 1}",
        )
        for indice, rut in enumerate(ruts)
    ])
    Receta.objects.bulk_create([
        Receta(paciente=paciente, codigo=f"QA09-{indice:03d}", fecha_inicio=hoy - timedelta(days=30),
               fecha_fin_exclusiva=hoy + timedelta(days=150), vigencia_meses=6, max_entregas=12)
        for indice, paciente in enumerate(pacientes)
    ])

    clave = secrets.token_urlsafe(24)

    def cuenta(nombre, rol):
        usuario = get_user_model().objects.create_user(username=nombre, password=clave, first_name="Persona", last_name="Sintética")
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
        return usuario

    qf = cuenta("qa09_qf", JEFA)
    cuenta("qa09_tecnico", TECNICO)
    encargados = [cuenta(f"qa09_encargado_{numero}", ENCARGADO) for numero in range(1, 5)]
    extenso = cuenta("qa09_encargado_200", ENCARGADO)
    del_limite = cuenta("qa09_encargado_limite", ENCARGADO)

    # Domicilios: 10 sin coordenadas registrados a mano y el resto con el comando de demostración.
    for paciente in pacientes[:10]:
        guardar_domicilio(qf, paciente.pk, {"sector": "azul", "localidad": "Localidad demo 1",
                                            "direccion": paciente.direccion, "referencias": "Sin coordenadas"})
    salida = io.StringIO()
    call_command("generar_domicilios_demo", stdout=salida)
    assert "Simulación: se crearían 660" in salida.getvalue() and Domicilio.objects.count() == 10
    call_command("generar_domicilios_demo", "--aplicar", "--cuenta", qf.username, "--semilla", "909", stdout=salida)
    assert Domicilio.objects.count() == 670
    assert Domicilio.objects.filter(latitud__isnull=False).count() == 660

    # 50 visitas para hoy por encargado (las 10 sin coordenadas repartidas) y 200 para el encargado extenso.
    for indice, paciente in enumerate(pacientes[:4 * VISITAS_POR_ENCARGADO]):
        programar_entrega(qf, paciente.pk, hoy, encargados[indice % 4].pk, uuid.uuid4())
    for paciente in pacientes[200:400]:
        programar_entrega(qf, paciente.pk, hoy + timedelta(days=1), extenso.pk, uuid.uuid4())
    # Unas próximas por encargado, para que «Mis entregas» tenga todas sus secciones.
    for indice, paciente in enumerate(pacientes[400:420]):
        programar_entrega(qf, paciente.pk, hoy + timedelta(days=2), encargados[indice % 4].pk, uuid.uuid4())
    programar_entrega(qf, pacientes[420].pk, hoy, del_limite.pk, uuid.uuid4())

    class Silencioso(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    class ServidorConcurrente(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    logging.getLogger("django.request").setLevel(logging.CRITICAL)
    servidor = make_server("127.0.0.1", 0, WSGIHandler(), server_class=ServidorConcurrente, handler_class=Silencioso)
    base = f"http://127.0.0.1:{servidor.server_port}"
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()

    farmacia = ClienteHTTP(base)
    farmacia.entrar("qa09_qf", clave)
    tecnico = ClienteHTTP(base)
    tecnico.entrar("qa09_tecnico", clave)
    terreno = []
    for usuario in encargados:
        cliente = ClienteHTTP(base)
        cliente.entrar(usuario.username, clave)
        terreno.append(cliente)
    limite = ClienteHTTP(base)
    limite.entrar(del_limite.username, clave)

    escenarios = ("mis_entregas", "mapa", "ir_a", "rutas_hoy", "rutas_futura_200", "mover", "restablecer", "mover_json",
                  "tramo", "parada_cercana")
    mediciones = {nombre: [] for nombre in escenarios}
    try:
        ruts_texto = [p.rut for p in pacientes]

        # 1. «Mis entregas» y «Mapa» de cada encargado: 50 visitas, 2-3 sin coordenadas, sin RUT en los datos.
        for indice in range(100):
            cliente = terreno[indice % 4]
            estado, html, cabeceras, duracion = cliente.pedir("/entregas/mis/")
            assert estado == 200 and sin_cache(cabeceras) and "Por visitar (50)" in html and "Parada 1" in html
            assert "Recorrido aprox. por camino:" in html and "data-compacta" in html and "Mover a la posición" not in html
            mediciones["mis_entregas"].append(duracion)
            estado, html, cabeceras, duracion = cliente.pedir("/entregas/mis/mapa/")
            assert estado == 200 and sin_cache(cabeceras)
            datos = datos_json(html, "datos-mapa")
            assert len(datos["paradas"]) + datos["sin_marcador"] == 50 and datos["sin_marcador"] >= 2
            assert "linea" not in datos and datos["distancia"] == "camino" and datos["total_km"]
            texto = json.dumps(datos, ensure_ascii=False)
            assert not any(rut in texto for rut in ruts_texto[:200]) and "+56 9" not in texto
            mediciones["mapa"].append(duracion)

        # 2. «Ir a esta parada» para paradas con coordenadas; la posición no viaja al servidor.
        rutas = {usuario.pk: ruta_del_dia(usuario) for usuario in encargados}
        for indice in range(100):
            usuario = encargados[indice % 4]
            parada = [p for p in rutas[usuario.pk].paradas if p.punto is not None][indice // 4]
            estado, html, cabeceras, duracion = terreno[indice % 4].pedir(f"/entregas/mis/ir/{parada.intento.pk}/")
            assert estado == 200 and sin_cache(cabeceras) and "Mostrar mi posición" in html and 'href="geo:' in html
            mediciones["ir_a"].append(duracion)

        # 3. «Rutas» de la Q.F.: hoy (igual a lo que ve el encargado) y mañana con 200 paradas.
        for indice in range(100):
            usuario = encargados[indice % 4]
            estado, html, cabeceras, duracion = farmacia.pedir(f"/entregas/rutas/?encargado={usuario.pk}&fecha={hoy.isoformat()}")
            assert estado == 200 and sin_cache(cabeceras)
            datos = datos_json(html, "datos-mapa")
            assert [p["intento"] for p in datos["paradas"]] == [p.intento.pk for p in rutas[usuario.pk].paradas if p.punto]
            assert "/entregas/mis/orden/mover/" not in html
            mediciones["rutas_hoy"].append(duracion)
        manana = (hoy + timedelta(days=1)).isoformat()
        for _ in range(20):
            estado, html, cabeceras, duracion = farmacia.pedir(f"/entregas/rutas/?encargado={extenso.pk}&fecha={manana}")
            assert estado == 200 and len(datos_json(html, "datos-mapa")["paradas"]) == 200
            mediciones["rutas_futura_200"].append(duracion)
        estado, html, _, _ = farmacia.pedir(f"/entregas/rutas/?encargado={encargados[0].pk}&fecha={(hoy - timedelta(days=1)).isoformat()}")
        assert estado == 400 and "Elige hoy o una fecha posterior" in html
        assert tecnico.pedir(f"/entregas/rutas/?encargado={encargados[0].pk}")[0] == 403

        # 3b. Tramo y parada más cercana (POST JSON con la posición, que no se guarda). Primero el límite de 30 por
        # minuto con una cuenta aparte; después se levanta solo en este proceso aislado para medir.
        intento_limite = ruta_del_dia(del_limite).paradas[0].intento.pk
        posicion = {"latitud": float(settings.REPARTO_ORIGEN_LATITUD) - 0.01, "longitud": float(settings.REPARTO_ORIGEN_LONGITUD) + 0.01}
        respuestas = [limite.pedir_json("/entregas/mis/tramo/", {"intento": intento_limite, **posicion})[0]
                      for _ in range(views.LIMITE_POSICION_POR_MINUTO + 1)]
        assert respuestas[:-1] == [200] * views.LIMITE_POSICION_POR_MINUTO and respuestas[-1] == 429, respuestas[-3:]
        views.LIMITE_POSICION_POR_MINUTO = 10 ** 6
        rutas = {usuario.pk: ruta_del_dia(usuario) for usuario in encargados}
        for indice in range(100):
            usuario, cliente = encargados[indice % 4], terreno[indice % 4]
            con_punto = [p for p in rutas[usuario.pk].paradas if p.punto is not None]
            parada = con_punto[indice // 4]
            estado, datos, cabeceras, duracion = cliente.pedir_json("/entregas/mis/tramo/", {"intento": parada.intento.pk, **posicion})
            assert estado == 200 and sin_cache(cabeceras) and datos["intento"] == parada.intento.pk and datos["geometria"]
            mediciones["tramo"].append(duracion)
            estado, datos, cabeceras, duracion = cliente.pedir_json("/entregas/mis/cercana/", posicion)
            assert estado == 200 and sin_cache(cabeceras) and datos["intento"] in {p.intento.pk for p in con_punto}
            mediciones["parada_cercana"].append(duracion)
        ajena = [p for p in rutas[encargados[1].pk].paradas if p.punto is not None][0].intento.pk
        assert terreno[0].pedir_json("/entregas/mis/tramo/", {"intento": ajena, **posicion})[0] == 404
        assert farmacia.pedir_json("/entregas/mis/tramo/", {"intento": ajena, **posicion})[0] == 403
        enviadas = [s for s in osrm_simulado.solicitudes if s.startswith("/route/")]
        assert enviadas and enviadas[-1].startswith(f"/route/v1/driving/{posicion['longitud']:.6f},{posicion['latitud']:.6f};")

        # 3c. OSRM caído: orden en línea recta rotulado y sin total; el tramo y la sugerencia responden 503 con texto.
        osrm_simulado.modo = "error500"
        cache.clear()
        estado, html, _, _ = terreno[0].pedir("/entregas/mis/")
        assert estado == 200 and "Orden aproximado en línea recta: el servidor de rutas no respondió." in html
        assert "Recorrido aprox. por camino" not in html
        assert terreno[0].pedir_json("/entregas/mis/tramo/", {"intento": rutas[encargados[0].pk].paradas[0].intento.pk, **posicion})[0] in (503, 404)
        assert terreno[0].pedir_json("/entregas/mis/cercana/", posicion)[0] == 503
        osrm_simulado.modo = ""
        cache.clear()

        # 4. Mover (subir, bajar, a una posición) y volver al orden sugerido, 100 veces cada uno.
        for indice in range(100):
            cliente, usuario = terreno[indice % 4], encargados[indice % 4]
            estado, html, _, _ = cliente.pedir("/entregas/mis/")
            ruta = ruta_del_dia(usuario)
            intento = ruta.paradas[(indice * 7) % len(ruta.paradas)].intento.pk
            version, operacion = controles(html, intento)
            destino = ("subir", "bajar", "1", "25")[indice % 4]
            if (destino == "subir" and ruta.paradas[0].intento.pk == intento) or (destino == "bajar" and ruta.paradas[-1].intento.pk == intento):
                destino = "10"
            estado, html, cabeceras, duracion = cliente.pedir("/entregas/mis/orden/mover/", {
                "intento": intento, "destino": destino, "version": version, "operacion_id": operacion})
            assert estado == 200 and "Orden guardado." in html and "Tu orden de hoy, guardado a las" in html, destino
            mediciones["mover"].append(duracion)
            if indice == 0:  # el mismo formulario reenviado no mueve otra vez
                antes = [p.intento.pk for p in ruta_del_dia(usuario).paradas]
                cliente.pedir("/entregas/mis/orden/mover/", {"intento": intento, "destino": destino, "version": version,
                                                             "operacion_id": operacion})
                assert [p.intento.pk for p in ruta_del_dia(usuario).paradas] == antes
            version_actual = re.search(r'name="version" value="(\d+)" id="id_version"', html).group(1)
            operacion_actual = re.search(r'name="operacion_id" value="([^"]+)" id="id_operacion_id"', html).group(1)
            estado, html, cabeceras, duracion = cliente.pedir("/entregas/mis/orden/sugerido/", {
                "version": version_actual, "operacion_id": operacion_actual})
            assert estado == 200 and "Volviste al orden sugerido." in html
            mediciones["restablecer"].append(duracion)
        assert OrdenRuta.objects.count() == 4
        # 25 movimientos y 25 vueltas por encargado; el primero crea la versión 1 y el reenvío no la sube.
        assert all(OrdenRuta.objects.get(encargado=u).version == 50 for u in encargados)

        # 4b. Flechas y arrastre con JavaScript: el mismo servicio responde el orden en JSON (20 movimientos).
        for indice in range(20):
            cliente, usuario = terreno[indice % 4], encargados[indice % 4]
            ruta = ruta_del_dia(usuario)
            intento = ruta.paradas[-1 - indice // 4].intento.pk
            estado, datos, cabeceras, duracion = cliente.mover_json({"intento": intento, "destino": "1", "version": ruta.version,
                                                                    "operacion_id": str(uuid.uuid4())})
            assert estado == 200 and sin_cache(cabeceras) and datos["ok"] and datos["orden"][0]["intento"] == intento
            mediciones["mover_json"].append(duracion)

        # 5. Cálculo del orden con 200 paradas: el algoritmo solo y la ruta completa desde la base.
        azar = Random(200)
        origen = Punto("origen", float(settings.REPARTO_ORIGEN_LATITUD), float(settings.REPARTO_ORIGEN_LONGITUD))
        algoritmo = []
        for _ in range(20):
            puntos = [Punto(clave, origen.latitud + azar.uniform(-0.13, 0.13), origen.longitud + azar.uniform(-0.17, 0.17))
                      for clave in range(200)]
            inicio = time.perf_counter()
            orden = ordenar(origen, origen, puntos)
            algoritmo.append(time.perf_counter() - inicio)
            assert not orden.limite_excedido and len(orden.paradas) == 200
        consulta = []
        for _ in range(10):
            inicio = time.perf_counter()
            ruta = ruta_del_dia(extenso, hoy + timedelta(days=1))
            consulta.append(time.perf_counter() - inicio)
            assert len(ruta.paradas) == 200 and not ruta.limite_2opt_excedido

        # 6. Con el OSRM local real (--osrm-real): matriz de 52 y 202 puntos y un tramo, sin caché.
        real = {}
        if osrm_real:
            settings.OSRM_URL = osrm_real
            settings.OSRM_TIEMPO_ESPERA = 2.0
            con_coordenadas = list(Domicilio.objects.filter(latitud__isnull=False).order_by("pk")[:200])
            puntos = [Punto(d.pk, float(d.latitud), float(d.longitud)) for d in con_coordenadas]
            for nombre, cantidad in (("matriz_52_puntos", 50), ("matriz_202_puntos", 200)):
                tiempos = []
                for _ in range(10):
                    inicio = time.perf_counter()
                    matriz = osrm.tabla([origen, *puntos[:cantidad], origen])
                    tiempos.append(time.perf_counter() - inicio)
                    assert len(matriz) == cantidad + 2
                real[nombre] = resumen(tiempos)
            tiempos = []
            for indice in range(10):
                inicio = time.perf_counter()
                tramo = osrm.tramo(Punto("posicion", posicion["latitud"], posicion["longitud"]), puntos[indice])
                tiempos.append(time.perf_counter() - inicio)
                assert tramo.distancia_m > 0 and tramo.geometria
            real["tramo"] = resumen(tiempos)

        texto_auditoria = " ".join(" ".join(r) for r in RegistroAuditoria.objects.values_list("accion", "objeto_tipo", "objeto_id"))
        assert "ruta.ordenada" in texto_auditoria and "ruta.restablecida" in texto_auditoria
        assert MARCA not in texto_auditoria and "demostración" not in texto_auditoria and "-36." not in texto_auditoria
        assert not IntentoEntrega.objects.exclude(resultado="pendiente").exists()  # ordenar no registra visitas
        informe = {
            "resultado": "aprobado",
            "pacientes_sinteticos": 670,
            "domicilios": {"con_coordenadas_generadas": 660, "sin_coordenadas": 10},
            "encargados": {"visitas_hoy_por_encargado": VISITAS_POR_ENCARGADO, "encargado_con_200_para_manana": 1},
            "recorrido": ("generar_domicilios_demo (simulación y --aplicar) -> 200 programaciones de hoy y 200 de mañana -> "
                          "mis entregas (tarjetas compactas, total por camino) y mapa (sin línea ni RUT) -> ir a esta "
                          "parada -> rutas de la Q.F. (hoy, mañana con 200 paradas, ayer rechazado, técnico 403) -> "
                          "límite de 30 tramos por minuto (429) -> 100 tramos y 100 paradas más cercanas (ajena 404, "
                          "Q.F. 403) -> OSRM caído (línea recta rotulada, 503) -> 100 movimientos (más un reenvío "
                          "idempotente), 100 vueltas al orden sugerido y 20 movimientos en JSON"),
            "osrm": "simulado en 127.0.0.1 (distancia = 1,3 × línea recta)" + (f"; real en {osrm_real}" if osrm_real else ""),
            "mediciones_http": {nombre: resumen(valores) for nombre, valores in mediciones.items()},
            "calculo_200_paradas": {"algoritmo_ordenar": resumen(algoritmo), "ruta_del_dia_desde_la_base": resumen(consulta)},
            "osrm_real": real or "no medido (usar --osrm-real con el contenedor local encendido)",
            "limites": ("Loopback HTTP con servidor WSGI en SQLite temporal y OSRM simulado. Mover y restablecer incluyen la "
                        "redirección y el dibujo de «Mis entregas». No mide redes móviles, navegador, carga de teselas, "
                        "ubicación real, arrastre en un celular, lector de pantalla, aceptación ni usabilidad."),
        }
        print(json.dumps(informe, ensure_ascii=False, indent=2), flush=True)
        assert all(valor["p95_ms"] <= 2000 for valor in informe["mediciones_http"].values())
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)
        connections.close_all()


if __name__ == "__main__":
    from entregasapp.tests.osrm_simulado import OsrmSimulado

    osrm_real = (os.environ.get("OSRM_REAL_URL") or "http://127.0.0.1:5000") if "--osrm-real" in sys.argv else ""
    with tempfile.TemporaryDirectory(prefix="cesfam-spec09-", ignore_cleanup_errors=True) as temporal, OsrmSimulado() as simulado:
        os.environ["ARCHIVOS_PRIVADOS_ROOT"] = str(Path(temporal) / "privado")
        os.environ["OSRM_URL"] = simulado.url
        os.environ["OSRM_TIEMPO_ESPERA"] = "1.0"
        ejecutar(Path(temporal) / "qa.sqlite3", simulado, osrm_real)
    print("Servidor cerrado; SQLite temporal eliminada.", flush=True)
