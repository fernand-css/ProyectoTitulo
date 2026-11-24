"""Consultas de solo lectura del reparto a domicilio: elegibilidad, estado del domicilio y listas de trabajo.

Nada aquí escribe en la base. Las escrituras viven en `entregasapp.services`.
"""

import time as reloj
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db.models import Count, Exists, F, Max, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Lower, Trim
from django.utils import timezone

from coreapp.roles import ENCARGADO
from coreapp.utils.rut import condicion_busqueda_rut
from recetasapp.models import Paciente
from . import osrm
from .models import Domicilio, Entrega, InscripcionReparto, IntentoEntrega, OrdenRuta, RecetaEntrega
from .ruta import Punto, formatear_km, insertar, longitud_m, ordenar

EDAD_DESPACHO = 80  # Elegible con 80 años cumplidos o más: la misma regla del tótem (04). Cambio del 2026-11-13.


def limite_nacimiento(fecha):
    """Último día de nacimiento con el que se tienen 80 años cumplidos o más a `fecha`."""
    anio = fecha.year - EDAD_DESPACHO
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
    """Postrado, con 80 años o más a `fecha` o con una excepción de reparto vigente."""
    fecha = fecha or timezone.localdate()
    if paciente.requiere_despacho_en(fecha):
        return True
    return InscripcionReparto.objects.filter(paciente=paciente, retirada_en__isnull=True).exists()


def excepcion_vigente(paciente):
    return InscripcionReparto.objects.filter(paciente=paciente, retirada_en__isnull=True).select_related("creado_por").first()


def filtrar_busqueda(pacientes, buscar, prefijo=""):
    """Filtra por RUT (completo o su comienzo) o por nombre o apellido. `prefijo` permite buscar desde otra tabla."""
    buscar = (buscar or "").strip()
    if not buscar:
        return pacientes
    condicion = Q(**{f"{prefijo}nombres__icontains": buscar}) | Q(**{f"{prefijo}apellidos__icontains": buscar})
    por_rut = condicion_busqueda_rut(buscar, f"{prefijo}rut")
    if por_rut is not None:
        condicion |= por_rut
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


# Filtros de «Programar entrega» (RF-08-16, ampliación del 2026-11-13).
SIN_SECTOR = "sin"
MOTIVO_POSTRADO = "postrado"
MOTIVO_EDAD = "edad"
MOTIVO_EXCEPCION = "excepcion"
MOTIVOS_REPARTO = (
    (MOTIVO_POSTRADO, "Postrado"),
    (MOTIVO_EDAD, "80 años o más"),
    (MOTIVO_EXCEPCION, "Excepción vigente"),
)


def _clave_localidad(campo="localidad"):
    """Localidad sin distinguir mayúsculas ni espacios de los extremos («Dadinco» y «dadinco » son la misma)."""
    return Lower(Trim(campo))


def _entrega_abierta_de():
    return Entrega.objects.filter(paciente=OuterRef("pk"), estado__in=Entrega.ABIERTAS).values("pk")[:1]


def elegibles(fecha=None, *, buscar="", sector="", estado="", motivo="", localidad=""):
    """Pacientes del reparto con su domicilio (si existe), filtrables por búsqueda, sector, estado, motivo y localidad.

    Cada fila trae anotados `abierta_id` (su entrega abierta o None) y `con_excepcion`, para mostrar el motivo del
    reparto y el rótulo de entrega abierta sin una consulta por fila. `sector="sin"` reúne a los que no tienen
    domicilio o lo tienen sin sector. `localidad` es la clave normalizada que entrega `localidades_elegibles`.
    """
    fecha = fecha or timezone.localdate()
    pacientes = Paciente.objects.filter(condicion_elegible(fecha)).select_related("domicilio__verificado_por").annotate(
        fotos_cantidad=Count("domicilio__fotos", distinct=True),
        abierta_id=Subquery(_entrega_abierta_de()),
        con_excepcion=Exists(_excepcion_vigente()),
    ).order_by("apellidos", "nombres", "pk")
    pacientes = filtrar_busqueda(pacientes, buscar)
    if sector == SIN_SECTOR:
        pacientes = pacientes.filter(Q(domicilio__isnull=True) | Q(domicilio__sector=""))
    elif sector:
        pacientes = pacientes.filter(domicilio__sector=sector)
    if motivo == MOTIVO_POSTRADO:
        pacientes = pacientes.filter(es_postrado=True)
    elif motivo == MOTIVO_EDAD:
        pacientes = pacientes.filter(fecha_nacimiento__lte=limite_nacimiento(fecha))
    elif motivo == MOTIVO_EXCEPCION:
        pacientes = pacientes.filter(Exists(_excepcion_vigente()))
    if localidad:
        pacientes = pacientes.alias(localidad_clave=_clave_localidad("domicilio__localidad")).filter(localidad_clave=localidad)
    if estado == SIN_REGISTRAR:
        pacientes = pacientes.filter(domicilio__isnull=True)
    elif estado == VERIFICADO:
        pacientes = pacientes.filter(domicilio__verificado_en__isnull=False, direccion=F("domicilio__direccion_padron"))
    elif estado == PENDIENTE:
        pacientes = pacientes.filter(domicilio__isnull=False).exclude(
            domicilio__verificado_en__isnull=False, direccion=F("domicilio__direccion_padron"),
        )
    return pacientes


def localidades_elegibles(fecha=None):
    """[(clave, rótulo)] de las localidades registradas en los domicilios de los elegibles, sin vacías.

    Se agrupan por la clave normalizada y se muestran con la primera grafía registrada.
    """
    fecha = fecha or timezone.localdate()
    filas = (
        Domicilio.objects.filter(paciente__in=Paciente.objects.filter(condicion_elegible(fecha)))
        .annotate(clave=_clave_localidad()).exclude(clave="")
        .order_by("clave", "pk").values_list("clave", "localidad")
    )
    opciones = {}
    for clave, localidad in filas:
        opciones.setdefault(clave, localidad.strip())
    return list(opciones.items())


def motivos_de(paciente, fecha=None):
    """Rótulos del motivo del reparto (uno o varios). Se derivan, no se guardan.

    Usa la anotación `con_excepcion` de `elegibles` si está; si no, consulta la excepción vigente.
    """
    fecha = fecha or timezone.localdate()
    motivos = []
    if paciente.es_postrado:
        motivos.append("Postrado")
    if paciente.edad_en(fecha) >= EDAD_DESPACHO:
        motivos.append("80 años o más")
    con_excepcion = getattr(paciente, "con_excepcion", None)
    if con_excepcion is None:
        con_excepcion = InscripcionReparto.objects.filter(paciente=paciente, retirada_en__isnull=True).exists()
    if con_excepcion:
        motivos.append("Excepción")
    return motivos


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
        ultimo_registrado_en=Subquery(ultimo.values("registrado_en")[:1]),
        ultimo_sincronizado_en=Subquery(ultimo.values("sincronizado_en")[:1]),  # spec 11, RF-11-15
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
CAMINO = "camino"  # distancias de la matriz de OSRM (RF-09-20)
RECTA = "recta"    # respaldo en línea recta: OSRM no respondió o está desactivado; sin total
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
    total_m: object              # partida → paradas con coordenadas → CESFAM, por camino; None en el respaldo
    segundos_calculo: float
    limite_2opt_excedido: bool
    distancia: str = CAMINO      # CAMINO (matriz de OSRM) o RECTA (respaldo rotulado, sin total)

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
        """Visitas sin coordenadas fuera del cálculo, al final: en el orden sugerido, ordenadas por sector y
        localidad; en el manual, las que siguen después de la última con coordenadas, en el orden guardado."""
        return [parada for parada in self.paradas if not parada.numerada]

    @property
    def sin_marcador(self):
        return sum(1 for parada in self.paradas if parada.punto is None)

    @property
    def parte_del_origen(self):
        return self.partida_intento is None

    @property
    def total_km(self):
        return None if self.total_m is None else formatear_km(self.total_m)

    @property
    def por_camino(self):
        return self.distancia == CAMINO

    def parada_de(self, intento_id):
        return next((parada for parada in self.paradas if parada.intento.pk == intento_id), None)

    def parada_con_punto(self, intento_id):
        """La parada de la ruta con ese intento y coordenadas, o None: destino válido de un tramo (RF-09-21)."""
        parada = self.parada_de(intento_id)
        return parada if parada is not None and parada.punto is not None else None

    @property
    def proxima_con_punto(self):
        """La primera parada de la lista con coordenadas: el destino por defecto del tramo."""
        return next((parada for parada in self.paradas if parada.punto is not None), None)


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


def distancia_por_camino(puntos):
    """Función `distancia(a, b)` sobre la matriz de OSRM entre `puntos` (partida, domicilios y CESFAM), o None
    si OSRM no está disponible. La matriz solo tiene domicilios y el CESFAM, así que se guarda unos minutos en la
    caché (RF-09-20); la posición del encargado nunca pasa por aquí."""
    unicos, indice = [], {}
    for punto in puntos:
        if punto.clave not in indice:
            indice[punto.clave] = len(unicos)
            unicos.append(punto)
    if len(unicos) < 2:
        return None
    try:
        matriz = osrm.tabla(unicos, cachear=True)
    except osrm.OsrmNoDisponible:
        return None
    return lambda a, b: matriz[indice[a.clave]][indice[b.clave]]


def _aplicar_orden_guardado(guardados, vigentes, partida, origen, hoy, puntos, distancia):
    """Cruza el orden guardado con la ruta vigente e inserta las visitas nuevas (RF-09-05).

    Las guardadas que ya no están en la ruta (registradas, reasignadas o anuladas) desaparecen. Cada nueva con
    coordenadas entra donde menos alarga el recorrido, sin mover las demás; las nuevas sin coordenadas, al final.
    """
    secuencia = [(intento_id, False) for intento_id in guardados if intento_id in vigentes]
    presentes = {intento_id for intento_id, _ in secuencia}
    nuevas = [vigentes[pk] for pk in sorted(vigentes) if pk not in presentes]
    for intento in nuevas:
        punto = puntos[intento.pk]
        if punto is None:
            continue
        con_coordenadas = [indice for indice, (pk, _) in enumerate(secuencia) if puntos[pk] is not None]
        lugar = insertar([puntos[secuencia[indice][0]] for indice in con_coordenadas], partida, origen, punto,
                         distancia)
        if lugar < len(con_coordenadas):
            posicion = con_coordenadas[lugar]
        else:
            posicion = con_coordenadas[-1] + 1 if con_coordenadas else len(secuencia)
        secuencia.insert(posicion, (intento.pk, True))
    secuencia += [(intento.pk, True) for intento in nuevas if puntos[intento.pk] is None]
    # Enmienda del 2026-11-19 (decisión de la usuaria): las visitas sin coordenadas nunca entran a la ruta numerada.
    # Van siempre después de las que tienen coordenadas, sin número y en su orden guardado; un orden guardado antes,
    # con alguna sin coordenadas entre las numeradas, se lee así.
    secuencia = ([par for par in secuencia if puntos[par[0]] is not None]
                 + [par for par in secuencia if puntos[par[0]] is None])
    return [
        Parada(numero, vigentes[pk], puntos[pk], vigentes[pk].fecha_programada < hoy, nueva=nueva,
               numerada=puntos[pk] is not None)
        for numero, (pk, nueva) in enumerate(secuencia, start=1)
    ]


def ruta_del_dia(encargado, fecha=None, hoy=None, *, incluir_proximas=False):
    """Ruta de un encargado para `fecha` (hoy por defecto): orden guardado o sugerido. No escribe nada.

    Hoy: visitas sin resultado de hoy y atrasadas, partida desde la última visita registrada y orden guardado si
    existe. Fecha posterior (consulta de la Q.F.): solo las de esa fecha, sugeridas desde el CESFAM.

    Desde la enmienda (RF-09-20), el orden, las «Nuevas» y el total usan la distancia por camino de OSRM. Si OSRM
    no está disponible, el orden se calcula en línea recta (`distancia = RECTA`) y no hay total; un orden guardado
    no cambia, solo dónde se insertan las «Nuevas».
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
    puntos = {pk: punto_de(intento) for pk, intento in vigentes.items()}
    con_punto = [punto for punto in puntos.values() if punto is not None]
    distancia = distancia_por_camino([partida, *con_punto, origen]) if con_punto else None
    inicio = reloj.perf_counter()
    excedido = False
    if guardados:
        modo = MANUAL
        paradas = _aplicar_orden_guardado(guardados, vigentes, partida, origen, hoy, puntos, distancia)
    else:
        modo = SUGERIDO
        sugerido = ordenar(partida, origen, con_punto, distancia=distancia)
        excedido = sugerido.limite_excedido
        paradas = [Parada(numero, vigentes[punto.clave], punto, vigentes[punto.clave].fecha_programada < hoy)
                   for numero, punto in enumerate(sugerido.paradas, start=1)]
        sin = sorted((intento for pk, intento in vigentes.items() if puntos[pk] is None), key=_clave_sin_coordenadas)
        paradas += [Parada(numero, intento, None, intento.fecha_programada < hoy, numerada=False)
                    for numero, intento in enumerate(sin, start=len(paradas) + 1)]
    if distancia is not None:
        total = longitud_m([partida, *[parada.punto for parada in paradas if parada.punto is not None], origen], distancia)
    elif not con_punto and partida == origen:
        total = 0.0  # sin paradas con coordenadas no hay nada que preguntar a OSRM
    else:
        total = None
    return RutaDelDia(
        fecha=fecha, hoy=hoy, modo=modo, version=orden.version if orden else 0,
        guardado_en=orden.modificado_en if guardados else None, origen=origen, partida=partida,
        partida_intento=partida_intento, paradas=paradas, registradas=registradas, proximas=proximas,
        total_m=total, segundos_calculo=reloj.perf_counter() - inicio, limite_2opt_excedido=excedido,
        distancia=CAMINO if distancia is not None or total == 0.0 else RECTA,
    )
