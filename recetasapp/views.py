"""Pantallas privadas del padrón y recetas simuladas."""

import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from coreapp.mixins import RolRequeridoMixin, tiene_rol
from coreapp.roles import JEFA, TECNICO
from coreapp.utils.rut import normalizar_rut
from .forms import BusquedaPacienteForm, EntregaForm, ImportacionForm, RecetaForm
from .importacion import filas_demo, generar_archivo, importar_padron
from .models import ImportacionPadron, Paciente, Receta
from .services import crear_receta, evaluar_elegibilidad, registrar_entrega


@method_decorator(never_cache, name="dispatch")
@method_decorator(sensitive_post_parameters(), name="dispatch")
class FarmaciaView(RolRequeridoMixin, View):
    roles_permitidos = (JEFA, TECNICO)

    def render(self, template, contexto, **kwargs):
        respuesta = render(self.request, "recetas/" + template, contexto, **kwargs)
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        return respuesta


class PacientesView(FarmaciaView):
    def get(self, request):
        return self.mostrar(BusquedaPacienteForm())

    def post(self, request):
        return self.mostrar(BusquedaPacienteForm(request.POST))

    def mostrar(self, form):
        pacientes = Paciente.objects.order_by("apellidos", "nombres", "pk")
        pagina, buscar = 1, ""
        if form.is_bound:
            if form.is_valid():
                buscar, pagina = form.cleaned_data["buscar"], form.cleaned_data["pagina"] or 1
                if buscar:
                    condicion = Q(nombres__icontains=buscar) | Q(apellidos__icontains=buscar)
                    try:
                        condicion |= Q(rut=normalizar_rut(buscar))
                    except ValidationError:
                        pass
                    pacientes = pacientes.filter(condicion)
            else:
                pacientes = pacientes.none()
        page_obj = Paginator(pacientes, 20).get_page(pagina)
        return self.render("pacientes_lista.html", {"form": form, "page_obj": page_obj, "buscar": buscar})


class PacienteView(FarmaciaView):
    def get(self, request, pk):
        paciente = get_object_or_404(Paciente, pk=pk)
        return self.render("paciente_detalle.html", {"paciente": paciente, "recetas": paciente.recetas.order_by("-fecha_inicio", "-pk"), "puede_crear": tiene_rol(request.user, JEFA)})


class RecetaView(FarmaciaView):
    def get(self, request, pk):
        receta = get_object_or_404(Receta.objects.select_related("paciente", "receta_anterior"), pk=pk)
        return self.render("receta_detalle.html", {
            "receta": receta, "estado": evaluar_elegibilidad(receta),
            "entregas": receta.entregas.select_related("creado_por"),
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
        receta = get_object_or_404(Receta, pk=pk)
        return self.render("entrega_confirmar.html", {"receta": receta, "estado": evaluar_elegibilidad(receta), "form": EntregaForm(initial={"operacion_id": uuid.uuid4()})})

    def post(self, request, pk):
        receta = get_object_or_404(Receta, pk=pk)
        form = EntregaForm(request.POST)
        if form.is_valid():
            try:
                registrar_entrega(request.user, receta.pk, form.cleaned_data["operacion_id"])
            except ValidationError as error:
                form.add_error(None, error)
            except DatabaseError:
                form.add_error(None, "La entrega no fue confirmada. Reintenta con este mismo formulario.")
            else:
                messages.success(request, "Entrega del ciclo confirmada.")
                return redirect("recetasapp:receta_detalle", pk=pk)
        receta.refresh_from_db()
        return self.render("entrega_confirmar.html", {"receta": receta, "estado": evaluar_elegibilidad(receta), "form": form})


class ImportacionesView(FarmaciaView):
    roles_permitidos = (JEFA,)

    def get(self, request):
        return self.render("importacion_lista.html", {"page_obj": Paginator(ImportacionPadron.objects.select_related("creado_por"), 20).get_page(request.GET.get("page"))})


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
        return self.render("importacion_detalle.html", {"carga": carga, "page_obj": Paginator(carga.resultados.all(), 50).get_page(request.GET.get("page"))})


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
