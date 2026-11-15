# Enmienda del spec 05 (2026-11-15, RF-05-13): urgencia (U) pasa a ser un tipo de ventanilla.
# Paso 1 de 2: esquema. El paso de datos va en 0009, en su propia transacción: PostgreSQL no
# permite ALTER TABLE con disparadores de FK pendientes del borrado al revertir.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('turnosapp', '0007_intento_totem'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='tipoatencionventanilla',
            name='ventanilla_tipo_valido',
        ),
        migrations.AlterField(
            model_name='tipoatencionventanilla',
            name='codigo',
            field=models.CharField(choices=[('general', 'General'), ('preferencial', 'Preferencial'), ('cronicos', 'Crónicos'), ('urgencia', 'Urgencia')], max_length=12, primary_key=True, serialize=False),
        ),
        migrations.AddConstraint(
            model_name='tipoatencionventanilla',
            constraint=models.CheckConstraint(condition=models.Q(('codigo__in', ['general', 'preferencial', 'cronicos', 'urgencia'])), name='ventanilla_tipo_valido'),
        ),
    ]
