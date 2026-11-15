# Enmienda del spec 06 (2026-11-15, RF-06-13), paso 2 de 3: copia la letra del turno de cada evento.
# Va en su propia migración (transacción) para que PostgreSQL acepte el ALTER TABLE del paso 3.

from django.db import migrations
from django.db.models import OuterRef, Subquery


def rellenar(apps, schema_editor):
    AnuncioSala = apps.get_model("turnosapp", "AnuncioSala")
    EventoTurno = apps.get_model("turnosapp", "EventoTurno")
    AnuncioSala.objects.filter(letra__isnull=True).update(
        letra=Subquery(EventoTurno.objects.filter(pk=OuterRef("evento_id")).values("turno__letra")[:1]),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("turnosapp", "0010_anuncio_sala_letra"),
    ]

    operations = [
        migrations.RunPython(rellenar, migrations.RunPython.noop),
    ]
