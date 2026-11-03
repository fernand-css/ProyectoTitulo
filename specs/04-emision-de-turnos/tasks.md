# Tareas — 04 / Emisión de turnos

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-02. Estado: código y verificación técnica completados; T-04-04 y T-04-05 conservan pendientes visuales/impresión/accesibilidad. Host del navegador indisponible. Aceptación funcional pendiente.
No ejecutar tareas de código por el hecho de aparecer aquí.

- [x] **T-04-01 — Modelar turnos y numeración diaria.**
  - RF: RF-04-05, RF-04-06, RF-04-10.
  - Depende de: specs 01/02/03 disponibles; revisión y autorización del 04.
  - Archivos: `turnosapp/models.py`, nueva `migrations/0001_initial.py`, nuevos `tests/test_modelos.py` y `test_migraciones.py`; se reutiliza el paquete `tests/` existente.
  - Hecho cuando: contador, turno y vínculos tienen restricciones; base vacía y actualización sintética migran; se conserva recetas/usuarios/auditoría; no hay campo de discapacidad ni datos creados al arrancar.
  - Resultado: 13 pruebas nuevas y regresión completa de 291 aprobadas; check sin problemas y sin migraciones faltantes. Evidencia en `validation.md`; SQLite local sin migrar.
- [x] **T-04-02 — Implementar emisión transaccional, clasificación y recuperación.**
  - RF: RF-04-01 a RF-04-06, RF-04-09, RF-04-10.
  - Depende de: T-04-01.
  - Archivos previstos: nuevo `turnosapp/services.py`, `tests/test_servicios.py`, `test_concurrencia.py`, `test_auditoria.py`; `turnosapp/admin.py` para impedir escritura directa.
  - Hecho cuando: reglas domiciliarias y límites 60/80/81 correctos; un turno reúne todas las recetas elegibles sin consumir cupo; tres escenarios concurrentes mínimos preservan unicidad y auditoría única; rollback íntegro, reintentos acotados y recuperación sin renumeración ni acceso a otro paciente.
  - Resultado: 29 pruebas del módulo (incluidos cinco escenarios concurrentes) y 307 de regresión aprobadas. Auditoría cubierta en `test_servicios.py`; Admin no registra modelos para escritura. Contexto de sesión y CSRF se reservan para las vistas de T-04-03.
- [x] **T-04-03 — Integrar tótem público accesible y contexto temporal.**
  - RF: RF-04-01 a RF-04-04, RF-04-06, RF-04-07, RF-04-09.
  - Depende de: T-04-02.
  - Archivos previstos: nuevos `turnosapp/forms.py`, `templates/turnos/totem.html`, `resultado.html`, `static/css/turnos.css`, `static/js/totem.js`, `tests/test_vistas.py`; existentes `turnosapp/views.py`, `urls.py` y pruebas de navegación afectadas si corresponde.
  - Hecho cuando: teclado numérico con K y teclado físico funcionan; POST con CSRF es obligatorio; mensajes no exponen datos personales; resultado/finalización/expiración/navegación atrás limpian el contexto; `no-store` y ausencia de identificadores en URL verificados; sin selector público de prioridad, urgencia o discapacidad.
  - Resultado: código y 12 pruebas HTTP incorporados; 41 pruebas del módulo aprobadas. JavaScript pasa comprobación sintáctica. Funcionamiento visual/táctil, navegación atrás real y accesibilidad pendientes de revisión en navegador en T-04-05; no se declaran demostrados por estas pruebas.
- [ ] **T-04-04 — Preparar comprobante térmico de 80 mm y reimpresión.**
  - RF: RF-04-07, RF-04-08, RF-04-10.
  - Depende de: T-04-03.
  - Archivos previstos: nuevo `templates/turnos/comprobante.html`; ampliar `resultado.html`, `static/css/turnos.css`, `static/js/totem.js` y pruebas de vistas/integración.
  - Hecho cuando: solo se imprime número/fecha/hora/instrucciones; diseño de 80 mm sin recorte en vista previa; diálogo estándar, cancelación y reimpresión no cambian turno/recetas; no se afirma impresión física desde eventos del navegador. Registrar por separado la prueba con hardware o su pendiente.
  - Implementación lista: fragmento mínimo, CSS de 72 mm útiles para rollo nominal de 80 mm sin altura fija y control de diálogo/reimpresión. 43 pruebas Django del módulo y dos pruebas JavaScript aprobadas. Casilla pendiente de verificar vista previa en navegador; salida física pendiente de equipo. El diálogo se simuló, no se afirma impresión real.
- [ ] **T-04-05 — Validar integración, accesibilidad, carga e impresión y actualizar documentación.**
  - RF: RF-04-01 a RF-04-10.
  - Depende de: código de T-04-04 disponible; incluye cerrar su comprobación visual de impresión.
  - Archivos previstos: nuevos `turnosapp/tests/test_integracion.py`, `tools/verificar_spec_04_http.py`; documentación `README.md`, `docs/estructura.md`, memoria del proyecto y documentos de este spec.
  - Hecho cuando: check, migraciones, suite/regresión y HTTP real pasan en entorno sintético aislado; escenarios concurrentes, p95, escritorio/móvil/teclado y auditoría A/AA tienen resultados registrados; impresión física y prueba con cinco usuarios constan como verificadas o pendientes con su límite explícito. No declarar aceptación completa mientras falten comprobaciones requeridas.
  - Parte técnica completada: `test_integracion.py`, herramienta HTTP real, 322 pruebas Django, dos pruebas Node, check/migraciones, mediciones y documentación. Pendientes: navegador/teclado/móvil/axe y vista previa por host indisponible; impresora física y prueba con cinco usuarios. No marcar completada esta casilla ni Implementado hasta resolver las comprobaciones requeridas o redefinir expresamente su alcance.

## Autorización posterior

2026-11-02: el usuario aprobó el encabezado e invocó `spec-impl`, con instrucción de trabajar sin rama nueva y guardar por un único commit. Aplicar el [acuerdo de ejecución](spec.md#acuerdo-de-ejecución): `fdaza`, sin commits intermedios y conservando cambios ajenos. Las pausas por paso siguen vigentes según la skill; no hay autorización de despliegue ni intervención en equipos del CESFAM.

Confirmación posterior: «si, comienza» autoriza ejecutar T-04-01. Se mantienen las pausas para revisar el diff antes de T-04-02 y siguientes. Ningún commit intermedio.

Confirmación posterior: «si continua el paso 2» autoriza T-04-02; pausa antes de T-04-03.

Confirmación posterior: «si, continua» autoriza T-04-03; pausa antes de T-04-04. Continúan `fdaza` y un único commit al finalizar.

Confirmación posterior: «si, continua» después del paso 3 autoriza T-04-04; pausa antes de T-04-05.

Confirmación posterior: «sip» autoriza T-04-05. Se ejecutan comprobaciones técnicas y se registra el bloqueo del navegador. Un único commit de cierre técnico autorizado por el acuerdo original; sin despliegue ni aceptación funcional implícita.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-02 | Definición documental | Cuatro documentos e índice | Borrador guardado; ninguna tarea de código iniciada. |
| 2026-11-02 | T-04-01 | Modelos, migración inicial y 13 pruebas nuevas | 13 focalizadas y 291 de regresión aprobadas; check y migraciones correctos. |
| 2026-11-02 | T-04-02 | Servicios, Admin y pruebas funcionales/concurrentes | 29 del módulo y 307 de regresión aprobadas; sin migraciones faltantes. |
| 2026-11-02 | T-04-03 | Formulario, vistas, plantillas, CSS/JS y pruebas HTTP | Regresión de 317 aprobada; 41 focalizadas finales tras dos casos adicionales; sintaxis JS correcta; navegador pendiente. |
| 2026-11-02 | T-04-04 | Comprobante, estilos de impresión, control JS y pruebas | 43 del módulo, 321 de regresión y dos JavaScript aprobadas; vista previa/papel pendientes. |
| 2026-11-02 | T-04-05 (parte técnica) | Integración, HTTP real, mediciones y documentación | 322 Django, dos Node, check/migraciones y HTTP aprobados; navegador inaccesible; vista previa/axe/papel/usabilidad pendientes. |

## Reanudación

Última acción: verificación técnica y documentación cerradas. Entrega técnica del 04 en `fdaza`, mediante un único commit; cambios ajenos del 01/02/03 se preservan fuera del commit. Reanudar con host de navegador operativo para revisión visual, teclado, móvil, axe y vista previa; luego validar equipo térmico y usabilidad/aceptación. No repetir implementación ni marcar Implementado por pasar tests.

## Aceptación del usuario

Documento aprobado por el usuario. Aceptación funcional pendiente; no marcar automáticamente después de pasar pruebas.
