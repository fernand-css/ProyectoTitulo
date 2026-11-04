"""Estructura del menú principal: qué ve cada perfil, cómo se agrupa y cuál es la página actual.

Una sola lista alimenta la columna lateral del computador y la barra inferior del celular. Para sumar la
sección de una spec nueva basta con agregar una `Entrada` a `ENTRADAS`; las plantillas no cambian. Las
reglas de permiso son de presentación: cada vista sigue validando el rol en el servidor.

Las opciones se agrupan por lo que la persona hace (Trabajo, Equipo), no por el tipo de dato. Algunas llevan
una insignia con una cantidad (la fila de espera, las recetas por preparar): `contadores_del_menu` la calcula
solo para quien ve esa opción y solo cuando se dibuja el menú.
"""

from dataclasses import dataclass
from typing import Callable

from django.urls import reverse
from django.utils import timezone

from .roles import ENCARGADO, JEFA, SUPERUSUARIO, TECNICO

# La barra inferior muestra a lo más estos destinos más «Más»; con cinco botones cada uno sigue siendo
# lo bastante ancho (48 px o más) para tocarlo con el pulgar, incluso con texto muy grande.
MAXIMO_EN_BARRA = 4

CON_ACCESO = frozenset({JEFA, TECNICO, ENCARGADO, SUPERUSUARIO})
PERSONAL_DE_FARMACIA = frozenset({JEFA, TECNICO, SUPERUSUARIO})
GESTION = frozenset({JEFA, SUPERUSUARIO})

# Pantallas de turnosapp que configuran la atención (las usa la Jefa de Farmacia): no son «Atención».
CONFIGURACION_DE_TURNOS = ("gestion", "ventanilla_nueva", "ventanilla_configurar", "pesos")


def _en(app, *nombres, prefijos=()):
    """Página actual: una ruta de la app indicada, por nombre exacto o por prefijo."""
    def coincide(app_actual, nombre_actual):
        return app_actual == app and (nombre_actual in nombres or nombre_actual.startswith(prefijos))
    return coincide


@dataclass(frozen=True)
class Entrada:
    clave: str
    etiqueta: str
    destino: str                   # nombre de URL
    icono: str                     # símbolo del sprite (components/iconos.html)
    grupo: str = ""                # título del grupo en el menú lateral; vacío = sin título
    roles: frozenset = CON_ACCESO  # perfiles que la ven; una cuenta sin perfil solo ve el inicio
    activa: Callable = lambda app, nombre: False
    corta: str = ""                # nombre para la columna plegada, donde el largo no cabe
    en_barra: bool = False         # destino de trabajo: va en la barra inferior del celular
    otra_pestana: bool = False
    etiquetas_por_rol: tuple = ()  # variantes del texto por perfil: ((rol, texto), ...)
    contador: str = ""             # clave en `contadores_del_menu` de la cantidad que muestra como insignia
    contador_texto: str = ""       # cómo la lee un lector de pantalla: «en espera», «por preparar»


ENTRADAS = (
    Entrada(
        "inicio", "Inicio", "coreapp:inicio", "i-inicio", roles=None, corta="Inicio", en_barra=True,
        activa=_en("coreapp", "inicio"),
        etiquetas_por_rol=((ENCARGADO, "Entregas en terreno"),),
    ),
    Entrada(
        "turnos", "Atención", "turnosapp:panel", "i-turno", grupo="Trabajo", roles=PERSONAL_DE_FARMACIA,
        en_barra=True, contador="fila", contador_texto="en espera",
        activa=lambda app, nombre: app == "turnosapp" and nombre not in (*CONFIGURACION_DE_TURNOS, "sala"),
    ),
    Entrada("padron", "Pacientes", "recetasapp:pacientes", "i-padron", grupo="Trabajo", roles=PERSONAL_DE_FARMACIA,
            en_barra=True, activa=_en("recetasapp", "pacientes", "paciente_detalle", "plantilla", prefijos=("importacion",))),
    Entrada("recetas", "Recetas", "recetasapp:recetas", "i-documento", grupo="Trabajo", roles=PERSONAL_DE_FARMACIA,
            en_barra=True, contador="por_preparar", contador_texto="por preparar",
            activa=_en("recetasapp", "recetas", "recetas_lista", "entrega_confirmar", prefijos=("receta_", "preparacion"))),
    Entrada("sala", "Sala de espera", "turnosapp:sala", "i-sala", grupo="Trabajo", roles=PERSONAL_DE_FARMACIA,
            corta="Sala", otra_pestana=True),
    Entrada("ventanillas", "Ventanillas y pesos", "turnosapp:gestion", "i-ventanilla", grupo="Equipo", roles=GESTION,
            corta="Ventan.", activa=lambda app, nombre: app == "turnosapp" and nombre in CONFIGURACION_DE_TURNOS),
    Entrada("usuarios", "Usuarios", "usuariosapp:gestion_usuarios", "i-usuarios", grupo="Equipo", roles=GESTION,
            activa=_en("usuariosapp", prefijos=("gestion_",))),
    Entrada("administracion", "Administración", "admin:index", "i-ajustes", grupo="Equipo",
            roles=frozenset({SUPERUSUARIO}), corta="Admin."),
)

PERFIL = Entrada("perfil", "Mi perfil", "usuariosapp:perfil", "i-usuario", corta="Perfil",
                 activa=_en("usuariosapp", "perfil", "cambiar_clave"))


@dataclass(frozen=True)
class Opcion:
    """Una entrada ya resuelta para una persona y una página."""
    clave: str
    etiqueta: str
    corta: str
    url: str
    icono: str
    activa: bool
    otra_pestana: bool
    insignia: int = 0
    insignia_texto: str = ""


@dataclass(frozen=True)
class Grupo:
    clave: str
    titulo: str
    opciones: tuple


@dataclass(frozen=True)
class Persona:
    nombre: str
    iniciales: str
    rol: str


@dataclass(frozen=True)
class Menu:
    grupos: tuple           # menú lateral, en orden
    barra: tuple            # destinos de la barra inferior del celular
    mas: tuple              # el resto de los destinos: hoja «Más»
    perfil: Opcion | None   # «Mi perfil», aparte porque pertenece a la cuenta
    mas_activa: bool        # la página actual está en «Más»
    persona: Persona | None


def _visible(entrada, rol):
    if entrada.roles is None:  # el inicio lo ve toda cuenta, aunque aún no tenga perfil
        return True
    return rol in entrada.roles


def _resolver(entrada, rol, app, nombre, contadores=None):
    etiqueta = dict(entrada.etiquetas_por_rol).get(rol, entrada.etiqueta)
    cantidad = (contadores or {}).get(entrada.contador, 0) if entrada.contador else 0
    return Opcion(
        clave=entrada.clave, etiqueta=etiqueta, corta=entrada.corta, url=reverse(entrada.destino),
        icono=entrada.icono, activa=bool(app and entrada.activa(app, nombre)), otra_pestana=entrada.otra_pestana,
        insignia=cantidad, insignia_texto=entrada.contador_texto if cantidad else "",
    )


def armar_menu(rol, app="", nombre="", persona=None, contadores=None):
    """Menú de un perfil (`rol`) en la página `app:nombre`; un rol vacío es una cuenta sin perfil asignado."""
    visibles = [_resolver(entrada, rol, app, nombre, contadores) for entrada in ENTRADAS if _visible(entrada, rol)]
    claves_en_barra = [e.clave for e in ENTRADAS if e.en_barra and _visible(e, rol)][:MAXIMO_EN_BARRA]
    grupos, titulos = [], {e.clave: e.grupo for e in ENTRADAS}
    for opcion in visibles:
        titulo = titulos[opcion.clave]
        if not grupos or grupos[-1][0] != titulo:
            grupos.append((titulo, []))
        grupos[-1][1].append(opcion)
    barra = tuple(o for o in visibles if o.clave in claves_en_barra)
    mas = tuple(o for o in visibles if o.clave not in claves_en_barra)
    perfil = _resolver(PERFIL, rol, app, nombre) if rol else None
    return Menu(
        grupos=tuple(Grupo(clave=f"g{indice}", titulo=titulo, opciones=tuple(opciones))
                     for indice, (titulo, opciones) in enumerate(grupos)),
        barra=barra, mas=mas, perfil=perfil,
        mas_activa=any(o.activa for o in mas) or bool(perfil and perfil.activa), persona=persona,
    )


def contadores_del_menu(rol):
    """Cantidades de las insignias del menú, solo para el personal de farmacia.

    «fila»: turnos esperando hoy. «por_preparar»: recetas de turnos activos que aún no se marcan listas.
    Son dos consultas de conteo; los imports van aquí para que el núcleo no dependa de las otras apps al cargar.
    """
    if rol not in PERSONAL_DE_FARMACIA:
        return {}
    from recetasapp.preparacion import por_preparar
    from turnosapp.models import Turno

    hoy = timezone.localdate()
    return {
        "fila": Turno.objects.filter(fecha=hoy, estado="esperando").count(),
        "por_preparar": por_preparar(hoy).filter(lista_en__isnull=True).count(),
    }
