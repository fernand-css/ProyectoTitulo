# SPEC 07 — Preparación y tiempos de espera

> **Estado:** Implementado
> **Depende de:** [SPEC 01](../01-base-del-proyecto/spec.md), [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 03](../03-padron-y-recetas/spec.md), [SPEC 04](../04-emision-de-turnos/spec.md) y [SPEC 05](../05-cola-ponderada-y-llamado/spec.md)
> **Fecha:** 2026-11-03
> **Objetivo:** Registrar cuándo queda lista la preparación de cada receta de un turno, permitir retirar después los medicamentos preparados de quien no se presentó y mostrar un tiempo estimado de espera calculado con los tiempos reales de preparación.

Módulo: `recetasapp` (preparación y retiro) con integración en `turnosapp` (emisión, tótem, comprobante y panel). Fuente: HU-06, HU-17, HU-18, HU-21, RNF-01/02/04/05 del [informe](../../docs/Informe.md) y las respuestas del usuario en esta sesión.
Implementación autorizada por el usuario el 2026-11-03 al solicitar la implementación y confirmar el inicio de T-07-01. Aceptación funcional: pendiente.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

Hoy un turno solo dice «esperando» o «llamado». El sistema no sabe si los medicamentos de ese turno ya están preparados, cuánto tarda en prepararse una receta ni qué pasa con lo preparado cuando el paciente no se presenta. El 05 dejó explícitamente fuera estos puntos: marcar ausente conserva el turno, pero no crea ningún registro de medicamento preparado, y el cierre de atención sin entrega no prueba que haya preparación ni merma.

Resultado esperado:

- Cada receta de un turno tiene un registro de preparación que nace al emitir el turno y que el personal marca como «Lista».
- Los medicamentos preparados que no se entregaron aparecen en una lista de «pendientes de retiro», con la fecha original de preparación. El personal los busca por RUT o apellido y registra el retiro sin volver a pasar por la fila.
- Con los tiempos reales de preparación, el sistema calcula un tiempo promedio por receta y estima la espera. El paciente la ve al emitir su turno y el personal la ve en su panel.

## Actores y permisos

| Acción / datos | Anónimo / tótem | Técnico | Encargado de terreno | Q.F. | Superusuario activo |
|---|---|---|---|---|---|
| Emitir turno (crea la recepción de preparación) | Sí, según 04 | Mismo flujo público | Mismo flujo público | Mismo flujo público | Mismo flujo público |
| Ver el tiempo estimado en el resultado y el comprobante | Sí, solo ese texto | — | — | — | — |
| Ver «Por preparar» y «Pendientes de retiro» | No | Sí | No | Sí | Sí |
| Marcar «Lista» y corregir una marca propia o ajena del día | No | Sí | No | Sí | Sí |
| Registrar el retiro de un preparado pendiente | No | Sí | No | Sí | Sí |
| Ver la estimación y la carga de preparación en el panel del 05 | No | Sí | No | Sí | Sí |
| Dar de baja un preparado (merma) | No | No | No | No | No |
| Elegir qué se prepara primero o borrar historial | No | No | No | No | No |

Revalidar cuenta activa, perfil y rol único en servidor; conservar la excepción del superusuario del 02. **La Q.F. puede marcar «Lista» y registrar retiros por decisión expresa del usuario** (ver decisiones): difiere de la matriz del 03 y del 05, donde solo el Técnico confirma entregas. La excepción se limita a estas dos acciones. El cierre de atención del 05 y la confirmación de entrega del 03 siguen siendo del Técnico y del superusuario. El Encargado de terreno no accede a nada de este módulo.

## Alcance y exclusiones

**Incluye:**
- Registro de preparación por cada receta de cada turno emitido, desde su recepción hasta «Lista».
- Marcar «Lista» y corregir una marca equivocada.
- Sección **Preparación dentro de Recetas**, con las pestañas «Por preparar» y «Pendientes de retiro». No se agrega una entrada al menú principal.
- Lista de pendientes de retiro con búsqueda por RUT o apellido, y registro del retiro posterior con las reglas de vigencia de la fecha de preparación.
- Medición del tiempo de trabajo, promedio histórico por receta y estimación de espera.
- Estimación visible en el resultado del tótem, el comprobante impreso y el panel del Técnico del 05.

**Fuera de este spec:**
- Dar de baja o descartar un preparado (merma) y el panel de mermas por período: HU-20, otro spec. Aquí solo se conserva la fecha original de preparación para que ese panel pueda calcularla.
- Mostrar la estimación en la pantalla pública de sala: el usuario no la eligió. El contrato del 06 no cambia.
- Derivar un paciente no retirado hacia entregas a domicilio, notificaciones y logística (HU-12 a HU-16, HU-19, HU-22).
- Elegir manualmente la prioridad de preparación, reservar cupo de receta al preparar, escáner o código de barras, inventario o stock de medicamentos.
- Modo sin conexión (reserva 11).
- Cualquier integración con Rayén (RNF-07).

## Historias y flujo

1. Al emitirse un turno, el sistema crea una preparación «recibida» por cada receta vinculada, con la hora de emisión como recepción. Es parte de la misma operación: si no se puede registrar, el turno no se emite.
2. En **Recetas › Preparación › Por preparar**, el personal ve los turnos activos de hoy (esperando o llamados) con sus recetas por preparar. Al terminar una, pulsa «Marcar lista». Se guarda quién y cuándo, y cuánto trabajo midió.
3. Si se marcó por error, puede corregirse mientras el turno siga activo y la receta no se haya entregado. La corrección no entra al promedio.
4. Cuando el turno se llama y el paciente se presenta, el Técnico cierra la atención y confirma entregas como en el 05. Este spec no cambia ese flujo.
5. Si el turno queda ausente, se cierra al cambiar la jornada sin llamar, o se cierra sin entregar una receta ya preparada, esa receta aparece en **Pendientes de retiro**, con su fecha de preparación y el motivo.
6. Cuando el paciente regresa, el personal busca por RUT o apellido, abre el registro y pulsa «Registrar retiro». Se crea la entrega de la receta original, sin nueva fila ni nuevo número.
7. Si la receta se agotó o cambió mientras tanto, el retiro se rechaza con el motivo visible y el registro sigue pendiente.
8. Al emitir un turno, el tótem muestra y el comprobante imprime un tiempo aproximado de espera. El panel del Técnico muestra la carga de preparación y la estimación vigente.

## Requisitos funcionales

- **RF-07-01 — Recepción al emitir:** CUANDO el sistema emite un turno, ENTONCES crea en la misma transacción una preparación «recibida» por cada receta vinculada, con `recibida_en` igual al instante de emisión del turno. SI la creación falla, ENTONCES no se emite el turno y no queda número consumido. Recuperar un turno ya emitido (idempotencia del 04) no crea preparaciones nuevas.
- **RF-07-02 — Marcar «Lista»:** CUANDO un usuario autorizado marca una preparación de un turno activo de la jornada, ENTONCES queda «Lista» una sola vez, con quién, cuándo y el inicio de su intervalo de trabajo (RF-07-07). Marcar de nuevo la misma preparación devuelve el resultado original sin duplicar la medición. Marcar no cambia el estado del turno ni el contador de entregas de la receta.
- **RF-07-03 — Corregir «Lista»:** CUANDO un usuario autorizado corrige una marca, ENTONCES la preparación vuelve a «recibida» y su medición se descarta, siempre que el turno siga activo y la receta no tenga entrega. En otro caso, se rechaza con el motivo. La corrección queda en la auditoría.
- **RF-07-04 — Pantalla «Por preparar»:** EL SISTEMA muestra, dentro de Recetas, los turnos activos de hoy con sus recetas pendientes de preparar, en orden de llegada, con número de turno, tipo de atención, espera transcurrida, código de receta, «entrega n de m» y la acción «Marcar lista». Muestra las ya listas con su hora y quién las marcó. Se actualiza sin recargar. Indica con texto cuando no hay nada por preparar.
- **RF-07-05 — Pendientes de retiro:** EL SISTEMA lista como pendiente toda preparación «Lista» sin entrega cuyo turno quedó `ausente`, `sin_atencion_cierre` o cerrado con la receta sin entregar. NO lista las de turnos activos ni las de turnos reincorporados. Permite buscar por RUT o apellido. Cada fila muestra paciente, receta, turno de origen, motivo del cierre, **fecha original de preparación** y días transcurridos.
- **RF-07-06 — Retiro posterior:** CUANDO un usuario autorizado registra el retiro de un pendiente, ENTONCES el sistema crea la entrega de la receta original, vinculada a su turno de origen, sin pasar por la cola. La vigencia se evalúa a la **fecha de preparación**; el cupo se evalúa con el contador actual y nunca puede excederse. Repetir la operación no duplica la entrega ni el descuento. SI la receta se agotó, ENTONCES se rechaza con el motivo y el registro sigue pendiente. El retiro no modifica el estado ni el cierre histórico del turno.
- **RF-07-07 — Tiempo de trabajo y promedio:** AL marcar «Lista», el sistema guarda el **intervalo de trabajo**: desde el más tardío entre la recepción y la última marca «Lista» del mismo usuario ese día, hasta la marca actual. Con eso calcula el promedio por receta de los últimos 14 días, usando solo intervalos de hasta 30 minutos y exigiendo al menos 5 muestras. Con menos muestras usa 5 minutos por receta. Los intervalos descartados y las correcciones no entran, pero se conservan.
- **RF-07-08 — Estimación de espera:** EL SISTEMA estima la espera como *(recetas aún no listas de los turnos activos de hoy) × (promedio por receta) ÷ (ventanillas en atención)*, redondeada hacia arriba a tramos de 5 minutos. SI no hay ventanillas en atención, ENTONCES no estima y lo dice con texto. SI el resultado es menor de 5 minutos, ENTONCES muestra «menos de 5 minutos». Siempre se rotula como aproximada.
- **RF-07-09 — Estimación para el paciente:** CUANDO el tótem muestra el resultado de un turno, ENTONCES incluye el tiempo aproximado de espera, y el comprobante de 80 mm lo imprime con la misma frase. Al recuperar un turno ya emitido se recalcula con la cola actual. Nunca incluye RUT, nombre, categoría ni datos de recetas. SI no se puede estimar, ENTONCES el texto lo dice y orienta a consultar con el personal.
- **RF-07-10 — Estimación para el personal:** EL PANEL del 05 muestra al Técnico y a la Q.F. cuántas recetas faltan por preparar, el promedio vigente con su número de muestras y la estimación actual, y se actualiza con su consulta periódica. Enlaza a la sección Preparación.
- **RF-07-11 — Permisos, privacidad y auditoría:** EL SISTEMA aplica la matriz de permisos, exige POST con CSRF para todo cambio y revalida actor y estado en servidor. Las vistas del módulo son privadas y no se guardan en caché. La auditoría registra quién marcó, corrigió o retiró, sin RUT, nombres ni texto libre. Si falla la auditoría de una operación, se revierte esa operación.
- **RF-07-12 — Concurrencia y compatibilidad:** EL SISTEMA no genera dos preparaciones por receta de turno, no cuenta dos veces una marca «Lista», no registra dos entregas por el mismo vínculo turno-receta ni excede el cupo, incluso con operaciones simultáneas y entre las pantallas del 03, del 05 y de este spec. SI un ausente tiene todas sus recetas ya retiradas, ENTONCES no puede reincorporarse. Las pruebas existentes del 03, 04, 05 y 06 pasan sin cambios.

## Datos y reglas

- **Preparación:** una por vínculo `TurnoReceta`. Estados derivados: *recibida* (sin marca), *lista* (con marca), *retirada* (con `EntregaReceta` del vínculo). No se guarda un estado redundante que pueda desincronizarse.
- **Pendiente de retiro:** no es una tabla aparte. Se deriva de una preparación *lista* y sin entrega, cuyo turno está `ausente`, `sin_atencion_cierre`, o cerrado (`atendido` o `cerrado_sin_entrega`) con esa receta sin entregar. Así reincorporar un ausente lo saca de la lista sin sincronizar nada.
- **Tiempos:** se guardan en segundos y en horas con zona horaria. La jornada y los días usan `America/Santiago`. Una preparación sin marca al cerrar la jornada no tiene tiempo ni entra a ninguna lista.
- **Retiro y vigencia:** la fecha de referencia es la de la marca «Lista». Desde la marca queda establecido que la receta estaba vigente para esa preparación; el retiro posterior no reevalúa ese hecho. El cupo se mantiene como restricción dura de la base: si otra entrega agotó la receta, el retiro no procede.
- **Cierre histórico:** el `DetalleCierre` del 05 no cambia. Una receta que se cerró «sin entregar» y se retiró después conserva su cierre original; el retiro es una entrega posterior vinculada al mismo turno-receta.
- **Turnos anteriores a este spec:** los turnos activos al aplicar la migración no tienen preparación y no aparecen en las listas ni en la estimación.
- **Datos públicos:** el tótem y el comprobante muestran solo el texto de espera. Ninguna salida pública incluye datos del paciente.
- **Parámetros iniciales** (propuestos, a confirmar): ventana de 14 días; mínimo de 5 muestras; valor por defecto de 5 min por receta; tope de intervalo de 30 min; redondeo de 5 min; consulta periódica de la sección cada 5 s.

## Criterios de aceptación

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-07-01 | Emitir un turno con tres recetas elegibles | Tres preparaciones «recibidas» con `recibida_en` igual a la emisión; una sola transacción. |
| RF-07-01 | Falla forzada al crear la preparación; recuperación del mismo turno | No hay turno ni número consumido; recuperar no duplica preparaciones. |
| RF-07-02 | Dos usuarios marcan la misma preparación a la vez | Una única marca y una única medición; el segundo recibe el resultado original. |
| RF-07-02 | Marcar la preparación de un turno ausente o de otra jornada | Rechazo con motivo; sin cambios. |
| RF-07-03 | Corregir una marca de un turno activo; corregir una ya entregada | La primera vuelve a «recibida» y sale del promedio; la segunda se rechaza. |
| RF-07-04 | Abrir «Por preparar» con turnos esperando y llamados | Orden de llegada, espera visible, acciones por receta y estado en texto; sin recargar al marcar. |
| RF-07-05 | Turno ausente con una receta lista y otra sin marcar | Solo la lista aparece en pendientes, con su fecha original de preparación. |
| RF-07-05 | Reincorporar el ausente | Sus recetas salen de pendientes. |
| RF-07-05 | Buscar por RUT sin puntos, con puntos y por apellido en mayúsculas | Mismo resultado; sin coincidencias, mensaje claro. |
| RF-07-06 | Retirar una receta preparada el lunes, vigente ese día y vencida el martes | Se registra la entrega con el actor y la fecha real; el contador sube una vez. |
| RF-07-06 | Cupo agotado por otra entrega antes del retiro | Rechazo con el motivo; registro sigue pendiente; contador intacto. |
| RF-07-06 | Repetir el POST del retiro | Una sola entrega. |
| RF-07-07 | 4 muestras válidas; 5 muestras; un intervalo de 31 min; muestras de 13 y 15 días | Con 4 usa 5 min; con 5 usa su promedio; el de 31 min y el de 15 días no entran; el de 13 días sí. |
| RF-07-07 | Un Técnico marca dos recetas seguidas | La segunda mide desde la marca anterior, no desde la emisión. |
| RF-07-08 | 6 recetas por preparar, promedio de 4 min, 2 ventanillas | 12 min → muestra «unos 15 minutos». |
| RF-07-08 | Sin ventanillas en atención; resultado menor de 5 min | Texto «No podemos estimar» y orientación al personal; «menos de 5 minutos». |
| RF-07-09 | Emitir y recuperar un turno; imprimir comprobante | El resultado y el comprobante muestran la misma frase; sin datos personales. |
| RF-07-10 | Avanzar la preparación con el panel abierto | La carga y la estimación cambian en el siguiente ciclo, sin recargar. |
| RF-07-11 | Encargado, anónimo, cuenta inactiva o sin perfil; POST sin CSRF | Acceso rechazado; ninguna acción se ejecuta. |
| RF-07-12 | Mínimo tres escenarios concurrentes con hilos y conexiones separadas | Cero duplicados de preparación, marca, entrega o descuento; el cupo nunca se excede. |
| RF-07-12 | Reincorporar un ausente cuyas recetas ya se retiraron | Rechazo con el motivo. |

## No funcionales

- Solo datos sintéticos y ORM de Django; sin SQL crudo. Compatible con PostgreSQL y con la SQLite temporal de las herramientas. Sin `select_for_update()`: UPDATE condicional, restricciones únicas, transacciones y reintentos acotados, como el resto del proyecto (RNF-02).
- Respuesta de 2 s o menos en el p95 para las acciones y consultas del módulo, y para la emisión con el cálculo agregado, con el padrón sintético de 670 pacientes y varias ventanillas (RNF-05). Se mide con evidencia propia.
- WCAG 2.1 AA (RNF-04): contraste de 4,5:1 como mínimo, estados con texto y no solo con color, foco visible, teclado, móvil y zoom. La estimación se lee completa por texto, sin depender de iconos. La revisión de navegador y axe, y la prueba de usabilidad con cinco personas, requieren evidencia propia y no se declaran por tener HTML o pruebas de servicios.
- Privacidad (RNF-01): datos personales solo en las vistas privadas autorizadas. Nada de RUT ni nombres en URL, registros del servidor o auditoría genérica.

## Compatibilidad

Conservar el tótem y el comprobante del 04, las reglas de elegibilidad y el contador del 03, la cola, el llamado, el cierre y los permisos del 05 y el contrato público del 06. Los cambios en servicios existentes son estrictamente aditivos: un parámetro nuevo para el retiro en el servicio de entregas del 03 y una validación nueva al reincorporar en el 05. Las pruebas del 03, 04, 05 y 06 deben pasar sin modificarse; todo cambio en emisión, llamado o asignación exige las pruebas concurrentes de CLAUDE.md.

Las dependencias existen en `specs/`. Sus pendientes de aceptación visual y funcional no se dan por cerrados aquí. El 06 no se modifica: deja fuera la estimación y este spec respeta esa decisión.

## Decisiones tomadas y alternativas

- **El usuario pidió que la preparación quede dentro de Recetas.** Modelo, servicios, vistas y plantillas viven en `recetasapp`; `turnosapp` solo llama a ellos desde la emisión y el panel. Se descarta crear una app nueva o una entrada del menú principal.
- **Recepción al emitir y marca «Lista» de un solo clic** (recomendado). Se descartan el paso intermedio «En preparación» (dos clics por receta, puede quedar sin marcar) y empezar al llamar (no permite tener medicamentos listos antes del llamado).
- **Corrección del cálculo propuesto en la pregunta.** El tiempo emisión→lista incluye la espera en la fila de preparación; usarlo como promedio por receta y luego multiplicarlo por las recetas pendientes cuenta esa espera dos veces. Por eso se guarda el **intervalo de trabajo** (desde la marca anterior del mismo usuario o la recepción, la que sea posterior). Mantiene el clic único y mide el trabajo real. Queda para revisión del usuario.
- **Pendientes de retiro desde tres cierres:** ausente, cierre de jornada sin llamar y atención cerrada sin entrega. HU-17 solo exige el primero. Se deriva en vez de guardarse para que reincorporar no exija sincronizar nada.
- **Solo retiro posterior, sin baja.** La merma y su panel son HU-20; aquí se conserva la fecha de preparación para ese cálculo. Se descarta una baja manual con motivo por agregar estados, permisos y auditoría ajenos a HU-17.
- **Estimación en el tótem, el comprobante y el panel del Técnico; no en la pantalla de sala.** HU-18 pide además que se actualice a medida que avanza la cola. El resultado del tótem dura segundos y el comprobante es papel, así que la actualización continua solo la ve el personal. **HU-18 queda cubierta de forma parcial**, y así debe decirse en la validación.
- **Fórmula: pendientes × promedio ÷ ventanillas en atención** (recomendada). Se descartan simular la cola ponderada (acopla el spec al planificador del 05) y no dividir (sobrestima con varias ventanillas). Se asume que cada ventanilla en atención representa a una persona que prepara.
- **Retiro con las reglas de vigencia de la fecha de preparación** (decisión del usuario; se recomendaba la fecha de retiro). Consecuencia: el servicio de entregas del 03 necesita un camino nuevo que evalúe la vigencia a esa fecha y acepte un turno ya cerrado. El cupo no es negociable: lo impone una restricción de la base (`receta_contador_en_cupo`).
- **La Q.F. también marca «Lista» y registra retiros** (decisión del usuario; se recomendaba solo Técnico y superusuario). Consecuencia: la entrega por retiro puede quedar a nombre de una Q.F., algo que la matriz del 03 y del 05 no permite hoy. Se limita a estas dos acciones y se registra el actor real.
- Se descarta reservar cupo al preparar: complicaría el contador del 03 y no lo pide HU-17.

## Supuestos y decisiones pendientes

Supuestos técnicos reversibles, sujetos a revisión del borrador:
- Los parámetros de la sección «Datos y reglas» son valores iniciales del prototipo, no una política institucional.
- Cada ventanilla en atención equivale a una persona que prepara.
- Los nombres de modelo, rutas y servicios son propuestas del `plan.md`.
- La consulta periódica de la sección reutiliza el patrón del panel del 05; el intervalo exacto se decide al implementar.

No hay bloqueos críticos para redactar. Pendiente de confirmar por el usuario: la corrección del intervalo de trabajo, los parámetros iniciales y que el «panel del Técnico» sea el `/turnos/panel/` del 05 además de la propia sección.

## Revisión y cambios

2026-11-03: primer bloque (inicio en la emisión con marca «Lista», tres cierres que dejan pendientes, solo retiro sin baja, estimación en tótem/comprobante/panel) y segundo bloque (fórmula recomendada, sección dentro de Recetas, reglas de vigencia a la fecha de preparación, Q.F. también marca y retira). Se guardan cuatro documentos como Borrador, sin código, migraciones ni aceptación funcional.
