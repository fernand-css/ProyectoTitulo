"""Datos sintéticos para las pruebas del panel de mermas (spec 13). Ningún dato representa a una persona real."""

import itertools
from datetime import datetime, time, timedelta

from django.utils import timezone

from entregasapp.tests.ayudas import cuenta, equipo, hoy, nacimiento_para, paciente, receta  # noqa: F401
from recetasapp.models import PreparacionReceta
from turnosapp.models import DetalleCierre, Turno, TurnoReceta

_NUMEROS = itertools.count(1)
CIERRES = ("ausente", "sin_atencion_cierre", "atendido", "cerrado_sin_entrega")


def instante(fecha, hora=10):
    return timezone.make_aware(datetime.combine(fecha, time(hora)), timezone.get_current_timezone())


def preparada(persona, *, estado="ausente", dias_atras=0, receta_=None, usuario, lista=True):
    """Turno cerrado (o activo) de hace `dias_atras` días con una receta preparada. Devuelve la preparación."""
    fecha = hoy() - timedelta(days=dias_atras)
    momento = instante(fecha)
    turno = Turno.objects.create(
        paciente=persona, rut=persona.rut, fecha=fecha, letra="G", numero=next(_NUMEROS), tipo_atencion="general",
        estado=estado, entrada_cola=momento, cerrado_en=momento + timedelta(hours=1) if estado in CIERRES else None,
    )
    vinculo = TurnoReceta.objects.create(turno=turno, receta=receta_ or receta(persona))
    return PreparacionReceta.objects.create(
        turno_receta=vinculo, recibida_en=momento,
        lista_en=momento + timedelta(minutes=10) if lista else None,
        lista_por=usuario if lista else None,
        inicio_medido=momento if lista else None,
        duracion_segundos=600 if lista else None,
    )


def entregada_en_la_atencion(preparacion, usuario):
    """Marca la receta como entregada dentro de su atención (con cierre y detalle), sin pasar por los servicios."""
    from recetasapp.models import EntregaReceta
    from turnosapp.models import CierreAtencion, OperacionAtencion
    import uuid

    vinculo = preparacion.turno_receta
    receta_ = vinculo.receta
    entrega = EntregaReceta.objects.create(receta=receta_, numero=receta_.entregas_completadas + 1,
                                           turno_receta=vinculo, creado_por=usuario, modificado_por=usuario)
    operacion = OperacionAtencion.objects.create(id=uuid.uuid4(), actor=usuario, tipo="cierre",
                                                 turno_id=vinculo.turno_id, huella="x" * 64, resultado={})
    cierre = CierreAtencion.objects.create(turno=vinculo.turno, actor=usuario, operacion=operacion, resultado="con_entrega")
    DetalleCierre.objects.create(cierre=cierre, turno_receta=vinculo, entregada=True, entrega=entrega)
    return entrega
