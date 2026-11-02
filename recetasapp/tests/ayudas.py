"""Preparación explícita de actores y archivos sintéticos para pruebas."""

import io
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from coreapp.roles import ENCARGADO, JEFA, TECNICO
from recetasapp.importacion import filas_demo, generar_archivo, importar_padron
from usuariosapp.models import Perfil


def actores():
    resultado = {}
    for nombre, rol in (("qf", JEFA), ("tecnico", TECNICO), ("encargado", ENCARGADO)):
        usuario = get_user_model().objects.create_user(username="sintetico_" + nombre)
        Perfil.objects.create(usuario=usuario)
        usuario.groups.add(Group.objects.get_or_create(name=rol)[0])
        resultado[nombre] = usuario
    resultado["admin"] = get_user_model().objects.create_superuser(username="sintetico_admin")
    return resultado


def fila(codigo="DEMO-0001"):
    datos = list(filas_demo(cantidad=1, inicio=date(2026, 1, 1)))[0]
    datos[8] = codigo
    return datos


def cargar(actor, filas, formato="csv"):
    return importar_padron(actor, io.BytesIO(generar_archivo(formato, filas)), formato)
