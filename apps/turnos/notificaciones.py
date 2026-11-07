"""Publicación posterior al commit. La bitácora y el turno permanecen en PostgreSQL."""
import logging

from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)
GRUPO_PANTALLA = "pantalla.turnos"


def publicar(evento):
    # Importación diferida: las pruebas puras no necesitan Channels instalado.
    try:
        from channels.layers import get_channel_layer

        capa = get_channel_layer()
        if capa is None:
            raise RuntimeError("No hay una capa de canales configurada.")
        async_to_sync(capa.group_send)(GRUPO_PANTALLA, {
            "type": "turno.actualizado",
            "evento": evento,
        })
    except Exception:
        # Fallar al publicar no debe hacer parecer fallida una operación ya confirmada.
        # La recuperación de pantalla deberá volver a leer PostgreSQL.
        logger.exception("No se pudo publicar el evento de turno %s", evento["evento_id"])
