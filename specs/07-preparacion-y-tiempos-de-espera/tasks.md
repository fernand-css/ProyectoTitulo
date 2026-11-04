# Tareas — 07 / Preparación y tiempos de espera

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-03. Estado: implementación y verificación técnica completas; revisión visual/axe/usabilidad y aceptación pendientes. Implementación autorizada por el usuario el 2026-11-03.

- [x] **T-07-01 — Esquema y recepción al emitir.**
  - RF: RF-07-01, RF-07-12.
  - Depende de: aprobación y autorización de implementación del 07; base 01–06 disponible.
  - Archivos previstos: `recetasapp/models.py`, nueva migración `recetasapp/0004_*`, `turnosapp/services.py`, `recetasapp/tests/test_preparacion_modelos.py`, `turnosapp/tests/test_emision_preparacion.py`, `turnosapp/tests/test_concurrencia_preparacion.py`.
  - Hecho cuando: cada turno emitido tiene una preparación por receta vinculada, creada en la misma transacción; una falla forzada revierte turno y número; recuperar un turno no duplica; la migración se aplica en una base desechable; un escenario concurrente de emisión con hilos y conexiones separadas no produce duplicados; **pasan las pruebas del 04, 05 y 06 sin cambios**.
- [x] **T-07-02 — Marcar y corregir «Lista», y medir el trabajo.**
  - RF: RF-07-02, RF-07-03, RF-07-07, RF-07-11.
  - Depende de: T-07-01.
  - Archivos previstos: `recetasapp/services.py`, `recetasapp/preparacion.py`, `recetasapp/tests/test_preparacion_servicios.py`, `test_preparacion_promedio.py`, y los escenarios concurrentes de marca en `test_concurrencia_preparacion.py`.
  - Hecho cuando: marcar es idempotente y concurrente sin doble medición; guarda el intervalo de trabajo según la regla; corregir exige turno activo y sin entrega; el promedio cumple ventana, tope y mínimo de muestras; la auditoría no lleva datos personales y revierte si falla; Técnico, Q.F. y superusuario pueden, y Encargado, anónimo y cuentas inválidas no.
- [x] **T-07-03 — Consultas derivadas y estimación.**
  - RF: RF-07-05, RF-07-08.
  - Depende de: T-07-02.
  - Archivos previstos: `recetasapp/preparacion.py`, `turnosapp/espera.py`, `recetasapp/tests/test_preparacion_consultas.py`, `turnosapp/tests/test_espera.py`.
  - Hecho cuando: pendientes de retiro incluye los tres cierres y excluye turnos activos y reincorporados; la búsqueda por RUT (con y sin puntos) y apellido funciona; la fórmula, el redondeo y los casos sin estimar se comprueban con valores exactos; el número de consultas por estimación es constante.
- [x] **T-07-04 — Retiro posterior e integración con 03/05.**
  - RF: RF-07-06, RF-07-12.
  - Depende de: T-07-03.
  - Archivos previstos: `recetasapp/services.py`, `turnosapp/atencion.py` (solo la validación al reincorporar), `recetasapp/tests/test_retiro.py`, `test_concurrencia_preparacion.py`.
  - Hecho cuando: el retiro crea una sola entrega del vínculo original con vigencia a la fecha de preparación; el cupo no se excede; repetir el POST no duplica; el cierre histórico no cambia; reincorporar con todo retirado se rechaza; al menos tres escenarios concurrentes (dos retiros, retiro frente a entrega del 03, retiro frente a reincorporación) cumplen sus invariantes; **las pruebas del 03 y del 05 pasan sin cambios**.
- [x] **T-07-05 — Sección Preparación dentro de Recetas.**
  - RF: RF-07-04, RF-07-05, RF-07-06, RF-07-11.
  - Depende de: T-07-04.
  - Archivos previstos: `recetasapp/views.py`, `urls.py`, `forms.py`, `templates/recetas/preparacion_*.html`, `templates/recetas/recetas_lista.html` (enlace), `static/css/preparacion.css`, posible `static/js/preparacion.js`, `recetasapp/tests/test_preparacion_vistas.py`, `test_preparacion_permisos.py`, `coreapp/tests/test_estaticos.py`.
  - Hecho cuando: las dos pestañas funcionan con sus acciones POST protegidas con CSRF, `no-store` y rechazo por rol en servidor; la hoja de estilos cumple las reglas de colores y contraste del proyecto; no hay entrada nueva en el menú; la revisión visual y axe quedan registradas como hechas o como pendientes de host.
- [x] **T-07-06 — Estimación en tótem, comprobante y panel.**
  - RF: RF-07-09, RF-07-10, RF-07-11.
  - Depende de: T-07-03 y T-07-05.
  - Archivos previstos: `turnosapp/services.py`, `turnosapp/panel.py`, `templates/turnos/resultado.html`, `comprobante.html`, `_estado.html`, pruebas de tótem, panel y privacidad.
  - Hecho cuando: el resultado y el comprobante muestran la misma frase, también al recuperar un turno; la prueba de privacidad no encuentra datos de un paciente sintético en ninguna salida pública; el panel muestra la carga y la estimación y se actualiza con su consulta; el tótem, el comprobante y el panel del 05 responden como antes en todo lo demás.
- [x] **T-07-07 — Integración, medición y documentación.**
  - RF: RF-07-01 a RF-07-12 (regresión).
  - Depende de: T-07-01 a T-07-06.
  - Archivos previstos: `tools/verificar_spec_07_http.py`, `README.md`, `docs/estructura.md`, `CLAUDE.md`, `specs/07-preparacion-y-tiempos-de-espera/validation.md`, `specs/README.md`.
  - Hecho cuando: la herramienta ejecuta el recorrido HTTP completo con SQLite temporal, 670 pacientes sintéticos y varias ventanillas, y registra el p95; la suite completa, las pruebas de JavaScript y `makemigrations --check` pasan; `validation.md` tiene resultados reales y límites; HU-18 se declara cubierta de forma parcial; el estado del spec no pasa a Implementado sin revisión de navegador, usabilidad y aceptación del usuario.

## Autorización posterior

El usuario autorizó la implementación de la spec 07 con «implementa la spec 07» y confirmó el inicio de T-07-01 con «sip, comienza» el 2026-11-03. Se autoriza la implementación de T-07-01 a T-07-07; no se autoriza migrar la base del proyecto ni hacer commits. Se conserva el acuerdo vigente de trabajar en `fdaza`.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-03 | Definición | Cuatro documentos del 07 e índice | Borrador guardado, sin código, migraciones ni dependencias instaladas. |
| 2026-11-03 | T-07-01 | Modelo `PreparacionReceta`, migración `0004_preparacionreceta`, emisión y pruebas nuevas; `manage.py test --noinput` | Preparación por vínculo dentro de la transacción de emisión. 523 pruebas Django pasan; ver `validation.md`. Se adaptó solo la limpieza del fixture de emisión para borrar primero la relación protegida; sus aserciones no cambiaron. |
| 2026-11-03 | T-07-02 | Servicios de marca/corrección, promedio y pruebas unitarias/concurrentes | Idempotencia, intervalos del mismo usuario, auditoría sin datos personales, matriz de roles, tope/ventana/mínimo y rollback cubiertos. |
| 2026-11-03 | T-07-03 | Consultas derivadas y `turnosapp/espera.py`; pruebas de consultas y fórmula | Búsqueda por RUT/apellido, tres cierres, redondeo, sin ventanillas y número constante de consultas verificados. |
| 2026-11-03 | T-07-04 | Retiro, reincorporación, concurrencia y compatibilidad con entregas | Vigencia a fecha de preparación, cupo actual, idempotencia y cierre histórico; cinco escenarios concurrentes. Se adaptó una limpieza de fixture `PROTECT`, sin cambiar aserciones de los specs anteriores. |
| 2026-11-03 | T-07-05 | Vistas, formularios, rutas, plantillas, CSS, actualización y pruebas HTTP/CSRF | Sección privada conectada a Recetas, búsqueda por POST y acciones con CSRF/no-store. Revisión visual/móvil/axe queda pendiente por host de navegador. |
| 2026-11-03 | T-07-06 | Resultado y comprobante del tótem, panel 05 y pruebas | Una única frase aproximada compartida; panel periódico con cantidad, promedio, muestras y enlace. Privacidad pública comprobada. |
| 2026-11-03 | T-07-07 | `tools/verificar_spec_07_http.py`, regresión, Node, `check`, migraciones y documentación | 670 pacientes, 100 turnos y cuatro ventanillas; siete escenarios HTTP, 100 muestras cada uno y todos los p95 bajo 110 ms. 550 pruebas Django y 58 pruebas Node pasan; `check` sin problemas y `makemigrations --check --dry-run` sin cambios. Ver resultados en `validation.md`. |

## Reanudación

T-07-01 a T-07-07 completadas en `fdaza`, con autorización de seguir de corrido del usuario el 2026-11-03. Revisión visual en navegador/axe, usabilidad y aceptación funcional siguen pendientes. No hacer commit ni migrar la base del proyecto.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
