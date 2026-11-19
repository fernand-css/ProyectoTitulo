"""Ejecutor de pruebas del proyecto: el de Django, con el servidor de rutas desactivado.

Spec 09 (enmienda del 2026-11-15, RF-09-19): las pruebas no dependen de que OSRM esté corriendo. Sin esto, con el
contenedor local encendido en 127.0.0.1:5000, las pruebas de la ruta recibirían distancias reales por camino y
dejarían de ser deterministas. Cada prueba que necesita OSRM lo simula y lo activa con `override_settings`.
"""

from django.conf import settings
from django.test.runner import DiscoverRunner


class EjecutorPruebas(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._osrm_url = settings.OSRM_URL
        settings.OSRM_URL = ""
        # Spec 12, quinta enmienda: ninguna prueba envía avisos en segundo plano sin pedirlo.
        self._avisos = settings.REPARTO_AVISOS_AUTOMATICOS
        settings.REPARTO_AVISOS_AUTOMATICOS = "no"

    def teardown_test_environment(self, **kwargs):
        settings.OSRM_URL = self._osrm_url
        settings.REPARTO_AVISOS_AUTOMATICOS = self._avisos
        super().teardown_test_environment(**kwargs)
