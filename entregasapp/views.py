"""Pantallas privadas del reparto a domicilio (spec 08).

La matriz de permisos se aplica dos veces: aquí, con `RolRequeridoMixin` o la comprobación exacta del
encargado, y otra vez en `entregasapp.services`. Ocultar un botón nunca es el control. Todas las respuestas
llevan `Cache-Control: no-store` y las URL solo contienen identificadores internos (nunca RUT ni nombres).
"""

import json
import math
import time
import uuid
from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.cache import never_cache

from coreapp.mixins import RolRequeridoMixin, tiene_rol
from coreapp.roles import ENCARGADO, JEFA, TECNICO
from recetasapp.models import Paciente
from recetasapp.services import evaluar_elegibilidad
from . import consultas, fotos, mapa, osrm, services
from .ruta import Punto, formatear_distancia
from .forms import (
    AnularForm, BusquedaForm, DomicilioForm, EntregadaForm, ExcepcionForm, FiltroDomiciliosForm, FiltroEntregasForm,
    FiltroProgramarForm, FotosForm, MoverParadaForm, NoEntregadaForm, ProgramarForm, ProgramarVariosForm, ReasignarForm,
    RestablecerOrdenForm, RutaForm, VersionForm,
)
from .models import Domicilio, Entrega, FotoDomicilio, InscripcionReparto, IntentoEntrega, RecetaEntrega

TODOS = (JEFA, TECNICO, ENCARGADO)
FARMACIA = (JEFA, TECNICO)
GESTION = (JEFA,)


def _mensaje(error, defecto="No se pudo completar la operación."):
    return error.messages[0] if getattr(error, "messages", None) else defecto


def _nombre(usuario):
    if usuario is None:
        return "Cuenta retirada"
    return usuario.get_full_name().strip() or usuario.get_username()


@method_decorator(never_cache, name="dispatch")
class EntregasView(RolRequeridoMixin, View):
    roles_permitidos = TODOS

    def render(self, template, contexto, **kwargs):
        contexto.setdefault("es_encargado", services.es_encargado(self.request.user))
        contexto.setdefault("puede_gestionar", tiene_rol(self.request.user, JEFA))
        respuesta = render(self.request, "entregas/" + template, contexto, **kwargs)
        respuesta.headers["Referrer-Policy"] = "same-origin"
        return respuesta

    def pestanas(self, actual):
        if services.es_encargado(self.request.user):
            opciones = [("mis", "Mis entregas", "entregasapp:mis", consultas.contar_mis_entregas(self.request.user)),
                        ("mapa", "Mapa", "entregasapp:mapa", None),
                        ("domicilios", "Domicilios", "entregasapp:domicilios", None)]
        else:
            opciones = [("programacion", "Programación", "entregasapp:programacion", None),
                        ("pendientes", "Pendientes de gestión", "entregasapp:pendientes", consultas.pendientes_gestion().count())]
            if tiene_rol(self.request.user, JEFA):  # spec 09: «Rutas» es de la Q.F. y el superusuario, no del Técnico
                opciones.append(("rutas", "Rutas", "entregasapp:rutas", None))
            opciones.append(("domicilios", "Domicilios", "entregasapp:domicilios", None))
        return [{"clave": clave, "texto": texto, "url": reverse(destino), "cantidad": cantidad, "actual": clave == actual}
                for clave, texto, destino, cantidad in opciones]


class SoloEncargadoView(EntregasView):
    """Registro en terreno: solo el encargado (el superusuario no atestigua visitas)."""

    def test_func(self):
        return services.es_encargado(self.request.user)


class IndiceView(EntregasView):
    def get(self, request):
        if services.es_encargado(request.user):
            return redirect("entregasapp:mis")
        if tiene_rol(request.user, *FARMACIA):
            return redirect("entregasapp:programacion")
        raise PermissionDenied


def _encargados(ids):
    return {u.pk: _nombre(u) for u in get_user_model().objects.filter(pk__in=[i for i in ids if i])}


def _preparar_filas(entregas):
    """Anota cada entrega con el nombre del encargado y el estado del domicilio, sin consultas por fila."""
    nombres = _encargados({e.ultimo_encargado for e in entregas})
    for entrega in entregas:
        entrega.encargado_nombre = nombres.get(entrega.ultimo_encargado, "—")
        entrega.domicilio_estado = consultas.estado_domicilio(entrega.paciente, consultas.domicilio_de(entrega.paciente))
        entrega.motivo_texto = dict(IntentoEntrega.Motivo.choices).get(entrega.ultimo_motivo, "")
    return entregas


class ProgramacionView(EntregasView):
    roles_permitidos = FARMACIA

    def get(self, request):
        form = FiltroEntregasForm(request.GET or None)
        form.fields.pop("motivo")
        filtros = form.filtros() if form.is_bound else {}
        page_obj = Paginator(consultas.programadas(**filtros), 50).get_page(request.GET.get("page"))
        page_obj.object_list = _preparar_filas(list(page_obj.object_list))
        return self.render("programacion.html", {
            "form": form, "page_obj": page_obj, "pestanas": self.pestanas("programacion"), "hoy": timezone.localdate(),
            "filtrado": bool(filtros),
        })


class ProgramarView(EntregasView):
    """Buscar un paciente elegible, revisar las recetas que se fijarán y confirmar la programación."""

    roles_permitidos = GESTION

    def paciente_preseleccionado(self, valor):
        if not valor:
            return None
        try:
            return get_object_or_404(Paciente, pk=int(valor))
        except (TypeError, ValueError):
            raise Http404 from None

    def contexto_paciente(self, paciente, fecha):
        hoy = timezone.localdate()
        return {
            "paciente": paciente,
            "elegible": consultas.es_elegible(paciente, fecha or hoy),
            "abierta": consultas.entrega_abierta(paciente),
            "domicilio_estado": consultas.estado_domicilio(paciente),
            "domicilio": consultas.domicilio_de(paciente),
        }

    def get(self, request):
        paciente = self.paciente_preseleccionado(request.GET.get("paciente"))
        if paciente is None:
            return self.lista(FiltroProgramarForm(fecha=timezone.localdate()))
        form = ProgramarForm(initial={"fecha": timezone.localdate(), "operacion_id": uuid.uuid4()})
        return self.render("programar.html", {**self.contexto_paciente(paciente, None), "form": form,
                                              "pestanas": self.pestanas("programacion")})

    def post(self, request):
        accion = request.POST.get("accion")
        if accion == "buscar":
            return self.buscar(request)
        paciente = self.paciente_preseleccionado(request.POST.get("paciente"))
        if paciente is None:
            raise Http404
        form = ProgramarForm(request.POST)
        contexto = {"form": form, "pestanas": self.pestanas("programacion")}
        if not form.is_valid():
            return self.render("programar.html", {**self.contexto_paciente(paciente, None), **contexto})
        datos = form.cleaned_data
        contexto.update(self.contexto_paciente(paciente, datos["fecha"]))
        if accion != "confirmar":
            contexto["revision"] = {
                "fecha": datos["fecha"], "encargado": datos["encargado"],
                "recetas": [(r, evaluar_elegibilidad(r, datos["fecha"])) for r in services.recetas_para_despacho(paciente, datos["fecha"])],
            }
            return self.render("programar.html", contexto)
        try:
            entrega = services.programar_entrega(request.user, paciente.pk, datos["fecha"], datos["encargado"].pk, datos["operacion_id"])
        except services.EntregaAbiertaExistente as error:
            messages.warning(request, "El paciente ya tiene una entrega a domicilio abierta. Se muestra a continuación.")
            return redirect("entregasapp:detalle", pk=error.entrega_id)
        except ValidationError as error:
            form.add_error(None, _mensaje(error))
        except DatabaseError:
            form.add_error(None, "No pudimos programar la entrega. Inténtalo nuevamente con el mismo formulario.")
        else:
            messages.success(request, f"Entrega programada para el {datos['fecha']:%d/%m/%Y} con {entrega.recetas.count()} receta(s).")
            return redirect("entregasapp:detalle", pk=entrega.pk)
        return self.render("programar.html", contexto)

    def buscar(self, request):
        """Respaldo sin JavaScript de la lista (RF-08-16): la misma búsqueda y los filtros con «Buscar»."""
        return self.lista(FiltroProgramarForm(request.POST, fecha=timezone.localdate()))

    def lista(self, form):
        return self.render("programar.html", {**contexto_lista_programar(form), "pestanas": self.pestanas("programacion")})


# Lista y programación de varios (RF-08-16 y RF-08-17, ampliación del 2026-11-13) ------------------------------

POR_PAGINA_PROGRAMAR = 50
SAL_LOTE = "entregas.programar_lote"


def contexto_lista_programar(form):
    """Elegibles a hoy con la búsqueda y los filtros del formulario, en páginas de 50, sin consultas por fila."""
    hoy = timezone.localdate()
    filtros = form.filtros()
    page_obj = Paginator(consultas.elegibles(hoy, **filtros), POR_PAGINA_PROGRAMAR).get_page(form.pagina())
    filas = list(page_obj.object_list)
    for persona in filas:
        persona.domicilio_registrado = consultas.domicilio_de(persona)
        persona.domicilio_estado = consultas.estado_domicilio(persona, persona.domicilio_registrado)
        persona.motivos = consultas.motivos_de(persona, hoy)
    page_obj.object_list = filas
    return {"form": form, "page_obj": page_obj, "total": page_obj.paginator.count, "filtrado": bool(filtros), "hoy": hoy}


class ProgramarListaView(EntregasView):
    """Fragmento de la lista para la búsqueda en vivo. Por POST: el RUT o el nombre nunca van en la URL."""

    roles_permitidos = GESTION

    def post(self, request):
        form = FiltroProgramarForm(request.POST, fecha=timezone.localdate())
        return self.render("_programar_lista.html", contexto_lista_programar(form))


def _ids_enviados(valores):
    """Identificadores enteros positivos, sin repetir y en el orden recibido; lo demás se descarta."""
    vistos = {}
    for valor in valores:
        try:
            identificador = int(valor)
        except (TypeError, ValueError):
            continue
        if identificador > 0:
            vistos.setdefault(identificador, None)
    return list(vistos)


def _nombre_paciente(paciente):
    return f"{paciente.apellidos}, {paciente.nombres}"


def _url_programacion(encargado_id, fecha):
    return f"{reverse('entregasapp:programacion')}?encargado={encargado_id}&desde={fecha:%Y-%m-%d}&hasta={fecha:%Y-%m-%d}"


class ProgramarVariosView(EntregasView):
    """Fecha y encargado para un lote, y resumen para revisar antes de confirmar (RF-08-17).

    La selección llega como `ids` (casillas) o como `todos=1` con la búsqueda y los filtros; en ese caso la lista se
    resuelve aquí, nunca con ids del navegador. Las reglas se recalculan a la fecha elegida.
    """

    roles_permitidos = GESTION

    def seleccion(self, request):
        """(pacientes, ids sin paciente, datos ocultos para reenviar la selección). None si no hay selección válida."""
        hoy = timezone.localdate()
        if request.POST.get("todos") == "1":
            filtro = FiltroProgramarForm(request.POST, fecha=hoy)
            if not filtro.is_valid():
                return None
            filtros = filtro.filtros()
            pacientes = list(consultas.elegibles(hoy, **filtros))
            if not pacientes:
                return None
            return pacientes, [], [("todos", "1"), *filtros.items()]
        ids = _ids_enviados(request.POST.getlist("ids"))
        if not ids:
            return None
        pacientes = list(Paciente.objects.filter(pk__in=ids).select_related("domicilio").order_by("apellidos", "nombres", "pk"))
        encontrados = {persona.pk for persona in pacientes}
        return pacientes, [pid for pid in ids if pid not in encontrados], [("ids", pid) for pid in ids]

    def post(self, request):
        seleccion = self.seleccion(request)
        if seleccion is None:
            messages.warning(request, "Marca al menos un paciente de la lista o usa «Seleccionar los filtrados». "
                                      "Si cambiaste la búsqueda, vuelve a seleccionar.")
            return redirect("entregasapp:programar")
        pacientes, faltantes, ocultos = seleccion
        paso_revision = "fecha" in request.POST
        form = ProgramarVariosForm(request.POST if paso_revision else None, initial={"fecha": timezone.localdate()})
        contexto = {"form": form, "ocultos": ocultos, "cantidad": len(pacientes) + len(faltantes),
                    "pestanas": self.pestanas("programacion")}
        if paso_revision and form.is_valid():
            contexto["revision"] = self.revisar(pacientes, faltantes, form.cleaned_data["fecha"], form.cleaned_data["encargado"])
        return self.render("programar_varios.html", contexto, status=400 if paso_revision and not form.is_valid() else 200)

    def revisar(self, pacientes, faltantes, fecha, encargado):
        """Clasifica a cada paciente como el servicio: elegible a la fecha, sin entrega abierta y con recetas."""
        ids = [persona.pk for persona in pacientes]
        elegibles = set(Paciente.objects.filter(pk__in=ids).filter(consultas.condicion_elegible(fecha)).values_list("pk", flat=True))
        abiertas = dict(Entrega.objects.filter(paciente_id__in=ids, estado__in=Entrega.ABIERTAS).values_list("paciente_id", "pk"))
        recetas = services.recetas_para_despacho_lote(ids, fecha)
        programables, omitidos = [], []
        for persona in pacientes:
            if persona.pk not in elegibles:
                omitidos.append({"paciente": persona, "motivo": services.OMITIDO_NO_ELEGIBLE})
            elif persona.pk in abiertas:
                omitidos.append({"paciente": persona, "motivo": services.OMITIDO_ABIERTA, "entrega_id": abiertas[persona.pk]})
            elif not recetas[persona.pk]:
                omitidos.append({"paciente": persona, "motivo": services.OMITIDO_SIN_RECETAS})
            else:
                persona.domicilio_registrado = consultas.domicilio_de(persona)
                persona.recetas_lote = [(receta, evaluar_elegibilidad(receta, fecha)) for receta in recetas[persona.pk]]
                programables.append(persona)
        omitidos += [{"paciente": None, "motivo": services.OMITIDO_NO_DISPONIBLE} for _ in faltantes]
        firmado = {
            "lote": str(uuid.uuid4()), "ids": [persona.pk for persona in programables], "fecha": fecha.isoformat(),
            "encargado": encargado.pk, "actor": self.request.user.pk,
            "omitidos": [[o["paciente"].pk if o["paciente"] else None, o["motivo"]] for o in omitidos],
        }
        return {
            "fecha": fecha, "encargado": encargado, "encargado_nombre": _nombre(encargado),
            "programables": programables, "omitidos": omitidos, "total": len(pacientes) + len(faltantes),
            "recetas_total": sum(len(persona.recetas_lote) for persona in programables),
            "contexto": signing.dumps(firmado, salt=SAL_LOTE, compress=True), "tramo": services.TRAMO_MAXIMO,
            "url_programacion": _url_programacion(encargado.pk, fecha),
        }


class ProgramarTramoView(EntregasView):
    """Confirma un lote revisado: por tramos de hasta 25 (JSON, con JavaScript) o completo (HTML, sin JavaScript).

    El contexto firmado fija los pacientes, la fecha, el encargado y la cuenta que revisó; el servidor igual
    revalida todo al programar a cada paciente. Las respuestas JSON no llevan RUT ni nombres.
    """

    roles_permitidos = GESTION

    def error(self, mensaje, por_tramos):
        if por_tramos:
            return JsonResponse({"error": mensaje}, status=400)
        messages.error(self.request, mensaje)
        return redirect("entregasapp:programar")

    def post(self, request):
        por_tramos = "desde" in request.POST
        try:
            firmado = signing.loads(request.POST.get("contexto", ""), salt=SAL_LOTE)
            ids = [int(pid) for pid in firmado["ids"]]
            fecha = date.fromisoformat(firmado["fecha"])
            encargado_id, actor_id, lote = int(firmado["encargado"]), int(firmado["actor"]), str(firmado["lote"])
            omitidos = [(pid, str(motivo)) for pid, motivo in firmado.get("omitidos", [])]
        except (signing.BadSignature, KeyError, TypeError, ValueError):
            return self.error("La revisión no es válida o fue alterada. Vuelve a revisar el lote.", por_tramos)
        if actor_id != request.user.pk:
            return self.error("Esta revisión la hizo otra cuenta. Revisa el lote con tu propia sesión.", por_tramos)
        desde, hasta = 0, len(ids)
        if por_tramos:
            try:
                desde, hasta = int(request.POST["desde"]), int(request.POST.get("hasta", ""))
            except (TypeError, ValueError):
                desde = hasta = -1
            if not (0 <= desde < hasta <= len(ids) and hasta - desde <= services.TRAMO_MAXIMO):
                return self.error(f"El tramo no es válido: envía de a {services.TRAMO_MAXIMO} pacientes como máximo.", True)
        try:
            resultados = services.programar_lote(request.user, ids[desde:hasta], fecha, encargado_id, lote)
        except ValidationError as error:
            return self.error(_mensaje(error), por_tramos)
        if por_tramos:
            return JsonResponse({"desde": desde, "hasta": hasta, "resultados": [
                {"paciente": r.paciente_id, "estado": "programado", "entrega": r.entrega_id, "recetas": r.recetas}
                if r.programado else {"paciente": r.paciente_id, "estado": "omitido", "motivo": r.motivo}
                for r in resultados
            ]})
        return self.resumen_final(resultados, omitidos, fecha, encargado_id)

    def resumen_final(self, resultados, omitidos_revision, fecha, encargado_id):
        """Resumen sin JavaScript: «Se programaron X de Y» y los omitidos de la revisión y de la confirmación."""
        omitidos = [*omitidos_revision, *[(r.paciente_id, r.motivo) for r in resultados if not r.programado]]
        nombres = {persona.pk: _nombre_paciente(persona)
                   for persona in Paciente.objects.filter(pk__in=[pid for pid, _ in omitidos if pid])}
        total = len(resultados) + len(omitidos_revision)
        return self.render("programar_varios.html", {
            "resultado": {
                "programados": sum(r.programado for r in resultados), "total": total,
                "omitidos": [{"nombre": nombres.get(pid, "Paciente no disponible"), "motivo": motivo} for pid, motivo in omitidos],
                "url_programacion": _url_programacion(encargado_id, fecha),
            },
            "cantidad": total, "pestanas": self.pestanas("programacion"),
        })


class PendientesView(EntregasView):
    roles_permitidos = FARMACIA

    def get(self, request):
        form = FiltroEntregasForm(request.GET or None)
        filtros = form.filtros() if form.is_bound else {}
        page_obj = Paginator(consultas.pendientes_gestion(**filtros), 50).get_page(request.GET.get("page"))
        page_obj.object_list = _preparar_filas(list(page_obj.object_list))
        return self.render("pendientes.html", {
            "form": form, "page_obj": page_obj, "filtrado": bool(filtros),
            "no_descontadas": list(consultas.no_descontadas()[:200]), "pestanas": self.pestanas("pendientes"),
        })


class DetalleEntregaView(EntregasView):
    def entrega(self, pk):
        entrega = get_object_or_404(Entrega.objects.select_related("paciente", "anulada_por", "creado_por"), pk=pk)
        if services.es_encargado(self.request.user):
            if not entrega.intentos.filter(encargado=self.request.user).exists():
                raise PermissionDenied
        elif not tiene_rol(self.request.user, *FARMACIA):
            raise PermissionDenied
        return entrega

    def contexto(self, entrega, reasignar=None, anular=None):
        intentos = list(entrega.intentos.select_related("encargado", "registrado_por"))
        ultimo = intentos[-1] if intentos else None
        recetas = list(entrega.recetas.select_related("receta", "entrega_receta", "revisada_por"))
        contexto = {
            "entrega": entrega, "paciente": entrega.paciente, "intentos": intentos, "ultimo": ultimo, "recetas": recetas,
            "domicilio": consultas.domicilio_de(entrega.paciente),
            "domicilio_estado": consultas.estado_domicilio(entrega.paciente),
            "pestanas": self.pestanas("mis" if services.es_encargado(self.request.user) else
                                      "pendientes" if entrega.estado == Entrega.Estado.PENDIENTE_GESTION else "programacion"),
        }
        if entrega.abierta and tiene_rol(self.request.user, JEFA) and ultimo is not None:
            contexto["reasignar"] = reasignar or ReasignarForm(initial={
                "fecha": timezone.localdate(), "intento_id": ultimo.pk, "resultado_visto": ultimo.resultado,
                "operacion_id": uuid.uuid4()})
            contexto["anular"] = anular or AnularForm()
        return contexto

    def get(self, request, pk):
        return self.render("detalle.html", self.contexto(self.entrega(pk)))


class ReasignarView(DetalleEntregaView):
    roles_permitidos = GESTION

    def post(self, request, pk):
        entrega = self.entrega(pk)
        form = ReasignarForm(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                nuevo = services.reasignar(request.user, entrega.pk, fecha=datos["fecha"], encargado_id=datos["encargado"].pk,
                                           intento_id=datos["intento_id"], operacion_id=datos["operacion_id"],
                                           resultado_visto=datos["resultado_visto"])
            except ValidationError as error:
                form.add_error(None, _mensaje(error))
            except DatabaseError:
                form.add_error(None, "No pudimos reasignar la entrega. Inténtalo nuevamente.")
            else:
                messages.success(request, f"Entrega reasignada: intento {nuevo.numero} para el {nuevo.fecha_programada:%d/%m/%Y} "
                                          f"con {_nombre(nuevo.encargado)}.")
                return redirect("entregasapp:detalle", pk=entrega.pk)
        entrega.refresh_from_db()
        return self.render("detalle.html", self.contexto(entrega, reasignar=form))


class AnularView(DetalleEntregaView):
    roles_permitidos = GESTION

    def post(self, request, pk):
        entrega = self.entrega(pk)
        form = AnularForm(request.POST)
        if form.is_valid():
            try:
                services.anular_entrega(request.user, entrega.pk, form.cleaned_data["motivo"], form.cleaned_data["nota"])
            except ValidationError as error:
                form.add_error(None, _mensaje(error))
            except DatabaseError:
                form.add_error(None, "No pudimos anular la entrega. Inténtalo nuevamente.")
            else:
                messages.success(request, "Entrega anulada. Sus recetas ya se pueden dispensar en farmacia.")
                return redirect("entregasapp:detalle", pk=entrega.pk)
        entrega.refresh_from_db()
        return self.render("detalle.html", self.contexto(entrega, anular=form))


class RevisadaView(EntregasView):
    roles_permitidos = GESTION

    def post(self, request, pk):
        try:
            services.marcar_revisada(request.user, pk)
        except ValidationError as error:
            messages.error(request, _mensaje(error))
        except DatabaseError:
            messages.error(request, "No pudimos marcar la receta como revisada. Inténtalo nuevamente.")
        else:
            messages.success(request, "Receta marcada como revisada.")
        return redirect(reverse("entregasapp:pendientes") + "#no-descontadas")


# Encargado de terreno ---------------------------------------------------------------------------------------

def _preparar_intentos(intentos, hoy):
    for intento in intentos:
        paciente = intento.entrega.paciente
        intento.paciente = paciente
        intento.domicilio = consultas.domicilio_de(paciente)
        intento.domicilio_estado = consultas.estado_domicilio(paciente, intento.domicilio)
        intento.fotos = list(intento.domicilio.fotos.all()) if intento.domicilio else []
        intento.atrasada = intento.fecha_programada < hoy
        intento.lista_recetas = [
            {"codigo": v.receta.codigo, "numero": v.receta.entregas_completadas + 1, "maximo": v.receta.max_entregas}
            for v in intento.entrega.recetas.all()
        ]
    return intentos


def _preparar_ruta(ruta, hoy, *, controles=False):
    """Datos de las tarjetas de la ruta (spec 09). Con `controles`, una operación por parada para reordenar."""
    _preparar_intentos([parada.intento for parada in ruta.paradas] + list(ruta.proximas), hoy)
    for parada in ruta.paradas:
        parada.intento.parada = parada
        if controles:
            parada.operacion_id = uuid.uuid4()
    for intento in ruta.registradas:
        intento.paciente = intento.entrega.paciente
    return ruta


def _contexto_ruta(ruta):
    cantidad = ruta.sin_marcador
    return {
        "ruta": ruta, "posiciones": range(1, len(ruta.paradas) + 1),
        "sin_marcador_texto": f"{cantidad} visita sin marcador" if cantidad == 1 else f"{cantidad} visitas sin marcador",
    }


class MisEntregasView(SoloEncargadoView):
    """Ruta numerada del día (spec 09): paradas en orden, sin coordenadas, registradas hoy y próximas."""

    def get(self, request):
        hoy = timezone.localdate()
        ruta = _preparar_ruta(consultas.ruta_del_dia(request.user, hoy=hoy, incluir_proximas=True), hoy, controles=True)
        for intento in [parada.intento for parada in ruta.paradas] + list(ruta.proximas):
            if intento.domicilio is not None:  # RF-08-18: el botón de fotos de la tarjeta, solo para el encargado
                intento.fotos_form = contexto_fotos(
                    intento.domicilio, intento.fotos, prefijo=f"i{intento.pk}",
                    volver=reverse("entregasapp:mis") + f"#parada-{intento.pk}")
        return self.render("mis_entregas.html", {
            **_contexto_ruta(ruta), "hoy": hoy, "pestanas": self.pestanas("mis"), "controles": True,
            "restablecer": RestablecerOrdenForm(initial={"version": ruta.version, "operacion_id": uuid.uuid4()}),
            "teselas": mapa.teselas(),
        })


class MapaView(SoloEncargadoView):
    def get(self, request):
        hoy = timezone.localdate()
        ruta = _preparar_ruta(consultas.ruta_del_dia(request.user, hoy=hoy), hoy)
        return self.render("mapa.html", {
            **_contexto_ruta(ruta), "hoy": hoy, "pestanas": self.pestanas("mapa"), "datos_mapa": mapa.datos_mapa(ruta),
        })


class IrAView(SoloEncargadoView):
    """«Ir a esta parada»: la posición se calcula y se queda en el navegador; aquí solo va el destino."""

    def get(self, request, pk):
        intento = get_object_or_404(IntentoEntrega, pk=pk)
        if intento.encargado_id != request.user.pk:
            raise PermissionDenied
        hoy = timezone.localdate()
        ruta = consultas.ruta_del_dia(request.user, hoy=hoy)
        parada = ruta.parada_de(intento.pk)
        if parada is None:
            messages.info(request, "Esa visita ya no está en tu ruta de hoy. Revisa la lista actualizada.")
            return redirect("entregasapp:mis")
        if parada.punto is None:
            messages.info(request, "Esta visita no tiene coordenadas: usa la dirección y las referencias para llegar.")
            return redirect(reverse("entregasapp:mis") + f"#parada-{intento.pk}")
        _preparar_intentos([parada.intento], hoy)
        datos = mapa.datos_ir_a(parada)
        return self.render("ir_a.html", {
            "parada": parada, "intento": parada.intento, "datos_ir_a": datos, "hoy": hoy, "pestanas": self.pestanas("mis"),
            "geo": f"geo:{datos['lat']:.6f},{datos['lon']:.6f}", "coordenadas": f"{datos['lat']:.6f}, {datos['lon']:.6f}",
        })


def _quiere_json(request):
    return "application/json" in request.headers.get("Accept", "")


def _json_sin_cache(datos, status=200):
    respuesta = JsonResponse(datos, status=status)
    respuesta["Cache-Control"] = "no-store, private"
    return respuesta


def _orden_en_json(request, mensaje):
    """Estado del orden tras guardarlo (RF-09-17): la secuencia que manda el servidor, la versión nueva, el rótulo
    y el total, para que orden.js reordene la lista sin recargar. Sin datos personales en la secuencia."""
    hoy = timezone.localdate()
    ruta = consultas.ruta_del_dia(request.user, hoy=hoy)
    contexto = {"ruta": ruta}
    return _json_sin_cache({
        "ok": True, "mensaje": mensaje, "version": ruta.version, "manual": ruta.manual,
        "orden": [{"intento": parada.intento.pk, "numero": parada.numero, "numerada": parada.numerada}
                  for parada in ruta.paradas],
        "rotulo": render_to_string("entregas/_ruta_rotulo.html", contexto, request=request),
        "resumen": render_to_string("entregas/_ruta_resumen.html", contexto, request=request),
    })


class MoverParadaView(SoloEncargadoView):
    """Flechas y arrastre (RF-09-17). Sin JavaScript, POST y recarga; con `Accept: application/json`, responde
    el orden nuevo en JSON. El servicio y sus garantías (versión, operación idempotente) son los mismos."""

    def post(self, request):
        form = MoverParadaForm(request.POST)
        destino = reverse("entregasapp:mis")
        quiere_json = _quiere_json(request)
        if not form.is_valid():
            texto = "No se pudo cambiar el orden. Vuelve a intentarlo desde la lista."
            if quiere_json:
                return _json_sin_cache({"ok": False, "error": texto}, status=400)
            messages.error(request, texto)
            return redirect(destino)
        datos = form.cleaned_data
        try:
            services.mover_parada(request.user, datos["intento"], datos["destino"], datos["version"], datos["operacion_id"])
        except ValidationError as error:
            texto, status = _mensaje(error), 409 if _mensaje(error) == services.MENSAJE_ORDEN_CAMBIO else 400
        except DatabaseError:
            texto, status = "No pudimos guardar el orden. Inténtalo nuevamente.", 503
        else:
            texto = "Orden guardado. Desde ahora manda tu orden de hoy."
            if quiere_json:
                return _orden_en_json(request, texto)
            messages.success(request, texto)
            return redirect(f"{destino}#parada-{datos['intento']}")
        if quiere_json:
            return _json_sin_cache({"ok": False, "error": texto}, status=status)
        messages.error(request, texto)
        return redirect(f"{destino}#parada-{datos['intento']}")


# Tramo por camino y parada más cercana (spec 09, enmienda del 2026-11-15, RF-09-19, RF-09-21 y RF-09-22) -------
#
# La posición del encargado llega por POST (JSON con X-CSRFToken) solo para la solicitud en curso: vive en variables
# locales, nunca se guarda en la base, la sesión, la caché ni la auditoría, ni se escribe en registros ni en los
# mensajes de error. El destino del tramo se lee siempre de la ruta de hoy en la base; del cuerpo solo se toma el
# identificador de la visita. El límite de solicitudes cuenta por cuenta, nunca por posición.

LIMITE_POSICION_POR_MINUTO = 30
TEXTO_SIN_OSRM = "No se pudo calcular el tramo: el servidor de rutas no respondió. Sigue el orden de la lista."
# OSRM respondió, pero no hay camino por calles desde la posición (por ejemplo, fuera de la zona del mapa cargado).
TEXTO_SIN_CAMINO = ("No hay un camino por calles desde tu ubicación hasta esa parada. Si estás fuera de la zona "
                    "del mapa de rutas, no se puede calcular. Sigue el orden de la lista.")
TEXTO_SIN_CAMINO_CERCANA = ("No se pudo sugerir una parada: no hay un camino por calles desde tu ubicación. Si estás "
                            "fuera de la zona del mapa de rutas, no se puede calcular. Sigue el orden de la lista.")
TEXTO_SIN_OSRM_CERCANA = ("No se pudo sugerir una parada: el servidor de rutas no respondió. "
                          "La más cercana solo se mide por camino; sigue el orden de la lista.")
TEXTO_POSICION_INVALIDA = "No recibimos una posición válida. Vuelve a pulsar «Mostrar mi posición»."
TEXTO_LIMITE = "Pediste muchos cálculos seguidos. Espera un minuto y vuelve a intentarlo."


class PosicionNoValida(ValueError):
    pass


def _leer_posicion(cuerpo):
    """Punto con la posición del cuerpo JSON, o `PosicionNoValida` (sin repetir los valores recibidos)."""
    try:
        latitud, longitud = float(cuerpo["latitud"]), float(cuerpo["longitud"])
    except (KeyError, TypeError, ValueError):
        raise PosicionNoValida from None
    if not (math.isfinite(latitud) and math.isfinite(longitud) and -90 <= latitud <= 90 and -180 <= longitud <= 180):
        raise PosicionNoValida
    return Punto("posicion", latitud, longitud)


def _limite_superado(usuario):
    """30 solicitudes por minuto por encargado, con un contador en la caché que solo lleva el id de la cuenta."""
    clave = f"entregas:posicion:{usuario.pk}:{int(time.time() // 60)}"
    cache.add(clave, 0, 90)
    try:
        return cache.incr(clave) > LIMITE_POSICION_POR_MINUTO
    except ValueError:  # la clave venció entre add e incr
        cache.set(clave, 1, 90)
        return False


class PosicionView(SoloEncargadoView):
    """Base del tramo y la parada más cercana: solo el encargado (comprobación exacta), POST con CSRF y JSON."""

    http_method_names = ["post"]

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return _json_sin_cache({"error": "Solo el encargado de terreno calcula tramos de su ruta."}, status=403)
        return super().handle_no_permission()

    def post(self, request):
        if _limite_superado(request.user):
            return _json_sin_cache({"error": TEXTO_LIMITE}, status=429)
        try:
            cuerpo = json.loads(request.body or b"{}")
            if not isinstance(cuerpo, dict):
                raise PosicionNoValida
            posicion = _leer_posicion(cuerpo)
        except (ValueError, UnicodeDecodeError):
            return _json_sin_cache({"error": TEXTO_POSICION_INVALIDA}, status=400)
        ruta = consultas.ruta_del_dia(request.user, hoy=timezone.localdate())
        return self.responder(cuerpo, posicion, ruta)


class TramoView(PosicionView):
    """RF-09-21 y RF-09-23: tramo por camino desde la posición hasta una parada de la ruta de hoy."""

    def responder(self, cuerpo, posicion, ruta):
        try:
            intento_id = int(cuerpo.get("intento"))
        except (TypeError, ValueError):
            return _json_sin_cache({"error": "Elige una parada de tu ruta de hoy."}, status=400)
        parada = ruta.parada_con_punto(intento_id)
        if parada is None:
            return _json_sin_cache({"error": "Esa visita no está en tu ruta de hoy o no tiene coordenadas."}, status=404)
        try:
            tramo = osrm.tramo(posicion, parada.punto)
        except osrm.SinCamino:
            return _json_sin_cache({"error": TEXTO_SIN_CAMINO}, status=422)
        except osrm.OsrmNoDisponible:
            return _json_sin_cache({"error": TEXTO_SIN_OSRM}, status=503)
        return _json_sin_cache({
            "intento": parada.intento.pk, "numero": parada.numero, "distancia_m": round(tramo.distancia_m),
            "distancia_texto": formatear_distancia(tramo.distancia_m), "geometria": tramo.geometria,
        })


class ParadaCercanaView(PosicionView):
    """RF-09-22: la parada con coordenadas más cercana por camino desde la posición. Sin OSRM no sugiere nada."""

    def responder(self, cuerpo, posicion, ruta):
        con_punto = [parada for parada in ruta.paradas if parada.punto is not None]
        if not con_punto:
            return _json_sin_cache({"error": "No hay paradas con coordenadas en tu ruta de hoy."}, status=404)
        try:
            fila = osrm.tabla([posicion, *[parada.punto for parada in con_punto]], origenes=[0])[0]
        except osrm.SinCamino:
            return _json_sin_cache({"error": TEXTO_SIN_CAMINO_CERCANA}, status=422)
        except osrm.OsrmNoDisponible:
            return _json_sin_cache({"error": TEXTO_SIN_OSRM_CERCANA}, status=503)
        distancia, elegida = min(((fila[i + 1], parada) for i, parada in enumerate(con_punto)),
                                 key=lambda par: (par[0], par[1].intento.pk))
        return _json_sin_cache({
            "intento": elegida.intento.pk, "numero": elegida.numero, "distancia_m": round(distancia),
            "distancia_texto": formatear_distancia(distancia),
            "es_primera": ruta.paradas[0].intento.pk == elegida.intento.pk, "version": ruta.version,
        })


class RestablecerOrdenView(SoloEncargadoView):
    def post(self, request):
        form = RestablecerOrdenForm(request.POST)
        if not form.is_valid():
            messages.error(request, "No se pudo volver al orden sugerido. Vuelve a intentarlo desde la lista.")
            return redirect("entregasapp:mis")
        try:
            orden = services.restablecer_orden(request.user, form.cleaned_data["version"], form.cleaned_data["operacion_id"])
        except ValidationError as error:
            messages.error(request, _mensaje(error))
        except DatabaseError:
            messages.error(request, "No pudimos volver al orden sugerido. Inténtalo nuevamente.")
        else:
            messages.success(request, "Volviste al orden sugerido." if orden else "Ya estabas en el orden sugerido.")
        return redirect("entregasapp:mis")


class RutasView(EntregasView):
    """Consulta de la Q.F. y el superusuario (spec 09, RF-09-10): ruta de un encargado por fecha, sin acciones."""

    roles_permitidos = GESTION

    def get(self, request):
        hoy = timezone.localdate()
        filtrado = "encargado" in request.GET or "fecha" in request.GET
        form = RutaForm(request.GET if filtrado else None, initial={"fecha": hoy})
        contexto = {"form": form, "hoy": hoy, "pestanas": self.pestanas("rutas"), "consulta": True}
        if filtrado and form.is_valid():
            encargado, fecha = form.cleaned_data["encargado"], form.cleaned_data["fecha"]
            ruta = _preparar_ruta(consultas.ruta_del_dia(encargado, fecha, hoy), hoy)
            contexto.update(_contexto_ruta(ruta), encargado=encargado, encargado_nombre=_nombre(encargado),
                            datos_mapa=mapa.datos_mapa(ruta, consulta=True), teselas=mapa.teselas())
        return self.render("rutas.html", contexto, status=400 if filtrado and not form.is_valid() else 200)


class RegistroView(SoloEncargadoView):
    def intento(self, pk):
        intento = get_object_or_404(IntentoEntrega.objects.select_related("entrega__paciente"), pk=pk)
        if intento.encargado_id != self.request.user.pk:
            raise PermissionDenied
        return intento

    def contexto(self, intento, entregada=None, no_entregada=None):
        hoy = timezone.localdate()
        _preparar_intentos([intento], hoy)
        return {
            "errores": [f for f in (entregada, no_entregada) if f is not None and f.non_field_errors()],
            "intento": intento, "hoy": hoy, "pestanas": self.pestanas("mis"),
            "registrable": intento.resultado == IntentoEntrega.Resultado.PENDIENTE and intento.fecha_programada <= hoy,
            "entregada": entregada or EntregadaForm(initial={"operacion_id": uuid.uuid4()}),
            "no_entregada": no_entregada or NoEntregadaForm(initial={"operacion_id": uuid.uuid4()}),
            "foco": self.request.GET.get("resultado", ""),
        }

    def get(self, request, pk):
        return self.render("registro.html", self.contexto(self.intento(pk)))


class InicioTrasladoView(SoloEncargadoView):
    http_method_names = ["post"]

    def post(self, request, pk):
        try:
            registrado = services.iniciar_traslado(request.user, pk)
        except ValidationError as error:
            messages.error(request, _mensaje(error))
        except DatabaseError:
            messages.error(request, "No se pudo guardar el inicio del traslado. Vuelve a intentarlo.")
        else:
            if registrado:
                messages.success(request, "Traslado iniciado.")
            else:
                messages.info(request, "Este traslado ya estaba iniciado.")
        return redirect("entregasapp:mis")


class EntregadaView(RegistroView):
    def post(self, request, pk):
        intento = self.intento(pk)
        form = EntregadaForm(request.POST)
        if form.is_valid():
            try:
                resultado = services.registrar_entregada(request.user, intento.pk, form.cleaned_data["operacion_id"])
            except ValidationError as error:
                form.add_error(None, _mensaje(error))
            except DatabaseError:
                form.add_error(None, "No se registró la entrega. Reintenta con este mismo formulario.")
            else:
                vinculos = list(RecetaEntrega.objects.filter(entrega_id=intento.entrega_id))
                descontadas = sum(v.resultado == RecetaEntrega.Resultado.DESCONTADA for v in vinculos)
                texto = f"Entrega registrada. Se descontaron {descontadas} de {len(vinculos)} receta(s)."
                if descontadas < len(vinculos):
                    texto += " Las demás quedaron para revisión de la Q.F."
                if resultado.repetido:
                    texto = "Esta entrega ya estaba registrada. No se descontó otra vez."
                messages.success(request, texto)
                return redirect("entregasapp:mis")
        intento.refresh_from_db()
        return self.render("registro.html", self.contexto(intento, entregada=form), status=400)


class NoEntregadaView(RegistroView):
    def post(self, request, pk):
        intento = self.intento(pk)
        form = NoEntregadaForm(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                resultado = services.registrar_no_entregada(request.user, intento.pk, datos["motivo"], datos["nota"], datos["operacion_id"])
            except ValidationError as error:
                form.add_error(None, _mensaje(error))
            except DatabaseError:
                form.add_error(None, "No se registró el resultado. Reintenta con este mismo formulario.")
            else:
                messages.success(request, "Resultado registrado: no entregada. La Q.F. la verá en «Pendientes de gestión»."
                                 if not resultado.repetido else "Este resultado ya estaba registrado.")
                return redirect("entregasapp:mis")
        intento.refresh_from_db()
        return self.render("registro.html", self.contexto(intento, no_entregada=form), status=400)


# Domicilios -------------------------------------------------------------------------------------------------

class DomiciliosView(EntregasView):
    def get(self, request):
        datos = {clave: request.GET[clave] for clave in ("sector", "estado") if request.GET.get(clave)}
        return self.mostrar(FiltroDomiciliosForm(datos or None))

    def post(self, request):
        return self.mostrar(FiltroDomiciliosForm(request.POST))

    def mostrar(self, form):
        filtros, pagina = {}, 1
        if form.is_bound and form.is_valid():
            filtros = {clave: form.cleaned_data[clave] for clave in ("buscar", "sector", "estado")}
            pagina = form.cleaned_data["pagina"] or 1
        page_obj = Paginator(consultas.elegibles(**filtros), 30).get_page(pagina)
        page_obj.object_list = list(page_obj.object_list)
        for paciente in page_obj.object_list:
            paciente.domicilio_estado = consultas.estado_domicilio(paciente, consultas.domicilio_de(paciente))
            paciente.domicilio_registrado = consultas.domicilio_de(paciente)
        return self.render("domicilios.html", {
            "form": form, "page_obj": page_obj, "filtros": filtros, "pestanas": self.pestanas("domicilios"),
        })


class DomicilioView(EntregasView):
    def paciente(self, pk):
        return get_object_or_404(Paciente, pk=pk)

    def contexto(self, paciente, form=None):
        domicilio = consultas.domicilio_de(paciente)
        puede_editar = tiene_rol(self.request.user, JEFA, ENCARGADO)
        elegible = consultas.es_elegible(paciente)
        contexto = {
            "paciente": paciente, "domicilio": domicilio, "estado": consultas.estado_domicilio(paciente, domicilio),
            "elegible": elegible, "excepcion": consultas.excepcion_vigente(paciente),
            "abierta": consultas.entrega_abierta(paciente), "fotos": list(domicilio.fotos.all()) if domicilio else [],
            "puede_editar": puede_editar and (elegible or domicilio is not None),
            "puede_verificar": services.es_encargado(self.request.user) and domicilio is not None,
            "pestanas": self.pestanas("domicilios"), "maximo_fotos": FotoDomicilio.MAXIMO,
        }
        if contexto["puede_editar"]:
            contexto["form"] = form or DomicilioForm.desde_domicilio(domicilio, paciente)
            contexto["datos_usar_mapa"] = mapa.datos_usar_mapa()  # RF-09-25: «Usar mapa», sin datos del paciente
        if domicilio is not None and puede_editar:  # RF-08-18: gestionan fotos el encargado, la Q.F. y el superusuario
            volver = reverse("entregasapp:domicilio", args=[paciente.pk]) + "#fotos"
            contexto["fotos_form"] = contexto_fotos(domicilio, contexto["fotos"], prefijo="domicilio", volver=volver)
        if domicilio is not None:
            contexto["verificar_form"] = VersionForm(initial={"version": domicilio.version})
            if domicilio.latitud is not None:  # spec 09 (RF-09-11): mapa pequeño de solo lectura
                contexto["datos_punto"] = mapa.datos_punto(domicilio)
        return contexto

    def get(self, request, pk):
        return self.render("domicilio.html", self.contexto(self.paciente(pk)))

    def post(self, request, pk):
        if not tiene_rol(request.user, JEFA, ENCARGADO):
            raise PermissionDenied
        paciente = self.paciente(pk)
        form = DomicilioForm(request.POST)
        if form.is_valid():
            datos = dict(form.cleaned_data)
            version = datos.pop("version")
            try:
                services.guardar_domicilio(request.user, paciente.pk, datos, version=version)
            except ValidationError as error:
                form.add_error(None, _mensaje(error, "Revisa los datos del domicilio."))
            except DatabaseError:
                form.add_error(None, "No pudimos guardar el domicilio. Inténtalo nuevamente.")
            else:
                messages.success(request, "Domicilio guardado.")
                return redirect("entregasapp:domicilio", pk=paciente.pk)
        return self.render("domicilio.html", self.contexto(paciente, form=form), status=400)


class VerificarView(SoloEncargadoView):
    def post(self, request, pk):
        domicilio = get_object_or_404(Domicilio, pk=pk)
        form = VersionForm(request.POST)
        try:
            if not form.is_valid():
                raise ValidationError("El domicilio cambió; revisa los datos nuevos.")
            services.verificar_domicilio(request.user, domicilio.pk, form.cleaned_data["version"])
        except ValidationError as error:
            messages.error(request, _mensaje(error))
        except DatabaseError:
            messages.error(request, "No pudimos marcar el domicilio. Inténtalo nuevamente.")
        else:
            messages.success(request, "Domicilio marcado como verificado.")
        return redirect("entregasapp:domicilio", pk=domicilio.paciente_id)


class FotoView(EntregasView):
    def get(self, request, pk):
        foto = get_object_or_404(FotoDomicilio, pk=pk)
        try:
            archivo = fotos.abrir(foto.archivo.name)
        except OSError:
            raise Http404 from None
        respuesta = FileResponse(archivo, content_type="image/jpeg")
        respuesta["Content-Disposition"] = "inline"
        respuesta["X-Content-Type-Options"] = "nosniff"
        respuesta["Cache-Control"] = "no-store, private"
        return respuesta


def contexto_fotos(domicilio, fotos_actuales, *, prefijo, volver, form=None, error=None, error_foto=None):
    """Datos del formulario de fotos (modal o página aparte), con lo que se eligió si hubo un error."""
    descripciones = form.descripciones() if form is not None else {}
    marcadas = {str(valor) for valor in form.borrar()} if form is not None else set()
    libres = FotoDomicilio.MAXIMO - len(fotos_actuales) + len([f for f in fotos_actuales if str(f.pk) in marcadas])
    return {
        "domicilio": domicilio, "fotos": fotos_actuales, "prefijo": prefijo, "volver": volver,
        "mostradas": ",".join(str(foto.pk) for foto in fotos_actuales), "marcadas": marcadas,
        "espacios": [{"numero": n, "descripcion": descripciones.get(n, ""), "visible": n <= libres,
                      "error": error if error_foto == n else ""} for n in range(1, FotosForm.ESPACIOS + 1)],
        "error_general": error if error and not error_foto else "", "error_foto": error_foto,
        "maximo_fotos": FotoDomicilio.MAXIMO,
    }


class FotosView(EntregasView):
    """RF-08-18: registrar o gestionar las fotos de un domicilio en un solo guardado, todo o nada.

    Con JavaScript, el modal envía el POST con `Accept: application/json` y recibe el resultado en JSON. Sin
    JavaScript, el botón abre esta página con el mismo formulario y el POST redirige a la página de origen.
    """

    roles_permitidos = (JEFA, ENCARGADO)

    def domicilio(self, pk):
        return get_object_or_404(Domicilio.objects.select_related("paciente"), pk=pk)

    def destino(self, domicilio, valor):
        if valor and valor.startswith("/") and url_has_allowed_host_and_scheme(
                valor, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            return valor
        return reverse("entregasapp:domicilio", args=[domicilio.paciente_id]) + "#fotos"

    def pagina(self, domicilio, volver, *, status=200, **opciones):
        datos = contexto_fotos(domicilio, list(domicilio.fotos.all()), prefijo="pagina", volver=volver, **opciones)
        return self.render("fotos.html", {
            "fotos_contexto": datos, "fotos": datos["fotos"], "domicilio": domicilio, "paciente": domicilio.paciente,
            "maximo_fotos": FotoDomicilio.MAXIMO, "pestanas": self.pestanas("domicilios"),
        }, status=status)

    def get(self, request, pk):
        domicilio = self.domicilio(pk)
        return self.pagina(domicilio, self.destino(domicilio, request.GET.get("volver")))

    def post(self, request, pk):
        domicilio = self.domicilio(pk)
        quiere_json = "application/json" in request.headers.get("Accept", "")
        form = FotosForm(request.POST, request.FILES)
        volver = self.destino(domicilio, request.POST.get("volver"))
        error_foto = None
        try:
            if not form.is_valid():
                raise ValidationError(services.MENSAJE_FOTOS_CAMBIARON)
            services.gestionar_fotos(request.user, domicilio.pk, mostradas=form.cleaned_data["mostradas"],
                                     borrar=form.borrar(), nuevas=form.nuevas())
        except services.ErrorFoto as falla:
            error, error_foto = _mensaje(falla), falla.numero
        except ValidationError as falla:
            error = _mensaje(falla)
        except DatabaseError:
            error = "No pudimos guardar las fotos y no se aplicó ningún cambio. Inténtalo nuevamente."
        else:
            messages.success(request, "Fotos guardadas sin metadatos ni ubicación.")
            if quiere_json:
                return JsonResponse({"ok": True, "volver": volver})
            return redirect(volver)
        if quiere_json:
            return JsonResponse({"ok": False, "error": error, "foto": error_foto}, status=400)
        if not error_foto:
            form = None  # el conjunto cambió: se muestra el estado actual, sin lo elegido
        elif form.files:
            error += " Vuelve a elegir los archivos: el navegador no los conserva al recargar la página."
        return self.pagina(domicilio, volver, status=400, form=form, error=error, error_foto=error_foto)


# Excepciones de reparto -------------------------------------------------------------------------------------

class ExcepcionesView(EntregasView):
    roles_permitidos = GESTION

    def contexto(self, busqueda=None, resultados=None, form=None):
        vigentes = list(InscripcionReparto.objects.filter(retirada_en__isnull=True)
                        .select_related("paciente", "creado_por").order_by("paciente__apellidos", "paciente__nombres"))
        return {"busqueda": busqueda or BusquedaForm(), "resultados": resultados, "form": form, "vigentes": vigentes,
                "pestanas": self.pestanas("programacion")}

    def get(self, request):
        contexto = self.contexto()
        preseleccion = request.GET.get("paciente")
        if preseleccion and preseleccion.isdigit():
            paciente = Paciente.objects.filter(pk=int(preseleccion)).first()
            if paciente:
                contexto["resultados"] = self.candidatos(Paciente.objects.filter(pk=paciente.pk))
        return self.render("excepciones.html", contexto)

    def candidatos(self, pacientes):
        hoy = timezone.localdate()
        resultado = []
        for paciente in pacientes[:10]:
            paciente.ya_elegible = paciente.requiere_despacho_en(hoy)
            paciente.excepcion = consultas.excepcion_vigente(paciente)
            paciente.formulario = ExcepcionForm(initial={"paciente": paciente.pk}, prefix=f"p{paciente.pk}")
            resultado.append(paciente)
        return resultado

    def post(self, request):
        if request.POST.get("accion") == "buscar":
            busqueda = BusquedaForm(request.POST)
            resultados = []
            if busqueda.is_valid() and busqueda.cleaned_data["buscar"]:
                pacientes = consultas.filtrar_busqueda(Paciente.objects.order_by("apellidos", "nombres", "pk"),
                                                       busqueda.cleaned_data["buscar"])
                resultados = self.candidatos(pacientes)
            return self.render("excepciones.html", self.contexto(busqueda=busqueda, resultados=resultados))
        prefijo = request.POST.get("prefijo", "")
        form = ExcepcionForm(request.POST, prefix=prefijo if prefijo.startswith("p") and prefijo[1:].isdigit() else None)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                services.inscribir_excepcion(request.user, datos["paciente"], datos["motivo"], datos["nota"])
            except ValidationError as error:
                form.add_error(None, _mensaje(error))
            except DatabaseError:
                form.add_error(None, "No pudimos inscribir la excepción. Inténtalo nuevamente.")
            else:
                messages.success(request, "Excepción de reparto inscrita. El paciente ya aparece en Domicilios y en Programación.")
                return redirect("entregasapp:excepciones")
        identificador = form.cleaned_data.get("paciente")  # solo si el campo vino válido (entero)
        paciente = Paciente.objects.filter(pk=identificador).first() if identificador else None
        resultados = []
        if paciente:
            resultados = self.candidatos(Paciente.objects.filter(pk=paciente.pk))
            resultados[0].formulario = form
        return self.render("excepciones.html", self.contexto(resultados=resultados), status=400)


class ExcepcionRetirarView(EntregasView):
    roles_permitidos = GESTION

    def post(self, request, pk):
        try:
            services.retirar_excepcion(request.user, pk)
        except ValidationError as error:
            messages.error(request, _mensaje(error))
        except DatabaseError:
            messages.error(request, "No pudimos retirar la excepción. Inténtalo nuevamente.")
        else:
            messages.success(request, "Excepción retirada. Si tenía una entrega abierta, sigue abierta hasta que la gestiones.")
        return redirect("entregasapp:excepciones")
