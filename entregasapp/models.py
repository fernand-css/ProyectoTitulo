"""Domicilios del reparto y entregas a domicilio con su historial de intentos (spec 08).

La escritura ocurre solo en `entregasapp.services`, con auditoría y transacciones; el Admin no registra estos
modelos. Las restricciones de la base son la garantía final de las reglas (una entrega abierta por paciente,
un intento pendiente por entrega, tres fotos por domicilio), aunque haya solicitudes simultáneas.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from coreapp.models import ModeloAuditado
from .fotos import almacenamiento_privado


class Sector(models.TextChoices):
    """Sectores MAIS del CESFAM."""
    VERDE = "verde", "Verde"
    AZUL = "azul", "Azul"
    ROJO = "rojo", "Rojo"


class Domicilio(ModeloAuditado):
    """Domicilio de reparto de un paciente. La importación del padrón nunca lo modifica."""

    paciente = models.OneToOneField("recetasapp.Paciente", on_delete=models.PROTECT, related_name="domicilio")
    sector = models.CharField(max_length=5, choices=Sector.choices, blank=True)
    localidad = models.CharField(max_length=120, blank=True)
    direccion = models.CharField("dirección", max_length=500)
    referencias = models.CharField(max_length=500, blank=True)
    latitud = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitud = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    precision_metros = models.PositiveIntegerField("precisión en metros", null=True, blank=True)
    # Dirección del padrón de la que partió o que se revisó por última vez; si el padrón cambia, se avisa.
    direccion_padron = models.CharField(max_length=500, blank=True)
    verificado_en = models.DateTimeField(null=True, blank=True)
    verificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="domicilios_verificados",
    )
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(direccion=""), name="domicilio_direccion_presente"),
            models.CheckConstraint(condition=Q(sector__in=["", "verde", "azul", "rojo"]), name="domicilio_sector_valido"),
            models.CheckConstraint(
                condition=Q(latitud__isnull=True, longitud__isnull=True) | Q(latitud__isnull=False, longitud__isnull=False),
                name="domicilio_coordenadas_juntas",
            ),
            models.CheckConstraint(
                condition=Q(latitud__isnull=True)
                | Q(latitud__gte=-90, latitud__lte=90, longitud__gte=-180, longitud__lte=180),
                name="domicilio_coordenadas_en_rango",
            ),
            models.CheckConstraint(
                condition=Q(precision_metros__isnull=True) | Q(latitud__isnull=False),
                name="domicilio_precision_con_coordenadas",
            ),
            models.CheckConstraint(
                condition=Q(verificado_en__isnull=True, verificado_por__isnull=True)
                | Q(verificado_en__isnull=False, verificado_por__isnull=False),
                name="domicilio_verificacion_completa",
            ),
            models.CheckConstraint(
                condition=Q(verificado_en__isnull=True) | ~Q(sector=""), name="domicilio_verificado_con_sector",
            ),
            models.CheckConstraint(condition=Q(version__gte=1), name="domicilio_version_positiva"),
        ]
        indexes = [models.Index(fields=["sector"], name="domicilio_sector_idx")]

    def __str__(self):
        return f"Domicilio {self.pk}"


class FotoDomicilio(ModeloAuditado):
    """Foto del entorno ya recomprimida a JPEG y sin metadatos; el original no se conserva."""

    MAXIMO = 3

    domicilio = models.ForeignKey(Domicilio, on_delete=models.PROTECT, related_name="fotos")
    posicion = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(MAXIMO)])
    archivo = models.FileField(storage=almacenamiento_privado, upload_to="domicilios/", max_length=200)
    descripcion = models.CharField("descripción", max_length=120)
    ancho = models.PositiveIntegerField()
    alto = models.PositiveIntegerField()
    bytes = models.PositiveIntegerField()

    class Meta:
        ordering = ["posicion"]
        constraints = [
            models.UniqueConstraint(fields=["domicilio", "posicion"], name="foto_posicion_unica"),
            models.CheckConstraint(condition=Q(posicion__gte=1, posicion__lte=3), name="foto_posicion_en_rango"),
            models.CheckConstraint(condition=~Q(descripcion=""), name="foto_descripcion_presente"),
        ]

    def __str__(self):
        return f"Foto de domicilio {self.pk}"


class InscripcionReparto(ModeloAuditado):
    """Excepción de la Q.F.: un paciente que no es postrado ni mayor de 80 entra al reparto."""

    class Motivo(models.TextChoices):
        MOVILIDAD = "movilidad_reducida", "Movilidad reducida"
        DISCAPACIDAD = "discapacidad", "Discapacidad"
        SIN_RED = "sin_red_apoyo", "Sin red de apoyo"
        INDICACION = "indicacion_clinica", "Indicación clínica"
        OTRO = "otro", "Otro"

    paciente = models.ForeignKey("recetasapp.Paciente", on_delete=models.PROTECT, related_name="inscripciones_reparto")
    motivo = models.CharField(max_length=20, choices=Motivo.choices)
    nota = models.CharField(max_length=200, blank=True)
    retirada_en = models.DateTimeField(null=True, blank=True)
    retirada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
    )

    class Meta:
        ordering = ["-creado_en", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["paciente"], condition=Q(retirada_en__isnull=True), name="inscripcion_vigente_unica",
            ),
            models.CheckConstraint(
                condition=Q(motivo__in=["movilidad_reducida", "discapacidad", "sin_red_apoyo", "indicacion_clinica", "otro"]),
                name="inscripcion_motivo_valido",
            ),
            models.CheckConstraint(condition=~Q(motivo="otro") | ~Q(nota=""), name="inscripcion_nota_con_otro"),
            models.CheckConstraint(
                condition=Q(retirada_en__isnull=True, retirada_por__isnull=True)
                | Q(retirada_en__isnull=False, retirada_por__isnull=False),
                name="inscripcion_retiro_completo",
            ),
        ]

    def __str__(self):
        return f"Inscripción de reparto {self.pk}"


class Entrega(ModeloAuditado):
    """Un despacho a domicilio: sus recetas fijadas al programar y sus intentos de visita."""

    class Estado(models.TextChoices):
        PROGRAMADA = "programada", "Programada"
        PENDIENTE_GESTION = "pendiente_gestion", "Pendiente de gestión"
        ENTREGADA = "entregada", "Entregada"
        ANULADA = "anulada", "Anulada"

    class MotivoAnulacion(models.TextChoices):
        RETIRARA = "retirara_farmacia", "Retirará en farmacia"
        SIN_RECETAS = "sin_recetas_vigentes", "Sin recetas vigentes"
        NO_REQUIERE = "no_requiere_despacho", "Ya no requiere despacho"
        OTRO = "otro", "Otro"

    ABIERTAS = ("programada", "pendiente_gestion")
    CERRADAS = ("entregada", "anulada")

    paciente = models.ForeignKey("recetasapp.Paciente", on_delete=models.PROTECT, related_name="despachos")
    estado = models.CharField(max_length=17, choices=Estado.choices, default=Estado.PROGRAMADA)
    operacion_id = models.UUIDField(unique=True, editable=False)
    cerrada_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=20, choices=MotivoAnulacion.choices, blank=True)
    nota_anulacion = models.CharField(max_length=200, blank=True)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
    )

    class Meta:
        ordering = ["-creado_en", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["paciente"], condition=Q(estado__in=["programada", "pendiente_gestion"]),
                name="entrega_abierta_unica",
            ),
            models.CheckConstraint(
                condition=Q(estado__in=["programada", "pendiente_gestion", "entregada", "anulada"]),
                name="entrega_estado_valido",
            ),
            models.CheckConstraint(
                condition=Q(estado__in=["programada", "pendiente_gestion"], cerrada_en__isnull=True)
                | Q(estado__in=["entregada", "anulada"], cerrada_en__isnull=False),
                name="entrega_cierre_coherente",
            ),
            models.CheckConstraint(
                condition=(Q(estado="anulada", anulada_por__isnull=False) & ~Q(motivo_anulacion=""))
                | (~Q(estado="anulada") & Q(motivo_anulacion="", nota_anulacion="", anulada_por__isnull=True)),
                name="entrega_anulacion_coherente",
            ),
            models.CheckConstraint(
                condition=Q(motivo_anulacion__in=["", "retirara_farmacia", "sin_recetas_vigentes", "no_requiere_despacho", "otro"]),
                name="entrega_motivo_anulacion_valido",
            ),
            models.CheckConstraint(
                condition=~Q(motivo_anulacion="otro") | ~Q(nota_anulacion=""), name="entrega_nota_anulacion_con_otro",
            ),
        ]
        indexes = [models.Index(fields=["estado", "paciente"], name="entrega_estado_paciente_idx")]

    @property
    def abierta(self):
        return self.estado in self.ABIERTAS

    def __str__(self):
        return f"Entrega a domicilio {self.pk}"


class RecetaEntrega(ModeloAuditado):
    """Receta fijada a una entrega. Al registrar «entregada» se descuenta o queda «no descontada» con su causa."""

    class Resultado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        DESCONTADA = "descontada", "Descontada"
        NO_DESCONTADA = "no_descontada", "No descontada"

    entrega = models.ForeignKey(Entrega, on_delete=models.PROTECT, related_name="recetas")
    receta = models.ForeignKey("recetasapp.Receta", on_delete=models.PROTECT, related_name="despachos")
    resultado = models.CharField(max_length=13, choices=Resultado.choices, default=Resultado.PENDIENTE)
    entrega_receta = models.OneToOneField(
        "recetasapp.EntregaReceta", null=True, blank=True, on_delete=models.PROTECT, related_name="despacho",
    )
    causa = models.CharField(max_length=200, blank=True)
    revisada_en = models.DateTimeField(null=True, blank=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
    )

    class Meta:
        ordering = ["receta_id"]
        constraints = [
            models.UniqueConstraint(fields=["entrega", "receta"], name="receta_entrega_unica"),
            models.CheckConstraint(
                condition=Q(resultado__in=["pendiente", "descontada", "no_descontada"]), name="receta_entrega_resultado_valido",
            ),
            models.CheckConstraint(
                condition=Q(resultado="descontada", entrega_receta__isnull=False)
                | (~Q(resultado="descontada") & Q(entrega_receta__isnull=True)),
                name="receta_entrega_descuento_coherente",
            ),
            models.CheckConstraint(
                condition=(Q(resultado="no_descontada") & ~Q(causa="")) | (~Q(resultado="no_descontada") & Q(causa="")),
                name="receta_entrega_causa_coherente",
            ),
            models.CheckConstraint(
                condition=Q(revisada_en__isnull=True, revisada_por__isnull=True)
                | Q(resultado="no_descontada", revisada_en__isnull=False, revisada_por__isnull=False),
                name="receta_entrega_revision_coherente",
            ),
        ]

    def __str__(self):
        return f"Receta de entrega a domicilio {self.pk}"


class IntentoEntrega(ModeloAuditado):
    """Visita programada de una entrega. Una vez registrado su resultado, no cambia."""

    class Resultado(models.TextChoices):
        PENDIENTE = "pendiente", "Programado, sin resultado"
        ENTREGADA = "entregada", "Entregada"
        NO_ENTREGADA = "no_entregada", "No entregada"
        REASIGNADO = "reasignado", "Reasignado"
        ANULADO = "anulado", "Anulado"

    class Motivo(models.TextChoices):
        SIN_RECEPTOR = "sin_receptor", "No había nadie para recibir"
        NO_ENCONTRADO = "domicilio_no_encontrado", "Domicilio no encontrado"
        CAMINO = "camino_intransitable", "Camino intransitable"
        RECHAZO = "rechazo", "Paciente o cuidador rechaza la entrega"
        AUSENTE = "paciente_ausente", "Paciente no se encuentra en el domicilio"
        OTRO = "otro", "Otro"

    entrega = models.ForeignKey(Entrega, on_delete=models.PROTECT, related_name="intentos")
    numero = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    fecha_programada = models.DateField()
    encargado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="intentos_entrega")
    resultado = models.CharField(max_length=12, choices=Resultado.choices, default=Resultado.PENDIENTE)
    motivo = models.CharField(max_length=23, choices=Motivo.choices, blank=True)
    nota = models.CharField(max_length=200, blank=True)
    registrado_en = models.DateTimeField(null=True, blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
    )
    # Identificador del registro del resultado (idempotencia; la reserva 11 lo generará en el cliente).
    operacion_id = models.UUIDField(unique=True, null=True, blank=True)
    # Operación que creó el intento: la programación (intento 1) o una reasignación. Hace idempotente el reenvío.
    creado_con = models.UUIDField(unique=True, null=True, blank=True)

    class Meta:
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(fields=["entrega", "numero"], name="intento_numero_unico"),
            models.UniqueConstraint(
                fields=["entrega"], condition=Q(resultado="pendiente"), name="intento_pendiente_unico",
            ),
            models.CheckConstraint(condition=Q(numero__gte=1), name="intento_numero_positivo"),
            models.CheckConstraint(
                condition=Q(resultado__in=["pendiente", "entregada", "no_entregada", "reasignado", "anulado"]),
                name="intento_resultado_valido",
            ),
            models.CheckConstraint(
                condition=Q(motivo__in=[
                    "", "sin_receptor", "domicilio_no_encontrado", "camino_intransitable", "rechazo",
                    "paciente_ausente", "otro",
                ]),
                name="intento_motivo_valido",
            ),
            models.CheckConstraint(
                condition=(Q(resultado="no_entregada") & ~Q(motivo="")) | (~Q(resultado="no_entregada") & Q(motivo="")),
                name="intento_motivo_coherente",
            ),
            models.CheckConstraint(condition=Q(resultado="no_entregada") | Q(nota=""), name="intento_nota_solo_no_entregada"),
            models.CheckConstraint(condition=~Q(motivo="otro") | ~Q(nota=""), name="intento_nota_con_otro"),
            models.CheckConstraint(
                condition=Q(resultado="pendiente", registrado_en__isnull=True, registrado_por__isnull=True, operacion_id__isnull=True)
                | (~Q(resultado="pendiente") & Q(registrado_en__isnull=False, registrado_por__isnull=False, operacion_id__isnull=False)),
                name="intento_registro_coherente",
            ),
        ]
        indexes = [
            models.Index(fields=["encargado", "resultado", "fecha_programada"], name="intento_encargado_idx"),
            models.Index(fields=["resultado", "fecha_programada"], name="intento_resultado_fecha_idx"),
        ]

    def __str__(self):
        return f"Intento {self.numero} de entrega {self.entrega_id}"
