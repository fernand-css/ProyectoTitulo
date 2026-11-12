"""Pantallas privadas del reparto a domicilio (spec 08).

La matriz de permisos se aplica dos veces: aquí, con `RolRequeridoMixin` o la comprobación exacta del
encargado, y otra vez en `entregasapp.services`. Ocultar un botón nunca es el control. Todas las respuestas
llevan `Cache-Control: no-store` y las URL solo contienen identificadores internos (nunca RUT ni nombres).
"""

import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from coreapp.mixins import RolRequeridoMixin, tiene_rol
from coreapp.roles import ENCARGADO, JEFA, TECNICO
from recetasapp.models import Paciente
from recetasapp.services import evaluar_elegibilidad
from . import consultas, fotos, mapa, services
from .forms import (
    AnularForm, BusquedaForm, DomicilioForm, EntregadaForm, ExcepcionForm, FiltroDomiciliosForm, FiltroEntregasForm,
    FotoForm, MoverParadaForm, NoEntregadaForm, ProgramarForm, ReasignarForm, RestablecerOrdenForm, RutaForm, VersionForm,
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
            return self.render("programar.html", {"busqueda": BusquedaForm(), "pestanas": self.pestanas("programacion")})
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
        busqueda = BusquedaForm(request.POST)
        pacientes = []
        if busqueda.is_valid() and busqueda.cleaned_data["buscar"]:
            pacientes = list(consultas.elegibles(buscar=busqueda.cleaned_data["buscar"])[:20])
            abiertas = set(Entrega.objects.filter(paciente__in=pacientes, estado__in=Entrega.ABIERTAS).values_list("paciente_id", flat=True))
            for paciente in pacientes:
                paciente.tiene_abierta = paciente.pk in abiertas
                paciente.domicilio_estado = consultas.estado_domicilio(paciente, consultas.domicilio_de(paciente))
        return self.render("programar.html", {"busqueda": busqueda, "resultados": pacientes, "buscado": True,
                                              "pestanas": self.pestanas("programacion")})


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
        return self.render("mis_entregas.html", {
            **_contexto_ruta(ruta), "hoy": hoy, "pestanas": self.pestanas("mis"), "controles": True,
            "restablecer": RestablecerOrdenForm(initial={"version": ruta.version, "operacion_id": uuid.uuid4()}),
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


class MoverParadaView(SoloEncargadoView):
    def post(self, request):
        form = MoverParadaForm(request.POST)
        destino = reverse("entregasapp:mis")
        if not form.is_valid():
            messages.error(request, "No se pudo cambiar el orden. Vuelve a intentarlo desde la lista.")
            return redirect(destino)
        datos = form.cleaned_data
        try:
            services.mover_parada(request.user, datos["intento"], datos["destino"], datos["version"], datos["operacion_id"])
        except ValidationError as error:
            messages.error(request, _mensaje(error))
        except DatabaseError:
            messages.error(request, "No pudimos guardar el orden. Inténtalo nuevamente.")
        else:
            messages.success(request, "Orden guardado. Desde ahora manda tu orden de hoy.")
        return redirect(f"{destino}#parada-{datos['intento']}")


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
                            datos_mapa=mapa.datos_mapa(ruta, consulta=True))
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

    def contexto(self, paciente, form=None, foto_form=None):
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
            if domicilio is not None:
                contexto["foto_form"] = foto_form or FotoForm()
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


class FotoAgregarView(EntregasView):
    roles_permitidos = (JEFA, ENCARGADO)

    def post(self, request, pk):
        domicilio = get_object_or_404(Domicilio, pk=pk)
        form = FotoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                services.agregar_foto(request.user, domicilio.pk, form.cleaned_data["foto"], form.cleaned_data["descripcion"])
            except ValidationError as error:
                form.add_error("foto", _mensaje(error))
            except DatabaseError:
                form.add_error(None, "No pudimos guardar la foto. Inténtalo nuevamente.")
            else:
                messages.success(request, "Foto agregada sin metadatos ni ubicación.")
                return redirect(reverse("entregasapp:domicilio", args=[domicilio.paciente_id]) + "#fotos")
        paciente = Paciente.objects.get(pk=domicilio.paciente_id)
        return self.render("domicilio.html", DomicilioView(request=request).contexto(paciente, foto_form=form), status=400)


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


class FotoEliminarView(EntregasView):
    roles_permitidos = (JEFA, ENCARGADO)

    def post(self, request, pk):
        foto = get_object_or_404(FotoDomicilio.objects.select_related("domicilio"), pk=pk)
        paciente_id = foto.domicilio.paciente_id
        try:
            services.eliminar_foto(request.user, foto.pk)
        except ValidationError as error:
            messages.error(request, _mensaje(error))
        except DatabaseError:
            messages.error(request, "No pudimos borrar la foto. Inténtalo nuevamente.")
        else:
            messages.success(request, "Foto borrada.")
        return redirect(reverse("entregasapp:domicilio", args=[paciente_id]) + "#fotos")


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
