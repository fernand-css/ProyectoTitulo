# Tareas — 03 / Padrón y recetas

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha de definición: 2026-11-01. Actualización: 2026-11-02. Estado: pasos 1 a 5 completados; verificación técnica y documentación del paso 6 completadas, visual/móvil/axe pendientes por entorno. Autorizada en `fdaza`, sin rama nueva y con commit al terminar.

Las rutas de los pasos completados existen en el código. El alcance restante de validación se identifica expresamente; una prueba planificada no equivale a evidencia ejecutada.

- [x] **T-03-01 — Crear modelos y migración inicial del dominio.**
  - RF: RF-03-01, RF-03-06, RF-03-07, RF-03-09.
  - Depende de: specs 01/02 disponibles; revisión y autorización del 03.
  - Archivos previstos: `recetasapp/models.py`, nueva `migrations/0001_initial.py`, `tests/test_modelos.py`.
  - Hecho cuando: pacientes, recetas, entregas, cargas y resultados tienen restricciones verificadas; base nueva y actualización sintética migran conservando cuentas/auditoría; no se crean datos al arrancar.
- [x] **T-03-02 — Implementar servicios de recetas y entregas auditadas.**
  - RF: RF-03-07, RF-03-08, RF-03-09, RF-03-10.
  - Depende de: T-03-01.
  - Archivos previstos: nuevo `recetasapp/services.py`, `tests/test_servicios.py`, `test_concurrencia.py`, `test_auditoria.py`; `recetasapp/admin.py` para impedir escritura directa.
  - Hecho cuando: creación/renovación conserva historial; calendario y elegibilidad cubren límites; una entrega suma una vez; repetición y concurrencia no exceden cupo; contador coincide con eventos y fallo de auditoría revierte cambios; permisos se validan dentro del servicio.
- [x] **T-03-03 — Implementar importación y reportes persistentes.**
  - RF: RF-03-01 a RF-03-06, RF-03-10.
  - Depende de: T-03-02.
  - Archivos previstos: nuevo `recetasapp/importacion.py`, ampliación de services, `requirements.txt`, nuevos `tests/test_importacion.py` y ampliación de pruebas de concurrencia/auditoría.
  - Hecho cuando: CSV/XLSX cumplen contrato; estructura y límites se validan; filas válidas continúan y las rechazadas no dejan cambios de dominio; duplicados se resuelven sin depender del orden; no se altera historial por reimportación; concurrencia con entregas/cargas preserva invariantes; bitácora, conteos y estados distinguen rechazos e interrupciones.
- [x] **T-03-04 — Proveer plantillas y datos sintéticos reproducibles.**
  - RF: RF-03-02, RF-03-11.
  - Depende de: T-03-03.
  - Archivos previstos: generadores en `recetasapp/importacion.py`, nuevo `management/commands/generar_padron_demo.py`, nuevo `tests/test_comandos.py`.
  - Hecho cuando: comando explícito con semilla y salida indicada genera CSV/XLSX de 670 pacientes con RUT válidos y ejemplos de recetas; no escribe la base ni sobrescribe un destino existente sin opción explícita; ambos archivos se importan y repiten sin duplicar identidades.
- [x] **T-03-05 — Integrar vistas privadas, formularios y navegación.**
  - RF: RF-03-01, RF-03-02, RF-03-06 a RF-03-10.
  - Depende de: T-03-04.
  - Archivos previstos: nuevos `recetasapp/forms.py`, `tests/test_vistas.py`; `recetasapp/views.py`, `urls.py`; nuevas plantillas `templates/recetas/`; navbar e inicio y pruebas de navegación afectadas.
  - Hecho cuando: Técnico consulta y confirma entregas; Q.F. importa, crea y renueva; reportes/plantillas respetan permisos; GET no cambia dominio; POST exige CSRF; búsqueda no expone identificadores en URL; se muestran estados vacíos, errores y conflictos recuperables; roles, superusuario e IDs manipulados están cubiertos.
- [ ] **T-03-06 — Verificar alcance completo y actualizar documentación.**
  - RF: RF-03-01 a RF-03-11.
  - Depende de: T-03-05.
  - Archivos previstos: pruebas pertinentes, eventual herramienta HTTP aislada; `README.md`, `docs/estructura.md`, `CLAUDE.md`, cuatro documentos de esta carpeta e índice.
  - Hecho cuando: checks, migraciones y regresión tienen resultados reales; se demuestra carga/repetición de 670 pacientes en ambos formatos, historial y permisos; revisión HTTP/CSRF, visual, móvil, accesibilidad y p95 quedan registrados con límites. El bloqueo efectivo de emisión de turnos permanece explícitamente pendiente de su integración futura, sin declararlo probado aquí.
  - Avance: código, regresión, HTTP real/CSRF, migraciones, carga y repetición de 670, rendimiento, comprobaciones estructurales de accesibilidad y documentación completados. Pendiente: revisión visual/móvil y axe del módulo. El host de navegador no responde y Firefox no expone una ventana capturable; no marcar realizadas esas comprobaciones.

## Autorización posterior

2026-11-02: estado Aprobado y petición explícita `spec-impl 03-padron-y-recetas`, sin rama nueva y con commit. Confirmación «comienza» para el paso 1; posteriormente «si, ahora continua todos los pasos solito» autoriza pasos 2 a 6 sin pausas. Commit al terminar, dejando constancia de límites y conservando cambios ajenos.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-01 | Definición documental | `spec.md`, `plan.md`, `tasks.md`, `validation.md` e índice | Borrador creado con decisiones confirmadas y diseño propuesto; ninguna tarea de código ejecutada |
| 2026-11-02 | T-03-01 | `recetasapp/models.py`, `migrations/0001_initial.py`, `tests/test_modelos.py`; pruebas focalizadas, regresión y control de migraciones | 15 pruebas focalizadas aprobadas; 202 de regresión aprobadas; sin cambios de migración pendientes. Ver validación |
| 2026-11-02 | T-03-02/03 | Servicios e importación; migración 0002 de conteos por fila; pruebas de negocio/importación/concurrencia | Primera colisión de bitácora corregida con reintentos acotados; filas y auditoría atómicas, cupo e idempotencia verificados |
| 2026-11-02 | T-03-04/05 | Comando demo, formularios, vistas, rutas, plantillas, navbar/inicio y pruebas | Descarga/generación CSV/XLSX, 670 pacientes, roles, CSRF, búsquedas y formularios verificados |
| 2026-11-02 | T-03-06, verificación técnica | Suite Django, herramienta HTTP aislada, checks y documentación | Resultados exactos en validation.md; revisión visual/móvil y axe pendientes por acceso al navegador |

## Reanudación

Código y documentación implementados en `fdaza`; verificación técnica completada. Pendiente de T-03-06: revisar las pantallas en escritorio/móvil, teclado/texto ampliado y axe con navegador disponible; luego registrar aceptación real y cerrar el estado si corresponde. No se migró la SQLite local ni se creó rama. El cambio previo del spec 02 se conserva fuera del commit del 03.

## Aceptación del usuario

Reglas y documento completo: Aprobado. Continuación sin pausas: autorizada expresamente. Aceptación funcional del software: pendiente; servicios e interfaz implementados y verificados técnicamente, con límite visual registrado.
