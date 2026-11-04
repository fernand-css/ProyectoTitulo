"""Datos de presentación de la libreta de control: situación, casillas y vigencia.

Solo lee: ninguna función escribe en la base ni decide permisos. La regla de
elegibilidad sigue siendo `services.evaluar_elegibilidad`; aquí se vuelve a
expresar como una única situación para mostrarla con ícono y texto.
"""

from datetime import timedelta

from django.utils import timezone

# Sobre este cupo la libreta deja de dibujar una casilla por entrega y muestra una barra.
MAX_CASILLAS = 24
# En las filas del padrón la mini-libreta usa puntos hasta este cupo.
MAX_PUNTOS = 12

SITUACIONES = {
    "vigente": {"clave": "vigente", "texto": "Vigente", "icono": "i-ok", "clase": "insignia-activa"},
    "futura": {"clave": "futura", "texto": "Aún no inicia", "icono": "i-calendario", "clase": "insignia-espera"},
    "vencida": {"clave": "vencida", "texto": "Vencida", "icono": "i-alerta", "clase": "insignia-alerta"},
    "agotada": {"clave": "agotada", "texto": "Agotada", "icono": "i-sello", "clase": "insignia-inactiva"},
}

# Frase para la fila del padrón cuando ninguna receta del paciente admite entregas.
SIN_VIGENTE = {
    "futura": "La receta aún no inicia su vigencia",
    "vencida": "La última receta está vencida",
    "agotada": "La última receta agotó sus entregas",
}


def situacion(receta, hoy=None):
    """Situación única de una receta; es «vigente» exactamente cuando admite entregas."""
    hoy = hoy or timezone.localdate()
    if hoy >= receta.fecha_fin_exclusiva:
        return SITUACIONES["vencida"]
    if receta.entregas_completadas >= receta.max_entregas:
        return SITUACIONES["agotada"]
    if hoy < receta.fecha_inicio:
        return SITUACIONES["futura"]
    return SITUACIONES["vigente"]


def _dias(cantidad):
    return "1 día" if cantidad == 1 else f"{cantidad} días"


def casillas(receta, entregas=(), proxima=False):
    """Una casilla por entrega del ciclo, o None si el cupo es demasiado grande para dibujarlas.

    Estados: «sellada» (entrega confirmada), «proxima» (la siguiente, solo si se pide) y «libre».
    """
    if receta.max_entregas > MAX_CASILLAS:
        return None
    por_numero = {entrega.numero: entrega for entrega in entregas}
    resultado = []
    for numero in range(1, receta.max_entregas + 1):
        if numero <= receta.entregas_completadas:
            estado = "sellada"
        elif proxima and numero == receta.entregas_completadas + 1:
            estado = "proxima"
        else:
            estado = "libre"
        resultado.append({"numero": numero, "estado": estado, "entrega": por_numero.get(numero)})
    return resultado


def porcentaje_entregas(receta):
    return round(100 * min(receta.entregas_completadas, receta.max_entregas) / receta.max_entregas)


def puntos(receta):
    """Un punto por entrega (lleno si ya se selló), o None si el cupo es demasiado grande para dibujarlos."""
    if receta.max_entregas > MAX_PUNTOS:
        return None
    return [numero <= receta.entregas_completadas for numero in range(1, receta.max_entregas + 1)]


def linea_vigencia(receta, hoy=None):
    """Posición de «hoy» entre el inicio y el último día válido, con la frase que la explica."""
    hoy = hoy or timezone.localdate()
    inicio, fin = receta.fecha_inicio, receta.fecha_fin_exclusiva
    ultimo_dia = fin - timedelta(days=1)
    total = max((fin - inicio).days, 1)
    avance = min(max((hoy - inicio).days, 0), total)
    if hoy < inicio:
        fase, texto = "antes", f"Comienza en {_dias((inicio - hoy).days)}"
    elif hoy >= fin:
        fase, texto = "despues", f"Venció hace {_dias((hoy - ultimo_dia).days)}"
    else:
        restantes = (fin - hoy).days
        fase = "dentro"
        texto = "Hoy es el último día de vigencia" if restantes == 1 else f"Quedan {restantes} días de vigencia"
    return {
        "porcentaje": round(100 * avance / total), "fase": fase, "texto": texto,
        "inicio": inicio, "ultimo_dia": ultimo_dia,
    }


def resumen_paciente(recetas, hoy=None):
    """Lo que Farmacia necesita ver de un paciente en una fila del padrón.

    Elige la primera receta vigente (la más reciente); si no hay, la más reciente.
    `recetas` debe venir ordenada de la más nueva a la más antigua.
    """
    hoy = hoy or timezone.localdate()
    recetas = list(recetas)
    if not recetas:
        return {"receta": None, "situacion": None, "texto": "Sin recetas registradas", "detalle": "", "puntos": None, "porcentaje": 0}
    elegida, estado = recetas[0], situacion(recetas[0], hoy)
    for receta in recetas:
        candidato = situacion(receta, hoy)
        if candidato["clave"] == "vigente":
            elegida, estado = receta, candidato
            break
    completadas, maximo = elegida.entregas_completadas, elegida.max_entregas
    if estado["clave"] == "vigente":
        texto = f"{completadas} de {maximo} entregas"
        detalle = f"Quedan {maximo - completadas}"
    else:
        texto, detalle = "Sin receta vigente", SIN_VIGENTE[estado["clave"]]
    return {
        "receta": elegida, "situacion": estado, "texto": texto, "detalle": detalle,
        "puntos": puntos(elegida), "porcentaje": porcentaje_entregas(elegida),
    }


# (clave, campo de la carga, texto, ícono): cada fila de una carga cae en exactamente una categoría.
CATEGORIAS_CARGA = (
    ("creadas", "filas_creadas", "Con altas", "i-mas"),
    ("actualizadas", "filas_actualizadas", "Con actualizaciones", "i-lapiz"),
    ("sin-cambios", "filas_sin_cambios", "Sin cambios", "i-ok"),
    ("omitidas", "filas_omitidas", "Duplicadas omitidas", "i-pausa"),
    ("rechazadas", "filas_rechazadas", "Rechazadas", "i-alerta"),
)
# Estado de una fila de resultado → (ícono, clase).
ESTADOS_FILA = {
    "creada": ("i-mas", "creadas"),
    "actualizada": ("i-lapiz", "actualizadas"),
    "sin_cambios": ("i-ok", "sin-cambios"),
    "omitida": ("i-pausa", "omitidas"),
    "rechazada": ("i-alerta", "rechazadas"),
}


def categorias_carga(carga):
    """Las cinco categorías de la carga con su cantidad; el total de la barra es la suma."""
    return [
        {"clave": clave, "texto": texto, "icono": icono, "cantidad": getattr(carga, campo)}
        for clave, campo, texto, icono in CATEGORIAS_CARGA
    ]


def preparar_fila(resultado):
    resultado.icono, resultado.clase = ESTADOS_FILA[resultado.estado]
    return resultado


def preparar_receta(receta, entregas=(), proxima=False, hoy=None):
    """Adjunta a la receta los datos de presentación; devuelve la misma instancia."""
    from .services import evaluar_elegibilidad

    receta.situacion = situacion(receta, hoy)
    receta.estado = evaluar_elegibilidad(receta, hoy)
    receta.casillas = casillas(receta, entregas, proxima and receta.estado["elegible"])
    receta.porcentaje = porcentaje_entregas(receta)
    return receta


# (clave, texto en plural, ícono) de las partes de la regleta del resumen. Son excluyentes: suman el total.
SEGMENTOS_RESUMEN = (
    ("vigente", "Vigentes", "i-ok"),
    ("futura", "Aún no inician", "i-calendario"),
    ("agotada", "Agotadas", "i-sello"),
    ("vencida", "Vencidas", "i-alerta"),
)


def segmentos_resumen(conteos):
    """Partes de la regleta con su cantidad; la clave sirve también de filtro en la lista de recetas."""
    return [
        {"clave": clave, "texto": texto, "icono": icono, "cantidad": conteos[clave]}
        for clave, texto, icono in SEGMENTOS_RESUMEN
    ]


def preparar_por_vencer(receta, hoy=None):
    """Días que le quedan a una receta vigente y último día en que sirve."""
    hoy = hoy or timezone.localdate()
    receta.dias = (receta.fecha_fin_exclusiva - hoy).days
    receta.ultimo_dia = receta.fecha_fin_exclusiva - timedelta(days=1)
    receta.entregas_restantes = max(0, receta.max_entregas - receta.entregas_completadas)
    return receta


def preparar_fila_receta(receta, hoy=None):
    """Datos de una fila de la lista de recetas: situación, puntos de entrega y vigencia."""
    hoy = hoy or timezone.localdate()
    receta.situacion = situacion(receta, hoy)
    receta.puntos = puntos(receta)
    receta.porcentaje = porcentaje_entregas(receta)
    receta.entregas_restantes = max(0, receta.max_entregas - receta.entregas_completadas)
    receta.vigencia = linea_vigencia(receta, hoy)
    return receta
