"""Persistencia técnica del tótem; las mutaciones corresponden a sus servicios."""
import uuid
from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class EstadoActivacion(models.TextChoices):
    SIN_CODIGO = "SIN_CODIGO", "Sin código"
    PENDIENTE = "PENDIENTE", "Pendiente"
    UTILIZADO = "UTILIZADO", "Utilizado"
    CADUCADO = "CADUCADO", "Caducado"
    INVALIDADO = "INVALIDADO", "Invalidado"


class DispositivoTotem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alias = models.SlugField(max_length=64, unique=True)
    activo = models.BooleanField(default=False)
    version_credencial = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    # Solo se conserva el último código. La referencia es un ID de correlación,
    # no el código ni una credencial. Los terminales conservan referencia/fechas,
    # pero eliminan el hash. Los servicios auditan la historia en OperacionTurno.
    estado_activacion = models.CharField(
        max_length=12, choices=EstadoActivacion.choices, default=EstadoActivacion.SIN_CODIGO,
    )
    referencia_activacion = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    hash_activacion = models.CharField(max_length=256, blank=True, default="", editable=False)
    activacion_emitida_en = models.DateTimeField(null=True, blank=True)
    activacion_expira_en = models.DateTimeField(null=True, blank=True)
    activacion_cerrada_en = models.DateTimeField(null=True, blank=True)
    intentos_fallidos = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(5)],
    )

    # Capacidad y consumo persistidos; no se reservan cupos en este modelo.
    limite_minuto = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1)])
    limite_hora = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1)])
    ventana_minuto = models.DateTimeField(null=True, blank=True)
    ventana_hora = models.DateTimeField(null=True, blank=True)
    solicitudes_minuto = models.PositiveIntegerField(default=0)
    solicitudes_hora = models.PositiveIntegerField(default=0)

    creado_en = models.DateTimeField(default=timezone.now, editable=False)
    actualizado_en = models.DateTimeField(auto_now=True)
    activado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("alias",)
        # Permisos humanos explícitos; no conceden operaciones a dispositivos.
        default_permissions = ()
        permissions = [
            ("consultar_dispositivos", "Puede consultar dispositivos de tótem"),
            ("generar_codigos_activacion", "Puede generar códigos de activación"),
            ("revocar_dispositivos", "Puede revocar dispositivos de tótem"),
            ("caducar_codigos_activacion", "Puede caducar códigos de activación"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(alias__regex=r"^[a-zA-Z0-9_-]+$"), name="totem_alias_tecnico"),
            models.CheckConstraint(condition=Q(version_credencial__gte=1), name="totem_version_positiva"),
            models.CheckConstraint(condition=Q(intentos_fallidos__gte=0, intentos_fallidos__lte=5), name="totem_intentos_validos"),
            models.CheckConstraint(condition=Q(limite_minuto__gte=1, limite_hora__gte=1), name="totem_limites_positivos"),
            models.CheckConstraint(
                condition=Q(solicitudes_minuto__gte=0, solicitudes_hora__gte=0)
                & Q(solicitudes_minuto__lte=F("limite_minuto"))
                & Q(solicitudes_hora__lte=F("limite_hora"))
                & Q(solicitudes_minuto__lte=F("solicitudes_hora")),
                name="totem_consumos_validos",
            ),
            models.CheckConstraint(
                condition=Q(ventana_minuto__isnull=True, ventana_hora__isnull=True,
                            solicitudes_minuto=0, solicitudes_hora=0)
                | Q(ventana_minuto__isnull=False, ventana_hora__isnull=False),
                name="totem_ventanas_presentes",
            ),
            models.CheckConstraint(
                condition=Q(ventana_minuto__isnull=True)
                | (Q(ventana_minuto__gte=F("ventana_hora"))
                   & Q(ventana_minuto__lt=F("ventana_hora") + timedelta(hours=1))),
                name="totem_ventanas_coherentes",
            ),
            models.CheckConstraint(
                condition=Q(activo=False) | Q(activado_en__isnull=False),
                name="totem_activo_con_fecha",
            ),
            models.CheckConstraint(
                condition=Q(actualizado_en__gte=F("creado_en"))
                & (Q(activado_en__isnull=True) | Q(activado_en__gte=F("creado_en")))
                & (Q(activado_en__isnull=True) | Q(activado_en__lte=F("actualizado_en")))
                & (Q(activacion_emitida_en__isnull=True) | Q(activacion_emitida_en__gte=F("creado_en")))
                & (Q(activacion_emitida_en__isnull=True) | Q(activacion_emitida_en__lte=F("actualizado_en")))
                & (Q(activacion_cerrada_en__isnull=True) | Q(activacion_cerrada_en__lte=F("actualizado_en"))),
                name="totem_fechas_tecnicas",
            ),
            models.CheckConstraint(
                condition=Q(estado_activacion=EstadoActivacion.SIN_CODIGO,
                            referencia_activacion__isnull=True, hash_activacion="",
                            activacion_emitida_en__isnull=True, activacion_expira_en__isnull=True,
                            activacion_cerrada_en__isnull=True, intentos_fallidos=0)
                | (Q(referencia_activacion__isnull=False, activacion_emitida_en__isnull=False,
                     activacion_expira_en__isnull=False)
                   & ((Q(estado_activacion=EstadoActivacion.PENDIENTE,
                         activacion_cerrada_en__isnull=True, intentos_fallidos__lt=5)
                       & ~Q(hash_activacion=""))
                      | Q(estado_activacion=EstadoActivacion.UTILIZADO,
                          hash_activacion="", activacion_cerrada_en__isnull=False,
                          activado_en__isnull=False, intentos_fallidos__lt=5)
                      | Q(estado_activacion=EstadoActivacion.CADUCADO,
                          hash_activacion="", activacion_cerrada_en__isnull=False, intentos_fallidos__lt=5)
                      | Q(estado_activacion=EstadoActivacion.INVALIDADO,
                          hash_activacion="", activacion_cerrada_en__isnull=False))),
                name="totem_codigo_estructura",
            ),
            models.CheckConstraint(
                condition=(Q(activacion_expira_en__isnull=True)
                           | Q(activacion_expira_en__gt=F("activacion_emitida_en")))
                & (Q(activacion_cerrada_en__isnull=True)
                   | Q(activacion_cerrada_en__gte=F("activacion_emitida_en"))),
                name="totem_codigo_orden",
            ),
            models.CheckConstraint(
                condition=~Q(estado_activacion=EstadoActivacion.CADUCADO)
                | Q(activacion_cerrada_en__gte=F("activacion_expira_en")),
                name="totem_codigo_caducado",
            ),
            models.CheckConstraint(
                condition=~Q(estado_activacion=EstadoActivacion.UTILIZADO)
                | (Q(activacion_cerrada_en__lt=F("activacion_expira_en"))
                   & Q(activado_en__gte=F("activacion_cerrada_en"))),
                name="totem_codigo_usado_vigente",
            ),
        ]

    @property
    def estado_activacion_actual(self):
        """Caducidad efectiva sin escrituras ni tareas automáticas.

        Un PENDIENTE vencido se considera CADUCADO inmediatamente. Un servicio
        puede materializarlo, borrar el hash y registrar su cierre.
        Los estados terminales no cambian por el mero paso del tiempo.
        """
        if (
            self.estado_activacion == EstadoActivacion.PENDIENTE
            and self.activacion_expira_en is not None
            and timezone.now() >= self.activacion_expira_en
        ):
            return EstadoActivacion.CADUCADO
        return self.estado_activacion

    def __str__(self):
        return self.alias
