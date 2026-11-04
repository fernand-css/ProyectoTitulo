"""Padrón sintético e historial del control interno de recetas."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from coreapp.models import ModeloAuditado
from coreapp.utils.rut import normalizar_rut


class Paciente(ModeloAuditado):
    rut = models.CharField("RUT", max_length=12, unique=True)
    nombres = models.CharField(max_length=150)
    apellidos = models.CharField(max_length=150)
    fecha_nacimiento = models.DateField()
    es_cronico = models.BooleanField(default=False)
    es_postrado = models.BooleanField(default=False)
    telefono = models.CharField(max_length=30, blank=True)
    direccion = models.CharField(max_length=500, blank=True)

    def clean(self):
        super().clean()
        errores = {}
        try:
            self.rut = normalizar_rut(self.rut)
        except ValidationError:
            errores["rut"] = "Ingresa un RUT válido."
        if self.fecha_nacimiento and self.fecha_nacimiento > timezone.localdate():
            errores["fecha_nacimiento"] = "La fecha de nacimiento no puede ser futura."
        for campo in ("nombres", "apellidos"):
            valor = getattr(self, campo).strip()
            setattr(self, campo, valor)
            if not valor:
                errores[campo] = "Este campo es obligatorio."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.rut = normalizar_rut(self.rut)
        return super().save(*args, **kwargs)

    @property
    def edad(self):
        hoy = timezone.localdate()
        nacimiento = self.fecha_nacimiento
        return hoy.year - nacimiento.year - (
            (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)
        )

    def __str__(self):
        return f"Paciente {self.pk}"


class Receta(ModeloAuditado):
    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="recetas")
    codigo = models.CharField(max_length=64, unique=True)
    fecha_inicio = models.DateField()
    vigencia_meses = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    max_entregas = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    fecha_fin_exclusiva = models.DateField()
    entregas_completadas = models.PositiveIntegerField(default=0, editable=False)
    receta_anterior = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="renovaciones",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(vigencia_meses__gte=1), name="receta_vigencia_positiva"),
            models.CheckConstraint(condition=Q(max_entregas__gte=1), name="receta_maximo_positivo"),
            models.CheckConstraint(
                condition=Q(entregas_completadas__gte=0) & Q(entregas_completadas__lte=F("max_entregas")),
                name="receta_contador_en_cupo",
            ),
            models.CheckConstraint(condition=Q(fecha_fin_exclusiva__gt=F("fecha_inicio")), name="receta_fechas_ordenadas"),
            models.CheckConstraint(condition=~Q(receta_anterior=F("pk")), name="receta_no_autorenovacion"),
        ]

    def clean(self):
        super().clean()
        self.codigo = self.codigo.strip()
        if not self.codigo:
            raise ValidationError({"codigo": "Este campo es obligatorio."})
        if self.receta_anterior_id:
            anterior = type(self).objects.filter(pk=self.receta_anterior_id).first()
            if anterior is None:
                raise ValidationError({"receta_anterior": "La receta anterior no existe."})
            if anterior.paciente_id != self.paciente_id:
                raise ValidationError({"receta_anterior": "La receta anterior debe ser del mismo paciente."})

    def __str__(self):
        return f"Receta {self.pk}"


class EntregaReceta(ModeloAuditado):
    turno_receta = models.OneToOneField(
        "turnosapp.TurnoReceta", null=True, blank=True, on_delete=models.PROTECT, related_name="entrega",
    )
    receta = models.ForeignKey(Receta, on_delete=models.PROTECT, related_name="entregas")
    numero = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    operacion_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(fields=["receta", "numero"], name="entrega_ordinal_unico"),
            models.CheckConstraint(condition=Q(numero__gte=1), name="entrega_numero_positivo"),
        ]

    def __str__(self):
        return f"Entrega de receta {self.pk}"

    def clean(self):
        super().clean()
        if self.turno_receta_id and self.receta_id != self.turno_receta.receta_id:
            raise ValidationError({"turno_receta": "El vínculo no corresponde a esta receta."})


class ImportacionPadron(ModeloAuditado):
    class Formato(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "Excel (.xlsx)"

    class Estado(models.TextChoices):
        PROCESANDO = "procesando", "Procesando"
        COMPLETADA = "completada", "Completada"
        FALLIDA = "fallida", "Fallida"

    referencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    archivo_sha256 = models.CharField(
        max_length=64, validators=[RegexValidator(r"\A[0-9a-f]{64}\Z", "La referencia del archivo no es válida.")],
    )
    formato = models.CharField(max_length=4, choices=Formato.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PROCESANDO)
    total_filas = models.PositiveIntegerField(default=0)
    filas_creadas = models.PositiveIntegerField(default=0)
    filas_actualizadas = models.PositiveIntegerField(default=0)
    filas_sin_cambios = models.PositiveIntegerField(default=0)
    filas_omitidas = models.PositiveIntegerField(default=0)
    filas_rechazadas = models.PositiveIntegerField(default=0)
    pacientes_creados = models.PositiveIntegerField(default=0)
    pacientes_actualizados = models.PositiveIntegerField(default=0)
    recetas_creadas = models.PositiveIntegerField(default=0)
    recetas_actualizadas = models.PositiveIntegerField(default=0)
    resumen_fallo = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-creado_en", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(formato__in=["csv", "xlsx"]), name="carga_formato_valido"),
            models.CheckConstraint(condition=Q(estado__in=["procesando", "completada", "fallida"]), name="carga_estado_valido"),
        ]

    def __str__(self):
        return f"Carga {self.referencia}"


class ResultadoFilaImportacion(ModeloAuditado):
    class Estado(models.TextChoices):
        CREADA = "creada", "Creada"
        ACTUALIZADA = "actualizada", "Actualizada"
        SIN_CAMBIOS = "sin_cambios", "Sin cambios"
        OMITIDA = "omitida", "Omitida"
        RECHAZADA = "rechazada", "Rechazada"

    importacion = models.ForeignKey(ImportacionPadron, on_delete=models.PROTECT, related_name="resultados")
    numero_fila = models.PositiveIntegerField(validators=[MinValueValidator(2)])
    estado = models.CharField(max_length=11, choices=Estado.choices)
    codigo_motivo = models.CharField(max_length=60, blank=True)
    mensaje = models.CharField(max_length=200, blank=True)
    pacientes_creados = models.PositiveSmallIntegerField(default=0)
    pacientes_actualizados = models.PositiveSmallIntegerField(default=0)
    recetas_creadas = models.PositiveSmallIntegerField(default=0)
    recetas_actualizadas = models.PositiveSmallIntegerField(default=0)
    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, null=True, blank=True, related_name="resultados_importacion")
    receta = models.ForeignKey(Receta, on_delete=models.PROTECT, null=True, blank=True, related_name="resultados_importacion")

    class Meta:
        ordering = ["numero_fila"]
        constraints = [
            models.UniqueConstraint(fields=["importacion", "numero_fila"], name="carga_fila_unica"),
            models.CheckConstraint(condition=Q(numero_fila__gte=2), name="carga_fila_datos"),
            models.CheckConstraint(condition=Q(estado__in=["creada", "actualizada", "sin_cambios", "omitida", "rechazada"]), name="fila_estado_valido"),
        ]

    def clean(self):
        super().clean()
        if self.receta_id and self.receta.paciente_id != self.paciente_id:
            raise ValidationError({"receta": "La receta debe corresponder al paciente de la fila."})

    def __str__(self):
        return f"Resultado de carga {self.importacion_id}, fila {self.numero_fila}"


class PreparacionReceta(ModeloAuditado):
    """Recepción y medición de preparación de una receta emitida en un turno."""

    turno_receta = models.OneToOneField(
        "turnosapp.TurnoReceta", on_delete=models.PROTECT, related_name="preparacion",
    )
    recibida_en = models.DateTimeField()
    lista_en = models.DateTimeField(null=True, blank=True)
    lista_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="preparaciones_marcadas",
    )
    inicio_medido = models.DateTimeField(null=True, blank=True)
    duracion_segundos = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(lista_en__isnull=True, lista_por__isnull=True,
                      inicio_medido__isnull=True, duracion_segundos__isnull=True)
                    | Q(lista_en__isnull=False, lista_por__isnull=False,
                        inicio_medido__isnull=False, duracion_segundos__isnull=False)
                ),
                name="preparacion_lista_campos_coherentes",
            ),
            models.CheckConstraint(
                condition=Q(lista_en__isnull=True) | Q(inicio_medido__lte=F("lista_en")),
                name="preparacion_intervalo_ordenado",
            ),
        ]
        indexes = [
            models.Index(fields=["lista_en"], name="preparacion_lista_en_idx"),
            models.Index(fields=["recibida_en"], name="preparacion_recibida_idx"),
        ]

    def __str__(self):
        return f"Preparación de vínculo {self.turno_receta_id}"
