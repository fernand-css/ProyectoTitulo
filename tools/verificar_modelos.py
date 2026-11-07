"""Inspección de modelos sin conexión, persistencia ni migraciones aplicadas.

Usa únicamente Django ya disponible. El backend dummy es una barrera de conexión
para esta inspección; la aplicación y las pruebas de integración usan PostgreSQL.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django
from django.conf import settings

settings.configure(
    INSTALLED_APPS=[
        "django.contrib.auth", "django.contrib.contenttypes",
        "apps.usuarios", "apps.pacientes", "apps.turnos",
    ],
    AUTH_USER_MODEL="usuarios.Usuario",
    DATABASES={"default": {"ENGINE": "django.db.backends.dummy"}},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    USE_TZ=True,
    TIME_ZONE="America/Santiago",
)
django.setup()

from django.core.checks import Tags, run_checks
from django.db import models
from apps.pacientes.models import Paciente
from apps.turnos.models import EstadoCola, Turno, Ventanilla
from apps.usuarios.models import Usuario

errores = run_checks(tags=[Tags.models])
for error in errores:
    print(error)
if errores:
    raise SystemExit(1)

assert settings.AUTH_USER_MODEL == "usuarios.Usuario"
assert isinstance(Usuario._meta.pk, models.BigAutoField)
assert Paciente._meta.get_field("identificador_sintetico").unique
assert not Turno._meta.get_field("paciente").null
assert Turno._meta.get_field("ventanilla").null
assert Ventanilla._meta.get_field("operador").unique
nombres = {restriccion.name for restriccion in Turno._meta.constraints}
assert {"turno_numero_por_jornada", "turno_un_activo_paciente", "turno_un_ocupante_ventanilla", "turno_estado_asignacion_fechas"} <= nombres
assert EstadoCola._meta.get_field("peso_general").default == 2
assert EstadoCola._meta.get_field("peso_preferencial").default == 1
print("Inspección estructural correcta: usuario, FK, unicidades, estados y pesos 2:1.")
print("No se abrió una base de datos ni se aplicaron migraciones.")
