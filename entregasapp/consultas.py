"""Consultas de solo lectura del reparto a domicilio: elegibilidad, estado del domicilio y listas de trabajo.

Nada aquí escribe en la base. Las escrituras viven en `entregasapp.services`.
"""

from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Count, Exists, F, Max, OuterRef, Prefetch, Q, Subquery
from django.utils import timezone

from coreapp.roles import ENCARGADO
from coreapp.utils.rut import normalizar_rut
from recetasapp.models import Paciente
from .models import Domicilio, Entrega, InscripcionReparto, IntentoEntrega, RecetaEntrega

EDAD_DESPACHO = 80  # Elegible si tiene más de 80 años cumplidos: la misma regla del tótem (04).


def limite_nacimiento(fecha):
    """Último día de nacimiento con el que se tienen más de 80 años (81 o más) a `fecha`."""
    anio = fecha.year - (EDAD_DESPACHO + 1)
    try:
        return fecha.replace(year=anio)
    except ValueError:  # 29 de febrero en un año sin ese día
        return date(anio, 2, 28)


def _excepcion_vigente():
    return InscripcionReparto.objects.filter(paciente=OuterRef("pk"), retirada_en__isnull=True)


def condicion_elegible(fecha):
    """Condición de `Paciente` equivalente a `es_elegible`, para filtrar listas sin recorrer el padrón."""
    return Q(es_postrado=True) | Q(fecha_nacimiento__lte=limite_nacimiento(fecha)) | Q(Exists(_excepcion_vigente()))


def es_elegible(paciente, fecha=None):
    """Postrado, mayor de 80 años a `fecha` o con una excepción de reparto vigente."""
    fecha = fecha or timezone.localdate()
    if paciente.requiere_despacho_en(fecha):
        return True
    return InscripcionReparto.objects.filter(paciente=paciente, retirada_en__isnull=True).exists()


def excepcion_vigente(paciente):
    return InscripcionReparto.objects.filter(paciente=paciente, retirada_en__isnull=True).select_related("creado_por").first()


def filtrar_busqueda(pacientes, buscar, prefijo=""):
    """Filtra por RUT exacto o por nombre o apellido. `prefijo` permite buscar desde otra tabla."""
    buscar = (buscar or "").strip()
    if not buscar:
        return pacientes
    condicion = Q(**{f"{prefijo}nombres__icontains": buscar}) | Q(**{f"{prefijo}apellidos__icontains": buscar})
    try:
        condicion |= Q(**{f"{prefijo}rut": normalizar_rut(buscar)})
    except ValidationError:
        pass
    return pacientes.filter(condicion)


# Estado del domicilio ---------------------------------------------------------------------------------------

SIN_REGISTRAR = "sin_registrar"
PENDIENTE = "pendiente"
VERIFICADO = "verificado"


@dataclass(frozen=True)
class EstadoDomicilio:
    clave: str             # sin_registrar, pendiente o verificado
    texto: str             # rótulo en palabras: nunca se comunica solo con color
    padron_cambio: bool    # la dirección del padrón difiere de la que se revisó
    direccion_padron: str  # dirección actual del padrón, para mostrarla junto al aviso


def domicilio_de(paciente):
    """Domicilio del paciente o None; aprovecha `select_related("domicilio")` si la consulta lo trajo."""
    try:
        return paciente.domicilio
    except Domicilio.DoesNotExist:
        return None


def estado_domicilio(paciente, domicilio=None):
    """Estado efectivo: «verificado» solo con marca y sin cambios en el padrón desde la última revisión."""
    if domicilio is None:
        domicilio = domicilio_de(paciente)
    if domicilio is None:
        return EstadoDomicilio(SIN_REGISTRAR, "Sin registrar", False, paciente.direccion)
    cambio = paciente.direccion != domicilio.direccion_padron
    if domicilio.verificado_en and not cambio:
        return EstadoDomicilio(VERIFICADO, "Verificado", False, paciente.direccion)
    return EstadoDomicilio(PENDIENTE, "Pendiente de verificar", cambio, paciente.direccion)


def elegibles(fecha=None, *, buscar="", sector="", estado=""):
    """Pacientes del reparto con su domicilio (si existe), filtrables por búsqueda, sector y estado."""
    fecha = fecha or timezone.localdate()
    pacientes = Paciente.objects.filter(condicion_elegible(fecha)).select_related("domicilio__verificado_por").annotate(
        fotos_cantidad=Count("domicilio__fotos", distinct=True),
    ).order_by("apellidos", "nombres", "pk")
    pacientes = filtrar_busqueda(pacientes, buscar)
    if sector:
        pacientes = pacientes.filter(domicilio__sector=sector)
    if estado == SIN_REGISTRAR:
        pacientes = pacientes.filter(domicilio__isnull=True)
    elif estado == VERIFICADO:
        pacientes = pacientes.filter(domicilio__verificado_en__isnull=False, direccion=F("domicilio__direccion_padron"))
    elif estado == PENDIENTE:
        pacientes = pacientes.filter(domicilio__isnull=False).exclude(
            domicilio__verificado_en__isnull=False, direccion=F("domicilio__direccion_padron"),
        )
    return pacientes


# Entregas ---------------------------------------------------------------------------------------------------

def recetas_con_despacho_abierto(receta_ids):
    """Recetas (de las indicadas) fijadas a una entrega a domicilio abierta: no se dispensan en farmacia."""
    ids = list(receta_ids)
    if not ids:
        return set()
    return set(
        RecetaEntrega.objects.filter(receta_id__in=ids, entrega__estado__in=Entrega.ABIERTAS)
        .values_list("receta_id", flat=True)
    )


def despacho_abierto_de_receta(receta_id):
    """La entrega abierta que lleva esta receta, o None."""
    vinculo = RecetaEntrega.objects.select_related("entrega").filter(
        receta_id=receta_id, entrega__estado__in=Entrega.ABIERTAS,
    ).first()
    return vinculo.entrega if vinculo else None


def entrega_abierta(paciente):
    return Entrega.objects.filter(paciente=paciente, estado__in=Entrega.ABIERTAS).first()


def encargados_activos():
    """Cuentas activas con perfil y un único rol, que es Encargado de terreno (sin superusuarios)."""
    from django.contrib.auth import get_user_model
    from coreapp.roles import ROLES_INTERNOS

    usuarios = get_user_model().objects.filter(
        is_active=True, is_superuser=False, perfil__isnull=False, groups__name=ENCARGADO,
    ).exclude(groups__name__in=[rol for rol in ROLES_INTERNOS if rol != ENCARGADO])
    return usuarios.distinct().order_by("first_name", "last_name", "username")


def _intentos_con_contexto():
    recetas = RecetaEntrega.objects.select_related("receta").order_by("receta_id")
    return IntentoEntrega.objects.select_related(
        "entrega__paciente__domicilio", "encargado",
    ).prefetch_related(
        Prefetch("entrega__recetas", queryset=recetas),
        "entrega__paciente__domicilio__fotos",
    )


@dataclass(frozen=True)
class MisEntregas:
    hoy: list
    atrasadas: list
    proximas: list

    @property
    def total(self):
        return len(self.hoy) + len(self.atrasadas) + len(self.proximas)


def mis_entregas(encargado, hoy=None):
    """Intentos sin resultado del encargado: de hoy, atrasados y próximos, por fecha, sector y localidad."""
    hoy = hoy or timezone.localdate()
    intentos = list(
        _intentos_con_contexto().filter(encargado=encargado, resultado=IntentoEntrega.Resultado.PENDIENTE)
        .order_by("fecha_programada", "entrega__paciente__domicilio__sector",
                  "entrega__paciente__domicilio__localidad", "pk")
    )
    return MisEntregas(
        hoy=[i for i in intentos if i.fecha_programada == hoy],
        atrasadas=[i for i in intentos if i.fecha_programada < hoy],
        proximas=[i for i in intentos if i.fecha_programada > hoy],
    )


def contar_mis_entregas(encargado, hoy=None):
    hoy = hoy or timezone.localdate()
    return IntentoEntrega.objects.filter(
        encargado=encargado, resultado=IntentoEntrega.Resultado.PENDIENTE, fecha_programada__lte=hoy,
    ).count()


def _ultimo_intento():
    return IntentoEntrega.objects.filter(entrega=OuterRef("pk")).order_by("-numero")


def _entregas_con_ultimo_intento():
    ultimo = _ultimo_intento()
    return Entrega.objects.select_related("paciente__domicilio").annotate(
        ultimo_numero=Max("intentos__numero"),
        ultimo_fecha=Subquery(ultimo.values("fecha_programada")[:1]),
        ultimo_encargado=Subquery(ultimo.values("encargado_id")[:1]),
        ultimo_motivo=Subquery(ultimo.values("motivo")[:1]),
        ultimo_nota=Subquery(ultimo.values("nota")[:1]),
        ultimo_resultado=Subquery(ultimo.values("resultado")[:1]),
        recetas_cantidad=Count("recetas", distinct=True),
    )


def _aplicar_filtros(entregas, *, motivo="", sector="", encargado=None, desde=None, hasta=None):
    if motivo:
        entregas = entregas.filter(ultimo_motivo=motivo)
    if sector:
        entregas = entregas.filter(paciente__domicilio__sector=sector)
    if encargado:
        entregas = entregas.filter(ultimo_encargado=getattr(encargado, "pk", encargado))
    if desde:
        entregas = entregas.filter(ultimo_fecha__gte=desde)
    if hasta:
        entregas = entregas.filter(ultimo_fecha__lte=hasta)
    return entregas


def pendientes_gestion(**filtros):
    """Entregas «pendiente de gestión» con su último intento; filtros por motivo, sector, encargado y fechas."""
    entregas = _entregas_con_ultimo_intento().filter(estado=Entrega.Estado.PENDIENTE_GESTION)
    return _aplicar_filtros(entregas, **filtros).order_by("ultimo_fecha", "pk")


def programadas(**filtros):
    """Entregas programadas con su intento pendiente, por fecha; mismos filtros (sin motivo)."""
    filtros.pop("motivo", None)
    entregas = _entregas_con_ultimo_intento().filter(estado=Entrega.Estado.PROGRAMADA)
    return _aplicar_filtros(entregas, **filtros).order_by("ultimo_fecha", "paciente__domicilio__sector", "pk")


def no_descontadas():
    """Recetas que quedaron sin descontar al registrar una entrega y que la Q.F. aún no revisa."""
    return RecetaEntrega.objects.filter(
        resultado=RecetaEntrega.Resultado.NO_DESCONTADA, revisada_en__isnull=True,
    ).select_related("receta", "entrega__paciente").order_by("entrega__cerrada_en", "pk")
