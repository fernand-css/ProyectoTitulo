"""HTTP de Django y canal público de sala con origen validado."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cesfam.settings')

django_asgi_app = get_asgi_application()

# Django debe inicializar el registro de modelos antes de importar las rutas.
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from turnosapp.routing import websocket_urlpatterns

# Quinta enmienda del spec 12: los avisos por correo salen en segundo plano desde este proceso.
from entregasapp.despachador import despachador

despachador.iniciar()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(URLRouter(websocket_urlpatterns)),
})
