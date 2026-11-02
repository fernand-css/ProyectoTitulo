from django.apps import AppConfig


class UsuariosappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usuariosapp'

    def ready(self):
        from . import signals  # noqa: F401
