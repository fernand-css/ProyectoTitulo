# Enmienda del spec 04 (2026-11-15), paso 1 de 3: columnas nuevas todavía opcionales.

import django.db.models.deletion
from django.db import migrations, models


LETRAS = [("P", "P"), ("G", "G"), ("C", "C"), ("U", "U")]
TIPOS = [
    ("general", "General"), ("preferencial", "Preferencial"),
    ("cronicos", "Crónicos"), ("urgencia", "Urgencia"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("turnosapp", "0003_anuncio_sala"),
    ]

    operations = [
        # El contador deja de ser único por fecha; la unicidad (fecha, letra) llega en 0006.
        migrations.AlterField(
            model_name="contadorturnosdiario",
            name="fecha",
            field=models.DateField(),
        ),
        migrations.AddField(
            model_name="contadorturnosdiario",
            name="letra",
            field=models.CharField(choices=LETRAS, default="G", max_length=1),
        ),
        migrations.AlterField(
            model_name="turno",
            name="paciente",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="turnos", to="recetasapp.paciente",
            ),
        ),
        migrations.AddField(
            model_name="turno",
            name="rut",
            field=models.CharField(max_length=12, null=True, verbose_name="RUT"),
        ),
        migrations.AddField(
            model_name="turno",
            name="letra",
            field=models.CharField(choices=LETRAS, max_length=1, null=True),
        ),
        migrations.AlterField(
            model_name="turno",
            name="tipo_atencion",
            field=models.CharField(choices=TIPOS, max_length=12),
        ),
        migrations.RemoveConstraint(
            model_name="turno",
            name="turno_tipo_valido",
        ),
        migrations.AddConstraint(
            model_name="turno",
            constraint=models.CheckConstraint(
                condition=models.Q(("tipo_atencion__in", ["general", "preferencial", "cronicos", "urgencia"])),
                name="turno_tipo_valido",
            ),
        ),
    ]
