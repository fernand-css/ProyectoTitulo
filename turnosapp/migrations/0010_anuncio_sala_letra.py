# Enmienda del spec 06 (2026-11-15, RF-06-13), paso 1 de 3: letra del anuncio, todavía opcional.

from django.db import migrations, models


LETRAS = [("P", "P"), ("G", "G"), ("C", "C"), ("U", "U")]


class Migration(migrations.Migration):

    dependencies = [
        ("turnosapp", "0009_ventanilla_urgencia_datos"),
    ]

    operations = [
        migrations.AddField(
            model_name="anunciosala",
            name="letra",
            field=models.CharField(choices=LETRAS, max_length=1, null=True),
        ),
    ]
