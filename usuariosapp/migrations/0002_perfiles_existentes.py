"""Preparar perfiles sin inferir roles ni verificar correos existentes."""

from django.conf import settings
from django.db import migrations


def crear_perfiles(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    Usuario = apps.get_model(app_label, model_name)
    Perfil = apps.get_model("usuariosapp", "Perfil")
    alias = schema_editor.connection.alias
    for usuario_id in Usuario.objects.using(alias).values_list("pk", flat=True).iterator():
        Perfil.objects.using(alias).get_or_create(usuario_id=usuario_id)


class Migration(migrations.Migration):
    dependencies = [
        ("usuariosapp", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_perfiles, migrations.RunPython.noop),
    ]
