# Validación — 09 / Mapa y orden de visita

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-12. Entorno: Windows 11, Python 3.13.17, Django 5.2.19, Node 24.22.1, Leaflet 1.9.4 (paquete npm). Pruebas de Django sobre la base de pruebas desechable de PostgreSQL (`test_<DB_NAME>`); herramienta HTTP sobre una SQLite temporal; pruebas de Node con un DOM y un Leaflet simulados. Solo datos sintéticos (670 pacientes generados, RUT ficticios con DV válido y domicilios con coordenadas aleatorias que no representan viviendas reales).
Referencia de código: rama `crojas-base`, cambios sin commit sobre `5751ec5`.
Estado: **verificación técnica ejecutada**; revisión de navegador, axe, usabilidad y aceptación funcional **pendientes**. El spec sigue en **Aprobado**.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-09-01 | `test_ruta_consultas.py` (`test_hoy_y_atrasadas…`, `test_sin_intentos_reasignados_ni_anulados`) | Hoy y atrasadas en la ruta; próximas aparte; sin intentos de otro encargado, reasignados ni anulados | 3 de hoy y 1 de ayer numeradas (la de ayer «atrasada»); la de mañana en próximas; las 2 del otro encargado, la reasignada y la anulada fuera | aprobada |
| RF-09-02 | `test_ruta.py` (17); `test_ruta_consultas.py` | Orden determinista; 2-opt no peor que el vecino más cercano e igual a la fuerza bruta en los casos construidos; recálculo desde la última visita registrada | B, C, A con 6,0 km; el caso con cruce pasa de 2,1,3,4 a 3,1,2,4 sin cruces e igual a la fuerza bruta; 40 casos aleatorios nunca peores; tras registrar B, C, A desde B con 5 km | aprobada |
| RF-09-03 | `test_ruta_consultas.py`; `test_vistas_mapa.py` | Visitas sin coordenadas al final, agrupadas y rotuladas; contador en el mapa | Al final, por sector y localidad, sin número; «Sin coordenadas: fuera del orden sugerido (1)»; el mapa dice «2 visitas sin marcador» | aprobada |
| RF-09-04 | `test_orden_manual.py` (10); `test_concurrencia_ruta.py`; `test_vistas_mapa.py` | Orden guardado sin recálculo; idempotencia; una edición ganadora por versión; vuelve a la sugerencia al día siguiente; solo el encargado | Igual; la visita sin coordenadas movida a la posición 1 queda numerada y sin marcador; Q.F., superusuario y Técnico reciben `PermissionDenied`; otro encargado no alcanza la visita ajena | aprobada |
| RF-09-05 | `test_ruta.py` (`InsertarTests`); `test_ruta_consultas.py` | Visita nueva en la inserción más barata con rótulo; sin coordenadas al final; salidas eliminadas; sin rótulo tras guardar | A, D («Nueva»), B, C; luego E sin coordenadas al final; al anular B queda A, D, C, E; al mover cualquier parada, las nuevas quedan guardadas sin rótulo | aprobada |
| RF-09-06 | `test_orden_manual.py`; `test_vistas_mapa.py` | Vuelve a la sugerencia y queda auditado | Igual (`ruta.restablecida`); sin orden con paradas no hace nada | aprobada |
| RF-09-07 | `test_ruta_consultas.py`; `test_vistas_mapa.py` | Solo las registradas hoy, con resultado, motivo y hora, sin número | Igual; la registrada ayer no aparece | aprobada |
| RF-09-08 | `test_vistas_mapa.py` (`MapaTests`); `mapa.test.cjs` (8) | Números iguales a la lista; línea, total, atribución; aviso si fallan las teselas; sin RUT | 4 paradas numeradas como la lista, 2 registradas, CESFAM, línea de 6 puntos y total; sin RUT, teléfono ni notas; atribución con enlace a OSM; con `tileerror` aparece el aviso y los marcadores siguen; el resumen se arma con texto | aprobada |
| RF-09-09 | `ir_a.test.cjs` (7); `test_vistas_mapa.py` (`IrAParadaTests`) | Distancia y rumbo correctos; detención; errores en texto; ninguna solicitud de red con la posición | 1° = 111,19 km; «850 m», «1,0 km», «1,2 km»; los ocho rumbos; aviso al iniciar, al leer y al llegar a menos de 100 m (una vez); «Detener», `pagehide` y ocultar detienen `watchPosition`; sin permiso, sin posición y sin HTTPS con texto; el módulo funciona en un contexto donde la red falla | aprobada |
| RF-09-10 | `test_vistas_mapa.py` (`RutasTests`); `test_permisos_mapa.py` | Hoy igual a lo que ve el encargado; futura sugerida; pasada rechazada; Técnico y encargado sin acceso | Igual; mañana parte del CESFAM solo con las de ese día; ayer y un encargado no válido dan 400 con texto; sin controles de orden ni «Ir a esta parada» | aprobada |
| RF-09-11 | `test_vistas_mapa.py` (`MapaDomicilioTests`) | Mapa pequeño con coordenadas; texto sin ellas | Datos del punto con su precisión para los cuatro perfiles, sin RUT; sin coordenadas, «Sin coordenadas» y sin Leaflet | aprobada |
| RF-09-12 | `test_configuracion_mapa.py` (7); `coreapp/tests/test_estaticos.py` | Valores por defecto; `E001`, `E002` y `E003`; Leaflet local con licencia; sin CDN | Igual; `python manage.py check` informa los errores; Leaflet 1.9.4 con su licencia BSD-2-Clause, sus imágenes y su `.map` | aprobada |
| RF-09-13 | `test_generar_domicilios_demo.py` (4); herramienta HTTP | Simulación sin cambios; creación reproducible y auditada; sin tocar los existentes; rechazo sin permiso | Igual; dentro del radio, sin verificar, auditados a nombre de la Q.F.; repetir no toca nada y la misma semilla da los mismos domicilios; Técnico, encargado, cuenta inexistente y `--aplicar` sin cuenta rechazados | aprobada |
| RF-09-14 | `test_permisos_mapa.py` (7); `test_orden_manual.py`; `mapa.test.cjs` | Matriz, CSRF, `no-store`, `referrerPolicy` de solo origen, auditoría sin datos personales | Igual; anónimo al inicio de sesión; cuenta inactiva o sin perfil sin acceso; POST sin CSRF 403 sin cambios; «Rutas» manipulada 400 sin datos; `strict-origin`; auditoría solo con el tipo y el id de `OrdenRuta`; si la auditoría falla, la operación se revierte | aprobada |
| RF-09-15 | `test_concurrencia_ruta.py` (3 escenarios con hilos y conexiones de PostgreSQL, 3 vueltas cada uno); regresión completa | Un orden por encargado y día; una edición ganadora; sin visitas duplicadas ni perdidas; 03 al 07 sin cambios | Igual en 3 corridas seguidas (ver regresión); una sola prueba del 08 ajustada, listada en `plan.md` | aprobada |

## Regresión de la base

| Comando | Resultado |
|---|---|
| `python manage.py test --noinput --parallel 1` antes de empezar (base `5751ec5`) | 755 pruebas: 754 aprobadas y 1 error previo ajeno al 09 (`turnosapp.tests.test_sala_servidor`: Windows no deja borrar su SQLite temporal, `WinError 32`). |
| `python manage.py test --noinput --parallel 1`, primera corrida completa | 834 pruebas: 831 aprobadas; 2 errores nuevos en `coreapp.tests.test_plantillas::test_todas_las_plantillas_renderizan` (`entregas/ir_a.html` y `_orden_controles.html` fallaban dibujadas sin contexto) y el error previo de `test_sala_servidor`. Se corrigieron con una rama «sin datos», como la de `_tarjeta_intento.html`. |
| `python manage.py test --noinput --parallel 1` al cierre | **834 pruebas: 833 aprobadas** y el mismo error previo de `test_sala_servidor`. 79 pruebas nuevas sobre las 755 de la línea base: 77 en `entregasapp` (17 del algoritmo, 7 de configuración, 3 de modelos, 12 de consultas, 10 de orden manual, 3 concurrentes, 14 de vistas, 7 de permisos y estructura y 4 del comando), 1 en `test_navegacion.py` y 1 en `test_estaticos.py`. |
| `python manage.py test entregasapp.tests.test_concurrencia_ruta` tres veces seguidas | 3 aprobadas en cada corrida. |
| `node --test turnosapp/tests/*.test.cjs recetasapp/tests/*.test.cjs entregasapp/tests/*.test.cjs` | 90 aprobadas (15 nuevas: 8 de `mapa.js` y 7 de `ir_a.js`). |
| `python manage.py check` y `python manage.py makemigrations --check --dry-run` | Sin problemas; sin cambios pendientes. |

Durante la implementación, las pruebas corrigieron sus propias expectativas en cuatro casos sin cambiar el código: (1) la inserción en un recorrido de ida y vuelta por la misma línea admite dos lugares igual de baratos, así que se usó un recorrido en cuadrado; (2) en «Mis entregas», desde la última visita registrada A queda antes que B, como corresponde; (3) los signos de los rumbos simulados estaban invertidos; (4) la versión final esperada en la herramienta HTTP era 50, no 51. En el código solo se agregó un orden estable para paradas en el mismo punto (por id del intento), que no cambia el largo del recorrido.

## Rendimiento HTTP

`python tools/verificar_spec_09_http.py` (2026-11-12, salida 0, resultado «aprobado»): SQLite temporal, 670 pacientes sintéticos (600 mayores de 80 y 70 postrados), `generar_domicilios_demo` en simulación y con `--aplicar` (660 domicilios con coordenadas) más 10 sin coordenadas, cuatro encargados con 50 visitas para hoy y un quinto con 200 para mañana. Recorre «Mis entregas» y «Mapa» (comprueba que los datos no traen RUT ni teléfono), «Ir a esta parada», «Rutas» de la Q.F. (hoy igual a lo que ve el encargado, mañana con 200 paradas, ayer rechazado y el Técnico con 403), 100 movimientos (más un reenvío que no mueve otra vez) y 100 vueltas al orden sugerido. Comprueba también que la auditoría no tiene datos personales y que ordenar no registra visitas.

| Escenario | Muestras | p50 (ms) | p95 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|
| Mis entregas (50 visitas) | 100 | 292,79 | 336,80 | 416,45 |
| Mapa | 100 | 103,95 | 138,13 | 202,86 |
| Ir a esta parada | 100 | 49,23 | 78,55 | 112,34 |
| Rutas de hoy | 100 | 149,82 | 174,64 | 250,92 |
| Rutas de mañana con 200 paradas | 20 | 392,36 | 515,67 | 559,17 |
| Mover (incluye la redirección y el dibujo de la lista) | 100 | 395,73 | 470,53 | 570,24 |
| Volver al orden sugerido (ídem) | 100 | 341,85 | 387,18 | 470,32 |

Cálculo con 200 paradas, medido aparte: `ruta.ordenar` (vecino más cercano y 2-opt) p95 97,80 ms en 20 conjuntos aleatorios; `ruta_del_dia` desde la base, p95 254,24 ms en 10 lecturas.

## Revisión visual si aplica

No ejecutada en este host. Pendientes:
- escritorio y celular: «Mis entregas», «Mapa», «Ir a esta parada», «Rutas» y mapa del domicilio;
- axe, navegación del mapa por teclado, lector de pantalla y zoom al 200 %;
- carga real de teselas de OpenStreetMap (atribución, referente de solo origen y aviso con la red cortada) y ubicación real en contexto seguro.

Lo que sí se comprobó en el HTML servido (`test_permisos_mapa.py::EstructuraMapaTests`): un solo `h1`, ids únicos, campos con etiqueta, botones con tipo e imágenes con texto alternativo en las pantallas nuevas y en las del 08 que cambiaron.

## Límites y fallos

- Distancia en línea recta, sin caminos: la lista y el mapa lo dicen siempre.
- El mapa base exige conexión (sin conexión: reserva 11) y el proveedor de teselas ve la IP y el área visible del mapa.
- La ubicación del navegador exige HTTPS o `localhost`.
- La posición nunca llega al servidor, así que no hay evidencia del lado del servidor sobre el seguimiento: las pruebas de Node con geolocalización simulada son la evidencia.
- La herramienta HTTP mide loopback con SQLite, sin red móvil ni dibujo en el navegador. «Mis entregas» con 50 visitas es la página más pesada (un selector de 50 posiciones por tarjeta); su p95 quedó en 336,80 ms.
- La 2-opt no garantiza el óptimo: coincide con la fuerza bruta en los casos construidos y nunca empeora al vecino más cercano.

**Corrección del 2026-11-15 — prueba intermitente.** `test_concurrencia_ruta.test_2_tres_ediciones_desde_la_misma_version_una_gana` fallaba a veces en la regresión completa (1 de 3 corridas aisladas). Causa: usaba «subir» y «bajar», y según quién ganó la vuelta anterior la parada podía quedar en un extremo. Ese movimiento se rechazaba con «Esta parada ya es la primera.», su transacción se revertía y otro se aplicaba, así que un perdedor no recibía el aviso esperado. El servicio se comportaba bien; solo cambió la prueba, que ahora usa posiciones absolutas (1, 4 y 2) siempre válidas y muestra los mensajes recibidos si falla. Resultado: el archivo pasó 20 de 20 corridas y `manage.py test entregasapp` aprobó 218 pruebas en PostgreSQL.

## Aplicación y reversión

Migración `entregasapp/0002_ordenruta`: aplicada solo en las bases de pruebas y en la SQLite temporal de la herramienta. **La base PostgreSQL del proyecto no se migró**; hay que aplicar `python manage.py migrate` en la base de demostración elegida cuando el usuario lo apruebe. Revertirla (`python manage.py migrate entregasapp 0001`) elimina solo los órdenes manuales. `generar_domicilios_demo` no se ejecutó sobre la base del proyecto.

## Enmienda del 2026-11-15 (implementada el 2026-11-16)

Estado: **verificación técnica ejecutada** el 2026-11-16 en `crojas-base`, sin commit sobre `72208b8`; navegador, celular real, axe, usabilidad y aceptación **pendientes**. Pruebas de Django sobre la base de pruebas desechable de PostgreSQL, con OSRM desactivado por el ejecutor de pruebas y simulado donde hace falta (`entregasapp/tests/osrm_simulado.py`, servidor en 127.0.0.1 con puerto libre); pruebas de Node con un DOM simulado (`dom_simulado.cjs`). Solo datos sintéticos.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-09-16 | `test_vistas_mapa.py` (`test_tarjetas_compactas_…`); `tarjetas.test.cjs` (6) | Tarjetas compactas con número y rótulos; varias expandidas; sin JavaScript, expandidas | Número, rótulos, nombre, dirección, «Entregar», «No entregada» y «Expandir» (`aria-expanded`, `aria-controls`); la próxima con «Programada para el dd/mm/aaaa»; el botón llega oculto y el detalle visible (sin JavaScript); con JavaScript dos tarjetas abiertas a la vez, «Contraer» y el foco en el botón; se recuerdan en `sessionStorage` del día y se tolera un almacenamiento que falla | aprobada (navegador pendiente) |
| RF-09-17 | `test_vistas_mapa.py` (lista, JSON y POST sin JavaScript); `orden.test.cjs` (13) | Orden guardado con flechas y arrastre; Esc cancela; choque de versión revierte con aviso; sin «Mover a la posición» | Flechas con nombre accesible («Bajar parada 1: …»), la que no aplica oculta; POST sin JavaScript con recarga; con `Accept: application/json` responde orden, versión, rótulo y total, 409 con «Tu orden cambió en otro dispositivo; revisa la lista.» y 400 en un borde; en Node: la flecha mueve la tarjeta y aplica el orden del servidor, el fallo restaura la lista y lo anuncia, el arrastre con mouse lleva la parada 3 a la 1 y anuncia «Parada movida a la posición 1.», Esc y soltar fuera devuelven sin enviar, el toque largo de 300 ms empieza el arrastre y un movimiento antes es desplazamiento, la página se desplaza sola cerca de los bordes; «Mover a la posición» no existe; la Q.F. en «Rutas» no ve flechas ni franja | aprobada (celular real pendiente) |
| RF-09-18 | `tarjetas.test.cjs`; `test_vistas_mapa.py` | Mapa pequeño solo al expandir; «Domicilio sin coordenadas» | Se dibuja una vez, al primer «Expandir», sin arrastre ni zoom con los dedos y solo con latitud, longitud y precisión; sin coordenadas, «Domicilio sin coordenadas»; sin Leaflet o con error, el aviso de texto | aprobada (teselas reales pendientes) |
| RF-09-19 | `test_osrm.py` (11); `test_configuracion_mapa.py` (6 nuevas); `test_tramo.py`; `docker logs osrm` | `longitud,latitud`; errores como «no disponible»; `E004` y `E005`; la posición no queda en la base, auditoría, sesión, caché ni registros | Tabla y ruta con `lon,lat` y 6 decimales, sin proxies del entorno; 500, `NoRoute`, JSON mal formado, distancia nula, servidor apagado y forma inesperada dan `OsrmNoDisponible` sin coordenadas en el mensaje; tiempo agotado en menos de 0,9 s con espera de 0,5 s; URL vacía desactiva sin consultar; caché solo para la matriz sin la posición; `E004` para `ftp://x`, `http://h:5000/?a=1` y otros, `E005` para 5, 0,1 y 2,5 s; tras tramo, parada más cercana, 404 y 503, la huella de la posición no aparece en `dumpdata`, la sesión, la caché local ni los registros capturados, y la auditoría no crece. El contenedor local ya corre con `--algorithm mld --max-table-size 300 --verbosity WARNING`, publicado solo en `127.0.0.1:5000`; tras una consulta de tramo, `docker logs --tail 4 osrm` no mostró ninguna línea | aprobada |
| RF-09-20 | `test_ruta.py` (4 nuevas); `test_ruta_consultas.py` (6 nuevas) | Orden y total por camino; respaldo rotulado sin total; 2-opt asimétrico igual a la fuerza bruta | Matriz de un solo sentido construida a mano: el vecino más cercano recorre 20,4 km y el 2-opt adaptado 10,1 km, igual a la fuerza bruta; 40 matrices asimétricas al azar nunca peores que el vecino más cercano; con un río simulado el orden sigue al camino (B, A) y el total es la suma de la matriz; OSRM caído (500, `NoRoute`, JSON malo, distancia nula, URL vacía): orden en línea recta, `distancia = "recta"` y sin total; el orden manual no cambia; las «Nuevas» se insertan con la matriz; la matriz se pide una vez y se guarda en caché; sin paradas con coordenadas no se consulta | aprobada |
| RF-09-21 | `test_tramo.py` (7); `tramo.test.cjs` (9); `mapa.test.cjs` (6 nuevas) | Tramo hasta la próxima o la elegida; recálculo con umbrales; sin línea del recorrido; aviso sin permiso u OSRM | Tramo hasta la primera parada con coordenadas y luego hasta la elegida con «Trazar tramo hasta aquí»; no recalcula a 100 m y sí a 200 m pasados 20 s (cerca: 30 m y 10 s); «Detener» y `pagehide` borran el tramo; sin permiso, sin contexto seguro, sin señal u OSRM caído: sin línea y con aviso; los datos del mapa no traen `linea`; el destino se toma de la base (visita ajena, sin coordenadas o registrada: 404; coordenadas manipuladas en el cuerpo, ignoradas); 30 por minuto y luego 429 sin consultar a OSRM; Técnico, Q.F. y superusuario 403; sin CSRF 403; todas `no-store` | aprobada (celular real en contexto seguro pendiente) |
| RF-09-22 | `test_tramo.py` (`ParadaCercanaTests`, 4); `mapa.test.cjs` | Parada más cercana por camino; mover a la posición 1; sin sugerencia con OSRM caído | Posición junto a la parada 4: la destaca con otra forma y «La más cercana por camino es la parada 4, a 50 m»; con `mover_parada(destino=1)` queda primera y el orden pasa a manual, y la siguiente consulta dice «Ya es tu próxima parada» sin ofrecer moverla; por camino gana otra aunque en línea recta gane la primera; OSRM caído: 503 y ninguna sugerencia; sin posición, el botón explica que hace falta la ubicación | aprobada |
| RF-09-23 | `ir_a.test.cjs` (6); `test_vistas_mapa.py` | Distancia por camino; sin rumbo ni línea recta; aviso de 100 m | «La parada 3 está a 1,2 km por camino.»; un solo aviso a menos de 100 m por camino; sin OSRM, sin señal, sin permiso o sin HTTPS: texto sin distancia; la página no menciona la línea recta ni el rumbo y conserva el enlace `geo:` y las coordenadas | aprobada (celular real pendiente) |
| RF-09-24 | `test_vistas_mapa.py` (`RutasTests`); `test_permisos_mapa.py` | Tarjetas de consulta; mapa solo con marcadores, sin posición | Tarjetas compactas expandibles con mapa pequeño, sin flechas, franja, «Entregar», botón de fotos, «Ir a esta parada» ni tramo; datos del mapa sin `linea`, sin rutas de tramo y sin campos de posición | aprobada |
| RF-09-25 | `usar_mapa.test.cjs` (7); `test_vistas_mapa.py` (`UsarMapaTests`, 2) | Centro correcto; marcar y copiar 6 decimales; precisión vacía; foco de vuelta | Sin coordenadas abre en el CESFAM sin marca; con coordenadas válidas, marcado en el punto; clic y «Marcar el centro del mapa» marcan (otro clic reemplaza); «Usar este punto» copia `-36.501235`, vacía la precisión, lanza `input` y `change`, cierra y devuelve el foco; «Cancelar», Esc y la X no cambian nada; el botón solo aparece con JavaScript, `<dialog>` y Leaflet, y solo para quien edita; guardar coordenadas nuevas por HTTP deja el domicilio sin verificar | aprobada (navegador pendiente) |
| RF-09-26 | `tramo.test.cjs`; `mapa.test.cjs`; `orden.test.cjs`; `tarjetas.test.cjs` | Avisos de texto; nada se guarda | Sin red: «Sin conexión: no se pudo calcular el tramo…», «Sin conexión: no se pudo calcular la parada más cercana.» y «Sin conexión: no se guardó el cambio de orden.», sin enviar nada; mapa de tarjeta sin Leaflet con aviso. El modal de fotos ya se probó en el 08 (`fotos.test.cjs`) | aprobada (navegador sin red pendiente) |
| RNF-05 | `tools/verificar_spec_09_http.py --osrm-real` | p95 ≤ 2 s; matriz de 52 y 202 puntos y un tramo medidos aparte | Ver «Rendimiento HTTP de la enmienda» | aprobada (loopback) |
| RNF-04 | axe, teclado, zoom al 200 %, 320 px, lector de pantalla; usabilidad con cinco personas | Sin errores AA; flechas como alternativa al arrastre; diálogos accesibles | Revisión en el navegador integrado del 2026-11-16 (ver «Revisión en navegador de la enmienda»): flechas de 48 × 48 px, sin desplazamiento horizontal a 375 px, foco que vuelve a «Usar mapa» y anuncios en `aria-live`. No se ejecutaron axe, lector de pantalla, zoom al 200 %, 320 px ni la prueba con cinco personas | parcial (axe y usabilidad pendientes) |
| Lienzo | T-09-10 (Claude Design) | Pantallas pedidas en celular y computador, con datos sintéticos | 12 pantallas publicadas en un lienzo privado; revisadas y aprobadas por el usuario el 2026-11-15 | aprobada (revisión de diseño, no de la implementación) |

### Regresión de la enmienda

| Comando | Resultado |
|---|---|
| `python manage.py test --noinput --parallel 1`, primera corrida | 1013 pruebas: 3 fallos y 1 error de esta implementación más el error previo de `test_sala_servidor` (`WinError 32`). `test_plantillas` exigía que `_dialogo_usar_mapa.html` dibujara algo sin contexto (se agregó la rama «sin datos»), y `MapaDomicilioTests` suponía que un domicilio sin coordenadas nunca carga Leaflet (quien edita lo carga para «Usar mapa»; la prueba se ajustó y quedó listada en `plan.md`). |
| `python manage.py test --noinput --parallel 1`, al cierre | **1013 pruebas: 1012 aprobadas** y el mismo error previo de `test_sala_servidor` (`WinError 32`: Windows no deja borrar su SQLite temporal), ajeno al 09. Son 179 más que las 834 del 2026-11-12, entre las del 10, las de la enmienda del 08 y estas del 09. |
| `node --test turnosapp/tests/*.test.cjs recetasapp/tests/*.test.cjs entregasapp/tests/*.test.cjs` | 166 aprobadas (76 más que las 90 del 2026-11-12: las del 08 de fotos y visor, y del 09 `tarjetas` 6, `orden` 13, `tramo` 9, `usar_mapa` 7, `mapa` 16 y `ir_a` 6). |
| `python manage.py check` y `python manage.py makemigrations --check --dry-run` | Sin problemas; sin cambios pendientes (la enmienda no tiene migraciones). |

### Rendimiento HTTP de la enmienda

`python tools/verificar_spec_09_http.py --osrm-real` (2026-11-16, salida 0, resultado «aprobado»), corrido solo, después de la suite: SQLite temporal, 670 pacientes sintéticos, 660 domicilios generados y 10 sin coordenadas, cuatro encargados con 50 visitas, un quinto con 200 para mañana y un OSRM simulado (distancia = 1,3 × línea recta). Comprueba además el 429 a las 31 solicitudes de tramo en un minuto (después levanta el límite solo en ese proceso para medir), la visita ajena (404), la Q.F. en el tramo (403), la URL enviada a OSRM con `longitud,latitud`, y con OSRM caído el rótulo «Orden aproximado en línea recta…», la ausencia del total y el 503 del tramo y de la parada más cercana. Una corrida anterior, en paralelo con la suite, también aprobó (p95 máximo 594,89 ms en «mover»).

| Escenario | Muestras | p50 (ms) | p95 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|
| Mis entregas (50 visitas, tarjetas compactas) | 100 | 233,17 | 285,68 | 464,93 |
| Mapa | 100 | 98,02 | 138,67 | 389,77 |
| Ir a esta parada | 100 | 73,67 | 98,80 | 166,59 |
| Rutas de hoy | 100 | 129,04 | 163,49 | 220,84 |
| Rutas de mañana con 200 paradas | 20 | 344,74 | 523,63 | 530,31 |
| Mover sin JavaScript (incluye la redirección y el dibujo de la lista) | 100 | 306,36 | 371,31 | 524,02 |
| Volver al orden sugerido (ídem) | 100 | 271,86 | 311,22 | 332,98 |
| Mover con JavaScript (JSON) | 20 | 122,11 | 136,38 | 146,51 |
| Tramo por camino | 100 | 77,02 | 95,50 | 225,14 |
| Parada más cercana | 100 | 76,86 | 105,56 | 178,50 |

Cálculo con 200 paradas (en línea recta, como antes): `ruta.ordenar` p95 81,30 ms en 20 conjuntos; `ruta_del_dia` desde la base, p95 252,37 ms en 10 lecturas.

Con el OSRM local real (`127.0.0.1:5000`, Ñuble, MLD), sin caché, 10 muestras cada uno: matriz de 52 puntos p50 67,57 ms y p95 133,66 ms; matriz de 202 puntos p50 225,83 ms y p95 272,89 ms; un tramo p50 19,90 ms y p95 39,97 ms. Todos quedan bajo el tiempo de espera por defecto de 1 s.

### Revisión en navegador de la enmienda (2026-11-16)

Navegador integrado de la aplicación de escritorio, contra un servidor local de revisión con una SQLite temporal y datos sintéticos (8 pacientes, 2 encargados, la Q.F. y el Técnico; cuentas `revision_*` con una clave temporal que no se registró). Se probó con el OSRM local real y también con él apagado. La ubicación se simuló reemplazando `Geolocation.prototype.watchPosition`: el panel no entrega la ubicación real, y sin la simulación respondió «No diste permiso…», que también se comprobó.

| Pantalla | Revisado | Resultado |
|---|---|---|
| «Mis entregas» (escritorio) | Rótulo y total por camino con OSRM real («Recorrido aprox. por camino: 26,0 km»); tarjetas compactas; «Expandir»/«Contraer»; mapa pequeño al expandir; flecha «Bajar»; arrastre con el mouse de la parada 3 a la 1 | Bien tras corregir el defecto 1. La flecha y el arrastre reordenan sin recargar, renumeran (la visita sin coordenadas pasa a ser la parada 6), dejan abiertas las tarjetas abiertas, mantienen el foco en la flecha, anuncian «Parada movida a la posición N.» y muestran «Volver al orden sugerido» |
| «Mis entregas» con OSRM apagado | Rótulo y total | «Tu orden de hoy… Sin total del recorrido: el servidor de rutas no respondió.» y sin total, como pide RF-09-20; demoras corregidas (defecto 3) |
| «Mapa» con OSRM real | «Mostrar mi posición», tramo, «Sugerir parada más cercana», «Mover al siguiente lugar», «Detener» | Tramo hasta la parada 1 de 9,4 km por camino; la más cercana se destaca con forma, número y texto («La más cercana por camino es la parada 5, a 20 m.») y su tramo; «Mover al siguiente lugar» la deja primera, recarga y anuncia «Parada movida al primer lugar. Tu orden de hoy quedó guardado.»; «Detener» borra el tramo y la posición. Corregidos los defectos 2 y 4 |
| «Mapa» con OSRM apagado | Tramo y sugerencia | «No se pudo calcular el tramo: el servidor de rutas no respondió…» sin línea ni sugerencia |
| «Ir a esta parada» | Guía por camino, «Leer distancia», «Detener», enlace `geo:` | «La parada 1 está a 3,3 km por camino.» con el tramo real desde el CESFAM por los caminos; el anuncio repite el texto; «Detener» limpia. Corregido el defecto 5 |
| «Rutas» (Q.F.) | Tarjetas de consulta, mapa | Orden guardado por el encargado, 6 tarjetas compactas que se expanden con su mapa pequeño, sin flechas, franja, fotos, tramo ni «Mostrar mi posición»; mapa solo con marcadores |
| Domicilio: «Usar mapa» (Q.F.) | Abrir, clic real, «Marcar el centro del mapa», Esc, «Usar este punto», guardar | Abre en el CESFAM con la mira y el foco en el mapa; el clic marca y copia 6 decimales; la precisión queda vacía; al guardar, «Domicilio guardado.», «Pendiente de verificar» y aparece el mapa pequeño. Corregido el defecto 6 |
| Celular (375 × 812, emulado) | «Mis entregas», «Rutas» | Sin desplazamiento horizontal (solo las pestañas se desplazan en su propio contenedor, como en el 08); flechas de 48 × 48 px; franja de 16 px; corregido el defecto 7 |

Defectos encontrados y corregidos en esta revisión (ninguno lo detectaban las pruebas automáticas):

1. «Mis entregas» no cargaba `leaflet.css`: el mapa pequeño de la tarjeta salía en blanco. Se agregó a su bloque de estilos.
2. **Todos los marcadores numerados** (también los de la versión del 2026-11-12) tenían el número descentrado: `leaflet.css`, cargado después, imponía `display: block` a `.leaflet-marker-icon`. `entregas.css` usa ahora `.leaflet-container .marcador`.
3. Con OSRM apagado, en Windows cada consulta esperaba el tiempo de espera completo: el tramo tardó 2,06 s y la parada más cercana 2,05 s (sobre RNF-05), y «Mis entregas» 1,1 s. `osrm.py` da OSRM por no disponible durante 30 s tras una falla de red, de tiempo o del servidor (no tras un camino imposible), sin volver a esperarlo. Pruebas nuevas en `test_osrm.py`.
4. Con un tramo corto, el mapa se acercaba al tramo y dejaba fuera la posición y la parada. Ahora, al cambiar de destino, encuadra la posición, el tramo y la parada (zoom máximo 16), y al recalcular no mueve la vista. Prueba nueva en `mapa.test.cjs`.
5. Un botón deshabilitado («Mostrar mi posición» mientras sigue la posición, «Usar este punto» sin marca) se veía activo. `entregas.css` le da fondo suave, borde punteado y cursor de no disponible.
6. Al cerrar «Usar mapa», el foco quedaba en el mapa del diálogo cerrado: el evento `close` no llegó en el panel. `cerrar()` devuelve el foco al botón directamente.
7. En celular, los tres botones de la tarjeta compacta iban apilados y «Entregar» se partía a mitad de palabra. «Entregar» y «No entregada» comparten fila, «Expandir» va debajo, y el texto ya no se corta.
8. Con un orden propio y OSRM caído, el «Mapa» repetía «Sin total del recorrido…» en el rótulo y en la leyenda. La leyenda ya no lo repite en el orden propio.

Después de las correcciones: `python manage.py test entregasapp coreapp --noinput --parallel 1` aprobó 413 pruebas; Node, 167 (una nueva del encuadre); y `tools/verificar_spec_09_http.py --osrm-real` dio «aprobado», con un p95 máximo de 641,76 ms en «Rutas» de mañana con 200 paradas, el tramo en 110,67 ms y la parada más cercana en 111,59 ms. Con el OSRM real: matriz de 52 puntos 118,01 ms, de 202 puntos 247,32 ms y un tramo 44,45 ms (p95). No se volvió a correr la suite completa; los cambios solo tocan `entregasapp`, sus plantillas, `entregas.css` y los JS del reparto.

Observación sin corregir: los domicilios sintéticos de demostración caen lejos de los caminos, OSRM los ajusta al camino más cercano y el tramo une solo esos puntos ajustados. Por eso, en la revisión, «20 m» midió entre dos puntos del camino que estaban a unos 100 m de la posición y de la parada. El tramo no se une con una línea recta, porque RF-09-23 la quitó. Con domicilios reales en un camino la diferencia es menor; queda para la revisión en terreno.

### Límites de la enmienda

- La revisión del 2026-11-16 fue en el navegador integrado de escritorio, con el celular emulado a 375 px y la ubicación simulada. Sigue sin probarse en un celular real: el arrastre con el dedo, el toque largo, el desplazamiento cerca de los bordes, la ubicación real en contexto seguro y los avisos al lector de pantalla.
- Las pruebas de Django no usan el OSRM real; el contenedor local solo se usó en la medición aparte (`--osrm-real`). La cartografía rural de OpenStreetMap puede estar incompleta: no se compararon tramos conocidos en terreno.
- La parada más cercana y el tramo se miden con un OSRM simulado en la herramienta (distancia = 1,3 × línea recta).
- La posición viaja a Django en el cuerpo del POST: la evidencia de que no se guarda es de la base de pruebas, la sesión, la caché local y los registros de Django capturados; no cubre registros de un proxy o servidor web delante de Django en un despliegue real.

## Corrección del 2026-11-19: la última numerada no baja

- **Hallazgo (navegador del panel de la app, 375 × 812, previsualización sintética):** con 4 numeradas y 3 sin coordenadas, «Bajar» en la parada 4 la cambió con la primera sin coordenadas, que pasó a «Parada 4»; tres pulsaciones más metieron las tres sin coordenadas a la ruta y la sección quedó vacía. Con 1 numerada y 1 sin coordenadas, la sin coordenadas quedó «Parada 1». La usuaria lo vio también con 1 numerada y 2 en «Sin sector».
- **Corrección:** `services.mover_parada` rechaza «Bajar» en la última numerada; `_orden_controles.html` y `orden.js` (`aplicarOrden`) ocultan esa flecha.
- **Pruebas:** `test_orden_manual.py` agrega `test_la_ultima_numerada_no_baja_y_no_arrastra_una_sin_coordenadas` y `test_flechas_de_la_pagina_con_una_numerada_y_dos_sin_coordenadas`; `orden.test.cjs` agrega la prueba de `aplicarOrden`. `python manage.py test entregasapp.tests.test_orden_manual entregasapp.tests.test_vistas_mapa entregasapp.tests.test_concurrencia_ruta entregasapp.tests.test_permisos_mapa entregasapp.tests.test_ruta_consultas`: 59 OK. `node --test entregasapp/tests/*.test.cjs`: 132 OK.
- **Navegador, después de la corrección (1 numerada y 2 en «Sin sector»):** la numerada no muestra flechas; «Subir» en una sin coordenadas la deja «Parada 1» y la numerada pasa a «Parada 2» sin «Bajar»; «Bajar» en la sin coordenadas la devuelve a su sección.
- **Detalles menores vistos, sin corregir:** el aviso dice «Parada movida a la posición N» también para visitas sin número; con dos toques rápidos, el aviso «Espera a que termine de guardarse…» lo reemplaza el del primer toque; con una sola visita la franja de arrastre se muestra aunque no hace nada; al separar una visita de su grupo, el rótulo de sector se repite.

## Enmienda del 2026-11-19: las secciones no se mezclan

- **Pedido de la usuaria:** con una sin coordenadas subida a «Parada 1» y una con coordenadas debajo, al subir la con coordenadas la sin coordenadas volvía sola a su sección (límite aceptado del 2026-11-16). La usuaria decidió que las sin coordenadas no puedan pasar a «Por visitar en orden».
- **Cambio:** `consultas._aplicar_orden_guardado`, `services._dentro_de_su_seccion` (desde `mover_parada`), `_orden_controles.html`, `_ruta.html` (texto) y `orden.js` (flechas y arrastre por sección).
- **Pruebas actualizadas:** en `test_orden_manual.py`, los casos que subían o movían D (sin coordenadas) a la ruta ahora esperan el rechazo, y hay pruebas nuevas de que las sin coordenadas se ordenan entre ellas (flechas y posición). En `test_ruta_consultas.py`, un orden guardado con la sin coordenadas adelante se lee con ella al final. `test_permisos_mapa.py` arma el orden manual moviendo una con coordenadas. En `orden.test.cjs`: las flechas de borde y un arrastre de una sin coordenadas que no sale de su sección y envía la posición 3.
- **Comandos:** `python manage.py test entregasapp coreapp`: 546 OK. `node --test entregasapp/tests/*.test.cjs`: 133 OK.
- **Navegador (375 × 812, previsualización sintética, 4 con coordenadas y 3 sin coordenadas):** la primera sin coordenadas no ofrece «Subir» y la última numerada no ofrece «Bajar»; las flechas reordenan dentro de cada sección. Arrastrar con el mouse una sin coordenadas sobre la última numerada, o la última numerada sobre las sin coordenadas, termina en «La parada quedó en el mismo lugar.» sin cambiar de sección. No se probó el arrastre táctil en un celular real.

## Aceptación funcional

Pendiente.
