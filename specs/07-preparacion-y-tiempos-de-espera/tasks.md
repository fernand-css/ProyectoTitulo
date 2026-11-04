# Tareas — 07 / Preparación y tiempos de espera

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-03. Estado: propuestas. Implementación autorizada: NO.
No ejecutar tareas de código por el hecho de aparecer aquí.

- [ ] **T-07-01 — Esquema y recepción al emitir.**
  - RF: RF-07-01, RF-07-12.
  - Depende de: aprobación y autorización de implementación del 07; base 01–06 disponible.
  - Archivos previstos: `recetasapp/models.py`, nueva migración `recetasapp/0004_*`, `turnosapp/services.py`, `recetasapp/tests/test_preparacion_modelos.py`, `turnosapp/tests/test_emision_preparacion.py`, `turnosapp/tests/test_concurrencia_preparacion.py`.
  - Hecho cuando: cada turno emitido tiene una preparación por receta vinculada, creada en la misma transacción; una falla forzada revierte turno y número; recuperar un turno no duplica; la migración se aplica en una base desechable; un escenario concurrente de emisión con hilos y conexiones separadas no produce duplicados; **pasan las pruebas del 04, 05 y 06 sin cambios**.
- [ ] **T-07-02 — Marcar y corregir «Lista», y medir el trabajo.**
  - RF: RF-07-02, RF-07-03, RF-07-07, RF-07-11.
  - Depende de: T-07-01.
  - Archivos previstos: `recetasapp/services.py`, `recetasapp/preparacion.py`, `recetasapp/tests/test_preparacion_servicios.py`, `test_preparacion_promedio.py`, y los escenarios concurrentes de marca en `test_concurrencia_preparacion.py`.
  - Hecho cuando: marcar es idempotente y concurrente sin doble medición; guarda el intervalo de trabajo según la regla; corregir exige turno activo y sin entrega; el promedio cumple ventana, tope y mínimo de muestras; la auditoría no lleva datos personales y revierte si falla; Técnico, Q.F. y superusuario pueden, y Encargado, anónimo y cuentas inválidas no.
- [ ] **T-07-03 — Consultas derivadas y estimación.**
  - RF: RF-07-05, RF-07-08.
  - Depende de: T-07-02.
  - Archivos previstos: `recetasapp/preparacion.py`, `turnosapp/espera.py`, `recetasapp/tests/test_preparacion_consultas.py`, `turnosapp/tests/test_espera.py`.
  - Hecho cuando: pendientes de retiro incluye los tres cierres y excluye turnos activos y reincorporados; la búsqueda por RUT (con y sin puntos) y apellido funciona; la fórmula, el redondeo y los casos sin estimar se comprueban con valores exactos; el número de consultas por estimación es constante.
- [ ] **T-07-04 — Retiro posterior e integración con 03/05.**
  - RF: RF-07-06, RF-07-12.
  - Depende de: T-07-03.
  - Archivos previstos: `recetasapp/services.py`, `turnosapp/atencion.py` (solo la validación al reincorporar), `recetasapp/tests/test_retiro.py`, `test_concurrencia_preparacion.py`.
  - Hecho cuando: el retiro crea una sola entrega del vínculo original con vigencia a la fecha de preparación; el cupo no se excede; repetir el POST no duplica; el cierre histórico no cambia; reincorporar con todo retirado se rechaza; al menos tres escenarios concurrentes (dos retiros, retiro frente a entrega del 03, retiro frente a reincorporación) cumplen sus invariantes; **las pruebas del 03 y del 05 pasan sin cambios**.
- [ ] **T-07-05 — Sección Preparación dentro de Recetas.**
  - RF: RF-07-04, RF-07-05, RF-07-06, RF-07-11.
  - Depende de: T-07-04.
  - Archivos previstos: `recetasapp/views.py`, `urls.py`, `forms.py`, `templates/recetas/preparacion_*.html`, `templates/recetas/recetas_lista.html` (enlace), `static/css/preparacion.css`, posible `static/js/preparacion.js`, `recetasapp/tests/test_preparacion_vistas.py`, `test_preparacion_permisos.py`, `coreapp/tests/test_estaticos.py`.
  - Hecho cuando: las dos pestañas funcionan con sus acciones POST protegidas con CSRF, `no-store` y rechazo por rol en servidor; la hoja de estilos cumple las reglas de colores y contraste del proyecto; no hay entrada nueva en el menú; la revisión visual y axe quedan registradas como hechas o como pendientes de host.
- [ ] **T-07-06 — Estimación en tótem, comprobante y panel.**
  - RF: RF-07-09, RF-07-10, RF-07-11.
  - Depende de: T-07-03 y T-07-05.
  - Archivos previstos: `turnosapp/services.py`, `turnosapp/panel.py`, `templates/turnos/resultado.html`, `comprobante.html`, `_estado.html`, pruebas de tótem, panel y privacidad.
  - Hecho cuando: el resultado y el comprobante muestran la misma frase, también al recuperar un turno; la prueba de privacidad no encuentra datos de un paciente sintético en ninguna salida pública; el panel muestra la carga y la estimación y se actualiza con su consulta; el tótem, el comprobante y el panel del 05 responden como antes en todo lo demás.
- [ ] **T-07-07 — Integración, medición y documentación.**
  - RF: RF-07-01 a RF-07-12 (regresión).
  - Depende de: T-07-01 a T-07-06.
  - Archivos previstos: `tools/verificar_spec_07_http.py`, `README.md`, `docs/estructura.md`, `CLAUDE.md`, `specs/07-preparacion-y-tiempos-de-espera/validation.md`, `specs/README.md`.
  - Hecho cuando: la herramienta ejecuta el recorrido HTTP completo con SQLite temporal, 670 pacientes sintéticos y varias ventanillas, y registra el p95; la suite completa, las pruebas de JavaScript y `makemigrations --check` pasan; `validation.md` tiene resultados reales y límites; HU-18 se declara cubierta de forma parcial; el estado del spec no pasa a Implementado sin revisión de navegador, usabilidad y aceptación del usuario.

## Autorización posterior

Pendiente. Registrar mensaje y fecha, y las tareas autorizadas, solo cuando ocurra. Aprobar los requisitos no autoriza producción ni commits. Se conserva el valor de `AutoCreateBranch` y el acuerdo vigente de trabajar en `fdaza`.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-03 | Definición | Cuatro documentos del 07 e índice | Borrador guardado, sin código, migraciones ni dependencias instaladas. |

## Reanudación

Última acción real: definición documental del 07. Siguiente paso: revisión del usuario, cambio a Aprobado y autorización explícita con `/spec-impl 07-preparacion-y-tiempos-de-espera`. Sin bloqueos técnicos conocidos.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
