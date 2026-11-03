# Tareas — 06 / Pantalla de sala y voz

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-03. Estado: T-06-01 a T-06-07 completadas técnicamente; revisión visual pendiente por host, hardware y aceptación pendientes.
Autorización: invocación de `/spec-impl 06` y confirmación explícita del inicio de los pasos 1 a 7.

- [x] **T-06-01 — Esquema y registro público del llamado.**
  - RF: RF-06-01, RF-06-09.
  - Depende de: aprobación y autorización de implementación del 06; base 01–05 disponible.
  - Archivos previstos: `turnosapp/models.py`, nueva migración `turnosapp/0003_*`, nuevo `turnosapp/sala.py` (helper de registro), `turnosapp/cola.py` y `turnosapp/atencion.py` (enganche), `turnosapp/tests/test_sala_anuncios.py`, `turnosapp/tests/test_concurrencia_sala.py`.
  - Hecho cuando: cada llamado y re-llamado deja un anuncio, en la misma transacción, con el número y la ventanilla correctos y sin referencia al paciente; repetir una operación o reprocesar un pendiente no duplica; un fallo del registro revierte el llamado y deja el pendiente recuperable; al menos tres escenarios concurrentes con hilos y conexiones separadas cumplen sus invariantes; **pasan las pruebas del 05 sin cambios**; la migración se aplica en una base temporal.
- [x] **T-06-02 — Estado público y pantalla base.**
  - RF: RF-06-04, RF-06-09, RF-06-12.
  - Depende de: T-06-01.
  - Archivos previstos: `turnosapp/sala.py`, `turnosapp/views.py`, `turnosapp/urls.py`, `templates/components/Layout/base_sala.html`, `templates/turnos/sala.html`, `turnosapp/tests/test_sala_estado.py`.
  - Hecho cuando: `/turnos/sala/` y `/turnos/sala/estado/` responden sin sesión, con `no-store` y sin cookies para quien solo mira; el estado muestra ventanillas, recientes, espera (con el límite de 40) y hora del servidor; la prueba que recorre cada salida no encuentra datos de un paciente sintético; el tótem y el panel del 05 responden igual.
- [x] **T-06-03 — Capa ASGI, canal en vivo y vigilante.**
  - RF: RF-06-02, RF-06-03, RF-06-12.
  - Depende de: T-06-01 y T-06-02.
  - Archivos previstos: `requirements.txt`, `cesfam/settings.py`, `cesfam/asgi.py`, nuevos `turnosapp/consumers.py`, `routing.py` y `vigilante.py`, `turnosapp/tests/test_sala_canal.py`.
  - Hecho cuando: `daphne` y `channels` quedan instalados y `runserver` sirve HTTP y WebSocket; la conexión recibe el estado completo, luego cada anuncio una sola vez y en orden, incluso si lo hizo otro proceso y aunque confirme fuera de orden; los mensajes del cliente se ignoran; el origen no permitido y el exceso de conexiones se rechazan; el vigilante se detiene sin pantallas y resiste un error de lectura; el resto de la suite sigue pasando.
- [x] **T-06-04 — Cliente de sala: conexión, reconexión y respaldo.**
  - RF: RF-06-04, RF-06-08.
  - Depende de: T-06-03.
  - Archivos previstos: `static/js/sala.js`, `turnosapp/tests/sala.test.cjs`, ajustes de `templates/turnos/sala.html`.
  - Hecho cuando: la pantalla se actualiza sola desde el canal; cae y se recupera con las esperas indicadas; tras tres fallos pasa a consultar cada segundo y vuelve al canal; deduplica por `id`; el reloj usa la hora del servidor; las pruebas de JavaScript lo cubren con servidor y temporizadores simulados.
- [x] **T-06-05 — Voz, tono y fila de avisos.**
  - RF: RF-06-05, RF-06-06, RF-06-07.
  - Depende de: T-06-04.
  - Archivos previstos: `static/js/sala.js`, `turnosapp/tests/sala.test.cjs`.
  - Hecho cuando: la frase de pantalla y la de voz salen de la misma función; cada aviso suena con tono y dos repeticiones sin superponerse; la fila se acota en cinco y descarta los más antiguos; no se pronuncia el historial al abrir ni lo que tenga más de 60 s, y sí lo perdido y reciente al reconectar; el estado del sonido y la ausencia de voz en español se muestran en texto; las pruebas lo cubren con voz y audio simulados.
- [x] **T-06-06 — Presentación, accesibilidad y menú.**
  - RF: RF-06-10, RF-06-12.
  - Depende de: T-06-02 y T-06-05.
  - Archivos previstos: `static/css/sala.css`, `templates/turnos/sala.html`, `templates/components/navbar.html`, ajustes de `base.html` solo si se decide ocultar la franja, `coreapp/tests/test_estaticos.py`, pruebas de navegación.
  - Hecho cuando: tipografía grande, región viva para el llamado, estados con texto, foco visible, sin destellos y con «reducir movimiento» respetado; la hoja sin colores propios y con contraste verificado por prueba; el enlace «Pantalla de sala» aparece solo para Técnico, Q.F. y superusuario; la revisión visual y axe quedan registradas como hechas o como pendientes de host.
- [x] **T-06-07 — Integración, medición y documentación.**
  - RF: RF-06-11, RF-06-12 y regresión de RF-06-01 a RF-06-10.
  - Depende de: T-06-01 a T-06-06.
  - Archivos previstos: `tools/verificar_spec_06_http.py`, `README.md`, `docs/estructura.md`, `CLAUDE.md`, `specs/06-pantalla-sala-y-voz/validation.md`, `specs/README.md`.
  - Hecho cuando: la herramienta mide al menos 100 llamados con proceso web aparte, cuatro ventanillas y dos pantallas, y el p95 queda registrado con sus muestras y carga; la suite completa, las pruebas de JavaScript y `makemigrations --check` pasan; `validation.md` tiene resultados reales y límites; el estado del spec no pasa a Implementado sin la revisión de navegador, la voz en el hardware real, la prueba con cinco personas y la aceptación del usuario.

## Autorización posterior

2026-11-03: el usuario solicita «$spec-impl 06 solo crea un commit despues de terminar la implementacion», elige «2» para continuar preservando los cambios locales y confirma «si» al inicio de T-06-01. Se trabaja en `fdaza`, sin rama nueva, según el acuerdo de `CLAUDE.md`. Un único commit al terminar, excluyendo cambios ajenos. Se mantienen las pausas de revisión entre pasos; no se modifica `AutoCreateBranch`. No se autoriza migrar la base del proyecto ni se declara aceptación funcional.

## Ejecución

El usuario confirmó «si» para continuar con T-06-02 después de la revisión de T-06-01, «si» para T-06-03 después de la revisión de T-06-02, «si, continua» para T-06-04 después de revisar T-06-03, «si, continua» para T-06-05 tras revisar T-06-04 y «sip» para T-06-06, el 2026-11-03.

También confirmó «sip» para T-06-07. El único commit técnico final está autorizado por el mensaje original; no se autoriza merge/push ni migrar la base del proyecto.

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-03 | Definición | Cuatro documentos del 06 e índice | Borrador guardado, sin código, migraciones ni dependencias instaladas. |
| 2026-11-03 | T-06-01 | `models.py`, migración `0003_anuncio_sala`, `sala.py`, `cola.py`, `atencion.py`, dos archivos de pruebas nuevos | Registro atómico e idempotente; 146 pruebas de turnos aprobadas (133 previas + 13 nuevas), incluidos cuatro escenarios concurrentes. Migración aplicada en la base de pruebas PostgreSQL desechable, sin migrar la base del proyecto. Evidencia en `validation.md`. |
| 2026-11-03 | T-06-02 | `sala.py`, `views.py`, `urls.py`, `base_sala.html`, `sala.html`, `test_sala_estado.py` | Estado público de jornada chilena, tarjetas, recientes, espera y reloj del servidor; GET/HEAD públicos con `no-store` y sin cookies. 160 pruebas de turnos aprobadas (146 anteriores + 14 nuevas). Sin canal ni actualización automática todavía. |
| 2026-11-03 | T-06-03 | `requirements.txt`, `settings.py`, `asgi.py`, `consumers.py`, `routing.py`, `vigilante.py`, `test_sala_canal.py`, `test_sala_servidor.py` | Channels/Daphne instalados; canal público con origen, límites, latido y vigilancia. 16 pruebas nuevas y suite completa de 511 aprobadas. Servidor real y emisor en procesos separados con SQLite temporal; estáticos y HTTP correctos. Cliente de navegador y medición de carga pendientes. |
| 2026-11-03 | T-06-04 | `static/js/sala.js`, `templates/turnos/sala.html`, `turnosapp/tests/sala.test.cjs` | Cliente en vivo, reconexión, respaldo HTTP, deduplicación por jornada y reloj del servidor. 23 pruebas JS nuevas y 12 existentes aprobadas (35); 44 pruebas Django de sala/canal/servidor/estáticos aprobadas. Voz, revisión de navegador y carga pendientes. |
| 2026-11-03 | T-06-05 | `static/js/sala.js`, `templates/turnos/sala.html`, `turnosapp/tests/sala.test.cjs` | Activación/prueba, voz española, tono, dos repeticiones y fila de cinco pendientes. 19 pruebas JS nuevas (54 totales, todas OK) y 28 Django seleccionadas OK. Voz audible en el hardware real y revisión de navegador pendientes. |
| 2026-11-03 | T-06-06 | `static/css/sala.css`, `sala.html`, `sala.js`, `navbar.html`, `coreapp/tests/test_estaticos.py`, `test_sala_estado.py` | Composición para sala, texto grande, región viva, foco, paleta probada, sin destellos, menú por rol. 52 pruebas Django seleccionadas (5 nuevas) y 54 JS OK. Revisión visual/axe intentada, bloqueada por el host; no se declara hecha. Servidor temporal de QA cerrado y eliminado. |
| 2026-11-03 | T-06-07 | `tools/verificar_spec_06_http.py`, README, estructura, memoria, índice y documentos del 06 | 100 llamados a dos pantallas, cuatro puestos y 670 pacientes/turnos; p95 444,12 ms (máximo 536,66 ms). HTTP y 96 cierres reales del 05 bajo límite. Herramienta termina con código 0 y elimina el temporal. Regresión final: 516 pruebas Django y 54 JS OK; configuración y migraciones sin incidencias. Commit único de cierre técnico autorizado, conservando cambios ajenos. |

## Reanudación

Última acción real: siete pasos implementados y validación técnica final aprobada. Commit único de cierre técnico solicitado por el usuario en `fdaza`, excluyendo cambios previos ajenos. Continuación: revisión visual/axe cuando el host permita navegador, comprobación audible en el equipo de sala, prueba con cinco personas y aceptación funcional del usuario. El spec conserva Aprobado hasta completar esos pendientes. Base del proyecto sin migrar: requiere aprobación antes de usar allí el nuevo código. No hay despliegue, merge ni push autorizados. Temporal de medición y temporales de intentos fallidos eliminados.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
