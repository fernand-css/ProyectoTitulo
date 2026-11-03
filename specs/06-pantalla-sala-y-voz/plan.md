# Plan técnico — 06 / Pantalla de sala y voz

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-03. Estado: siete pasos técnicos completos; revisión visual pendiente por host y aceptación funcional pendiente.
Autorización de implementación: `/spec-impl 06` e inicio de los pasos 1 a 7 confirmados el 2026-11-03. Se conserva `fdaza`, con cambios previos preservados y un único commit al terminar; revisión entre pasos.

## Inspección de la base

Revisados `CLAUDE.md`, el informe (HU-04, HU-05, HU-08, HU-09, RNF-02/04/05, NS03, NS07 y el §7.1), el índice de specs, las plantillas y los cuatro documentos del 05 y del 04. Del código real:

- `turnosapp/cola.py` crea el evento `llamado` dentro de la transacción de selección (`EventoTurno.objects.create(... accion="llamado" ...)`). `turnosapp/atencion.py` crea el `rellamado` con `_evento(turno, "rellamado", ...)` dentro de `_operar`, que está decorada con `@transaction.atomic`.
- `EventoTurno` tiene UUID, secuencia por turno, acción, instante, actor, ventanilla y operación. No tiene un orden global ni está pensado para publicarse: apunta al turno y, por él, al paciente.
- Según el 05, toda operación del personal y toda selección reservan el mismo estado diario (`EstadoColaDiaria.version`, con UPDATE condicional). Esto serializa los llamados y re-llamados del día; el plan se apoya en ello y lo comprueba con pruebas, sin darlo por supuesto.
- El panel privado consulta `turnosapp:estado` cada segundo (`static/js/cola.js`); no usa WebSocket.
- `cesfam/asgi.py` es la plantilla estándar de Django (solo HTTP). No hay Channels, Daphne ni WebSocket. `INSTALLED_APPS` no los incluye y `requirements.txt` tampoco.
- La base del proyecto es PostgreSQL (`cesfam/settings.py`); las herramientas `tools/verificar_spec_0X_http.py` reemplazan `DATABASES` por una SQLite temporal antes de `django.setup()`.
- El tótem usa `components/Layout/base_publica.html` (panel de identidad a la izquierda), pensado para pantallas con formularios. La sala necesita una pantalla completa sin navegación.
- `static/css/` y `static/js/` ya tienen `cola.*` y `totem.js` para sus módulos; las URL de `.css` y `.js` se versionan con `coreapp/storage.py`, así que una hoja nueva no queda en caché vieja.
- Al definir el plan, `channels` y `daphne` no estaban instalados. En T-06-03 se instalaron y fijaron `channels==4.3.2` y `daphne==4.2.3`, compatibles con el Django 5.2.18 y Python 3.13 del entorno; `pip check` y la suite pasan.
- Cambios locales ajenos a preservar: el árbol tiene cambios sin commitear de otras tareas (recetas, base de datos, menú). No incluirlos ni revertirlos.

## Diseño propuesto

Se extiende `turnosapp`; no se crea otra app. Se agrega la capa ASGI en `cesfam` porque es configuración del proyecto, no de un módulo.

```text
Técnico / procesar_cola (cualquier proceso)
  └─ llamado o re-llamado + AnuncioSala   ── misma transacción ──┐
                                                                  ▼ commit
Proceso web (Daphne)                                         base de datos
  ├─ vigilante (1 por proceso, solo con pantallas conectadas)
  │     lee anuncios nuevos y el estado público cada 0,5 s
  └─ SalaConsumer ── WebSocket /ws/sala/ ──► pantalla de sala (navegador)
                                               ├─ fila de avisos → tono + voz (dos veces)
                                               └─ si no hay WebSocket: GET /turnos/sala/estado/ cada 1 s
```

Decisiones de diseño, con su motivo:

1. **Un solo camino de entrega.** Todo anuncio llega a la pantalla por la lectura de la base del vigilante; no hay publicación directa desde el servicio que llama. Así un llamado hecho por `procesar_cola` (otro proceso) llega igual que uno hecho desde el panel, y no hay dos rutas que puedan duplicar o perder un aviso. La capa de canales es `InMemoryChannelLayer`, que solo comunica los consumidores del mismo proceso; es suficiente porque cada proceso web tiene su propio vigilante.
2. **Tabla pública separada.** `AnuncioSala` guarda solo lo que se puede mostrar. El vigilante y el consumidor nunca leen `Turno` más allá de lo necesario para el estado (números y estados), ni ven pacientes.
3. **Estado calculado, no guardado.** Las tarjetas de ventanilla, los números en espera y los recientes se calculan en cada lectura. Solo los anuncios se persisten, porque son eventos y necesitan orden e identidad.
4. **La pantalla es el único lugar que decide qué se dice en voz alta.** El servidor envía anuncios con identidad; el navegador decide, según su fila y la vigencia, qué pronunciar. Así la voz no depende del servidor ni de que haya una pantalla conectada en el momento del llamado.
5. **Respaldo HTTP.** El estado se expone también por `GET /turnos/sala/estado/`, que sirve para el primer pintado, para la pantalla cuando el WebSocket no se logra y para la herramienta de medición.

### Carrera de orden en la lectura incremental

Un cursor `id > último` puede saltarse un anuncio: si la transacción A toma el `id` 10, la B toma el 11 y B confirma primero, el vigilante lee hasta el 11 y el 10 llega después. El plan lo cubre de dos formas:

- **Prevención.** El 05 ya serializa llamados y re-llamados con el estado diario, de modo que el anuncio se inserta después de reservar esa fila y dos anuncios del día no se solapan. Una prueba concurrente lo verifica.
- **Defensa.** El vigilante no confía solo en el cursor: en cada pasada lee los anuncios con `id > cursor` **o** con `instante` de los últimos 30 segundos, y entrega los que no estén en un conjunto acotado de ids ya enviados. Un anuncio que confirma tarde se entrega igual, una sola vez. Una prueba simula la confirmación fuera de orden.

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-06-01 | Existentes `turnosapp/models.py`, `cola.py`, `atencion.py`; nueva migración `turnosapp/0003_*`; nuevo `turnosapp/sala.py` | Modelo `AnuncioSala`; helper `registrar_anuncio(evento, turno, ventanilla)` llamado en la misma transacción del llamado y del re-llamado | `test_sala_anuncios.py`; regresión completa del 05 |
| RF-06-01 | `turnosapp/tests/test_concurrencia_sala.py` | Tres o más escenarios concurrentes con `TransactionTestCase` | Un anuncio por evento, ids estrictos, sin pérdidas |
| RF-06-02 | Nuevos `turnosapp/consumers.py`, `routing.py`; existentes `cesfam/asgi.py`, `settings.py` | `SalaConsumer` de solo lectura, validación de origen, límites de conexiones, latido | `test_sala_canal.py` con `WebsocketCommunicator` |
| RF-06-03 | Nuevo `turnosapp/vigilante.py` | Vigilante por proceso, con cursor y ventana de repaso; arranca y se detiene según haya pantallas | Pruebas del vigilante, incluido el anuncio que confirma fuera de orden |
| RF-06-04 | `turnosapp/sala.py`; `views.py`, `urls.py`; nueva plantilla `templates/turnos/sala.html` | Estado público, vista HTML y endpoint JSON de respaldo | `test_sala_estado.py`; HTTP real |
| RF-06-05, RF-06-06, RF-06-07 | Nuevo `static/js/sala.js` | Fila de avisos, frases canónicas, voz dos veces, tono, activación y prueba del sonido | `sala.test.cjs` (Node) con voz y reloj simulados |
| RF-06-08 | `static/js/sala.js` | Reconexión con esperas crecientes, latido, respaldo HTTP y deduplicación por `id` | `sala.test.cjs`; prueba HTTP real de corte |
| RF-06-09 | `sala.py`, `consumers.py`, vistas | Contenido mínimo y `no-store`; revisión de lo que sale | Pruebas que recorren cada salida buscando datos privados |
| RF-06-10 | `templates/turnos/sala.html`, nuevo `static/css/sala.css`, nuevo layout `base_sala.html` | Tipografía, contraste, región viva, movimiento reducido | Pruebas de contraste y estructura; axe y revisión visual (pendientes de navegador) |
| RF-06-11 | Nuevo `tools/verificar_spec_06_http.py` | Mide confirmación → recepción con proceso web aparte | p95 y cantidad de muestras en `validation.md` |
| RF-06-12 | `templates/components/navbar.html`; `settings.py`, `requirements.txt` | Enlace de menú, dependencias y ASGI | Pruebas de navegación y de rutas existentes |

## Datos y contratos

### Modelo

```text
AnuncioSala
  id                 BigAutoField, creciente (orden y cursor)
  fecha              DateField, fecha local de Chile
  numero             PositiveIntegerField (>= 1)
  ventanilla_numero  PositiveIntegerField (>= 1), copiado al llamar
  accion             CharField: "llamado" | "rellamado" (CheckConstraint)
  instante           DateTimeField (el del EventoTurno)
  evento             OneToOneField(EventoTurno, on_delete=PROTECT)
  índice             (fecha, id)
```

Sin referencia al paciente ni al turno. `evento` hace idempotente el registro: un reproceso del mismo evento choca con la unicidad y el helper lo trata como ya registrado. No se registra el modelo con escritura libre en Admin.

### Mensajes del canal (JSON, del servidor al cliente)

| Mensaje | Contenido |
|---|---|
| `estado` | `ahora` (hora del servidor), `fecha`, `ultimo_id`, `ventanillas` (`numero`, `estado`, `llamado`, `desde`), `recientes` (hasta 20 anuncios de la jornada con `id`, `numero`, `ventanilla`, `accion`, `instante`; la pantalla muestra seis), `espera` (`cantidad`, `numeros` hasta 40, `restantes`). Se envía al conectar y cuando cambia. |
| `anuncio` | `id`, `numero`, `ventanilla`, `accion`, `instante`. Uno por anuncio nuevo. |
| `latido` | `ahora`. Cada 15 s. |

El cliente no envía nada; cualquier mensaje entrante se ignora y no se registra su contenido. `GET /turnos/sala/estado/` devuelve el mismo objeto `estado`.

### Vigilante

Una tarea `asyncio` por proceso, con una cuenta de conexiones: arranca con la primera pantalla y se detiene con la última. Cada 0,5 s ejecuta una lectura breve en un hilo (`database_sync_to_async`): anuncios con `id > cursor` o con `instante` de los últimos 30 s no enviados todavía, y el estado público. Difunde cada anuncio nuevo en orden y el estado solo si cambió (comparado por una firma). Si la lectura falla, registra el error sin datos personales, espera y reintenta, sin cerrar las pantallas; el estado de respaldo sigue disponible. El intervalo es un parámetro de configuración.

Detalle implementado en T-06-03: seis consultas por lectura (las cinco del estado y una de anuncios). Al conectar se toma el historial de la jornada como base para no reemitirlo; luego se retienen solo los ids que la ventana de lectura puede repetir, por conexión. Las altas y lecturas se coordinan con un candado asíncrono; los ids menores que confirman tarde se entregan una vez al detectarlos, aunque el cursor ya sea mayor. Se usa `channel_layer.send` por consumidor porque informa `ChannelFull`; ante saturación se cierra con 1013 para permitir recuperación, en lugar de descartar anuncios silenciosamente con `group_send`. No se publica desde los servicios emisores.

### Conexión y límites

`SalaConsumer` es `AsyncJsonWebsocketConsumer`. La conexión pasa por `AllowedHostsOriginValidator` (usa `ALLOWED_HOSTS`). Antes de aceptar, el consumidor revisa un contador por proceso (20 en total, 5 por dirección) y rechaza con código de cierre si se supera. No hay autenticación: la pantalla es pública. Se acota el tamaño de cualquier mensaje entrante.

### Rutas

| Ruta | Uso |
|---|---|
| `GET /turnos/sala/` | Pantalla de sala, pública. Incluye el estado inicial en la página para pintar sin esperar al canal. |
| `GET /turnos/sala/estado/` | Estado JSON de respaldo. Solo lectura, `no-store`. |
| `WS /ws/sala/` | Canal en vivo, de solo lectura. |

### Cliente (`static/js/sala.js`)

- **Frases:** `llamado` → «Número {n}, ventanilla {v}»; `rellamado` → «Nuevamente, número {n}, ventanilla {v}». La misma función produce el texto de pantalla y el de la voz, para que no puedan diferir.
- **Deduplicación:** T-06-04 mantiene los ids vistos durante la jornada en memoria, sin persistirlos en el navegador; se limpian al cambiar de fecha. Se usa un conjunto y no solo el máximo, para aceptar el id menor que confirma tarde y que ya defiende el vigilante. El último id por ventanilla impide que ese anuncio haga retroceder una tarjeta o reabra una atención finalizada. La primera carga marca el historial existente; T-06-05 incorpora la voz solo para anuncios nuevos/perdidos vigentes, sin repetir el historial ni lo recibido por otro transporte.
- **Fila de avisos:** máximo cinco; cada uno suena completo (tono, voz, pausa de 1,5 s, voz) antes del siguiente. Si se acumulan más, descarta los más antiguos de la fila.
- **Voz:** `speechSynthesis`, con preferencia por `es-CL` y luego cualquier `es-*`; velocidad algo menor que la normal. Si no hay voz en español, lo informa en texto y mantiene tono y aviso visual. Las voces se cargan de forma asíncrona (`voiceschanged`).
- **Tono:** generado con Web Audio (dos notas breves), sin archivos de audio.
- **Activación:** el botón «Activar sonido» crea el contexto de audio y emite una locución de prueba dentro del gesto, que es lo que los navegadores exigen. El estado se muestra siempre en texto.
- **Reconexión:** esperas de 1 s que crecen hasta 10 s; tras tres fallos, consulta `GET /turnos/sala/estado/` cada 1 s y sigue intentando el canal. Si pasan 30 s sin ningún mensaje ni latido, la pantalla considera caída la conexión.
- **Reloj:** muestra la hora del servidor (`ahora` de cada mensaje) en `America/Santiago`, avanzando con un temporizador local entre mensajes.

Implementado en T-06-04: reconexión lineal de 1, 2, …, 10 s; tras tres fallos, consulta HTTP inmediata y luego cada segundo. Las consultas no se superponen y se abortan tras 5 s si no responden; llevan `no-store` y omiten credenciales. Un estado válido del WebSocket cancela el respaldo y descarta respuestas HTTP pendientes mediante una versión de transporte. Los latidos corrigen la hora del servidor y el reloj avanza con `performance.now()`, sin depender de la hora configurada en el navegador. Al cambiar la jornada se limpia el contenido anterior incluso sin conexión; al salir se liberan recursos y al volver desde la caché de navegación se reconecta. Sin WebSocket disponible se usa directamente el respaldo.

Implementado en T-06-05: controlador local de sonido en `sala.js`. Los botones se habilitan al cargar JavaScript; no hay reproducción antes del gesto. Activar solicita la locución de prueba dentro del clic y reanuda Web Audio; Probar no interrumpe un aviso en curso. Los llamados usan dos notas (880/1174 Hz), frase común con el texto visual, dos locuciones con velocidad 0,9 y pausa de 1,5 s. El aviso activo se marca en texto y en su tarjeta; el límite de cinco corresponde a los pendientes, sin cortar el que ya comenzó. Un lote se acota antes de comenzar, descartando los más antiguos. Se comprueba la vigencia al recibir y al desencolar; el aviso ya iniciado se completa, salvo error del motor, cambio de jornada o salida de la página. La primera carga nunca encola su historial; los estados posteriores recuperan ids no vistos en orden ascendente. Ausencia de voz española, rechazo de reproducción y fallos de audio quedan visibles. Una locución sin respuesta se cancela tras 15 s para no bloquear la fila. Al cambiar de jornada se cancela la voz/fila; al salir también se cierra AudioContext y se requiere activar de nuevo tras volver.

## Permisos e interfaz

| Superficie | Acceso |
|---|---|
| Pantalla, estado de respaldo y canal | Público, solo lectura |
| Enlace «Pantalla de sala» del menú | Técnico, Q.F. y superusuario; `target="_blank"` con `rel="noopener"` |
| Panel privado del 05 | Sin cambios |

Layout: plantilla nueva `components/Layout/base_sala.html`, que extiende `base.html` y sustituye el cuerpo por una pantalla completa sin navegación ni pie. La franja superior (aviso de demostración y tamaño de texto) se conserva por defecto; si estorba en el equipo de la sala, se agrega un bloque en `base.html` para ocultarla. Estilos propios en `static/css/sala.css` con las variables de `base.css`, sin colores nuevos fuera del sistema.

Boceto (pantalla horizontal):

```text
┌───────────────────────────────────────────────────────────────┐
│ Farmacia · CESFAM San Nicolás            martes 3 nov · 14:32 │
├───────────────────────────────┬───────────────────────────────┤
│  Se llama al                  │  Ventanilla 1    18           │
│  Número 23                    │  Ventanilla 2    23   ◀ suena │
│  Ventanilla 2                 │  Ventanilla 3    Disponible   │
│  (la frase que dice la voz)   │  Ventanilla 4    Sin atención │
├───────────────────────────────┴───────────────────────────────┤
│  Llamados recientes   23 · V2 · 14:32     22 · V1 · 14:31 ... │
│  En espera: 7 personas    24  25  26  28  29  30  31          │
├───────────────────────────────────────────────────────────────┤
│  Sonido activado · Probar sonido                 Conectada    │
└───────────────────────────────────────────────────────────────┘
```

Principios: el número y la ventanilla son lo más grande de la pantalla; la tarjeta de la ventanilla que suena se marca con borde y texto, no solo con color; el único movimiento es el destaque del llamado, lento y sin parpadeo, y se apaga con «reducir movimiento»; el estado de conexión y de sonido siempre dicen su estado con palabras. Sin números de espera la zona muestra «Nadie en espera». Responsiva hasta tabletas; no se diseña para teléfonos.

T-06-06 implementada: composición en dos columnas, número destacado, tarjetas por ventanilla y filas de recientes/espera debajo. Bitter identifica la farmacia y Atkinson presenta números/textos. `sala.css` usa únicamente los tokens existentes: tinta `#2a1613`, blanco `#ffffff`, suave `#fdf1e0`, trigo `#fef2a0`, activo `#8f3434` y acción `#e98b50`, definidos en `base.css`; no agrega colores propios. Se optó por destaque estático con borde y texto, sin animaciones ni destellos. Tamaños en rem, grilla adaptable, foco visible y regla explícita para movimiento reducido. Se conserva la franja de demostración/tamaño de texto. El llamado mantiene una región viva; el aviso hablado se muestra aparte sin duplicar otra región viva, y los estados idénticos de sonido no se reescriben. El menú valida el rol mediante el contexto del servidor y abre la sala en otra pestaña con `noopener` y aviso accesible. Contraste y estructura probados; navegador/axe pendientes por bloqueo del host descrito en `validation.md`.

## Migraciones y reversión

Una migración `turnosapp/0003_*` que crea `AnuncioSala` con sus restricciones e índice. No toca datos existentes ni migra turnos. Los llamados anteriores a la migración no tienen anuncio y no aparecen en «llamados recientes»; el estado de las ventanillas sí los refleja porque se calcula desde los turnos. El retroceso elimina la tabla y sus anuncios, que son derivados de eventos del 05 y no historia clínica; aun así, se recomienda respaldo antes de retroceder. No se ejecuta en esta fase y, en la implementación, solo en una base temporal y luego en la del proyecto con aprobación.

## Plan de pruebas

Ejecutor de Django, datos sintéticos y, para el canal, `TransactionTestCase` con `channels.testing`. Los hilos del vigilante no ven una transacción abierta de otro hilo, por eso no se usa `TestCase`.

**Anuncios y concurrencia (RF-06-01).** Nuevos `test_sala_anuncios.py` y `test_concurrencia_sala.py`. Casos: llamado automático y re-llamado crean su anuncio con el número y la ventanilla correctos; repetir el POST o reprocesar el pendiente no duplica; un fallo forzado del registro revierte el llamado y deja el pendiente; ventanilla y número se copian y un cambio posterior de la ventanilla no altera el anuncio. Escenarios concurrentes (hilos, barrera y conexiones separadas, con número de hilos e iteraciones registrado): cuatro ventanillas llaman a la vez; el mismo re-llamado se envía dos veces a la vez; un llamado se confirma mientras el vigilante lee; `procesar_cola` y una acción manual coinciden. Invariantes: un anuncio por evento, `id` distintos y crecientes, ninguno perdido.

**Canal y vigilante (RF-06-02, RF-06-03).** `test_sala_canal.py`: la conexión recibe `estado` completo; un anuncio nuevo llega una sola vez y en orden; un mensaje del cliente se ignora; origen no permitido y exceso de conexiones se rechazan; se desconecta y el vigilante se detiene al irse la última pantalla; un error de lectura no cierra las pantallas; un anuncio que confirma fuera de orden (id menor, después) se entrega igual y una sola vez.

**Estado y privacidad (RF-06-04, RF-06-09).** `test_sala_estado.py`: tarjetas con número, «Disponible» y «Sin atención» según habilitación y automatismo; ventanilla retirada oculta; recientes y espera correctos (límite de 40 y «y N más»); solo la jornada local. Una prueba recorre el HTML, el JSON y los mensajes del canal buscando RUT, nombres, categorías, UUID de turno o de paciente y recetas de un paciente sintético, y falla si aparece alguno. Cabeceras `no-store` y ausencia de cookies para quien solo mira.

**Cliente (RF-06-05 a RF-06-08).** `turnosapp/tests/sala.test.cjs` con Node, voz, audio y reloj simulados, igual que `impresion.test.cjs`: frase de pantalla y de voz idénticas; dos repeticiones con pausa; fila sin superposición; descarte sobre cinco; no pronuncia el historial al abrir ni anuncios de más de 60 s; sí dice los perdidos recientes al reconectar; deduplicación por `id`; esperas de reconexión; paso al respaldo tras tres fallos; aviso sin voz en español; estado del sonido.

**Servidor y regresión (RF-06-12).** Prueba de navegación por rol; rutas del tótem y del panel responden igual; `manage.py check`, `makemigrations --check --dry-run` y la suite completa. Se corre primero la suite del 05 (sus pruebas concurrentes son el contrato que se toca).

**Medición (RF-06-11).** `tools/verificar_spec_06_http.py`, siguiendo las herramientas anteriores: SQLite temporal, 670 pacientes sintéticos y un **proceso aparte** con el servidor ASGI. El emisor confirma llamados llamando a los servicios del 05 y mide el tiempo hasta recibir el anuncio en dos clientes WebSocket, con 100 llamados, cuatro ventanillas y sondeo de cuatro paneles privados. Se usó `websockets==16.1.1` solo en la herramienta: Autobahn asyncio no puede importarse tras activar Twisted durante la inicialización de Daphne. Se informa p50, p95, máximo, número de muestras y carga. Un coordinador sin Django conserva el temporal y espera a que terminen emisor/servidor antes de eliminar SQLite, para liberar todos los handles en Windows. Se usa `perf_counter` común en emisor/receptor y un callback `on_commit` en el registro del anuncio; mide recepción de red local, no dibujado ni voz. Resultado final: p95 444,12 ms, máximo 536,66 ms para recepción en ambas pantallas. Detalles en validación.

**Navegador (pendiente de host).** Revisión de la pantalla en Chrome o Edge con un televisor o un monitor grande: voz en español, activación del sonido, reconexión, texto grande, teclado, zoom y axe A/AA. En el modo quiosco, comprobar si el parámetro de reproducción automática basta para la voz; si no, se conserva la activación manual. Prueba con al menos cinco personas representativas y aceptación funcional son comprobaciones aparte.

Comandos previstos: `manage.py check`, `makemigrations --check --dry-run`, `test turnosapp --noinput` y la suite completa, `node --test` de los archivos nuevos y de los existentes, la herramienta HTTP y `git diff --check`.

## Riesgos, alternativas y dependencias

- **El registro del anuncio puede bloquear llamados.** Al estar en la misma transacción, un defecto lo haría fallar todo. Se mitiga con pruebas de regresión del 05 y con el pendiente recuperable. Alternativa descartada: registrarlo después del commit, que permitiría un llamado sin aviso.
- **Orden de confirmación.** Descrito arriba; prevención por la serialización del 05 y defensa por el repaso de 30 s, ambas con pruebas.
- **Voz del navegador.** Depende del equipo y puede no existir una voz en español, o requerir un gesto aun en modo quiosco. Se avisa en texto y se conserva el aviso visual; se comprueba en el hardware real, que es una dependencia institucional.
- **Carga de lectura.** Cuatro o cinco consultas cada 0,5 s por proceso web, solo con pantallas conectadas. Se mide con la herramienta; si pesara, el intervalo pasa a 1 s y el respaldo HTTP absorbe la diferencia sin salirse de los 2 s.
- **Capa de canales en memoria.** Solo comunica el proceso propio; no sirve para publicar entre procesos y por eso no se usa para eso. Si más adelante se quiere empujar sin esperar a la lectura, el siguiente paso es Redis, fuera de este spec.
- **Daphne y Windows.** Se espera que funcione con `runserver` al agregar `daphne` primero en `INSTALLED_APPS`; debe comprobarse con el flujo real del equipo, incluido el servicio de estáticos y el autorecargado.
- **Proxys y WebSocket.** Un proxy que no deje pasar WebSocket cae al respaldo HTTP, con 1 s de espera.
- **Reloj del equipo.** La hora mostrada y la vigencia de 60 s usan la hora del servidor, no la del navegador.
- **Paquetes nuevos:** `channels` y `daphne`, justificados por RF-06-02 y el informe. Fijar versiones compatibles con Django 5.2 al implementar. Solo con `daphne` se obtiene un servidor ASGI de desarrollo; el despliegue real lo define el DESAMU con su unidad de TIC.
- **Observaciones previas que afectan el cambio:** los pendientes visuales y de aceptación del 04 y del 05 siguen abiertos y no se dan por cerrados aquí.

## Documentos afectados

En esta fase: los cuatro documentos del 06 y el índice `specs/README.md`. En la implementación: `README.md` (arranque con Daphne, ruta de la pantalla, `procesar_cola` y requisitos del equipo de la sala), `docs/estructura.md`, `requirements.txt`, `.env.example` solo si se agrega algún parámetro, y la memoria del proyecto (`CLAUDE.md`), que hoy anota el 06 como pendiente. Las evidencias del 04 y del 05 no se reescriben.

## Plan de implementación

1. **Esquema y registro público.** Modelo, migración, helper y enganche en el llamado y el re-llamado, con pruebas y las concurrentes. Primer paso ejecutable; deja el sistema funcionando sin pantalla.
2. **Estado público y pantalla base.** `sala.py`, endpoint JSON, vista y plantilla con el estado inicial, sin WebSocket todavía; funciona con el respaldo.
3. **Capa ASGI y canal.** Dependencias, `settings`, `asgi.py`, consumidor, vigilante y límites, con pruebas del canal.
4. **Cliente de sala.** Conexión, reconexión, respaldo, deduplicación, reloj y pintado; pruebas de JavaScript.
5. **Voz y sonido.** Fila de avisos, frases, tono, activación y estados; pruebas de JavaScript.
6. **Presentación y accesibilidad.** Estilos, layout de sala, región viva, movimiento reducido, enlace de menú y pruebas de estructura y contraste.
7. **Integración y medición.** Herramienta de latencia, regresión completa, documentación y validación con límites honestos. Último paso.

## Decisiones para implementar

Ninguna es crítica para empezar. Para confirmar al revisar: los valores de los parámetros iniciales del spec; si la franja superior se conserva en la sala; y la versión exacta de `channels` y `daphne`. Aun sin dudas, esta fase termina antes del código.
