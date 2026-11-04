# SPEC 06 — Pantalla de sala y voz

> **Estado:** Implementado
> **Depende de:** [SPEC 01](../01-base-del-proyecto/spec.md), [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 04](../04-emision-de-turnos/spec.md) y [SPEC 05](../05-cola-ponderada-y-llamado/spec.md)
> **Fecha:** 2026-11-03
> **Objetivo:** Mostrar en una pantalla pública de la sala de espera cada llamado y re-llamado del 05, con su número y ventanilla, un aviso visual y una voz que dicen lo mismo, a no más de 2 segundos de que el Técnico lo confirma.

Módulo: `turnosapp` (extensión), más la configuración ASGI de `cesfam`. Fuente: respuestas del usuario del 2026-11-03 (dos bloques de preguntas), HU-04, HU-05, HU-08 y HU-09, RNF-02, RNF-04, RNF-05, NS03 y NS07 del [informe](../../docs/Informe.md) y la arquitectura de tiempo real del §7.1 (WebSocket).
Implementación autorizada por el usuario el 2026-11-03 mediante `/spec-impl 06`; inicio de T-06-01 a T-06-07 confirmado en cada paso («sip» para T-06-06 y T-06-07). Se conserva `fdaza` y el trabajo previo por elección explícita «2». Un único commit después de terminar la implementación; revisión del diff entre pasos según la skill. Los siete pasos técnicos están completos; navegador/axe, hardware, usabilidad y aceptación funcional siguen pendientes. Por ello el estado se conserva Aprobado.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

El 05 llama a los pacientes y deja eventos durables (`EventoTurno`: `llamado` y `rellamado`), pero el llamado solo se ve en el panel privado del Técnico. En la sala de espera nadie ve ni oye a quién se llama, que es justamente lo que el papel resolvía mal: los pacientes, en su mayoría adultos mayores, no saben cuándo ni adónde ir. Las HU-04, HU-05, HU-08 y HU-09 siguen sin cumplirse del lado del paciente.

El resultado es una pantalla pública, de solo lectura, que se abre en el equipo de la sala. Cuando el Técnico confirma un llamado o un re-llamado, la pantalla muestra el número y la ventanilla con un aviso destacado y una voz dice lo mismo, dos veces. La pantalla se reconoce como lograda porque:

- el número y la ventanilla aparecen en menos de 2 segundos, sin recargar;
- lo que se lee y lo que se oye es la misma frase;
- ningún dato de una persona sale de las vistas privadas;
- si se cae la conexión, la pantalla lo dice y se recupera sola.

## Actores y permisos

| Acción | Anónimo (equipo de la sala) | Técnico | Encargado de terreno | Q.F. | Superusuario activo |
|---|---|---|---|---|---|
| Abrir la pantalla `/turnos/sala/`, su canal en vivo | Sí, solo lectura, sin sesión | Sí | Sí | Sí | Sí |
| Ver el enlace «Pantalla de sala» en el menú | No | Sí | No | Sí | Sí |
| Enviar datos o comandos por el canal en vivo | No: el servidor los ignora | No | No | No | No |
| Ver RUT, nombre, categoría o recetas en la pantalla | No | No | No | No | No |
| Activar o probar el sonido de la pantalla | Acción local del navegador que la muestra | Igual | Igual | Igual | Igual |
| Configurar qué muestra la pantalla | No existe configuración en este spec | — | — | — | — |

La pantalla pública no depende de una cuenta, por lo que usuario inactivo o perfil ausente no la afectan. El enlace del menú sí revalida el rol en el servidor: el Encargado de terreno no lo ve y, si abre la URL, sigue pudiendo ver la pantalla pública, porque su contenido es el mismo que ve cualquiera en la sala. No se concede ningún permiso nuevo sobre el panel privado del 05.

## Alcance y exclusiones

Incluye:

- registro público de cada llamado y re-llamado, hecho en la misma transacción del 05;
- canal WebSocket de solo lectura con vigilancia de la base, que sirve también a los llamados hechos por otro proceso (`procesar_cola`);
- la pantalla de sala con una tarjeta por ventanilla, el último llamado destacado, los llamados recientes, la hora y fecha, y la cantidad y los números en espera;
- aviso visual y voz concordantes, con fila de avisos, activación y prueba del sonido, y un respaldo cuando no hay voz en español;
- reconexión automática del canal en vivo, sin respaldo por consulta HTTP (retirado el 2026-11-03);
- un enlace del menú para el personal;
- pruebas de concurrencia y una medición de la latencia confirmación → pantalla.

Fuera de este spec:

- **Tiempo estimado de espera (HU-18).** Se marcó al comienzo, pero la decisión final del usuario es dejarlo para un spec propio, que también deberá definir la medición de la preparación (HU-17). La pantalla no muestra ninguna estimación.
- Pasar el panel privado del 05 a WebSocket: sigue consultando cada segundo y no cambia.
- Modo sin conexión y caché de la PWA (reservado al 11) y notificaciones por mensaje al paciente (reservado al 12).
- Servicio de voz en la nube, grabaciones propias y nombres de pacientes en la voz.
- Varias pantallas con contenido distinto y configuración de qué ventanillas se muestran.
- Redis y despliegue con varios servidores detrás de un balanceador. El prototipo funciona con uno o varios procesos web gracias a la vigilancia de la base, sin servicio de mensajería aparte.
- Pruebas de usabilidad con cinco personas y aceptación funcional: son comprobaciones separadas, que este spec no declara cumplidas.

## Historias y flujo

1. El personal abre `/turnos/sala/` en el equipo de la sala. La pantalla carga su estado completo y se conecta al canal en vivo.
2. La pantalla pide activar el sonido, porque los navegadores no permiten audio sin un gesto de la persona. Quien instala el equipo pulsa «Activar sonido» una vez; el estado queda visible. Sin sonido la pantalla funciona igual, solo en modo visual.
3. El Técnico confirma un llamado (o re-llamado) en el 05. En la misma transacción queda un anuncio público con número y ventanilla.
4. El vigilante del servidor detecta el anuncio nuevo en menos de un segundo y lo envía a las pantallas conectadas.
5. La pantalla destaca el llamado con el texto «Número 23, ventanilla 2» (o «Nuevamente, número 23, ventanilla 2» si es un re-llamado). La voz dice esa misma frase dos veces, con una pausa entre ambas.
6. Si llegan varios llamados casi juntos, la voz los dice uno tras otro sin superponerse. Los números siguen visibles en la pantalla aunque algún aviso hablado se descarte.
7. Cuando el Técnico finaliza la atención o declara ausente al paciente, la tarjeta de esa ventanilla pasa a «Disponible» (o «Sin atención») sin pronunciar nada.
8. Si la conexión se corta, aparece un aviso visible, la pantalla reintenta con esperas crecientes. Al volver, recibe el estado completo; dice los llamados recientes que se perdió durante la caída y no repite los que ya había dicho.

## Requisitos funcionales

- **RF-06-01 — Registro público del llamado:** CUANDO el 05 confirma un llamado o un re-llamado, EL SISTEMA registra en la misma transacción un anuncio público con número de turno, número de ventanilla, tipo (`llamado` o `rellamado`) e instante, ligado de forma única al evento del 05. SI el anuncio no se puede registrar, ENTONCES se revierte el llamado completo y queda el pendiente recuperable del 05; no puede existir un llamado sin su anuncio ni un anuncio sin llamado. Repetir la misma operación no crea otro anuncio.
- **RF-06-02 — Canal en vivo de solo lectura:** CUANDO la pantalla se conecta al canal `/ws/sala/`, EL SISTEMA valida el origen de la conexión, aplica los límites de conexiones y le envía el estado público completo; después le envía cada anuncio nuevo y cada cambio de estado. SI el cliente envía datos, ENTONCES el servidor los ignora y no cambia nada. El canal envía además un latido periódico para detectar conexiones caídas.
- **RF-06-03 — Difusión entre procesos:** EL SISTEMA revisa la base cada 0,5 segundos por proceso web, y solo mientras haya pantallas conectadas, para detectar anuncios nuevos y cambios del estado público, y los difunde a las pantallas de ese proceso. Esto incluye los llamados hechos por `procesar_cola` u otro proceso. Cada anuncio se entrega una sola vez por conexión, en orden, sin pérdidas ni duplicados.
- **RF-06-04 — Contenido de la pantalla:** LA PANTALLA muestra: una tarjeta por cada ventanilla no retirada, con el número que está llamando, «Disponible» si tiene atención activa hoy y no está llamando, o «Sin atención» si no la tiene; el último llamado en grande; los últimos seis llamados con su hora; la hora y la fecha de Chile; y la cantidad de personas en espera con sus números en orden numérico, rotulados «En espera», nunca «próximos». No muestra tiempo estimado. No muestra RUT, nombre, categoría, recetas ni la prioridad de nadie.
- **RF-06-05 — Aviso visual y de voz concordantes:** CUANDO llega un anuncio, LA PANTALLA lo destaca visualmente con una frase y LA VOZ dice esa misma frase. Las frases son fijas: «Número {n}, ventanilla {v}» para un llamado y «Nuevamente, número {n}, ventanilla {v}» para un re-llamado. La voz repite la frase dos veces, con una pausa corta, y la precede un tono breve. Nada depende solo del color ni solo del sonido.
- **RF-06-06 — Fila de avisos de voz:** LOS AVISOS hablados se dicen en orden de llegada, completos y sin superponerse; la pantalla marca el aviso que suena. SI se acumulan más de cinco, ENTONCES se descartan los más antiguos de la fila, cuyos números siguen visibles. SI un aviso tiene más de 60 segundos al llegar a la pantalla, ENTONCES no se pronuncia. Al abrir la pantalla no se pronuncia el historial. Al reconectar tras una caída sí se pronuncian los anuncios que se perdieron durante ella, siempre que tengan menos de 60 segundos; los ya dichos no se repiten.
- **RF-06-07 — Activación y estado del sonido:** MIENTRAS el navegador no haya recibido un gesto de la persona, LA PANTALLA muestra de forma permanente y en texto que el sonido está desactivado y ofrece «Activar sonido». Una vez activado, muestra «Sonido activado» y ofrece «Probar sonido». SI el equipo no tiene una voz en español, ENTONCES lo avisa en texto, conserva el tono y el aviso visual y no finge que hubo voz.
- **RF-06-08 — Reconexión:** SI se pierde el canal en vivo, ENTONCES LA PANTALLA muestra en texto que no está conectada, conserva lo último que mostró, avisa que puede estar desactualizada y reintenta con esperas de 1 s hasta un máximo de 10 s. Tras tres intentos fallidos pide además acercarse a la ventanilla. Al recuperarse recibe el estado completo. SI el navegador no admite WebSocket, ENTONCES lo dice en texto y conserva el contenido inicial. No hay respaldo por HTTP (retirado el 2026-11-03).
- **RF-06-09 — Privacidad del contenido público:** EL CANAL y la pantalla solo contienen número de turno, número de ventanilla, tipo, instante, identificador del anuncio y la cantidad y números en espera. No se expone ninguna referencia al paciente, al turno interno ni a recetas. Las respuestas HTTP llevan `Cache-Control: no-store`, el sitio no pone cookies a quien solo mira la pantalla y los registros del servidor no contienen datos personales.
- **RF-06-10 — Accesibilidad de la pantalla:** LA PANTALLA cumple WCAG 2.1 AA: contraste de al menos 4,5:1 en el texto, tipografía grande y legible a distancia, aviso del llamado en una región viva, estados con texto, foco visible en los controles, sin destellos de más de tres por segundo y respeto de «reducir movimiento». El tamaño del texto puede ampliarse con el control existente del proyecto.
- **RF-06-11 — Sincronía medida:** EL SISTEMA muestra un llamado confirmado en la pantalla en 2 segundos o menos en al menos el 95 % de los casos, medido desde que se confirma la transacción del llamado hasta que el navegador de la pantalla recibe el anuncio. La medición registra cuántos llamados, con qué carga y con qué pantallas conectadas.
- **RF-06-12 — Acceso del personal y compatibilidad:** EL MENÚ ofrece «Pantalla de sala» a Técnico, Q.F. y superusuario, que la abre en otra pestaña. LAS rutas HTTP existentes, el tótem, el panel privado del 05 y su consulta periódica siguen funcionando igual con el servidor ahora capaz de WebSocket.

## Datos y reglas

### Registro público

Se propone un modelo `AnuncioSala`, con numeración global creciente que ordena la entrega:

| Campo | Regla |
|---|---|
| `id` | Entero autoincremental. Es el cursor de entrega: orden estricto e identidad pública del anuncio. |
| `fecha` | Fecha local de Chile del llamado. |
| `numero` | Número del turno llamado (positivo). |
| `ventanilla_numero` | Número de la ventanilla (positivo), copiado al momento del llamado. |
| `accion` | `llamado` o `rellamado`. |
| `instante` | Instante del evento, el mismo del `EventoTurno`. |
| `evento` | Relación uno a uno con `EventoTurno`: garantiza un solo anuncio por evento y hace idempotente el reproceso. |

El anuncio no guarda ni expone al paciente. Los anuncios se conservan como historial y no se borran en este spec.

### Estado público

No se guarda: se calcula en cada consulta de la jornada actual (`America/Santiago`).

- **Ventanillas:** las no retiradas. Con un turno llamado muestran su número y desde cuándo. Sin turno llamado muestran «Disponible» si su automatismo está activo hoy y están habilitadas, y «Sin atención» en otro caso.
- **Llamados recientes:** la pantalla muestra los últimos seis anuncios de la jornada. El estado envía hasta veinte para que la pantalla pueda decir los que se perdió durante una caída de conexión.
- **En espera:** cantidad de turnos de la jornada en estado `esperando` y sus números en orden numérico. Se muestran hasta 40 y, si hay más, «y N más». El orden numérico no promete el orden de llamado, que depende de la cola ponderada del 05.
- **Reloj:** la pantalla muestra la hora del servidor en `America/Santiago`, no la del navegador, para que un reloj descuadrado no engañe a nadie.

### Parámetros iniciales

Son propuestas ajustables en el plan, no reglas institucionales:

| Parámetro | Valor |
|---|---|
| Revisión de la base por proceso | 0,5 s |
| Latido del canal | cada 15 s; la pantalla reconecta si pasan 30 s sin recibir nada |
| Reconexión | 1 s, creciendo hasta 10 s |
| Intentos antes de pedir acercarse a la ventanilla | 3 |
| Fila de avisos hablados | máximo 5 |
| Vigencia de un aviso hablado | 60 s |
| Repeticiones de la voz | 2, con 1,5 s de pausa |
| Conexiones por proceso | 20 en total y 5 por dirección |

### Cambio de jornada

A medianoche la pantalla muestra solo la fecha nueva y no pronuncia anuncios de la anterior. Los anuncios de días pasados quedan en la tabla y no se vuelven a enviar.

## Criterios de aceptación

| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-06-01 | El Técnico confirma un llamado y luego un re-llamado | Quedan dos anuncios, de tipo `llamado` y `rellamado`, cada uno ligado a su evento, con el número y la ventanilla correctos. |
| RF-06-01 | Se repite el mismo POST de re-llamado o se reprocesa el pendiente | Un solo anuncio por evento; sin duplicados. |
| RF-06-01 | Falla el registro del anuncio durante un llamado | El llamado no queda confirmado y el pendiente sigue recuperable; no hay llamado sin anuncio. |
| RF-06-02 | Una pantalla se conecta y luego envía mensajes | Recibe el estado completo; los mensajes enviados no cambian nada. |
| RF-06-02 | Se conectan más pantallas que el límite o desde un origen no permitido | La conexión se rechaza; las pantallas ya conectadas no se afectan. |
| RF-06-03 | `procesar_cola` llama a un paciente en otro proceso | La pantalla conectada al servidor web recibe el anuncio en menos de 2 s, una sola vez. |
| RF-06-03 | Cuatro ventanillas llaman casi a la vez | Cuatro anuncios, en orden de `id`, sin pérdidas ni repeticiones en cada pantalla. |
| RF-06-04 | Hay llamados, ventanillas sin operador y personas en espera | La pantalla muestra cada ventanilla con su estado, el último llamado, los recientes, la hora y los números «En espera»; no aparece estimación de espera. |
| RF-06-04 | Hay más de 40 en espera | Se muestran 40 números y «y N más». |
| RF-06-05 | Llega un llamado y luego un re-llamado | La frase en pantalla y la frase de la voz coinciden letra por letra en ambos casos; la voz la dice dos veces. |
| RF-06-06 | Llegan seis avisos juntos | Se dicen en fila sin superponerse, se descartan los más antiguos de la fila por sobre cinco y todos los números permanecen visibles. |
| RF-06-06 | La pantalla se abre con anuncios previos, o llega uno de más de 60 s | No se pronuncia ninguno de ellos. |
| RF-06-06 | La conexión cae, ocurre un llamado durante la caída y la pantalla reconecta a los 20 s | Se pronuncia ese llamado una vez; los anteriores a la caída no se repiten. |
| RF-06-07 | La pantalla se abre sin gesto previo | Muestra en texto «Sonido desactivado» y el botón; tras pulsarlo muestra «Sonido activado» y permite probarlo. |
| RF-06-07 | El equipo no tiene voz en español | Avisa en texto, mantiene tono y aviso visual y no dice haber hablado. |
| RF-06-08 | Se corta la conexión y vuelve | Aparece el aviso de desconexión, reintenta con las esperas indicadas y, al volver, muestra el estado actual y dice solo lo que se perdió y sigue vigente. |
| RF-06-08 | El WebSocket no logra conectarse tras tres intentos | Conserva lo último mostrado, avisa que puede estar desactualizada, pide acercarse a la ventanilla y sigue reintentando. |
| RF-06-09 | Se inspeccionan el canal, el HTML y los registros | Solo hay número, ventanilla, tipo, instante, identificador, cantidad y números en espera; ni RUT, nombre, categoría ni referencias internas. |
| RF-06-10 | Auditoría automática y revisión de contraste, teclado y zoom | Sin errores de nivel AA, contraste ≥ 4,5:1, controles con foco visible y estados con texto. |
| RF-06-11 | Se miden al menos 100 llamados con la carga descrita y dos pantallas conectadas | El p95 de confirmación → recepción es ≤ 2 s y se registran la carga y el número de muestras. |
| RF-06-12 | Técnico, Q.F., Encargado y anónimo miran el menú | Los tres primeros ven el enlace según la matriz; el Encargado y el anónimo no. Las rutas del 04 y del 05 responden como antes. |

## No funcionales

- **Concurrencia (RNF-02):** el cambio toca el llamado del 05, así que requiere pruebas concurrentes con `TransactionTestCase`, hilos y conexiones separadas, con al menos tres escenarios: varias ventanillas llamando a la vez, repetición simultánea de un mismo re-llamado y llamado concurrente con la lectura del vigilante. Se afirman invariantes (un anuncio por evento, `id` estrictos, ningún anuncio perdido ni repetido), no solo la ausencia de errores.
- **Rendimiento (RNF-05, NS03):** ≤ 2 s entre confirmación y pantalla en el 95 % de los llamados, y ≤ 2 s en el 95 % de las solicitudes HTTP del spec, con datos sintéticos y el padrón de 670. La vigilancia no debe degradar las acciones del 05: se mide con la pantalla conectada.
- **Accesibilidad (RNF-04, NS07):** WCAG 2.1 AA según RF-06-10. La auditoría automática y la prueba con al menos cinco personas representativas requieren evidencia propia; no se declaran por tener pruebas de HTML.
- **Privacidad (RNF-01):** solo datos sintéticos. Ningún RUT, nombre ni categoría en el canal, el HTML público ni los registros. La pantalla no escribe nada del paciente en el navegador.
- **Portabilidad:** solo ORM de Django, sin SQL propio del motor, para correr sobre PostgreSQL (la base actual) y SQLite temporal (las herramientas de verificación).

## Compatibilidad

Se conservan el tótem y su comprobante (04), el padrón y las recetas (03), la autenticación y los roles (02) y el panel privado del 05 con su consulta cada segundo. El enganche en `cola.py` y `atencion.py` modifica la transacción del llamado y del re-llamado: antes de tocarla deben pasar las pruebas concurrentes del 05, que son sus contratos. No se renumera ni se modifica el historial de turnos; la migración solo agrega la tabla de anuncios. El servidor pasa a atender HTTP y WebSocket (ASGI); las herramientas `tools/verificar_spec_0X_http.py` siguen usando WSGI y SQLite temporal.

Las dependencias existen con los pendientes que sus propios documentos declaran (navegador, axe, usabilidad y aceptación). Este spec no los da por cerrados.

## Decisiones tomadas y alternativas

- **Tiempo real: WebSocket con Channels y vigilancia de la base.** Elegido por el usuario. Se descartó **Channels con Redis** por agregar un servicio que en Windows hay que instalar aparte, y la **consulta cada segundo sin WebSocket** por apartarse del informe (§7.1). La vigilancia de la base es la única vía de entrega: sirve igual aunque el llamado lo haga otro proceso y no depende de una capa de mensajes compartida.
- **Voz: síntesis del navegador de la pantalla.** Elegida por el usuario. Se descartaron las grabaciones propias (hay que grabar y mantener los archivos) y los servicios de voz en la nube (proveedor, costo e internet por definir). Se acepta que la calidad dependa del equipo de la sala y se exige avisar cuando no hay voz en español.
- **Acceso: pública de solo lectura con límites.** Elegida por el usuario. Se descartó la clave de pantalla por agregar un paso de instalación. La seguridad descansa en que el contenido no tiene datos personales, en la validación del origen y en el límite de conexiones.
- **Contenido extra:** hora y fecha, y números en espera en orden numérico con su cantidad. El usuario marcó además el tiempo estimado y los «próximos» según el orden real de llamado; al decidir, descartó los «próximos» y el tiempo estimado. Motivos: el orden de llamado no es el numérico y puede cambiar con cada llegada, y la estimación depende de la preparación, que no existe todavía (HU-18 y HU-17).
- **Voz dos veces por llamado.** Elegido por el usuario pensando en adultos mayores y una sala con ruido. Es una lectura ampliada de HU-04/05, que piden una voz al llamar y al re-llamar.
- **Fila de avisos en vez de interrupción.** Elegida por el usuario: ningún número queda sin decirse por una interrupción, a cambio de que la fila pueda atrasarse y por eso se acota en cinco y a 60 s.
- **Anuncio público en la misma transacción del llamado.** Garantiza que no haya llamado sin anuncio. A cambio, un defecto del registro bloquearía los llamados: se cubre con pruebas del 05 y con el pendiente recuperable.
- **Tabla pública separada del evento privado.** `AnuncioSala` no tiene referencia al paciente ni al turno, para que la privacidad esté en el diseño y no solo en la serialización.
- **El panel privado del 05 no cambia.** Mantiene su consulta cada segundo; llevarlo a WebSocket sería otro cambio sobre contratos con pruebas concurrentes.
- **Sonido con activación manual.** Los navegadores impiden reproducir audio sin un gesto. Se muestra el estado en texto y se documenta la opción de equipo en modo quiosco para quien instale la pantalla.
- **Tono generado en el navegador.** No requiere archivos de audio ni licencias.

## Supuestos y decisiones pendientes

No quedan preguntas funcionales bloqueantes. Supuestos técnicos reversibles, a confirmar en la revisión del plan:

- Los valores de la tabla de parámetros iniciales.
- Que el equipo de la sala tenga un navegador con síntesis de voz y una voz en español (idealmente `es-CL`); debe comprobarse en el hardware real, que es una dependencia institucional del informe.
- Que el servidor ASGI (Daphne) y Channels funcionen con el flujo actual de `runserver`; la versión exacta de los paquetes se fija en la implementación.
- Si la franja superior del layout (aviso de demostración y control de tamaño de texto) se conserva o se oculta en la pantalla de sala. Se propone conservarla.

## Revisión y cambios

2026-11-03 (posterior a la implementación): por instrucción del usuario se retira `GET /turnos/sala/estado/` (vista `sala_estado`, ruta y atributo `data-estado-url`) y con él el respaldo HTTP del cliente. La pantalla depende solo del WebSocket; el estado inicial sigue incrustado en `sala.html`. Consecuencia: si un proxy bloquea WebSocket o el canal cae, la pantalla no se actualiza hasta recuperar la conexión. Se actualizan RF-06-08, RF-06-09 y los parámetros; el historial de `validation.md` no se reescribe.

2026-11-03: primer bloque (WebSocket con Channels y vigilancia de la base, voz del navegador, pantalla pública de solo lectura, contenido adicional) y segundo bloque (números en espera en orden numérico con cantidad, tiempo estimado fuera, voz dos veces, fila de avisos). Se guardan cuatro documentos como Borrador, sin código, migraciones ni aceptación funcional.
