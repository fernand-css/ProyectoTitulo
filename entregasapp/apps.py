from django.apps import AppConfig


class EntregasappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'entregasapp'

    def ready(self):
        from . import checks  # noqa: F401  (registra la comprobación de la configuración del mapa)
