# Validación — 04 / Emisión de turnos

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-02. Estado: **código y verificación técnica final completados; navegador, vista previa, accesibilidad integral, papel y aceptación pendientes**.
Entorno ejecutado: Windows, Python 3.13.15 del venv, Django 5.2.18, ejecutor Django y SQLite temporal creada/destruida por tests, con pacientes sintéticos. El padrón de 670 y las mediciones de emisión se reservan para integración.
Referencia de código: commit de cierre técnico del 04 en `fdaza`, que incluye este documento; sin commits intermedios. La matriz siguiente es planificación funcional; la evidencia real se detalla por separado.

## Matriz de comprobaciones previstas

La matriz conserva el plan de aceptación integral, no certifica comprobaciones visuales ausentes. La evidencia real de servicios/HTTP/esquema/impresión simulada se detalla debajo. RF-04-01/07/08 y RNF-04 siguen parcialmente pendientes de navegador; RNF-05 tiene medición local secuencial; la parte de base/servicios y privacidad/CSRF de RF-04-02 a RF-04-06 y RF-04-09/10 está cubierta por pruebas y HTTP.

| RF | Prueba / pasos / comando previsto | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-04-01 | RUT con/sin puntos, K/k, vacío y DV erróneo; teclado físico/visible | Normalización y error accesible; no RUT en URL | No ejecutado | Pendiente |
| RF-04-02 | No registrado, postrado, edades 80/81 | Orientación correcta; bloqueo sin despacho ficticio | No ejecutado | Pendiente |
| RF-04-03 | Varias recetas elegibles y bloqueadas; ninguna elegible | Una selección de todas las utilizables o rechazo sin emitir | No ejecutado | Pendiente |
| RF-04-04 | Edades 59/60/80/81; crónico y postrado; formulario manipulado | Clasificación y precedencia correctas; sin discapacidad/urgencia automática | No ejecutado | Pendiente |
| RF-04-05 | Primera emisión, tipos distintos, reinicio de aplicación y cambio de fecha controlado | Serie diaria compartida, persistente y única | No ejecutado | Pendiente |
| RF-04-06 | Hilos: mismo UUID/paciente, distintos UUID/mismo paciente y distintos pacientes | Cero duplicados y un activo por paciente/día | No ejecutado | Pendiente |
| RF-04-06/09 | Respuesta perdida, UUID para otro paciente, bloqueo de SQLite y auditoría fallida | Recuperación segura, error recuperable o rollback íntegro | No ejecutado | Pendiente |
| RF-04-07 | Resultado, inactividad, finalizar y navegación atrás | Limpieza; sin identidad ni antecedentes en resultado público | No ejecutado | Pendiente |
| RF-04-08 | Vista previa/PDF de 80 mm, cancelar y reimprimir | Mismo número; solo contenido mínimo; sin recortes de diseño | No ejecutado | Pendiente |
| RF-04-08 | Impresora térmica instalada; imprimir en papel y reimprimir | Número legible, márgenes adecuados y mismo turno | Sin equipo definido ni prueba física | Pendiente |
| RF-04-09 | HTTP real con/sin CSRF; manipular categoría/recetas; acceso a resultado ajeno y Admin | Rechazo sin cambios indebidos ni exposición | No ejecutado | Pendiente |
| RF-04-10 | Emitir/recuperar frente a entregas/importación; revisar contadores e historial | Sin consumo/reserva por emisión; historial consistente | No ejecutado | Pendiente |
| RNF-02 | Tres escenarios concurrentes mínimos con `TransactionTestCase` e hilos | Restricciones y eventos consistentes; errores recuperables identificados | No ejecutado | Pendiente |
| RNF-04 | Escritorio/móvil, teclado, zoom y auditoría A/AA; prueba con cinco usuarios | Accesibilidad verificada con evidencia y límites | No ejecutado | Pendiente |
| RNF-05 | ≥ 100 solicitudes por escenario; padrón sintético de 670; registrar equipo/carga/p95 | p95 ≤ 2 s de emisión/recuperación; impresión medida aparte | No ejecutado | Pendiente |

## Comandos y resultados reales

### Cierre técnico del paso 5

| Comprobación final | Resultado real |
|---|---|
| `.\venv\Scripts\python.exe manage.py test --noinput` | **322 pruebas aprobadas en 70,373 s**; check sin problemas; SQLite temporal creada/destruida. |
| `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run` | Sin cambios detectados. |
| `node --test turnosapp/tests/impresion.test.cjs` | Dos pruebas aprobadas; diálogo simulado, no impresora real. |
| `.\venv\Scripts\python.exe tools/verificar_spec_04_http.py` | HTTP real aprobado con 670 pacientes sintéticos y 24 migraciones, 105 turnos únicos y 105 eventos de emisión; cero entregas consumidas. Servidor cerrado y base temporal eliminada. |
| `git diff --check` | Sin errores de espacios; advertencias LF/CRLF del entorno. |
| Computer Use: inventario del entorno | `The browser access host is unavailable` y `Computer Use native pipe is unavailable`. No se ejecutó revisión visual ni auditoría de navegador. |

La herramienta HTTP usa Windows 11 (10.0.26200), Python 3.13.15, Django 5.2.18, SQLite en archivo temporal y servidor WSGI de prueba en loopback con hilos. Primer intento falló por configuración de QA: DEBUG falso activaba cookies HTTPS contra HTTP local. Se corrigió únicamente el entorno del proceso de QA a DEBUG verdadero, igual que la herramienta del 03; no se cambió `settings.py`, la base local ni la configuración de producción. El intento inicial no se contó como éxito. La posterior ejecución completó y limpió su entorno.

Recorre emisión, reenvío, CSRF real ausente, operación de otra sesión, ampliación/finalización, rechazo de contexto anterior, estáticos, privacidad del HTML y concurrencia HTTP con tres solicitudes para un paciente y tres pacientes distintos. El caso de CSRF ausente produce el aviso esperado del framework; no contiene RUT ni datos clínicos.

| Escenario HTTP POST | Muestras | Solicitudes simultáneas | p95 |
|---|---|---|---|
| Nueva emisión | 100 | 1 | 44,46 ms |
| Recuperación | 100 | 1 | 35,34 ms |
| Rechazo domiciliario | 100 | 1 | 31,67 ms |

Percentil calculado por rango más próximo (`ceil(0,95 × N)`) sobre tiempo completo de cada POST y lectura de respuesta. GET de preparación y tiempo humano de impresión se excluyen. Cumple ≤ 2 s en el entorno local medido; no demuestra capacidad sostenida de producción ni p95 bajo carga concurrente. Las pruebas de concurrencia son comprobaciones adicionales de integridad.

`test_integracion.py` agrega comprobación de identificadores únicos, un único `main`, etiquetas y referencias `aria-describedby` existentes, errores con `aria-invalid`, `no-store` y resultado sin identidad. No sustituye axe ni revisión de teclado real. El service worker no tiene manejador `fetch` ni caché de datos del tótem.

| Comando | Resultado real de T-04-01 |
|---|---|
| `.\venv\Scripts\python.exe manage.py makemigrations turnosapp` | Creó `0001_initial.py` con tres modelos, índice y restricciones; sin aplicar a la base local. |
| `.\venv\Scripts\python.exe manage.py test turnosapp --noinput` | Primera ejecución: 12 pruebas de modelos aprobadas y un error en el test de migración por pasar un destino `None` a `project_state`. Corregido el test para excluir ese destino al construir el estado histórico. |
| `.\venv\Scripts\python.exe manage.py test turnosapp --noinput` | Ejecución corregida: **13 pruebas aprobadas en 1,059 s**, base temporal creada y destruida. |
| `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run` | Sin cambios detectados. |
| `.\venv\Scripts\python.exe manage.py check` | Sin problemas. |
| `.\venv\Scripts\python.exe manage.py test --noinput` | **291 pruebas aprobadas en 85,800 s**; check sin problemas; base temporal creada y destruida. |

Las pruebas verifican unicidad del contador diario, número por fecha compartido entre categorías, turno activo por paciente/fecha y UUID global; rechazos de número no positivo y tipo/estado no admitidos incluso mediante UPDATE; vínculos únicos y validación de pertenencia; protección de historial; ausencia de consumo de entregas y de datos personales duplicados. La prueba de migración aplica, revierte y reaplica el esquema sobre pacientes/recetas/entregas sintéticos previos, conservando cuentas, hashes, grupos, perfiles y auditoría; no crea turnos al migrar.

Dos comandos de comprobación recibieron acceso denegado al intérprete bajo el entorno restringido; se reejecutaron fuera de ese entorno con la aprobación correspondiente y finalizaron correctamente. No se interpretó ese fallo como error del proyecto. No hay pruebas de emisión ni concurrencia todavía: corresponden a T-04-02.

## Regresión de la base

### Evidencia del paso 2

`manage.py test turnosapp --noinput`: **29 pruebas aprobadas en 1,402 s**, con SQLite temporal creada/destruida. Son 13 del esquema, 11 funcionales y 5 concurrentes. El paso 2 agrega 16 casos. Una ejecución previa detectó agotamiento de reintentos en tres solicitudes para el mismo paciente con UUID distintos; se ajustó la espera a exponencial limitada con variación aleatoria y 12 intentos. No se alteraron las restricciones para hacer pasar la prueba.

Los cinco escenarios concurrentes usan barrera y conexiones independientes: mismo UUID con 3 emisores; distintos UUID para un paciente con 3 emisores; 3 pacientes disputando serie; emisión frente a entrega; emisión frente a importación. En los tres primeros todos obtuvieron resultado válido y la base conservó números únicos, contador igual a emisiones, un turno por paciente/día, un vínculo por turno del caso y un evento por emisión. En los dos últimos quedaron una sola receta y contadores de entregas correctos, sin consumo por emisión. Cada escenario se ejecutó una vez en la suite final focalizada; no constituye prueba de carga sostenida ni medición de p95.

Las pruebas funcionales cubren selección colectiva, recuperación sin cambiar selección tras agregar/agotar recetas, límites de edad y postrado, RUT normalizado, UUID inválido/ajeno, rechazo sin consumir correlativo, nuevo día, ausencia de modelos editables en Admin, auditoría con actor nulo y rollback, error no transitorio sin reintento y agotamiento recuperable de los 12 intentos. El resultado del servicio contiene únicamente número, fecha, instante y señal de recuperación. No se ha implementado ni validado aún el contexto de sesión/CSRF de las vistas del tótem.

`manage.py makemigrations --check --dry-run`: sin cambios detectados. El primer intento tuvo acceso denegado al intérprete y se repitió fuera del entorno restringido. No se aplicaron migraciones a la base local.

`manage.py test --noinput`: **307 pruebas aprobadas en 90,855 s**; check sin problemas; SQLite temporal creada y destruida. No se cambiaron pruebas de módulos anteriores. `git diff --check -- turnosapp specs/README.md`: sin errores de espacios. PostgreSQL no se ejecutó; el manejo de sus colisiones por nombre de restricción permanece sin prueba sobre ese motor.

13 pruebas nuevas focalizadas aprobadas y suite completa de **291 pruebas aprobadas**, frente a 278 pruebas previas. Incluye las migraciones y los módulos anteriores sin modificar sus pruebas. Herramienta HTTP y validación funcional integral pendientes; este resultado verifica el paso de esquema, no el funcionamiento completo del 04.

## Revisión visual si aplica

### Evidencia automatizada del paso 4

`manage.py test turnosapp --noinput`: **43 pruebas aprobadas en 1,678 s**, con dos nuevos casos para comprobante. Comparan contenido idéntico al recuperar el mismo turno, verifican número y ausencia de identidad, categorías, recetas, formularios y CSRF en el fragmento imprimible; no hay nuevo turno, evento de emisión ni entrega. La entrada y errores no incluyen comprobante.

`node --test turnosapp/tests/impresion.test.cjs`: **dos pruebas aprobadas** con DOM y diálogo simulados. Se ejecuta el JavaScript real del tótem: cancelar/reimprimir abre dos diálogos, solo llama al endpoint de ampliación y no limpia durante el diálogo; al cerrarlo permite comprobar la sesión antes de limpiar; contexto vencido impide imprimir y limpia una sola vez. No sustituyen ejecución real en navegador, CSS de impresión ni salida de papel. `node --check static/js/totem.js` y diff sin errores.

CSS preparado para área útil de 72 mm y margen de 4 mm sobre papel nominal de 80 mm, sin altura fija. Pendientes vista previa sin recortes, revisión móvil/teclado y prueba con térmica. No se creó PDF ni se afirmó aceptación de hardware en este paso.

Regresión del paso 4: `manage.py test --noinput`, **321 pruebas aprobadas en 74,688 s**, con check sin problemas y SQLite temporal creada/destruida. El ajuste final de reanudación del temporizador se verificó además con las dos pruebas Node; la suite Django no ejecuta JavaScript.

### Evidencia automatizada del paso 3

`manage.py test turnosapp --noinput`: **41 pruebas aprobadas en 1,715 s**, con 12 casos nuevos de vistas. Verifican GET sin emisión, teclado con K en HTML, `no-store`, normalización/errores sin reflejar entrada, resultado sin identidad, campos manipulados sin autoridad, UUID ajeno/de otro contexto, sesión sin RUT, renovación/expiración de contexto, CSRF real obligatorio en los tres POST, limpieza sin cerrar sesión del personal y ausencia de endpoint enumerable. Una pestaña antigua no limpia el contexto nuevo y la ampliación caducada no revive la operación.

`manage.py check`: sin problemas. `node --check static/js/totem.js`: sintaxis correcta. `git diff --check -- turnosapp static/css/turnos.css static/js/totem.js specs/README.md`: sin errores de espacios. El log fijo «No se pudo completar la operación del tótem» aparece durante el caso de fallo técnico simulado; no contiene la excepción ni datos del paciente.

Regresión completa: `manage.py test --noinput`, **317 pruebas aprobadas en 73,388 s**, con base temporal creada/destruida. Esa ejecución precede a dos casos adicionales de contexto y a la organización final de helpers de pruebas; la ejecución focalizada posterior de 41 pruebas verifica esos cambios. No se afirma una ejecución completa de 319 pruebas. La última comprobación focalizada también cubre el guardado de contexto dentro del manejo de errores de base.

No se ejecutó navegador en este paso. El código de teclado, temporizadores, ampliación, recarga sin JS y limpieza de DOM/navegación atrás está incorporado; su revisión de ejecución real, foco, móvil y auditoría A/AA sigue pendiente. No se implementó aún botón de impresión ni comprobante del paso 4. La existencia del HTML y la comprobación sintáctica no prueban accesibilidad integral ni funcionamiento táctil.

Pendientes capturas sintéticas de ingreso/error/resultado, teclado, foco, zoom, móvil, inactividad y limpieza tras navegación/impresión. Pendiente auditoría automática de accesibilidad y evaluación manual. La prueba con cinco usuarios representativos es independiente.

Para impresión registrar navegador, impresora, controlador, papel de 80 mm, márgenes, encabezados/pies y resultado físico sin datos personales. Una vista previa o PDF acredita diseño, pero no compatibilidad ni salida real en impresora. Cancelar/reimprimir debe conservar el número y no generar entregas.

## Límites y fallos

El esquema, servicios y HTTP del tótem tienen evidencia automatizada y hay mediciones locales de rendimiento. Revisión visual/JavaScript real, vista previa, teclado/móvil y axe bloqueados por host indisponible; impresión física sin equipo definido; prueba con cinco usuarios y aceptación pendientes. No se declara cumplimiento integral de los RF ni RNF ni se marca Implementado. No hay integración de despachos, ventanillas, urgencia, discapacidad, llamados ni WebSocket en este alcance. HU-07 permanece parcial aun cuando se complete la emisión.

## Aplicación y reversión

Se creó la migración inicial y se aplicó al crear la base temporal de tests y de HTTP. Se comprobó retroceso y reaplicación sobre dominio sintético previo; no se modificó la SQLite local y no hubo despliegue, configuración de impresoras ni rama nueva. Cierre técnico mediante un único commit autorizado en `fdaza`. No se ha probado restaurar un respaldo externo. La reversión del esquema de turnos elimina su historial y requiere respaldo consistente si se debe conservar.

## Aceptación funcional

Pendiente. Documento Aprobado, T-04-01 autorizada mediante «si, comienza» y T-04-02 mediante «si continua el paso 2». Las comprobaciones del esquema y servicios no certifican interfaz, impresión física, accesibilidad ni aceptación del software completo.
