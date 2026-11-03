# Validación — 05 / Cola ponderada y llamado

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-02. Estado: **seis pasos técnicos completos; navegador/axe/usabilidad y aceptación pendientes**.
Entorno ejecutado: Windows, Python 3.13.15 del venv, Django 5.2.18 y SQLite temporal, con datos sintéticos. HTTP real sobre WSGI concurrente en loopback, 670 pacientes y cuatro ventanillas. Referencia: cambios del 05 en `fdaza`, único commit solicitado al cierre.

## Matriz inicial de comprobaciones previstas

### Revisión de pendientes — 2026-11-03

Se revisó el rendimiento y se repitió `tools/verificar_spec_05_http.py`: **aprobado**, con 670 pacientes sintéticos, cuatro ventanillas y 100 muestras por operación. p95 de emisión **52,37 ms**, estado privado **42,68 ms** y cierre con entrega **314,02 ms**; las tres operaciones quedan por debajo de 2 s en la carga secuencial local medida. Los tres escenarios HTTP concurrentes y la recuperación del pendiente en un proceso nuevo también pasaron. Servidor cerrado y SQLite temporal eliminada; la base local no se modificó. El intérprete requirió ejecución autorizada fuera del sandbox tras un rechazo de acceso.

**Pendiente de rendimiento:** medir p95 durante carga concurrente sostenida de varias ventanillas y tótem. La herramienta actual mide latencia secuencial y comprueba integridad concurrente por separado; por ello, ni la evidencia anterior ni esta repetición completan ese requisito de RNF-05. También falta la medición de la experiencia en Edge; estos tiempos HTTP no incluyen renderizado del navegador.

Se intentó usar Edge por petición del usuario. `cua.getBrowser({id: "edge"})` devolvió «The browser access host is unavailable» y `cua.listWindows()` devolvió «Computer Use native pipe is unavailable», con error de archivo no encontrado (os error 2). No fue posible acceder al navegador ni realizar acciones en su ventana. Quedan pendientes Edge, axe, teclado, zoom, móvil, usabilidad con cinco personas y aceptación funcional. Se conserva el estado Aprobado.

La tabla conserva la planificación inicial. Sus resultados actuales están en las evidencias de T-05-01 a T-05-06: RF-05-01 a RF-05-12 con comprobaciones automatizadas aprobadas; RNF-02 con pruebas concurrentes y RNF-05 con medición local aprobada. RNF-04 y aceptación siguen pendientes. No interpretar «No ejecutado» de esta tabla histórica como el resultado final.

| RF | Prueba prevista | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-05-01 | Ocupación doble, un Técnico con dos ventanas, preparación repetida y archivo | Ocupación exclusiva, cuatro iniciales sin duplicar, historia conservada | No ejecutado | Pendiente |
| RF-05-02 | Colas abastecidas, vacías, compatibilidad, cambios de pesos y capacidad | P,P,C,G compartido con FIFO; sin bloqueos por huecos ni reinicios por ventanilla | No ejecutado | Pendiente |
| RF-05-03 | Reloj controlado 11:59/12:00/14:59/15:00, varios vencidos y retorno | Advertencia/rescate correctos y desempate estable; retorno reinicia tramo | No ejecutado | Pendiente |
| RF-05-04 | Activar, cerrar, ausentar, emitir y reincorporar con ventanas disponibles | Selección automática compatible sin doble asignación | No ejecutado | Pendiente |
| RF-05-05 | Re-llamado intencional y reenvío, cambios concurrentes | Conserva asignación; evento único por operación; sin descuento | No ejecutado | Pendiente |
| RF-05-06 | Ausencia antes/después del minuto y retorno frente a nueva emisión | Reloj servidor y re-llamado respetados; nunca dos activos del paciente | No ejecutado | Pendiente |
| RF-05-07 | Dos recetas seleccionadas con conflicto en una; 03/05 concurrentes | Cierre atómico, entregas únicas por atención, cupos/historial íntegros | No ejecutado | Pendiente |
| RF-05-08 | Fallo después de cierre confirmado y reinicio de procesador | Entregas conservadas y pendiente recuperable sin doble llamado | No ejecutado | Pendiente |
| RF-05-09 | Pausa/deshabilitar frente a selección; cerrar atención vigente | Bloqueo inmediato de nuevas asignaciones y cierre vigente permitido | No ejecutado | Pendiente |
| RF-05-10 | Medianoche con esperando y llamado; comienzo nuevo día | Cierre histórico de esperando; llamado conservado; activación requerida | No ejecutado | Pendiente |
| RF-05-11 | Tótem con cada estado, reenvío de UUID y reincorporación concurrente | Recuperar activo o nuevo número elegible sin activo; no reactivar cerrados | No ejecutado | Pendiente |
| RF-05-12 | Matriz/CSRF/IDs/UUID ajenos, revocación y fallo de auditoría | Rechazo o rollback correcto, sin información personal en trazas | No ejecutado | Pendiente |
| RNF-02 | ≥3 escenarios con hilos/conexiones reales y carga descrita | Cero duplicados, dobles asignaciones y llamadas a deshabilitadas | No ejecutado | Pendiente |
| RNF-04 | Navegador, móvil, teclado, zoom, axe A/AA y cinco usuarios | Evidencia propia de accesibilidad y límites claros | No ejecutado | Pendiente |
| RNF-05 | ≥100 muestras por operación y carga concurrente con varias ventanillas/tótem | ≤2 s p95 en entorno descrito; recuperación medida aparte | No ejecutado | Pendiente |

## Comandos y resultados reales

### Integración final T-05-06

`python tools/verificar_spec_05_http.py`: **aprobado** con SQLite temporal eliminada al cerrar, 670 pacientes sintéticos y cuatro Técnicos/ventanillas. Inicio/ocupación por HTTP autenticado, CSRF rechazado cuando falta, 100 emisiones, 100 consultas de estado y 100 cierres con entregas comprobadas. Tres escenarios HTTP concurrentes: tres emisiones del mismo paciente (un turno), tres pacientes diferentes (turnos únicos), dos sesiones reenviando el mismo cierre (una entrega). Totales previos a recuperación: 104 turnos y 101 entregas; sin doble descuento.

| Operación HTTP | Muestras secuenciales | p95 |
|---|---:|---:|
| Emisión | 100 | 73,51 ms |
| Estado privado | 100 | 55,18 ms |
| Cierre con entrega | 100 | 177,05 ms |

Las muestras del cierre incluyen selección posterior y redirección al panel. Las tres cargas concurrentes se verifican separadamente; los p95 no acreditan carga de producción ni sincronización con sala. No se afirma NS03 del 06. Se persistió un pendiente sin callback y se lanzó un proceso Python nuevo con `procesar_cola`: recuperó exactamente un llamado, un evento y conservó las 101 entregas. Es reinicio del procesador, sin reinicio de Windows ni prueba de caída abrupta durante commit. Los tests previos cubren fallos transaccionales, ausencia/retorno, jornada y carreras con conexiones independientes.

Primera invocación bloqueada por acceso del sandbox a Python; se reintentó con permisos autorizados. Primera ejecución HTTP detectó un error en la herramienta: enviaba UUID aleatorio en vez del emitido por la sesión del tótem; se corrigió leyendo el campo real del formulario. No se cambió la aplicación. Ejecución posterior íntegra aprobada. Regresión vigente de T-05-05: **411 Django y siete JavaScript aprobadas**, sin cambios posteriores en lógica de aplicación ni migraciones; no se repitió innecesariamente la suite.

Computer Use `cua.getState()` devolvió `apps: []`, `browsers: []`, «Computer Use native pipe is unavailable» y «The browser access host is unavailable» en esta sesión. No hubo navegador, capturas, teclado/zoom/móvil ni axe del 05. Usabilidad con cinco personas y aceptación funcional pendientes. No se marca Implementado. README, estructura y memoria documentan preparación explícita y comando continuo; la base local no se migró ni preparó. No se hicieron commits intermedios ni nueva rama.

| Comando / comprobación de T-05-01 | Resultado real |
|---|---|
| `manage.py makemigrations turnosapp recetasapp --noinput` | Generó recetas 0003 y turnos 0002; no las aplicó a la base local. |
| `manage.py test turnosapp recetasapp.tests.test_modelos --noinput` | Primera ejecución: 59 pruebas, un error en el test histórico de migración del 04 por asumir el último esquema de recetas al retroceder turnos. Corregido el destino histórico a recetas 0002. |
| `manage.py test turnosapp.tests.test_esquema_cola turnosapp.tests.test_migraciones --noinput` | 13 aprobadas en 8,434 s: 12 nuevas de esquema/preparación y la migración anterior del 04 ajustada. |
| `manage.py test turnosapp.tests.test_esquema_cola turnosapp.tests.test_migracion_cola --noinput` | 13 aprobadas en 6,894 s: esquema/preparación y nueva prueba de actualización desde 04. |
| `manage.py makemigrations --check --dry-run` | Sin cambios detectados. |
| `manage.py test --noinput` | **335 pruebas aprobadas en 92,159 s**; check sin problemas; SQLite temporal creada y destruida. |
| `git diff --check -- turnosapp recetasapp specs/05-cola-ponderada-y-llamado` | Sin errores de espacios; advertencias LF/CRLF del entorno. |

El comando de preparación se probó exclusivamente mediante Django sobre SQLite temporal: cuatro ventanillas, tres tipos, configuración 2/1/1, sin automatismo/cuentas/turnos/entregas. Repetición conserva tipos/pesos personalizados y no duplica auditoría; fallo simulado de auditoría revierte toda preparación. Se verifican unicidad de ocupación/operador/llamado, coherencia de estados/asignación/cierre, pesos positivos, eventos y pendientes, vínculo único de entrega y motivos exigidos para no entrega. Las validaciones entre tablas de receta/turno se complementarán en servicios; `clean()` no sustituye reglas transaccionales.

La nueva prueba de migración aplica, revierte y reaplica desde 04 conservando número/UUID/fecha del turno, entrada a cola igual a emisión original, contador de receta y entrega histórica sin asociación inventada. No se crean ventanillas/configuración/eventos al migrar. La migración anterior conserva pruebas de cuentas/grupos/perfiles/auditoría. No se ha probado reversión con estados de atención nuevos ya poblados ni restauración de respaldo.

Un intento de test recibió acceso denegado al intérprete; se reejecutó con permisos fuera del entorno restringido. No se contabilizó como prueba de aplicación ni se evitó el control de permisos. La suite completa finalizó correctamente antes de cerrar este paso.

Comandos previstos al implementar: `manage.py check`, `manage.py makemigrations --check --dry-run`, `manage.py test turnosapp recetasapp --noinput`, suite completa, `tools/verificar_spec_05_http.py` y `git diff --check`. Crear/migrar/preparar datos únicamente en entorno sintético aislado para la validación.

## Regresión de la base

### Evidencia del paso 2

Primera ejecución focalizada de 17 pruebas: error de importación `uuid` en el nuevo disparador de emisión; se corrigió la importación, sin cambiar las reglas. Ejecución posterior de `test_cola test_concurrencia_cola`: **17 aprobadas en 0,804 s**. Al agregar prueba de apertura de otra ventanilla, una ejecución de 75 pruebas del módulo tuvo un fallo por dejar aserciones del caso de cola vacía dentro del caso nuevo; se corrigió la separación del test. La regresión completa posterior (`manage.py test --noinput`) pasó con **353 pruebas en 85,317 s**, con check sin problemas y SQLite temporal creada/destruida. Se agregaron 18 casos respecto de las 335 anteriores.

Los casos verifican P,P,C,G y FIFO, huecos/compatibilidad, prioridad por antigüedad a 15 minutos sin consumir cursor, umbrales 12/15, entrada actual de retorno simulado, cambio de configuración, pesos grandes sin lista proporcional, apertura de otra ventanilla sin reiniciar ciclo, activación de otra jornada, operador revocado, repetición idempotente y error no transitorio sin reintento. El caso de emisión ejecuta el callback posterior al commit del flujo y comprueba llamado automático, recuperación del activo y contador de receta intacto.

Tres escenarios con barreras y conexiones independientes, tres hilos cada uno: mismo pendiente; distintos pendientes disputando un turno; tres ventanillas/pendientes comparten cursor. Se comprueban un llamado/evento en los dos primeros, tres asignaciones únicas con categorías P,P,C en el tercero y ausencia de pendientes duplicados sin procesar.

Un fallo simulado de auditoría revierte el llamado/evento y deja el disparador pendiente. `procesar_cola` en otra invocación de servicio lo recupera sin duplicar. Se demuestra persistencia y reprocesamiento por comando en la misma ejecución de tests, no reinicio real de proceso/SO; esa comprobación integral se mantiene para T-05-06. El log fijo «Selección automática pendiente de recuperar» corresponde a ese fallo simulado y no contiene detalles privados.

No hay cierre/ausencia/retorno/pausa operativos ni pantalla privada aún. Los datos de ocupación usados en estas pruebas se preparan directamente como fixtures; los servicios correspondientes son T-05-03. `makemigrations --check --dry-run`: sin cambios detectados; T-05-02 no agrega esquema.

Se añadieron 13 pruebas (12 de esquema/preparación y una de migración del 05). Suite final de **335 aprobadas**, frente a 322 previas, incluida la prueba histórica de actualización del 04 ajustada a la nueva dependencia. El HTTP real y rendimiento históricos del 04 no validan el automatismo del 05. El 03 conserva sus pruebas y contratos; la lógica compartida de entregas aún no se refactorizó.

## Revisión visual si aplica

### Evidencia de T-05-05

Se incorporan `panel.py`, `vistas_operacion.py`, formularios, rutas privadas, diez plantillas de atención, `cola.css`, `cola.js` y accesos desde inicio/navbar. El Técnico ocupa e inicia su ventanilla, pausa, re-llama, marca ausente y confirma entregas; Q.F. supervisa y configura tipos, habilitación y pesos. La cola muestra número/tipo/espera con umbrales y paginación, sin nombres en sus filas. La atención propia e historial autorizado incluyen identificación privada. Se muestran pendientes recuperables, ausencia de configuración y falta de cobertura; se aclara que no hay avisos públicos de sala todavía. Ningún modelo de turnos se registra para escritura directa en Admin.

`manage.py test coreapp.tests.test_plantillas --noinput`: **17 aprobadas en 0,415 s**. Durante el desarrollo se corrigió el filtro de espera para usar el filtro existente `minutos`. `manage.py test turnosapp.tests.test_panel --noinput`: **15 aprobadas en 1,791 s**. Casos: GET sin escrituras de dominio y no-store; roles/revocación/anónimo; Q.F. sin entrega; Técnico sin configuración; puesto ajeno; GET 405 en acciones; CSRF exigido en siete destinos; doble POST de cierre con payload conservado; errores sin descuentos y UUID preservado; fallo del próximo llamado con entrega conservada y recuperación visible; tipos/pesos inválidos; IDs únicos, referencias HTML resueltas y un main; historial con etiquetas y recetas.

`node --test turnosapp/tests/cola.test.cjs turnosapp/tests/impresion.test.cjs`: **siete aprobadas**, cinco nuevas de consulta y dos de impresión existentes. Se comprueba GET sin caché, pausa de actualización/refresco manual, conservación del formulario con foco, eliminación del fragmento privado ante sesión revocada y recuperación de fallo de consulta. Son comprobaciones del contrato JavaScript en Node, sin motor de navegador ni medición visual. `makemigrations --check --dry-run`: sin cambios detectados.

La consulta periódica solo lee el estado; el proceso durable sigue llamando aunque la pestaña se cierre mientras la ventanilla permanezca activa. La interfaz avisa que debe pausarse al abandonar el puesto. Los errores mantienen el UUID del formulario para recuperar la operación sin repetir entregas. No se migró la base local. La comprobación en navegador, axe, teclado, zoom y móvil se reserva a T-05-06; los tests de estructura no acreditan accesibilidad integral.

Regresión completa final `manage.py test --noinput`: **411 pruebas aprobadas en 133,295 s**, check sin problemas y SQLite temporal creada/destruida. Son 15 nuevas respecto de las 396 del paso anterior. `git diff --check`: sin errores de espacios; solo advertencias de normalización LF/CRLF. Rama verificada `fdaza`, sin commit intermedio.

### Evidencia de T-05-04

Primera ejecución `test_cierre recetasapp.tests.test_servicios`: **20 aprobadas en 1,930 s**, con 12 casos nuevos de cierre y ocho del servicio anterior de recetas. Ejecución ampliada `test_cierre test_concurrencia_cierre recetasapp.tests.test_concurrencia`: **24 aprobadas en 2,892 s**, con 16 casos funcionales nuevos, cuatro carreras nuevas y cuatro carreras existentes de recetas. Suite completa `manage.py test --noinput`: **396 aprobadas en 131,798 s**, con check sin problemas y SQLite temporal creada/destruida. Son 20 nuevas respecto de las 376 anteriores.

Casos: cierre completo/reenvío con próximo turno llamado; parcial y motivos; cero entregas con motivo; agotamiento de una seleccionada que revierte las demás; reutilización de entrega del 03 preservando actor/fecha; fallo del cierre sin borrar entrega previa; fallo de próximo llamado con cierre/entregas conservados y recuperación del pendiente; fallo de auditoría en cierre/segunda entrega; UUID con otra selección y receta/rol ajenos; formulario 03 anterior al cierre con contexto firmado; token alterado; detección de cambio de contador cuando el formulario independiente precedía a la llamada; alias de operación recuperada que no puede aplicarse a otra receta. Una entrega ya confirmada no se convierte en no entrega por la selección del cierre.

Cuatro carreras con barrera y conexiones reales: tres reenvíos del mismo cierre (3 hilos), dos UUID para una atención (2), 03 frente a 05 con el vínculo de atención explícito (2) y tres confirmaciones del último cupo en 03 seguidas del cierre (3). Siempre quedan dos entregas y dos detalles para las dos recetas del turno, un cierre y contadores iguales a uno; no se adjudica dos veces la misma entrega. La prueba 03/05 conserva contexto explícito, igual que el formulario firmado real; no se presume que una entrega independiente posterior pertenezca a un turno antiguo.

`manage.py check`: sin problemas. `makemigrations --check --dry-run`: sin cambios detectados. No se migró la base local. Los formularios del 03 se prueban con el cliente HTTP de Django; no se realizó revisión visual ni existe aún pantalla de cierre del 05.

### Evidencia de T-05-03

`manage.py test turnosapp.tests.test_atencion --noinput`: **17 pruebas aprobadas en 0,938 s**. Ejecución ampliada `test_atencion test_concurrencia_atencion`: **23 aprobadas en 2,261 s**. Se cubren ocupación exclusiva/idempotente, liberación con historial, inicio automático, pausa conservando atención, impedimento de liberar con llamado, ausencia a 59/60 segundos, re-llamado que reinicia plazo, reenvío sin afectar siguiente, deshabilitación confirmada y habilitación sin activar, matriz/revocación, UUID/payload ajenos, rollback de auditoría, retorno al final con número conservado, retorno bloqueado por otro activo, configuración por Q.F. y cierre de jornada/llamado de otra fecha/UUID terminal.

Seis escenarios concurrentes con barreras y conexiones independientes: dos operadores por una ventanilla (2 hilos), un operador por dos ventanillas (2), pausa frente a selección (2), deshabilitación frente a selección (2), emisión frente a reincorporación (2) y tres reenvíos de re-llamado (3). Un llamado confirmado antes de pausa/deshabilitación puede permanecer, pero no se agrega otro después; retorno/emisión dejan un único activo. Las pruebas usan las acciones reales del servicio, no solo cambios directos de flags. Los cierres con entregas se reservan al paso 4.

`makemigrations --check --dry-run`: sin cambios detectados. `manage.py test --noinput`: **376 pruebas aprobadas en 126,898 s**, con check sin problemas y SQLite temporal creada/destruida. Se agregaron 23 respecto de las 353 anteriores. Después se reforzó un caso funcional para que emita mediante el servicio real tras ausencia, en lugar de preparar el segundo turno directamente; `test_atencion` final: **17 aprobadas en 1,303 s**. No hubo cambio posterior de implementación. No se migró la base local ni se habilitaron endpoints privados de operación todavía.

Panel del Técnico/Q.F., cierre y motivos, cola con tiempos, estados y recuperación incorporados en T-05-05 con pruebas automatizadas. Pendiente probar teclado, zoom y móvil con identidad existente. El 04 registró host de navegador y pipe nativo no disponibles; comprobar disponibilidad en T-05-06 y registrar el resultado actual, sin asumir bloqueo ni revisión realizada.

La pantalla pública y voz pertenecen al 06: no habrá evidencia de NS03/NS07 completa aquí. La auditoría automática no sustituye los cinco usuarios ni aceptación funcional.

## Límites y fallos

El esquema, preparación, planificador, operación/jornada, cierre/entregas y panel cuentan con evidencia automatizada, HTTP real y recuperación en proceso nuevo. Los formularios del 03/05 no tienen revisión en navegador del 05. No se afirma aceptación integral. Sin tecnología de WebSocket/voz elegida. Preparación de medicamentos, pendientes de retiro y estimación de HU-17/18 fuera de alcance. La ponderación no es una política validada por el CESFAM.

## Aplicación y reversión

Se crearon dos migraciones y se ejecutaron solo en SQLite temporal, incluida prueba de retroceso/reaplicación con datos previos. La preparación operativa se ejecutó solo en tests. No se modificó la base local, rama ni commits. Restauración de respaldo y aplicación real pendientes; retroceder esquema con datos nuevos de atención no se presenta como operación sin pérdida.

## Aceptación funcional

Pendiente. El usuario marcó Aprobado, invocó `spec-impl 05` y confirmó «si, continua» para T-05-01. No marcar Implementado ni aceptación completa por las pruebas del esquema.
