"""Reglas puras: no dependen de Django, Redis ni de una base de datos."""
from dataclasses import dataclass

GENERAL = "GENERAL"
PREFERENCIAL = "PREFERENCIAL"
CATEGORIAS = (GENERAL, PREFERENCIAL)
ACTIVOS = ("PENDIENTE", "LLAMADO", "EN_ATENCION")
OCUPAN_VENTANILLA = ("LLAMADO", "EN_ATENCION")
TERMINALES = ("ATENDIDO", "AUSENTE", "CANCELADO")
TRANSICIONES = {
    "PENDIENTE": frozenset(("LLAMADO", "CANCELADO")),
    "LLAMADO": frozenset(("EN_ATENCION", "AUSENTE")),
    "EN_ATENCION": frozenset(("ATENDIDO",)),
    "ATENDIDO": frozenset(),
    "AUSENTE": frozenset(),
    "CANCELADO": frozenset(),
}


def validar_peso(peso):
    if type(peso) is not int or not 1 <= peso <= 100:
        raise ValueError("Cada peso debe ser un entero entre 1 y 100.")


def validar_transicion(origen, destino):
    if destino not in TRANSICIONES.get(origen, ()):
        raise ValueError(f"Transición no permitida: {origen} → {destino}.")


def numero_visible(categoria, correlativo):
    if categoria not in CATEGORIAS:
        raise ValueError("Categoría inválida.")
    if type(correlativo) is not int or correlativo < 1:
        raise ValueError("Correlativo inválido.")
    prefijo = "G" if categoria == GENERAL else "P"
    return f"{prefijo}-{correlativo:03d}"


@dataclass(frozen=True)
class Seleccion:
    categoria: str | None
    siguiente_categoria: str
    consumidos: int


def seleccionar(peso_general, peso_preferencial, siguiente, consumidos, disponibles):
    """Cupos G,G,P por defecto; una categoría vacía no acumula créditos.

    La persistencia y exclusión mutua pertenecen al servicio PostgreSQL.
    El llamador aporta disponibilidad y conserva la salida en su transacción.
    """
    validar_peso(peso_general)
    validar_peso(peso_preferencial)
    pesos = {GENERAL: peso_general, PREFERENCIAL: peso_preferencial}
    if siguiente not in CATEGORIAS:
        raise ValueError("Estado de arbitraje inválido.")
    if type(consumidos) is not int or not 0 <= consumidos < pesos[siguiente]:
        raise ValueError("Cupo consumido inválido.")
    presentes = set(disponibles)
    if not presentes <= set(CATEGORIAS):
        raise ValueError("Categoría disponible inválida.")
    if not presentes:
        return Seleccion(None, GENERAL, 0)
    otra = PREFERENCIAL if siguiente == GENERAL else GENERAL
    elegida = siguiente if siguiente in presentes else otra
    # Si se omitió una categoría vacía, se descarta el cupo incompleto.
    usados = consumidos + 1 if elegida == siguiente else 1
    alterna = PREFERENCIAL if elegida == GENERAL else GENERAL
    if usados >= pesos[elegida]:
        return Seleccion(elegida, alterna, 0)
    return Seleccion(elegida, elegida, usados)
