# Spec 10 (2026-11-15, RF-10-04, 05 y 07): letra y número anteriores en el historial del turno.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('turnosapp', '0012_anuncio_sala_letra_obligatoria'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='eventoturno',
            name='letra_anterior',
            field=models.CharField(blank=True, choices=[('P', 'P'), ('G', 'G'), ('C', 'C'), ('U', 'U')], max_length=1),
        ),
        migrations.AddField(
            model_name='eventoturno',
            name='numero_anterior',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='eventoturno',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('letra_anterior', ''), ('numero_anterior__isnull', True)), models.Q(('letra_anterior__in', ['P', 'G', 'C', 'U']), ('numero_anterior__gte', 1)), _connector='OR'), name='evento_numero_anterior_coherente'),
        ),
    ]
