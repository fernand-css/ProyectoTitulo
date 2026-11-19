"""Despachador de avisos por correo dentro del servidor web (quinta enmienda del spec 12, RF-12-24 a RF-12-28).

Un hilo por proceso, como el vigilante de la sala: lo inicia `cesfam/asgi.py` o `cesfam/wsgi.py`, nunca un comando
de gestión. Procesa la bandeja al arrancar, cada `INTERVALO` segundos y apenas se confirma un aviso nuevo
(`avisar`, llamado con `transaction.on_commit`). La base es la fuente de verdad: varios procesos pueden despachar a la
vez sin duplicar envíos, gracias a las reservas con token de `notificaciones`.
"""

import logging
import threading

from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)

INTERVALO = 60  # segundos entre vueltas sin clics: aviso del día, reservas vencidas y reintentos.
VUELTAS_POR_CICLO = 20  # lotes de 25 avisos como máximo por ciclo antes de volver a esperar.
MODOS = ("smtp", "simular", "no")


def transporte_configurado():
    from . import notificaciones

    modo = getattr(settings, "REPARTO_AVISOS_AUTOMATICOS", "no")
    return {"smtp": notificaciones.enviar_smtp, "simular": notificaciones.enviar_simulado}.get(modo)


def ciclo(transporte):
    """Procesa la bandeja hasta vaciarla o agotar las vueltas. Nunca lanza: un fallo espera la vuelta siguiente."""
    from . import notificaciones

    procesados = 0
    try:
        for _ in range(VUELTAS_POR_CICLO):
            lote = notificaciones.procesar_avisos(transporte)
            procesados += lote
            if not lote:
                break
    except Exception as error:  # noqa: BLE001 - el hilo debe sobrevivir a cualquier fallo (RF-12-28)
        # Solo el tipo de error: los mensajes de SMTP o de la base podrían incluir direcciones.
        logger.warning("El despachador de avisos falló en esta vuelta (%s); reintentará.", type(error).__name__)
    finally:
        connections.close_all()  # conexiones propias de este hilo
    return procesados


class Despachador:
    def __init__(self):
        self._despertar = threading.Event()
        self._parar = threading.Event()
        self._candado = threading.Lock()
        self._hilo = None

    @property
    def activo(self):
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self):
        """Inicia el hilo si la configuración lo permite. Devuelve True si queda corriendo."""
        transporte = transporte_configurado()
        if transporte is None:
            return False
        with self._candado:
            if self.activo:
                return True
            self._parar.clear()
            self._hilo = threading.Thread(
                target=self._bucle, args=(transporte,), name="despachador-avisos", daemon=True,
            )
            self._hilo.start()
            return True

    def avisar(self):
        """Despierta al hilo para enviar ya un aviso recién confirmado. Sin hilo, no hace nada."""
        self._despertar.set()

    def detener(self, espera=5):
        self._parar.set()
        self._despertar.set()
        hilo = self._hilo
        if hilo is not None:
            hilo.join(espera)
        self._hilo = None

    def _bucle(self, transporte):
        while not self._parar.is_set():
            self._despertar.clear()
            ciclo(transporte)
            self._despertar.wait(INTERVALO)


despachador = Despachador()
