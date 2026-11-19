# SPEC 11 — Reparto sin conexión

> **Estado:** Aprobado
> **Depende de:** [SPEC 01](../01-base-del-proyecto/spec.md), [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 08](../08-domicilios-y-entregas/spec.md), [SPEC 09](../09-mapa-y-orden-de-visita/spec.md), [SPEC 12](../12-notificaciones-reparto/spec.md) y [SPEC 13](../13-panel-de-mermas/spec.md)
> **Fecha:** 2026-11-18
> **Objetivo:** Que el encargado de terreno, sin señal, vea sus visitas de hoy y las atrasadas y registre «entregada» o «no entregada», y que esos registros lleguen al servidor sin pérdidas ni duplicados en 5 minutos o menos después de recuperar la señal.

Módulo solicitado: `entregasapp` (paquete de la ruta, sincronización y vista sin conexión) y `coreapp` (service worker de la PWA). Fuente: HU-14 y HU-15 (parte sin conexión), RNF-03, NS05, NS06 y RNF-09 del [informe](../../docs/Informe.md); reserva 11 del [índice](../README.md); respuestas de la usuaria del 2026-11-18.
Implementación autorizada: sí, el 2026-11-18 (`/spec-impl 11-reparto-sin-conexion` en `crojas-base`, sin rama nueva, todos los pasos sin pausas y con los documentos aún sin commit). Revisión de la usuaria: Aprobado, con los supuestos técnicos tal como están escritos; aceptación funcional pendiente.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

La comuna tiene 57,9 % de ruralidad y en varios sectores no hay señal móvil. Hoy «Mis entregas» y el registro de resultados (spec 08) exigen conexión: si el encargado llega a un domicilio sin señal, no puede ver los datos de la visita ni registrar lo que pasó, y tiene que anotarlo aparte y cargarlo después. El informe exige lo contrario: RNF-03 (Must) pide consultar y registrar sin señal y sincronizar el 100 % en 5 minutos o menos tras reconectar, sin duplicados (NS05).

El resultado se reconoce porque:

- con señal, al abrir «Mis entregas», el celular guarda la ruta del día; sin señal, la app abre la misma ruta desde el celular y avisa «Sin conexión»;
- el encargado registra «Entregada» o «No entregada» con su motivo sin señal, y la parada queda marcada «Registrada sin conexión · por enviar»;
- al volver la señal los registros se envían solos (o con «Sincronizar ahora»), cada uno una sola vez, y la Q.F. los ve con la hora en que ocurrieron y la hora en que llegaron;
- si la Q.F. reasignó o anuló la visita mientras tanto, el registro no se aplica, el encargado ve por qué y la Q.F. puede revisarlo en la auditoría.

## Actores y permisos

| Acción / datos | Anónimo | Técnico | Encargado de terreno asignado | Otro encargado | Q.F. | Director | Superusuario activo |
|---|---|---|---|---|---|---|---|
| Descargar el paquete de su ruta del día | No (login) | No (403) | Sí, solo sus visitas | Solo las suyas | No (403) | No (403) | No (403): no atestigua visitas, igual que en el 08 |
| Ver la ruta guardada en el celular sin señal | — | — | Sí, en el mismo navegador donde la descargó | No ve la de otro | — | — | — |
| Registrar entregada / no entregada sin señal | — | — | Sí, sobre sus visitas pendientes | — | — | — | — |
| Sincronizar registros guardados | No (login) | No (403) | Sí, solo los que hizo con su propia cuenta | Rechazados con `otro_usuario` | No (403) | No (403) | No (403) |
| Ver la hora del registro y la de llegada en el detalle | No | Sin cambios respecto del 08 | Sí (sus visitas) | — | Sí | Sin cambios | Sí |

Se revalidan en el servidor la cuenta activa, el perfil y el rol único (spec 02) en cada descarga y en cada sincronización. El encargado se comprueba de forma exacta (sin `tiene_rol`), igual que en el 08. Un usuario inactivo o con sesión vencida no puede sincronizar: la cola sigue en el celular hasta que vuelva a entrar con la misma cuenta.

## Alcance y exclusiones

Incluye:

- el service worker con caché versionada de la interfaz (estilos, scripts, fuentes, íconos) y una página sin conexión, sin datos personales;
- el paquete de la ruta del día del encargado (hoy y atrasadas), guardado en el celular con los datos de la tarjeta;
- la vista sin conexión de la ruta y del registro de resultados, en el orden guardado del 09;
- la cola local de registros con su identificador de operación y la sincronización automática, por Background Sync donde exista y por un botón;
- la hora del registro tomada del celular, con límites, y la hora de llegada al servidor;
- el rechazo de registros en conflicto, visible para el encargado y auditado;
- la regla de los avisos del 12 para registros que llegan tarde;
- el borrado de los datos del celular al cerrar sesión, al cambiar el día y cuando entra otra cuenta;
- pruebas concurrentes, pruebas del JavaScript y medición HTTP aislada de NS05.

No incluye:

- «Iniciar traslado» sin señal: avisar «en camino» horas después no sirve; sigue exigiendo señal;
- fotos del domicilio, verificar domicilios, editar direcciones y cambiar el orden de las paradas sin señal: siguen exigiendo señal (RF-09-26 y enmienda del 08);
- mapa base, teselas, tramo por camino, «Sugerir parada más cercana» e «Ir a esta parada» sin señal: la política de OpenStreetMap prohíbe la descarga masiva y un mapa propio de Ñuble merece otro spec;
- vistas de la Q.F., el Técnico, el Director, el tótem y la sala sin conexión;
- cifrar la base del navegador: se mitiga con datos mínimos y borrado (ver decisiones);
- notificaciones push y SMS (spec 12, fuera de este alcance);
- una app nativa (fuera del alcance del proyecto);
- datos reales: solo el padrón y los domicilios sintéticos.

## Historias y flujo

1. **Preparación con señal.** El encargado abre «Mis entregas» en el CESFAM o en cualquier punto con señal. La página descarga el paquete del día y muestra «Ruta guardada en este celular a las 08:12 · 14 visitas». Si algo cambia (la Q.F. programa o reasigna), basta volver a abrir «Mis entregas» con señal para actualizarla.
2. **Sin señal.** Al abrir la app o recargar una página del reparto sin señal, el service worker muestra la vista sin conexión: aviso «Sin conexión», hora de la última descarga y la lista de paradas en el orden guardado, con nombre, dirección, referencias, localidad, sector, teléfono y cantidad de recetas. El mapa no se muestra; un texto explica que necesita señal.
3. **Registro sin señal.** En una parada, el encargado pulsa «Entregada» o «No entregada» (con motivo y nota opcional), confirma y la parada pasa a «Registrada sin conexión · por enviar», con la hora. Puede deshacer un registro que aún no se envió.
4. **Sincronización.** Al volver la señal, con la app abierta, los registros se envían solos en los primeros 30 segundos; en Chrome para Android también se envían con la app cerrada. El botón «Sincronizar ahora» fuerza el envío. El contador «N registros por enviar» baja a cero y cada parada muestra su resultado del servidor.
5. **Rechazo.** Si un registro no se aplica (visita reasignada o anulada, fuera de plazo, hora no válida), queda en «No se pudo enviar» con el motivo en palabras, hasta que el encargado pulse «Entendido». La Q.F. ve el rechazo en la auditoría.
6. **Cierre.** Al cerrar sesión se borra la ruta guardada. Si quedan registros sin enviar, la salida avisa antes cuántos son.

## Requisitos funcionales

- **RF-11-01 — Interfaz disponible sin señal.** EL SISTEMA registra un service worker que guarda en una caché versionada los estilos, scripts, fuentes, íconos y la página sin conexión. CUANDO cambia la versión de los estáticos, la caché anterior se borra al activarse el service worker nuevo. EL SISTEMA nunca guarda en la caché del service worker páginas privadas, respuestas JSON ni fotos: esas respuestas siguen con `Cache-Control: no-store`.
- **RF-11-02 — Paquete de la ruta.** CUANDO el encargado abre «Mis entregas» con señal, EL SISTEMA entrega un paquete con sus visitas pendientes de hoy y atrasadas, en el orden de `ruta_del_dia` (orden guardado o sugerido, spec 09), con: identificador del intento, número de parada, fecha programada, si está atrasada, nombre del paciente, dirección, referencias, localidad, sector, teléfono, cantidad de recetas, si el traslado ya se inició y la lista de motivos de no entrega. Lleva además la fecha local, la hora del servidor, el identificador interno de la cuenta y la versión del formato. EL SISTEMA no incluye el RUT, las fotos, las coordenadas, el correo para avisos ni los nombres de los medicamentos.
- **RF-11-03 — Guardado local acotado.** EL SISTEMA guarda el paquete solo en la base del navegador (IndexedDB) del origen de la app, ligado a la cuenta y a la fecha. SI la fecha del paquete no es la de hoy en el celular, o la cuenta que entró no es la del paquete, o se cierra sesión, ENTONCES el paquete se borra y la vista sin conexión dice «No hay una ruta guardada para hoy. Ábrela con señal».
- **RF-11-04 — Vista sin conexión.** SI una página del reparto no carga por falta de red, ENTONCES el service worker muestra la vista sin conexión, que dibuja la ruta desde el paquete. La vista dice siempre «Sin conexión» y la hora de la última descarga, con texto y no solo con color. Si no hay paquete válido, solo muestra el aviso del RF-11-03, sin datos.
- **RF-11-05 — Registro sin señal.** CUANDO el encargado confirma «Entregada» o «No entregada» sin señal (o el envío del formulario falla por la red), EL SISTEMA guarda en la cola local un registro con: identificador de operación (el del formulario, o uno nuevo generado en el celular), intento, resultado, motivo y nota (si no se entregó), hora del celular e identificador de la cuenta. La parada pasa a «Registrada sin conexión · por enviar». No se permite un segundo registro para el mismo intento mientras haya uno en la cola; el encargado puede deshacer uno que no se ha enviado. Las reglas del formulario del 08 (motivo obligatorio, nota de hasta 200 caracteres, «Otro» con nota) se validan también en el celular.
- **RF-11-06 — Sincronización.** CUANDO vuelve la conexión con la app abierta, EL SISTEMA envía la cola en menos de 30 segundos y luego reintenta cada 30 segundos mientras queden registros. Donde el navegador ofrezca Background Sync, también la envía con la app cerrada. El botón «Sincronizar ahora» la envía de inmediato. Se envía en lotes de hasta 50 registros por solicitud; el servidor responde por cada uno `aplicado`, `ya_aplicado` o `rechazado` con su código, y el celular quita de la cola los dos primeros. Un error de red, del servidor o de sesión deja el registro en la cola para el siguiente intento.
- **RF-11-07 — Sin duplicados.** EL SISTEMA aplica cada registro con los servicios del 08 (`registrar_entregada`, `registrar_no_entregada`) y su identificador de operación. Reenviar el mismo registro, enviarlo desde dos pestañas o desde la página y Background Sync a la vez da `ya_aplicado` y nunca descuenta dos veces una receta.
- **RF-11-08 — Hora del registro con límites.** EL SISTEMA guarda la hora del celular como hora del registro (`registrado_en`) y la hora de llegada como `sincronizado_en`. Rechaza con `hora_invalida` una hora más de 5 minutos posterior a la del servidor o de una fecha anterior a la fecha programada de la visita. Rechaza con `fuera_de_plazo` un registro que llega después de 2 días desde la fecha local del registro (llega a más tardar el día del registro + 2). La vigencia de las recetas se evalúa a la fecha local del registro, no a la de llegada; las recetas que viajan con su preparación (spec 13) siguen evaluándose a su fecha de preparación.
- **RF-11-09 — Conflictos.** SI al llegar el registro el intento ya no está pendiente (reasignado, anulado o con otro resultado) o ya no pertenece al encargado, ENTONCES EL SISTEMA no lo aplica, responde `rechazado` con el código (`reasignada`, `anulada`, `ya_registrada`, `no_asignada`) y registra en la auditoría `intento.sincronizacion_rechazada` con el código, sin la nota. Gana lo que ya está en el servidor, igual que en el 08 (RF-08-15).
- **RF-11-10 — Rechazos visibles.** CUANDO un registro vuelve `rechazado`, EL SISTEMA lo saca de la cola y lo muestra en «No se pudo enviar» con el motivo en palabras (por ejemplo, «La Q.F. reasignó esta visita antes de que llegara tu registro») hasta que el encargado pulse «Entendido».
- **RF-11-11 — Cuenta del registro.** SI el registro fue hecho con otra cuenta que la de la sesión que sincroniza, ENTONCES se rechaza con `otro_usuario` y no se audita como resultado. El responsable que queda guardado es siempre la cuenta de la sesión, que coincide con la del registro.
- **RF-11-12 — Avisos tardíos.** CUANDO se aplica un registro sin conexión, EL SISTEMA crea el aviso del 12 («entregado» o «no entregado») con su vigencia de 2 horas contada desde la hora del registro. SI el registro se hizo hace más de 2 horas, ENTONCES el aviso se guarda `omitido` con el código `registro_tardio` y no se envía.
- **RF-11-13 — Estado visible.** «Mis entregas» y la vista sin conexión muestran, en una región que se anuncia al lector de pantalla (`aria-live="polite"`): conectado o sin conexión, hora de la última descarga, «N registros por enviar», «Enviando…» y el resultado del último envío. Nada depende solo del color.
- **RF-11-14 — Salida con pendientes.** CUANDO el encargado pulsa «Salir» con registros por enviar, EL SISTEMA avisa «Tienes N registros sin enviar. Si sales, se enviarán cuando vuelvas a entrar con esta cuenta» y pide confirmación. Al salir se borra el paquete; la cola se conserva, ligada a la cuenta, y solo se envía cuando esa misma cuenta vuelve a entrar. Una cola con más de 2 días se borra (sería rechazada por RF-11-08).
- **RF-11-15 — Detalle para la Q.F.** EL SISTEMA muestra en el detalle de la entrega y en «Pendientes de gestión», para un intento registrado sin conexión, «Registrada sin conexión a las HH:MM · recibida a las HH:MM».
- **RF-11-16 — Con señal, sin cambios.** SI hay señal, ENTONCES el registro sigue el flujo del 08 (formulario del servidor). La cola local solo se usa cuando el envío falla por la red o el navegador está sin conexión.

## Datos y reglas

- **En el servidor:** `IntentoEntrega` agrega `sincronizado_en` (fecha y hora, opcional). Un intento con `sincronizado_en` tiene `registrado_en` y `registrado_por`. `registrado_en` pasa a ser la hora del celular para los registros sin conexión; para los demás sigue siendo la hora del servidor. No se agregan modelos.
- **En el celular (IndexedDB):** dos almacenes: `paquete` (uno por cuenta, se reemplaza en cada descarga) y `cola` (registros pendientes y rechazados, con clave `operacion_id`). No se usan `localStorage` ni la caché del service worker para datos personales.
- **Límites:** hasta 50 registros por solicitud de sincronización; tolerancia de reloj de 5 minutos; plazo de 2 días; reintento cada 30 segundos.
- **Auditoría:** el registro aplicado conserva sus acciones del 08 (`intento.entregado`, `intento.no_entregado`); el rechazo agrega `intento.sincronizacion_rechazada`. La auditoría nunca guarda la nota ni datos del paciente.
- **Privacidad:** el paquete lleva solo lo que ya muestra la tarjeta de «Mis entregas», sin RUT; la vista sin conexión no es pública (necesita una cuenta con sesión previa en ese navegador) y se borra según RF-11-03. La cola guarda identificadores, motivo y nota; la nota puede tener texto libre y se borra al aplicarse o a los 2 días.

## Criterios de aceptación

| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-11-01 | Se publica una versión nueva de los estáticos y se recarga la app. | La caché anterior se borra; ninguna página privada ni JSON aparece en la caché del service worker. |
| RF-11-02 | El encargado A abre «Mis entregas» con 3 visitas de hoy y 1 atrasada. | El paquete trae las 4, en el orden de la ruta, sin RUT, fotos, coordenadas ni correo. El encargado B, la Q.F. y el superusuario reciben 403. |
| RF-11-03 | El paquete es de ayer, o entra otra cuenta, o se cierra sesión. | No se muestra ninguna visita y se ve «No hay una ruta guardada para hoy». |
| RF-11-04 | Con el paquete guardado se corta la red y se recarga «Mis entregas». | Se ve la vista sin conexión con las 4 paradas y el aviso «Sin conexión». |
| RF-11-05 | Sin señal, se registra «No entregada» sin motivo; luego con motivo «Otro» sin nota; luego con motivo válido. | Los dos primeros se rechazan en el celular con el mensaje del 08; el tercero queda «por enviar»; un segundo registro del mismo intento no se ofrece. |
| RF-11-06 | Hay 3 registros en cola y vuelve la red con la app abierta. | En menos de 30 s se envían; el contador baja a 0. Con el servidor caído, siguen en la cola y se reintentan. |
| RF-11-07 | El mismo lote se envía dos veces en paralelo. | Cada registro se aplica una vez; la segunda respuesta es `ya_aplicado`; las recetas se descuentan una vez. |
| RF-11-08 | Registros con hora futura (+10 min), con fecha anterior a la programada y uno de hace 3 días. | Se rechazan con `hora_invalida`, `hora_invalida` y `fuera_de_plazo`. Uno de ayer a las 19:50 que llega hoy a las 08:10 se aplica con `registrado_en` de ayer, y sus recetas se evalúan a la fecha de ayer. |
| RF-11-09 | La Q.F. reasigna la visita y después llega el registro sin conexión. | Respuesta `rechazado/reasignada`; el intento nuevo sigue pendiente; hay una auditoría `intento.sincronizacion_rechazada`. |
| RF-11-10 | Un registro vuelve rechazado. | Aparece en «No se pudo enviar» con el motivo en palabras y desaparece al pulsar «Entendido». |
| RF-11-11 | La cola de la cuenta A se envía con la sesión de la cuenta B. | Respuesta `rechazado/otro_usuario`; el intento sigue pendiente. |
| RF-11-12 | Un registro de hace 1 h y otro de hace 3 h se aplican, con correo para avisos. | El primero crea un aviso pendiente que vence a las 2 h del registro; el segundo, un aviso `omitido` con `registro_tardio`. |
| RF-11-13 | Se usa la vista con lector de pantalla y sin color. | Los cambios de estado se anuncian y se entienden solo con texto. |
| RF-11-14 | Se pulsa «Salir» con 2 registros por enviar. | Aparece el aviso con la cifra; al confirmar, el paquete se borra y la cola se envía al volver a entrar con la misma cuenta. |
| RF-11-15 | La Q.F. abre una entrega registrada sin conexión. | Ve la hora del registro y la de llegada. |
| RF-11-16 | Con señal, el encargado registra desde el formulario. | Funciona como en el 08; la cola local no se usa. |

## No funcionales

- **NS05 / RNF-03:** con 100 registros guardados sin conexión, el 100 % se sincroniza en 5 minutos o menos desde que vuelve la red, con 0 duplicados, medido con `tools/verificar_spec_11_http.py` en una base aislada.
- **RNF-05:** el paquete y cada lote de sincronización responden en 2 s o menos en el 95 % de las solicitudes, con 670 pacientes sintéticos y rutas de 40 visitas.
- **RNF-02:** pruebas concurrentes con `TransactionTestCase` e hilos, al menos tres escenarios: lote duplicado en paralelo, sincronización frente a reasignación y sincronización frente a anulación.
- **RNF-04:** la vista sin conexión cumple WCAG 2.1 AA (contraste, tamaño de texto del sitio, foco visible, mensajes claros); se audita con axe.
- **RNF-09:** la PWA se instala desde el navegador y la vista sin conexión funciona en al menos un celular Android real.
- **RNF-01:** datos mínimos en el celular, sin RUT, borrados según RF-11-03 y RF-11-14; HTTPS en el despliegue (el service worker solo funciona en HTTPS o `localhost`).

## Compatibilidad

- Se conservan los contratos del 08: servicios de registro, idempotencia por `operacion_id`, «gana una sola operación» (RF-08-15) y descuento con `_registrar_entrega_sin_reintento`. Los servicios ganan un parámetro opcional con la hora del registro; sin él, se comportan como hoy.
- Se conservan el orden guardado y las secciones del 09; el paquete solo lee `ruta_del_dia`. OSRM no es necesario: si no responde, la ruta usa la línea recta, como ya hace el 09.
- Se conserva la regla del 13 para las recetas preparadas (evaluación a su fecha de preparación).
- Se conservan los avisos del 12 y sus pruebas; solo cambia la vigencia para los registros sin conexión.
- `templates/pwa/sw.js` deja de ser mínimo (spec 01); `pwa.js` sigue registrándolo con alcance `/`.
- La sala del 06 y el tótem del 04 no cambian: el service worker no intercepta sus rutas ni el WebSocket.

## Supuestos y decisiones pendientes

Decisiones de la usuaria del 2026-11-18:

1. Sin señal se ve y se registra; traslado, fotos, verificación y orden siguen pidiendo señal.
2. El celular guarda los datos de la tarjeta (con teléfono, sin RUT ni fotos) solo de hoy y atrasadas, y los borra al salir, al cambiar el día o al entrar otra cuenta.
3. La hora del registro es la del celular, con límites, y aparte se guarda la de llegada.
4. En conflicto gana el servidor; el rechazo se muestra al encargado y se audita.
5. Se acepta un registro hasta 2 días después de hecho; la vigencia se evalúa a la fecha del registro.
6. Sincronización automática con la app abierta, Background Sync donde exista y botón «Sincronizar ahora».
7. Sin mapa sin señal: solo la lista.
8. Los avisos del 12 se envían si el registro llega dentro de 2 horas desde que se hizo; si no, quedan omitidos.

Supuestos técnicos reversibles (propuestos en este borrador, revisables):

- Tolerancia de reloj de 5 minutos y lotes de 50 registros.
- El token CSRF de la sesión se guarda junto a la cola para que Background Sync pueda enviar; si la sesión cambia, el envío falla y se reintenta con la página abierta.
- La cola se conserva al salir (RF-11-14) porque perder un registro de terreno es peor que guardar identificadores y una nota hasta 2 días.
- No se cifra IndexedDB: una clave en el mismo navegador no protege frente a quien tiene el celular desbloqueado; se mitiga con datos mínimos y borrado.

Bloqueos críticos: ninguno.

## Revisión y cambios

- 2026-11-18: borrador creado con `/spec` a partir de la reserva 11 y de las decisiones de la usuaria de esta fecha. Pendiente la revisión de la usuaria; no está aprobado ni autorizado para implementar.
- 2026-11-18: la usuaria lo pasó a Aprobado y ejecutó `/spec-impl` (en `crojas-base`, todos los pasos sin pausas). Implementado técnicamente el mismo día (T-11-01 a T-11-09, migración `entregasapp/0007`); navegador real, celular Android, axe, usabilidad y aceptación pendientes. Se conserva Aprobado.

## Decisiones de implementación (2026-11-18)

Aplican el spec sin cambiar sus requisitos; las que se apartan del plan quedan anotadas con su motivo:

1. **Sin código `fecha_futura`.** El plan lo listaba para una visita programada después de la fecha del registro, pero RF-11-08 y su criterio piden `hora_invalida` para ese caso. Manda el spec: se usa `hora_invalida`.
2. **Reenvío ya aplicado sin tomar la cola del día.** `sin_conexion.sincronizar_uno` reconoce por `operacion_id` (solo lectura) un registro ya aplicado y responde `ya_aplicado` sin llamar al servicio; es la misma comprobación que el servicio hace antes de escribir y un intento registrado no cambia. Motivo: un celular que reintenta no debe hacer esperar a los demás.
3. **Página sin conexión en `/entregas/mis/sin-conexion/`, guardada por mensaje.** El service worker no la descarga al instalarse (exige la sesión del encargado): «Mis entregas» le pide guardarla (`postMessage`) tras descargar el paquete, y el service worker solo guarda una respuesta 200 propia, sin redirecciones. Si aún no está guardada, muestra un texto mínimo «Sin conexión».
4. **JavaScript sin Alpine.** La vista sin conexión y la barra de estado son JavaScript simple (`almacen.js`, `sincronizar.js`, `sin_conexion.js`), como el resto de `static/js/entregas/`, para probarlos en Node con `dom_simulado.cjs`; `almacen.js` y `sincronizar.js` se comparten con el service worker (`importScripts`).
5. **Cuenta activa en el celular.** `pwa.js` recibe el id interno de la cuenta (`data-cuenta`) y lo guarda como cuenta activa; Background Sync solo envía la cola de esa cuenta, para que la de otra espere a que esa cuenta vuelva a entrar (RF-11-14) en vez de rechazarse con `otro_usuario`.
6. **Auditoría del rechazo.** `intento.sincronizacion_rechazada` con `objeto_tipo` `entregasapp.IntentoEntrega` y `objeto_id` `«id del intento»:«código»` (el modelo de auditoría no tiene otro campo); nunca la nota.
7. **Formulario con señal.** «Registrar visita» envía el formulario del 08 con `fetch` sin seguir la redirección; si el servidor responde con errores, se vuelve a enviar de forma normal para mostrar su página (seguro: misma operación y nada aplicado). Solo un fallo de red, o el navegador sin conexión, usa la cola (RF-11-16).
8. **Lotes simultáneos fuera de 2 s, aceptados como límite.** Con varios celulares enviando a la vez, cada registro espera su turno en la cola del día (contrato del 08) y un lote superó los 2 s en la medición aislada sobre SQLite (5,3 s). La usuaria decidió el 2026-11-18 («Dejarlo como límite») no cambiar el spec: RNF-05 se mide con un celular a la vez (p95 1,7 s) y el caso simultáneo queda informado en `validation.md`.
