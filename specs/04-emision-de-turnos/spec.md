# SPEC 04 — Emisión de turnos

> **Estado:** Aprobado (cambio de la usuaria del 2026-11-15 para implementar la enmienda; antes «Implementado»)
> **Depende de:** [SPEC 01 — Base del proyecto](../01-base-del-proyecto/spec.md), [SPEC 02 — Autenticación, roles y auditoría](../02-autenticacion-roles-auditoria/spec.md) y [SPEC 03 — Padrón y recetas](../03-padron-y-recetas/spec.md)
> **Fecha:** 2026-11-02
> **Enmienda:** 2026-11-15 — tótem abierto, letras P/G/C, mensaje neutro y límite de intentos (RF-04-02 a RF-04-08 modificados, con el comprobante en PDF a pantalla completa y sin impresión; RF-04-11 y RF-04-12 nuevos). Aprobada por la usuaria; **implementada el 2026-11-15** (908 pruebas OK y verificación HTTP aislada; navegador, visor de PDF real, axe, usabilidad y aceptación pendientes; ver `validation.md`). El estado «Implementado» se refiere al texto anterior a la enmienda.
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
| Emitir turno sin receta elegible o fuera del padrón (enmienda 2026-11-15) | Sí, automático | Mismo flujo público | Mismo flujo público | Mismo flujo público | Mismo flujo público |
| Elegir categoría, forzar prioridad o marcar urgencia (U) | No | Spec 10 | No | Spec 10 | Spec 10 |
| Modificar/borrar turnos desde Admin | No | No | No | No | No |

El tótem no es una cuenta ni un rol operativo. Los servicios públicos no conceden privilegios por existir una sesión de personal. Se conservan las reglas de habilitación, perfil y rol único para las pantallas privadas existentes y la excepción administrativa del spec 02. No se incorpora un panel privado de gestión de turnos en este alcance.

## Alcance y exclusiones

Incluye emisión de HU-07: teclado en pantalla con dígitos, K, borrar y limpiar; validación de RUT; búsqueda interna en padrón; selección automática de todas las recetas elegibles; clasificación general/preferencial/crónicos; correlativo diario compartido; recuperación del turno activo; idempotencia, concurrencia y auditoría; número en pantalla, comprobante imprimible de 80 mm y reimpresión del mismo número.

Excluye llamado/rellamado, ausentes, cierre de atención, cola ponderada, asignación y configuración de ventanillas, pantalla de sala, voz, estimación de espera, urgencia validada por personal, preparación/no retiro, logística real, notificaciones, WebSocket, modo sin conexión y despliegue físico. El 06 sigue reservado para WebSocket; no se inventa una dependencia documental para las funciones futuras.

La discapacidad queda fuera del padrón, archivos de importación, modelos y clasificación automática. El usuario eligió dejar su validación con el personal; este spec no implementa esa validación ni una reclasificación manual. La urgencia también queda para un spec de gestión por personal. *(Enmienda 2026-11-15: el [spec 10](../10-gestion-de-turnos-por-personal/spec.md) asignará la letra U con un número nuevo de la serie U, la pondrá primera en la fila, imprimirá un comprobante nuevo y auditará quién la marcó. El tótem nunca emite U.)*

HU-07 se cubre parcialmente: el tipo se determina aquí; la ventanilla y el estado real del despacho se incorporarán en sus módulos. No declarar cumplida la historia completa al terminar este spec.

## Historias y flujo

1. El paciente abre el tótem e ingresa su RUT. Puede utilizar teclado físico o el teclado visible, incluida K para el DV.
2. El servidor normaliza y valida el RUT. Un DV incorrecto permite corregir. *(Enmienda 2026-11-15: un RUT válido que no está en el padrón también recibe turno, sin alta automática del paciente.)*
3. ~~Si es postrado o su edad cumplida es mayor de 80 años, se bloquea la emisión.~~ *(Derogado el 2026-11-15: postrados y personas de 80 años o más reciben turno preferencial.)*
4. Se recupera el turno activo de ese RUT y del día de hoy si existe. Si no existe, se reúnen en un solo turno todas las recetas elegibles que no estén en una entrega a domicilio abierta. Si el paciente tenía recetas elegibles y todas están en despacho, no se emite turno y se muestra el mensaje neutro. Si no tiene ninguna receta elegible, o no está en el padrón, el turno se emite sin recetas.
5. El servidor clasifica el nuevo turno con su letra (P, G o C) y le asigna el siguiente número diario de la serie de esa letra. No incrementa ni reserva entregas de las recetas.
6. *(Enmienda 2026-11-15: la pantalla muestra el comprobante en PDF a pantalla completa, sin impresión; ver RF-04-08.)* La pantalla muestra el número y ofrece imprimir el comprobante. El navegador abre el diálogo para la impresora instalada en el equipo. El comprobante contiene número, fecha, hora y una instrucción genérica de esperar el llamado.
7. Cancelar o fallar la impresión no elimina el turno. Reimprimir y repetir la solicitud devuelven el mismo número; no crean otra llegada. *(Enmienda 2026-11-15: no hay botón «Nueva atención»; la pantalla vuelve sola al inicio para la siguiente persona.)*

## Requisitos funcionales

- **RF-04-01 — Entrada accesible:** admitir RUT con/sin puntos, normalizar con las utilidades existentes y validar DV en servidor. Permitir K/k, corrección y limpieza, sin escribir RUT en URL o logs.
- **RF-04-02 — Padrón y atención domiciliaria** *(modificado el 2026-11-15)*: no crear pacientes desde el tótem. Todo RUT válido recibe turno, esté o no en el padrón, incluidos postrados y personas de 80 años o más. La única excepción es el paciente con recetas elegibles que están todas en una entrega a domicilio abierta: no recibe número, no se consume número de la serie y ve el mensaje neutro de RF-04-11. `Paciente.requiere_despacho_en` sigue decidiendo quién es elegible para el reparto del [spec 08](../08-domicilios-y-entregas/spec.md), pero ya no bloquea la emisión. *(Texto anterior: rechazo del RUT no registrado y bloqueo de postrados y de personas de 80 años o más, este último por el cambio del 2026-11-13.)*
- **RF-04-03 — Recetas** *(modificado el 2026-11-15)*: vincular todas las recetas del paciente que sean elegibles según `evaluar_elegibilidad` y que no estén en una entrega a domicilio abierta. Una receta vencida, futura, agotada o en despacho no se vincula ni impide aprovechar otra elegible. Si no queda ninguna, el turno se emite igual, sin recetas, y la ventanilla resuelve la atención. Si alguna receta venció o se agotó, la pantalla agrega el aviso de renovación de RF-04-11, sin mostrar códigos, medicamentos ni historial.
- **RF-04-04 — Clasificación automática por letra** *(modificado el 2026-11-15)*: **P** (preferencial) para 60 años cumplidos o más, para postrados y para personas de 80 años o más; **C** (crónicos) para menores de 60 con `es_cronico`; **G** (general) para el resto y para todo RUT que no está en el padrón. P prevalece sobre C. La letra **U** (urgencia) no la emite el tótem: la asigna el personal en el [spec 10 — Gestión de turnos por personal](../10-gestion-de-turnos-por-personal/spec.md). No inferir discapacidad del RUT, agregarla al padrón ni ofrecer autoselección de urgencia/prioridad.
- **RF-04-05 — Número y persistencia** *(modificado el 2026-11-15)*: cada letra tiene su propia serie de enteros positivos por fecha local de Chile, y el número se muestra como letra, guion y tres dígitos (P-001, G-014, C-009). Cada serie comienza en 1 cada día; no reiniciar por abrir el navegador, reiniciar el servidor o imprimir. Unicidad por (fecha, letra, número). Conservar historial y vínculos a recetas. *(Texto anterior: un correlativo único compartido por todos los tipos.)*
- **RF-04-06 — Repetición y concurrencia** *(modificado el 2026-11-15)*: el turno guarda el RUT normalizado y `paciente` es opcional (vacío para quien no está en el padrón). Mantener como máximo un turno activo por RUT y día. La recuperación solo considera turnos de la fecha actual, también los «llamado»: un turno llamado de un día anterior no se devuelve. Reenvíos, doble toque y solicitudes simultáneas conservan el mismo turno; solicitudes para RUT distintos no comparten número dentro de una letra. Reutilizar una operación para otro RUT debe rechazarse. Un conflicto agotado informa reintento sin éxito falso. El RUT guardado nunca se muestra en el tótem, el comprobante ni la sala.
- **RF-04-07 — Pantalla y limpieza** *(modificado el 2026-11-15)*: mostrar el número grande (con su letra) sin nombre, RUT, condición de crónico, recetas ni razón de preferencia. No hay botón «Nueva atención»: la pantalla del número vuelve sola al inicio a los 30 s, y tras un rechazo o error se genera una operación nueva sin intervención, de modo que la siguiente persona pueda ingresar su RUT. Se conserva «Necesito más tiempo» (WCAG 2.2.1). Limpiar entrada y datos de la operación al volver al inicio; no permitir que el siguiente usuario recupere el comprobante previo desde la interfaz.
- **RF-04-08 — Comprobante en PDF a pantalla completa** *(modificado el 2026-11-15)*: al terminar el ingreso del RUT con un número emitido o recuperado, el tótem muestra a pantalla completa, en vertical (1080×1920), un comprobante en PDF generado por el servidor, con la identidad visual del CESFAM San Nicolás. Contiene:
  - letra y número, y la categoría escrita;
  - fecha y hora de llegada;
  - la frase de espera del spec 07;
  - pasos genéricos y la sugerencia de sacarle una foto;
  - el aviso de renovación cuando corresponde (RF-04-11).

  **No se imprime:** se retiran la impresora térmica y el diálogo de impresión del navegador. El PDF no lleva RUT, nombre, recetas ni motivo de la preferencia. Se genera al momento, no se guarda, solo se sirve a la sesión de esa operación con `no-store` y no tiene URL pública ni código QR. Una franja HTML fija al pie mantiene la cuenta de 30 s y «Necesito más tiempo» (WCAG 2.2.1), y la página conserva el número como texto en una región `status` para lectores de pantalla. Repetir la solicitud muestra el mismo número. *(Texto anterior: comprobante térmico de 80 mm con diálogo del navegador y reimpresión.)*
- **RF-04-09 — Auditoría y protección:** registrar una sola emisión confirmada con referencia técnica y fecha/hora; el origen es el tótem y el actor de autoservicio no es un funcionario ficticio. Revertir emisión, correlativo y relaciones si falla auditar. Exigir POST con CSRF y no aceptar paciente, categoría, correlativo ni recetas elegidas por el navegador como autoridad.
- **RF-04-10 — Integración:** emitir o recuperar no registra `EntregaReceta` ni cambia contadores, fechas o máximos. Las recetas vinculadas representan las elegibles al emitir; futuras atenciones deben revalidar vigencia y cupo. El 04 no introduce transiciones de llamado, finalización ni expiración persistente de turnos.
- **RF-04-11 — Mensaje neutro** *(nuevo, 2026-11-15)*: todo rechazo de un RUT con DV válido muestra el mismo texto («Acércate a la ventanilla para continuar tu atención.»), con el mismo código HTTP y la misma estructura de respuesta, para no revelar si la persona está en el padrón ni si tiene un despacho. El error de formato o de DV tiene su propio mensaje. Única excepción decidida por la usuaria: el aviso «Necesitas renovar tu receta» se conserva junto al número cuando alguna receta venció o se agotó. El aviso va dentro del comprobante en PDF (RF-04-08) y por eso es **estático**: un PDF no admite animación. Se destaca con color, ícono y texto grande, sin depender solo del color. *(La animación pedida el 2026-11-15 se descarta el mismo día al elegir el comprobante en PDF.)*
- **RF-04-12 — Límite de intentos** *(nuevo, 2026-11-15)*: como máximo 10 solicitudes por minuto por equipo, contadas por IP de origen y por sesión. Al superarlas, el tótem queda en pausa breve con el mensaje neutro y se audita el evento sin el RUT. El recuento se guarda en la base de datos, no en la caché en memoria, porque cada proceso de Daphne tendría la suya.

## Datos y reglas

- La identidad del paciente continúa en `recetasapp.Paciente`; no se altera el contrato CSV/XLSX del spec 03. *(Enmienda 2026-11-15: el turno guarda además el RUT normalizado, el único dato personal que se duplica, para dar turno a quien no está en el padrón y aplicar la unicidad por RUT y día. Es un dato privado: solo lo ve el personal.)*
- *(Enmienda 2026-11-15)* Un turno sin recetas no genera `PreparacionReceta`: no afecta el promedio de preparación del spec 07, pero sí cuenta en el volumen de la cola. El spec 05 debe admitir cerrar una atención sin recetas y su reincorporación deja de aplicar el bloqueo por edad o postración.
- Edad calculada para la fecha local: exactamente 60 entra a preferencial; exactamente 80 sigue presencial; con 81 cumplidos corresponde bloqueo. Un postrado se bloquea a cualquier edad. Esta regla reproduce el acuerdo «mayor de 80». *(Reemplazada el 2026-11-13 por el [spec 08, RF-08-01](../08-domicilios-y-entregas/spec.md): exactamente 80 se bloquea y 79 es el último año preferencial; la regla es `Paciente.requiere_despacho_en`, compartida con el reparto.)*
- Recuperar un turno conserva número, letra, clasificación y recetas originales. No añade nuevas recetas ni renumera. *(La frase sobre el bloqueo domiciliario se deroga el 2026-11-15.)*
- Recuperar el turno no garantiza que sus recetas sigan utilizables; no constituye autorización para dispensar. El módulo de atención deberá consultar su estado vigente.
- En el 04, el único estado operativo creado es `esperando`. «Activo» significa ese estado para la restricción actual; el próximo spec que agregue estados deberá ampliar expresamente la restricción. Un turno del día anterior permanece en el historial y no bloquea una emisión del nuevo día ni se llama automáticamente. *(Enmienda 2026-11-15: esto incluye un turno que quedó «llamado» al cerrar el día; la recuperación lo ignora y el RUT recibe un turno nuevo.)*
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

**Criterios de la enmienda del 2026-11-15** (reemplazan las filas de RF-04-02, RF-04-03 y RF-04-04 de arriba y la parte de RF-04-05 sobre la serie compartida):

| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-04-02 | RUT válido que no está en el padrón | Recibe turno G sin recetas; no se crea paciente. |
| RF-04-02 | Postrado de cualquier edad, o persona de 79, 80 y 81 años | Recibe turno P. |
| RF-04-02 | Todas sus recetas elegibles están en una entrega a domicilio abierta | No hay turno ni se consume número; mensaje neutro. |
| RF-04-03 | Una receta elegible y otra en despacho | El turno vincula solo la elegible que no está en despacho. |
| RF-04-03 | Sin recetas elegibles; una de ellas vencida o agotada | Turno sin recetas, con el aviso de renovación. |
| RF-04-04 | Edades 59 y 60; crónico de 59; no crónico de 59 | C para el crónico de 59, G para el no crónico de 59, P desde 60. Nunca U desde el tótem. |
| RF-04-05 | Emisiones de P, G y C el mismo día y al cambiar la fecha | Cada letra lleva su serie desde 1; no se repite (fecha, letra, número); el nuevo día reinicia las tres. |
| RF-04-06 | Turno «llamado» de ayer y el mismo RUT hoy | Se emite un turno nuevo de hoy; no se devuelve el de ayer. |
| RF-04-06 | El mismo RUT fuera del padrón en solicitudes simultáneas | Un solo turno activo y un evento de emisión. |
| RF-04-07 | Se muestra el número o hay un rechazo | Sin botón «Nueva atención»; vuelve solo al inicio (30 s tras el número) y la siguiente persona puede ingresar su RUT sin tocar nada; «Necesito más tiempo» amplía el plazo. |
| RF-04-11 | No registrado (antes), despacho abierto, operación cerrada y RUT distinto en la misma sesión | Mismo texto, mismo código HTTP y misma estructura. El aviso de renovación aparece solo junto a un número emitido. |
| RF-04-08 | Número emitido, recuperado y con aviso de renovación | PDF vertical a pantalla completa con letra, número, categoría, fecha, hora, espera y pasos; aviso estático cuando corresponde; sin RUT, nombre ni recetas; franja con la cuenta de 30 s y «Necesito más tiempo». |
| RF-04-08 | Pedir el PDF sin la sesión de la operación, después de volver al inicio, o desde otro navegador | Rechazo; el PDF no queda guardado ni accesible por URL. |
| RF-04-12 | 11 solicitudes en un minuto desde el mismo equipo | La undécima queda en pausa con mensaje neutro y se audita sin RUT. |

Las pruebas concurrentes (`TransactionTestCase` e hilos) cubren al menos: el mismo RUT fuera del padrón en paralelo, letras distintas en paralelo sin choques dentro de cada serie, y un despacho abierto mezclado con emisiones.

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
- *(2026-11-15)* Tótem abierto a todo RUT válido para que la atención aguda y quienes no están en el padrón no sigan dependiendo del rollo de papel. Se descartan la emisión manual por el personal y el rechazo de los no registrados.
- *(2026-11-15)* Identificación por RUT normalizado guardado en el turno. Se descarta guardar una huella HMAC en su lugar.
- *(2026-11-15)* Una serie por letra (P, G, C) en vez del correlativo compartido: números más cortos y legibles; las restricciones únicas evitan los choques que producían los rollos de papel. Se descarta la serie compartida con letra delante.
- *(2026-11-15)* Mensaje neutro y límite de intentos en lugar de autenticar el equipo del tótem; el aviso de renovación se conserva por decisión de la usuaria.
- *(2026-11-15)* **Comprobante en PDF a pantalla completa, sin papel** (decisión de la usuaria): se descartan la impresora térmica de 80 mm (elegida el 2026-11-02), un PDF con botón de impresión y la descarga al celular por QR, esta última porque exigiría un enlace público al comprobante.
- *(2026-11-15)* **Desvío del informe (HU-07):** el informe pide no ofrecer número presencial a postrados y mayores de 80 y mostrar el estado de su despacho. Por decisión de la usuaria reciben turno preferencial, porque si llegan a la farmacia deben poder ser atendidos; solo se excluyen las recetas que van en un despacho abierto. La letra U responde a la «urgencia» de HU-07 y HU-10, asignada por el personal en el [spec 10](../10-gestion-de-turnos-por-personal/spec.md).

## Riesgos residuales (2026-11-15)

- Sin autenticación del equipo, quien conozca un RUT ajeno puede sacar un turno a nombre de esa persona y alterar la estimación de espera. El límite de intentos lo acota, pero no lo impide.
- El aviso de renovación revela a quien conozca un RUT ajeno que esa persona tiene una receta crónica vencida o agotada. Se acepta por decisión de la usuaria.
- Se acepta en el prototipo, que corre en un entorno aislado. La implementación real debe decidir con la unidad TIC del DESAMU si autentica el equipo del tótem y si mantiene el aviso.

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

2026-11-13 (cambio desde el spec 08, implementado en `crojas-base`): por decisión del equipo, el corte de edad pasa a «80 años cumplidos o más» (`edad >= 80`) para el tótem y el reparto a la vez ([spec 08, RF-08-01](../08-domicilios-y-entregas/spec.md)). Un paciente de 80 años ya no recibe número: el tótem lo orienta al personal con «Consulta tu despacho con el personal», y el preferencial queda de 60 a 79 años. Solo cambiaron las aserciones del límite de edad en `turnosapp/tests/test_servicios.py` (80 pasa de preferencial a bloqueo; se agrega 79 como preferencial); las demás pruebas del 04 siguen sin cambios. Los criterios de RF-04-02 y RF-04-04 de arriba conservan su texto original con esta nota. Este spec se trabajó en `fdaza`: hay que avisar al equipo.

2026-11-15 (enmienda por la revisión de los specs 01–07, hallazgos A2, A4 y A5): la usuaria decidió:
- abrir el tótem a todo RUT válido, salvo cuando todas sus recetas elegibles están en un despacho abierto (se excluyen solo las recetas del despacho);
- identificar por RUT, sin huella;
- conservar el aviso de renovación, ojalá animado;
- mantener los 30 s y el límite propuesto;
- usar letras con una serie por letra (P, G y C desde el tótem, U solo por el personal);
- quitar el botón «Nueva atención» para que la pantalla vuelva sola al inicio.

Se modifican RF-04-02 a RF-04-07 y se agregan RF-04-11 y RF-04-12. La regla de 80 años del cambio del 2026-11-13 deja de bloquear en el tótem; en el spec 08 sigue definiendo la elegibilidad del reparto. Quedan pendientes:
- la implementación, con sus pruebas concurrentes;
- las enmiendas correspondientes en los specs 05 (fila U primera, cierre sin recetas, reincorporación), 06 (la voz y la sala dicen la letra) y 08 (nota en RF-08-01);
- el [spec 10 — Gestión de turnos por personal](../10-gestion-de-turnos-por-personal/spec.md).

Sin cambios de código en esta enmienda.

2026-11-15 (posterior): la usuaria decidió que el comprobante quede al terminar el ingreso del RUT, solo en PDF, a pantalla completa en un tótem vertical, con diseño propio del CESFAM San Nicolás, durante 30 s. Se modifica RF-04-08 (sin impresión térmica) y el aviso de renovación de RF-04-11 pasa a ser estático. El diseño visual se trabaja aparte de este documento.
