"""Pestañas de la sección Recetas y de la ficha del paciente: qué ofrecen y cuál está abierta.

Cada pestaña es un enlace a su propia dirección (nada se oculta con JavaScript), así que se puede volver
atrás, compartir el enlace y usarlas con teclado y lector de pantalla. La cantidad es la que ayuda a decidir
adónde ir: lo que falta por preparar, lo que espera retiro.
"""

from django.urls import reverse
from django.utils import timezone

from . import preparacion
from .models import Receta

PESTANAS_FICHA = ("recetas", "entregas", "datos")


def _marcar(pestanas, actual):
    return [{**pestana, "actual": pestana["clave"] == actual} for pestana in pestanas]


def recetas(actual, total=None):
    """Pestañas de Recetas. `actual` es la clave de la abierta; `total` evita recontar si la vista ya lo tiene."""
    por_preparar = preparacion.por_preparar(timezone.localdate()).filter(lista_en__isnull=True).count()
    return _marcar([
        {"clave": "resumen", "texto": "Resumen", "url": reverse("recetasapp:recetas"), "cantidad": None},
        {"clave": "lista", "texto": "Todas las recetas", "url": reverse("recetasapp:recetas_lista"),
         "cantidad": Receta.objects.count() if total is None else total},
        {"clave": "preparar", "texto": "Por preparar", "url": reverse("recetasapp:preparacion"), "cantidad": por_preparar},
        {"clave": "retiro", "texto": "Pendientes de retiro", "url": reverse("recetasapp:preparacion_pendientes"),
         "cantidad": preparacion.pendientes_retiro().count()},
    ], actual)


def pestana_de_ficha(valor):
    """Pestaña pedida en la URL de la ficha; cualquier otro valor abre «Recetas»."""
    return valor if valor in PESTANAS_FICHA else "recetas"


def ficha(paciente, actual, cantidad_recetas, cantidad_entregas):
    """Pestañas de la ficha de un paciente: sus recetas, sus entregas y sus datos."""
    base = reverse("recetasapp:paciente_detalle", args=[paciente.pk])
    return _marcar([
        {"clave": "recetas", "texto": "Recetas", "url": base, "cantidad": cantidad_recetas},
        {"clave": "entregas", "texto": "Entregas", "url": f"{base}?pestana=entregas", "cantidad": cantidad_entregas},
        {"clave": "datos", "texto": "Datos", "url": f"{base}?pestana=datos", "cantidad": None},
    ], actual)
