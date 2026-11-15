# Enmienda del spec 05 (2026-11-15, RF-05-13), paso 2 de 2: las ventanillas existentes
# reciben U, como las cuatro iniciales que crea preparar_ventanillas.

from django.db import migrations


def agregar_urgencia(apps, schema_editor):
    Tipo = apps.get_model("turnosapp", "TipoAtencionVentanilla")
    Ventanilla = apps.get_model("turnosapp", "Ventanilla")
    if not Ventanilla.objects.exists():
        return  # Base sin preparar: preparar_ventanillas crea los cuatro tipos.
    urgencia, _ = Tipo.objects.get_or_create(codigo="urgencia")
    for ventanilla in Ventanilla.objects.order_by("pk"):
        ventanilla.tipos.add(urgencia)


def quitar_urgencia(apps, schema_editor):
    """Solo quita el tipo; la historia de turnos U y sus eventos se conserva."""
    Tipo = apps.get_model("turnosapp", "TipoAtencionVentanilla")
    Ventanilla = apps.get_model("turnosapp", "Ventanilla")
    Ventanilla.tipos.through.objects.filter(tipoatencionventanilla_id="urgencia").delete()
    Tipo.objects.filter(codigo="urgencia").delete()



class Migration(migrations.Migration):

    dependencies = [
        ("turnosapp", "0008_ventanilla_urgencia"),
    ]

    operations = [
        migrations.RunPython(agregar_urgencia, quitar_urgencia),
    ]
