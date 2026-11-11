"""Recorrido HTTP del reparto a domicilio (spec 08) y p95 por escenario, con datos sintéticos.

Crea una SQLite temporal y una carpeta privada temporal para las fotos; no usa ni migra la base PostgreSQL del
proyecto ni su carpeta `privado/`. Padrón sintético de 670 pacientes (600 mayores de 80 y 70 postrados) más
10 pacientes menores con excepción de reparto para comprobar el bloqueo del tótem. Las fotos se dibujan en
memoria con Pillow. Ejecutar con el Python del venv:

    python tools/verificar_spec_08_http.py
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
    DB_NAME="qa08_sintetica",
    DEBUG="True",
    ALLOWED_HOSTS="127.0.0.1,localhost",
    PYTHONUNBUFFERED="1",
    PYTHONUTF8="1",
)

from django.conf import settings  # noqa: E402

MARCA = "QA08Privado"


def resumen(valores):
    ordenados = sorted(valores)
    return {
        "muestras": len(valores),
        "p50_ms": round(ordenados[math.ceil(.5 * len(valores)) - 1] * 1000, 2),
        "p95_ms": round(ordenados[math.ceil(.95 * len(valores)) - 1] * 1000, 2),
        "maximo_ms": round(max(valores) * 1000, 2),
    }


def jpeg_sintetico(semilla):
    """Imagen generada (degradado y figuras), nunca una foto real; con EXIF GPS falso para probar su limpieza."""
    from PIL import Image, ImageDraw

    azar = Random(semilla)
    lienzo = Image.new("RGB", (1200, 900), (azar.randrange(256), azar.randrange(256), azar.randrange(256)))
    dibujo = ImageDraw.Draw(lienzo)
    for _ in range(12):
        x, y = azar.randrange(1100), azar.randrange(800)
        dibujo.rectangle((x, y, x + azar.randrange(20, 200), y + azar.randrange(20, 200)),
                         fill=(azar.randrange(256), azar.randrange(256), azar.randrange(256)))
    exif = Image.Exif()
    exif[0x8825] = {1: "S", 2: (36.0, 30.0, 0.0), 3: "W", 4: (72.0, 12.0, 0.0)}
    salida = io.BytesIO()
    lienzo.save(salida, format="JPEG", quality=90, exif=exif.tobytes())
    return salida.getvalue()


class ClienteHTTP:
    def __init__(self, base):
        self.base = base
        self.cookies = http.cookiejar.CookieJar()
        self.http = build_opener(HTTPCookieProcessor(self.cookies))

    def token(self):
        return next((cookie.value for cookie in self.cookies if cookie.name == "csrftoken"), "")

    def pedir(self, ruta, datos=None, archivos=None):
        cuerpo, cabeceras = None, {"Referer": self.base + ruta, "Origin": self.base}
        if archivos is not None:
            limite = f"----qa08{uuid.uuid4().hex}"
            partes = []
            for nombre, valor in {**(datos or {}), "csrfmiddlewaretoken": self.token()}.items():
                partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{nombre}"\r\n\r\n{valor}\r\n'.encode())
            for nombre, (archivo, contenido, tipo) in archivos.items():
                partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{nombre}"; filename="{archivo}"\r\n'
                              f'Content-Type: {tipo}\r\n\r\n'.encode() + contenido + b"\r\n")
            partes.append(f"--{limite}--\r\n".encode())
            cuerpo = b"".join(partes)
            cabeceras["Content-Type"] = f"multipart/form-data; boundary={limite}"
        elif datos is not None:
            cuerpo = urlencode({**datos, "csrfmiddlewaretoken": self.token()}, doseq=True).encode()
        inicio = time.perf_counter()
        try:
            respuesta = self.http.open(Request(self.base + ruta, data=cuerpo, headers=cabeceras), timeout=30)
        except HTTPError as error:
            respuesta = error
        with respuesta:
            contenido = respuesta.read()
            duracion = time.perf_counter() - inicio
            tipo = respuesta.headers.get("Content-Type", "")
            texto = contenido.decode() if tipo.startswith("text/") else contenido
            return respuesta.status, texto, respuesta.headers, duracion

    def entrar(self, nombre, clave):
        estado, _, _, _ = self.pedir("/usuarios/entrar/")
        assert estado == 200
        estado, _, _, _ = self.pedir("/usuarios/entrar/", {"username": nombre, "password": clave})
        assert estado == 200, f"No se pudo autenticar {nombre}"


def oculto(html, nombre, ident=None):
    patron = rf'<input type="hidden" name="{nombre}" value="([^"]+)"' + (rf'[^>]*id="{ident}"' if ident else "")
    return re.search(patron, html).group(1)


def sin_cache(cabeceras):
    return "no-store" in cabeceras.get("Cache-Control", "")


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
    from PIL import Image
    from coreapp.models import RegistroAuditoria
    from coreapp.roles import ENCARGADO, JEFA, TECNICO
    from coreapp.utils.sinteticos import generar_ruts
    from entregasapp.models import Domicilio, Entrega, FotoDomicilio, InscripcionReparto, IntentoEntrega, RecetaEntrega
    from recetasapp.models import EntregaReceta, Paciente, Receta
    from turnosapp.models import ContadorTurnosDiario, Turno
    from usuariosapp.models import Perfil

    call_command("migrate", verbosity=0, interactive=False)
    call_command("preparar_ventanillas", verbosity=0)
    hoy = timezone.localdate()
    ruts = generar_ruts(680, Random(808))
    pacientes = Paciente.objects.bulk_create([
        Paciente(
            rut=rut, nombres=MARCA, apellidos=f"Sintetico {indice:03d}",
            # 600 mayores de 80 (86 años) y 70 postrados de 56 años, como el padrón de demostración.
            fecha_nacimiento=date(hoy.year - 86, 6, 15) if indice < 600 else date(hoy.year - 56, 3, 1),
            es_cronico=True, es_postrado=indice >= 600, telefono="+56 9 0000 0000",
            direccion=f"Camino sintético {indice}, km {indice % 9 + 1}",
        )
        for indice, rut in enumerate(ruts[:670])
    ])
    excepciones = Paciente.objects.bulk_create([
        Paciente(rut=rut, nombres=MARCA, apellidos=f"Excepcion {indice:02d}", fecha_nacimiento=date(hoy.year - 62, 1, 10),
                 es_cronico=True, telefono="+56 9 0000 0000", direccion=f"Parcela sintética {indice}")
        for indice, rut in enumerate(ruts[670:])
    ])
    Receta.objects.bulk_create([
        Receta(paciente=paciente, codigo=f"QA08-{indice:03d}", fecha_inicio=hoy - timedelta(days=30),
               fecha_fin_exclusiva=hoy + timedelta(days=150), vigencia_meses=6, max_entregas=12)
        for indice, paciente in enumerate([*pacientes, *excepciones])
    ])

    clave = secrets.token_urlsafe(24)

    def cuenta(nombre, rol):
        usuario = get_user_model().objects.create_user(username=nombre, password=clave, first_name="Persona", last_name="Sintética")
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
        return usuario

    qf = cuenta("qa08_qf", JEFA)
    cuenta("qa08_tecnico", TECNICO)
    encargados = [cuenta(f"qa08_encargado_{numero}", ENCARGADO) for numero in range(1, 5)]
    for paciente in excepciones:
        InscripcionReparto.objects.create(paciente=paciente, motivo="sin_red_apoyo", creado_por=qf, modificado_por=qf)

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
    farmacia.entrar("qa08_qf", clave)
    tecnico = ClienteHTTP(base)
    tecnico.entrar("qa08_tecnico", clave)
    terreno = []
    for usuario in encargados:
        cliente = ClienteHTTP(base)
        cliente.entrar(usuario.username, clave)
        terreno.append(cliente)
    totem = ClienteHTTP(base)

    escenarios = (
        "domicilios_lista", "domicilios_busqueda", "domicilio_guardar", "domicilio_verificar", "foto_ver",
        "programar_revisar", "programar_confirmar", "mis_entregas", "registro_entregada", "registro_no_entregada",
        "reasignar", "programacion_filtros", "pendientes_filtros", "totem_despacho_abierto",
    )
    mediciones = {nombre: [] for nombre in escenarios}
    subida_fotos = []
    try:
        # 1. Domicilios: lista, búsqueda por RUT (POST), registro con coordenadas y verificación en terreno.
        for indice in range(100):
            encargado = terreno[indice % 4]
            estado, html, cabeceras, duracion = encargado.pedir("/entregas/domicilios/?estado=sin_registrar")
            assert estado == 200 and sin_cache(cabeceras)
            mediciones["domicilios_lista"].append(duracion)
            paciente = pacientes[indice * 6]
            estado, html, cabeceras, duracion = encargado.pedir("/entregas/domicilios/", {"buscar": paciente.rut})
            assert estado == 200 and paciente.apellidos in html and paciente.rut not in cabeceras.get("Location", "")
            mediciones["domicilios_busqueda"].append(duracion)
            ruta = f"/entregas/domicilios/paciente/{paciente.pk}/"
            estado, html, cabeceras, duracion = encargado.pedir(ruta, {
                "sector": ("verde", "azul", "rojo")[indice % 3], "localidad": "Dadinco", "direccion": paciente.direccion,
                "referencias": "Casa roja, portón verde", "latitud": f"-36.{500000 + indice}", "longitud": f"-72.{200000 + indice}",
                "precision_metros": "8"})
            assert estado == 200 and "Domicilio guardado." in html and sin_cache(cabeceras)
            mediciones["domicilio_guardar"].append(duracion)
            domicilio = Domicilio.objects.get(paciente=paciente)
            estado, html, _, duracion = encargado.pedir(f"/entregas/domicilios/{domicilio.pk}/verificar/", {"version": domicilio.version})
            assert estado == 200 and "Domicilio marcado como verificado." in html
            mediciones["domicilio_verificar"].append(duracion)
        assert Domicilio.objects.filter(verificado_en__isnull=False).count() == 100

        # 2. Fotos: subida medida aparte (sin compromiso de p95 para redes móviles) y vista privada.
        for indice in range(20):
            domicilio = Domicilio.objects.order_by("pk")[indice]
            estado, html, _, duracion = terreno[0].pedir(
                f"/entregas/domicilios/{domicilio.pk}/fotos/", {"descripcion": f"Portón y fachada {indice}"},
                archivos={"foto": (f"entorno-{indice}.jpg", jpeg_sintetico(indice), "image/jpeg")})
            assert estado == 200 and "Foto agregada" in html
            subida_fotos.append(duracion)
            foto = FotoDomicilio.objects.get(domicilio=domicilio)
            estado, contenido, cabeceras, duracion = terreno[1].pedir(f"/entregas/fotos/{foto.pk}/")
            assert estado == 200 and sin_cache(cabeceras) and cabeceras["Content-Type"] == "image/jpeg"
            with Image.open(io.BytesIO(contenido)) as imagen:
                assert len(imagen.getexif()) == 0 and max(imagen.size) <= 1600
            mediciones["foto_ver"].append(duracion)
        foto = FotoDomicilio.objects.first()
        anonimo = ClienteHTTP(base)
        estado, html, _, _ = anonimo.pedir(f"/entregas/fotos/{foto.pk}/")
        assert estado == 200 and 'name="password"' in html  # redirigido al inicio de sesión, sin la imagen
        estado, _, _, _ = farmacia.pedir(f"/media/{foto.archivo.name}")
        assert estado == 404

        # 3. Programación: revisar las recetas y confirmar, repartidas entre los cuatro encargados.
        programados = pacientes[:100]
        for indice, paciente in enumerate(programados):
            ruta = "/entregas/programar/"
            estado, html, _, _ = farmacia.pedir(f"{ruta}?paciente={paciente.pk}")
            operacion = oculto(html, "operacion_id")
            datos = {"paciente": paciente.pk, "fecha": hoy.isoformat(), "encargado": encargados[indice % 4].pk,
                     "operacion_id": operacion}
            estado, html, cabeceras, duracion = farmacia.pedir(ruta, {**datos, "accion": "revisar"})
            assert estado == 200 and f"Receta QA08-{indice:03d}" in html and sin_cache(cabeceras)
            mediciones["programar_revisar"].append(duracion)
            estado, html, _, duracion = farmacia.pedir(ruta, {**datos, "accion": "confirmar"})
            assert estado == 200 and "Entrega programada" in html
            mediciones["programar_confirmar"].append(duracion)
            if indice == 0:  # repetir el POST no crea otra entrega
                farmacia.pedir(ruta, {**datos, "accion": "confirmar"})
        assert Entrega.objects.filter(estado="programada").count() == 100
        assert IntentoEntrega.objects.count() == 100

        # 4. Bloqueo de doble vía en el tótem: excepciones con su receta en despacho no reciben número.
        for paciente in excepciones:
            estado, html, _, _ = farmacia.pedir(f"/entregas/programar/?paciente={paciente.pk}")
            datos = {"paciente": paciente.pk, "fecha": hoy.isoformat(), "encargado": encargados[0].pk,
                     "operacion_id": oculto(html, "operacion_id"), "accion": "confirmar"}
            assert farmacia.pedir("/entregas/programar/", datos)[0] == 200
        for indice in range(100):
            paciente = excepciones[indice % len(excepciones)]
            estado, formulario, _, _ = totem.pedir("/turnos/totem/")
            operacion = re.search(r'name="operacion_id" value="([^"]+)"', formulario).group(1)
            estado, html, cabeceras, duracion = totem.pedir("/turnos/totem/", {"rut": paciente.rut, "operacion_id": operacion})
            assert estado == 400 and "Tienes un despacho a domicilio programado." in html
            assert MARCA not in html and paciente.rut not in html and sin_cache(cabeceras)
            mediciones["totem_despacho_abierto"].append(duracion)
        assert not Turno.objects.exists()
        assert not ContadorTurnosDiario.objects.filter(ultimo_numero__gt=0).exists()

        # 5. «Mis entregas» de cada encargado.
        for indice in range(100):
            estado, html, cabeceras, duracion = terreno[indice % 4].pedir("/entregas/mis/")
            assert estado == 200 and sin_cache(cabeceras) and "Hoy (" in html and MARCA in html
            mediciones["mis_entregas"].append(duracion)

        # 6. Registro en terreno: 50 entregadas y 50 no entregadas.
        intentos = list(IntentoEntrega.objects.filter(entrega__paciente__in=programados).select_related("encargado").order_by("pk"))
        clientes = {usuario.pk: cliente for usuario, cliente in zip(encargados, terreno)}
        for indice, intento in enumerate(intentos):
            cliente = clientes[intento.encargado_id]
            estado, html, _, _ = cliente.pedir(f"/entregas/intentos/{intento.pk}/")
            if indice % 2 == 0:
                operacion = oculto(html, "operacion_id", "entregada_operacion_id")
                estado, html, cabeceras, duracion = cliente.pedir(
                    f"/entregas/intentos/{intento.pk}/entregada/", {"operacion_id": operacion, "confirmar": "on"})
                assert estado == 200 and "Entrega registrada." in html
                mediciones["registro_entregada"].append(duracion)
                if indice == 0:  # doble toque: el mismo identificador no descuenta otra vez
                    estado, html, _, _ = cliente.pedir(f"/entregas/intentos/{intento.pk}/entregada/",
                                                       {"operacion_id": operacion, "confirmar": "on"})
                    assert "ya estaba registrada" in html
            else:
                operacion = oculto(html, "operacion_id", "no_entregada_operacion_id")
                estado, html, cabeceras, duracion = cliente.pedir(
                    f"/entregas/intentos/{intento.pk}/no-entregada/",
                    {"operacion_id": operacion, "motivo": ("sin_receptor", "domicilio_no_encontrado")[indice % 4 == 1]})
                assert estado == 200 and "no entregada" in html
                mediciones["registro_no_entregada"].append(duracion)
        assert Entrega.objects.filter(estado="entregada").count() == 50
        assert Entrega.objects.filter(estado="pendiente_gestion").count() == 50
        assert EntregaReceta.objects.count() == 50 and RecetaEntrega.objects.filter(resultado="descontada").count() == 50
        assert all(r.entregas_completadas <= r.max_entregas for r in Receta.objects.all())

        # 7. Consultas con filtros de la Q.F. y del técnico.
        filtros = [
            "?sector=verde", "?motivo=sin_receptor", f"?encargado={encargados[1].pk}",
            f"?desde={hoy.isoformat()}&hasta={hoy.isoformat()}", "",
        ]
        for indice in range(100):
            cliente = farmacia if indice % 2 == 0 else tecnico
            estado, html, cabeceras, duracion = cliente.pedir("/entregas/pendientes/" + filtros[indice % 5])
            assert estado == 200 and sin_cache(cabeceras)
            mediciones["pendientes_filtros"].append(duracion)
            estado, html, cabeceras, duracion = cliente.pedir("/entregas/programacion/" + filtros[indice % 5].replace("motivo=sin_receptor", "sector=azul"))
            assert estado == 200 and sin_cache(cabeceras)
            mediciones["programacion_filtros"].append(duracion)

        # 8. Reasignación de las 50 no entregadas a mañana con otro encargado.
        manana = (hoy + timedelta(days=1)).isoformat()
        for indice, entrega in enumerate(list(Entrega.objects.filter(estado="pendiente_gestion").order_by("pk"))):
            estado, html, _, _ = farmacia.pedir(f"/entregas/{entrega.pk}/")
            datos = {"fecha": manana, "encargado": encargados[(indice + 1) % 4].pk,
                     "intento_id": oculto(html, "intento_id"), "resultado_visto": oculto(html, "resultado_visto"),
                     "operacion_id": oculto(html, "operacion_id")}
            estado, html, cabeceras, duracion = farmacia.pedir(f"/entregas/{entrega.pk}/reasignar/", datos)
            assert estado == 200 and "Entrega reasignada" in html
            mediciones["reasignar"].append(duracion)
        assert Entrega.objects.filter(estado="pendiente_gestion").count() == 0
        assert IntentoEntrega.objects.filter(entrega__paciente__in=programados).count() == 150

        texto_auditoria = " ".join(RegistroAuditoria.objects.values_list("objeto_id", flat=True))
        assert MARCA not in texto_auditoria and "Dadinco" not in texto_auditoria
        informe = {
            "resultado": "aprobado",
            "pacientes_sinteticos": 670,
            "excepciones_sinteticas": len(excepciones),
            "encargados": 4,
            "recorrido": ("domicilios (lista, búsqueda, registro con coordenadas, verificación) -> fotos generadas -> "
                          "100 programaciones -> tótem con despacho abierto -> mis entregas -> 50 entregadas y 50 no "
                          "entregadas -> consultas con filtros -> 50 reasignaciones"),
            "mediciones_http": {nombre: resumen(valores) for nombre, valores in mediciones.items()},
            "subida_de_fotos_aparte": resumen(subida_fotos),
            "limites": ("Loopback HTTP con servidor WSGI en SQLite temporal. No mide redes móviles, navegador, "
                        "ubicación real, cámara, aceptación ni usabilidad. La subida de fotos se informa sin "
                        "compromiso de p95."),
        }
        print(json.dumps(informe, ensure_ascii=False, indent=2), flush=True)
        assert all(valor["p95_ms"] <= 2000 for valor in informe["mediciones_http"].values())
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)
        connections.close_all()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="cesfam-spec08-", ignore_cleanup_errors=True) as temporal:
        os.environ["ARCHIVOS_PRIVADOS_ROOT"] = str(Path(temporal) / "privado")
        ejecutar(Path(temporal) / "qa.sqlite3")
    print("Servidor cerrado; SQLite y carpeta privada temporales eliminadas.", flush=True)
