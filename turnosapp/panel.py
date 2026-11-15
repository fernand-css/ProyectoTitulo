"""Proyección privada de solo lectura; nunca inicia ni procesa la cola por GET."""
import uuid
from datetime import timedelta
from django.core.paginator import Paginator
from django.db.models import Count
from django.utils import timezone
from coreapp.mixins import tiene_rol
from coreapp.roles import JEFA, TECNICO
from .cola import espera_turno
from .models import TIPOS_VENTANILLA, ConfiguracionCola, PendienteSeleccion, Turno, Ventanilla


def _preparaciones_del_turno(turno):
    """Recetas del turno llamado, para marcarlas listas sin salir del panel."""
    if turno is None:
        return []
    from recetasapp.models import PreparacionReceta

    items = list(PreparacionReceta.objects.filter(turno_receta__turno=turno)
        .select_related("turno_receta__receta", "lista_por").order_by("turno_receta_id"))
    for item in items:
        receta = item.turno_receta.receta
        item.numero_entrega = receta.entregas_completadas + 1
        item.maximo_entregas = receta.max_entregas
    return items


# Filas a las que el personal puede mover un turno en espera (la urgencia tiene su propia acción).
OPCIONES_FILA = [("P", "Preferencial"), ("G", "General"), ("C", "Crónicos")]


def contexto_panel(usuario, pagina=1):
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    operar, gestionar = tiene_rol(usuario, TECNICO), tiene_rol(usuario, JEFA)
    ventanillas = list(Ventanilla.objects.select_related("operador").prefetch_related("tipos").order_by("retirada", "numero"))
    propia = next((v for v in ventanillas if v.operador_id == usuario.pk), None) if operar else None
    vigente = Turno.objects.select_related("paciente").filter(ventanilla=propia, estado="llamado").first() if propia else None
    preparaciones_vigente = _preparaciones_del_turno(vigente)
    # Qué turno atiende cada ventanilla, para listarlas todas con su estado.
    # Código con letra (P-014): las series por letra repiten números el mismo día.
    llamados = {ventanilla_id: f"{letra}-{numero:03d}" for ventanilla_id, letra, numero in
        Turno.objects.filter(estado="llamado").values_list("ventanilla_id", "letra", "numero")}
    for vent in ventanillas:
        vent.turno_actual = llamados.get(vent.pk)
        vent.es_propia = bool(propia and vent.pk == propia.pk)
        vent.nonce_ocupar = uuid.uuid4()
        vent.tipos_texto = ", ".join(tipo.get_codigo_display() for tipo in vent.tipos.all()) or "Ninguno"
        vent.activa_hoy = vent.automatico and vent.fecha_activacion == hoy and vent.habilitada and not vent.retirada
    espera = (Turno.objects.filter(fecha=hoy, estado="esperando")
        .annotate(cantidad_recetas=Count("recetas_vinculadas")).order_by("entrada_cola", "numero", "pk"))
    pagina_cola = Paginator(espera, 30).get_page(pagina)
    for turno in pagina_cola:
        turno.espera = espera_turno(turno, ahora)
    # Consulta propia: la de la fila cuenta recetas y repetiría turnos al agrupar.
    conteo = dict(Turno.objects.filter(fecha=hoy, estado="esperando").values_list("letra")
        .annotate(cantidad=Count("pk")).order_by())
    por_letra = [{"letra": letra, "cantidad": conteo.get(letra, 0)} for letra in ("P", "G", "C", "U")]
    habilitados = {tipo.codigo for vent in ventanillas if vent.habilitada and not vent.retirada for tipo in vent.tipos.all()}
    sin_cobertura = [etiqueta for codigo, etiqueta in TIPOS_VENTANILLA if codigo not in habilitados and espera.filter(tipo_atencion=codigo).exists()]
    from .espera import estimar_espera
    estimacion_preparacion = estimar_espera(ahora)
    return {"ventanillas": ventanillas, "propia": propia, "vigente": vigente, "pagina_cola": pagina_cola,
        "puede_operar": operar, "puede_gestionar": gestionar, "configuracion": ConfiguracionCola.objects.filter(pk=1).first(),
        "ausentes": Turno.objects.filter(fecha=hoy, estado="ausente").order_by("numero")[:100],
        "pendientes": PendienteSeleccion.objects.filter(estado="pendiente").order_by("creado_en")[:20],
        "sin_cobertura": sin_cobertura, "hoy": hoy, "ahora": ahora,
        "estimacion_preparacion": estimacion_preparacion,
        "preparaciones_vigente": preparaciones_vigente,
        "puede_ausente": bool(vigente and ahora >= vigente.ultimo_llamado + timedelta(seconds=60)),
        "segundos_ausente": max(0, 60 - int((ahora - vigente.ultimo_llamado).total_seconds())) if vigente else 0,
        "por_letra": por_letra, "opciones_dialogo": OPCIONES_FILA,
        "nonce_iniciar": uuid.uuid4(), "nonce_pausar": uuid.uuid4(), "nonce_liberar": uuid.uuid4(),
        "nonce_rellamar": uuid.uuid4(), "nonce_ausente": uuid.uuid4()}


# ---- Página «Ventanillas» de la Q.F.: tarjetas por ventanilla, resumen y orden de llamado ----

LETRA_DE_TIPO = {"preferencial": "P", "general": "G", "cronicos": "C", "urgencia": "U"}
NOMBRE_DE_LETRA = {"P": "preferencial", "G": "general", "C": "crónicos", "U": "urgencia"}
ESTADOS_VENTANILLA = {
    "atendiendo": "Atendiendo", "esperando": "Esperando turno", "pausa": "En pausa",
    "libre": "Libre", "cerrada": "Cerrada",
}


def _enumerar(palabras):
    return palabras[0] if len(palabras) == 1 else ", ".join(palabras[:-1]) + " y " + palabras[-1]


def _orden_de_llamado(config):
    """Secuencia del ciclo (P, P, C, G con pesos 2:1:1). Con muchos pasos se resume por cantidad."""
    if config is None:
        return None
    pesos = [("P", config.peso_preferencial), ("C", config.peso_cronicos), ("G", config.peso_general)]
    total = sum(peso for _, peso in pesos)
    nombres = {"P": ("preferencial", "preferenciales"), "C": ("crónico", "crónicos"), "G": ("general", "generales")}
    frase = _enumerar([f"{peso} {nombres[letra][peso != 1]}" for letra, peso in pesos])
    return {"secuencia": [letra for letra, peso in pesos for _ in range(peso)] if total <= 8 else None,
            "pesos": pesos, "frase": frase}


def contexto_gestion(usuario):
    datos = contexto_panel(usuario)
    hoy = datos["hoy"]
    from .models import OcupacionVentanilla
    terminos = {}
    for ocupacion in OcupacionVentanilla.objects.filter(motivo="termino_turno", cierre__isnull=False).order_by("cierre"):
        if timezone.localdate(ocupacion.cierre) == hoy:
            terminos[ocupacion.ventanilla_id] = ocupacion.cierre
    activas, retiradas = [], []
    for vent in datos["ventanillas"]:
        if vent.retirada:
            retiradas.append(vent)
            continue
        if not vent.habilitada:
            vent.estado_clave = "cerrada"
        elif vent.turno_actual:
            vent.estado_clave = "atendiendo"
        elif vent.operador_id and vent.activa_hoy:
            vent.estado_clave = "esperando"
        elif vent.operador_id:
            vent.estado_clave = "pausa"
        else:
            vent.estado_clave = "libre"
        vent.estado_texto = ESTADOS_VENTANILLA[vent.estado_clave]
        admitidas = {LETRA_DE_TIPO[tipo.codigo] for tipo in vent.tipos.all()}
        vent.letras = [letra for letra in ("P", "G", "C", "U") if letra in admitidas]
        vent.letras_texto = ("Solo " + _enumerar([NOMBRE_DE_LETRA[l] for l in vent.letras])) if 0 < len(vent.letras) < 4 else ""
        vent.letra_actual = vent.turno_actual[:1] if vent.turno_actual else ""
        vent.termino = terminos.get(vent.pk) if vent.estado_clave == "cerrada" else None
        vent.puede_terminar = bool(vent.operador_id or vent.habilitada)
        activas.append(vent)
    cuenta = lambda *claves: sum(v.estado_clave in claves for v in activas)
    datos.update(ventanillas_activas=activas, ventanillas_retiradas=retiradas,
        resumen=[("atendiendo", "Atendiendo", cuenta("atendiendo", "esperando")), ("pausa", "En pausa", cuenta("pausa")),
                 ("libre", "Libres", cuenta("libre")), ("cerrada", "Cerradas", cuenta("cerrada"))],
        orden=_orden_de_llamado(datos["configuracion"]))
    return datos
