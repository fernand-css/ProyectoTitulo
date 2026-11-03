"""Proyección privada de solo lectura; nunca inicia ni procesa la cola por GET."""
import uuid
from datetime import timedelta
from django.core.paginator import Paginator
from django.utils import timezone
from coreapp.mixins import tiene_rol
from coreapp.roles import JEFA, TECNICO
from .cola import espera_turno
from .models import ConfiguracionCola, PendienteSeleccion, Turno, Ventanilla


def contexto_panel(usuario, pagina=1):
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    operar, gestionar = tiene_rol(usuario, TECNICO), tiene_rol(usuario, JEFA)
    ventanillas = list(Ventanilla.objects.select_related("operador").prefetch_related("tipos").order_by("retirada", "numero"))
    propia = next((v for v in ventanillas if v.operador_id == usuario.pk), None) if operar else None
    vigente = Turno.objects.select_related("paciente").filter(ventanilla=propia, estado="llamado").first() if propia else None
    for vent in ventanillas:
        vent.nonce_ocupar = uuid.uuid4()
        vent.tipos_texto = ", ".join(tipo.get_codigo_display() for tipo in vent.tipos.all()) or "Ninguno"
        vent.activa_hoy = vent.automatico and vent.fecha_activacion == hoy and vent.habilitada and not vent.retirada
    espera = Turno.objects.filter(fecha=hoy, estado="esperando").order_by("entrada_cola", "numero", "pk")
    pagina_cola = Paginator(espera, 30).get_page(pagina)
    for turno in pagina_cola:
        turno.espera = espera_turno(turno, ahora)
    habilitados = {tipo.codigo for vent in ventanillas if vent.habilitada and not vent.retirada for tipo in vent.tipos.all()}
    sin_cobertura = [etiqueta for codigo, etiqueta in Turno.TipoAtencion.choices if codigo not in habilitados and espera.filter(tipo_atencion=codigo).exists()]
    return {"ventanillas": ventanillas, "propia": propia, "vigente": vigente, "pagina_cola": pagina_cola,
        "puede_operar": operar, "puede_gestionar": gestionar, "configuracion": ConfiguracionCola.objects.filter(pk=1).first(),
        "ausentes": Turno.objects.filter(fecha=hoy, estado="ausente").order_by("numero")[:100],
        "pendientes": PendienteSeleccion.objects.filter(estado="pendiente").order_by("creado_en")[:20],
        "sin_cobertura": sin_cobertura, "hoy": hoy, "ahora": ahora,
        "puede_ausente": bool(vigente and ahora >= vigente.ultimo_llamado + timedelta(seconds=60)),
        "nonce_iniciar": uuid.uuid4(), "nonce_pausar": uuid.uuid4(), "nonce_liberar": uuid.uuid4(),
        "nonce_rellamar": uuid.uuid4(), "nonce_ausente": uuid.uuid4()}
