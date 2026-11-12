"""Orden de visita en línea recta (spec 09, RF-09-02 y RF-09-05).

Módulo puro: no importa Django ni toca la base, así se prueba solo y se mide aparte. Todo es determinista: los
mismos puntos dan siempre el mismo orden, con desempate por la clave de cada parada (el identificador del
intento de entrega). Las distancias son en línea recta sobre la esfera (haversine): no consideran caminos.

- `ordenar`: vecino más cercano y mejora 2-opt sobre un camino con extremos fijos (sale de la partida, pasa por
  todas las paradas y termina en el destino, el CESFAM). Sobre `LIMITE_2OPT` paradas solo usa el vecino más
  cercano y lo informa.
- `insertar`: posición de inserción más barata de una parada nueva en una secuencia ya fijada.
"""

import math
from dataclasses import dataclass

RADIO_TIERRA_M = 6_371_000.0
LIMITE_2OPT = 200
# Mejoras menores que esto (en metros) se ignoran: evita ciclos por errores de redondeo con puntos repetidos.
TOLERANCIA_M = 1e-6


@dataclass(frozen=True)
class Punto:
    clave: object      # identificador estable (el intento); desempata y nombra la parada
    latitud: float
    longitud: float


@dataclass(frozen=True)
class Orden:
    paradas: tuple       # Punto en el orden de visita
    total_m: float       # partida → paradas → destino
    limite_excedido: bool  # más de LIMITE_2OPT paradas: solo vecino más cercano


def distancia_m(a, b):
    """Distancia haversine en metros entre dos puntos (radio terrestre de 6.371 km)."""
    lat1, lat2 = math.radians(a.latitud), math.radians(b.latitud)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitud - a.longitud)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(min(1.0, math.sqrt(h)))


def longitud_m(recorrido):
    """Largo de un recorrido (lista de puntos) sumando sus tramos."""
    return sum(distancia_m(a, b) for a, b in zip(recorrido, recorrido[1:]))


def _matriz(puntos):
    return [[distancia_m(a, b) for b in puntos] for a in puntos]


def _vecino_mas_cercano(matriz, n):
    """Índices 1..n en orden de visita desde el índice 0 (partida); desempata por índice (= clave ordenada)."""
    pendientes = set(range(1, n + 1))
    actual, camino = 0, []
    while pendientes:
        fila = matriz[actual]
        siguiente = min(pendientes, key=lambda indice: (fila[indice], indice))
        camino.append(siguiente)
        pendientes.remove(siguiente)
        actual = siguiente
    return camino


def _dos_opt(matriz, camino, destino):
    """Mejora 2-opt con extremos fijos: invierte tramos mientras alguno acorte el recorrido.

    `camino` son los índices de las paradas; la partida es el índice 0 y el destino, `destino`. Recorre los pares
    en un orden fijo y aplica la primera mejora de cada par, por lo que el resultado es determinista.
    """
    ruta = [0, *camino, destino]
    ultimo = len(ruta) - 2  # posición de la última parada
    mejorado = True
    while mejorado:
        mejorado = False
        for i in range(1, ultimo):
            anterior = ruta[i - 1]
            for j in range(i + 1, ultimo + 1):
                a, b, c, d = anterior, ruta[i], ruta[j], ruta[j + 1]
                delta = matriz[a][c] + matriz[b][d] - matriz[a][b] - matriz[c][d]
                if delta < -TOLERANCIA_M:
                    ruta[i:j + 1] = ruta[i:j + 1][::-1]
                    mejorado = True
    return ruta[1:-1]


def _mismo_punto_por_clave(paradas):
    """Paradas seguidas en el mismo punto (dos pacientes de una casa) quedan por clave; no cambia el largo."""
    resultado, grupo = [], []
    for punto in paradas:
        if grupo and (punto.latitud, punto.longitud) != (grupo[0].latitud, grupo[0].longitud):
            resultado.extend(sorted(grupo, key=lambda p: p.clave))
            grupo = []
        grupo.append(punto)
    resultado.extend(sorted(grupo, key=lambda p: p.clave))
    return tuple(resultado)


def ordenar(partida, destino, paradas, limite=LIMITE_2OPT):
    """Orden sugerido de `paradas` desde `partida` hasta `destino`, que reduce el largo en línea recta."""
    paradas = sorted(paradas, key=lambda punto: punto.clave)
    n = len(paradas)
    if n == 0:
        return Orden((), distancia_m(partida, destino), False)
    puntos = [partida, *paradas, destino]
    matriz = _matriz(puntos)
    camino = _vecino_mas_cercano(matriz, n)
    excedido = n > limite
    if not excedido and n > 1:
        camino = _dos_opt(matriz, camino, n + 1)
    total = matriz[0][camino[0]] + sum(matriz[a][b] for a, b in zip(camino, camino[1:])) + matriz[camino[-1]][n + 1]
    return Orden(_mismo_punto_por_clave(puntos[indice] for indice in camino), total, excedido)


def insertar(secuencia, partida, destino, nueva):
    """Índice (0..len) donde `nueva` alarga menos el recorrido partida → secuencia → destino.

    Ante empate elige el primer índice. `secuencia` solo contiene puntos con coordenadas.
    """
    mejor, costo_mejor = 0, None
    for indice in range(len(secuencia) + 1):
        previo = partida if indice == 0 else secuencia[indice - 1]
        siguiente = destino if indice == len(secuencia) else secuencia[indice]
        costo = distancia_m(previo, nueva) + distancia_m(nueva, siguiente) - distancia_m(previo, siguiente)
        if costo_mejor is None or costo < costo_mejor - TOLERANCIA_M:
            mejor, costo_mejor = indice, costo
    return mejor


def formatear_km(metros):
    """Total aproximado en km con un decimal y coma decimal: 23400 → «23,4»."""
    return f"{metros / 1000:.1f}".replace(".", ",")
