import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("entregasapp", "0003_recetaentrega_preparacion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="intentoentrega",
            name="traslado_iniciado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="intentoentrega",
            name="traslado_iniciado_por",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="+", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="intentoentrega",
            constraint=models.CheckConstraint(
                condition=models.Q(traslado_iniciado_en__isnull=True, traslado_iniciado_por__isnull=True)
                | models.Q(traslado_iniciado_en__isnull=False, traslado_iniciado_por__isnull=False),
                name="intento_traslado_inicio_completo",
            ),
        ),
        migrations.CreateModel(
            name="AvisoReparto",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tipo", models.CharField(choices=[("delivery.departed", "Reparto en camino")], max_length=20)),
                ("estado", models.CharField(choices=[
                    ("pendiente", "Pendiente"), ("reservado", "Reservado"), ("en_envio", "En envío"),
                    ("simulado", "Simulado"), ("aceptado_smtp", "Aceptado por SMTP"),
                    ("omitido", "Omitido"), ("obsoleto", "Obsoleto"),
                    ("fallido", "Fallido"), ("incierto", "Incierto"),
                ], max_length=16)),
                ("creado_en", models.DateTimeField()),
                ("vence_en", models.DateTimeField()),
                ("proximo_en", models.DateTimeField()),
                ("firma_destino", models.CharField(blank=True, max_length=64)),
                ("intentos_envio", models.PositiveSmallIntegerField(default=0)),
                ("reserva", models.UUIDField(blank=True, null=True)),
                ("reserva_hasta", models.DateTimeField(blank=True, null=True)),
                ("aceptado_en", models.DateTimeField(blank=True, null=True)),
                ("codigo_resultado", models.CharField(blank=True, max_length=32)),
                ("intento", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="avisos", to="entregasapp.intentoentrega",
                )),
            ],
            options={
                "constraints": [models.UniqueConstraint(
                    fields=("intento", "tipo"), name="aviso_reparto_intento_tipo_unico",
                )],
                "indexes": [models.Index(fields=["estado", "proximo_en"], name="aviso_reparto_estado_proximo")],
            },
        ),
    ]
