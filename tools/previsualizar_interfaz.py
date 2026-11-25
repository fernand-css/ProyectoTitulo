"""Sirve la interfaz en localhost con SQLite temporal y datos exclusivamente sintéticos.

Uso: venv/Scripts/python tools/previsualizar_interfaz.py [--port 8765]
Ctrl+C cierra el servidor y elimina su base. Nunca conecta a PostgreSQL.
"""

import argparse
import os
import secrets
import sys
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path
from random import Random

PROYECTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROYECTO))


def main():
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--port", type=int, default=8765)
    argumentos = opciones.parse_args()
    os.environ.update(
        DJANGO_SETTINGS_MODULE="cesfam.settings",
        SECRET_KEY=secrets.token_urlsafe(48),
        DB_NAME="revision_visual_sintetica",
        DEBUG="True",
        ALLOWED_HOSTS="127.0.0.1,localhost,testserver",
    )
    from django.conf import settings

    with tempfile.TemporaryDirectory(prefix="cesfam-interfaz-") as temporal:
        settings.DATABASES["default"] = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(Path(temporal) / "revision.sqlite3"),
            "OPTIONS": {"timeout": 20},
        }
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        import django

        django.setup()
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
        from django.core.management import call_command
        from django.db import connections
        from django.utils import timezone
        from daphne.server import Server
        from cesfam.asgi import application
        from coreapp.roles import DIRECTOR, JEFA, TECNICO, ENCARGADO
        from coreapp.utils.sinteticos import generar_ruts
        from recetasapp.models import Paciente, Receta, EntregaReceta, PreparacionReceta
        from recetasapp.services import calcular_fin, marcar_lista
        from turnosapp.atencion import ocupar_ventanilla, iniciar_automatico
        from turnosapp.cola import procesar_pendientes
        from turnosapp.services import emitir_turno
        from usuariosapp.models import Perfil

        call_command("migrate", verbosity=0, interactive=False)
        call_command("preparar_ventanillas", verbosity=0)
        clave = secrets.token_urlsafe(18) + "9!"
        usuarios = {}
        for nombre, rol in (("qf", JEFA), ("tecnico", TECNICO), ("terreno", ENCARGADO), ("director", DIRECTOR)):
            usuario = get_user_model().objects.create_user(
                username="revision_" + nombre,
                first_name={"qf": "Equipo", "tecnico": "Personal", "terreno": "Terreno", "director": "Dirección"}[nombre],
                last_name="de prueba",
                email=nombre + "@example.invalid",
                password=clave,
            )
            Perfil.objects.create(usuario=usuario, correo_verificado_en=timezone.now())
            usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
            usuarios[nombre] = usuario
        get_user_model().objects.create_superuser(
            username="revision_admin", password=clave, email="admin@example.invalid",
            first_name="Administración", last_name="de prueba",
        )
        hoy = timezone.localdate()
        for indice, rut in enumerate(generar_ruts(48, Random(814))):
            paciente = Paciente.objects.create(
                rut=rut, nombres="Paciente de prueba", apellidos=f"Simulado {indice + 1:02d}",
                fecha_nacimiento=date(1955 + indice % 40, 5, 12),
                es_cronico=indice % 3 == 0, es_postrado=indice == 47,
            )
            inicio = hoy - timedelta(days=(indice % 6) * 30)
            receta = Receta.objects.create(
                paciente=paciente, codigo=f"DEMO-{indice + 1:04d}", fecha_inicio=inicio,
                fecha_fin_exclusiva=calcular_fin(inicio, 6), vigencia_meses=6,
                max_entregas=6,
            )
            cantidad = indice % 5
            for numero in range(1, cantidad + 1):
                entrega = EntregaReceta.objects.create(
                    receta=receta, numero=numero, creado_por=usuarios["tecnico"],
                )
                EntregaReceta.objects.filter(pk=entrega.pk).update(
                    creado_en=timezone.now() - timedelta(days=(indice + numero * 7) % 30),
                )
            Receta.objects.filter(pk=receta.pk).update(entregas_completadas=cantidad)
            if indice < 12:
                emitir_turno(rut, uuid.uuid4())

        # Panel de mermas (spec 13): 45 días de turnos cerrados con recetas preparadas y sin retirar.
        from datetime import datetime, time as hora
        from turnosapp.models import Turno, TurnoReceta
        azar = Random(1313)
        recetas_demo = list(Receta.objects.select_related("paciente").order_by("pk"))
        cierres = ("ausente", "sin_atencion_cierre", "atendido", "cerrado_sin_entrega")
        # Enmienda del 2026-11-25: hora de emisión repartida, causa en los cierres con atención, recetas entregadas en
        # la atención y visitas a domicilio registradas, para revisar todo el dashboard.
        from entregasapp.models import Entrega, IntentoEntrega, RecetaEntrega
        from turnosapp.models import CierreAtencion, DetalleCierre, OperacionAtencion
        zona = timezone.get_current_timezone()
        causas = ("sin_stock", "no_la_pide", "no_vigente", "cambio_indicacion", "otro")
        etiquetas = {"sin_stock": "Sin stock", "no_la_pide": "Paciente no la pide", "no_vigente": "Receta no vigente o sin cupo",
                     "cambio_indicacion": "Cambio de indicación", "otro": "Otro: Detalle sintético de demostración"}
        pacientes_demo = list(Paciente.objects.order_by("pk")[:40])
        recetas_atencion = [Receta.objects.create(paciente=p, codigo=f"ATENCION-{i:04d}", fecha_inicio=hoy - timedelta(days=60),
                                                  fecha_fin_exclusiva=hoy + timedelta(days=150), vigencia_meses=6, max_entregas=200)
                            for i, p in enumerate(pacientes_demo)]
        numeros_entrega = {}

        def cerrar(turno, vinculo, entregada, instante):
            operacion = OperacionAtencion.objects.create(actor=usuarios["tecnico"], tipo="finalizar", turno=turno,
                                                         huella="v" * 64, resultado={})
            causa = "" if entregada else azar.choice(causas)
            cierre = CierreAtencion.objects.create(turno=turno, actor=usuarios["tecnico"], operacion=operacion, instante=instante,
                                                   resultado="con_entrega" if entregada else "sin_entrega", causa=causa,
                                                   motivo="" if entregada else etiquetas[causa])
            entrega = None
            if entregada:
                numeros_entrega[vinculo.receta_id] = numeros_entrega.get(vinculo.receta_id, 0) + 1
                entrega = EntregaReceta.objects.create(receta=vinculo.receta, numero=numeros_entrega[vinculo.receta_id],
                                                       turno_receta=vinculo)
                EntregaReceta.objects.filter(pk=entrega.pk).update(creado_en=instante)
            DetalleCierre.objects.create(cierre=cierre, turno_receta=vinculo, entregada=entregada, entrega=entrega,
                                         causa=causa, motivo="" if entregada else etiquetas[causa])

        for dias_atras in range(1, 46):
            fecha = hoy - timedelta(days=dias_atras)
            inicio_dia = timezone.make_aware(datetime.combine(fecha, hora(8)), zona)
            numero = 0
            for receta in azar.sample(recetas_demo, azar.randint(0, 4)):
                numero += 1
                momento = inicio_dia + timedelta(minutes=azar.randint(0, 11 * 60))
                estado = cierres[(dias_atras + numero) % 4]
                turno = Turno.objects.create(
                    paciente=receta.paciente, rut=receta.paciente.rut, fecha=fecha, letra="G", numero=numero,
                    tipo_atencion="general", estado=estado, entrada_cola=momento,
                    cerrado_en=momento + timedelta(hours=1),
                )
                Turno.objects.filter(pk=turno.pk).update(creado_en=momento)
                vinculo = TurnoReceta.objects.create(turno=turno, receta=receta)
                PreparacionReceta.objects.create(
                    turno_receta=vinculo, recibida_en=momento,
                    lista_en=momento + timedelta(minutes=12), lista_por=usuarios["tecnico"],
                    inicio_medido=momento, duracion_segundos=720,
                )
                if estado in ("atendido", "cerrado_sin_entrega"):
                    cerrar(turno, vinculo, False, momento + timedelta(hours=1))
            if fecha.weekday() < 5:
                for receta in azar.sample(recetas_atencion, 12):
                    numero += 1
                    momento = inicio_dia + timedelta(minutes=azar.randint(0, 11 * 60))
                    turno = Turno.objects.create(
                        paciente=receta.paciente, rut=receta.paciente.rut, fecha=fecha, letra="G", numero=numero,
                        tipo_atencion="general", estado="atendido", entrada_cola=momento, cerrado_en=momento + timedelta(minutes=30),
                    )
                    Turno.objects.filter(pk=turno.pk).update(creado_en=momento)
                    vinculo = TurnoReceta.objects.create(turno=turno, receta=receta)
                    PreparacionReceta.objects.create(
                        turno_receta=vinculo, recibida_en=momento, lista_en=momento + timedelta(minutes=12),
                        lista_por=usuarios["tecnico"], inicio_medido=momento, duracion_segundos=720,
                    )
                    cerrar(turno, vinculo, True, momento + timedelta(minutes=30))
                registro = inicio_dia + timedelta(hours=4)
                for n, receta in enumerate(azar.sample(recetas_atencion, 2)):
                    entrega = Entrega.objects.create(paciente=receta.paciente, estado="entregada", operacion_id=uuid.uuid4(),
                                                     cerrada_en=registro)
                    if n == 0 and azar.random() < 0.4:
                        IntentoEntrega.objects.create(entrega=entrega, numero=1, fecha_programada=fecha,
                                                      encargado=usuarios["terreno"], resultado="no_entregada",
                                                      motivo=azar.choice(("sin_receptor", "camino_intransitable", "domicilio_no_encontrado")),
                                                      registrado_en=registro - timedelta(hours=2),
                                                      registrado_por=usuarios["terreno"], operacion_id=uuid.uuid4())
                    numeros_entrega[receta.pk] = numeros_entrega.get(receta.pk, 0) + 1
                    entrega_receta = EntregaReceta.objects.create(receta=receta, numero=numeros_entrega[receta.pk])
                    RecetaEntrega.objects.create(entrega=entrega, receta=receta, resultado="descontada",
                                                 entrega_receta=entrega_receta)
                    IntentoEntrega.objects.create(entrega=entrega, numero=entrega.intentos.count() + 1, fecha_programada=fecha,
                                                  encargado=usuarios["terreno"], resultado="entregada", registrado_en=registro,
                                                  registrado_por=usuarios["terreno"], operacion_id=uuid.uuid4())
        for receta_id, cantidad in numeros_entrega.items():
            Receta.objects.filter(pk=receta_id).update(entregas_completadas=cantidad)

        # Reparto (specs 08, 09 y 11): tres visitas de hoy para el encargado, para revisar «Mis entregas» y la vista
        # sin conexión. Pacientes y coordenadas sintéticos, cerca del origen configurado.
        from entregasapp.services import guardar_domicilio, programar_entrega
        for indice, rut in enumerate(generar_ruts(3, Random(1111))):
            paciente = Paciente.objects.create(
                rut=rut, nombres="Paciente de reparto", apellidos=f"Simulado {indice + 1:02d}",
                fecha_nacimiento=date(1940, 3, 1), telefono="+56 9 0000 0000", direccion="Camino sintético",
            )
            Receta.objects.create(paciente=paciente, codigo=f"REPARTO-{indice + 1:04d}", fecha_inicio=hoy - timedelta(days=10),
                                  fecha_fin_exclusiva=hoy + timedelta(days=150), vigencia_meses=6, max_entregas=6)
            guardar_domicilio(usuarios["qf"], paciente.pk, {
                "sector": ("verde", "azul", "rojo")[indice], "localidad": "Localidad demo",
                "direccion": f"Camino sintético km {indice + 2}", "referencias": "Portón sintético",
                "latitud": f"{settings.REPARTO_ORIGEN_LATITUD + 0.01 * (indice + 1):.6f}",
                "longitud": f"{settings.REPARTO_ORIGEN_LONGITUD + 0.01 * (indice + 1):.6f}",
            })
            programar_entrega(usuarios["qf"], paciente.pk, hoy, usuarios["terreno"].pk, uuid.uuid4())

        from turnosapp.models import Ventanilla
        ventanilla = Ventanilla.objects.get(numero=1)
        ocupar_ventanilla(usuarios["tecnico"], ventanilla.pk, uuid.uuid4())
        iniciar_automatico(usuarios["tecnico"], ventanilla.pk, uuid.uuid4())
        procesar_pendientes()
        for preparacion in PreparacionReceta.objects.order_by("pk")[:3]:
            marcar_lista(usuarios["qf"], preparacion.pk)

        print(f"Vista local aislada: http://127.0.0.1:{argumentos.port}/", flush=True)
        print("Cuentas sintéticas: revision_qf / revision_tecnico / revision_terreno / revision_director / revision_admin", flush=True)
        print(f"Clave temporal: {clave}", flush=True)
        print("La base temporal se elimina al cerrar con Ctrl+C.", flush=True)
        try:
            Server(
                ASGIStaticFilesHandler(application),
                endpoints=[f"tcp:port={argumentos.port}:interface=127.0.0.1"],
                verbosity=0,
            ).run()
        finally:
            connections.close_all()


if __name__ == "__main__":
    main()
