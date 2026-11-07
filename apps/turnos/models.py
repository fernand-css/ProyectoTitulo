from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .dominio import ACTIVOS, GENERAL, OCUPAN_VENTANILLA, numero_visible


def fecha_local():
    return timezone.localdate()


class Categoria(models.TextChoices):
    GENERAL = "GENERAL", "General"
    PREFERENCIAL = "PREFERENCIAL", "Preferencial"


class Estado(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    LLAMADO = "LLAMADO", "Llamado"
    EN_ATENCION = "EN_ATENCION", "En atención"
    ATENDIDO = "ATENDIDO", "Atendido"
    AUSENTE = "AUSENTE", "Ausente"
    CANCELADO = "CANCELADO", "Cancelado"


class Ventanilla(models.Model):
    numero = models.PositiveSmallIntegerField(unique=True, validators=[MinValueValidator(1)])
    habilitada = models.BooleanField(default=True)
    operador = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True, blank=True, on_delete=models.PROTECT,
        related_name="ventanilla_asignada",
    )

    class Meta:
        ordering = ("numero",)
        constraints = [models.CheckConstraint(condition=Q(numero__gte=1), name="ventanilla_numero_positivo")]
        permissions = [("configurar_ventanillas", "Puede configurar las ventanillas")]

    def __str__(self):
        return f"Ventanilla {self.numero}"


def condicion_estado_fechas():
    """Coherencia de una fila, adicional a la máquina de estados del servicio."""
    estados = (
        (Estado.PENDIENTE, False, False, False, False),
        (Estado.CANCELADO, False, False, False, True),
        (Estado.LLAMADO, True, True, False, False),
        (Estado.EN_ATENCION, True, True, True, False),
        (Estado.ATENDIDO, True, True, True, True),
        (Estado.AUSENTE, True, True, False, True),
    )
    resultado = Q(pk__isnull=True)  # Ninguna fila persistida satisface esta rama.
    for estado, asignado, llamado, iniciado, cerrado in estados:
        resultado |= Q(
            estado=estado,
            ventanilla__isnull=not asignado,
            operador__isnull=not asignado,
            primer_llamado__isnull=not llamado,
            ultimo_llamado__isnull=not llamado,
            inicio_atencion__isnull=not iniciado,
            cierre__isnull=not cerrado,
        )
    return resultado


class Turno(models.Model):
    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.PROTECT, related_name="turnos")
    fecha_jornada = models.DateField(default=fecha_local)
    categoria = models.CharField(max_length=12, choices=Categoria.choices)
    correlativo = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    ventanilla = models.ForeignKey(
        Ventanilla, null=True, blank=True, on_delete=models.PROTECT, related_name="turnos",
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name="turnos_atendidos",
    )
    emitido = models.DateTimeField(default=timezone.now)
    primer_llamado = models.DateTimeField(null=True, blank=True)
    ultimo_llamado = models.DateTimeField(null=True, blank=True)
    inicio_atencion = models.DateTimeField(null=True, blank=True)
    cierre = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        ordering = ("emitido", "id")
        indexes = [models.Index(fields=["fecha_jornada", "estado", "categoria", "emitido", "id"], name="turno_cola_idx")]
        permissions = [
            ("operar_turnos", "Puede llamar y atender turnos"),
            ("cancelar_turnos", "Puede cancelar turnos pendientes"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["fecha_jornada", "categoria", "correlativo"], name="turno_numero_por_jornada"),
            models.UniqueConstraint(fields=["paciente"], condition=Q(estado__in=ACTIVOS), name="turno_un_activo_paciente"),
            models.UniqueConstraint(fields=["ventanilla"], condition=Q(estado__in=OCUPAN_VENTANILLA), name="turno_un_ocupante_ventanilla"),
            models.CheckConstraint(condition=Q(categoria__in=Categoria.values), name="turno_categoria_valida"),
            models.CheckConstraint(condition=Q(correlativo__gte=1), name="turno_correlativo_positivo"),
            models.CheckConstraint(condition=Q(version__gte=1), name="turno_version_positiva"),
            models.CheckConstraint(condition=condicion_estado_fechas(), name="turno_estado_asignacion_fechas"),
            models.CheckConstraint(condition=Q(primer_llamado__isnull=True) | Q(primer_llamado__gte=F("emitido")), name="turno_llamado_posterior"),
            models.CheckConstraint(condition=Q(ultimo_llamado__isnull=True) | Q(ultimo_llamado__gte=F("primer_llamado")), name="turno_rellamado_posterior"),
            models.CheckConstraint(condition=Q(inicio_atencion__isnull=True) | Q(inicio_atencion__gte=F("ultimo_llamado")), name="turno_inicio_posterior"),
            models.CheckConstraint(condition=Q(cierre__isnull=True) | Q(cierre__gte=F("emitido")), name="turno_cierre_posterior_emision"),
            models.CheckConstraint(condition=Q(cierre__isnull=True) | Q(inicio_atencion__isnull=True) | Q(cierre__gte=F("inicio_atencion")), name="turno_cierre_posterior_inicio"),
            models.CheckConstraint(condition=Q(cierre__isnull=True) | Q(ultimo_llamado__isnull=True) | Q(cierre__gte=F("ultimo_llamado")), name="turno_cierre_posterior_llamado"),
        ]

    @property
    def numero_visible(self):
        return numero_visible(self.categoria, self.correlativo)

    def __str__(self):
        return f"{self.fecha_jornada} / {self.numero_visible}"


class EstadoCola(models.Model):
    """Fila única de coordinación. Se bloquea antes de cualquier mutación de turnos."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    fecha_jornada = models.DateField(default=fecha_local)
    peso_general = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(100)])
    peso_preferencial = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
    siguiente_categoria = models.CharField(max_length=12, choices=Categoria.choices, default=GENERAL)
    consumidos = models.PositiveSmallIntegerField(default=0)

    class Meta:
        permissions = [("configurar_cola", "Puede configurar los pesos de la cola")]
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="cola_fila_unica"),
            models.CheckConstraint(condition=Q(peso_general__gte=1, peso_general__lte=100, peso_preferencial__gte=1, peso_preferencial__lte=100), name="cola_pesos_validos"),
            models.CheckConstraint(condition=(Q(siguiente_categoria=Categoria.GENERAL, consumidos__lt=F("peso_general")) | Q(siguiente_categoria=Categoria.PREFERENCIAL, consumidos__lt=F("peso_preferencial"))), name="cola_cupo_valido"),
        ]


class ContadorTurno(models.Model):
    """Correlativo independiente por categoría y jornada; siempre bajo el bloqueo de cola."""
    fecha_jornada = models.DateField()
    categoria = models.CharField(max_length=12, choices=Categoria.choices)
    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["fecha_jornada", "categoria"], name="contador_jornada_categoria"),
            models.CheckConstraint(condition=Q(categoria__in=Categoria.values), name="contador_categoria_valida"),
        ]


class OperacionTurno(models.Model):
    """Bitácora persistente; nunca se almacena exclusivamente en Redis."""
    turno = models.ForeignKey(Turno, null=True, blank=True, on_delete=models.PROTECT, related_name="operaciones")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    accion = models.CharField(max_length=30)
    momento = models.DateTimeField(default=timezone.now)
    detalles = models.JSONField(default=dict)

    class Meta:
        ordering = ("id",)
