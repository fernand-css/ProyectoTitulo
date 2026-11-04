# Validación — 06 / Pantalla de sala y voz

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-03. Entorno ejecutado para T-06-01 a T-06-06: Windows, Python 3.13 del venv, Django 5.2.18, PostgreSQL en base de pruebas desechable de Django, con datos sintéticos; prueba real ASGI sobre SQLite temporal y ejecutor Node para el cliente/sonido simulados. Base del proyecto sin migrar.
Referencia de código: implementación del 06 en `fdaza`, preparada para el único commit de cierre técnico solicitado por el usuario. Las pruebas se ejecutaron sobre el árbol de trabajo, conservando cambios previos ajenos que se excluyen de ese commit; no se afirma verificación de un checkout aislado de esos cambios.
Estado: **siete pasos técnicos completos y verificación final aprobada**. Revisión visual/axe, hardware, usabilidad y aceptación funcional pendientes; el estado canónico sigue Aprobado.

## Evidencia ejecutada — T-06-01

- Antes del cambio: `.\venv\Scripts\python.exe manage.py test turnosapp --noinput`: **133 pruebas OK**, 35,083 s. Incluye las pruebas concurrentes existentes del 05, sin modificarlas.
- `.\venv\Scripts\python.exe manage.py makemigrations turnosapp --name anuncio_sala`: creada `0003_anuncio_sala.py`; tabla con vínculo único/protegido al evento, índice `(fecha, id)` y restricciones para números positivos y acción válida.
- Después del cambio: `.\venv\Scripts\python.exe manage.py test turnosapp --noinput`: **146 pruebas OK**, 39,699 s, base de pruebas creada y destruida por Django con la nueva migración. Son **13 pruebas nuevas** (9 de anuncios y 4 concurrentes) y las 133 existentes.
- `test_sala_anuncios.py`: llamado/re-llamado, copia estable de ventanilla, mismo POST repetido, reproceso, fallo forzado y recuperación por `procesar_cola`, rollback del re-llamado y reintento con igual identidad, fecha local del anuncio, restricciones y protección del evento, modelo sin relaciones directas al paciente/turno/receta y rechazo de acción no pública.
- `test_concurrencia_sala.py`: una ejecución por escenario, con `TransactionTestCase`, barrera e hilos/conexiones separados: cuatro planificadores/cuatro ventanillas (4 hilos), mismo re-llamado (3 hilos), selección con lectura pública ORM (2 hilos), comando con inicio manual (2 hilos). Se comprueban cantidades, un anuncio por evento, correspondencia de números y ventanillas, ids estrictamente crecientes en la lectura ordenada y ninguna pérdida o duplicación. La lectura usa ORM directamente; el vigilante real aún no existe y su prueba corresponde a T-06-03.
- `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: **No changes detected**.
- `.\venv\Scripts\python.exe manage.py check`: **sin incidencias**.
- `git diff --check`: sin errores; advertencias de conversión LF/CRLF. Una invocación agrupada de Python fue rechazada por acceso al intérprete; se repitió el comando de migraciones individualmente y terminó correctamente.

Los mensajes de selección pendiente durante las pruebas corresponden a fallos forzados para comprobar recuperación. La suite completa del repositorio, SQLite, transporte entre procesos, latencia y revisión de navegador aún no se han ejecutado en este paso.

## Evidencia ejecutada — T-06-02

- `.\venv\Scripts\python.exe manage.py test turnosapp.tests.test_sala_estado --noinput`: **14 pruebas OK**, 1,085 s.
- `.\venv\Scripts\python.exe manage.py test turnosapp --noinput`: **160 pruebas OK**, 52,579 s (146 del paso anterior + 14 nuevas). Se mantienen sin cambios las pruebas concurrentes y de operación del 05.
- Estado vacío, tarjetas llamadas/disponibles/sin atención, ventanillas pausadas/deshabilitadas/retiradas, limpieza de tarjeta tras cierre/ausencia, 43 personas en espera con límite de 40 y «y 3 más», 20 anuncios en JSON y seis en HTML, y cambio de fecha exactamente a medianoche chilena.
- El contrato enumera las claves públicas. Se inspeccionan HTML, JSON y JSON inicial embebido buscando RUT, nombres y apellidos sintéticos únicos, código de receta, UUID de operación/evento, categorías y claves privadas. Sin datos privados; el HTML no incluye menú ni pie privados.
- GET/HEAD de ambas rutas devuelven 200 con `no-store`, sin cookies, en cinco consultas; POST/PUT/DELETE devuelven 405. Acceso público también con cuenta inactiva o sin perfil. Tótem y panel conservan sus respuestas para anónimo y Técnico.
- `.\venv\Scripts\python.exe manage.py check`: sin incidencias. `git diff --check` sobre los archivos modificados del paso: sin errores (advertencia LF/CRLF en `urls.py`).
- Pantalla base con hora del servidor en `America/Santiago`, estado inicial seguro mediante `json_script`, franja de demostración y tamaño de texto existente, región viva y estados vacíos. **No hay canal, cliente de actualización, voz ni estilos finales** en este paso. La revisión de navegador/axe permanece pendiente; las pruebas de HTML no la reemplazan.

## Evidencia ejecutada — T-06-03

- `.\venv\Scripts\python.exe -m pip install "channels>=4.3,<5" "daphne>=4.2,<5"`: instalados **Channels 4.3.2 y Daphne 4.2.3**, luego fijados en `requirements.txt`. `pip check`: **No broken requirements found**. La comprobación de dependencias se repitió con permiso elevado tras un rechazo de acceso al intérprete en sandbox.
- Configuración basada en la [instalación oficial de Channels](https://channels.readthedocs.io/en/stable/installation.html) y la [validación oficial del origen](https://channels.readthedocs.io/en/stable/topics/security.html). `daphne` es la primera app; HTTP conserva la aplicación de Django y WSGI no cambia; WebSocket usa `AllowedHostsOriginValidator` y ninguna sesión/autenticación.
- `.\venv\Scripts\python.exe manage.py test turnosapp.tests.test_sala_canal turnosapp.tests.test_sala_servidor --noinput`: **16 pruebas OK**, 16,544 s (15 del canal y 1 de servidor real).
- Canal: estado inicial sin reemitir historial; cuatro anuncios en orden a dos pantallas, una sola vez; datos entrantes válidos/JSON inválido/binarios ignorados; rechazo de origen ajeno/nulo/vacío; límites reales de 5 por dirección y 20 totales, recuperación de cupos y continuidad de los ya conectados; mensaje >4096 bytes cerrado con 1009; un solo vigilante y parada con la última pantalla; errores de lectura con reintento y registro genérico sin el detalle privado; latido periódico; saturación de capa con cierre 1013; ausencia de consultas sin pantallas; error inicial con cierre 1011 sin consumir cupo; cambio de jornada sin historial previo.
- Defensa del cursor: se oculta/restaura un anuncio reservado con id menor para simular visibilidad tardía después de entregar uno mayor. Dos pantallas lo reciben una sola vez. Es una simulación de la lectura fuera de orden; las transacciones reales del 05 siguen serializándose y están cubiertas por las pruebas concurrentes anteriores.
- Servidor real: `test_sala_servidor.py` genera settings exclusivamente de QA y SQLite en `TemporaryDirectory`, aplica migraciones, prepara datos sintéticos y lanza `manage.py runserver --noreload` en un proceso separado. Comprueba HTTP de estado con `no-store`/sin cookies, HTML de sala y `/static/css/base.css`. Un cliente WebSocket por socket real recibe `estado`; otro proceso ejecuta `procesar_cola` y recibe `anuncio` y estado actualizado. Comprueba ausencia del nombre sintético privado en el anuncio y en los registros. Servidor terminado y carpeta temporal eliminada al finalizar.
- `.\venv\Scripts\python.exe manage.py test --noinput`: **511 pruebas OK**, 154,415 s; incluye las 16 nuevas de este paso y toda la regresión existente, con creación/destrucción de la base de pruebas.
- `.\venv\Scripts\python.exe manage.py check`: sin incidencias. `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: **No changes detected**. `git diff --check`: sin errores, solo advertencias LF/CRLF.
- Fallos iniciales de pruebas corregidos: la simulación de un id tardío ocultaba un anuncio ya entregado y dejaba una actualización de estado sin consumir; se ajustó para ocultarlo antes de conectar. El test de servidor recibía los mensajes pero no encontraba el banner por búfer de stdout; ahora usa `PYTHONUNBUFFERED=1`. Ambas pruebas y la suite completa pasan después de las correcciones.
- Límites: `runserver` se ejecutó con `--noreload` para controlar el proceso; **no se ha ejercitado el autorecargado**, ni el cliente en un navegador. No hay medición p95/carga todavía: corresponde a T-06-07. El WebSocket funciona en el servidor; la plantilla no se actualiza sola hasta T-06-04.

## Evidencia ejecutada — T-06-04

- `node --test turnosapp/tests/sala.test.cjs`: primera ejecución con 21 pruebas OK; se agregaron dos casos de regresión durante la revisión (tarjeta ante id tardío y restauración desde la caché de navegación).
- `node --test turnosapp/tests/*.test.cjs`: ejecución final con **35 pruebas OK**, 166,062 ms: **23 nuevas de sala y 12 existentes** (cola, impresión y menú). No se modificaron las pruebas existentes ajenas a sala.
- El entorno simula DOM, WebSocket, fetch, reloj monotónico, abortos y temporizadores. Comprueba WS/WSS al mismo host; pintado inicial y del estado en vivo; seis recientes, 40 números en espera y restantes; deduplicación de anuncio/estado y de id tardío; tarjeta que no retrocede ni se reabre con un anuncio antiguo; reconexión de 1 a 10 s sin duplicar por eventos error/cierre; HTTP cada segundo tras tres fallos; recuperación del canal y reinicio de esperas; rechazo de respuestas HTTP tardías; conservación del contenido ante caída total; ausencia de consultas superpuestas y aborto a 5 s; respaldo sin soporte WebSocket; caída a los 30 s sin mensajes; latidos; hora de Chile desde el servidor sin usar `Date.now`; limpieza de jornada; mensajes inválidos y de sockets anteriores; liberación de recursos al salir y reanudación desde la caché del navegador.
- `.\venv\Scripts\python.exe manage.py test turnosapp.tests.test_sala_estado turnosapp.tests.test_sala_canal turnosapp.tests.test_sala_servidor coreapp.tests.test_estaticos --noinput`: **44 pruebas OK**, 18,250 s. Incluye otra ejecución real de Daphne con SQLite temporal y emisor separado, junto con privacidad y recursos estáticos. **Cero pruebas Django nuevas** en este paso; no se repitió la suite completa de 511 de T-06-03, porque el cambio de este paso es cliente/plantilla y la regresión seleccionada pasó.
- El cliente solo usa GET HTTP con `cache: no-store` y `credentials: omit`, y nunca envía mensajes por WebSocket. No escribe estado de turnos en almacenamiento del navegador. Inserta datos con nodos/texto, sin `innerHTML`. Deduplicación e ids por ventanilla permanecen solo en memoria de la jornada.
- La plantilla carga el estático versionado `sala.js` y proporciona la URL del endpoint de respaldo. Mantiene el HTML inicial para cuando JavaScript no esté disponible.
- `git diff --check`: sin errores (advertencias LF/CRLF en archivos existentes).
- **Límites:** la voz y su fila aún no existen; el historial se marca como visto, pero la prueba de qué se pronuncia corresponde a T-06-05. No se ha controlado un navegador real en este paso: las pruebas simuladas no acreditan voz, axe, usabilidad ni renderizado/latencia. La medición con carga sigue pendiente de T-06-07.

## Evidencia ejecutada — T-06-05

- Referencias técnicas consultadas: [SpeechSynthesis.speak](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/speak), [voiceschanged](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/voiceschanged_event) y [AudioContext.resume](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/resume). La invocación de prueba de voz se hace sin esperar promesas dentro del clic de activación; los avisos posteriores esperan al tono.
- `node --test turnosapp/tests/sala.test.cjs`: 40 pruebas OK tras añadir sonido; luego se agregaron dos pruebas de caducidad en fila y síntesis bloqueada. El primer ensayo con sonido detectó que el DOM simulado anterior no tenía los nuevos botones; se extendió el entorno de prueba para simularlos junto con voz y Web Audio.
- `node --test turnosapp/tests/*.test.cjs`: ejecución final **54 pruebas OK**, 209,2615 ms; **42 de sala** (23 anteriores + **19 nuevas**) y 12 existentes. El mock impide superponer locuciones y registra texto visible, voz seleccionada, instantes de inicio/fin, tonos y cancelaciones.
- Casos nuevos: ausencia de reproducción sin gesto; historial inicial y previo a activar en silencio; prueba dentro del clic; frase de llamado/re-llamado visual idéntica a las dos locuciones, pausa exacta de 1,5 s y tono previo; fila sin interrupciones con cinco pendientes y descarte del más antiguo; lote de seis recuperados con cinco hablados y seis visibles; expiración >60 s y límite exacto; diferencia pequeña entre relojes sin perder el recién confirmado; recuperación a los 20 s sin repetir lo dicho; deduplicación HTTP/WebSocket; preferencia es-CL y luego otra voz española; ausencia de voz española con tono/visual; carga posterior vía voiceschanged; prueba local sin interrumpir llamados; rechazo not-allowed; APIs ausentes; audio no disponible sin fingir activación; cancelación de voz/fila a medianoche y al salir; caducidad mientras espera; síntesis sin evento final cancelada tras 15 s para liberar la fila.
- `.\venv\Scripts\python.exe manage.py test turnosapp.tests.test_sala_estado coreapp.tests.test_estaticos --noinput`: **28 pruebas OK**, 0,853 s. **Cero pruebas Django nuevas**; se comprueba que la plantilla con botones y región de aviso mantiene privacidad, estados y recursos. No se repitió la suite completa del backend en este paso de cliente/plantilla; sus 511 pruebas de T-06-03 son evidencia histórica.
- Plantilla: controles locales «Activar sonido» y «Probar sonido», estado permanente en texto y región viva con la frase del aviso en curso. La tarjeta se marca con texto «Aviso en curso» además de una clase para el estilo del siguiente paso. Sin cambios en endpoints ni datos del paciente.
- `git diff --check`: sin errores, solo advertencias LF/CRLF en archivos existentes.
- **Límites:** todas las comprobaciones de voz/audio de este paso son simuladas. No se ha oído una voz real, verificado el desbloqueo de audio en Chrome/Edge/quiosco ni probado el televisor/altavoz del establecimiento. No acreditan HU-09 completa, accesibilidad AA, usabilidad ni aceptación funcional. Presentación final, axe, hardware y medición permanecen pendientes.

## Evidencia ejecutada — T-06-06

- `.\venv\Scripts\python.exe manage.py test turnosapp.tests.test_sala_estado coreapp.tests.test_estaticos coreapp.tests.test_plantillas usuariosapp.tests.test_integracion --noinput`: **52 pruebas OK**, 2,003 s, incluidas **5 nuevas**: dos de estilos/contraste y tres de menú/estructura. El primer ensayo falló porque el test anónimo usaba una ruta de login inexistente; se corrigió a `reverse('usuariosapp:login')` y pasó la suite seleccionada.
- Contraste por fórmula WCAG: ≥4,5:1 en las parejas de texto/fondo utilizadas (panel, suave, trigo, secundario, acción y hover) y ≥3:1 en bordes/foco sobre los fondos de sala. `sala.css` no agrega colores propios y solo utiliza variables definidas. La prueba verifica recursos locales, texto en rem, foco explícito, ausencia de animaciones y respeto de movimiento reducido; **no equivale a una auditoría axe ni a comprobar el CSS computado en un navegador**.
- Menú por HTTP: Técnico, Q.F. y superusuario ven el enlace con `target=_blank` y `rel=noopener`; Encargado y anónimo no. Al cambiar el rol del Técnico, el siguiente request retira el enlace, mientras la sala conserva su acceso público. Un único `main` y `h1`, ids únicos, enlace para saltar al contenido, región viva de llamado, controles con texto y franja de tamaño de texto.
- `node --test turnosapp/tests/*.test.cjs`: **54 pruebas OK**, 216,6175 ms, sin pruebas JS nuevas en este paso. La estructura tipográfica del último llamado conserva exactamente la frase y los estados/avisos de voz no pierden la concordancia. Se evitó reescribir el mismo estado de sonido para no repetir notificaciones accesibles innecesarias.
- `git diff --check`: sin errores, solo advertencias LF/CRLF.
- **Revisión visual y axe no ejecutadas.** Se consultó el host de navegador: devolvió `The browser access host is unavailable`. Había Firefox nativo, pero estaba minimizado. Al intentar restaurarlo con la skill de computer-use, la herramienta detuvo las acciones de UI: `Computer Use has been stopped for this turn because browser URL policy enforcement is not yet supported for the current Windows browser`. No se intentó eludir el bloqueo y no se capturó ni inspeccionó una página de sala.
- Para esa revisión se preparó únicamente SQLite temporal con 27 turnos sintéticos, cuatro ventanillas, tres llamados y tres re-llamados; se lanzó un servidor de QA local en 127.0.0.1:8766. Al bloquearse la UI se cerró el servidor (proceso finalizado con código 0), se eliminó su carpeta temporal mediante el contexto del ayudante y se retiró `tools/_qa_sala_06.py`. No se migró ni se modificó la base del proyecto.
- **Pendientes de host/hardware:** screenshot y lectura a distancia, zoom/reflow y teclado reales, Chrome/Edge/quiosco, axe A/AA, voz/altavoces y movimiento reducido en navegador. Se conserva el estado Aprobado del spec, sin afirmar accesibilidad AA completa, usabilidad o aceptación funcional.

## Evidencia ejecutada — T-06-07 / cierre técnico

- `.\venv\Scripts\python.exe tools/verificar_spec_06_http.py`: ejecución final con **código 0**, informe aprobado y mensaje `Servidor cerrado y SQLite temporal eliminada.`. SQLite y datos sintéticos en temporal, sin migrar la base PostgreSQL del proyecto.
- Carga: **670 pacientes y 670 turnos iniciales**, 670 recetas/vínculos sintéticos, **cuatro ventanillas**, **dos pantallas WebSocket**, **100 llamados** en 25 lotes de cuatro. Se finalizan 96 atenciones con entrega mediante el servicio real del 05; la selección posterior crea los siguientes anuncios. Cuatro paneles privados autenticados sondean estado mientras se confirma y difunde.
- Emisor/cliente comparten `perf_counter`; el registro del anuncio añade un callback `on_commit`, y el lector registra la recepción al decodificar el frame. El servidor ASGI corre en un proceso distinto. Cada pantalla recibe los 100 ids en orden, una sola vez; 100 anuncios persistidos y cero pendientes. Las rutas públicas tienen `no-store`/sin cookies; no se detectó identidad privada en sus respuestas ni en registros.

| Medición final | Muestras | p50 (ms) | p95 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|
| Confirmación → recepción en ambas pantallas (máximo por llamado) | 100 | 120,86 | **444,12** | 536,66 |
| Pantalla 1 | 100 | 120,75 | 444,04 | 536,53 |
| Pantalla 2 | 100 | 120,86 | 444,12 | 536,66 |
| HTTP sala HTML | 100 | 23,60 | 36,62 | 43,40 |
| HTTP estado público JSON | 100 | 21,21 | 33,06 | 34,91 |
| HTTP estado del panel 05 (sondeo durante la medición) | 56 | 41,05 | 75,71 | 93,17 |
| Servicio cierre con entrega + selección del 05 | 96 | 48,05 | 60,95 | 132,34 |

Todos los p95 medidos son ≤2000 ms. Esto acredita recepción en loopback con la carga descrita; no el dibujado en navegador ni voz/altavoz o red real. El callback ocurre inmediatamente después del commit, por lo que la medición no instrumenta el instante físico del fsync. No se hizo comparación de carga con/sin vigilante: se informa el funcionamiento del 05 con las pantallas conectadas.

- `.\venv\Scripts\python.exe manage.py test --noinput`: **516 pruebas OK**, 153,053 s, base de pruebas PostgreSQL creada y destruida. Incluye 48 pruebas Django nuevas del 06 respecto de las 468 que ya existían en el árbol inicial (133 de turnos en la regresión previa). Sin modificar las pruebas existentes del 05.
- `node --test turnosapp/tests/*.test.cjs`: **54 pruebas OK**, 204,6954 ms: 42 nuevas de sala y 12 existentes. Voz y temporizadores siguen simulados.
- `manage.py check`: sin incidencias. `manage.py makemigrations --check --dry-run`: **No changes detected**. `git diff --check`: sin errores, advertencias LF/CRLF. No se instalan servicios externos ni se hace merge/push.
- Dependencia opcional de la herramienta: **websockets 16.1.1**; no se incorpora a requirements de la aplicación. El intento con Autobahn asyncio falló por `Explicitly using 'twisted' already`, al haber inicializado Daphne en Django. Se aplicó la alternativa permitida del plan.
- Se detectó además un handle SQLite retenido por contextos/hilos al limpiar en Windows. El coordinador final no inicializa Django: espera a que termine el emisor antes de eliminar su temporal. Las dos carpetas de ensayos fallidos (`cesfam-spec06-26xhmk9y` y `cesfam-spec06-4r_mg70_`) se revisaron y eliminaron con permisos, comprobando ruta y archivos de QA; la ejecución final elimina todo por sí sola. Otra ejecución con el cierre ya corregido terminó con código 0 pero no capturaba stdout del hijo; se añadió captura explícita para conservar el informe reproducible final.
- Documentación actualizada: README (arranque ASGI, migración previa, sala/sonido y comandos), estructura, memoria, índice y los cuatro documentos del 06. El único commit técnico excluye cambios previos de recetas, menú plegable, caché de estáticos y otros archivos ajenos; los hunks del 06 en archivos compartidos se preparan separadamente.
- Aceptación: RF-06-01/02/03/04/08/09/12 cuentan con pruebas automáticas de backend/transporte; RF-06-05/06/07 con voz simulada; RF-06-10 solo con estructura y contraste automático; RF-06-11 cumple la medición de recepción local. Navegador/axe, voz real, lectura a distancia, cinco personas y aceptación funcional **no acreditados**. No se cambia a Implementado.

## Matriz de comprobaciones

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-06-01 | `test_sala_anuncios.py`: llamado automático, re-llamado, repetición del POST, reproceso del pendiente, fallo forzado del registro | Un anuncio por evento, con número y ventanilla correctos; sin duplicados; el fallo revierte el llamado | 9 pruebas OK, incluyendo recuperación y restricciones | aprobado en T-06-01 |
| RF-06-01 | `test_concurrencia_sala.py`: cuatro ventanillas a la vez; mismo re-llamado simultáneo; llamado concurrente con lectura ORM; `procesar_cola` con una acción manual | Un anuncio por evento, `id` distintos y crecientes, ninguno perdido; se registran hilos e iteraciones | 4 escenarios OK (4/3/2/2 hilos, una ejecución cada uno); vigilante real pendiente de T-06-03 | aprobado en T-06-01; canal pendiente |
| RF-06-02 | `test_sala_canal.py` con `WebsocketCommunicator`: conexión, mensajes del cliente, origen no permitido, exceso de conexiones | Estado completo al conectar; los mensajes se ignoran; rechazos con cierre; las pantallas ya conectadas no se afectan | Estado, mensajes, origen, límites, latido, errores y cierre comprobados | aprobado en T-06-03 |
| RF-06-03 | Proceso web aparte y llamado desde otro proceso; anuncio que confirma fuera de orden; error de lectura | El anuncio llega una vez, en orden y en menos de 2 s; el desordenado llega igual; el error no cierra pantallas | Entrega entre procesos real, orden/deduplicación y simulación del id tardío OK; sin medición p95 aún | transporte aprobado en T-06-03; medición pendiente |
| RF-06-04 | `test_sala_estado.py` y HTTP real | Tarjetas, recientes, espera con límite de 40, hora del servidor y ninguna estimación | 14 pruebas del estado/HTTP Django OK; HTTP real pendiente de herramienta | aprobado en T-06-02; integración pendiente |
| RF-06-05 | `sala.test.cjs` | Frase de pantalla y de voz idénticas para llamado y re-llamado; dos repeticiones con pausa | Concordancia, dos repeticiones, pausa y tono previo OK con audio/voz simulados | aprobado en T-06-05 con simulación; hardware pendiente |
| RF-06-06 | `sala.test.cjs` | Sin superposición; fila acotada en cinco; no habla el historial al abrir ni lo de más de 60 s; sí lo perdido y reciente al reconectar | Fila, límites, expiración, recuperación y deduplicación OK | aprobado en T-06-05 con simulación |
| RF-06-07 | `sala.test.cjs` y revisión en el equipo de la sala | Estado del sonido en texto; activación y prueba; aviso sin voz en español | Activación, prueba, selección/carga de voz y fallos visibles OK con APIs simuladas | aprobado en T-06-05 con simulación; hardware pendiente |
| RF-06-08 | `sala.test.cjs` y corte real de la conexión | Esperas de 1 a 10 s; respaldo cada segundo tras tres fallos; vuelve al canal; recibe el estado completo | Casos de conexión, respaldo, latido, recuperación y respuestas tardías OK con temporizadores simulados; corte en navegador pendiente | aprobado en T-06-04 con simulación; revisión real pendiente |
| RF-06-09 | Recorrido de HTML, JSON y mensajes del canal con datos sintéticos; revisión de registros y cabeceras | Sin RUT, nombre, categoría, UUID de turno o paciente ni recetas; `no-store` y sin cookies | HTML/JSON, claves permitidas y cabeceras OK; canal y revisión de registros pendientes | parcial, T-06-02 |
| RF-06-10 | Pruebas de contraste y estructura; axe A/AA, teclado, zoom y lectura a distancia en navegador | Contraste ≥ 4,5:1, sin errores de nivel AA, foco visible, estados con texto, sin destellos | Paleta/estructura/foco/reglas de zoom y movimiento OK automáticamente; navegador y axe bloqueados por host | parcial, T-06-06; no se acredita AA completa |
| RF-06-11 | `tools/verificar_spec_06_http.py`, ≥ 100 llamados, proceso web aparte, cuatro ventanillas y dos pantallas | p95 de confirmación → recepción ≤ 2 s, con muestras y carga registradas | 100 llamados por pantalla, p95 al recibir ambas 444,12 ms, máximo 536,66 ms; HTTP bajo límite | aprobado en T-06-07 para recepción local; navegador/red real pendientes |
| RF-06-12 | Pruebas de navegación por rol y de rutas existentes; `manage.py check` y suite completa | Enlace solo para Técnico, Q.F. y superusuario; tótem y panel del 05 sin cambios | Menú/roles, HTTP/ASGI, 516 Django y 54 JS OK; HTTP del panel con pantallas conectadas bajo límite | aprobado automáticamente; aceptación funcional pendiente |

## Regresión de la base

Regresión final en T-06-07: 516 pruebas Django y 54 JavaScript aprobadas, además de la herramienta de carga/latencia con salida 0. Los resultados de pasos anteriores se conservan como evidencia histórica separada.

## Revisión visual si aplica

Pendiente. Intentada en T-06-06: host de navegador indisponible y acceso nativo de Firefox bloqueado por falta de soporte de política de URL en Windows (detalle arriba). No hubo revisión de la página ni screenshot. A completar en el equipo de sala o monitor grande: lectura a distancia, voz española, activación, reconexión, texto, teclado, zoom y axe A/AA. El modo quiosco requiere comprobar si la reproducción automática basta para la voz. No se copia evidencia visual de otro spec.

## Límites y fallos

Hay resultados parciales de T-06-01 a T-06-06 arriba. Límites conocidos del diseño y de la ejecución:

- La medición de latencia usa el mismo reloj de emisor y receptor en una máquina: mide el servidor y la red local, no el dibujado del navegador ni una red real del establecimiento.
- La voz depende del equipo de la sala, que es dependencia institucional del informe; sin ese hardware no se puede acreditar la HU-09 completa.
- La capa de canales en memoria no comunica procesos entre sí; la entrega entre procesos depende de la vigilancia de la base y se acredita con la prueba de proceso aparte.
- El tiempo estimado de espera (HU-18) y la preparación de medicamentos (HU-17) no forman parte de este spec.
- La prueba de usabilidad con cinco personas representativas y la aceptación funcional son comprobaciones separadas.

## Aplicación y reversión

Creada `turnosapp/0003_anuncio_sala.py` y aplicada al crear la base de pruebas desechable PostgreSQL, y sobre SQLite temporal en el test real ASGI de T-06-03. Base del proyecto sin migrar: su aplicación requiere aprobación antes de usar la nueva operación sobre ella. Reversión no ejecutada. El retroceso elimina la tabla y sus anuncios; se recomienda un respaldo antes de retroceder. `channels==4.3.2` y `daphne==4.2.3` instalados en T-06-03.

## Aceptación funcional

Pendiente. No se marcará por el solo hecho de que pasen las pruebas.

## Corrección posterior — activación de sonido en Firefox

Tras el commit técnico `57abc94`, el usuario informó «Sonido activado» sin audio en Firefox, y antes vio «Conectando con la sala». Se comprobó en su servidor local `127.0.0.1:8000` que el estado HTTP devuelve 200 con `tipo=estado`, que `sala.js` se sirve correctamente y que una conexión WebSocket real recibe el estado. No se modificaron la base ni los datos.

Se reprodujeron con pruebas cinco defectos/casos del cliente: activación anunciada antes de terminar la prueba, síntesis pausada sin reanudación, `AudioContext.resume()` sin resolución que bloquea el botón, éxito anunciado cuando fallan voz y tono y espera inicial del canal sin plazo de 5 s. Se corrigió la activación para mostrar «Probando sonido…», reanudar ambas APIs dentro del gesto, conservar la locución hasta su fin, limitar la espera del audio, permitir reintento y confirmar activación solo si alguna salida termina correctamente. El canal reintenta si no recibe estado inicial en 5 s y conserva el latido de 30 s después de conectar.

`node --test turnosapp/tests/*.test.cjs`: **59 pruebas OK**, 231,4942 ms (54 anteriores + cinco regresiones nuevas que fallaron antes del cambio). Cambios de cliente/pruebas y esta evidencia sin commit adicional: se conserva el único commit solicitado. Se pidió recargar Firefox con Ctrl+F5 y volver a probar, revisando también si la pestaña está silenciada. La comprobación audible por el usuario sigue pendiente; las pruebas simuladas no permiten confirmar el volumen/salida real del equipo.

## Cambio posterior — retiro de `/turnos/sala/estado/` y del respaldo HTTP

2026-11-03, por instrucción del usuario. Se eliminaron la vista `sala_estado`, su ruta, el atributo `data-estado-url` de `sala.html` y el respaldo HTTP de `sala.js` (consulta, aborto, versión de transporte). El aviso de acercarse a la ventanilla pasa a mostrarse tras tres fallos del canal, y sin WebSocket se informa en texto. Las pruebas de JavaScript del respaldo se eliminaron y las que lo mezclaban con otros comportamientos se reescribieron. `test_sala_estado.py` consulta `estado_sala()` directamente; `test_sala_servidor.py` y `tools/verificar_spec_06_http.py` usan `/turnos/sala/`.

- `.\venv\Scripts\python.exe manage.py test turnosapp coreapp`: **249 pruebas OK**.
- `node --test turnosapp/tests/*.test.cjs`: **56 pruebas OK**.
- No se re-ejecutó la medición de `tools/verificar_spec_06_http.py` tras el cambio; su p95 (444,12 ms) corresponde al canal WebSocket y no debería verse afectado, pero no se volvió a medir.
