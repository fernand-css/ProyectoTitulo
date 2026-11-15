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

## Enmienda del 2026-11-15 (no ejecutada)

Estado: **no ejecutada**. La enmienda está en Borrador; no hay código ni resultados. Las filas describen la evidencia que hará falta.

| RF | Prueba / pasos / comando previstos | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-08-18 | `test_fotos.py`; `test_vistas.py`; `fotos.test.cjs` | Todo o nada; «La foto 2 no se pudo procesar»; conjunto cambiado rechazado; botón según la cantidad; página sin JavaScript | — | no ejecutada |
| RF-08-18 | `test_concurrencia.py` (tres escenarios nuevos, tres corridas) | Nunca más de 3 fotos; un ganador; ningún archivo huérfano | — | no ejecutada |
| RF-08-18 | Celular real: «Sacar foto» con la cámara; red cortada al guardar | La foto vuelve al modal; sin red no se guarda nada y se avisa | — | no ejecutada |
| RF-08-19 | `visor.test.cjs`; navegador con teclado y lector de pantalla | Se cierra con X, clic fuera y Esc; foco contenido y de vuelta en la miniatura | — | no ejecutada |
| RF-08-20 | Búsqueda en plantillas y JavaScript; `makemigrations --check --dry-run` | Sin «Ver domicilio»; «Nombre de la localidad»; sin migraciones | — | no ejecutada |
| RNF-05 | `tools/verificar_spec_08_http.py` (guardado de fotos) | p95 ≤ 2 s sin archivos grandes; tres fotos de 5 MB medidas aparte | — | no ejecutada |
| RNF-04 | axe, teclado y usabilidad | Diálogos accesibles; errores asociados y anunciados | — | no ejecutada |

## Aceptación funcional

Pendiente.
