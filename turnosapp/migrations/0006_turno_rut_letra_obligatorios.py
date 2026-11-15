# Enmienda del spec 04 (2026-11-15), paso 3 de 3: NOT NULL y restricciones por RUT y letra.
# Reversible mientras no existan turnos sin paciente ni números repetidos entre letras de una fecha.

from django.db import migrations, models


LETRAS = [("P", "P"), ("G", "G"), ("C", "C"), ("U", "U")]


class Migration(migrations.Migration):

    dependencies = [
        ("turnosapp", "0005_rellenar_rut_letra"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contadorturnosdiario",
            name="letra",
            field=models.CharField(choices=LETRAS, max_length=1),
        ),
        migrations.AlterField(
            model_name="turno",
            name="rut",
            field=models.CharField(max_length=12, verbose_name="RUT"),
        ),
        migrations.AlterField(
            model_name="turno",
            name="letra",
            field=models.CharField(choices=LETRAS, max_length=1),
        ),
        migrations.RemoveConstraint(
            model_name="turno",
            name="turno_numero_diario_unico",
        ),
        migrations.RemoveConstraint(
            model_name="turno",
            name="turno_activo_paciente_dia_unico",
        ),
        migrations.RemoveConstraint(
            model_name="turno",
            name="turno_llamado_paciente_unico",
        ),
        migrations.AddConstraint(
            model_name="contadorturnosdiario",
            constraint=models.UniqueConstraint(fields=("fecha", "letra"), name="contador_fecha_letra_unico"),
        ),
        migrations.AddConstraint(
            model_name="contadorturnosdiario",
            constraint=models.CheckConstraint(
                condition=models.Q(("letra__in", ["P", "G", "C", "U"])), name="contador_letra_valida",
            ),
        ),
        migrations.AddConstraint(
            model_name="turno",
            constraint=models.UniqueConstraint(
                fields=("fecha", "letra", "numero"), name="turno_numero_letra_diario_unico",
            ),
        ),
        migrations.AddConstraint(
            model_name="turno",
            constraint=models.UniqueConstraint(
                condition=models.Q(("estado__in", ["esperando", "llamado"])),
                fields=("rut", "fecha"), name="turno_activo_rut_dia_unico",
            ),
        ),
        migrations.AddConstraint(
            model_name="turno",
            constraint=models.CheckConstraint(condition=models.Q(("rut", ""), _negated=True), name="turno_rut_no_vacio"),
        ),
        migrations.AddConstraint(
            model_name="turno",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("letra", "G"), ("tipo_atencion", "general"))
                    | models.Q(("letra", "P"), ("tipo_atencion", "preferencial"))
                    | models.Q(("letra", "C"), ("tipo_atencion", "cronicos"))
                    | models.Q(("letra", "U"), ("tipo_atencion", "urgencia"))
                ),
                name="turno_letra_coherente",
            ),
        ),
        migrations.AddConstraint(
            model_name="turno",
            constraint=models.UniqueConstraint(
                condition=models.Q(("estado", "llamado")), fields=("rut",), name="turno_llamado_rut_unico",
            ),
        ),
        migrations.AddIndex(
            model_name="turno",
            index=models.Index(fields=["rut", "fecha"], name="turno_rut_fecha_idx"),
        ),
    ]
