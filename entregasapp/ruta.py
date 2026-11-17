"""Orden de visita (spec 09, RF-09-02 y RF-09-05; enmienda del 2026-11-15, RF-09-20).

Módulo puro: no importa Django ni toca la base, así se prueba solo y se mide aparte. Todo es determinista: los
mismos puntos dan siempre el mismo orden, con desempate por la clave de cada parada (el identificador del
intento de entrega).

Las funciones reciben `distancia(a, b)` en metros entre dos `Punto`. Desde la enmienda, `consultas` entrega la
distancia por camino de la matriz de OSRM, que puede diferir de ida y de vuelta; sin ella se usa la línea recta
sobre la esfera (haversine), que es el respaldo rotulado cuando OSRM no responde.

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


def longitud_m(recorrido, distancia=None):
    """Largo de un recorrido (lista de puntos) sumando sus tramos, en el sentido del recorrido."""
    distancia = distancia or distancia_m
    return sum(distancia(a, b) for a, b in zip(recorrido, recorrido[1:]))


def _matriz(puntos, distancia=None):
    distancia = distancia or distancia_m
    return [[distancia(a, b) for b in puntos] for a in puntos]


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


def _acumulados(matriz, ruta):
    """Sumas acumuladas del recorrido de ida (ruta[k] → ruta[k+1]) y de vuelta (ruta[k+1] → ruta[k])."""
    ida, vuelta = [0.0], [0.0]
    for a, b in zip(ruta, ruta[1:]):
        ida.append(ida[-1] + matriz[a][b])
        vuelta.append(vuelta[-1] + matriz[b][a])
    return ida, vuelta


def _dos_opt(matriz, camino, destino):
    """Mejora 2-opt con extremos fijos: invierte tramos mientras alguno acorte el recorrido.

    `camino` son los índices de las paradas; la partida es el índice 0 y el destino, `destino`. Recorre los pares
    en un orden fijo y aplica la primera mejora de cada par, por lo que el resultado es determinista.

    Admite distancias asimétricas (por camino, la ida y la vuelta pueden diferir): al invertir el tramo i..j,
    sus calles internas se recorren al revés, así que la diferencia suma el tramo de vuelta y resta el de ida,
    ambos con sumas acumuladas que se recalculan tras cada mejora (O(n²) por pasada). Con distancias
    simétricas el resultado es el mismo de antes.
    """
    ruta = [0, *camino, destino]
    ultimo = len(ruta) - 2  # posición de la última parada
    ida, vuelta = _acumulados(matriz, ruta)
    mejorado = True
    while mejorado:
        mejorado = False
        for i in range(1, ultimo):
            anterior = ruta[i - 1]
            for j in range(i + 1, ultimo + 1):
                a, b, c, d = anterior, ruta[i], ruta[j], ruta[j + 1]
                interno = (vuelta[j] - vuelta[i]) - (ida[j] - ida[i])
                delta = matriz[a][c] + matriz[b][d] - matriz[a][b] - matriz[c][d] + interno
                if delta < -TOLERANCIA_M:
                    ruta[i:j + 1] = ruta[i:j + 1][::-1]
                    ida, vuelta = _acumulados(matriz, ruta)
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


def ordenar(partida, destino, paradas, limite=LIMITE_2OPT, distancia=None):
    """Orden sugerido de `paradas` desde `partida` hasta `destino`, que reduce el largo según `distancia`
    (por defecto, en línea recta)."""
    distancia = distancia or distancia_m
    paradas = sorted(paradas, key=lambda punto: punto.clave)
    n = len(paradas)
    if n == 0:
        return Orden((), distancia(partida, destino), False)
    puntos = [partida, *paradas, destino]
    matriz = _matriz(puntos, distancia)
    camino = _vecino_mas_cercano(matriz, n)
    excedido = n > limite
    if not excedido and n > 1:
        camino = _dos_opt(matriz, camino, n + 1)
    total = matriz[0][camino[0]] + sum(matriz[a][b] for a, b in zip(camino, camino[1:])) + matriz[camino[-1]][n + 1]
    return Orden(_mismo_punto_por_clave(puntos[indice] for indice in camino), total, excedido)


def insertar(secuencia, partida, destino, nueva, distancia=None):
    """Índice (0..len) donde `nueva` alarga menos el recorrido partida → secuencia → destino.

    Ante empate elige el primer índice. `secuencia` solo contiene puntos con coordenadas.
    """
    distancia = distancia or distancia_m
    mejor, costo_mejor = 0, None
    for indice in range(len(secuencia) + 1):
        previo = partida if indice == 0 else secuencia[indice - 1]
        siguiente = destino if indice == len(secuencia) else secuencia[indice]
        costo = distancia(previo, nueva) + distancia(nueva, siguiente) - distancia(previo, siguiente)
        if costo_mejor is None or costo < costo_mejor - TOLERANCIA_M:
            mejor, costo_mejor = indice, costo
    return mejor


def formatear_km(metros):
    """Total aproximado en km con un decimal y coma decimal: 23400 → «23,4»."""
    return f"{metros / 1000:.1f}".replace(".", ",")


def formatear_distancia(metros):
    """Distancia para leer: bajo 1 km, en metros redondeados a 10 m («850 m»); desde 1 km, en km con un
    decimal y coma decimal («1,2 km»)."""
    redondeado = int(round(metros / 10.0)) * 10
    if redondeado < 1000:
        return f"{redondeado} m"
    return f"{metros / 1000:.1f} km".replace(".", ",")
