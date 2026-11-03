"""WebSocket público exclusivamente de salida."""
import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from .vigilante import vigilante

logger = logging.getLogger(__name__)


class SalaConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        cliente = self.scope.get("client")
        direccion = cliente[0] if cliente else "sin-direccion"

        async def iniciar(estado):
            await self.accept()
            await self.send_json(estado)

        try:
            aceptada = await vigilante.registrar(self.channel_name, direccion, self.channel_layer, iniciar, self.close)
        except Exception:
            logger.error("No se pudo abrir la pantalla de sala; puede reintentar la conexión.")
            await self.close(code=1011)
            return
        if not aceptada:
            await self.close(code=1013)

    async def disconnect(self, code):
        await vigilante.retirar(self.channel_name)

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        # No se interpreta JSON, ni se registra contenido, ni se ejecutan comandos.
        longitud = len(text_data.encode("utf-8")) if text_data is not None else len(bytes_data or b"")
        if longitud > settings.SALA_MAX_MENSAJE:
            await self.close(code=1009)

    async def sala_mensaje(self, evento):
        await self.send_json(evento["datos"])
