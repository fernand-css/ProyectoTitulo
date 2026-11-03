# SPEC 05 — Cola ponderada y llamado

> **Estado:** Aprobado
> **Depende de:** [SPEC 01](../01-base-del-proyecto/spec.md), [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 03](../03-padron-y-recetas/spec.md) y [SPEC 04](../04-emision-de-turnos/spec.md)
> **Fecha:** 2026-11-02
> **Objetivo:** Asignar automáticamente los turnos a ventanillas compatibles mediante una cola ponderada y permitir al Técnico confirmar entregas y cerrar la atención para continuar con el siguiente paciente sin duplicaciones.

Módulo: `turnosapp`, integrado con `recetasapp`. Fuente: respuestas del usuario en esta sesión y HU-04/05/06/10/11/21, RNF-01/02/04/05 del [informe](../../docs/Informe.md).
Revisión del documento completo: Aprobado por el usuario en el encabezado. Seis pasos autorizados y completados técnicamente. Navegador, accesibilidad integral, usabilidad y aceptación funcional pendientes; no se cambia a Implementado.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

El 04 emite turnos, pero solo dispone del estado `esperando`: no existen ventanillas, selección de cola, asignaciones ni cierre asociado a las entregas. La operación requiere distribuir la atención entre general, preferencial y crónicos y seguir atendiendo automáticamente cuando una ventanilla queda disponible.

El Técnico activa su ventanilla una vez y confirma las entregas realizadas al terminar. El sistema selecciona el próximo turno compatible, registra el llamado y mantiene un historial verificable. Las acciones repetidas o concurrentes no generan doble asignación ni descuentan dos veces una entrega.

## Actores y permisos

| Acción | Anónimo / tótem | Técnico | Encargado de terreno | Q.F. | Superusuario activo |
|---|---|---|---|---|---|
| Emitir o recuperar número | Según 04, con estados ampliados | Mismo flujo público | Mismo flujo público | Mismo flujo público | Mismo flujo público |
| Ver cola e historial operativo de turnos | No | Sí | No | Sí | Sí |
| Ocupar ventanilla libre, iniciar/pausar y operar atención propia | No | Sí | No | No | Sí |
| Re-llamar, declarar ausente y confirmar cierre/entregas propias | No | Sí | No | No | Sí |
| Reincorporar ausente a la cola, sin elegir posición/ventanilla | No | Sí | No | No | Sí |
| Configurar pesos y crear/habilitar/deshabilitar/archivar ventanillas | No | No | No | Sí | Sí |
| Consultar auditoría genérica | No | No | No | No | Según 02 |
| Elegir manualmente qué turno sigue o borrar historial | No | No | No | No | No |

Revalidar cuenta activa, perfil y rol único en servidor. Conservar la excepción del superusuario del 02. La Q.F. supervisa y configura; no adquiere permiso de confirmar entregas reservado al Técnico en el 03. La automatización actúa en la ventanilla activada por un Técnico habilitado, cuya identidad queda registrada; no atribuir al paciente que emite ni a una cuenta ficticia los llamados automáticos.

## Alcance y exclusiones

Incluye cola global ponderada, orden por llegada dentro de cada categoría, prioridad por espera prolongada, ocupación y activación de ventanillas, asignación compatible, llamado automático inicial y sucesivo, re-llamado registrado, ausencia manual, reincorporación, cierre con/sin entregas, auditoría, concurrencia y control de jornada. Cuatro ventanillas iniciales admiten general, preferencial y crónicos; Q.F. configura sus tipos y pesos. Se muestra tiempo transcurrido y advertencia de espera.

El **06 conserva WebSocket, pantalla pública y voz sincronizadas**. El 05 registra eventos durables para esa integración y muestra el llamado en el panel privado; no reproduce voz, publica fichas ni afirma sincronización pública. HU-04/05 y RNF de comunicación visual/sonora no quedan cumplidos íntegramente con este spec.

Fuera: preparación de medicamentos y pendientes de retiro de HU-17; estimación basada en preparación de HU-18; urgencia; validación de discapacidad; cambios de padrón/importación por esas condiciones; logística, indicadores, PWA offline y notificaciones. Marcar ausente conserva turno/recetas e historial, pero no crea un registro ficticio de medicamento preparado.

## Historias y flujo

1. Q.F. configura ventanillas habilitadas, tipos admitidos y pesos iniciales 2 preferenciales, 1 crónico y 1 general.
2. El Técnico ocupa una ventanilla libre e inicia la atención automática. El sistema llama al primer turno compatible según el algoritmo. No hay selección manual por fila.
3. Si la cola compatible está vacía, la ventanilla queda disponible. La llegada o reincorporación de un turno vuelve a activar la selección sin exigir otro clic del Técnico.
4. Re-llamar registra otro evento para el mismo turno/ventanilla y reinicia el plazo de un minuto para declarar ausencia. No consume otro puesto del ciclo ni una entrega.
5. Si el paciente no se presenta, el Técnico puede marcarlo ausente después del minuto; el sistema libera la ventanilla y llama al siguiente. No hay ausencia automática por temporizador.
6. En la atención, el Técnico selecciona cuáles recetas vinculadas entregó y confirma «Finalizar y confirmar entregas». Se revalida cada una y se cierra en una operación atómica. Las no entregadas conservan motivo; también se admite cerrar sin entrega con motivo.
7. Una vez confirmado el cierre se intenta el siguiente llamado. Si falla esa segunda operación, la entrega confirmada se conserva y queda pendiente recuperable; reintentar no repite descuentos.
8. Un ausente puede reincorporarse con el número original al final de su categoría, si no tiene otro turno activo. Si ya obtuvo otro número, no se reincorpora el anterior mientras exista ese activo.
9. Pausar impide nuevos llamados y permite cerrar la atención vigente. Deshabilitar por Q.F. exige confirmación si hay atención; también bloquea nuevos llamados desde la solicitud.
10. La nueva jornada no arrastra pendientes sin llamar del día anterior. Se conserva el historial, se permite finalizar una atención ya iniciada y el Técnico debe activar la ventanilla para la nueva jornada.

## Requisitos funcionales

- **RF-05-01 — Ventanillas y ocupación:** disponer de cuatro iniciales con los tres tipos; permitir a Q.F. crear, configurar, habilitar, deshabilitar y retirar de operación conservando historia. Cada Técnico ocupa como máximo una ventanilla y cada ventanilla tiene como máximo un operador y un turno vigente. No tomar una ocupada ni operar la ajena.
- **RF-05-02 — Cola ponderada:** ciclo compartido inicial `preferencial, preferencial, cronicos, general`, configurable por Q.F. con pesos enteros positivos. Dentro de cada grupo usar orden de entrada a la cola; saltar grupos vacíos o sin candidatos compatibles. El ciclo no se multiplica ni reinicia al abrir/cerrar ventanillas; con una abierta conserva la ponderación. Un hueco no deja sin atender otra categoría compatible.
- **RF-05-03 — Espera prolongada:** mostrar espera transcurrida, advertir desde 12 minutos y, a partir de 15 minutos inclusive, elegir el turno compatible más antiguo por encima del ciclo. Usar desempate estable. No enviar a ventanilla incompatible para cumplir el umbral. Conservar tiempos originales y del tramo actual tras reincorporación.
- **RF-05-04 — Selección totalmente automática:** iniciar habilita selección para la ventanilla; finalizar, marcar ausente, emitir, reincorporar y volver a disponer de una ventanilla deben provocar selección cuando exista capacidad. No exigir pulsar «Llamar siguiente» para cada paciente ni seleccionar por fila. No asignar dos veces ni a una ventanilla deshabilitada/pausada, ocupada o con operador no habilitado.
- **RF-05-05 — Llamado y re-llamado:** registrar número, fecha del turno, ventanilla, operador, instante y evento. Re-llamar conserva asignación y genera otro evento con identidad propia; repetir la misma operación no lo duplica. En el 05 el efecto visible es el panel privado; el aviso público/voz se integra en el 06.
- **RF-05-06 — Ausentes y retorno:** habilitar ausencia manual solo desde 60 segundos después del último llamado confirmado por el servidor; cada re-llamado reinicia ese plazo. Liberar la atención y continuar automáticamente, salvo pausa/deshabilitación. Reincorporar el mismo día al final de su categoría sin renumerar ni mantener su anterior prioridad por espera. Rechazar reincorporación si existe otro activo del paciente o si corresponde a otra jornada.
- **RF-05-07 — Cierre y entregas:** el Técnico confirma un subconjunto explícito de recetas vinculadas y motivos de no entrega. Solo las confirmadas registran una entrega del ciclo mediante las reglas del 03; ni llamar, re-llamar, ausentar, reincorporar o emitir descuentan. Si una seleccionada no es válida al confirmar, no guardar ninguna entrega ni el cierre hasta corregir la selección. Permitir cero entregas con motivo obligatorio. No agregar al turno recetas nuevas ajenas a su selección de emisión.
- **RF-05-08 — Continuación recuperable:** cerrar/entregar y llamar al siguiente son operaciones consecutivas separadas. El cierre crea un pendiente durable de selección. Si falla el próximo llamado, conservar cierre/entregas y advertir el pendiente. Reintentar o reenviar la confirmación devuelve el resultado original y no afecta la atención que pudo comenzar después. No perder el pendiente por reinicio del servidor.
- **RF-05-09 — Pausa y deshabilitación:** bloquear nuevas asignaciones desde que se confirma la solicitud, conservando la actual hasta terminar. Q.F. confirma deshabilitar si hay una atención. No trasladar automáticamente al paciente a otra ventanilla. Reanudar requiere activación explícita por el operador; retirar una ventanilla no borra historia ni abandona una atención.
- **RF-05-10 — Jornada:** antes de nuevas asignaciones cerrar los turnos antiguos aún esperando como `sin_atencion_cierre`, sin confundirlos con ausentes ni entregados. Conservar la atención que ya estaba llamada. La activación anterior no habilita llamados de la nueva fecha; exigir inicio explícito de la nueva jornada. La fecha usa `America/Santiago` y no depende del navegador.
- **RF-05-11 — Tótem y estados activos:** ampliar recuperación del 04 a turnos esperando o llamados, evitando nuevo número mientras exista uno activo. Cuando solo existen turnos ausentes, atendidos o cerrados, permitir nueva emisión si sigue habiendo recetas elegibles. Mantener correlativo diario único. No reactivar desde el tótem un ausente: emite nuevo cuando proceda; su retorno con el número original es una acción del Técnico y exige no tener otro activo.
- **RF-05-12 — Permisos, historial y auditoría:** aplicar matriz, CSRF y POST a cambios, revalidar actor/estado en servidor, conservar historial de ocupaciones/llamados/retornos/cierres/configuración y motivos. Sin borrado directo en Admin. Auditoría técnica sin RUT, nombres, datos clínicos ni texto libre de motivos. Si falla auditar una operación, revertir esa operación; no revertir un cierre previo por fallo al auditar el llamado siguiente.

## Datos y reglas

- Categorías heredadas del 04: general, preferencial y crónicos. No inferir ni almacenar discapacidad. Esta spec no modifica la clasificación de origen.
- Activo significa `esperando` o `llamado`. Un turno llamado ocupa su ventanilla hasta cerrar o declarar ausente; no se necesita otro clic de llamado al finalizar el anterior. El re-llamado nunca crea otra ocupación.
- Un turno registra cierre `atendido` si hubo alguna entrega confirmada, incluso si otras quedaron sin entregar; cierre sin entregas se distingue por resultado y motivo, sin contabilizarlo como dispensación. Ningún estado sustituye los eventos `EntregaReceta`.
- La ordenación tras retorno se basa en el nuevo ingreso a cola y su espera arranca de nuevo; preservar emisión original y todos los tramos para trazabilidad. El retorno no cambia categoría ni recetas originales.
- Cambiar pesos inicia el nuevo ciclo en la siguiente selección y no cambia turnos ya llamados. La prioridad por ≥15 minutos no avanza el cursor ponderado. Los cupos de categorías saltadas no se acumulan.
- Si todas las ventanillas habilitadas excluyen una categoría, mostrar el impedimento a Q.F./Técnico y conservar la espera; no alterar el tipo, saltar reglas ni inventar ventanilla.
- Los pendientes sin llamar del día anterior quedan cerrados, no ausentes. Los retornos de días anteriores requieren un número nuevo mediante el flujo normal del tótem. Una atención anterior ya iniciada se conserva y no permite emitir otra simultánea para ese paciente.
- La falta de una receta elegible al confirmar se corrige antes del cierre; no autoriza ignorar vigencia/cupo. Cada entrega queda asociada a su turno/receta, una sola vez, con actor y fecha. Las pantallas del 03 no deben duplicar una entrega de la misma atención.
- El cierre de atención sin entrega no demuestra que el paciente esté ausente, que haya medicamentos preparados ni que exista merma.

## Criterios de aceptación

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-05-01 | Dos Técnicos ocupan una ventanilla o uno ocupa dos | Una única ocupación válida; conflicto informado sin sobrescribir operador. |
| RF-05-02 | Todas las categorías tienen cola y solo una ventanilla admite las tres | Repite P,P,C,G; FIFO dentro de cada grupo; no reinicia al cambiar capacidad. |
| RF-05-02 | Una categoría está vacía o no es compatible | Continúa con otra compatible; no consume un llamado inexistente. |
| RF-05-03 | Esperas de 11:59, 12:00, 14:59 y 15:00 | Aviso desde 12:00; prioridad por antigüedad desde 15:00; sin asignación incompatible. |
| RF-05-04 | Activar, cerrar, ausentar o llegar un turno con cola vacía previa | Selección automática sin clic por paciente; sin doble asignación concurrente. |
| RF-05-05 | Re-llamar y repetir su POST | Misma ventanilla, un evento por operación, sin cambiar cursor ni entregas. |
| RF-05-06 | Declarar ausente antes/después del minuto, re-llamar y retornar | Reloj servidor respetado; retorno al final con mismo número; no duplica activos. |
| RF-05-07 | Seleccionar dos recetas y una se agota antes de confirmar | Ninguna entrega ni cierre parcial; permite corregir selección o cerrar sin entrega con motivo. |
| RF-05-07 | Confirmar entregas y repetir; intentar desde el módulo 03 | Una entrega por receta/atención; no excede cupo ni registra otra por el reenvío. |
| RF-05-08 | Entrega confirmada, fallo del siguiente llamado y reinicio | Entrega conservada, pendiente durable; recuperación llama una sola vez sin repetir descuento. |
| RF-05-09 | Pausa/deshabilitación concurrente con selección y cierre | Atención vigente conservada; ningún llamado nuevo tras el bloqueo. |
| RF-05-10 | Medianoche con esperando y llamado | Esperando anterior cerrado sin entrega; llamado conservado; nueva jornada exige activación. |
| RF-05-11 | Tótem con turno llamado, ausente y atendido | Recupera activo; sin activo emite nuevo si es elegible; no reincorpora un ausente silenciosamente. |
| RF-05-12 | Rol no autorizado, URL/IDs manipulados, CSRF ausente o fallo de auditoría | Acceso rechazado o rollback de la operación, sin afectar un cierre previamente confirmado. |

## No funcionales

Solo datos sintéticos, ORM y compatibilidad SQLite/futura PostgreSQL. No confiar en `select_for_update()` en SQLite: UPDATE condicional, restricciones, transacciones y reintentos acotados. Al menos tres escenarios reales de concurrencia con `TransactionTestCase`, hilos y conexiones separadas; cero turnos duplicados, doble asignación o asignación a ventanilla deshabilitada (RNF-02).

Medir ≤2 s p95 para acciones interactivas con carga descrita y padrón sintético de 670, incluyendo varias ventanillas y tótem. El NS03 de sincronización pública queda para el 06. No reutilizar rendimiento o pruebas del 04 como evidencia nueva.

WCAG 2.1 AA: contraste ≥4,5:1 para texto normal, etiquetas, foco, teclado, zoom y estados con texto. El panel identifica claramente automatismo activo/pausado, atención vigente, espera y error recuperable. No depender solo del color. La auditoría de navegador y prueba con cinco usuarios requieren evidencia propia; no declararlas por contar con HTML o pruebas de servicios.

Datos personales solo en vistas privadas autorizadas y únicamente lo necesario para identificar/entregar. No poner RUT/nombres en URL, logs, eventos públicos futuros ni auditoría genérica. Motivos operativos no deben incluir diagnósticos; conservarlos en historial privado.

## Compatibilidad

Conservar tótem/comprobante y selección de recetas del 04, padrón y permisos del 03 y habilitación del 02. Cambiar expresamente la restricción y consulta de «activo» del 04 para incluir llamado. No cambiar números emitidos ni borrar historial al migrar. Evitar contar dos veces al confirmar desde el 03 y desde la atención del 05.

Las dependencias existen; sus pendientes visuales/aceptación no se dan por cerrados aquí. El 06 es reserva, no dependencia implementada ni documento aprobado.

## Decisiones tomadas y alternativas

- Usuario eligió operación del personal en 05 y pantalla/voz sincronizadas en 06. Se descarta adelantar WebSocket.
- Aceptó pesos configurables 2:1:1, cola compartida y las cuatro ventanillas compatibles con los tres tipos. La proporción es del prototipo, no una política institucional acreditada.
- Reemplazó el botón por paciente por operación totalmente automática: al finalizar llama al siguiente. Aceptó iniciar una vez, pausa y toma automática de futuras llegadas si la cola quedó vacía.
- Aceptó ausencia manual tras un minuto del último llamado y retorno al final de la categoría, con número original. Se descarta ausencia automática.
- Aceptó advertencia a 12 minutos y rescate por antigüedad a 15, por encima de pesos.
- Aceptó confirmar entregas seleccionadas al finalizar, cierre sin entrega con motivo y atomicidad del cierre; el llamado posterior es recuperable y no revierte entregas confirmadas.
- Aceptó terminar atención vigente al pausar/deshabilitar y nueva activación diaria sin arrastrar la cola anterior.
- Última respuesta **3C** permite otro número si no hay turno activo; prevalece sobre la recomendación de impedir otro número todo el día. La reincorporación de un ausente no puede coexistir con un nuevo activo.
- HU-17, HU-18, urgencia y discapacidad quedan fuera. No se modifica el padrón para esas condiciones.

## Supuestos y decisiones pendientes

No quedan preguntas funcionales bloqueantes para redactar. Los nombres de modelos, rutas, algoritmo detallado y mecanismo de recuperación son propuestas técnicas de `plan.md` sujetas a revisión del borrador. El llamado del 05 no es un anuncio público hasta integrar el 06. No se declara cobertura completa de las HU de voz, sala de espera o preparados.

## Revisión y cambios

2026-11-02: primer bloque 1A/2A, llamado totalmente automático, 4A/5A y descuento al confirmar entrega al finalizar. Segundo bloque 1A/2A/3A/4A/5A. Último bloque 1A/2A/3C/4A. Se guardan cuatro documentos como Borrador, sin código, migraciones ni aceptación funcional.

## Acuerdo de ejecución

2026-11-02 (paso 6): «ok, hazlo brevemente por los limites» autoriza integración y cierre. HTTP con cuatro puestos, tres escenarios concurrentes, rendimiento y recuperación en proceso nuevo aprobados. Navegador/pipe no disponibles; visual, axe y aceptación siguen pendientes. Se realiza el único commit solicitado de los cambios del 05 en `fdaza`, preservando cambios ajenos preparados.

2026-11-02 (paso 5): el usuario confirmó «si, continua». Se incorporan panel privado, configuración Q.F., formularios de cierre, historial, navegación y consulta periódica de solo lectura. Se mantienen los avisos públicos/voz fuera del 05. Pausa antes de T-05-06, sin commit intermedio.

2026-11-02 (paso 4): el usuario confirmó «si» después del paso 3. Se incorpora cierre/entregas y contexto de confirmación del 03 para evitar descuentos duplicados entre pantallas. No se incorpora todavía el panel del 05. Pausa antes de T-05-05, sin commit intermedio.

2026-11-02 (paso 3): el usuario confirmó «si, continua» después del paso 2. Se incorporan servicios de operación y jornada, sin interfaz ni cierre/confirmación de entregas del paso 4. Pausa antes de T-05-04, sin commit intermedio.

2026-11-02 (paso 2): el usuario confirmó «si, continua» después del paso 1. Se incorpora planificador, pendientes durables, comando de procesamiento y disparador desde emisión. No se implementan todavía pantallas/acciones del personal ni cierre/entregas del 05. Se mantiene pausa antes de T-05-03, sin commit intermedio.

2026-11-02 (arranque): el usuario confirmó «si, continua» para T-05-01. Se incorporan esquema, restricciones, migraciones y preparación explícita; se registra solo evidencia ejecutada. No se inicia el algoritmo de T-05-02 ni se hace commit intermedio.

2026-11-02: usuario invocó `spec-impl 05` y reiteró «no crear una nueva rama, solo hacer commit». Rama actual verificada: `fdaza`. Se hará un único commit de los cambios propios del 05 al finalizar, sin commits intermedios. Hay cambios ajenos ya preparados en el índice de Git (01/02/03/04); preservarlos sin incluirlos en el commit del 05, sin stash ni limpieza. Esta instrucción prevalece sobre `AutoCreateBranch: true`. Confirmación de arranque y pausas por paso de la skill siguen vigentes mientras el usuario no indique otro ritmo.

Se conserva la preferencia vigente de trabajar en `fdaza`, sin rama nueva y con un solo commit de implementación al cierre autorizado. Esta definición no autoriza todavía implementación ni commit; no se modifica la configuración de ramas ni se heredan autorizaciones de código del 04.
