"""Datos sintéticos para las pruebas del reparto: pacientes, recetas, cuentas e imágenes generadas.

Ningún dato representa a una persona real. Los RUT son ficticios con dígito verificador válido y las fotos
se dibujan en memoria con Pillow (nunca fotos de viviendas reales).
"""

import io
import itertools
import uuid
from datetime import date, timedelta
from random import Random

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from coreapp.roles import ENCARGADO, JEFA, TECNICO
from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import Paciente, Receta
from usuariosapp.models import Perfil

_RUTS = generar_ruts(3000, Random(808))
_SECUENCIA = itertools.count()


def hoy():
    return timezone.localdate()


def nacimiento_para(edad, fecha=None, dias_extra=0):
    """Fecha de nacimiento con la que se cumplen `edad` años a `fecha` (y `dias_extra` días más joven)."""
    fecha = fecha or hoy()
    try:
        base = fecha.replace(year=fecha.year - edad)
    except ValueError:
        base = date(fecha.year - edad, 2, 28)
    return base + timedelta(days=dias_extra)


def paciente(*, edad=85, postrado=False, cronico=False, direccion="Camino a Dadinco km 2, casa roja", nacimiento=None):
    indice = next(_SECUENCIA)
    return Paciente.objects.create(
        rut=_RUTS[indice % len(_RUTS)], nombres="Paciente sintético", apellidos=f"Reparto {indice}",
        fecha_nacimiento=nacimiento or nacimiento_para(edad), es_postrado=postrado, es_cronico=cronico,
        telefono="+56 9 0000 0000", direccion=direccion,
    )


def receta(paciente, codigo=None, *, inicio=None, fin=None, maximo=6, completadas=0):
    inicio = inicio or hoy() - timedelta(days=30)
    return Receta.objects.create(
        paciente=paciente, codigo=codigo or f"DESP-{uuid.uuid4().hex[:10]}", fecha_inicio=inicio,
        vigencia_meses=6, max_entregas=maximo, entregas_completadas=completadas,
        fecha_fin_exclusiva=fin or hoy() + timedelta(days=150),
    )


def cuenta(nombre, rol=None, *, activa=True, perfil=True):
    usuario = get_user_model().objects.create_user(
        username=f"sintetico_{nombre}", first_name="Persona", last_name="Sintética", is_active=activa,
    )
    if perfil:
        Perfil.objects.create(usuario=usuario)
    if rol:
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
    return usuario


def equipo():
    """Q.F., técnico, dos encargados y un superusuario, todos sintéticos."""
    return {
        "qf": cuenta("qf_reparto", JEFA),
        "tecnico": cuenta("tecnico_reparto", TECNICO),
        "encargado": cuenta("encargado_reparto", ENCARGADO),
        "encargado2": cuenta("encargado_reparto_2", ENCARGADO),
        "admin": get_user_model().objects.create_superuser(username="sintetico_admin_reparto"),
    }


def imagen(formato="JPEG", tamano=(64, 48), *, color=(30, 90, 160), exif_gps=False, modo="RGB"):
    """Imagen sintética en memoria; con `exif_gps` lleva coordenadas falsas en su EXIF."""
    from PIL import Image

    lienzo = Image.new(modo, tamano, color if modo == "RGB" else (*color, 120))
    salida = io.BytesIO()
    opciones = {}
    if exif_gps:
        exif = Image.Exif()
        exif[0x010F] = "Fabricante sintético"  # Make
        exif[0x8825] = {1: "S", 2: (36.0, 30.0, 0.0), 3: "W", 4: (72.0, 12.0, 0.0)}  # GPSInfo
        opciones["exif"] = exif.tobytes()
    lienzo.save(salida, format=formato, **opciones)
    return salida.getvalue()


def archivo(contenido, nombre="foto.jpg", tipo="image/jpeg"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(nombre, contenido, content_type=tipo)


# Ruta del día (spec 09) ------------------------------------------------------------------------------------------

def punto_km(dx, dy):
    """(latitud, longitud) a `dx` km al este y `dy` km al norte del origen configurado (el CESFAM).

    Coordenadas sintéticas: no representan viviendas reales.
    """
    import math

    from django.conf import settings

    metros_por_grado = 6_371_000 * math.pi / 180
    latitud = settings.REPARTO_ORIGEN_LATITUD + dy * 1000 / metros_por_grado
    longitud = settings.REPARTO_ORIGEN_LONGITUD + dx * 1000 / (metros_por_grado * math.cos(math.radians(settings.REPARTO_ORIGEN_LATITUD)))
    return f"{latitud:.6f}", f"{longitud:.6f}"


def visita(equipo, en=None, *, fecha=None, encargado=None, domicilio=True, sector="verde", localidad="Localidad demo 1"):
    """Programa una entrega con su intento para el encargado. `en=(dx, dy)` en km del CESFAM; None = sin coordenadas.

    Con `domicilio=False` el paciente no tiene domicilio registrado. Devuelve el intento.
    """
    from entregasapp.services import guardar_domicilio, programar_entrega

    persona = paciente(edad=88)
    receta(persona)
    if domicilio:
        datos = {"sector": sector, "localidad": localidad, "direccion": "Camino sintético km 2",
                 "referencias": "Portón sintético"}
        if en is not None:
            datos["latitud"], datos["longitud"] = punto_km(*en)
            datos["precision_metros"] = "10"
        guardar_domicilio(equipo["qf"], persona.pk, datos)
    entrega = programar_entrega(equipo["qf"], persona.pk, fecha or hoy(), (encargado or equipo["encargado"]).pk, uuid.uuid4())
    return entrega.intentos.get()
