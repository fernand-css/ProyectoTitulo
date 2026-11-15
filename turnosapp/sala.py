"""Registro de llamados y proyección pública sin identidad de pacientes."""
from zoneinfo import ZoneInfo

from django.utils import timezone

from django.db.models import Count

from .models import AnuncioSala, Letra, Turno, Ventanilla

ZONA_SALA = ZoneInfo("America/Santiago")
# Orden de RF-06-13 para «En espera».
LETRAS_SALA = [Letra.PREFERENCIAL, Letra.GENERAL, Letra.CRONICOS, Letra.URGENCIA]


def instante_publico(instante):
    return timezone.localtime(instante, ZONA_SALA).isoformat()


def anuncio_publico(anuncio):
    """Lista explícita: nunca serializar el evento ni relaciones privadas."""
    return {
        "id": anuncio.id, "letra": anuncio.letra, "numero": anuncio.numero,
        "ventanilla": anuncio.ventanilla_numero, "accion": anuncio.accion,
        "instante": instante_publico(anuncio.instante),
    }


def estado_sala(ahora=None):
    ahora = ahora or timezone.now()
    fecha = timezone.localtime(ahora, ZONA_SALA).date()
    llamados = {
        turno["ventanilla_id"]: turno
        for turno in Turno.objects.filter(fecha=fecha, estado="llamado").values(
            "ventanilla_id", "letra", "numero", "ultimo_llamado",
        )
    }
    ventanillas = []
    for ventanilla in Ventanilla.objects.filter(retirada=False).order_by("numero").values(
        "id", "numero", "habilitada", "automatico", "fecha_activacion",
    ):
        turno = llamados.get(ventanilla["id"])
        disponible = ventanilla["habilitada"] and ventanilla["automatico"] and ventanilla["fecha_activacion"] == fecha
        ventanillas.append({
            "numero": ventanilla["numero"],
            "estado": "llamado" if turno else ("disponible" if disponible else "sin_atencion"),
            "llamado": turno["numero"] if turno else None,
            "letra": turno["letra"] if turno else None,
            "desde": instante_publico(turno["ultimo_llamado"]) if turno else None,
        })
    recientes = [anuncio_publico(a) for a in AnuncioSala.objects.filter(fecha=fecha).order_by("-id")[:20]]
    # RF-06-13: solo cantidades por letra; listar números sugería un orden de llamado que no existe.
    conteo = dict(Turno.objects.filter(fecha=fecha, estado="esperando").values_list("letra")
        .annotate(cantidad=Count("pk")).order_by())
    por_letra = [{"letra": str(letra), "cantidad": conteo.get(letra, 0)} for letra in LETRAS_SALA]
    return {
        "tipo": "estado", "ahora": instante_publico(ahora), "fecha": fecha.isoformat(),
        "ultimo_id": recientes[0]["id"] if recientes else 0,
        "ventanillas": ventanillas, "recientes": recientes,
        "espera": {"cantidad": sum(item["cantidad"] for item in por_letra), "por_letra": por_letra},
    }


def registrar_anuncio(evento, turno, ventanilla):
    """El llamador reserva la cola y confirma evento y anuncio en el mismo atomic."""
    if evento.accion not in ("llamado", "rellamado"):
        raise ValueError("Solo los llamados generan anuncios de sala.")
    anuncio, _ = AnuncioSala.objects.get_or_create(
        evento=evento,
        defaults={
            "fecha": timezone.localdate(evento.instante),
            "numero": turno.numero,
            "letra": turno.letra,
            "ventanilla_numero": ventanilla.numero,
            "accion": evento.accion,
            "instante": evento.instante,
        },
    )
    return anuncio
