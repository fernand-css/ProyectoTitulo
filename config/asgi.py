import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_application = get_asgi_application()

from channels.routing import ProtocolTypeRouter

# El endpoint WebSocket se incorpora después de validar el bloque de persistencia.
application = ProtocolTypeRouter({"http": django_application})
