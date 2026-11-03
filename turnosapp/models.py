"""Persistencia de llegadas y numeración diaria, sin dispensación de recetas."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from coreapp.models import ModeloAuditado


class ContadorTurnosDiario(models.Model):
    fecha = models.DateField(unique=True)
    ultimo_numero = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ultimo_numero__gte=0), name="turnos_contador_no_negativo",
            ),
        ]

    def __str__(self):
        return f"Contador de turnos {self.fecha}"


class Turno(ModeloAuditado):
    class TipoAtencion(models.TextChoices):
        GENERAL = "general", "General"
        PREFERENCIAL = "preferencial", "Preferencial"
        CRONICOS = "cronicos", "Crónicos"

    class Estado(models.TextChoices):
        ESPERANDO = "esperando", "Esperando"
        LLAMADO = "llamado", "Llamado"
        ATENDIDO = "atendido", "Atendido"
        AUSENTE = "ausente", "Ausente"
        CERRADO_SIN_ENTREGA = "cerrado_sin_entrega", "Cerrado sin entrega"
        SIN_ATENCION_CIERRE = "sin_atencion_cierre", "Sin atención al cierre"

    paciente = models.ForeignKey(
        "recetasapp.Paciente", on_delete=models.PROTECT, related_name="turnos",
    )
    fecha = models.DateField()
    numero = models.PositiveIntegerField()
    tipo_atencion = models.CharField(max_length=12, choices=TipoAtencion.choices)
    estado = models.CharField(max_length=24, choices=Estado.choices, default=Estado.ESPERANDO)
    operacion_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    entrada_cola = models.DateTimeField(default=timezone.now)
    ventanilla = models.ForeignKey("Ventanilla", null=True, blank=True, on_delete=models.PROTECT, related_name="turnos")
    operador = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="turnos_operados")
    ultimo_llamado = models.DateTimeField(null=True, blank=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["fecha", "numero"], name="turno_numero_diario_unico"),
            models.UniqueConstraint(
                fields=["paciente", "fecha"], condition=Q(estado__in=["esperando", "llamado"]),
                name="turno_activo_paciente_dia_unico",
            ),
            models.CheckConstraint(condition=Q(numero__gte=1), name="turno_numero_positivo"),
            models.CheckConstraint(
                condition=Q(tipo_atencion__in=["general", "preferencial", "cronicos"]),
                name="turno_tipo_valido",
            ),
            models.CheckConstraint(condition=Q(estado__in=["esperando", "llamado", "atendido", "ausente", "cerrado_sin_entrega", "sin_atencion_cierre"]), name="turno_estado_valido"),
            models.UniqueConstraint(fields=["ventanilla"], condition=Q(estado="llamado"), name="turno_llamado_ventanilla_unico"),
            models.UniqueConstraint(fields=["paciente"], condition=Q(estado="llamado"), name="turno_llamado_paciente_unico"),
            models.CheckConstraint(condition=(
                Q(estado="llamado", ventanilla__isnull=False, operador__isnull=False, ultimo_llamado__isnull=False)
                | (~Q(estado="llamado") & Q(ventanilla__isnull=True, operador__isnull=True))
            ), name="turno_asignacion_coherente"),
            models.CheckConstraint(condition=(
                Q(estado__in=["esperando", "llamado"], cerrado_en__isnull=True)
                | Q(estado__in=["atendido", "ausente", "cerrado_sin_entrega", "sin_atencion_cierre"], cerrado_en__isnull=False)
            ), name="turno_cierre_coherente"),
        ]
        indexes = [
            models.Index(fields=["fecha", "estado", "tipo_atencion"], name="turno_fecha_estado_tipo_idx"),
        ]

    def __str__(self):
        return f"Turno {self.fecha} / {self.numero}"


class TurnoReceta(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="recetas_vinculadas")
    receta = models.ForeignKey(
        "recetasapp.Receta", on_delete=models.PROTECT, related_name="turnos_vinculados",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["turno", "receta"], name="turno_receta_unica"),
        ]

    def clean(self):
        super().clean()
        if self.turno_id and self.receta_id:
            # La misma comprobación debe hacerse dentro del servicio de emisión.
            if self.turno.paciente_id != self.receta.paciente_id:
                raise ValidationError({"receta": "La receta debe pertenecer al paciente del turno."})

    def __str__(self):
        return f"Vínculo de turno {self.turno_id} / receta {self.receta_id}"


class TipoAtencionVentanilla(models.Model):
    codigo = models.CharField(max_length=12, primary_key=True, choices=Turno.TipoAtencion.choices)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(codigo__in=["general", "preferencial", "cronicos"]), name="ventanilla_tipo_valido")]

    def __str__(self):
        return self.get_codigo_display()


class Ventanilla(ModeloAuditado):
    numero = models.PositiveIntegerField(unique=True)
    habilitada = models.BooleanField(default=True)
    retirada = models.BooleanField(default=False)
    tipos = models.ManyToManyField(TipoAtencionVentanilla, related_name="ventanillas")
    operador = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="ventanilla_actual")
    automatico = models.BooleanField(default=False)
    fecha_activacion = models.DateField(null=True, blank=True)
    disponible_desde = models.DateTimeField(default=timezone.now)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(numero__gte=1), name="ventanilla_numero_positivo"),
            models.CheckConstraint(condition=~Q(retirada=True, habilitada=True), name="ventanilla_retiro_coherente"),
            models.CheckConstraint(condition=Q(automatico=False) | Q(habilitada=True, retirada=False, operador__isnull=False, fecha_activacion__isnull=False), name="ventanilla_automatico_coherente"),
        ]

    def __str__(self):
        return f"Ventanilla {self.numero}"


class OcupacionVentanilla(models.Model):
    ventanilla = models.ForeignKey(Ventanilla, on_delete=models.PROTECT, related_name="ocupaciones")
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ocupaciones_ventanilla")
    apertura = models.DateTimeField(default=timezone.now)
    cierre = models.DateTimeField(null=True, blank=True)
    motivo = models.CharField(max_length=60, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ventanilla"], condition=Q(cierre__isnull=True), name="ocupacion_vigente_vent_unica"),
            models.UniqueConstraint(fields=["tecnico"], condition=Q(cierre__isnull=True), name="ocupacion_vigente_tecnico_unica"),
            models.CheckConstraint(condition=Q(cierre__isnull=True) | Q(cierre__gte=models.F("apertura")), name="ocupacion_fechas_ordenadas"),
        ]


class ConfiguracionCola(ModeloAuditado):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    peso_preferencial = models.PositiveIntegerField(default=2)
    peso_cronicos = models.PositiveIntegerField(default=1)
    peso_general = models.PositiveIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(pk=1), name="cola_config_fila_unica"),
            models.CheckConstraint(condition=Q(peso_preferencial__gte=1, peso_cronicos__gte=1, peso_general__gte=1), name="cola_pesos_positivos"),
        ]


class EstadoColaDiaria(models.Model):
    fecha = models.DateField(unique=True)
    cursor = models.PositiveIntegerField(default=0)
    version_configuracion = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=0)


class OperacionAtencion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="operaciones_atencion")
    tipo = models.CharField(max_length=32)
    turno = models.ForeignKey(Turno, null=True, blank=True, on_delete=models.PROTECT, related_name="operaciones")
    ventanilla = models.ForeignKey(Ventanilla, null=True, blank=True, on_delete=models.PROTECT, related_name="operaciones")
    huella = models.CharField(max_length=64)
    resultado = models.JSONField(default=dict)
    creado_en = models.DateTimeField(auto_now_add=True)


class EventoTurno(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="eventos")
    secuencia = models.PositiveIntegerField()
    accion = models.CharField(max_length=32)
    instante = models.DateTimeField(default=timezone.now)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="eventos_turno")
    ventanilla = models.ForeignKey(Ventanilla, null=True, blank=True, on_delete=models.PROTECT, related_name="eventos")
    operacion = models.ForeignKey(OperacionAtencion, null=True, blank=True, on_delete=models.PROTECT, related_name="eventos")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["turno", "secuencia"], name="evento_secuencia_turno_unica"),
            models.CheckConstraint(condition=Q(secuencia__gte=1), name="evento_secuencia_positiva"),
        ]


class CierreAtencion(models.Model):
    turno = models.OneToOneField(Turno, on_delete=models.PROTECT, related_name="cierre_atencion")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cierres_atencion")
    operacion = models.OneToOneField(OperacionAtencion, on_delete=models.PROTECT, related_name="cierre")
    instante = models.DateTimeField(default=timezone.now)
    resultado = models.CharField(max_length=12, choices=[("con_entrega", "Con entrega"), ("sin_entrega", "Sin entrega")])
    motivo = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(resultado__in=["con_entrega", "sin_entrega"]), name="cierre_resultado_valido"),
            models.CheckConstraint(condition=~Q(resultado="sin_entrega") | ~Q(motivo=""), name="cierre_sin_entrega_motivo"),
        ]


class DetalleCierre(models.Model):
    cierre = models.ForeignKey(CierreAtencion, on_delete=models.PROTECT, related_name="detalles")
    turno_receta = models.OneToOneField(TurnoReceta, on_delete=models.PROTECT, related_name="detalle_cierre")
    entregada = models.BooleanField(default=False)
    motivo = models.CharField(max_length=500, blank=True)
    entrega = models.OneToOneField("recetasapp.EntregaReceta", null=True, blank=True, on_delete=models.PROTECT, related_name="detalle_cierre")

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            Q(entregada=True, entrega__isnull=False) | (Q(entregada=False, entrega__isnull=True) & ~Q(motivo=""))
        ), name="detalle_cierre_entrega_coherente")]

    def clean(self):
        super().clean()
        if self.cierre_id and self.turno_receta_id and self.cierre.turno_id != self.turno_receta.turno_id:
            raise ValidationError({"turno_receta": "La receta no corresponde al turno del cierre."})
        if self.entrega_id and self.turno_receta_id and self.entrega.receta_id != self.turno_receta.receta_id:
            raise ValidationError({"entrega": "La entrega no corresponde a la receta del turno."})
        if self.entrega_id and self.turno_receta_id and self.entrega.turno_receta_id != self.turno_receta_id:
            raise ValidationError({"entrega": "La entrega no está asociada a esta atención."})


class PendienteSeleccion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fecha = models.DateField(default=timezone.localdate)
    estado = models.CharField(max_length=12, default="pendiente", choices=[("pendiente", "Pendiente"), ("procesado", "Procesado")])
    motivo = models.CharField(max_length=48)
    intentos = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)
    ultimo_intento = models.DateTimeField(null=True, blank=True)
    procesado_en = models.DateTimeField(null=True, blank=True)
    codigo_fallo = models.CharField(max_length=48, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            Q(estado="pendiente", procesado_en__isnull=True) | Q(estado="procesado", procesado_en__isnull=False)
        ), name="pendiente_estado_coherente")]
        indexes = [models.Index(fields=["estado", "fecha"], name="pendiente_estado_fecha_idx")]
