"""Consultas de solo lectura del reparto a domicilio: elegibilidad, estado del domicilio y listas de trabajo.

Nada aquí escribe en la base. Las escrituras viven en `entregasapp.services`.
"""

import time as reloj
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Count, Exists, F, Max, OuterRef, Prefetch, Q, Subquery
from django.utils import timezone

from coreapp.roles import ENCARGADO
from coreapp.utils.rut import normalizar_rut
from recetasapp.models import Paciente
from .models import Domicilio, Entrega, InscripcionReparto, IntentoEntrega, OrdenRuta, RecetaEntrega
from .ruta import Punto, formatear_km, insertar, longitud_m, ordenar

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


# Ruta del día (spec 09) -----------------------------------------------------------------------------------------

SUGERIDO = "sugerido"
MANUAL = "manual"
REGISTRADOS = (IntentoEntrega.Resultado.ENTREGADA, IntentoEntrega.Resultado.NO_ENTREGADA)


def origen_ruta():
    """El CESFAM: punto de partida y destino final del recorrido (configurable en .env)."""
    return Punto("origen", float(settings.REPARTO_ORIGEN_LATITUD), float(settings.REPARTO_ORIGEN_LONGITUD))


def punto_de(intento):
    """Coordenadas del domicilio del paciente de la visita, o None si no tiene domicilio o coordenadas."""
    domicilio = domicilio_de(intento.entrega.paciente)
    if domicilio is None or domicilio.latitud is None:
        return None
    return Punto(intento.pk, float(domicilio.latitud), float(domicilio.longitud))


@dataclass
class Parada:
    """Una visita de la ruta. `numero` es su posición; `numerada` dice si la lista y el mapa muestran el número
    (en el orden sugerido, las visitas sin coordenadas quedan fuera del cálculo, al final y sin número)."""
    numero: int
    intento: IntentoEntrega
    punto: object  # ruta.Punto o None
    atrasada: bool
    nueva: bool = False
    numerada: bool = True


@dataclass
class RutaDelDia:
    fecha: date
    hoy: date
    modo: str                    # SUGERIDO o MANUAL
    version: int                 # 0 si el encargado no tiene un orden guardado para hoy
    guardado_en: object          # fecha y hora del orden guardado (modo manual), o None
    origen: object               # ruta.Punto del CESFAM
    partida: object              # ruta.Punto desde donde se calcula (el CESFAM o la última visita registrada)
    partida_intento: object      # intento registrado desde cuyo domicilio parte, o None
    paradas: list                # Parada en orden; en el modo sugerido, las sin coordenadas van al final sin número
    registradas: list            # intentos registrados hoy (solo si la fecha es hoy)
    proximas: list               # intentos de fechas posteriores (solo para el encargado)
    total_m: float               # partida → paradas con coordenadas → CESFAM, en línea recta
    segundos_calculo: float
    limite_2opt_excedido: bool

    @property
    def es_hoy(self):
        return self.fecha == self.hoy

    @property
    def manual(self):
        return self.modo == MANUAL

    @property
    def numeradas(self):
        return [parada for parada in self.paradas if parada.numerada]

    @property
    def sin_coordenadas(self):
        """En el orden sugerido: visitas sin coordenadas, fuera del cálculo, ya ordenadas por sector y localidad."""
        return [parada for parada in self.paradas if not parada.numerada]

    @property
    def sin_marcador(self):
        return sum(1 for parada in self.paradas if parada.punto is None)

    @property
    def parte_del_origen(self):
        return self.partida_intento is None

    @property
    def total_km(self):
        return formatear_km(self.total_m)

    def parada_de(self, intento_id):
        return next((parada for parada in self.paradas if parada.intento.pk == intento_id), None)


def _inicio_y_fin(dia):
    inicio = timezone.make_aware(datetime.combine(dia, time.min))
    return inicio, timezone.make_aware(datetime.combine(dia + timedelta(days=1), time.min))


def registradas_hoy(encargado, hoy=None):
    """Visitas que el encargado registró hoy como «entregada» o «no entregada», de la más antigua a la última."""
    hoy = hoy or timezone.localdate()
    inicio, fin = _inicio_y_fin(hoy)
    return list(
        IntentoEntrega.objects.select_related("entrega__paciente__domicilio")
        .filter(encargado=encargado, resultado__in=REGISTRADOS, registrado_en__gte=inicio, registrado_en__lt=fin)
        .order_by("registrado_en", "pk")
    )


def partida_del_dia(encargado, hoy=None, registradas=None):
    """(punto, intento): el domicilio con coordenadas de la última visita registrada hoy, o (CESFAM, None).

    Las visitas registradas cuyo domicilio no tiene coordenadas se ignoran.
    """
    if registradas is None:
        registradas = registradas_hoy(encargado, hoy)
    for intento in reversed(registradas):
        punto = punto_de(intento)
        if punto is not None:
            return punto, intento
    return origen_ruta(), None


def _clave_sin_coordenadas(intento):
    domicilio = domicilio_de(intento.entrega.paciente)
    sector = domicilio.sector if domicilio else ""
    localidad = domicilio.localidad.strip().lower() if domicilio else ""
    return (sector == "", sector, localidad == "", localidad, intento.pk)


def orden_guardado(encargado, fecha):
    """(OrdenRuta o None, ids de intentos en su orden). Un orden sin paradas vale la sugerencia."""
    orden = OrdenRuta.objects.filter(encargado=encargado, fecha=fecha).first()
    if orden is None:
        return None, []
    return orden, list(orden.paradas.order_by("posicion").values_list("intento_id", flat=True))


def _aplicar_orden_guardado(guardados, vigentes, partida, origen, hoy):
    """Cruza el orden guardado con la ruta vigente e inserta las visitas nuevas (RF-09-05).

    Las guardadas que ya no están en la ruta (registradas, reasignadas o anuladas) desaparecen. Cada nueva con
    coordenadas entra donde menos alarga el recorrido, sin mover las demás; las nuevas sin coordenadas, al final.
    """
    secuencia = [(intento_id, False) for intento_id in guardados if intento_id in vigentes]
    presentes = {intento_id for intento_id, _ in secuencia}
    nuevas = [vigentes[pk] for pk in sorted(vigentes) if pk not in presentes]
    puntos = {pk: punto_de(intento) for pk, intento in vigentes.items()}
    for intento in nuevas:
        punto = puntos[intento.pk]
        if punto is None:
            continue
        con_coordenadas = [indice for indice, (pk, _) in enumerate(secuencia) if puntos[pk] is not None]
        lugar = insertar([puntos[secuencia[indice][0]] for indice in con_coordenadas], partida, origen, punto)
        if lugar < len(con_coordenadas):
            posicion = con_coordenadas[lugar]
        else:
            posicion = con_coordenadas[-1] + 1 if con_coordenadas else len(secuencia)
        secuencia.insert(posicion, (intento.pk, True))
    secuencia += [(intento.pk, True) for intento in nuevas if puntos[intento.pk] is None]
    return [
        Parada(numero, vigentes[pk], puntos[pk], vigentes[pk].fecha_programada < hoy, nueva=nueva)
        for numero, (pk, nueva) in enumerate(secuencia, start=1)
    ]


def ruta_del_dia(encargado, fecha=None, hoy=None, *, incluir_proximas=False):
    """Ruta de un encargado para `fecha` (hoy por defecto): orden guardado o sugerido. No escribe nada.

    Hoy: visitas sin resultado de hoy y atrasadas, partida desde la última visita registrada y orden guardado si
    existe. Fecha posterior (consulta de la Q.F.): solo las de esa fecha, sugeridas desde el CESFAM.
    """
    hoy = hoy or timezone.localdate()
    fecha = fecha or hoy
    es_hoy = fecha == hoy
    pendientes = _intentos_con_contexto().filter(encargado=encargado, resultado=IntentoEntrega.Resultado.PENDIENTE)
    if not es_hoy:
        pendientes = pendientes.filter(fecha_programada=fecha)
    elif not incluir_proximas:
        pendientes = pendientes.filter(fecha_programada__lte=hoy)
    pendientes = list(pendientes.order_by("fecha_programada", "pk"))
    proximas = [i for i in pendientes if i.fecha_programada > hoy] if es_hoy else []
    vigentes = {i.pk: i for i in pendientes if not es_hoy or i.fecha_programada <= hoy}
    origen = origen_ruta()
    registradas, partida, partida_intento, orden, guardados = [], origen, None, None, []
    if es_hoy:
        registradas = registradas_hoy(encargado, hoy)
        partida, partida_intento = partida_del_dia(encargado, hoy, registradas)
        orden, guardados = orden_guardado(encargado, hoy)
    inicio = reloj.perf_counter()
    excedido = False
    if guardados:
        modo = MANUAL
        paradas = _aplicar_orden_guardado(guardados, vigentes, partida, origen, hoy)
    else:
        modo = SUGERIDO
        puntos = {pk: punto_de(intento) for pk, intento in vigentes.items()}
        sugerido = ordenar(partida, origen, [punto for punto in puntos.values() if punto is not None])
        excedido = sugerido.limite_excedido
        paradas = [Parada(numero, vigentes[punto.clave], punto, vigentes[punto.clave].fecha_programada < hoy)
                   for numero, punto in enumerate(sugerido.paradas, start=1)]
        sin = sorted((intento for pk, intento in vigentes.items() if puntos[pk] is None), key=_clave_sin_coordenadas)
        paradas += [Parada(numero, intento, None, intento.fecha_programada < hoy, numerada=False)
                    for numero, intento in enumerate(sin, start=len(paradas) + 1)]
    total = longitud_m([partida, *[parada.punto for parada in paradas if parada.punto is not None], origen])
    return RutaDelDia(
        fecha=fecha, hoy=hoy, modo=modo, version=orden.version if orden else 0,
        guardado_en=orden.modificado_en if guardados else None, origen=origen, partida=partida,
        partida_intento=partida_intento, paradas=paradas, registradas=registradas, proximas=proximas,
        total_m=total, segundos_calculo=reloj.perf_counter() - inicio, limite_2opt_excedido=excedido,
    )
