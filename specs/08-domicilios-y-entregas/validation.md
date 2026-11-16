# Validación — 08 / Domicilios y entregas a domicilio

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-11. Entorno: Windows 11, Python 3.13.17, Django 5.2.19, Pillow 12.3.0, Node 24.22.1. Pruebas de Django sobre la base de pruebas desechable de PostgreSQL (`test_<DB_NAME>`); herramienta HTTP sobre SQLite y carpeta privada temporales. Solo datos sintéticos (670 pacientes generados, RUT ficticios con DV válido, fotos dibujadas en memoria).
Referencia de código: rama `crojas-base`, cambios sin commit sobre `6032b7a`.
Estado: **verificación técnica ejecutada**; revisión de navegador, axe, usabilidad y aceptación funcional **pendientes**. El spec sigue en **Aprobado**.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-08-01 | `entregasapp/tests/test_elegibilidad.py` (6 pruebas); suite del 04 (`turnosapp.tests.test_servicios`, `test_vistas`) | 80 años y 364 días no; 81 sí; postrado de 50 sí; crónico de 60 no; excepción vigente sí y retirada no; el tótem clasifica igual (comparación con la fórmula anterior en 64 combinaciones, incluido el 29 de febrero) | Coincide en todos los casos; las pruebas del 04 pasan sin cambios | aprobada |
| RF-08-02 | `test_excepciones.py` (4) | Una vigente por paciente; segunda inscripción y paciente ya elegible rechazados; retiro con autor y fecha; la entrega abierta sigue abierta | Igual | aprobada |
| RF-08-03 | `test_domicilios.py` (10); escenarios concurrentes 6 y 6b | Creación desde el padrón; la importación del 03 no toca el domicilio; edición por versión: la segunda recibe «El domicilio cambió; revisa los datos nuevos.» | Igual; 3 ediciones simultáneas desde la misma versión: 1 guardada y 2 rechazadas; 2 creaciones simultáneas: 1 domicilio | aprobada |
| RF-08-04 | `test_domicilios.py`; `test_vistas.py` (`DomicilioVistaTests`) | Verificar sin sector se rechaza; con sector queda autor y hora; cambiar referencias, sector, localidad, dirección o coordenadas vuelve a pendiente; la Q.F., el superusuario y el Técnico no verifican | Igual; precisión sola, guardar sin cambios y fotos no cambian la verificación; aviso «La dirección del padrón cambió» con la dirección nueva | aprobada |
| RF-08-05 | `coreapp/tests/test_custom_image.py` (8); `test_fotos.py` (6); `test_vistas.py` (fotos por HTTP) | JPEG con GPS y PNG guardados como JPEG sin metadatos; PDF renombrado, GIF, truncada, 6 MB, demasiados píxeles y cuarta foto rechazados; sin huérfanos; 302 sin sesión, 200 `no-store` con rol; `/media/` no existe | Igual (EXIF vacío al releer, orientación corregida, lado mayor 1600); borrado del archivo tras confirmar; rollback sin archivo | aprobada |
| RF-08-06 | `test_programacion.py` (6); `test_vistas.py` (`ProgramarVistaTests`); escenario concurrente 1 | Solo la receta vigente (excluye vencida, agotada, futura, en turno activo y pendiente de retiro); una entrega abierta aun con 5 solicitudes simultáneas; reenvío idempotente; rechazos con motivo | Igual | aprobada |
| RF-08-07 | `test_doble_via.py` (5); escenarios concurrentes 2 y 4; herramienta HTTP | Tótem: «Tienes un despacho a domicilio programado. Consulta con el personal.» sin datos ni número; ventanilla: «La receta tiene una entrega a domicilio abierta.»; tras anular, vuelve a funcionar | Igual; el tótem emite con las recetas fuera del despacho; la reincorporación del 05 también se rechaza | aprobada |
| RF-08-08 | `test_registro.py` (`MisEntregasConsultaTests`); `test_vistas_encargado.py` (6) | Hoy, atrasadas («Atrasada desde el dd/mm») y próximas aparte; sin las de otro encargado; texto cuando no hay | Igual; el inicio del encargado (`/`) muestra «Mis entregas» | aprobada |
| RF-08-09 | `test_registro.py`; escenarios concurrentes 3 y 4 | Una receta vigente descontada (+1) y una vencida «no descontada» con causa; reenvío sin otro descuento; intento de mañana y de otro encargado rechazados | Igual; cupo agotado justo antes queda «no descontada» sin exceder | aprobada |
| RF-08-10 | `test_registro.py`; `test_vistas_encargado.py` | Sin motivo y «Otro» sin nota rechazados; con motivo, pendiente de gestión sin descuento y recetas aún bloqueadas | Igual | aprobada |
| RF-08-11 | `test_gestion.py` (11); `test_vistas.py` (`GestionVistaTests`); escenario concurrente 5 | Filtros exactos con una consulta; reasignar deja el intento anterior intacto y el nuevo en «Mis entregas» del otro encargado; un intento sin resultado queda «reasignado»; anular libera recetas | Igual; reasignar frente a registrar: exactamente un ganador en 3 vueltas × 3 corridas | aprobada |
| RF-08-12 | `test_gestion.py` (`RecetasNoDescontadasTests`); `test_vistas.py` | Sale de la lista con autor y fecha; texto cuando no queda ninguna | Igual | aprobada |
| RF-08-13 | `coreapp/tests/test_navegacion.py`, `test_inicio.py`; `test_vistas.py` (`FichaYRecetaTests`); `test_estructura.py` | Menú y pestañas por perfil; Técnico sin botones de cambio; inicio del encargado abre «Mis entregas»; ficha con domicilio y entrega abierta | Igual | aprobada |
| RF-08-14 | `test_permisos.py` (8) | Anónimo a inicio de sesión; cuenta inactiva o sin perfil sin acceso; POST del Técnico 403; POST sin CSRF 403; `no-store`; URL solo con enteros; auditoría sin RUT, nombres, direcciones, notas ni coordenadas; rollback si falla la auditoría | Igual | aprobada |
| RF-08-15 | `test_concurrencia.py` (7 pruebas, 6 escenarios con hilos y conexiones de PostgreSQL); regresión completa | Sin entregas abiertas duplicadas, resultados ni descuentos dobles; cupo nunca excedido; ninguna receta a la vez en turno activo y entrega abierta; ediciones no perdidas; pruebas del 03 al 07 sin cambiar aserciones | Igual (ver regresión) | aprobada |

## Regresión de la base

| Comando | Resultado |
|---|---|
| `python manage.py test --noinput --parallel 1` antes de empezar (base `6032b7a`) | 642 pruebas: 641 aprobadas y 1 error previo ajeno al 08 (`turnosapp.tests.test_sala_servidor`: Windows no deja borrar su SQLite temporal, `WinError 32`). |
| `python manage.py test --noinput --parallel 1` al cierre | **755 pruebas: 754 aprobadas** y el mismo error previo de `test_sala_servidor`. 113 pruebas nuevas (104 en `entregasapp`, 8 en `test_custom_image.py` y 1 en `test_navegacion.py`). |
| `python manage.py test entregasapp coreapp --noinput` tras los últimos ajustes (importaciones sin uso y validación del POST de excepciones) | 232 pruebas aprobadas. |
| `python manage.py test entregasapp.tests.test_concurrencia` tres veces seguidas | 7 aprobadas en cada corrida. |
| `node --test turnosapp/tests/*.test.cjs recetasapp/tests/*.test.cjs entregasapp/tests/*.test.cjs` | 75 aprobadas (5 nuevas de `ubicacion.js`). |
| `python manage.py check` y `python manage.py makemigrations --check --dry-run` | Sin problemas; sin cambios pendientes. |

Durante la implementación, la regresión detectó y se corrigieron: (1) la dependencia de `entregasapp/0001` sobre `recetasapp/0004` rompía dos pruebas de migración del 04/05 (ahora depende de `0002`); (2) la redirección del inicio del encargado rompía seis pruebas del 02, 06 y del tablero que esperan 200 en `/` (ahora el inicio muestra «Mis entregas» sin redirigir); (3) el escenario concurrente 5 encontró que «no entregada» y «reasignar» simultáneas podían aceptarse ambas (ahora se exige el resultado visto). Ninguna aserción del 03 al 07 cambió.

## Rendimiento HTTP

`python tools/verificar_spec_08_http.py` (2026-11-11, salida 0, resultado «aprobado»): SQLite y carpeta privada temporales, 670 pacientes sintéticos (600 mayores de 80 y 70 postrados), 10 excepciones y 4 encargados. Recorre domicilios (lista, búsqueda por RUT en POST, registro con coordenadas y verificación), 20 fotos generadas con EXIF GPS falso (se comprueba que la guardada no tiene EXIF ni supera 1600 px, que sin sesión redirige al inicio de sesión y que `/media/` da 404), 100 programaciones (más un reenvío que no duplica), el tótem con despacho abierto (400 con el mensaje, sin datos personales, sin turnos ni número consumido), «Mis entregas», 50 entregadas (más un doble envío sin descuento extra) y 50 no entregadas, consultas con filtros y 50 reasignaciones. Comprueba también que la auditoría no contiene datos personales.

| Escenario | Muestras | p50 (ms) | p95 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|
| Lista de domicilios | 100 | 52,11 | 74,76 | 130,54 |
| Búsqueda de domicilio (POST) | 100 | 40,22 | 61,00 | 67,18 |
| Guardar domicilio | 100 | 88,08 | 115,96 | 133,74 |
| Verificar domicilio | 100 | 82,57 | 109,30 | 118,93 |
| Ver foto privada | 20 | 13,26 | 34,30 | 35,31 |
| Programar: revisar recetas | 100 | 42,66 | 61,27 | 85,54 |
| Programar: confirmar | 100 | 96,74 | 137,71 | 276,47 |
| Mis entregas | 100 | 49,19 | 62,35 | 66,06 |
| Registrar entregada | 50 | 76,61 | 100,87 | 111,03 |
| Registrar no entregada | 50 | 64,41 | 99,87 | 136,68 |
| Reasignar | 50 | 81,47 | 105,70 | 123,83 |
| Programación con filtros | 100 | 38,61 | 56,15 | 84,83 |
| Pendientes con filtros | 100 | 48,71 | 63,38 | 82,67 |
| Tótem con despacho abierto | 100 | 23,68 | 46,39 | 61,95 |
| Subida de foto (aparte, sin compromiso) | 20 | 97,66 | 114,18 | 123,74 |

Todos los escenarios quedan bajo los 2 s de p95 de RNF-05. Es loopback con servidor WSGI y SQLite: no mide la red del CESFAM ni redes móviles, el dibujo en el navegador, la cámara ni la ubicación real. La subida de fotos se informa sin prometer un valor para redes móviles.

## Revisión visual si aplica

No ejecutada. En esta sesión no se abrió un navegador: quedan pendientes la revisión visual en escritorio y celular, axe, la navegación por teclado, el zoom al 200 %, la ubicación real del navegador en contexto seguro (HTTPS o `localhost`) y la toma de fotos desde un celular. Lo comprobado sin navegador está en `test_estructura.py` (un `h1`, ids únicos, etiquetas de campos y `alt` en imágenes) y en `coreapp/tests/test_estaticos.py` (`entregas.css` usa solo variables de `base.css`, cuyo contraste AA ya se verifica).

## Límites y fallos

- La parte sin conexión de HU-15 (RNF-03, NS05) queda para la reserva 11. El `operacion_id` del registro ya es único e idempotente, pero hoy lo genera el servidor al dibujar el formulario.
- HU-14 (mapa y orden de visita) queda para el 09; HU-19 y HU-22, para la reserva 12; el panel de mermas, para el 10.
- La ubicación del navegador requiere HTTPS o `localhost`; sin ello el botón lo explica y se escriben las coordenadas a mano.
- La usabilidad con cinco personas y la aceptación funcional requieren evidencia propia.
- Pruebas del 01/02 ajustadas por RF-08-13 (menú y pestañas nuevas): ver la lista en [plan.md](plan.md#notas-de-implementación-2026-11-11). Las del 03 al 07 no cambiaron.

## Aplicación y reversión

Migración nueva: `entregasapp/0001_initial` (depende de `recetasapp/0002` y del modelo de usuario). Solo se aplicó en bases de prueba y en la SQLite temporal de la herramienta; **no se migró la base PostgreSQL del proyecto**. Para usar el módulo: `python manage.py migrate`. Antes de revertir, respaldar la base y la carpeta `ARCHIVOS_PRIVADOS_ROOT`; los descuentos ya hechos y las `EntregaReceta` creadas por despachos no se revierten.

## Ampliación del 2026-11-13 (implementada)

Fecha: 2026-11-13. Rama `crojas-base`, cambios sin commit sobre `6262cfe`. El entorno es el mismo de arriba, con PostgreSQL desechable para las pruebas de Django y SQLite temporal para la herramienta. La fila de RF-08-01 de la tabla principal valida la regla anterior (`edad > 80`); la vigente es la de esta tabla.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-08-01 | `test_elegibilidad.py` (7 pruebas); `turnosapp/tests/test_servicios.py` (`test_limites_de_edad_cronico_y_postrado`) | 79 años y 364 días: no elegible y preferencial en el tótem. 80 recién cumplidos y 81: elegibles y bloqueados con «Consulta tu despacho con el personal». `condicion_elegible`, `es_elegible`, `requiere_despacho_en` y el tótem coinciden con `>= 80` en 112 combinaciones (incluido el 29 de febrero) | Igual. En el 04 solo cambió la tupla de 80 (preferencial → bloqueo) y se agregó 79 | aprobada |
| RF-08-16 | `test_programar_lista.py` (15 pruebas) | Páginas de 50 con su total. Cada filtro solo y combinado («Sin sector», localidad con otra grafía, paciente con dos motivos). Búsqueda «G»…«Gonz» y por RUT. Entrega abierta rotulada, enlazada y sin casilla activa. Respaldo `accion=buscar` igual al fragmento. Consultas constantes por página. Sin RUT, nombres ni `buscar=` en las URL. Técnico y encargado 403; CSRF; `no-store` | Igual | aprobada |
| RF-08-16 | `programar.test.cjs` (Node) | Espera de 300 ms; sin solicitud si los filtros no cambian; cancelación y descarte de respuestas fuera de orden; anuncio de la cantidad; error con «Reintentar» | Igual | aprobada |
| RF-08-17 | `test_programar_lote.py` (16 pruebas) | `recetas_para_despacho_lote` igual al cálculo por paciente y con consultas constantes. Cada paciente por separado: omitidos con motivo y sin revertir a los demás. Reenvío completo o por partes sin duplicar. Escenario de aceptación: 120 filtrados con 4 abiertas y 2 sin recetas dan 114 en la revisión y «programado» en 114 tramos de JSON, sin RUT ni nombres. Firma alterada, otra Q.F., tramo inválido o mayor de 25 y fecha pasada firmada: 400 sin cambios. Técnico 403. Sin JavaScript: «Se programaron 2 de 3» con los omitidos. Auditoría: una `entrega.programada` por entrega, sin datos personales | Igual | aprobada |
| RF-08-17 | `programar.test.cjs` (Node) | Selección conservada entre páginas y búsquedas; «Seleccionar los N filtrados» anulado al cambiar un filtro, con aviso; `todos=1` o ids ocultos al enviar; tramos en orden con avance; corte y reintento desde el tramo sin respuesta; rechazo del servidor con su texto; doble clic al final sin reenvío | Igual | aprobada |
| RF-08-17 | `test_estructura.py` (`test_pantallas_de_programar_varios`) | Selección, revisión y resumen final con un `h1`, ids únicos y campos etiquetados; `role="status"`, `<progress>` y `<details>` presentes | Igual | aprobada |
| RF-08-15 | `test_concurrencia.py`, escenarios 7 a 10 | Dos lotes con pacientes en común; el mismo tramo dos veces a la vez; un lote frente al tótem de una excepción del lote; un lote frente a la programación individual. Resultado esperado: una sola entrega abierta por paciente, programado en un lote y omitido en el otro, y ninguna receta a la vez en un turno activo y en una entrega abierta | Igual en 3 vueltas por escenario; el archivo completo (11 pruebas) pasó 3 corridas seguidas | aprobada |

### Regresión de la ampliación

| Comando | Resultado |
|---|---|
| `python manage.py test --noinput --parallel 1` antes de empezar (base `6262cfe`) | 834 pruebas: 833 aprobadas y el error previo de `test_sala_servidor` (`WinError 32`). |
| `python manage.py test --noinput --parallel 1` al cierre | **871 pruebas aprobadas** (37 nuevas). En esta corrida, el error previo de `test_sala_servidor` no apareció. |
| `python manage.py test entregasapp.tests.test_concurrencia` tres veces seguidas | 11 aprobadas en cada corrida. |
| `node --test entregasapp/tests/*.test.cjs turnosapp/tests/*.test.cjs recetasapp/tests/*.test.cjs` | 101 aprobadas (11 nuevas de `programar.test.cjs`). |
| `python manage.py check` y `python manage.py makemigrations --check --dry-run` | Sin problemas; «No changes detected» (la ampliación no trae migraciones). |

Observación ajena a la ampliación: en una corrida parcial (`entregasapp coreapp`) falló una vez `test_concurrencia_ruta.test_2_tres_ediciones_desde_la_misma_version_una_gana` (spec 09, código no tocado aquí). Pasó en 3 reejecuciones seguidas y en la regresión completa. Queda como posible intermitencia del 09 para revisar.

### Rendimiento HTTP de la ampliación

`python tools/verificar_spec_08_http.py` (2026-11-13, salida 0, «aprobado»). Usa las mismas condiciones de arriba, más 40 pacientes presenciales sintéticos para el tótem. Antes de ampliarla, la herramienta fallaba en «Mis entregas» porque buscaba un marcador anterior al spec 09; se corrigió (ver [plan.md](plan.md#notas-de-implementación-de-la-ampliación-2026-11-13)). Los escenarios anteriores siguen bajo los 2 s (p95 máximo 110,09 ms, «Registrar entregada»).

| Escenario | Muestras | p50 (ms) | p95 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|
| Lista inicial de «Programar entrega» (680 elegibles) | 50 | 42,89 | 61,62 | 64,86 |
| Fragmento con búsqueda y filtros | 100 | 36,32 | 50,47 | 63,90 |
| Tramo de 25 pacientes al confirmar | 25 | 687,42 | 845,89 | 951,71 |
| Tótem (emisión real) mientras corre el lote | 40 | 59,93 | 260,45 | 515,83 |

Medido aparte, sin compromiso de p95:
- **Revisión del lote completo:** 680 seleccionados con «todos» (620 programables y 60 omitidos con entrega abierta), en 163,72 ms y 204,2 KB de HTML.
- **Confirmación del lote:** 25 tramos en 17,25 s. Entre revisión y confirmación, 17,7 s.

Comprobaciones de la herramienta:
- Reenviar un tramo ya confirmado devuelve «programado» sin entregas nuevas.
- Ninguna receta queda a la vez en un turno activo y en una entrega abierta.
- Las 40 emisiones del tótem durante el lote dieron comprobante.

Es loopback con WSGI y SQLite. No mide la espera de 300 ms ni el dibujo en el navegador.

### Pendientes de la ampliación

No ejecutados en esta sesión (no se abrió un navegador):
- La búsqueda en vivo con lector de pantalla y teclado: foco que no se mueve y anuncio de la cantidad.
- La barra de selección en celular y con zoom al 200 %.
- La confirmación por tramos con una red real.
- axe y la usabilidad con cinco personas.
- La aceptación funcional.

Hay que avisar al equipo del cambio del 04, que se trabajó en `fdaza`.

## Enmienda del 2026-11-15 (verificación técnica)

Estado: **verificación técnica ejecutada** el 2026-11-15 en `crojas-base`, sin commit, sobre `caf8b9f`. Base de pruebas desechable de PostgreSQL; herramienta HTTP y vista local sobre SQLite y carpeta privada temporales. Solo imágenes generadas (Pillow en el servidor y `<canvas>` en el navegador). Sin migraciones.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-08-18 | `test_fotos.py` (`GestionarFotosTests`, 8; `FotosServicioTests`, 7, las reglas del RF-08-05 ahora a través de `gestionar_fotos`) | Todo o nada; «La foto 2 no se pudo procesar»; conjunto cambiado rechazado; con 3 solo se agrega al marcar una; los archivos borrados se eliminan al confirmar y los nuevos si falla; auditoría sin datos personales | Igual: borrar 1 y agregar 2 (JPEG con GPS y PNG) deja 3 JPEG sin EXIF y 3 entradas de auditoría; la foto 2 inválida no cambia la base, los archivos ni la auditoría; una falla de la base borra los JPEG nuevos | aprobada |
| RF-08-18 | `test_concurrencia.py` (`ConcurrenciaFotosTests`, escenarios 11 a 13 con hilos y conexiones de PostgreSQL), tres corridas seguidas | Uno gana y el otro recibe el aviso; nunca más de 3; ningún archivo huérfano | 3 aprobadas en cada corrida (dos desde el mismo estado; guardar frente a borrar; tres que agregan con 2 guardadas) | aprobada |
| RF-08-18 | `test_vistas.py` (`FotosModalVistaTests`, 5), `test_permisos.py`, `test_vistas.py` (`DomicilioVistaTests`) | Botón según la cantidad; JSON con el número de la foto; página sin JavaScript; Técnico 403; CSRF; `volver` externo rechazado | Igual: 0 fotos → «Registrar fotos» con 3 espacios; 2 → «Gestionar fotos» con 1; 3 → 0 espacios y «Ya hay 3 fotos…»; el Técnico ve miniaturas y visor sin botón | aprobada |
| RF-08-18 | Navegador del panel de la app (Chromium), vista local aislada (3 pacientes sintéticos, cuenta de terreno), escritorio y 375 × 812 | Modal como el lienzo; error junto a la foto; guardado; cerrar descarta y devuelve el foco | Marcar «Borrar» tacha la foto, cambia a «Deshacer» y abre un espacio; una PNG y un PDF renombrado .jpg dan «La foto 2 no se pudo procesar: el archivo no es una foto JPEG o PNG válida.», el foco va al aviso, el modal sigue abierto y no cambia nada; luego, borrar 1 y agregar 1 guarda y recarga con «Fotos guardadas sin metadatos ni ubicación.»; la X, «Cancelar» y Esc (tecla real) descartan lo elegido y el foco vuelve al botón; sin desplazamiento horizontal a 375 px | aprobada (revisión técnica del agente, no de usuarios) |
| RF-08-18 | Celular real: «Sacar foto» con la cámara; red cortada al guardar | La foto vuelve al modal; sin red no se guarda nada y se avisa | El aviso sin red está probado en Node (`fotos.test.cjs`); la cámara real y el corte de red reales no se probaron | pendiente |
| RF-08-19 | `visor.test.cjs` (8); navegador del panel | Se cierra con la X, con un clic fuera y con Esc; foco contenido y de vuelta en la miniatura | Igual en Node y en el navegador (tres ciclos seguidos sin imágenes sobrantes); la miniatura tiene `role="button"` y el nombre «Ver foto ampliada: …»; Espacio la abre | aprobada; lector de pantalla pendiente |
| RF-08-20 | `grep` en plantillas y JavaScript; `test_estructura.py`; `mapa.test.cjs`; `makemigrations --check --dry-run` | Sin «Ver domicilio»; «Nombre de la localidad»; sin migraciones | No queda «Ver domicilio» (sí «Ver domicilios», que no cambia); el formulario, la ficha y el filtro dicen «Nombre de la localidad»; `No changes detected` | aprobada |
| RNF-05 | `tools/verificar_spec_08_http.py` (primera corrida; ver límites) | p95 ≤ 2 s sin archivos grandes; tres fotos de 5 MB medidas aparte | Guardado del modal (borrar 1 y agregar una PNG pequeña), 20 muestras: p95 135,63 ms; subida de una foto de cámara: p95 157,54 ms; tres JPEG de 4,98 MB en una solicitud, 5 muestras: p95 1328,77 ms (loopback); ver foto: p95 21,44 ms | aprobada para las fotos |
| RNF-04 | `test_estructura.py` (diálogos con nombre, botones con tipo, miniaturas con nombre); navegador | Diálogos accesibles; errores asociados y anunciados | Estructura aprobada; el error de la foto queda en `aria-describedby` de su descripción y recibe el foco; axe, lector de pantalla y usabilidad no se ejecutaron | pendiente (axe y usabilidad) |

### Regresión de la enmienda

| Comando | Resultado |
|---|---|
| `python manage.py test --noinput --parallel 1` (primera corrida) | 967 pruebas: 4 errores nuevos en `test_plantillas` (los parciales de fotos no se dibujaban con contexto vacío; se corrigió con guardas `{% if f %}` / `{% if foto %}`) y el error previo de `test_sala_servidor` (`WinError 32`). |
| `python manage.py test coreapp.tests.test_plantillas coreapp.tests.test_estaticos entregasapp --noinput` tras la corrección | 279 aprobadas. |
| `python manage.py test --noinput --parallel 1` (corrida final) | **967 pruebas: 966 aprobadas** y el mismo error previo, ajeno al 08, de `test_sala_servidor` (`WinError 32`). |
| `node --test turnosapp/tests/*.test.cjs recetasapp/tests/*.test.cjs entregasapp/tests/*.test.cjs coreapp/tests/*.test.cjs` | 124 aprobadas (incluye `fotos.test.cjs`, 7, y `visor.test.cjs`, 8). |
| `python manage.py check`; `makemigrations --check --dry-run` | Sin problemas; `No changes detected`. |

Hallazgos corregidos durante la revisión en el navegador:
- Con el atributo `hidden`, el aviso general vacío seguía visible porque `.message` fija `display`.
- Los textos `sr-only` agrandaban el diálogo y la cabecera se salía de la vista.
- El fondo del visor dejaba pasar la página detrás del pie.
- Chrome entregó el evento `close` del `<dialog>` con retraso: lo elegido no se limpiaba y una imagen vieja podía quedar en el visor. Ahora se limpia al cerrar con la X, «Cancelar», un clic fuera o Esc (`cancel`).

### Límites

- **Herramienta HTTP:** la medición de fotos es de la primera corrida, que pasó todas las comprobaciones de fotos y después falló por el p95 del tramo de 25 del lote (4253,83 ms; antes 845,89 ms). La segunda y la tercera corrida fallaron antes de imprimir el informe, en `programados_lote == programables` (619 y 617 de 620), con el tótem emitiendo en paralelo. Es la misma falla intermitente que ya anotó la validación del 04 tras su enmienda. Esta enmienda no toca la programación ni el tótem, y los presenciales del tótem (45 años) no son elegibles para el lote. Queda **pendiente de investigar** fuera de esta enmienda (investigada y corregida después: ver [Falla intermitente del lote frente al tótem](#falla-intermitente-del-lote-frente-al-tótem-2026-11-15)).
- No se probaron la cámara de un celular real, un corte de red real, un lector de pantalla, axe ni la usabilidad con cinco personas.
- Si el proceso muere entre escribir los JPEG y la transacción, pueden quedar archivos sin fila (riesgo aceptado en el plan; sin limpieza periódica).
- La revisión en el navegador la hizo el agente, con datos sintéticos; no reemplaza la aceptación del usuario.

## Falla intermitente del lote frente al tótem (2026-11-15)

Diagnóstico y corrección de la falla que anotaron los límites de arriba y la validación del 04 (`programados_lote == programables`: 619 y 617 de 620 en el paso 10 de la herramienta). Trabajo en un worktree desde `crojas-base` (`caf8b9f`) con los cambios sin commit de la enmienda de fotos, sin commit. Solo pacientes sintéticos, SQLite temporal y bases PostgreSQL desechables de nombre único (creadas y borradas en cada corrida; se comprobó que no quedó ninguna). La base PostgreSQL del proyecto no se usó ni se migró.

### Causa

- **SQLite (la herramienta):** los pacientes que faltaban salieron como «No se pudo programar; vuelve a confirmar». `programar_entrega` agotó los 8 intentos de `reintentar_conflictos`, **todos con `OperationalError: database is locked`**, de 3 a 45 ms cada uno. No hubo `ConflictoOperacion` ni `ConflictoCola`, ni otra regla. La SQLite temporal usa el diario `delete` y el `BEGIN` diferido de Django. `programar_entrega` empieza leyendo (`autorizar`, el usuario, el `get_or_create` de la cola) y escribe en el UPDATE de `bloquear_cola`. Si otra conexión tiene la escritura, SQLite responde ocupado **al instante**, sin la espera de 5 s, para evitar un interbloqueo. Las escrituras del tótem que empiezan escribiendo (guardar la sesión, contar el intento del RF-04-12) sí esperan su turno. Una prueba mínima con `sqlite3` lo muestra: leer y luego escribir falla en 0,4 ms; escribir primero o `BEGIN IMMEDIATE` espera unos 340 ms y sigue.
- **PostgreSQL (la base real):** con el mismo escenario, el lote no omitió a nadie (14 rondas de 620), pero **el tótem dejó a 6 de 560 personas sin número** («El sistema está ocupado.»). `bloquear_cola` comparaba la versión leída: el tótem esperaba el bloqueo de la fila del día mientras el lote programaba y, al llegarle el turno, la versión había cambiado (`ConflictoCola`). Con las transacciones seguidas del lote, a veces perdía los 12 reintentos.
- **Personas distintas:** en la prueba, el tótem atiende a 40 pacientes presenciales de 45 años y el lote a 620 mayores de 80. El choque viene de que la cola del día es una sola llave para toda la jornada, no de que se cruce la misma persona.
- **No la creó la enmienda del 04:** con `ecc860f` (antes de la enmienda) la reproducción también omite (6 de 6 rondas).

### Corrección aplicada

1. `turnosapp.cola.bloquear_cola` toma la fila del día con `UPDATE version = version + 1`, **sin comparar la versión**, y la relee. Quien espera sigue cuando el otro confirma. Todos los llamadores (tótem, atención, preparación, retiro, entregas, gestión por personal) leen sus datos después de tomar la cola, o los releen. En SQLite la comparación nunca fallaba. Anotado en el plan del 05.
2. `entregasapp.services.programar_lote` vuelve a intentar al final del tramo a los pacientes con la base ocupada, hasta 3 vueltas (`VUELTAS_OCUPADOS`, pausa de 50 ms que crece), con la misma operación `uuid5(lote, paciente)`.
3. `tools/verificar_spec_08_http.py` informa los omitidos de la confirmación con su motivo (solo el id sintético) y falla si el hilo del tótem no recibe el formulario o se cae. Antes, el hilo podía morir sin que la herramienta lo notara.

Descartadas tras medirlas: SQLite en modo `IMMEDIATE` en la herramienta (el lote acaparaba la escritura; el tótem emitió 31, 3 y 18 de 40, y en una corrida su hilo murió) y una pausa de 15 ms entre pacientes (PostgreSQL siguió rechazando 2 de 320 en el tótem, y el p95 del tramo pasó de 5 s).

### Evidencia

| Prueba | Resultado |
|---|---|
| Reproducción enfocada del paso 10, SQLite, código anterior | 8 de 8 rondas con omitidos (15); con `ecc860f`, 6 de 6 (11) |
| Ídem, PostgreSQL desechable, código anterior | 0 omitidos; tótem con 6 de 560 sin número; 60 a 120 `ConflictoCola` del tótem por ronda |
| Ídem, PostgreSQL desechable, **código corregido** | 8 rondas: 0 omitidos, tótem 320 de 320, **0 conflictos** en el lote y en el tótem. p95 del tramo 1,2 a 1,8 s en 6 rondas; 4,3 s en una ronda lenta (lote de 41 s, sin conflictos) |
| `turnosapp.tests.test_concurrencia_cola.LlaveDelDiaTests` (nueva, hilos y PostgreSQL) | Quien espera la fila sigue y ve la versión del otro. Con el `bloquear_cola` anterior falla con `ConflictoCola` |
| `test_programar_lote.py` (2 nuevas) | El ocupado vuelve al final del tramo y queda programado sin duplicar; si sigue ocupado, sale «vuelve a confirmar» tras 1 + 3 intentos sin detener a los demás |
| `python manage.py test --noinput --parallel 1` (base de pruebas PostgreSQL de nombre único) | **970 pruebas: 969 aprobadas** y el error previo, ajeno, de `test_sala_servidor` (`WinError 32`) |
| `python tools/verificar_spec_08_http.py`, 3 corridas seguidas | Las 3 con 620 de 620 y el tótem 40 de 40 (p95 432, 206 y 218 ms). p95 del tramo de 25: **1897 ms (aprobada), 2232 ms y 2044 ms (fallan por p95)** |
| Revisión en `crojas-base` con la corrección del lote y la enmienda de fotos juntas (2026-11-15) | `python manage.py test --noinput --parallel 1`: **970 pruebas, 969 aprobadas** y el error previo de `test_sala_servidor`. Node 124 aprobadas; `check` y `makemigrations --check --dry-run` sin cambios. `tools/verificar_spec_08_http.py`, 1 corrida: **aprobada** (salida 0), lote 620 de 620, tramo de 25 p95 1010,76 ms, tótem durante el lote p95 209,99 ms, guardado de fotos p95 152,77 ms. |

### Límites

- **p95 del tramo de 25 en SQLite (decisión del equipo, 2026-11-15: se registra como límite de la medición).** Mientras el tótem de la herramienta emite 40 personas seguidas (unas 10 por segundo, mucho más que un tótem real), el tramo de 25 roza los 2 s: 1897, 2232 y 2044 ms en las tres corridas con la corrección. Es la espera del lote en la SQLite temporal, donde el bloqueo de escritura es de toda la base. La corrección de `bloquear_cola` no la cambia, y no es un paciente omitido ni un conflicto: en las tres corridas se programaron 620 de 620 y el tótem dio 40 de 40. Por eso la herramienta puede terminar con `AssertionError` en la comprobación final del p95 aunque el informe diga «aprobado» en todo lo demás. El escenario de la herramienta no se cambió.
- La latencia en PostgreSQL se midió en un equipo con tiempos variables (lotes de 19 a 41 s; una ronda con el tramo en 4,3 s sin conflictos). No reemplaza una medición en el servidor del prototipo.

## Aceptación funcional

Pendiente.
