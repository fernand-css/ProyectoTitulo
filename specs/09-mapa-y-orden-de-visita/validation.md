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

## Aplicación y reversión

Migración `entregasapp/0002_ordenruta`: aplicada solo en las bases de pruebas y en la SQLite temporal de la herramienta. **La base PostgreSQL del proyecto no se migró**; hay que aplicar `python manage.py migrate` en la base de demostración elegida cuando el usuario lo apruebe. Revertirla (`python manage.py migrate entregasapp 0001`) elimina solo los órdenes manuales. `generar_domicilios_demo` no se ejecutó sobre la base del proyecto.

## Aceptación funcional

Pendiente.
