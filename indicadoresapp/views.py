"""Panel de mermas (spec 13): consulta, reportes y derivación al reparto."""

import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from coreapp.auditoria import registrar_referencia
from coreapp.mixins import RolRequeridoMixin
from coreapp.roles import DIRECTOR, ETIQUETAS_ROLES, JEFA, SUPERUSUARIO, estado_acceso
from recetasapp.graficos import columnas
from recetasapp.models import Paciente
from . import entregas, graficos, mermas, reportes
from .filtros import FiltroMermasForm, atajos

FORMATOS = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _rol_texto(usuario):
    rol = estado_acceso(usuario)[1]
    return "Administración" if rol == SUPERUSUARIO else ETIQUETAS_ROLES.get(rol, "")


def _consulta(periodo, extra=None):
    """Parámetros GET del filtro (fechas y tipo), sin datos personales."""
    partes = [f"desde={periodo.inicio:%Y-%m-%d}", f"hasta={periodo.fin:%Y-%m-%d}", f"tipo={periodo.tipo}"]
    partes += [f"{clave}={valor}" for clave, valor in (extra or {}).items()]
    return "?" + "&".join(partes)


def _grafico_evolucion(resumen):
    grafico = columnas(resumen.serie)
    for columna in grafico["columnas"]:
        fecha = columna["fecha"]
        columna["texto"] = (f"Semana del {reportes.fecha_corta(fecha)}" if resumen.por_semana
                            else reportes.fecha_corta(fecha))
        columna["tip"] = f"{columna['texto']}: {columna['valor']} receta{'s' if columna['valor'] != 1 else ''}"
    for marca in grafico["marcas_x"]:
        marca["texto"] = f"{marca['fecha'].day} {reportes.MESES[marca['fecha'].month - 1]}"
    return grafico


def _decimal(valor):
    """Un decimal con coma, sin el «,0» sobrante (texto para leer, no para un atributo SVG)."""
    texto = f"{valor:.1f}".replace(".", ",")
    return texto[:-2] if texto.endswith(",0") else texto


def _grafico_entregas(periodo):
    """Entregas confirmadas del período como columnas (y su promedio de 7 días si va por día), con sus textos."""
    datos = entregas.resumir(periodo)
    if not datos.total:
        return None
    grafico = columnas(datos.serie, datos.promedios or None)
    for columna in grafico["columnas"]:
        fecha, valor = columna["fecha"], columna["valor"]
        cantidad = f"{valor} entrega{'s' if valor != 1 else ''}"
        if datos.por_semana:
            columna["texto"] = f"Semana del {reportes.fecha_corta(fecha)}"
            columna["tip"] = f"{columna['texto']}: {cantidad}"
        else:
            columna["texto"] = reportes.fecha_corta(fecha)
            columna["promedio_texto"] = _decimal(columna["promedio"])
            columna["tip"] = (f"{columna['texto']}: {cantidad} · promedio de {entregas.VENTANA_PROMEDIO} días: "
                              f"{columna['promedio_texto']}")
    for marca in grafico["marcas_x"]:
        marca["texto"] = reportes.fecha_corta(marca["fecha"])
    grafico.update(
        por_semana=datos.por_semana, ventana=entregas.VENTANA_PROMEDIO,
        promedio_diario=_decimal(datos.total / periodo.dias),
        maximo_texto=(f"la semana del {reportes.fecha_corta(grafico['dia_maximo'])}" if datos.por_semana
                      else f"el {reportes.fecha_corta(grafico['dia_maximo'])}"),
        ultimo_promedio_texto=_decimal(grafico["ultimo_promedio"]) if grafico["ultimo_promedio"] is not None else "",
    )
    return grafico


@method_decorator(never_cache, name="dispatch")
class PanelMermasView(RolRequeridoMixin, View):
    """RF-13-02 a RF-13-04. También es el inicio de la Dirección del CESFAM (RF-13-08)."""

    roles_permitidos = (JEFA, DIRECTOR)

    def get(self, request):
        form = FiltroMermasForm(request.GET or None)
        periodo = form.periodo()
        resumen = mermas.resumir(periodo)
        paginas = Paginator(resumen.pacientes, mermas.POR_PAGINA)
        pagina = paginas.get_page(form.pagina())
        pagina.object_list = mermas.pacientes_de_la_pagina(list(pagina.object_list))
        hoy = timezone.localdate()
        contexto = {
            "form": form, "periodo": periodo, "resumen": resumen, "pagina": pagina,
            "puede_derivar": estado_acceso(request.user)[1] in (JEFA, SUPERUSUARIO),
            "atajos": [
                {"texto": texto, "url": _consulta(mermas.Periodo(desde, hasta, periodo.tipo)),
                 "actual": (desde, hasta) == (periodo.inicio, periodo.fin)}
                for texto, desde, hasta in atajos(hoy)
            ],
            "consulta": _consulta(periodo),
            "blister": graficos.blister(resumen.cifras),
            "evolucion": _grafico_evolucion(resumen) if resumen.merma and resumen.por_semana else None,
            "calendario": (graficos.calendario(resumen.serie, periodo.inicio, periodo.fin)
                           if resumen.merma and not resumen.por_semana else None),
            "frase_dia": graficos.frase_dia_semana(resumen.por_dia_semana, resumen.merma, periodo.dias),
            "espera": graficos.barras([(i, texto, cantidad) for i, (texto, cantidad) in enumerate(resumen.espera)]),
            "sin_retirar_viejas": sum(cantidad for _, cantidad in resumen.espera[3:]),
            "por_tipo": graficos.division(resumen.por_tipo),
            "por_cierre": graficos.barras(resumen.por_cierre, ordenar=True),
            "inicio_texto": reportes.fecha_larga(periodo.inicio), "fin_texto": reportes.fecha_larga(periodo.fin),
            "entregas": _grafico_entregas(periodo),
        }
        return render(request, "indicadores/mermas.html", contexto)


@method_decorator(never_cache, name="dispatch")
class ReporteMermasView(RolRequeridoMixin, View):
    """RF-13-05: Excel o PDF con cifras y gráficos, nunca con datos personales. Cada descarga queda auditada."""

    roles_permitidos = (JEFA, DIRECTOR)

    def get(self, request, formato):
        if formato not in FORMATOS:
            raise Http404
        periodo = FiltroMermasForm(request.GET or None).periodo()
        datos = reportes.datos_desde(mermas.resumir(periodo), _rol_texto(request.user))
        contenido = reportes.excel(datos) if formato == "xlsx" else reportes.pdf(datos)
        registrar_referencia(
            request.user, f"mermas.reporte_{formato}", "indicadores.ReporteMermas",
            f"{periodo.inicio:%Y-%m-%d}_{periodo.fin:%Y-%m-%d}_{periodo.tipo}",
        )
        respuesta = HttpResponse(contenido, content_type=FORMATOS[formato])
        respuesta["Content-Disposition"] = f'attachment; filename="{datos.nombre_base}.{formato}"'
        return respuesta


class DerivarForm(forms.Form):
    fecha = forms.DateField(label="Fecha de la visita", help_text="Hoy o una fecha posterior.",
                            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    motivo = forms.ChoiceField(label="Motivo de la excepción de reparto", required=False)
    nota = forms.CharField(label="Nota", max_length=200, required=False, widget=forms.Textarea(attrs={"rows": 2}),
                           help_text="Obligatoria con el motivo «Otro». Hasta 200 caracteres.")
    operacion_id = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, elegible=True, **kwargs):
        from entregasapp.forms import _encargado
        from entregasapp.models import InscripcionReparto

        super().__init__(*args, **kwargs)
        self.fields["encargado"] = _encargado()
        self.elegible = elegible
        if elegible:
            del self.fields["motivo"]
            del self.fields["nota"]
        else:
            self.fields["motivo"].required = True
            self.fields["motivo"].choices = [("", "Elige un motivo"), *InscripcionReparto.Motivo.choices]
        self.order_fields(["fecha", "encargado", "motivo", "nota", "operacion_id"])

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha < timezone.localdate():
            raise forms.ValidationError("La fecha debe ser hoy o posterior.")
        return fecha

    def clean(self):
        datos = super().clean()
        if not self.elegible and datos.get("motivo") == "otro" and not (datos.get("nota") or "").strip():
            self.add_error("nota", "Con el motivo «Otro», escribe una nota breve.")
        return datos


def _mensaje(error):
    return " ".join(error.messages) if hasattr(error, "messages") else str(error)


@method_decorator(never_cache, name="dispatch")
class DerivarMermaView(RolRequeridoMixin, View):
    """RF-13-06: la Q.F. (o el superusuario) deriva a un paciente al reparto con lo ya preparado."""

    roles_permitidos = (JEFA,)

    def contexto(self, request, paciente, form):
        from entregasapp import consultas
        from entregasapp.services import preparaciones_para_derivar

        return {
            "paciente": paciente, "form": form, "elegible": form.elegible,
            "motivos": consultas.motivos_de(paciente), "preparaciones": preparaciones_para_derivar(paciente),
            "abierta": consultas.entrega_abierta(paciente),
            # Vuelve al panel con el mismo filtro (fechas y tipo; nunca datos personales).
            "volver": reverse("indicadoresapp:mermas") + _consulta(FiltroMermasForm(request.GET or None).periodo()),
        }

    def get(self, request, paciente_id):
        from entregasapp import consultas

        paciente = get_object_or_404(Paciente, pk=paciente_id)
        form = DerivarForm(initial={"fecha": timezone.localdate(), "operacion_id": uuid.uuid4()},
                           elegible=consultas.es_elegible(paciente))
        return render(request, "indicadores/derivar.html", self.contexto(request, paciente, form))

    def post(self, request, paciente_id):
        from entregasapp import consultas, services

        paciente = get_object_or_404(Paciente, pk=paciente_id)
        fecha_pedida = DerivarForm.base_fields["fecha"].widget.value_from_datadict(request.POST, {}, "fecha")
        try:
            fecha = forms.DateField().clean(fecha_pedida)
        except ValidationError:
            fecha = timezone.localdate()
        form = DerivarForm(request.POST, elegible=consultas.es_elegible(paciente, fecha))
        if form.is_valid():
            datos = form.cleaned_data
            try:
                entrega = services.derivar_desde_merma(
                    request.user, paciente.pk, datos["fecha"], datos["encargado"].pk, datos["operacion_id"],
                    motivo=datos.get("motivo", ""), nota=(datos.get("nota") or "").strip(),
                )
            except services.EntregaAbiertaExistente as error:
                messages.warning(request, "Ya tiene una entrega abierta. Se muestra a continuación.")
                return redirect("entregasapp:detalle", pk=error.entrega_id)
            except ValidationError as error:
                form.add_error(None, _mensaje(error))
            except DatabaseError:
                form.add_error(None, "No pudimos derivar al paciente. Inténtalo nuevamente con el mismo formulario.")
            else:
                cantidad = entrega.recetas.count()
                messages.success(
                    request, f"Derivado al reparto: entrega programada para el {datos['fecha']:%d/%m/%Y} "
                             f"con {cantidad} receta{'s' if cantidad != 1 else ''}.",
                )
                return redirect("entregasapp:detalle", pk=entrega.pk)
        return render(request, "indicadores/derivar.html", self.contexto(request, paciente, form), status=200)
