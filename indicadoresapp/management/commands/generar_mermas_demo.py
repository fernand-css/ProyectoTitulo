"""Historial sintético para la demostración del panel de mermas (spec 13).

SOLO PARA LA BASE DE DEMOSTRACIÓN, con el padrón sintético ya importado. Crea, en días anteriores a hoy, turnos
cerrados con una receta preparada que no se entregó en la atención: eso es lo que el panel cuenta como merma.
Una parte se retira después en farmacia con el servicio auditado del 07 (`retirar_preparado`), para que el panel
también muestre recuperadas.

No toca la jornada de hoy (ni su cola ni su contador), no emite por el tótem ni programa entregas, y numera los
turnos de cada día después de los que ya existan. Los turnos históricos se escriben directo en la base, sin
auditoría por turno, porque representan atenciones pasadas de una demostración. Sin `--aplicar` solo informa.
Repetirlo agrega más historial.
"""

import uuid
from datetime import datetime, time, timedelta
from random import Random

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from coreapp.mixins import tiene_rol
from coreapp.roles import JEFA
from recetasapp.models import PreparacionReceta, Receta
from recetasapp.services import retirar_preparado
from turnosapp.models import Turno, TurnoReceta

# Cómo cerró el turno: la mayoría de las recetas no retiradas son de pacientes ausentes.
CIERRES = (("ausente", 45), ("atendido", 25), ("cerrado_sin_entrega", 15), ("sin_atencion_cierre", 15))
EDAD_PREFERENCIAL = 60


def _cierre(azar):
    tirada = azar.randint(1, 100)
    acumulado = 0
    for estado, peso in CIERRES:
        acumulado += peso
        if tirada <= acumulado:
            return estado
    return CIERRES[0][0]


def _fila(receta, fecha):
    """Letra y tipo como los asignaría el tótem: preferencial desde 60 años, crónico o general."""
    paciente = receta.paciente
    if paciente.edad_en(fecha) >= EDAD_PREFERENCIAL:
        return "P", "preferencial"
    if paciente.es_cronico:
        return "C", "cronicos"
    return "G", "general"


class Command(BaseCommand):
    help = ("SOLO PARA LA BASE DE DEMOSTRACIÓN. Crea días anteriores con turnos cerrados y recetas preparadas sin "
            "retirar, para ver el panel de mermas, y retira una parte después en farmacia. Sin --aplicar solo "
            "informa lo que haría. Requiere el padrón sintético importado.")

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Escribe en la base. Sin esta opción, solo simula.")
        parser.add_argument("--cuenta", help="Usuario de una cuenta Q.F. o superusuario activa; marca las preparaciones "
                                             "y registra los retiros tardíos.")
        parser.add_argument("--dias", type=int, default=60, help="Días hacia atrás, sin contar hoy (1 a 366; por defecto 60).")
        parser.add_argument("--por-dia", type=int, default=20,
                            help="Recetas no retiradas por día, en promedio (1 a 200; por defecto 20).")
        parser.add_argument("--recuperadas", type=int, default=15,
                            help="Porcentaje que se retira después en farmacia (0 a 100; por defecto 15).")
        parser.add_argument("--semilla", type=int, default=1313, help="Semilla del azar (resultados reproducibles).")

    def handle(self, *args, **opciones):
        dias, por_dia, recuperadas = opciones["dias"], opciones["por_dia"], opciones["recuperadas"]
        if not 1 <= dias <= 366:
            raise CommandError("--dias debe estar entre 1 y 366.")
        if not 1 <= por_dia <= 200:
            raise CommandError("--por-dia debe estar entre 1 y 200.")
        if not 0 <= recuperadas <= 100:
            raise CommandError("--recuperadas debe estar entre 0 y 100.")
        actor = self.cuenta(opciones["cuenta"], opciones["aplicar"])
        hoy = timezone.localdate()
        recetas = list(Receta.objects.select_related("paciente").filter(
            entregas_completadas__lt=F("max_entregas"), fecha_fin_exclusiva__gt=hoy,
        ).order_by("pk"))
        if not recetas:
            raise CommandError("No hay recetas vigentes. Importa primero el padrón sintético (Pacientes → Importar).")
        if not opciones["aplicar"]:
            self.stdout.write(
                f"Simulación: se crearían cerca de {dias * por_dia} recetas preparadas sin retirar en los últimos {dias} "
                f"días (sin hoy), sobre {len(recetas)} recetas vigentes, y se retiraría después cerca del {recuperadas} %. "
                "La base no fue modificada. Usa --aplicar --cuenta <usuario Q.F.> para crearlas."
            )
            return
        azar = Random(opciones["semilla"])
        zona = timezone.get_current_timezone()
        creadas = []
        for dias_atras in range(dias, 0, -1):
            fecha = hoy - timedelta(days=dias_atras)
            vigentes = [r for r in recetas if r.fecha_inicio <= fecha < r.fecha_fin_exclusiva]
            cantidad = min(len(vigentes), max(0, round(azar.gauss(por_dia, por_dia / 4))))
            if not cantidad:
                continue
            creadas += self.crear_dia(fecha, azar.sample(vigentes, cantidad), azar, zona, actor)
        retiradas = 0
        for preparacion_id in [pk for pk in creadas if azar.randint(1, 100) <= recuperadas]:
            try:
                retirar_preparado(actor, preparacion_id, uuid.uuid4())
                retiradas += 1
            except ValidationError:  # receta agotada o vencida a esa fecha: queda como merma
                continue
        self.stdout.write(self.style.SUCCESS(
            f"Historial sintético creado: {len(creadas)} recetas preparadas en {dias} días; {retiradas} retiradas "
            f"después en farmacia y {len(creadas) - retiradas} sin retirar. Abre «Mermas» con el rango de {dias} días."
        ))

    @transaction.atomic
    def crear_dia(self, fecha, recetas, azar, zona, actor):
        siguientes = {
            letra: (Turno.objects.filter(fecha=fecha, letra=letra).aggregate(m=Max("numero"))["m"] or 0) + 1
            for letra in ("P", "G", "C")
        }
        ids = []
        for receta in recetas:
            letra, tipo = _fila(receta, fecha)
            numero = siguientes[letra]
            siguientes[letra] += 1
            llegada = timezone.make_aware(datetime.combine(fecha, time(8, 0)), zona) + timedelta(minutes=azar.randint(0, 600))
            turno = Turno.objects.create(
                paciente=receta.paciente, rut=receta.paciente.rut, fecha=fecha, letra=letra, numero=numero,
                tipo_atencion=tipo, estado=_cierre(azar), entrada_cola=llegada,
                cerrado_en=llegada + timedelta(minutes=azar.randint(20, 90)),
            )
            lista = llegada + timedelta(minutes=azar.randint(5, 25))
            preparacion = PreparacionReceta.objects.create(
                turno_receta=TurnoReceta.objects.create(turno=turno, receta=receta),
                recibida_en=llegada, lista_en=lista, lista_por=actor, inicio_medido=llegada,
                duracion_segundos=int((lista - llegada).total_seconds()),
            )
            ids.append(preparacion.pk)
        return ids

    def cuenta(self, usuario, aplicar):
        if not usuario:
            if aplicar:
                raise CommandError("Con --aplicar indica --cuenta con el usuario de una cuenta Q.F. o superusuario.")
            return None
        actor = get_user_model().objects.filter(username=usuario).first()
        if actor is None or not tiene_rol(actor, JEFA):
            raise CommandError("La cuenta indicada no existe o no es una cuenta Q.F. o superusuario activa.")
        return actor
