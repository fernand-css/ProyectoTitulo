# Enmienda del spec 04 (2026-11-15), paso 2 de 3: rellena RUT, letra y series por letra.
# No renumera turnos: cada serie (fecha, letra) continúa desde el mayor número ya emitido con esa letra.

from collections import defaultdict

from django.db import migrations
from django.db.models import Case, Max, OuterRef, Subquery, Value, When


LETRA_POR_TIPO = {"general": "G", "preferencial": "P", "cronicos": "C", "urgencia": "U"}


def rellenar(apps, schema_editor):
    Turno = apps.get_model("turnosapp", "Turno")
    Paciente = apps.get_model("recetasapp", "Paciente")
    Contador = apps.get_model("turnosapp", "ContadorTurnosDiario")

    # Antes de la enmienda todo turno tenía paciente; su RUT ya está normalizado en el padrón.
    Turno.objects.filter(rut__isnull=True).update(
        rut=Subquery(Paciente.objects.filter(pk=OuterRef("paciente_id")).values("rut")[:1]),
    )
    Turno.objects.filter(letra__isnull=True).update(letra=Case(
        *(When(tipo_atencion=tipo, then=Value(letra)) for tipo, letra in LETRA_POR_TIPO.items()),
        default=Value("G"),
    ))

    maximos = defaultdict(dict)
    for fila in Turno.objects.values("fecha", "letra").annotate(maximo=Max("numero")).order_by():
        maximos[fila["fecha"]][fila["letra"]] = fila["maximo"]

    # Los contadores anteriores tienen la letra provisional G. Si la fecha tiene turnos,
    # cada letra emitida queda con su propio máximo (el registro existente toma G si hubo G,
    # o la primera letra emitida); si no, se conserva el valor anterior como serie G.
    for contador in Contador.objects.order_by("pk"):
        series = maximos.pop(contador.fecha, None)
        if series is None:
            continue
        contador.letra = "G" if "G" in series else min(series)
        contador.ultimo_numero = series.pop(contador.letra)
        contador.save(update_fields=["letra", "ultimo_numero"])
        for letra, maximo in series.items():
            Contador.objects.update_or_create(
                fecha=contador.fecha, letra=letra, defaults={"ultimo_numero": maximo},
            )
    # Turnos de fechas sin contador (cargados fuera del servicio): se crean sus series.
    for fecha, series in maximos.items():
        for letra, maximo in series.items():
            Contador.objects.update_or_create(fecha=fecha, letra=letra, defaults={"ultimo_numero": maximo})


def revertir(apps, schema_editor):
    """Vuelve a un contador compartido por fecha con el mayor número de sus series."""
    Contador = apps.get_model("turnosapp", "ContadorTurnosDiario")
    for fila in Contador.objects.values("fecha").annotate(maximo=Max("ultimo_numero")).order_by():
        filas = list(Contador.objects.filter(fecha=fila["fecha"]).order_by("pk").values_list("pk", flat=True))
        Contador.objects.filter(pk=filas[0]).update(letra="G", ultimo_numero=fila["maximo"])
        Contador.objects.filter(pk__in=filas[1:]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("recetasapp", "0001_initial"),
        ("turnosapp", "0004_turno_rut_letra"),
    ]

    operations = [
        migrations.RunPython(rellenar, revertir),
    ]
