# Tareas — 05 / Cola ponderada y llamado

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-02. Estado: seis pasos técnicos completados; navegador/axe/usabilidad y aceptación pendientes.
Las tareas no constituyen autorización de código, migración o commit.

- [x] **T-05-01 — Esquema, restricciones y preparación operativa.**
  - RF: RF-05-01, RF-05-02, RF-05-05, RF-05-07, RF-05-08, RF-05-10, RF-05-11, RF-05-12.
  - Depende de: aprobación/implementación autorizada del 05 y base 01–04 disponible.
  - Archivos previstos: `turnosapp/models.py`, nuevas migraciones de turnos/recetas; modelos de recetas para vínculo; nuevo comando `preparar_ventanillas`; tests de modelos/migraciones.
  - Hecho cuando: estados y restricciones nuevos admiten historial existente sin renumerar/borrar; base vacía y actualización sintética funcionan; cuatro ventanillas y pesos se preparan explícitamente sin activar llamados ni duplicar al repetir.
  - Resultado: dos migraciones, comando idempotente y 13 pruebas nuevas incorporadas; **335 pruebas de regresión aprobadas**, sin migraciones faltantes. Preparación y migraciones solo en SQLite temporal; código de cola aún pendiente.
- [x] **T-05-02 — Cola y procesador automático durable.**
  - RF: RF-05-02, RF-05-03, RF-05-04, RF-05-08, RF-05-12.
  - Depende de: T-05-01.
  - Archivos previstos: nuevos `cola.py`, `management/commands/procesar_cola.py`, `tests/test_cola.py`, `test_concurrencia_cola.py`; integración de disparadores en `services.py`.
  - Hecho cuando: P,P,C,G global, compatibilidad, rescate a 15 min y cursor son deterministas; no duplica llamado ni deriva a deshabilitada; pendientes sobreviven reinicio y se procesan una vez sin requerir un clic por paciente.
  - Resultado: planificador y comando incorporados; 18 pruebas nuevas (15 funcionales y tres concurrentes); **353 de regresión aprobadas**, sin migraciones faltantes. Persistencia y recuperación probadas por comando; reinicio real de proceso, acciones operativas y sus carreras se validarán en pasos posteriores.
- [x] **T-05-03 — Operación de ventanilla, ausentes, retorno y jornada.**
  - RF: RF-05-01, RF-05-04, RF-05-05, RF-05-06, RF-05-09, RF-05-10, RF-05-11, RF-05-12.
  - Depende de: T-05-02.
  - Archivos previstos: nuevo `atencion.py`, tests de ventanillas/atención/jornada; ampliación de emisión y sus pruebas.
  - Hecho cuando: ocupación exclusiva, activación/pausa, minuto de ausencia, re-llamado idempotente y retorno correcto; nuevo número solo sin activo y con elegibilidad; medianoche no arrastra cola ni elimina atención vigente; no hay traslados inesperados.
  - Resultado: 23 pruebas nuevas (17 funcionales/jornada y seis concurrentes), regresión de **376 aprobada**, 17 focalizadas finales aprobadas y sin migraciones faltantes. Sin interfaz ni cierre de entregas aún; no se modificó la base local.
- [x] **T-05-04 — Cierre y entregas sin duplicación entre módulos.**
  - RF: RF-05-07, RF-05-08, RF-05-12.
  - Depende de: T-05-03.
  - Archivos previstos: `recetasapp/services.py`, `turnosapp/atencion.py`, tests de cierre y concurrencia de entregas/cola.
  - Hecho cuando: confirmación seleccionada atómica con cierre, motivo de no entrega, integración idempotente 03/05, cupo respetado y entrega conservada si falla el próximo llamado; reenvío de cierre anterior no altera el turno que vino después.
  - Resultado: cierre integrado y contexto firmado del formulario de recetas incorporados; 20 pruebas nuevas (16 funcionales y cuatro concurrentes); **396 de regresión aprobadas**, sin migraciones faltantes. Formulario del 03 probado con cliente Django; panel/cierre visual del 05 todavía pendientes del paso 5.
- [x] **T-05-05 — Panel y configuración con permisos.**
  - RF: RF-05-01 a RF-05-12.
  - Depende de: T-05-04.
  - Archivos previstos: `turnosapp/forms.py`, `views.py`, `urls.py`, Admin sin escritura directa; nuevas plantillas panel/gestión/cierre/historial y estáticos de cola; navbar/inicio y pruebas afectadas.
  - Hecho cuando: Técnico opera su ventanilla sin seleccionar siguiente; Q.F. configura pero no confirma entregas; GET no muta, POST tiene CSRF; estados automáticos/pausa/conflicto/pendiente son claros y privados; sin pantalla pública ni voz ficticias.
  - Resultado: panel privado, gestión de ventanillas/pesos, cierre e historial incorporados; 15 pruebas nuevas de cliente Django y cinco de JavaScript aprobadas; regresión completa de **411 aprobadas**, sin migraciones faltantes. GET de panel/estado/cierre/historial sin escrituras, permisos por rol/puesto, CSRF y reenvío idempotente comprobados. Revisión visual y HTTP real quedan para T-05-06.
- [x] **T-05-06 — Integración y evidencia final.**
  - RF: RF-05-01 a RF-05-12; RNF-01/02/04/05.
  - Depende de: T-05-05.
  - Archivos previstos: `tools/verificar_spec_05_http.py`, pruebas de integración/regresión, `README.md`, `docs/estructura.md`, memoria y cuatro documentos del 05.
  - Hecho cuando: migraciones, suites, al menos tres escenarios concurrentes, HTTP real, rendimiento y recuperación tras reinicio tienen resultados reales; navegador/axe/teclado/usabilidad/aceptación se verifican o se registran pendientes explícitos. No declarar Implementado si faltan criterios de aceptación requeridos.
  - Resultado: herramienta HTTP aprobada con 670 pacientes sintéticos, cuatro ventanillas, tres escenarios concurrentes y recuperación de pendiente en un proceso nuevo. Cien muestras por operación: p95 emisión 73,51 ms, estado 55,18 ms y cierre 177,05 ms. Regresión vigente: 411 Django y siete JavaScript aprobadas. Host de navegador y pipe nativo no disponibles en esta sesión; revisión visual/axe/usabilidad y aceptación pendientes explícitos. Estado Aprobado conservado.

### Enmienda del 2026-11-15 (RF-05-13)

- [x] **T-05-07 — Urgencia como tipo de ventanilla.**
  - RF: RF-05-13 (RF-05-01).
  - Archivos previstos: `turnosapp/models.py`, migración `0008`, `preparar_ventanillas`, pruebas de esquema y migración.
  - Hecho cuando: las ventanillas admiten P, C, G y U; las existentes reciben U al migrar; la reversión quita U sin borrar historia.
  - Resultado: `TIPOS_VENTANILLA` incluye urgencia (formulario, panel y `preparar_ventanillas` lo heredan). Migraciones `0008` (esquema) y `0009` (datos, separada porque PostgreSQL rechaza ALTER TABLE con disparadores de FK pendientes al revertir). Una base sin ventanillas no recibe tipos. Dos pruebas nuevas de migración y la de preparación ajustada a cuatro tipos; 75 focalizadas aprobadas sobre PostgreSQL, sin migraciones faltantes.
- [x] **T-05-08 — Fila U primero.**
  - RF: RF-05-13 (RF-05-02, RF-05-03).
  - Depende de: T-05-07.
  - Archivos previstos: `turnosapp/cola.py`, pruebas de cola y concurrencia.
  - Hecho cuando: un U compatible se llama antes que cualquier P, C o G (también ante rescate de 15 minutos), varios U por orden de entrada, el cursor ponderado no avanza; tres escenarios concurrentes sin doble asignación.
  - Resultado: `_candidato` busca primero el U compatible más antiguo y devuelve el cursor sin cambios; el rescate de 15 minutos excluye U. Cinco pruebas funcionales (orden, rescate, varias U, compatibilidad y U sin ventanilla compatible) y tres concurrentes con `TransactionTestCase` e hilos (mismo U disputado, tres ventanillas con dos U, ventanillas incompatibles). 26 aprobadas en PostgreSQL.
- [x] **T-05-09 — Cierre de turnos sin recetas.**
  - RF: RF-05-13 (RF-05-07).
  - Depende de: T-05-07.
  - Archivos previstos: `turnosapp/atencion.py`, `forms.py`, `templates/turnos/finalizar.html`, pruebas de cierre.
  - Hecho cuando: un turno sin recetas vinculadas se cierra «sin entrega» con el motivo fijo «Atención sin recetas del sistema», sin pedir texto, sin `EntregaReceta` ni dispensación.
  - Resultado: `atencion.MOTIVO_SIN_RECETAS` reemplaza cualquier motivo recibido cuando no hay vínculos; `FinalizarForm` quita recetas y motivo y deja solo la confirmación; `finalizar.html` explica el cierre. Dos pruebas nuevas (servicio con y sin paciente del padrón, formulario por cliente Django); 24 aprobadas con las de cierre.
- [x] **T-05-10 — Integración de la enmienda.**
  - RF: RF-05-13; RNF-02.
  - Depende de: T-05-08 y T-05-09.
  - Archivos previstos: `tools/verificar_spec_05_http.py`, `CLAUDE.md`, `docs/estructura.md`, cuatro documentos del 05.
  - Hecho cuando: regresión completa, migraciones sin faltantes y HTTP real con resultados registrados; pendientes visuales explícitos.
  - Resultado: regresión completa de **920 aprobadas** en PostgreSQL (908 previas y 12 nuevas), cinco suites JavaScript aprobadas, `check` y `makemigrations --check` limpios. La herramienta HTTP agrega el escenario de la enmienda: con una sola ventanilla automática, U se llama antes que un G de 20 minutos y que el turno emitido por el tótem para un RUT fuera del padrón; los tres cierres sin recetas llevan el motivo fijo y no crean entregas. `CLAUDE.md`, `docs/estructura.md` y `specs/README.md` actualizados. Navegador/axe/usabilidad y aceptación siguen pendientes.

## Autorización posterior

2026-11-02: encabezado Aprobado por el usuario e invocación de `spec-impl 05`, con instrucción explícita de no crear rama y hacer commit. Aplicar acuerdo de `spec.md`: `fdaza`, un solo commit al finalizar y cambios ajenos del índice preservados fuera del commit. Arranque de T-05-01 pendiente de confirmación; pausas de revisión por paso vigentes.

Confirmación posterior «si, continua» autoriza T-05-01. Se mantienen las pausas de revisión antes de T-05-02 y siguientes; ningún commit intermedio.

Confirmación posterior «si, continua» tras el paso 1 autoriza T-05-02; pausa antes de T-05-03.

Confirmación posterior «si, continua» tras el paso 2 autoriza T-05-03; pausa antes de T-05-04.

Confirmación posterior «si» tras el paso 3 autoriza T-05-04; pausa antes de T-05-05.

Confirmación posterior «si, continua» autoriza T-05-05; pausa antes de T-05-06. Se mantiene la rama y el único commit al finalizar.

Confirmación «ok, hazlo brevemente por los limites» autoriza T-05-06 y el cierre con el único commit previamente solicitado, sin nueva rama.

2026-11-15: la usuaria pidió «sigamos con los cambios de la spec 5» para implementar la enmienda RF-05-13 sobre `fdaza`, sin rama nueva y con un único commit al cierre. Pausa de revisión tras cada paso.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-02 | Definición | Cuatro documentos e índice | Borrador; ninguna tarea de código iniciada. |
| 2026-11-02 | T-05-01 | Modelos, dos migraciones, comando y pruebas | 13 pruebas nuevas; regresión completa de 335 aprobada; sin migraciones faltantes. |
| 2026-11-02 | T-05-02 | Cola, procesador, disparador de emisión y pruebas | 18 nuevas; 353 de regresión aprobadas; sin migraciones faltantes. |
| 2026-11-02 | T-05-03 | Operación, jornada e integración con emisión | 23 nuevas; 376 de regresión aprobadas y 17 focalizadas finales; sin migraciones faltantes. |
| 2026-11-02 | T-05-04 | Cierre/entregas y contexto de formularios del 03 | 20 nuevas; 396 de regresión aprobadas; sin migraciones faltantes. |
| 2026-11-02 | T-05-05 | Panel, gestión, formularios, historial y navegación | 15 nuevas de Django y cinco de JavaScript aprobadas; 411 de regresión aprobadas; integración visual/HTTP pendiente. |
| 2026-11-02 | T-05-06 | HTTP real, proceso nuevo y documentación | HTTP/rendimiento aprobados; pendientes visuales y aceptación registrados. |
| 2026-11-15 | T-05-07 | Tipo U de ventanilla, migraciones 0008/0009 y pruebas | 75 focalizadas aprobadas; sin migraciones faltantes. |
| 2026-11-15 | T-05-08 | `cola._candidato`, pruebas de cola y concurrencia | 8 nuevas; 26 focalizadas aprobadas. |
| 2026-11-15 | T-05-09 | Cierre sin recetas en servicio, formulario y plantilla | 2 nuevas; 24 focalizadas aprobadas. |
| 2026-11-15 | T-05-10 | Regresión, HTTP real y documentos | 920 Django y 5 JavaScript aprobadas; HTTP aprobado con el escenario de la enmienda. |

## Reanudación

Última acción: T-05-10 (enmienda RF-05-13) completada técnicamente el 2026-11-15; antes, T-05-06. Siguiente: revisión visual con navegador disponible, axe, teclado/zoom/móvil, usabilidad y aceptación del equipo. No marcar Implementado por las pruebas automatizadas. Rama `fdaza`, único commit autorizado al cierre; cambios ajenos del índice preservados.

## Aceptación del usuario

Documento aprobado por el usuario. Aceptación funcional pendiente; no deducirla de aprobación documental o tests.
