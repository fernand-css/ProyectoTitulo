"""Panel de mermas (spec 13): dashboard y descargas."""

from calendar import monthrange

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from coreapp.auditoria import registrar_referencia
from coreapp.mixins import RolRequeridoMixin
from coreapp.roles import DIRECTOR, ETIQUETAS_ROLES, JEFA, SUPERUSUARIO, estado_acceso
from recetasapp.graficos import columnas
from . import canales as canales_mod
from . import graficos, reportes
from . import tablero as tablero_mod
from .periodos import DIA, MES, FiltroPanelForm, opciones

FORMATOS = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "pdf": "application/pdf",
}


def _rol_texto(usuario):
    rol = estado_acceso(usuario)[1]
    return "Administración" if rol == SUPERUSUARIO else ETIQUETAS_ROLES.get(rol, "")


def _plural(cantidad, singular, plural=None):
    return f"{cantidad} {singular if cantidad == 1 else (plural or singular + 's')}"


def _decimal(valor):
    """Un decimal con coma, sin el «,0» sobrante (texto para leer, no para un atributo SVG)."""
    texto = f"{valor:.1f}".replace(".", ",")
    return texto[:-2] if texto.endswith(",0") else texto


def _textos_columnas(grafico, granularidad):
    for columna in grafico["columnas"]:
        columna["texto"] = graficos.etiqueta(columna["fecha"], granularidad)
    for marca in grafico["marcas_x"]:
        marca["texto"] = graficos.marca(marca["fecha"], granularidad)
    return grafico


def _merma_por_periodo(tablero):
    """RF-13-15: calendario hasta 31 días (con los días que aún no llegan del mes en curso) o columnas."""
    resumen, periodo = tablero.resumen, tablero.periodo
    if not resumen.merma:
        return None, None
    if periodo.granularidad == DIA:
        hasta = None
        if periodo.clase == MES and not periodo.completo:
            hasta = periodo.inicio.replace(day=monthrange(periodo.inicio.year, periodo.inicio.month)[1])
        return graficos.calendario(resumen.serie, periodo.inicio, periodo.fin, hasta), None
    grafico = _textos_columnas(columnas(resumen.serie), periodo.granularidad)
    for columna in grafico["columnas"]:
        columna["tip"] = f"{columna['texto']}: {_plural(columna['valor'], 'receta')}"
    return None, grafico


def _agrupar(periodo, por_dia, campos):
    """Suma por clave de la serie (día, semana o mes) los `campos` de cada `Dia` de `canales.por_dia`."""
    serie = {clave: [0] * len(campos) for clave in periodo.claves()}
    for fecha, dia in por_dia.items():
        valores = serie[periodo.clave(fecha)]
        for i, campo in enumerate(campos):
            valores[i] += getattr(dia, campo)
    return list(serie.items())


def _entregas_por_dia(tablero):
    """RF-13-17: farmacia (en la atención o desde la ficha, y retiradas después) y domicilio, en dos gráficos."""
    periodo, canales = tablero.periodo, tablero.canales
    granularidad = periodo.granularidad
    farmacia_serie = _agrupar(periodo, canales.por_dia, ("farmacia_atencion_o_ficha", "farmacia_retiradas_despues"))
    domicilio_serie = _agrupar(periodo, canales.por_dia, ("domicilio_entregadas", "domicilio_no_entregadas"))
    farmacia = domicilio = None
    if any(sum(valores) for _, valores in farmacia_serie):
        promedios = canales_mod.promedios_farmacia(periodo, canales) if granularidad == DIA else None
        farmacia = _textos_columnas(graficos.columnas_apiladas(farmacia_serie, ("atencion", "despues"), promedios),
                                    granularidad)
        for columna in farmacia["columnas"]:
            atencion, despues = columna["valores"]
            columna["tip"] = (f"{columna['texto']}: {_plural(columna['total'], 'receta')} ({atencion} en la atención o "
                              f"desde la ficha, {despues} retirada{'s' if despues != 1 else ''} después)")
            if columna["promedio"] is not None:
                columna["promedio_texto"] = _decimal(columna["promedio"])
                columna["tip"] += f" · promedio de 7 días: {columna['promedio_texto']}"
    if any(sum(valores) for _, valores in domicilio_serie):
        domicilio = _textos_columnas(graficos.columnas_apiladas(domicilio_serie, ("entregadas", "no_entregadas")),
                                     granularidad)
        for columna in domicilio["columnas"]:
            buenas, malas = columna["valores"]
            columna["tip"] = (f"{columna['texto']}: {buenas} entregada{'s' if buenas != 1 else ''}, "
                              f"{malas} no entregada{'s' if malas != 1 else ''}")
    return farmacia, domicilio


def _filas_canales(canales):
    def fila(texto, entregadas, no_entregadas, clave):
        total = entregadas + no_entregadas
        return {"clave": clave, "texto": texto, "entregadas": tablero_mod.entero(entregadas),
                "no_entregadas": tablero_mod.entero(no_entregadas), "total": tablero_mod.entero(total),
                "porcentaje": f"{tablero_mod.decimal(100 * entregadas / total)} %" if total else "—"}

    return [
        fila("Farmacia", canales.farmacia_entregadas, canales.farmacia_no_entregadas, "farmacia"),
        fila("Domicilio", canales.domicilio_entregadas, canales.domicilio_no_entregadas, "domicilio"),
        fila("Total", canales.entregadas, canales.no_entregadas, "total"),
    ]


@method_decorator(never_cache, name="dispatch")
class PanelMermasView(RolRequeridoMixin, View):
    """Dashboard de mermas y entregas (RF-13-11 a RF-13-20). También es el inicio de la Dirección (RF-13-08)."""

    roles_permitidos = (JEFA, DIRECTOR)

    def get(self, request):
        hoy = timezone.localdate()
        form = FiltroPanelForm(request.GET or None, hoy=hoy)
        periodo = form.elegido()
        tablero = tablero_mod.armar(periodo, hoy)
        resumen, canales = tablero.resumen, tablero.canales
        calendario, evolucion = _merma_por_periodo(tablero)
        farmacia, domicilio = _entregas_por_dia(tablero)
        anterior, siguiente = periodo.anterior(), periodo.siguiente(hoy)
        contexto = {
            "form": form, "periodo": periodo, "tablero": tablero, "resumen": resumen, "canales": canales,
            "opciones": opciones(periodo, hoy), "consulta": periodo.consulta(),
            "anterior_url": anterior.consulta() if anterior else "",
            "siguiente_url": siguiente.consulta() if siguiente else "",
            # La Q.F. y el superusuario ven «Pendientes de retiro»; la Dirección no (RF-13-08).
            "ve_pendientes": estado_acceso(request.user)[1] in (JEFA, SUPERUSUARIO),
            "cifras": tablero.cifras,
            "filas_canales": _filas_canales(canales),
            "calendario": calendario, "evolucion": evolucion,
            "frase_dia": graficos.frase_dia_semana(resumen.por_dia_semana, resumen.merma, periodo.dias),
            "motivos_farmacia": graficos.barras(canales.motivos_farmacia, ordenar=True),
            "motivos_domicilio": graficos.barras(canales.motivos_domicilio, ordenar=True),
            "no_entregadas_farmacia": sum(cantidad for _, _, cantidad in canales.motivos_farmacia),
            "farmacia": farmacia, "domicilio": domicilio,
            "preparadas": graficos.barra_100(reportes.partes_preparadas(resumen)),
            "espera": graficos.barras([(i, texto, cantidad) for i, (texto, cantidad) in enumerate(resumen.espera)]),
            "por_tipo": graficos.division(resumen.por_tipo),
            "ausentes": tablero.ausentes,
            "formatos": (("xlsx", "Excel"), ("csv", "CSV"), ("pdf", "PDF")),
        }
        return render(request, "indicadores/mermas.html", contexto)


@method_decorator(never_cache, name="dispatch")
class ReporteMermasView(RolRequeridoMixin, View):
    """RF-13-21: Excel, CSV o PDF con las cifras del dashboard, nunca con datos personales. Cada descarga se audita."""

    roles_permitidos = (JEFA, DIRECTOR)

    def get(self, request, formato):
        if formato not in FORMATOS:
            raise Http404
        hoy = timezone.localdate()
        periodo = FiltroPanelForm(request.GET or None, hoy=hoy).elegido()
        datos = reportes.datos_desde(tablero_mod.armar(periodo, hoy), _rol_texto(request.user))
        generador = {"xlsx": reportes.excel, "csv": reportes.csv_por_dia, "pdf": reportes.pdf}[formato]
        contenido = generador(datos)
        registrar_referencia(
            request.user, f"mermas.reporte_{formato}", "indicadores.ReporteMermas",
            f"{periodo.inicio:%Y-%m-%d}_{periodo.fin:%Y-%m-%d}_{periodo.tipo}",
        )
        respuesta = HttpResponse(contenido, content_type=FORMATOS[formato])
        respuesta["Content-Disposition"] = f'attachment; filename="{datos.nombre_base}.{formato}"'
        return respuesta

