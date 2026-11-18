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
        for dias_atras in range(1, 46):
            fecha = hoy - timedelta(days=dias_atras)
            momento = timezone.make_aware(datetime.combine(fecha, hora(10)), timezone.get_current_timezone())
            for numero, receta in enumerate(azar.sample(recetas_demo, azar.randint(0, 4)), start=1):
                turno = Turno.objects.create(
                    paciente=receta.paciente, rut=receta.paciente.rut, fecha=fecha, letra="G", numero=numero,
                    tipo_atencion="general", estado=cierres[(dias_atras + numero) % 4], entrada_cola=momento,
                    cerrado_en=momento + timedelta(hours=1),
                )
                PreparacionReceta.objects.create(
                    turno_receta=TurnoReceta.objects.create(turno=turno, receta=receta), recibida_en=momento,
                    lista_en=momento + timedelta(minutes=12), lista_por=usuarios["tecnico"],
                    inicio_medido=momento, duracion_segundos=720,
                )

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
