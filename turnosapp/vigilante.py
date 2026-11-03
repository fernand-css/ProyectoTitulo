"""Lectura compartida de anuncios durables; independiente del proceso emisor."""
import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.exceptions import ChannelFull
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import AnuncioSala
from .sala import ZONA_SALA, anuncio_publico, estado_sala, instante_publico

logger = logging.getLogger(__name__)


def leer_sala(cursor):
    ahora = timezone.now()
    fecha = timezone.localtime(ahora, ZONA_SALA).date()
    anuncios = [anuncio_publico(a) for a in AnuncioSala.objects.filter(fecha=fecha).filter(
        Q(id__gt=cursor) | Q(instante__gte=ahora - timedelta(seconds=30)),
    ).order_by("id")]
    return estado_sala(ahora), anuncios


def firma_estado(estado):
    return json.dumps({k: v for k, v in estado.items() if k != "ahora"}, sort_keys=True)


@dataclass
class Suscripcion:
    direccion: str
    capa: object
    cerrar: object
    firma: str
    fecha: str
    vistos: set = field(default_factory=set)


class VigilanteSala:
    def __init__(self):
        self.conexiones = {}
        self.tarea = None
        self.cursor = 0
        self.fecha = None
        self._candado = asyncio.Lock()

    async def registrar(self, canal, direccion, capa, iniciar, cerrar):
        async with self._candado:
            if (len(self.conexiones) >= settings.SALA_MAX_CONEXIONES or
                    sum(s.direccion == direccion for s in self.conexiones.values()) >= settings.SALA_MAX_POR_DIRECCION):
                return False
            # La lectura y el alta no se intercalan con una difusión del vigilante.
            estado, anuncios = await database_sync_to_async(leer_sala)(0)
            await iniciar(estado)
            vistos = {a["id"] for a in anuncios} | {a["id"] for a in estado["recientes"]}
            self.conexiones[canal] = Suscripcion(direccion, capa, cerrar, firma_estado(estado), estado["fecha"], vistos)
            if self.tarea is None:
                self.fecha, self.cursor = estado["fecha"], estado["ultimo_id"]
                self.tarea = asyncio.create_task(self._vigilar())
            return True

    async def retirar(self, canal):
        tarea = None
        async with self._candado:
            self.conexiones.pop(canal, None)
            if not self.conexiones:
                tarea, self.tarea = self.tarea, None
        if tarea is not None:
            tarea.cancel()
            with suppress(asyncio.CancelledError):
                await tarea

    async def _enviar(self, canal, suscripcion, mensajes):
        try:
            for mensaje in mensajes:
                # send informa saturación; group_send podría descartar en silencio.
                await suscripcion.capa.send(canal, {"type": "sala.mensaje", "datos": mensaje})
            return True
        except ChannelFull:
            self.conexiones.pop(canal, None)
            await suscripcion.cerrar(code=1013)
            return False

    async def revisar(self, latido=False):
        async with self._candado:
            if not self.conexiones:
                return
            estado, anuncios = await database_sync_to_async(leer_sala)(self.cursor)
            if estado["fecha"] != self.fecha:
                self.fecha, self.cursor = estado["fecha"], 0
            firma = firma_estado(estado)
            ids = {a["id"] for a in anuncios}
            for canal, s in list(self.conexiones.items()):
                if s.fecha != estado["fecha"]:
                    s.fecha = estado["fecha"]
                    s.vistos.clear()
                nuevos = [a for a in anuncios if a["id"] not in s.vistos]
                mensajes = [{"tipo": "anuncio", **a} for a in nuevos]
                if s.firma != firma:
                    mensajes.append(estado)
                if latido:
                    mensajes.append({"tipo": "latido", "ahora": estado["ahora"]})
                if await self._enviar(canal, s, mensajes):
                    # Solo se retienen ids que la ventana incremental puede releer.
                    s.vistos.intersection_update(ids)
                    s.vistos.update(a["id"] for a in nuevos)
                    s.firma = firma
            self.cursor = max([self.cursor] + [a["id"] for a in anuncios])

    async def _vigilar(self):
        bucle = asyncio.get_running_loop()
        proximo_latido = bucle.time() + settings.SALA_LATIDO
        try:
            while self.conexiones:
                await asyncio.sleep(settings.SALA_INTERVALO)
                try:
                    latido = bucle.time() >= proximo_latido
                    await self.revisar(latido=latido)
                    if latido:
                        proximo_latido = bucle.time() + settings.SALA_LATIDO
                except Exception:
                    # No incluir excepciones, consultas ni contenido del cliente.
                    logger.error("No se pudo actualizar el estado público de sala; se reintentará.")
        finally:
            if self.tarea is asyncio.current_task():
                self.tarea = None


vigilante = VigilanteSala()
