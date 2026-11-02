from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Perfil",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("correo_verificado_en", models.DateTimeField(blank=True, null=True)),
                ("correo_pendiente", models.EmailField(blank=True, max_length=254)),
                ("solicitud_correo", models.UUIDField(blank=True, null=True)),
                ("usuario", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="perfil", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
