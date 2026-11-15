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

### Enmienda del 2026-11-15 (implementada el 2026-11-15; navegador, visor de PDF real y aceptación pendientes)

- [x] **T-04-06 — Esquema: RUT en el turno, paciente opcional, letras y series por letra.**
  - RF: RF-04-04, RF-04-05, RF-04-06.
  - Depende de: ninguna.
  - Archivos previstos: `turnosapp/models.py`, migraciones de esquema y de datos, `turnosapp/tests/test_modelos.py`, `test_migraciones.py`.
  - Hecho cuando: las restricciones nuevas rechazan duplicados por (fecha, letra, número) y por (RUT, fecha) activos; la migración rellena `rut` y `letra` sin renumerar; `makemigrations --check` limpio.
  - Resultado: `Turno.rut`, `Turno.letra`, `paciente` opcional, `urgencia`, `Turno.codigo` y el contador por (fecha, letra). Las migraciones son tres y no una: `0004` (columnas opcionales), `0005` (`RunPython` reversible) y `0006` (`NOT NULL` y restricciones), siguiendo la regla de los tres pasos. Se suma la restricción `turno_letra_coherente` (tipo ↔ letra), y `turno_rut_no_vacio` y el índice `turno_rut_fecha_idx`. `TIPOS_VENTANILLA` excluye la urgencia de los tipos de ventanilla. `emitir_turno` solo rellena `rut`/`letra` y usa el contador de su letra; sus reglas de negocio no cambian (eso es T-04-07). Compatibilidad: la selección automática y la reincorporación comparan por `rut`; las vistas privadas usan `Turno.codigo` y toleran `paciente=None`.
- [x] **T-04-07 — Servicio: tótem abierto, despacho, clasificación por letra, recuperación del día y renovación.**
  - RF: RF-04-02, RF-04-03, RF-04-04, RF-04-06, RF-04-11.
  - Depende de: T-04-06.
  - Archivos previstos: `turnosapp/services.py`, `turnosapp/tests/test_servicios.py`, `test_concurrencia.py`.
  - Hecho cuando: los criterios de la enmienda pasan, incluidos los tres escenarios concurrentes con `TransactionTestCase` e hilos.
  - Resultado: `emitir_turno` acepta todo RUT válido (sin padrón → G sin recetas, sin crear paciente); `clasificar_atencion` da P a postrados y a 60 o más (incluye 80+), C a crónicos menores de 60 y G al resto, sin llamar a `requiere_despacho_en`; vincula las elegibles fuera de despacho abierto y, si todas están en despacho, rechaza sin consumir número. `_anterior` busca por `rut` y solo la fecha de hoy, también «llamado»; una operación de otro RUT, cerrada o de otro día da el rechazo neutro. Un solo código (`CODIGO_RECHAZO = "rechazo"`) y texto (`MENSAJE_NEUTRO`), también en las vistas para «RUT distinto en la misma sesión» y «operación vencida»; «ocupado» (reintentos agotados) conserva su texto. `ResultadoEmision.renovacion` usa `requiere_renovacion`: receta vencida o agotada **que no tiene una renovación** (`renovaciones__isnull=True`), para no pedir renovar lo ya renovado. `atencion.reincorporar` deja de clasificar (sin bloqueo por edad). La interfaz del aviso y del PDF queda para T-04-09.
- [x] **T-04-08 — Límite de intentos por equipo.**
  - RF: RF-04-12.
  - Depende de: T-04-06.
  - Archivos previstos: `turnosapp/models.py` (`IntentoTotem`), `turnosapp/views.py`, pruebas de vistas y concurrencia.
  - Hecho cuando: la undécima solicitud del minuto queda en pausa con mensaje neutro y auditoría sin RUT, también con hilos concurrentes.
  - Resultado: `IntentoTotem` (migración `0007_intento_totem`) con clave = huella `salted_hmac` de la IP (`REMOTE_ADDR`) o de la sesión, ventana por minuto y restricción única; `services.registrar_intento_totem` cuenta con UPDATE condicional (`cantidad__lt=10`), reintenta la creación ante `IntegrityError`, limpia ventanas de más de 10 min y audita una vez por clave y ventana (`totem.limite_superado`, sin RUT). `views.totem` lo evalúa antes de validar la operación y responde con el mensaje neutro. `turnosapp/tests/test_limite.py`: 8 pruebas, dos con `TransactionTestCase` e hilos (servicio y vista).
- [x] **T-04-09 — Interfaz: sin «Nueva atención», vuelta automática y comprobante en PDF a pantalla completa.**
  - RF: RF-04-07, RF-04-08, RF-04-11.
  - Depende de: T-04-07.
  - Archivos previstos: `requirements.txt` (ReportLab), `turnosapp/comprobante.py` (nuevo, generación del PDF), `turnosapp/views.py`, `urls.py`, `templates/turnos/totem.html`, `resultado.html`; se retiran `comprobante.html` y los estilos de impresión; `static/js/totem.js`, `static/css/turnos.css`, fuentes en `static/`, pruebas de vistas y `.cjs`.
  - Hecho cuando: no queda el botón; un rechazo deja lista la entrada para otro RUT; el PDF vertical solo se sirve a la sesión de la operación, con `no-store` y sin datos personales; el aviso de renovación aparece estático cuando corresponde; la franja de 30 s y «Necesito más tiempo» funciona; probado en el visor de PDF del navegador del tótem.
  - Resultado: sin formulario «Nueva atención» en `totem.html` y `resultado.html` (queda un formulario oculto para la limpieza automática); `views._rechazo` rota la operación tras cada rechazo o error. `turnosapp/comprobante.py` dibuja el PDF vertical de 1080×1920 pt con ReportLab 4.5.1 (Helvetica, porque las fuentes del proyecto son woff2) y la vista `turnosapp:comprobante_pdf` lo sirve solo a la sesión con la operación vigente, `inline`, `no-store` y `nosniff`, sin guardar archivos. `resultado.html` lo incrusta a pantalla completa con `<object>`, texto alternativo y una región `status` con el código; franja HTML fija con la cuenta y «Necesito más tiempo». Se retiran `templates/turnos/comprobante.html`, los estilos de impresión y `impresion.test.cjs`; nuevo `totem.test.cjs` (5). `turnosapp/tests/test_comprobante_pdf.py`: 6 pruebas (PDF válido, sin RUT ni nombre, aviso de renovación, rechazo sin sesión o tras finalizar, `no-store`). **Pendiente:** probarlo en el visor de PDF del navegador real del tótem.
- [x] **T-04-10 — Validar la enmienda y actualizar documentación.** *(parte técnica; navegador, visor de PDF real, axe, usabilidad y aceptación pendientes)*
  - RF: RF-04-02 a RF-04-07, RF-04-11, RF-04-12.
  - Depende de: T-04-06 a T-04-09 y las enmiendas de los specs 05 y 06.
  - Hecho cuando: regresión completa, HTTP aislado y resultados reales en `validation.md`; navegador, axe y aceptación constan como verificados o pendientes.
  - Resultado: ver la fila del 2026-11-15 en «Ejecución» y la sección de la enmienda en `validation.md`. `tools/verificar_spec_04_http.py` se adaptó (postrado recibe P, 106 turnos, comprobación del límite) y las de los specs 05, 07 y 08 levantan el límite solo en su base aislada.

## Autorización posterior

2026-11-15: la usuaria aprobó la enmienda del documento («aplica los cambios a la spec 04», «si, continua con todos los cambios»). Esa aprobación es documental; T-04-06 a T-04-10 no están autorizadas para implementación.

2026-11-15 (posterior): la usuaria cambió el estado a Aprobado («cambialo a aprobado») y autorizó implementar los pasos 1 a 5 seguidos («si, comienza con el paso 1 y hasta el 5 continua sin parar»), en `fdaza` y sin commit.

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
| 2026-11-15 | Enmienda documental | `spec.md`, `plan.md`, `tasks.md`, `validation.md` | Tótem abierto, letras, mensaje neutro y límite de intentos; T-04-06 a T-04-10 propuestas; sin código. |
| 2026-11-15 | T-04-06 | `turnosapp/models.py`, migraciones `0004`–`0006`, `services.py`, marcas de `cola.py`/`atencion.py`, `TIPOS_VENTANILLA` en `forms.py`/`panel.py`/`preparar_ventanillas`; pruebas de modelos, migraciones y las que crean turnos a mano | `makemigrations --check --dry-run`: «No changes detected»; `check`: sin problemas. `test turnosapp.tests.test_modelos turnosapp.tests.test_migraciones turnosapp.tests.test_migracion_cola`: 19 OK. `test turnosapp recetasapp entregasapp --noinput`: 619 OK. `test --noinput` (suite completa): 876 OK. PostgreSQL de pruebas; la base local no se migró. **Corrección tras revisión (2026-11-15):** `cola._candidato` excluye por `rut` (no por `paciente_id`, que con NULL detenía la selección); `atencion` reincorpora comprobando otro activo por `rut` y `clasificar_atencion(None)` devuelve general; `ResultadoEmision` suma `letra`/`codigo`, y el tótem, comprobante, panel (`_estado.html`, `panel.py`), historial, finalizar y Preparación muestran `Turno.codigo` y «No registrado en el padrón» sin enlace a ficha; nueva `turnosapp/tests/test_sin_padron.py` (6). `check`: sin problemas; `makemigrations --check --dry-run`: «No changes detected»; 6 módulos focalizados: 89 OK. `test turnosapp recetasapp entregasapp --noinput`: 625, 623 OK, 1 error preexistente `test_sala_servidor` (WinError 32 al borrar SQLite temporal) y 1 fallo intermitente ajeno `entregasapp.tests.test_concurrencia_ruta.test_2` (orden de ruta del 09; aislado: 2 de 3 corridas OK). |
| 2026-11-15 | T-04-07 | `turnosapp/services.py`, `views.py` (mensaje neutro), `atencion.py`; pruebas `test_servicios.py`, `test_concurrencia.py` (3 escenarios nuevos: mismo RUT fuera del padrón con 5 UUID; 8 emisiones P/G/C en paralelo; despacho abierto mezclado con 4 emisiones), `test_vistas.py` (2 nuevas), `test_atencion.py`; `entregasapp/tests/test_elegibilidad.py`, `test_doble_via.py`, `test_concurrencia.py`; `tools/verificar_spec_08_http.py` (texto del tótem) | `check`: sin problemas; `makemigrations --check --dry-run`: «No changes detected». `test turnosapp.tests.test_servicios`: 17 OK; `test turnosapp.tests.test_concurrencia`: 8 OK; `test turnosapp.tests.test_vistas`: 16 OK. `test turnosapp recetasapp entregasapp --noinput`: 636 OK (200,4 s), sin el WinError 32 de `test_sala_servidor` en esta corrida. Pendiente: `tools/verificar_spec_04_http.py` aún espera 400 en «rechazo_domicilio» (postrados) y no se ejecutó (T-04-10). |
| 2026-11-15 | T-04-08 y T-04-09 | `IntentoTotem`, migración `0007`, `services.registrar_intento_totem`, `views.py`, `urls.py`, `comprobante.py`, `totem.html`, `resultado.html`, `totem.js`, `turnos.css`, `requirements.txt` (ReportLab); pruebas `test_limite.py` (8), `test_comprobante_pdf.py` (6), `totem.test.cjs` (5) | `check`: sin problemas; `makemigrations --check --dry-run`: «No changes detected»; `node --test turnosapp/tests/*.test.cjs`: 66 OK; `test turnosapp --noinput`: 237 OK (106,1 s). |
| 2026-11-15 | T-04-10 (parte técnica) | Suite completa, JavaScript, HTTP aislado y documentación | `test --noinput`: **908 OK** (324,6 s, PostgreSQL de pruebas; la base local no se migró). `node --test recetasapp/tests/*.test.cjs`: 7 OK. `git diff --check`: sin errores. `tools/verificar_spec_04_http.py`: aprobado, SQLite temporal, 670 pacientes sintéticos, 36 migraciones, 106 turnos, límite (10 aceptadas, la undécima con mensaje neutro); p95 emisión 72,08 ms, recuperación 45,99 ms, postrado 41,46 ms (100 muestras cada uno, secuencial). |

## Reanudación

Última acción: verificación técnica y documentación cerradas. Entrega técnica del 04 en `fdaza`, mediante un único commit; cambios ajenos del 01/02/03 se preservan fuera del commit. Reanudar con host de navegador operativo para revisión visual, teclado, móvil, axe y vista previa; luego validar equipo térmico y usabilidad/aceptación. No repetir implementación ni marcar Implementado por pasar tests.

## Aceptación del usuario

Documento aprobado por el usuario. Aceptación funcional pendiente; no marcar automáticamente después de pasar pruebas.
