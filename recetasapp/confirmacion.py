"""Contexto firmado del formulario para no convertir una pantalla vieja en otra entrega."""
from django.core import signing
from django.core.exceptions import ValidationError
from turnosapp.models import TurnoReceta

SALT = "recetas.entrega.contexto"


def preparar_contexto(actor, receta, operacion_id):
    vinculo = TurnoReceta.objects.filter(receta=receta, turno__estado="llamado").first()
    return signing.dumps({"actor": actor.pk, "receta": receta.pk, "operacion": str(operacion_id),
        "turno_receta": vinculo.pk if vinculo else None, "contador": receta.entregas_completadas}, salt=SALT)


def leer_contexto(actor, receta, operacion_id, contexto):
    if not contexto:
        if TurnoReceta.objects.filter(receta=receta, turno__estado="llamado").exists():
            raise ValidationError("Abre nuevamente la confirmación para revisar la atención vigente.")
        return {}  # Compatibilidad de los clientes anteriores cuando no hay atención llamada.
    try:
        datos = signing.loads(contexto, salt=SALT)
        if (datos["actor"], datos["receta"], datos["operacion"]) != (actor.pk, receta.pk, str(operacion_id)):
            raise ValueError
        return {"turno_receta_id": datos["turno_receta"], "contador_esperado": datos["contador"]}
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise ValidationError("La confirmación cambió. Abre nuevamente el formulario.") from None
