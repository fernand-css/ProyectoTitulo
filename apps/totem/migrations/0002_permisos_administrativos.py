"""Opciones de permisos exclusivamente; no altera columnas ni datos."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("totem", "0001_initial")]

    operations = [
        migrations.AlterModelOptions(
            name="dispositivototem",
            options={
                "ordering": ("alias",),
                "default_permissions": (),
                "permissions": [
                    ("consultar_dispositivos", "Puede consultar dispositivos de tótem"),
                    ("generar_codigos_activacion", "Puede generar códigos de activación"),
                    ("revocar_dispositivos", "Puede revocar dispositivos de tótem"),
                    ("caducar_codigos_activacion", "Puede caducar códigos de activación"),
                ],
            },
        ),
    ]
