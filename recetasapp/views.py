"""Pantallas privadas del padrón y recetas simuladas."""

import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from coreapp.mixins import RolRequeridoMixin, tiene_rol
from coreapp.roles import JEFA, TECNICO
from coreapp.utils.rut import normalizar_rut
from .forms import BusquedaPacienteForm, BusquedaRecetaForm, EntregaForm, ImportacionForm, RecetaForm
from .importacion import filas_demo, generar_archivo, importar_padron
from . import consultas, presentacion, tablero
from .models import ImportacionPadron, Paciente, Receta
from .services import crear_receta, registrar_entrega


@method_decorator(never_cache, name="dispatch")
@method_decorator(sensitive_post_parameters(), name="dispatch")
class FarmaciaView(RolRequeridoMixin, View):
    roles_permitidos = (JEFA, TECNICO)

    def render(self, template, contexto, **kwargs):
        respuesta = render(self.request, "recetas/" + template, contexto, **kwargs)
        # Los formularios necesitan conservar su origen para la validación
        # CSRF. No enviar el referente a destinos externos.
        respuesta.headers["Referrer-Policy"] = "same-origin"
        return respuesta


class PacientesView(FarmaciaView):
    def get(self, request):
        # Los enlaces del resumen llegan con el filtro en la URL; la búsqueda por RUT nunca viaja así.
        datos = {"filtro": request.GET["filtro"]} if "filtro" in request.GET else None
        return self.mostrar(BusquedaPacienteForm(datos))

    def post(self, request):
        return self.mostrar(BusquedaPacienteForm(request.POST))

    def mostrar(self, form):
        pacientes = Paciente.objects.order_by("apellidos", "nombres", "pk")
        pagina, buscar, filtro = 1, "", ""
        if form.is_bound:
            if form.is_valid():
                buscar, pagina = form.cleaned_data["buscar"], form.cleaned_data["pagina"] or 1
                filtro = form.cleaned_data["filtro"]
                if filtro == "sin_vigente":
                    pacientes = consultas.pacientes_sin_vigente().order_by("apellidos", "nombres", "pk")
                if buscar:
                    condicion = Q(nombres__icontains=buscar) | Q(apellidos__icontains=buscar)
                    try:
                        condicion |= Q(rut=normalizar_rut(buscar))
                    except ValidationError:
                        pass
                    pacientes = pacientes.filter(condicion)
            else:
                pacientes = pacientes.none()
        pacientes = pacientes.prefetch_related(Prefetch("recetas", queryset=Receta.objects.order_by("-fecha_inicio", "-pk")))
        page_obj = Paginator(pacientes, 20).get_page(pagina)
        page_obj.object_list = list(page_obj.object_list)
        for paciente in page_obj.object_list:
            paciente.resumen = presentacion.resumen_paciente(paciente.recetas.all())
        return self.render("pacientes_lista.html", {
            "form": form, "page_obj": page_obj, "buscar": buscar, "filtro": filtro,
            "filtros": [{"clave": "", "texto": "Todos"}] + [{"clave": clave, "texto": texto} for clave, texto in consultas.FILTROS_PACIENTE],
        })


class RecetasView(FarmaciaView):
    """Tablero de recetas (cifras, gráficos y ranking) y, debajo, todas las recetas con su situación."""

    def get(self, request):
        datos = {"situacion": request.GET["situacion"]} if "situacion" in request.GET else None
        return self.mostrar(BusquedaRecetaForm(datos), request)

    def post(self, request):
        return self.mostrar(BusquedaRecetaForm(request.POST), request)

    def mostrar(self, form, request):
        hoy = timezone.localdate()
        recetas = Receta.objects.select_related("paciente")
        pagina, buscar, situacion = 1, "", ""
        if form.is_bound:
            if form.is_valid():
                buscar, pagina = form.cleaned_data["buscar"], form.cleaned_data["pagina"] or 1
                situacion = form.cleaned_data["situacion"]
                recetas = consultas.filtrar_recetas(recetas, situacion, hoy)
                if buscar:
                    condicion = Q(codigo__icontains=buscar) | Q(paciente__nombres__icontains=buscar) | Q(paciente__apellidos__icontains=buscar)
                    try:
                        condicion |= Q(paciente__rut=normalizar_rut(buscar))
                    except ValidationError:
                        pass
                    recetas = recetas.filter(condicion)
            else:
                recetas = recetas.none()
        # Lo que vence primero va arriba cuando se mira lo vigente; en el resto, lo más reciente.
        orden = ("fecha_fin_exclusiva", "pk") if situacion in ("vigente", "por_vencer") else ("-fecha_inicio", "-pk")
        page_obj = Paginator(recetas.order_by(*orden), 20).get_page(pagina)
        page_obj.object_list = [presentacion.preparar_fila_receta(receta, hoy) for receta in page_obj.object_list]
        conteos = consultas.contar_recetas(hoy)
        pestanas = [{"clave": "", "texto": "Todas", "cantidad": conteos["total"]}]
        pestanas += [{"clave": clave, "texto": texto, "cantidad": conteos[clave]} for clave, texto in consultas.FILTROS_RECETA]
        # El periodo del gráfico de entregas viaja en la URL: no es un dato personal.
        panel = tablero.armar(hoy, tablero.periodo_valido(request.GET.get("periodo")))
        return self.render("recetas_lista.html", {
            "form": form, "page_obj": page_obj, "buscar": buscar, "situacion": situacion, "pestanas": pestanas, "tablero": panel,
        })


class PacienteView(FarmaciaView):
    def get(self, request, pk):
        paciente = get_object_or_404(Paciente, pk=pk)
        recetas = [presentacion.preparar_receta(receta) for receta in paciente.recetas.order_by("-fecha_inicio", "-pk")]
        recetas.sort(key=lambda receta: receta.situacion["clave"] != "vigente")
        return self.render("paciente_detalle.html", {"paciente": paciente, "recetas": recetas, "puede_crear": tiene_rol(request.user, JEFA)})


class RecetaView(FarmaciaView):
    def get(self, request, pk):
        receta = get_object_or_404(Receta.objects.select_related("paciente", "receta_anterior"), pk=pk)
        entregas = list(receta.entregas.select_related("creado_por"))
        presentacion.preparar_receta(receta, entregas)
        # El sello nuevo se estampa solo cuando la persona acaba de confirmar la entrega.
        sello_nuevo = any("entrega-sellada" in mensaje.tags.split() for mensaje in messages.get_messages(request))
        return self.render("receta_detalle.html", {
            "receta": receta, "estado": receta.estado, "entregas": entregas,
            "vigencia": presentacion.linea_vigencia(receta), "sello_nuevo": sello_nuevo,
            "puede_crear": tiene_rol(request.user, JEFA), "puede_entregar": tiene_rol(request.user, TECNICO),
        })


class CrearRecetaView(FarmaciaView):
    roles_permitidos = (JEFA,)

    def preparar(self, pk=None):
        self.anterior = get_object_or_404(Receta.objects.select_related("paciente"), pk=pk) if pk else None
        return self.anterior.paciente if self.anterior else None

    def get(self, request, pk=None):
        paciente = self.preparar(pk)
        return self.render("receta_form.html", {"form": RecetaForm(paciente=paciente), "anterior": self.anterior})

    def post(self, request, pk=None):
        paciente = self.preparar(pk)
        form = RecetaForm(request.POST, paciente=paciente)
        if form.is_valid():
            datos = dict(form.cleaned_data)
            datos["paciente_id"] = datos.pop("paciente").pk
            try:
                receta = crear_receta(request.user, anterior_id=pk, **datos)
            except ValidationError:
                form.add_error(None, "No se guardó la receta. Revisa código, fechas y cupo.")
            except DatabaseError:
                form.add_error(None, "No pudimos guardar la receta. Inténtalo nuevamente.")
            else:
                messages.success(request, "La receta simulada se guardó.")
                return redirect("recetasapp:receta_detalle", pk=receta.pk)
        return self.render("receta_form.html", {"form": form, "anterior": self.anterior})


class ConfirmarEntregaView(FarmaciaView):
    roles_permitidos = (TECNICO,)

    def get(self, request, pk):
        receta = get_object_or_404(Receta.objects.select_related("paciente"), pk=pk)
        presentacion.preparar_receta(receta, proxima=True)
        from .confirmacion import preparar_contexto
        operacion = uuid.uuid4()
        return self.render("entrega_confirmar.html", {"receta": receta, "estado": receta.estado,
            "form": EntregaForm(initial={"operacion_id": operacion, "contexto": preparar_contexto(request.user, receta, operacion)})})

    def post(self, request, pk):
        receta = get_object_or_404(Receta.objects.select_related("paciente"), pk=pk)
        form = EntregaForm(request.POST)
        if form.is_valid():
            try:
                from .confirmacion import leer_contexto
                contexto = leer_contexto(request.user, receta, form.cleaned_data["operacion_id"], form.cleaned_data["contexto"])
                entrega = registrar_entrega(request.user, receta.pk, form.cleaned_data["operacion_id"], **contexto)
            except ValidationError as error:
                form.add_error(None, error)
            except DatabaseError:
                form.add_error(None, "La entrega no fue confirmada. Reintenta con este mismo formulario.")
            else:
                if entrega.operacion_id == form.cleaned_data["operacion_id"]:
                    messages.success(request, "Entrega del ciclo confirmada.", extra_tags="entrega-sellada")
                else:
                    messages.info(request, "La entrega de esta atención ya estaba registrada. No se descontó otra entrega.")
                return redirect("recetasapp:receta_detalle", pk=pk)
        receta.refresh_from_db()
        presentacion.preparar_receta(receta, proxima=True)
        return self.render("entrega_confirmar.html", {"receta": receta, "estado": receta.estado, "form": form})


class ImportacionesView(FarmaciaView):
    roles_permitidos = (JEFA,)

    def get(self, request):
        page_obj = Paginator(ImportacionPadron.objects.select_related("creado_por"), 20).get_page(request.GET.get("page"))
        page_obj.object_list = list(page_obj.object_list)
        for carga in page_obj.object_list:
            carga.categorias = presentacion.categorias_carga(carga)
        return self.render("importacion_lista.html", {"page_obj": page_obj})


class NuevaImportacionView(FarmaciaView):
    roles_permitidos = (JEFA,)

    def get(self, request):
        return self.render("importacion_form.html", {"form": ImportacionForm()})

    def post(self, request):
        form = ImportacionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                carga = importar_padron(request.user, form.cleaned_data["archivo"], form.cleaned_data["formato"])
            except (ValidationError, DatabaseError):
                form.add_error(None, "No pudimos completar el registro de la carga. Revisa la bitácora antes de reintentar.")
            else:
                return redirect("recetasapp:importacion_detalle", referencia=carga.referencia)
        return self.render("importacion_form.html", {"form": form})


class ImportacionView(FarmaciaView):
    roles_permitidos = (JEFA,)

    def get(self, request, referencia):
        carga = get_object_or_404(ImportacionPadron.objects.select_related("creado_por"), referencia=referencia)
        solo_rechazadas = request.GET.get("estado") == "rechazada"
        resultados = carga.resultados.filter(estado="rechazada") if solo_rechazadas else carga.resultados.all()
        page_obj = Paginator(resultados, 50).get_page(request.GET.get("page"))
        page_obj.object_list = [presentacion.preparar_fila(resultado) for resultado in page_obj.object_list]
        return self.render("importacion_detalle.html", {
            "carga": carga, "page_obj": page_obj, "solo_rechazadas": solo_rechazadas,
            "categorias": presentacion.categorias_carga(carga),
        })


class PlantillaView(FarmaciaView):
    roles_permitidos = (JEFA,)

    def get(self, request, formato):
        if formato not in ("csv", "xlsx"):
            from django.http import Http404
            raise Http404
        contenido = generar_archivo(formato, filas_demo(cantidad=1))
        respuesta = HttpResponse(contenido, content_type="text/csv; charset=utf-8" if formato == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        respuesta["Content-Disposition"] = f'attachment; filename="plantilla-padron-sintetico.{formato}"'
        respuesta["Cache-Control"] = "no-store"
        return respuesta
