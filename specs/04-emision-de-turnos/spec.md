# SPEC 04 — Emisión de turnos

> **Estado:** Implementado
> **Depende de:** [SPEC 01 — Base del proyecto](../01-base-del-proyecto/spec.md), [SPEC 02 — Autenticación, roles y auditoría](../02-autenticacion-roles-auditoria/spec.md) y [SPEC 03 — Padrón y recetas](../03-padron-y-recetas/spec.md)
> **Fecha:** 2026-11-02
> **Objetivo:** Permitir que el paciente ingrese su RUT en el tótem y obtenga un único turno presencial diario activo para sus recetas elegibles, con número en pantalla y comprobante para impresora térmica.

Módulo solicitado: `turnosapp`, reutilizando padrón y elegibilidad de `recetasapp`.
Fuente: respuestas del usuario del 2026-11-02; HU-07, HU-21 y RNF-01/02/04/05/07 de [Informe.md](../../docs/Informe.md).
Revisión del documento completo: Aprobado por el usuario en el encabezado. Implementación autorizada por invocación de `spec-impl` y confirmaciones sucesivas hasta T-04-05 («sip»). Código y verificación técnica completados; revisión visual, vista previa, auditoría integral de accesibilidad, impresión física y aceptación pendientes. Se conserva Aprobado; ver `validation.md`.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

El padrón y las recetas ya existen, pero `turnosapp` conserva su esqueleto. El paciente necesita registrar su llegada sin números duplicados ni confusión entre filas. La emisión debe comprobar las recetas disponibles sin registrar todavía una entrega de medicamentos.

El resultado será un tótem público con entrada de RUT, número visible y comprobante térmico de 80 mm. Si no corresponde atención presencial o faltan recetas utilizables, explicará el siguiente paso sin exponer antecedentes clínicos, nombres ni identificadores del paciente en el resultado o comprobante.

## Actores y permisos

| Acción / datos | Anónimo / tótem | Técnico | Encargado de terreno | Q.F. | Superusuario activo |
|---|---|---|---|---|---|
| Solicitar turno introduciendo RUT | Sí | Mismo flujo público | Mismo flujo público | Mismo flujo público | Mismo flujo público |
| Ver número y solicitar impresión del resultado de su operación | Sí, en el contexto de la operación | Igual | Igual | Igual | Igual |
| Consultar padrón y recetas completos | No | Según spec 03 | No | Según spec 03 | Según spec 03 |
| Consultar listado de turnos de otros pacientes desde el tótem | No | No | No | No | No |
| Forzar prioridad, emitir sin receta o eludir bloqueo domiciliario | No | No | No | No | No |
| Modificar/borrar turnos desde Admin | No | No | No | No | No |

El tótem no es una cuenta ni un rol operativo. Los servicios públicos no conceden privilegios por existir una sesión de personal. Se conservan las reglas de habilitación, perfil y rol único para las pantallas privadas existentes y la excepción administrativa del spec 02. No se incorpora un panel privado de gestión de turnos en este alcance.

## Alcance y exclusiones

Incluye emisión de HU-07: teclado en pantalla con dígitos, K, borrar y limpiar; validación de RUT; búsqueda interna en padrón; selección automática de todas las recetas elegibles; clasificación general/preferencial/crónicos; correlativo diario compartido; recuperación del turno activo; idempotencia, concurrencia y auditoría; número en pantalla, comprobante imprimible de 80 mm y reimpresión del mismo número.

Excluye llamado/rellamado, ausentes, cierre de atención, cola ponderada, asignación y configuración de ventanillas, pantalla de sala, voz, estimación de espera, urgencia validada por personal, preparación/no retiro, logística real, notificaciones, WebSocket, modo sin conexión y despliegue físico. El 06 sigue reservado para WebSocket; no se inventa una dependencia documental para las funciones futuras.

La discapacidad queda fuera del padrón, archivos de importación, modelos y clasificación automática. El usuario eligió dejar su validación con el personal; este spec no implementa esa validación ni una reclasificación manual. La urgencia también queda para un spec de gestión por personal.

HU-07 se cubre parcialmente: el tipo se determina aquí; la ventanilla y el estado real del despacho se incorporarán en sus módulos. No declarar cumplida la historia completa al terminar este spec.

## Historias y flujo

1. El paciente abre el tótem e ingresa su RUT. Puede utilizar teclado físico o el teclado visible, incluida K para el DV.
2. El servidor normaliza y valida el RUT. Un DV incorrecto permite corregir; un paciente no encontrado recibe indicación de consultar al personal, sin alta automática.
3. Si es postrado o su edad cumplida es mayor de 80 años, se bloquea la emisión y se muestra «Consulta tu despacho con el personal». No se afirma que exista un despacho programado ni se muestra un estado ficticio.
4. Para los demás, se recupera el turno activo de ese paciente y día si existe. Si no existe, se comprueba que al menos una receta sea elegible y se reúnen todas las que lo sean en un solo turno.
5. El servidor clasifica el nuevo turno y le asigna el siguiente correlativo diario disponible. No incrementa ni reserva entregas de las recetas.
6. La pantalla muestra el número y ofrece imprimir el comprobante. El navegador abre el diálogo para la impresora instalada en el equipo. El comprobante contiene número, fecha, hora y una instrucción genérica de esperar el llamado.
7. Cancelar o fallar la impresión no elimina el turno. Reimprimir y repetir la solicitud devuelven el mismo número; no crean otra llegada. El tótem permite finalizar y limpiar el resultado para la siguiente persona.

## Requisitos funcionales

- **RF-04-01 — Entrada accesible:** admitir RUT con/sin puntos, normalizar con las utilidades existentes y validar DV en servidor. Permitir K/k, corrección y limpieza, sin escribir RUT en URL o logs.
- **RF-04-02 — Padrón y atención domiciliaria:** no crear pacientes desde el tótem. Rechazar RUT válido no registrado con indicación de asistencia. Bloquear a postrados y mayores de 80 años con el aviso acordado, sin crear turno ni prometer estado de despacho.
- **RF-04-03 — Recetas:** emitir solo si hay al menos una receta elegible según `evaluar_elegibilidad`; vincular todas las elegibles del paciente. Una receta vencida, futura o agotada no se vincula ni impide aprovechar otra elegible. Sin ninguna disponible, informar que consulte al personal; para vencimiento/agotamiento indicar que requiere renovación, sin mostrar códigos, medicamentos ni historial.
- **RF-04-04 — Clasificación automática:** después del bloqueo domiciliario, asignar preferencial a pacientes con edad cumplida de 60 a 80 años inclusive; para menores de 60, crónicos si `es_cronico`, y general en caso contrario. Preferencial prevalece sobre crónicos. No inferir discapacidad del RUT, agregarla al padrón ni ofrecer autoselección de urgencia/prioridad.
- **RF-04-05 — Número y persistencia:** asignar un correlativo entero positivo único por fecha local de Chile, compartido por todos los tipos. Cada nueva fecha comienza en 1; no reiniciar por abrir el navegador, reiniciar el servidor o imprimir. Conservar historial y vínculos a recetas.
- **RF-04-06 — Repetición y concurrencia:** mantener como máximo un turno activo por paciente y día. Reenvíos, doble toque y solicitudes simultáneas conservan el mismo turno; solicitudes para pacientes distintos no comparten número. Reutilizar una operación para otro paciente debe rechazarse. Un conflicto agotado informa reintento sin éxito falso.
- **RF-04-07 — Pantalla y limpieza:** mostrar el número grande sin nombre, RUT, condición de crónico, recetas ni razón de preferencia. Limpiar entrada y datos de la operación al finalizar o expirar la pantalla; no permitir que el siguiente usuario recupere el comprobante previo desde la interfaz.
- **RF-04-08 — Impresión térmica:** ofrecer comprobante preparado para rollo de 80 mm mediante el diálogo estándar del navegador. Imprimir únicamente número, fecha, hora e indicaciones genéricas. Reimprimir conserva contenido y número; la cancelación, falta de papel o indisponibilidad de la impresora no crea otro turno. No afirmar impresión física confirmada a partir del cierre del diálogo.
- **RF-04-09 — Auditoría y protección:** registrar una sola emisión confirmada con referencia técnica y fecha/hora; el origen es el tótem y el actor de autoservicio no es un funcionario ficticio. Revertir emisión, correlativo y relaciones si falla auditar. Exigir POST con CSRF y no aceptar paciente, categoría, correlativo ni recetas elegidas por el navegador como autoridad.
- **RF-04-10 — Integración:** emitir o recuperar no registra `EntregaReceta` ni cambia contadores, fechas o máximos. Las recetas vinculadas representan las elegibles al emitir; futuras atenciones deben revalidar vigencia y cupo. El 04 no introduce transiciones de llamado, finalización ni expiración persistente de turnos.

## Datos y reglas

- La identidad del paciente continúa en `recetasapp.Paciente`; no se duplican sus datos personales en turnos ni se altera el contrato CSV/XLSX del spec 03.
- Edad calculada para la fecha local: exactamente 60 entra a preferencial; exactamente 80 sigue presencial; con 81 cumplidos corresponde bloqueo. Un postrado se bloquea a cualquier edad. Esta regla reproduce el acuerdo «mayor de 80».
- Recuperar un turno conserva número, clasificación y recetas originales. No añade nuevas recetas ni renumera. El bloqueo domiciliario se evalúa antes de devolver un resultado presencial; un cambio posterior del padrón no se usa para eludirlo.
- Recuperar el turno no garantiza que sus recetas sigan utilizables; no constituye autorización para dispensar. El módulo de atención deberá consultar su estado vigente.
- En el 04, el único estado operativo creado es `esperando`. «Activo» significa ese estado para la restricción actual; el próximo spec que agregue estados deberá ampliar expresamente la restricción. Un turno del día anterior permanece en el historial y no bloquea una emisión del nuevo día ni se llama automáticamente.
- La operación idempotente identifica un intento; la unicidad por paciente/fecha protege también peticiones con distintas operaciones o navegadores.
- No ofrecer número de ventanilla, posición o tiempo estimado mientras esas funciones no existan.

## Criterios de aceptación

| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-04-01 | RUT con distintas formas, DV K/k, DV incorrecto y entrada vacía | Se reconoce la misma identidad normalizada o se informa error corregible sin emisión. |
| RF-04-02 | RUT válido ausente, postrado de cualquier edad o paciente con 81 años | No se crea turno; el mensaje corresponde y no inventa despacho. |
| RF-04-03 | Hay varias recetas elegibles y otras vencidas/futuras/agotadas | Un solo turno contiene exclusivamente todas las elegibles. |
| RF-04-03 | No hay recetas o todas están bloqueadas | No hay emisión; se orienta al personal/renovación según corresponda. |
| RF-04-04 | Edades 59, 60, 80 y 81; crónico menor y mayor de 60 | Se respeta la precedencia y los límites, sin campo de discapacidad ni urgencia pública. |
| RF-04-05 | Emisiones de distintos tipos el mismo día y después del cambio de fecha | Números distintos de una serie compartida; el nuevo día comienza en 1; historial conservado. |
| RF-04-06 | Doble toque, reenvío, pérdida de respuesta y emisión simultánea para el mismo paciente | Un turno activo y un evento de emisión; se recupera su número sin duplicados. |
| RF-04-06 | Emisiones simultáneas para pacientes distintos | Ningún par fecha/número se repite; no se informan éxitos sin persistencia. |
| RF-04-07/08 | Resultado y vista previa térmica; finalizar y volver atrás | Sin datos personales/clínicos; número legible; la pantalla anterior no se recupera desde la interfaz. |
| RF-04-08 | Imprimir, cancelar y reimprimir | Se conserva el mismo turno; el papel/vista previa tiene 80 mm y no se registra una entrega de medicamentos. |
| RF-04-09 | POST sin CSRF, categoría/IDs manipulados o fallo de auditoría | Rechazo o rollback íntegro; sin turno parcial ni datos personales en trazas. |
| RF-04-10 | Emitir/recuperar con recetas disponibles y luego registrar entrega por el módulo existente | Emitir/recuperar no altera cupos; la entrega sigue las reglas independientes del spec 03. |

## No funcionales

Solo datos sintéticos. El campo de RUT es una entrada transitoria para la búsqueda, no un dato a reproducir en resultados públicos. No guardar padrón, RUT ni recetas en localStorage, caché offline o URL. Respuestas del flujo con `Cache-Control: no-store`; impedir que errores técnicos reflejen la entrada. Conocer un RUT no equivale a autenticar al paciente ni permite consultar su ficha.

Aplicar WCAG 2.1 AA, contraste mínimo 4,5:1 para texto normal, etiquetas y errores asociados, foco visible, teclado físico, zoom y botones táctiles amplios. Los mensajes no dependen solo de color o sonido. No hay llamados sonoros en este alcance. Verificar con auditoría automática y revisión manual; la prueba con cinco usuarios representativos del RNF-04 permanece pendiente hasta contar con evidencia real.

Medir el p95 de solicitudes de emisión/recuperación con padrón sintético de 670 pacientes frente a RNF-05 (≤ 2 s), registrando entorno, muestra y carga. El tiempo humano en el diálogo de impresión y la salida mecánica del papel se miden aparte. RNF-02 exige cero duplicados y al menos tres escenarios concurrentes con `TransactionTestCase` e hilos; SQLite requiere restricciones, UPDATE condicional y reintentos, no confiar en `select_for_update()`.

## Compatibilidad

Conservar seis apps, ORM, un solo `settings.py`, `auth.User`, permisos, auditoría y contratos del spec 03. No integrar API con Rayén ni un servicio externo de discapacidad. No extender las reservas 06/11/12 ni atribuir a este spec los cierres pendientes de otros módulos.

## Decisiones tomadas y alternativas

- Se eligió emisión en tótem; llamados, ventanillas y cola se separan para limitar el 04.
- Sin logística implementada, se bloquea la emisión domiciliaria y se orienta al personal. Se descarta simular un despacho real.
- Un turno reúne todas las recetas elegibles y no descuenta entregas. Se descarta un número por receta y elegir recetas clínicas desde la pantalla pública.
- Se aceptó la clasificación por edad/crónico y la precedencia preferencial sobre crónicos. Urgencia se posterga a gestión por personal.
- El usuario eligió expresamente **no incluir discapacidad en el padrón**; su validación queda con el personal, fuera de este spec. La alternativa de agregar un indicador o columna se descarta.
- Correlativo diario único compartido y recuperación del turno activo. Se descartan rollos independientes por tipo.
- Impresión térmica de 80 mm por impresora instalada y diálogo del navegador. Se descarta impresión silenciosa, conexión directa ESC/POS y agente local en este prototipo.

## Supuestos y decisiones pendientes

No quedan decisiones funcionales bloqueantes para redactar el borrador. Los modelos, rutas y valores de interfaz del plan son propuestas técnicas sujetas a revisión del documento, no código ya existente.

Modelo, controlador y equipo de la impresora no fueron informados. Se puede desarrollar y comprobar la vista previa de 80 mm; la compatibilidad física y sus márgenes deben verificarse con el equipo disponible antes de aceptar la impresión real. Una prueba PDF no sustituye esa evidencia. La validación manual de discapacidad y la prioridad por urgencia requieren otra definición; no declarar su cobertura aquí.

## Revisión y cambios

2026-11-02: el usuario eligió 1A/2A/3A/4A y 5A con impresión térmica; ratificó las recomendaciones. En la última aclaración eligió 1C/2A/3A y precisó «no incluyamos la discapacidad en el padrón». Esta última instrucción prevalece sobre la mención de discapacidad en la propuesta de clasificación. Se documentan emisión, edades, crónicos y térmica con diálogo. Estado Borrador; sin autorización de implementación ni aceptación funcional.

2026-11-02 (posterior): el usuario cambió el encabezado a Aprobado e invocó `spec-impl 04-emision-de-turnos`, indicando «solo guardarlo por un commit y no crear una nueva rama». Se registra el acuerdo siguiente; no se inició código ni validación funcional.

2026-11-02 (arranque): el usuario confirmó «si, comienza». Se inició T-04-01 en `fdaza`: modelos, migración inicial y pruebas de integridad/actualización. La evidencia del paso se registra en `validation.md`; los servicios de emisión y su concurrencia permanecen para T-04-02.

2026-11-02 (paso 2): el usuario indicó «si continua el paso 2». Se incorporan servicios de emisión/recuperación, clasificación y auditoría transaccional, sin cambios de interfaz ni descuento de entregas. Se mantiene `fdaza`, sin commit intermedio y con pausa antes de T-04-03.

## Acuerdo de ejecución

T-04-05 autorizada con «sip». Verificación técnica final: 322 pruebas Django, dos JavaScript y HTTP real sobre 670 pacientes sintéticos/24 migraciones. El intento de revisión por Computer Use falló por host de navegador y pipe nativo indisponibles. Se documentan límites en lugar de declarar verificaciones visuales o impresión física. Se conserva Aprobado y se guarda el cierre técnico mediante el único commit autorizado en `fdaza`, sin incluir cambios ajenos del 01/02/03.

Continuación de T-04-04 autorizada por «si, continua» después del cierre del paso 3. Se incorpora comprobante y diálogo; la revisión visual de impresión y prueba física permanecen pendientes. Pausa antes de T-04-05.

Continuación de T-04-03 autorizada por «si, continua» después del cierre del paso 2. El formulario y contexto del tótem se incorporan; se mantiene la pausa antes de T-04-04. Ver evidencia y límites en `validation.md`.

Trabajar en la rama actual `fdaza`, sin crear ni cambiar de rama. El usuario autoriza un único commit de los cambios propios del spec 04 al finalizar; no hacer commits intermedios ni incluir cambios ajenos del 01/02/03. Esta instrucción explícita prevalece sobre `AutoCreateBranch: true` y el flujo predeterminado de ramas de la skill. Conservar el trabajo local existente sin stash ni limpieza. Se mantienen la confirmación de arranque y las pausas por paso de `spec-impl` mientras el usuario no indique otro ritmo. La invocación y la aprobación documental no equivalen a aceptación funcional ni autorización de despliegue.
