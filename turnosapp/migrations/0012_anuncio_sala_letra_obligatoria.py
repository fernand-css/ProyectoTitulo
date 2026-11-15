# Enmienda del spec 06 (2026-11-15, RF-06-13), paso 3 de 3: letra obligatoria y válida.

from django.db import migrations, models


LETRAS = [("P", "P"), ("G", "G"), ("C", "C"), ("U", "U")]


class Migration(migrations.Migration):

    dependencies = [
        ("turnosapp", "0011_rellenar_anuncio_letra"),
    ]

    operations = [
        migrations.AlterField(
            model_name="anunciosala",
            name="letra",
            field=models.CharField(choices=LETRAS, max_length=1),
        ),
        migrations.AddConstraint(
            model_name="anunciosala",
            constraint=models.CheckConstraint(
                condition=models.Q(("letra__in", ["P", "G", "C", "U"])), name="sala_letra_valida",
            ),
        ),
    ]
