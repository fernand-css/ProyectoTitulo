# SPEC 08 — Domicilios y entregas a domicilio

> **Estado:** Aprobado (versión del 2026-11-11). **Ampliación del 2026-11-13 en Aprobado:** cambia RF-08-01 (80 años o más) y agrega RF-08-16 y RF-08-17 (lista con filtros y búsqueda en vivo, y programación de varios pacientes a la vez).
> **Enmienda del 2026-11-15, Aprobada** por el usuario el mismo día, tras revisar el lienzo de diseño; implementada técnicamente el mismo día (T-08-14 a T-08-16; navegador real del celular, axe, usabilidad y aceptación pendientes). El título de su sección conserva «Borrador» para no romper los enlaces; manda esta cabecera (ver [Enmienda del 2026-11-15](#enmienda-del-2026-11-15-borrador)): modal «Registrar fotos»/«Gestionar fotos» que guarda todo junto (modifica RF-08-05), visor de imagen y los textos «Detalles del domicilio» y «Nombre de la localidad» (RF-08-18 a RF-08-20). Va junto con la [enmienda del spec 09](../09-mapa-y-orden-de-visita/spec.md#enmienda-del-2026-11-15-borrador), que revierte la exclusión de elegir coordenadas en el mapa.
> **Depende de:** [SPEC 01](../01-base-del-proyecto/spec.md), [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 03](../03-padron-y-recetas/spec.md), [SPEC 04](../04-emision-de-turnos/spec.md), [SPEC 05](../05-cola-ponderada-y-llamado/spec.md) y [SPEC 07](../07-preparacion-y-tiempos-de-espera/spec.md)
> **Fecha:** 2026-11-11
> **Objetivo:** Registrar y verificar los domicilios de los pacientes del reparto, programar y asignar sus entregas a un encargado de terreno, registrar con conexión si se entregaron y reprogramar las no realizadas, conservando el historial.

Módulo: `entregasapp` (domicilios, programación y registro), con cambios acotados en `recetasapp` (servicio de entregas y ficha del paciente), `turnosapp` (emisión del tótem) y `coreapp` (menú, inicio y procesamiento de imágenes). Fuente: HU-12, HU-13, HU-15 (parte con conexión), HU-16 y HU-21; RNF-01/02/04/05/07; IG03 e IG04 del [informe](../../docs/Informe.md); respuestas del usuario del 2026-11-11.
Implementación autorizada: sí, el 2026-11-11 (`/spec-impl 08-domicilios-y-entregas` en `crojas-base`, todos los pasos). Revisión del usuario: Aprobado; aceptación funcional pendiente.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

El reparto a domicilio atiende a unos 70 pacientes postrados y a unos 600 mayores de 80 años, en una comuna con un 57,9 % de ruralidad. Hoy depende del conocimiento de los conductores y de direcciones ambiguas («Dadinco, km 2 casa roja»): preguntan a los vecinos, no hay registro de quién entregó, qué no se entregó ni por qué, y un intento fallido se reorganiza de memoria. El sistema ya dirige a postrados y mayores de 80 desde el tótem hacia el personal («Consulta tu despacho con el personal»), pero no tiene dónde continuar ese despacho.

Resultado esperado:

- Cada paciente del reparto tiene un domicilio con sector, localidad, dirección, referencias, coordenadas y hasta tres fotos del entorno. Se distinguen los domicilios verificados en terreno de los pendientes.
- La Q.F. programa cada entrega con fecha y encargado. El sistema impide duplicarla y fija las recetas que lleva.
- El encargado ve sus entregas desde el celular y registra «entregada» o «no entregada» con su motivo. Al entregar, el contador «n de m» de cada receta avanza como en farmacia.
- La Q.F. filtra las entregas no realizadas y las reasigna con una nueva fecha y encargado. Los intentos anteriores se conservan.

## Actores y permisos

| Acción / datos | Anónimo / tótem | Técnico | Encargado de terreno | Q.F. | Superusuario activo |
|---|---|---|---|---|---|
| Ver domicilios, fotos y entregas | No | Sí, solo consulta | Sí | Sí | Sí |
| Registrar o editar un domicilio, agregar o borrar fotos | No | No | Sí | Sí | Sí |
| Marcar un domicilio como verificado | No | No | **Sí** | No | No |
| Inscribir o retirar una excepción de reparto | No | No | No | Sí | Sí |
| Programar una o varias entregas, reasignar o anular una entrega; marcar revisada una receta no descontada | No | No | No | Sí | Sí |
| Ver «Mis entregas» y registrar el resultado | No | No | Solo las suyas | No | No |
| Emitir turno con una receta de entrega abierta | Rechazado con texto | — | — | — | — |
| Confirmar en farmacia una receta de entrega abierta | — | Rechazado con motivo | — | — | — |

Revalidar cuenta activa, perfil y rol único en el servidor, como en el 02. **Excepción a la regla del superusuario:** por decisión del usuario, el superusuario actúa como la Q.F. No verifica domicilios ni registra resultados, porque esas acciones atestiguan una visita en terreno. Solo el encargado asignado a un intento registra su resultado. El Técnico consulta sin modificar.

## Alcance y exclusiones

**Incluye:**
- Regla de elegibilidad para el reparto: postrado o de 80 años o más (cambio del 2026-11-13), o inscrito como excepción por la Q.F.
- *(Ampliación 2026-11-13, Borrador)* En «Programar entrega», la lista completa de elegibles con filtros (sector, motivo del reparto, estado del domicilio y localidad) y búsqueda que actualiza la lista mientras se escribe.
- *(Ampliación 2026-11-13, Borrador)* Programación de varios pacientes en una sola acción, con la misma fecha y el mismo encargado, revisión previa y resumen de los programados y omitidos.
- Domicilio por paciente: sector MAIS (Verde, Azul o Rojo), localidad, dirección, referencias, coordenadas opcionales y estado de verificación.
- Coordenadas tomadas con la ubicación del navegador del celular o escritas a mano. No usa ningún proveedor de mapas.
- Hasta tres fotos privadas por domicilio, recomprimidas y sin metadatos.
- Programación y asignación de entregas con sus recetas, y una sola entrega abierta por paciente.
- Bloqueo de doble vía: una receta con entrega abierta no se dispensa en farmacia.
- «Mis entregas» del encargado y registro con conexión de «entregada» o «no entregada», con motivo.
- Descuento del cupo de la receta al registrar «entregada».
- Pendientes de gestión, reasignación con historial, anulación y revisión de las recetas no descontadas.
- Entrada «Entregas» en el menú, inicio del encargado y domicilio en la ficha del paciente.

**Fuera de este spec:**
- Mapa con íconos, orden de visita sugerido y cualquier proveedor de cartografía (HU-14): spec 09.
- Registro sin conexión, caché del service worker y sincronización diferida (HU-15 sin conexión, RNF-03, NS05): reserva 11. Aquí el registro exige conexión, pero el diseño deja preparada la idempotencia que necesitará.
- Notificación de despacho en camino y confirmación por el paciente o cuidador (HU-19, HU-22): reserva 12. Este spec no envía mensajes ni usa el teléfono del paciente salvo para mostrarlo al encargado.
- Panel de mermas y los indicadores IG03 e IG04 (HU-20, HU-11): spec 10. Este spec deja los datos con los que se calculan.
- Reasignación o anulación de varias entregas a la vez en Pendientes de gestión, y repartir un mismo lote entre varios encargados (la programación de varios del RF-08-17 usa un solo encargado). Preparación o armado de la bolsa en farmacia; inventario; rutas, vehículos y geolocalización en tiempo real (fuera de alcance del informe).
- Marcar el punto del domicilio en un mapa, con latitud y longitud que se actualizan al mover el marcador: se registrará en el spec 09, que es dueño de la cartografía y ya muestra el mapa en la ficha del domicilio (decisión del usuario, 2026-11-13). *(Enmienda 2026-11-15: el 09 lo agrega como «Usar mapa» en el formulario del domicilio, RF-09-25. El motivo está en su tabla de decisiones revertidas.)*
- Escribir en `Paciente` o cambiar la importación del 03. Integración con Rayén (RNF-07).

## Historias y flujo

1. **Domicilio (HU-12).** En **Entregas › Domicilios**, el encargado o la Q.F. buscan a un paciente del reparto por RUT o apellido. Si su domicilio aún no existe, el formulario parte con la dirección del padrón. Al guardar se registran sector, localidad, dirección, referencias y, si se quiere, coordenadas («Usar mi ubicación actual» o ingreso manual) y fotos.
2. **Verificación.** En terreno, el encargado confirma que el domicilio es correcto y pulsa «Marcar verificado». Se guarda quién y cuándo. Cualquier cambio posterior en los datos de ubicación lo devuelve a «pendiente de verificar». Si una importación posterior trae otra dirección en el padrón, el domicilio también vuelve a pendiente y muestra la dirección nueva para revisarla.
3. **Excepciones.** Si un paciente no es postrado ni tiene 80 años o más, pero necesita despacho, la Q.F. lo inscribe con un motivo de catálogo. Puede retirar la inscripción después.
4. **Programación (HU-13).** En **Entregas › Programación**, la Q.F. busca a un paciente elegible y elige una fecha (hoy o posterior) y un encargado activo. Revisa las recetas que el sistema seleccionó y confirma. Nace una entrega abierta con su primer intento. Si el paciente ya tiene una entrega abierta, el sistema lo impide y enlaza a ella. Si no tiene recetas elegibles, se rechaza con el motivo.
   - *(Ampliación 2026-11-13, Borrador)* Al pulsar «Programar entrega», la Q.F. ve de inmediato a todos los pacientes del reparto, paginados. Bajo la barra de búsqueda hay filtros de sector, motivo del reparto, estado del domicilio y localidad. Al escribir o cambiar un filtro, la lista se actualiza sin recargar la página. Puede seguir eligiendo a un paciente («Elegir», flujo individual), o marcar varios con casillas o con «Seleccionar los N filtrados» (todos los que cumplen la búsqueda y los filtros, en todas las páginas). Con «Programar seleccionados» elige una fecha y un encargado para todos, revisa un resumen por paciente y confirma. El sistema programa a cada paciente por separado, muestra el avance y al final informa «Se programaron X de Y», con los omitidos y su motivo.
5. **Mientras está abierta**, sus recetas no se dispensan en farmacia: el tótem orienta al personal y la confirmación de ventanilla muestra el motivo.
6. **Terreno (HU-15).** El encargado abre **Mis entregas** en el celular. Ve los intentos asignados de hoy, los atrasados y los próximos, con paciente, teléfono, domicilio, referencias, fotos y recetas. Al visitar, registra «Entregada» o «No entregada» con motivo.
7. **Entregada:** el sistema descuenta cada receta que sigue elegible en la fecha de la visita. Las que no lo son quedan «no descontadas» con su causa y aparecen a la Q.F. para revisión. La entrega se cierra.
8. **No entregada:** la entrega pasa a «pendiente de gestión» sin descontar nada.
9. **Gestión (HU-16).** En **Entregas › Pendientes de gestión**, la Q.F. filtra por motivo, sector, encargado y fecha. Con «Reasignar» crea un nuevo intento con otra fecha y otro encargado, y el anterior queda intacto en el historial. Con «Anular» cierra la entrega con un motivo y libera sus recetas. También puede reasignar un intento programado que aún no tiene resultado.

## Requisitos funcionales

- **RF-08-01 — Elegibilidad para el reparto** *(modificado el 2026-11-13, Borrador)*: EL SISTEMA considera elegible, en una fecha dada, a un paciente postrado, con **80 años cumplidos o más** a esa fecha (`edad >= 80`) o con una inscripción de excepción vigente. La regla de postrado y edad sigue siendo una sola función, compartida por el tótem del 04 y este módulo. Por eso el tótem también cambia: a un paciente de 80 años no le da número y lo orienta al personal («Consulta tu despacho con el personal»), y el preferencial del tótem queda de 60 a 79 años. *Antes:* `edad > 80`, sin cambiar el 04. *(Nota del 2026-11-15: la [enmienda del spec 04](../04-emision-de-turnos/spec.md) deja de usar esta regla en el tótem. Postrados y personas de 80 años o más reciben turno preferencial; el tótem solo excluye las recetas que están en una entrega abierta y da el mensaje neutro si no queda ninguna. Aquí la regla sigue definiendo quién es elegible para el reparto, sin otros cambios.)*
- **RF-08-02 — Excepciones:** CUANDO la Q.F. inscribe a un paciente no elegible por edad ni postración, EL SISTEMA guarda el motivo del catálogo, una nota opcional, quién y cuándo. Hay como máximo una inscripción vigente por paciente; no vence sola. Retirarla conserva el registro, con quién y cuándo. SI el paciente ya es elegible por edad o postración, ENTONCES no se inscribe y se informa. Retirar una excepción no cierra la entrega abierta que tenga.
- **RF-08-03 — Registro de domicilio:** EL SISTEMA guarda un domicilio por paciente elegible, con sector MAIS, localidad, dirección, referencias y coordenadas opcionales (latitud y longitud juntas, con precisión opcional en metros). Al crearlo se ofrece la dirección del padrón como valor inicial y se recuerda esa dirección de origen. La importación del 03 nunca modifica el domicilio. SI dos personas editan el mismo domicilio a la vez, ENTONCES la segunda recibe «El domicilio cambió; revisa los datos nuevos» y no sobrescribe la primera.
- **RF-08-04 — Verificación:** CUANDO el encargado marca un domicilio como verificado, EL SISTEMA guarda quién y cuándo, siempre que tenga sector y dirección. CUANDO cambian el sector, la localidad, la dirección, las referencias o las coordenadas, el domicilio vuelve a «pendiente de verificar». SI la dirección actual del padrón difiere de la dirección de origen recordada, ENTONCES el domicilio se muestra como pendiente con el aviso «La dirección del padrón cambió» y la dirección nueva, hasta que alguien lo guarde de nuevo. Agregar o borrar fotos no cambia la verificación.
- **RF-08-05 — Fotos del entorno:** EL SISTEMA admite hasta tres fotos por domicilio, en JPEG o PNG de 5 MB o menos, cada una con una descripción breve y obligatoria que sirve de texto alternativo. Las recomprime a JPEG, corrige su orientación, elimina todos sus metadatos (incluida la ubicación GPS) y limita su tamaño. Las guarda fuera de los archivos públicos y solo las entrega una vista con sesión y rol, sin caché. Rechaza archivos que no son imágenes, imágenes dañadas o demasiado grandes, y una cuarta foto. El borrado elimina el archivo y queda auditado. El formulario recuerda con texto no fotografiar personas ni patentes. *(Enmienda 2026-11-15: las fotos se agregan y se borran en un modal que aplica todos los cambios juntos, y se ven en un visor; ver RF-08-18 y RF-08-19. Las reglas de formato, tamaño, recompresión, privacidad y auditoría no cambian.)*
- **RF-08-06 — Programar entrega:** CUANDO la Q.F. programa una entrega para un paciente elegible a la fecha elegida, con fecha igual o posterior a hoy y un encargado con cuenta activa, EL SISTEMA crea la entrega «programada» y su primer intento, y fija como recetas de la entrega todas las elegibles a esa fecha según el 03. Excluye las recetas con un turno activo y las que esperan retiro en el 07. SI no queda ninguna receta, ENTONCES rechaza con el motivo. SI el paciente ya tiene una entrega abierta, ENTONCES rechaza y enlaza a ella; la base lo impide aunque haya dos solicitudes simultáneas. Repetir el POST no crea otra.
- **RF-08-07 — Bloqueo de doble vía:** MIENTRAS una entrega está abierta, sus recetas no son elegibles para el tótem del 04 ni para la confirmación de entrega del 03 y del 05. El tótem omite esas recetas; si no le queda ninguna, responde «Tienes un despacho a domicilio programado. Consulta con el personal.», sin datos del paciente ni de las recetas. La confirmación en farmacia se rechaza con «La receta tiene una entrega a domicilio abierta». Al cerrarse o anularse la entrega, las recetas vuelven a ser elegibles según sus reglas.
- **RF-08-08 — Mis entregas:** EL SISTEMA muestra al encargado solo sus intentos sin resultado: los de hoy, los atrasados (rotulados «Atrasada desde el dd/mm») y los próximos aparte. Cada uno muestra paciente, teléfono, sector y localidad, dirección, referencias, estado de verificación, fotos, coordenadas en texto y recetas con su «entrega n de m». La lista se ordena por fecha, sector y localidad; no hay mapa ni orden de visita. Indica con texto cuando no hay entregas. *(El orden y la presentación los cambió el spec 09. Enmienda 2026-11-15: tarjetas compactas con «Entregar», «No entregada» y «Expandir»; ver RF-09-16.)*
- **RF-08-09 — Registrar «entregada»:** CUANDO el encargado asignado registra «entregada» en un intento sin resultado con fecha programada igual o anterior a hoy, EL SISTEMA guarda el resultado con la fecha y hora del servidor y cierra la entrega. Por cada receta de la entrega crea la entrega de receta del 03, que avanza su contador, si sigue elegible a la fecha de la visita. Las que no lo son quedan «no descontadas» con la causa del 03. El cupo nunca se excede. Repetir la operación con el mismo identificador devuelve el resultado original sin otro descuento.
- **RF-08-10 — Registrar «no entregada»:** CUANDO el encargado asignado registra «no entregada», EL SISTEMA exige un motivo del catálogo y acepta una nota de hasta 200 caracteres (obligatoria con el motivo «Otro»). La entrega pasa a «pendiente de gestión», no descuenta nada y conserva sus recetas bloqueadas. Es idempotente como el RF-08-09.
- **RF-08-11 — Pendientes de gestión y reasignación:** EL SISTEMA lista a la Q.F. las entregas pendientes de gestión, con su último motivo, nota, encargado, fecha e intentos previos, y permite filtrar por motivo, sector, encargado y rango de fechas. Con «Reasignar», con fecha igual o posterior a hoy y encargado activo, crea un intento nuevo y deja la entrega «programada». Los intentos anteriores no se modifican. Reasignar un intento programado sin resultado lo cierra como «reasignado» y crea el siguiente. Con «Anular», que exige un motivo de catálogo, la entrega queda «anulada» y su intento pendiente, si existe, queda «anulado».
- **RF-08-12 — Recetas no descontadas:** EL SISTEMA muestra a la Q.F. las recetas que quedaron sin descontar al registrar una entrega, con paciente, receta, causa y fecha. Permite marcarlas «revisadas», con quién y cuándo. La lista indica con texto cuando no queda ninguna.
- **RF-08-13 — Navegación:** EL MENÚ agrega «Entregas» para el Técnico, la Q.F. y el superusuario, con las pestañas Programación, Pendientes de gestión y Domicilios. El encargado ve «Mis entregas» y «Domicilios», y su inicio lo lleva a «Mis entregas». La pestaña Datos de la ficha del paciente muestra su domicilio, su estado de verificación y su entrega abierta, con enlaces, a los perfiles que pueden verlos.
- **RF-08-14 — Permisos, privacidad y auditoría:** EL SISTEMA aplica la matriz de permisos en el servidor, exige POST con CSRF para todo cambio y revalida actor, asignación y estado en el servidor. Las vistas y las fotos son privadas y sin caché. En las URL solo hay identificadores internos, nunca RUT ni nombres. La auditoría registra quién creó, editó o verificó un domicilio, agregó o borró una foto, inscribió o retiró una excepción, programó, reasignó o anuló una entrega, registró un resultado y revisó una receta no descontada; no guarda RUT, nombres, direcciones, notas ni coordenadas. Si falla la auditoría, se revierte la operación.
- **RF-08-15 — Concurrencia y compatibilidad:** EL SISTEMA no crea dos entregas abiertas por paciente ni dos intentos sin resultado por entrega. No registra dos resultados por intento. No descuenta dos veces una receta ni excede su cupo. Nunca deja una receta a la vez en una entrega abierta y en un turno activo. No pierde ediciones concurrentes de un domicilio. Esto vale incluso con operaciones simultáneas entre este módulo, el tótem, la ventanilla y el retiro del 07. Las pruebas existentes del 03 al 07 pasan sin cambiar sus aserciones, salvo las del límite de edad del 04 que cambia el RF-08-01 del 2026-11-13 (80 años pasa de preferencial a bloqueo).
- **RF-08-16 — Lista de elegibles con filtros y búsqueda en vivo** *(2026-11-13, Borrador)*: CUANDO la Q.F. abre «Programar entrega» sin un paciente preseleccionado, EL SISTEMA muestra a todos los pacientes elegibles a hoy, en orden por apellido y nombre y en páginas de 50, con su motivo del reparto (Postrado, 80 años o más, Excepción; uno o varios), sector y localidad, estado del domicilio y si ya tiene una entrega abierta. Bajo la barra de búsqueda (RUT, nombre o apellido) ofrece cuatro filtros combinables: **sector** (Todos, Verde, Azul, Rojo, Sin sector), **motivo del reparto** (Todos, Postrado, 80 años o más, Excepción vigente), **estado del domicilio** (Todos, Verificado, Pendiente de verificar, Sin registrar) y **localidad** (Todas y las localidades registradas en los domicilios de los elegibles). MIENTRAS la Q.F. escribe o cambia un filtro, la lista y su cantidad se actualizan sin recargar la página y vuelven a la primera página. El foco se queda donde está y la cantidad nueva se anuncia a los lectores de pantalla. El RUT y los nombres buscados nunca van en la URL. Sin JavaScript, la misma búsqueda y los filtros funcionan con un botón «Buscar». Un paciente con entrega abierta aparece rotulado «Ya tiene una entrega abierta», con enlace a ella, y no se puede seleccionar. Sin resultados, se dice con texto y se ofrece «Excepciones de reparto».
- **RF-08-17 — Programar varios pacientes a la vez** *(2026-11-13, Borrador)*: CUANDO la Q.F. marca pacientes con sus casillas, o pulsa «Seleccionar los N filtrados» (todos los que cumplen la búsqueda y los filtros vigentes, en todas las páginas, **sin tope**), y luego «Programar seleccionados», EL SISTEMA pide una fecha (hoy o posterior) y un encargado activo para todos. Después muestra un **resumen para revisar**: fecha, encargado, cantidad de pacientes y de recetas, y por paciente sus recetas con «entrega n de m» (desplegables), junto con los que no se programarán y su motivo. CUANDO la Q.F. confirma, programa **a cada paciente por separado** con las mismas reglas y garantías del RF-08-06 y muestra el avance («Programando 50 de 118»). Al terminar informa «Se programaron X de Y» y lista los omitidos con su motivo: ya tiene una entrega abierta (también si otra persona lo programó al mismo tiempo), sin recetas disponibles en esa fecha o ya no es elegible. Un fallo de un paciente no detiene ni revierte a los demás. Repetir la confirmación del mismo lote, completa o por partes, no crea entregas duplicadas y entrega el mismo resultado de los ya programados. La casilla se conserva al cambiar de página, buscar o filtrar mientras la Q.F. no salga de la pantalla. Cambiar la búsqueda o un filtro anula «Seleccionar los N filtrados» y lo dice con texto.

## Datos y reglas

- **Domicilio:** uno por paciente, creado la primera vez que alguien lo guarda (no al importar). Sector obligatorio para verificar: Verde, Azul o Rojo (sectores MAIS del informe). Localidad hasta 120 caracteres, dirección hasta 500 y referencias hasta 500. Latitud y longitud con 6 decimales, en rangos válidos, ambas o ninguna. Precisión en metros opcional. Recuerda la dirección del padrón de la que partió o que se revisó por última vez.
- **Verificación:** se guarda (quién y cuándo). El estado efectivo es «verificado» solo si existe la marca y la dirección del padrón no cambió; si no, «pendiente de verificar». Un paciente sin domicilio guardado figura como «sin registrar».
- **Fotos:** a lo más tres por domicilio, con la base como garantía (posición 1 a 3, única por domicilio). Se guarda solo el JPEG procesado, con nombre aleatorio, ancho, alto y tamaño. El original no se conserva.
- **Excepción:** motivos *movilidad reducida*, *discapacidad*, *sin red de apoyo*, *indicación clínica* y *otro* (este último exige nota). Nota de hasta 200 caracteres.
- **Entrega:** paciente, estado (*programada*, *pendiente de gestión*, *entregada*, *anulada*) y recetas fijadas al programar. Abierta = programada o pendiente de gestión; restricción única parcial de una abierta por paciente. Al anular se guardan el motivo (*retirará en farmacia*, *sin recetas vigentes*, *ya no requiere despacho* u *otro* con nota obligatoria) y quién y cuándo.
- **Recetas de la entrega:** fijadas al programar y no cambian al reasignar. Cada una termina *pendiente*, *descontada* (con su entrega del 03) o *no descontada* (con causa y, cuando se revisa, quién y cuándo). Como hay una sola entrega abierta por paciente y cada receta pertenece a un paciente, una receta está a lo más en una entrega abierta.
- **Intento:** número correlativo por entrega, fecha programada, encargado y resultado: *pendiente*, *entregada*, *no entregada* (motivo y nota), *reasignado* o *anulado*. A lo más un intento pendiente por entrega. El resultado guarda quién lo registró, el instante del servidor y un identificador de operación único para la idempotencia.
- **Motivos de no entrega:** *no había nadie para recibir*, *domicilio no encontrado*, *camino intransitable*, *paciente o cuidador rechaza la entrega*, *paciente no se encuentra en el domicilio* y *otro* (nota obligatoria).
- **Fechas:** solo día, sin hora ni franja. La jornada usa `America/Santiago`. El resultado se registra desde la fecha programada en adelante, también con atraso, y siempre con la hora real del servidor.
- **Descuento:** usa el contador del 03 y su restricción de cupo (`receta_contador_en_cupo`). La vigencia se evalúa en la fecha de la visita, no en la de programación. La entrega de receta generada no tiene turno.
- **Historial:** nada se borra. Los intentos, resultados y anulaciones son definitivos; para corregir un error se reasigna o se anula, y queda el rastro.
- **Lote de programación** *(2026-11-13, Borrador)*: no es un modelo nuevo. Al revisar nace un identificador de lote, y la lista revisada (pacientes, fecha y encargado) viaja firmada a la confirmación. Cada entrega del lote usa como identificador de operación uno derivado del lote y del paciente: así un reenvío, completo o por partes, devuelve la entrega ya creada. Los omitidos y sus motivos solo se muestran en el resumen final y no se guardan. Lo programado queda en «Programación» y en la auditoría de cada entrega. Las recetas se recalculan al confirmar, como en la programación individual.
- **Motivo del reparto** *(2026-11-13)*: se deriva y no se guarda. Un paciente puede tener varios motivos a la vez (postrado y 80 años o más, por ejemplo) y aparece en el filtro de cada uno.
- **Datos sintéticos:** el padrón de 670 pacientes de demostración (70 postrados y 600 mayores de 80) sirve como base. Las herramientas y pruebas generan domicilios y fotos sintéticas (imágenes generadas, nunca fotos reales de viviendas).

## Criterios de aceptación

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-08-01 | *(2026-11-13)* Pacientes de 79 años y 364 días, 80 años recién cumplidos, 81 años, postrado de 50 y crónico de 60 sin excepción | Son elegibles el de 80, el de 81 y el postrado. En el tótem, el de 80 recibe «Consulta tu despacho con el personal» sin número y el de 79 años y 364 días recibe preferencial. |
| RF-08-02 | Inscribir al crónico de 60 con «sin red de apoyo»; inscribirlo otra vez; inscribir al de 80 | Uno vigente; la segunda inscripción se rechaza; el de 80 se rechaza por ya ser elegible. |
| RF-08-02 | Retirar la excepción con una entrega abierta | Excepción retirada con autor y fecha; la entrega sigue abierta. |
| RF-08-03 | Crear un domicilio desde la dirección del padrón; reimportar el padrón con otra dirección | El domicilio no cambia; se muestra pendiente con «La dirección del padrón cambió» y la dirección nueva. |
| RF-08-03 | Dos ediciones del mismo domicilio desde la misma versión | La primera se guarda; la segunda recibe el aviso y no sobrescribe. |
| RF-08-04 | Verificar sin sector; verificar con sector; cambiar las referencias | Rechazo; verificado con autor y hora; vuelve a pendiente. |
| RF-08-04 | La Q.F. o el superusuario intentan verificar | Rechazo; sin cambios. |
| RF-08-05 | Subir un JPEG con datos GPS en EXIF; un PNG; un PDF renombrado .jpg; uno de 6 MB; una cuarta foto | Los dos primeros se guardan como JPEG sin metadatos; los demás se rechazan con un mensaje claro. |
| RF-08-05 | Pedir la URL de una foto sin sesión, como Encargado y por la ruta pública `/media/` | 302 a inicio de sesión; 200 con `no-store`; la ruta pública no existe. |
| RF-08-06 | Programar a un paciente con 3 recetas: una vigente, una vencida y una en un turno activo | La entrega lleva solo la vigente. |
| RF-08-06 | Programar dos veces al mismo paciente; repetir el POST | Una sola entrega abierta; el segundo intento enlaza a la existente. |
| RF-08-06 | Fecha de ayer; encargado inactivo; paciente no elegible; sin recetas elegibles | Rechazo con motivo; sin cambios. |
| RF-08-07 | Una excepción con entrega abierta emite turno en el tótem con todas sus recetas en la entrega | Mensaje de despacho programado sin datos personales; no se consume número. |
| RF-08-07 | El Técnico confirma en farmacia una receta de entrega abierta; se anula la entrega y confirma otra vez | Primero rechazo con motivo; luego se registra la entrega. |
| RF-08-08 | Un encargado con intentos de hoy, de ayer sin resultado y de mañana; otro encargado | Ve hoy y la atrasada rotulada, y mañana aparte; no ve las del otro encargado. |
| RF-08-09 | Registrar «entregada» con dos recetas, una vencida ayer | Una descontada (contador +1); la otra «no descontada» con causa; la entrega se cierra. |
| RF-08-09 | Repetir el POST; intento de mañana; intento de otro encargado | Mismo resultado sin otro descuento; rechazo; rechazo. |
| RF-08-10 | «No entregada» sin motivo; con «Otro» sin nota; con «nadie en casa» | Rechazo; rechazo; pendiente de gestión, sin descuento. |
| RF-08-11 | Filtrar por «domicilio no encontrado» y sector Verde; reasignar a mañana con otro encargado | El intento 1 queda igual y el 2 aparece en «Mis entregas» del nuevo encargado. |
| RF-08-11 | Reasignar un intento programado sin resultado; anular con «retirará en farmacia» | El intento queda «reasignado» y nace el siguiente; la entrega queda anulada y sus recetas se pueden dispensar en farmacia. |
| RF-08-12 | Marcar revisada una receta no descontada | Sale de la lista con autor y fecha. |
| RF-08-13 | Entrar como Técnico, Q.F., Encargado y superusuario | Menú y pestañas según la matriz; el Técnico no ve botones de cambio; el inicio del encargado abre «Mis entregas». |
| RF-08-14 | Anónimo, cuenta inactiva o sin perfil, Técnico haciendo POST, POST sin CSRF | Acceso rechazado; ninguna acción se ejecuta; la auditoría no contiene RUT, nombres, direcciones, notas ni coordenadas. |
| RF-08-15 | Al menos tres escenarios concurrentes con hilos y conexiones separadas | Cero entregas abiertas duplicadas, resultados dobles o descuentos dobles; el cupo nunca se excede; ninguna receta queda a la vez en un turno activo y en una entrega abierta. |
| RF-08-16 | Abrir «Programar entrega» con 670 pacientes sintéticos | Se ven los elegibles en páginas de 50 con su cantidad total; la URL no tiene RUT ni nombres. |
| RF-08-16 | Escribir «Gonz» letra por letra; luego filtrar sector Verde, motivo «80 años o más», estado «Sin registrar» y una localidad | La lista y la cantidad cambian sin recargar; solo quedan los que cumplen todo; la cantidad se anuncia en una región `aria-live`; el foco sigue en el campo. |
| RF-08-16 | Filtrar «Sin sector»; un paciente con entrega abierta en la lista; sin JavaScript | Aparecen los sin domicilio o sin sector; el paciente con entrega abierta está rotulado, enlazado y sin casilla activa; la búsqueda y los filtros funcionan con «Buscar». |
| RF-08-17 | Marcar 3 en la página 1 y 2 en la página 2; buscar otra cosa y volver | Siguen marcados los 5; «Programar seleccionados (5)». |
| RF-08-17 | «Seleccionar los N filtrados» con 120 filtrados, de los cuales 4 tienen entrega abierta y 2 no tienen recetas; fecha de mañana y un encargado | El resumen muestra 114 a programar, sus recetas, y 6 que no se programarán con su motivo; al confirmar: «Se programaron 114 de 120», los 114 aparecen en «Programación» con esa fecha y encargado. |
| RF-08-17 | Cambiar un filtro después de «Seleccionar los N filtrados» | La selección de todos los filtrados se anula y se avisa con texto. |
| RF-08-17 | Repetir la confirmación del mismo lote (doble clic, recarga o corte de red a mitad) | Ninguna entrega duplicada; los ya programados se informan como programados. |
| RF-08-17 | Dos Q.F. programan lotes que comparten pacientes al mismo tiempo; un lote mientras el tótem emite a una excepción del lote | Cada paciente queda con una sola entrega abierta y sale como omitido en el otro lote; ninguna receta queda a la vez en un turno activo y en una entrega abierta. |
| RF-08-17 | Fecha de ayer; encargado inactivo; Técnico que hace el POST; contexto firmado alterado | Rechazo con motivo y sin cambios; 403 para el Técnico; la firma alterada se rechaza. |

## No funcionales

- Solo datos sintéticos y ORM de Django, sin SQL crudo. Compatible con PostgreSQL y con la SQLite temporal de las herramientas. Sin `select_for_update()`: UPDATE condicional, restricciones únicas, transacciones y reintentos acotados (RNF-02). Los UPDATE condicionales filtran solo campos propios, nunca relaciones (regla de PostgreSQL de CLAUDE.md).
- Respuesta de 2 s o menos en el p95 para las consultas y acciones del módulo, con el padrón de 670 pacientes, cientos de entregas y fotos de prueba (RNF-05). La subida de fotos se mide aparte y se informa sin prometer un valor para redes móviles.
- WCAG 2.1 AA (RNF-04): «Mis entregas» se diseña primero para celular, con botones de 48 px o más, texto ampliable y sin desplazamiento horizontal. Estados y verificación con texto y no solo con color, foco visible, teclado y descripciones obligatorias en las fotos. La revisión de navegador, axe y la usabilidad con cinco personas requieren evidencia propia.
- Privacidad (RNF-01): los datos de pacientes y las fotos solo aparecen en vistas privadas autorizadas. Las fotos no se publican en `/media/` ni van al repositorio, y pierden todos sus metadatos. La ubicación del navegador solo se pide con un gesto del usuario y no se guarda la del encargado, solo la del domicilio.
- La ubicación del navegador exige contexto seguro (HTTPS o `localhost`). Sin él, el botón explica con texto que hay que ingresar las coordenadas a mano.
- *(2026-11-13)* RNF-05 en la lista y la programación de varios: la lista, cada actualización de la búsqueda o los filtros y cada tramo de la confirmación responden en 2 s o menos en el p95. Como el lote no tiene tope, el navegador lo envía en tramos de hasta 25 pacientes. El tiempo total de un lote grande (el padrón completo, por ejemplo) se mide y se informa aparte, como la subida de fotos, sin prometer un valor. La revisión de un lote completo también se mide.
- *(2026-11-13)* WCAG 2.1 AA: casillas con etiqueta que nombra al paciente, cantidad de seleccionados y de resultados anunciada con texto, avance con `<progress>` y texto, foco visible y uso completo con teclado. Actualizar la lista no cambia el contexto ni mueve el foco (criterio 3.2.2).

## Compatibilidad

Conservar el padrón y la importación del 03 (no se escribe en `Paciente`), el contador y la elegibilidad de recetas del 03, el tótem y el comprobante del 04, la cola y el cierre del 05, la sala del 06 y la preparación y el retiro del 07. Los cambios en servicios existentes son aditivos:

- `recetasapp`: un camino nuevo en el servicio de entregas para el despacho a domicilio y una validación nueva que rechaza las recetas con entrega abierta en los otros caminos.
- `turnosapp`: la emisión omite las recetas con entrega abierta y la regla de postrado o mayor de 80 pasa a una función compartida, sin cambiar su resultado.

Todo cambio en la emisión exige las pruebas concurrentes de CLAUDE.md. Las pruebas del 03 al 07 deben pasar sin cambiar sus aserciones.

*(2026-11-13, Borrador)* Excepción explícita: el RF-08-01 modificado cambia el contrato del 04 (RF-04-02, RF-04-04 y la regla de edad de sus «Datos y reglas»: «exactamente 80 sigue presencial»). Cambian solo las aserciones del límite de edad del tótem (80 años: de preferencial a bloqueo; se agrega 79 como preferencial). Las demás pruebas del 03 al 07 siguen sin cambios. Al implementar se anota el cambio en el `spec.md` del 04 con referencia a este spec. El 04 se trabajó en `fdaza`: conviene avisar al equipo.

Preparación para otros specs:
- El registro de resultados acepta un identificador de operación generado por el cliente, que la reserva 11 reutilizará para sincronizar sin duplicados.
- La programación acepta un paciente preseleccionado por su identificador interno, para que el panel de mermas del spec 10 derive pacientes no retirados.
- Las coordenadas quedan disponibles para el mapa y el orden de visita del 09.

Las dependencias existen en `specs/`. Sus pendientes de aceptación visual y funcional no se dan por cerrados aquí.

## Decisiones tomadas y alternativas

- **Ciclo completo en un spec** (decisión del usuario, recomendada). Incluye HU-12, HU-13, la parte con conexión de HU-15 y HU-16, porque HU-16 no tiene sentido sin el registro de «no entregada». Esto reemplaza la división propuesta antes en la sesión, en la que HU-15 iba en el 09. El 09 queda para el mapa y el orden de visita (HU-14).
- **`Domicilio` como modelo aparte** (decisión del usuario, recomendada). La importación del 03 sobrescribe `Paciente.direccion`; si el domicilio verificado viviera ahí, una carga borraría el trabajo de terreno. El cambio de la dirección del padrón no se escribe en el domicilio, sino que se detecta y lo deja pendiente. Se descartan los campos en `Paciente` y un domicilio desconectado del padrón.
- **Sector MAIS más localidad** (decisión del usuario, recomendada). Permite filtrar por sector y agrupar visitas. Se descarta el texto libre.
- **Coordenadas y fotos** (decisión del usuario; se recomendaba sin fotos). Consecuencias: una dependencia nueva (Pillow), almacenamiento privado fuera de `/media/`, recompresión sin metadatos y una vista con rol para servirlas. Se limitan a tres fotos privadas y con descripción obligatoria, por decisión del usuario.
- **Elegibles: postrados, mayores de 80 y excepciones** (decisión del usuario). El corte de edad era `edad > 80`, igual que el tótem y el informe (se corrigió una pregunta que decía «80 o más»). Las excepciones usan un catálogo y no vencen (decisión del usuario, recomendada).
- **Corte de edad: 80 años o más** *(decisión del equipo, 2026-11-13; reemplaza el corte anterior)*. El usuario pidió que entren los de 80 años, no solo desde los 81. El informe dice «mayores de 80 años»; el equipo lo interpreta como 80 cumplidos o más y lo deja anotado aquí, como pide CLAUDE.md cuando una decisión se aparta del texto del informe. **Una sola regla para el tótem y el reparto** (decisión del usuario, recomendada): así no hay una persona de 80 años que saque número presencial y a la vez tenga despacho. Se descarta separar las reglas.
- **Programación de varios pacientes a la vez** *(decisión del usuario, 2026-11-13; antes estaba fuera del spec)*. Se agrega con «Seleccionar los N filtrados».
  - **Cada paciente por separado** (recomendada): se programan los válidos y se informan los omitidos, como la importación del padrón fila por fila. Se descarta todo o nada, porque un solo caso detendría al resto.
  - **Resumen para revisar y confirmar una vez** (recomendada). Se descarta programar sin revisión previa.
  - **Sin tope** (decisión del usuario; se recomendaba un tope de 50). Para cumplir RNF-05, el navegador envía el lote en tramos y muestra el avance. Se descartan la lista de solo la página visible y procesar el lote completo en una sola solicitud.
  - **Sin modelo nuevo**: lista revisada firmada y operación derivada del lote y el paciente. Se descarta guardar el lote y sus omitidos (`LoteProgramacion`), que exigiría una migración sin una consulta que la necesite.
- **Lista completa al entrar, con búsqueda en vivo** (decisión del usuario, recomendada). Permite elegir un sector completo sin escribir. Se descarta mostrar la lista solo al escribir.
- **Cuatro filtros: sector, motivo, estado del domicilio y localidad** (decisión del usuario). La localidad se elige de una lista de las ya registradas, para no duplicar la barra de búsqueda.
- **Descuento al registrar «entregada»** (decisión del usuario, recomendada). Así hay un único contador «n de m» para farmacia y domicilio. Se descartan el descuento al despachar (exigiría revertirlo si no se entrega) y la entrega sin recetas (el contador quedaría desalineado).
- **Solo se descuentan las recetas válidas en la fecha de la visita** (decisión del usuario, recomendada). El encargado no decide en terreno y la Q.F. revisa lo no descontado. A diferencia del retiro del 07, la vigencia se evalúa en la fecha de la visita.
- **Una entrega abierta por paciente** (decisión del usuario, recomendada), garantizada por una restricción única parcial. De ella se deduce que una receta está a lo más en una entrega abierta.
- **Entrega con intentos** (decisión del usuario, recomendada). El historial de HU-16 vive en filas inmutables de un mismo caso. Se descartan las entregas encadenadas.
- **Motivos de catálogo con nota** (decisión del usuario, recomendada). Permiten filtrar en HU-16 y en el panel de mermas. La nota es corta, opcional salvo con «Otro», y nunca entra a la auditoría.
- **Bloqueo de doble vía** (decisión del usuario, recomendada). Evita dispensar dos veces la misma receta. Afecta sobre todo a las excepciones, porque el tótem ya bloquea a postrados y mayores de 80. Consecuencia: cambia la emisión del 04 y la confirmación del 03, con pruebas concurrentes. La simetría (no programar recetas con turno activo o pendientes de retiro) se deduce de la misma decisión.
- **Permisos según las HU** (decisión del usuario, recomendada). Solo el encargado verifica y registra resultados; el superusuario actúa como Q.F., una excepción explícita a su acceso general.
- **Una entrada «Entregas» en el menú** (decisión del usuario, recomendada); el inicio del encargado pasa a «Mis entregas».
- **Solo fecha, sin franja horaria** (decisión del usuario, recomendada). Se puede registrar con atraso, siempre con la hora real.

## Supuestos y decisiones pendientes

Supuestos técnicos reversibles, sujetos a revisión del borrador:
- Los catálogos de motivos (no entrega, excepción y anulación) son propuestas del prototipo, no una política del CESFAM.
- El domicilio se crea al guardarlo por primera vez; la lista muestra a los elegibles sin domicilio como «sin registrar».
- La Q.F. y el encargado pueden agregar y borrar fotos (forma parte de editar el domicilio).
- Se puede programar a un paciente con domicilio pendiente o sin registrar; la programación y «Mis entregas» lo advierten con texto.
- Las recetas de una entrega no cambian al reasignar. Si se renovó una receta en el intertanto, la Q.F. anula y programa de nuevo.
- El encargado ve el nombre, el RUT y el teléfono del paciente en vistas privadas, como el resto del personal ve el padrón.
- Las fotos se reducen a 1600 px en su lado mayor y se guardan como JPEG de calidad 80.
- Nombres de modelos, rutas y servicios son propuestas del `plan.md`.

Supuestos de la ampliación del 2026-11-13, sujetos a revisión del borrador:
- Las inscripciones de excepción vigentes de pacientes que ya tienen 80 años se conservan; no se retiran solas. El paciente pasa a ser elegible también por edad y ambos motivos se muestran.
- La lista de «Programar entrega» usa la elegibilidad a hoy. La revisión del lote la recalcula a la fecha elegida.
- La búsqueda se actualiza unos 300 ms después de la última tecla. Las respuestas que llegan fuera de orden se descartan.
- La localidad se agrupa sin distinguir mayúsculas ni espacios de los extremos («Dadinco» y «dadinco » son la misma).
- Un lote usa un solo encargado; la distribución entre varios queda fuera.
- El flujo individual («Elegir» y `?paciente=` para el spec 10) se conserva sin cambios.

No hay bloqueos críticos para redactar. Por confirmar: los catálogos de motivos.

## Enmienda del 2026-11-15 (Borrador)

Pedida por el usuario el 2026-11-15, junto con la [enmienda del spec 09](../09-mapa-y-orden-de-visita/spec.md#enmienda-del-2026-11-15-borrador). Allí están las tarjetas compactas, el arrastre, OSRM y «Usar mapa». Este spec recibe la parte que es suya: fotos, visor y textos. Se trabaja en `crojas-base`. La versión aprobada sigue vigente hasta que el usuario apruebe la enmienda.

**Objetivo de la enmienda:** gestionar las fotos del domicilio en un modal que aplica todos los cambios juntos, verlas ampliadas en un visor y aclarar dos textos.

**Motivo de la reversión anotada en este spec:** la exclusión «Marcar el punto del domicilio en un mapa» ya enviaba ese cambio al 09. El 09 lo agrega ahora como «Usar mapa» (RF-09-25), porque con direcciones rurales ambiguas permite ubicar el domicilio desde la oficina, sin estar en el lugar. Las coordenadas siguen siendo opcionales y se siguen ingresando también a mano o con la ubicación del celular.

**Permisos:** no cambian. Gestionan fotos el encargado, la Q.F. y el superusuario (RF-08-05). En «Mis entregas», el botón de fotos lo ve solo el encargado; en «Rutas» no aparece; en «Detalles del domicilio», lo ven los tres. El Técnico solo ve las fotos y el visor.

**Fuera de la enmienda:** guardar fotos sin conexión o en cola para enviarlas después (reserva 11), editar la descripción de una foto ya guardada, recortar o girar imágenes en el navegador, más de tres fotos y cambios en `FotoDomicilio` o en el procesamiento de imágenes. La enmienda no tiene migraciones.

### Requisitos de la enmienda

- **RF-08-18 — Registrar o gestionar fotos en un modal** *(modifica RF-08-05 en la forma de agregar y borrar)*: EL SISTEMA muestra el botón «Registrar fotos» si el domicilio no tiene fotos y «Gestionar fotos» si tiene de 1 a 3, en la tarjeta expandida de «Mis entregas» (RF-09-16) y en «Detalles del domicilio». El botón abre un modal con:
  - las fotos actuales, cada una con «Borrar», que la marca para borrar y se puede deshacer;
  - espacios para fotos nuevas hasta completar 3, contando las marcadas para borrar. Con 3 fotos y ninguna marcada, solo permite borrar;
  - en cada espacio nuevo, «Elegir archivo» y «Sacar foto» (abre la cámara del celular con `capture="environment"`; en computador abre el selector de archivos), una vista previa y la descripción obligatoria de hasta 120 caracteres, que sirve de texto alternativo;
  - el recordatorio de no fotografiar personas ni patentes;
  - los botones «Guardar» y «Cancelar».

  Nada cambia hasta pulsar «Guardar». Entonces EL SISTEMA valida y procesa todas las fotos nuevas con las reglas del RF-08-05 y aplica en una sola transacción los borrados y las fotos nuevas: todo o nada.
  - SI una foto nueva falla (no es imagen, está dañada, pesa más de 5 MB o le falta la descripción), ENTONCES no se aplica ningún cambio y el aviso indica cuál, numerada en el orden del modal: «La foto 2 no se pudo procesar», con el motivo. El modal sigue abierto con lo elegido.
  - SI las fotos del domicilio cambiaron desde que se abrió el modal (otra persona agregó o borró una), ENTONCES no se aplica nada y se avisa: «Las fotos de este domicilio cambiaron en otro dispositivo. Cierra y vuelve a abrir para ver las actuales.».
  - SI no hay conexión, ENTONCES no se guarda nada y se dice con texto (RF-09-26).
  - «Cancelar», Esc o la X descartan todo lo elegido. El foco queda dentro del modal mientras está abierto y vuelve al botón que lo abrió.
  - Sin JavaScript, el botón lleva a una página con el mismo formulario y las mismas reglas.

  Cada foto agregada y cada foto borrada quedan en la auditoría, dentro de la misma transacción y sin datos personales. Los archivos de las fotos borradas se eliminan solo después de confirmar la transacción, y los de las fotos nuevas se eliminan si la transacción falla. Se retiran los formularios separados «Agregar foto» y «Borrar foto». Agregar o borrar fotos no cambia la verificación (RF-08-04).
- **RF-08-19 — Visor de imagen:** CUANDO alguien que puede ver el domicilio pulsa una miniatura (en la tarjeta de «Mis entregas», en «Rutas» o en «Detalles del domicilio»), EL SISTEMA abre un visor con la imagen ampliada, su descripción como texto alternativo y como pie, y una X en la esquina (48 px o más, con el nombre «Cerrar»). Se cierra con la X, con un clic fuera de la imagen o con Esc. Mientras está abierto, el foco queda dentro del visor; al cerrar, vuelve a la miniatura. La miniatura es un botón con nombre («Ver foto ampliada: descripción»). La imagen se sirve con la vista privada actual, sin caché. Sin JavaScript, la miniatura es un enlace a la imagen.
- **RF-08-20 — Textos:**
  - «Ver domicilio» pasa a «Detalles del domicilio» en todos los lugares donde aparece: tarjetas, «Ir a esta parada», resumen de los marcadores, lista de Domicilios y ficha del paciente. «Registrar domicilio» y «Ver domicilios» (la lista) no cambian.
  - «Localidad» pasa a «Nombre de la localidad» en el formulario del domicilio, en su ficha y en el filtro de «Programar entrega».
  - Solo cambian los textos: no cambian el modelo, la base ni los valores de los filtros.

### Criterios de aceptación de la enmienda

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-08-18 | Domicilio sin fotos; con 2; con 3 | «Registrar fotos» con 3 espacios; «Gestionar fotos» con 1 espacio; con 3, solo «Borrar», y al marcar una aparece un espacio. |
| RF-08-18 | Borrar 1 y agregar 2 (una JPEG con GPS en EXIF y una PNG) y guardar | Quedan 3 fotos JPEG sin metadatos; la borrada desaparece junto con su archivo; 3 entradas de auditoría. |
| RF-08-18 | Agregar 2 fotos, la segunda es un PDF renombrado .jpg, más un borrado | «La foto 2 no se pudo procesar»; ningún cambio en la base ni en los archivos; el modal sigue abierto. |
| RF-08-18 | Foto sin descripción; descripción de 121 caracteres; «Cancelar» con cambios elegidos | Rechazo con texto y sin cambios; cancelar no cambia nada. |
| RF-08-18 | Dos dispositivos guardan desde el mismo estado; uno guarda mientras el otro borra; dos guardan agregando fotos con 2 ya guardadas | Uno gana y el otro recibe el aviso; nunca más de 3 fotos; ningún archivo huérfano (tres escenarios con hilos). |
| RF-08-18 | El Técnico hace el POST; POST sin CSRF; sin JavaScript | 403; rechazo; la página aparte aplica las mismas reglas. |
| RF-08-19 | Abrir una miniatura; cerrar con la X, con clic fuera y con Esc; recorrer con Tab | Imagen ampliada con su descripción; se cierra de las tres formas; el foco no sale del visor y vuelve a la miniatura. |
| RF-08-20 | Recorrer las pantallas del 08 y el 09 | No queda «Ver domicilio»; el formulario, la ficha y el filtro dicen «Nombre de la localidad». |

### No funcionales de la enmienda

- RNF-05: el guardado de fotos sin archivos grandes responde en 2 s o menos en el p95. Con tres fotos de 5 MB se mide e informa aparte, sin prometer un valor para redes móviles, como la subida actual.
- WCAG 2.1 AA (RNF-04): diálogos con nombre, foco contenido que vuelve al control que los abrió, botones de 48 px o más y errores en texto asociados a su campo y anunciados.
- Privacidad (RNF-01): fotos privadas, sin metadatos y nunca en `/media/`. Solo imágenes sintéticas en las pruebas y en el lienzo de diseño.

### Decisiones de la enmienda

- **Todo o nada al guardar** (decisión del usuario). Se descarta aplicar las fotos que sí se procesaron, porque el encargado vería un estado distinto del que eligió.
- **Un solo modal también en «Detalles del domicilio»** (decisión del usuario, recomendada). Una sola forma de gestionar fotos; se retiran los formularios separados.
- **Cámara del celular con `capture`** (decisión del usuario, recomendada). No pide permiso de cámara al sitio. Se descarta la vista previa en vivo con `getUserMedia`.

### Supuestos de la enmienda

Supuestos técnicos reversibles, sujetos a la revisión del borrador:
- Las fotos nuevas y los borrados viajan en una sola solicitud. Para saber si las fotos cambiaron, el modal envía la lista de fotos que mostró.
- Marcar una foto para borrar libera su espacio en el mismo guardado; la regla «con 3 solo permite borrar» se aplica mientras no haya ninguna marcada.
- La numeración del aviso («La foto 2») cuenta solo las fotos nuevas, en el orden en que aparecen en el modal.

## Revisión y cambios

2026-11-11: cuatro bloques de preguntas: alcance (ciclo completo), domicilio aparte, sector MAIS con localidad y coordenadas con fotos; elegibles con excepciones, descuento al entregar, una entrega abierta por paciente y permisos; fotos, motivos, intentos y vigencia; menú, excepciones, fecha y doble vía. Se corrige el corte de edad a «mayores de 80». Se guardan los cuatro documentos como Borrador, sin código ni migraciones.

2026-11-11 (implementación, `crojas-base`): T-08-01 a T-08-08 ejecutadas sin cambiar requisitos. Ajustes técnicos anotados en [plan.md](plan.md#notas-de-implementación-2026-11-11): el inicio del encargado muestra «Mis entregas» en `/` sin redirigir (los specs anteriores esperan 200 en `/`); la reasignación exige el último intento y el resultado que la Q.F. vio (lo exige RF-08-15); la reincorporación del 05 se rechaza si una receta del turno está en una entrega abierta; `IntentoEntrega.creado_con` hace idempotente la reasignación. Estado: sigue **Aprobado**; navegador, axe, usabilidad y aceptación pendientes.

2026-11-13 (ampliación, Borrador): el usuario pidió filtros y búsqueda en vivo en «Programar entrega», «seleccionar todo» y el corte de edad de 80 años o más. Hubo dos bloques de preguntas:
- **Primer bloque:** programar varios a la vez; filtros de sector, motivo, estado del domicilio y localidad; una sola regla de 80 o más también para el tótem; el selector de punto en el mapa del domicilio va al spec 09.
- **Segundo bloque:** programar los válidos e informar los omitidos; resumen para revisar y confirmar; «Seleccionar los N filtrados» sin tope; lista completa al entrar.

Se modifican RF-08-01 y sus criterios, y se agregan RF-08-16 y RF-08-17 y las tareas T-08-09 a T-08-13 (propuestas). La versión aprobada del 2026-11-11 sigue vigente hasta que el usuario apruebe la ampliación. Sin código, migraciones ni cambios en otros specs.

2026-11-13 (implementación de la ampliación, `crojas-base`): T-08-09 a T-08-13 ejecutadas sin cambiar requisitos. Ajustes técnicos en [plan.md](plan.md#notas-de-implementación-de-la-ampliación-2026-11-13). El cambio de edad del 04 quedó anotado en su [spec.md](../04-emision-de-turnos/spec.md). Los rótulos «Borrador» dentro de los requisitos de la ampliación conservan el texto aprobado; la cabecera manda. Estado: sigue en **Aprobado**; quedan pendientes el navegador, axe, la usabilidad y la aceptación.

2026-11-15 (nota por la enmienda del spec 04): el tótem deja de bloquear a postrados y a personas de 80 años o más, y los rechazos usan un mensaje neutro. Los criterios de RF-08-01 (fila del tótem) y RF-08-07 sobre los mensajes del tótem quedan reemplazados por los del spec 04. El bloqueo de doble vía se conserva: una receta en una entrega abierta nunca se vincula a un turno. Sin cambios en los requisitos de reparto ni en el código del 08.

2026-11-15 (enmienda, Borrador): junto con la enmienda del 09, el usuario pidió el modal de fotos con guardado todo o nada, el visor de imagen y los textos «Detalles del domicilio» y «Nombre de la localidad». Se agregan RF-08-18 a RF-08-20 y las tareas T-08-14 a T-08-16 (propuestas), sin código ni migraciones. Ver [Enmienda del 2026-11-15](#enmienda-del-2026-11-15-borrador).

2026-11-15 (aprobación de la enmienda): el usuario revisó el lienzo de diseño y aprobó la enmienda («Apruebo todos los cambios»). Implementación pendiente: primero T-08-14 a T-08-16, luego T-09-11 a T-09-18 del 09.

2026-11-15 (implementación de la enmienda, `crojas-base`): T-08-14 a T-08-16 ejecutadas sin cambiar requisitos ni migraciones. Ajustes técnicos en [plan.md](plan.md#notas-de-implementación-de-la-enmienda-2026-11-15): se retiran `agregar_foto` y `eliminar_foto`; un UPDATE sin cambio sobre la fila del domicilio ordena los guardados simultáneos, y el modal y el visor no dependen del evento `close`. Hasta las tarjetas compactas del 09, el botón de fotos va en la fila de acciones de la tarjeta. Estado: sigue **Aprobado**; quedan pendientes la cámara y la red reales, axe, el lector de pantalla, la usabilidad y la aceptación.

2026-11-16 (reducción de fotos en el navegador, pedida por el usuario; complementa RF-08-18, sin migraciones ni cambios en el servidor): antes la foto viajaba tal como la sacaba el celular y solo se recomprimía en Django, así que una foto de más de 5 MB se rechazaba y en zonas con poca señal se subía el archivo completo. Ahora `fotos.js`, al elegir o sacar la foto, la redibuja en un lienzo con el lado mayor de 1600 px y la codifica como JPEG con calidad 0,85; la vista previa dice el tamaño con que se enviará («4,8 MB (se enviará reducida: 0,4 MB)») y «Guardar» envía esa versión, que ya no lleva EXIF ni ubicación porque el lienzo no los copia. La orientación se aplica al decodificar (`createImageBitmap` con `imageOrientation: "from-image"` o una `<img>`), y la transparencia de un PNG queda sobre blanco. Una foto de hasta 1600 px y 500 KB no se toca. Si el navegador no puede reducirla, o la reducida no pesa menos, se envía la original y el servidor la valida como siempre. `coreapp/utils/custom_image.py` sigue validando y recomprimiendo todo lo que llega. La página sin JavaScript no reduce.
