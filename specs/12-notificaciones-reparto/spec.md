# SPEC 12 — Aviso de reparto en camino por correo

> **Estado:** Aprobado  
> **Fecha:** 2026-11-18  
> **Depende de:** [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 08](../08-domicilios-y-entregas/spec.md) y [SPEC 09](../09-mapa-y-orden-de-visita/spec.md)  
> **Objetivo:** Enviar un aviso por correo al buzón autorizado del paciente sintético cuando su Encargado de terreno confirme que inicia el traslado hacia la parada asignada.  
> **Enmienda:** 2026-11-18, **Aprobada** por la usuaria el mismo día en el chat («apruebo la enmienda, impleméntala») (ver [Enmienda del 2026-11-18](#enmienda-del-2026-11-18--aviso-del-día-borrador)). Agrega un segundo aviso, «Hoy llega tu reparto de prueba», que se envía solo la mañana del día programado. No cambia el aviso «en camino» ni RF-12-01 a RF-12-06; agrega RF-12-07 a RF-12-13. Desde su aprobación, la enmienda se suma a lo aprobado el 2026-11-18.  
> **Segunda enmienda:** 2026-11-18, **Aprobada** por la usuaria el mismo día en el chat («apruebo las dos enmiendas, impleméntalas») (ver [Destino desde el padrón](#enmienda-del-2026-11-18--destino-desde-el-padrón-borrador)). El destino de ambos avisos pasa a ser el «correo para avisos» del padrón ([enmienda del SPEC 03](../03-padron-y-recetas/spec.md#enmienda-del-2026-11-18--correo-para-avisos-borrador)), se retira la lista JSON privada y se agrega un freno por dominios permitidos. Modifica RF-12-03, RF-12-06 y RF-12-12 y agrega RF-12-14 a RF-12-18. Desde su aprobación, reemplaza lo que se le opone de la versión anterior.  
> **Tercera enmienda:** 2026-11-18, **Aprobada** por la usuaria en el chat («yo quiero que pueda enviarse a cualquier correo») e implementada el mismo día (ver [Envío a cualquier correo](#enmienda-del-2026-11-18--envío-a-cualquier-correo)). `REPARTO_CORREO_DOMINIOS_PERMITIDOS` pasa a ser opcional: vacía, se envía a cualquier correo. Modifica RF-12-15 y RF-12-18.  
> **Cuarta enmienda:** 2026-11-18, **Aprobada** por la usuaria en el chat («cuando la reasigne igual envia un correo, cuando marque entregada o no entregada igual»), con las opciones recomendadas; ver [Avisos de reasignación y resultado](#enmienda-del-2026-11-18--avisos-de-reasignación-y-resultado). Agrega los avisos «reprogramado», «entregado» y «no entregado» (RF-12-19 a RF-12-23) y revierte la exclusión de los avisos de entrega completada y de visita fallida.  
> **Quinta enmienda:** 2026-11-18, **Aprobada** por la usuaria en el chat («necesito que el correo se envie al hacer click en el boton, no por comandos»), con las opciones recomendadas; ver [Envío automático desde el servidor web](#enmienda-del-2026-11-18--envío-automático-desde-el-servidor-web). El servidor web envía los avisos en segundo plano, sin comandos (RF-12-24 a RF-12-28). Modifica RF-12-05 y RF-12-07.

Base técnica verificada en GitHub: `crojas-base` en `4b682422500c9662b9dc9bcc79e52f9f6a0c63bf`. Rama propuesta para la implementación posterior: `spec-12-notificaciones-reparto`.

Implementación, migraciones de prueba y envíos de prueba autorizados expresamente por la usuaria el 2026-11-18. Aceptación funcional pendiente de verificación.

Documentos del cambio · [Plan técnico](plan.md) · [Tareas](tasks.md) · [Validación](validation.md)

## Problema y resultado

El Encargado puede consultar la ruta, navegar a una parada y registrar la visita. La demo agrega una confirmación explícita de salida por parada y envía un aviso al buzón de prueba asignado a ese paciente sintético.

## Actores y permisos

| Actor | Permiso |
|---|---|
| Encargado activo, con perfil habilitado y asignado al intento | Puede confirmar el inicio hacia su intento vigente y pendiente, programado para hoy o atrasado. |
| Otro Encargado, Técnico, Q.F. o superusuario | Carece de permiso para iniciar el traslado. |
| Usuario anónimo, inactivo o sin perfil habilitado | Se aplica el tratamiento de autenticación y acceso vigente, incluido el acceso directo a la URL. |
| Equipo de la demo | Configura la lista privada de buzones autorizados y opera el procesador. |
| Destinatario de prueba | Recibe el aviso en su buzón. El correo no solicita respuesta. |

## Alcance y exclusiones

Incluye el evento `delivery.departed`, una lista privada de buzones por paciente sintético, una bandeja de salida en PostgreSQL y un procesador Django con simulación y transporte SMTP.

Quedan fuera los avisos de entrega completada, visita fallida o retorno, la confirmación del destinatario, los envíos masivos por ruta, la edición de correos en el padrón, el modo sin conexión, Gmail API, n8n, WhatsApp, SMS, Rayén y el despliegue remoto.

## Historias y flujo

1. En «Mis entregas», el Encargado confirma «Iniciar traslado» en la tarjeta de una parada, incluso si carece de coordenadas.
2. Django guarda el inicio, la auditoría y el aviso en una transacción. La tarjeta muestra «Traslado iniciado» después de guardar.
3. El procesador prepara el aviso después del commit y comprueba si sigue vigente y si el buzón continúa autorizado. Envía un correo individual. Si no hay un destino válido, el inicio se conserva y el aviso queda omitido.
4. El equipo verifica la recepción en cada buzón autorizado del conjunto de prueba real.

## Requisitos funcionales

- **RF-12-01 — Inicio explícito.** La acción requiere un `POST` con CSRF y valida rol, asignación, fecha y que el intento siga vigente y pendiente. Abrir un marcador, consultar la ruta o iniciar la guía de navegación no genera avisos.
- **RF-12-02 — Registro único y atómico.** El inicio, la auditoría y el aviso se guardan juntos. Repetir la acción, incluso desde dos dispositivos, deja un solo inicio y un solo aviso. El Encargado sigue pudiendo registrar el resultado de la visita aunque haya omitido el inicio.
- **RF-12-03 — Destino y contenido.** Cada paciente sintético del conjunto de la demo tiene su propio buzón de prueba autorizado, configurado fuera del padrón. Cada correo tiene un único destinatario, sin CC ni CCO. El asunto propuesto es «Reparto de prueba en camino» y el cuerpo es «Tu reparto de prueba está en camino». Si una asignación se retira o cambia, los pendientes afectados se omiten. Los cambios de asignación se usan en nuevos inicios.
- **RF-12-04 — Vigencia.** A los 30 minutos del inicio, el aviso pendiente caduca. También se descarta si, antes de preparar el envío, se registra un resultado, se reasigna o se anula la visita. La reasignación permite generar un aviso propio para el nuevo intento.
- **RF-12-05 — Procesamiento recuperable.** El procesador permite simulación y SMTP. Recupera reservas en las que aún no se autorizó el envío y reintenta únicamente fallos temporales inequívocos dentro de la vigencia. Una respuesta perdida después de que el servidor pudo aceptar el correo deja el aviso incierto y bloquea el reenvío automático. Una falla de SMTP conserva el inicio ya confirmado.
- **RF-12-06 — Validación.** La aceptación exige pruebas simuladas y recepción real en el buzón autorizado de **cada paciente sintético del conjunto de validación**. Se comprueba que el aviso de un paciente no llegue a los otros buzones.

## Datos, privacidad y compatibilidad

- Se registran fecha y actor del inicio en `IntentoEntrega`. La bandeja identifica un aviso por intento y tipo de evento. Los intentos históricos empiezan sin inicio registrado.
- El mensaje y los registros externos excluyen nombres, RUT, domicilios, coordenadas, recetas, medicamentos y datos clínicos. La dirección de prueba solo se usa para el envío. Los registros de aplicación y la auditoría omiten direcciones y credenciales.
- La aceptación del servidor SMTP se registra por separado de la recepción observada en el buzón. La interfaz funciona con teclado y sin JavaScript, y la respuesta web no espera a SMTP.
- Se conservan los contratos de navegación, reasignación, anulación, registro de resultados, descuentos de recetas y correo de cuentas.

## Criterios de aceptación

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-12-01 | Inicio válido, intento ajeno o futuro, consulta y POST sin CSRF. | Solo el inicio válido registra el traslado y genera aviso. Una visita sin coordenadas admite el inicio. |
| RF-12-02 | Doble clic, solicitudes simultáneas o fallo al guardar el aviso o la auditoría. | Queda un solo inicio y aviso, o se revierte toda la operación si falla una escritura. |
| RF-12-03 | Pacientes con buzones distintos, paciente sin asignación y cambio o retiro de buzón. | Cada aviso se dirige solo al buzón autorizado correcto. Los casos sin asignación válida se omiten y ningún registro expone direcciones. |
| RF-12-04 | Transcurren los 30 minutos o el intento cambia antes de preparar. | No se invoca el transporte. El nuevo intento reasignado admite su propio aviso. |
| RF-12-05 | Falla el procesador antes de autorizar, SMTP rechaza temporalmente o se pierde la respuesta. | La reserva se recupera, el rechazo temporal se reintenta dentro de la vigencia o el resultado incierto se conserva sin reenvío, según corresponda. |
| RF-12-06 | Se ejecuta la prueba SMTP real con el padrón sintético de validación. | Se documenta la recepción en el buzón de cada paciente incluido y la ausencia de cruces entre destinatarios. |

## Decisiones y revisión

- 2026-11-18. La usuaria eligió una lista de buzones por paciente sintético, caducidad de 30 minutos y validación simulada y real por destinatario.
- Esta versión cubre parcialmente la [HU-19](../../docs/Informe.md). El informe contempla SMS o push al iniciar el recorrido y aviso de visita fallida. Esta demo usa correo SMTP al confirmar la salida hacia una parada.
- Quedan por preparar la lista privada y la base PostgreSQL sintética para la ejecución futura. La forma de configuración, el asunto y los límites técnicos del procesador son propuestas del borrador.

## Enmienda del 2026-11-18 — Aviso del día (Borrador)

**Objetivo de la enmienda:** Enviar, la mañana del día programado de una entrega a domicilio, un aviso por correo al buzón autorizado del paciente sintético, sin que nadie tenga que pulsar nada.

### Problema y resultado

Hoy el paciente o su cuidador solo se entera cuando el Encargado ya salió hacia su parada. La usuaria pidió que el correo llegue «justo el día que debe mandarse el pedido», para que alguien esté en casa. Con la enmienda, cada paciente con buzón autorizado y visita pendiente para hoy recibe a primera hora «Hoy llega tu reparto de prueba»; más tarde, si el Encargado confirma la salida, recibe además el aviso «en camino» de siempre.

### Alcance de la enmienda

Incluye un tipo de aviso nuevo, `delivery.scheduled_today`, generado por el mismo procesador `procesar_avisos_reparto` a partir de una hora configurable y hasta una hora límite, y enviado por la misma bandeja, los mismos transportes y las mismas garantías del RF-12-05.

Queda fuera: avisar visitas atrasadas de días anteriores, avisar la víspera, indicar una franja horaria o el orden de la parada, avisar al anular o reprogramar, cualquier interfaz nueva para el personal, y los canales y exclusiones ya listados en este spec (SMS, WhatsApp, push, correos en el padrón, etc.).

### Requisitos de la enmienda

- **RF-12-07 — Generación automática del aviso del día.** CUANDO el procesador corre en un día cuya hora local está entre la hora del aviso (`REPARTO_AVISO_DIA_HORA`, por omisión 08:00) y la hora límite (`REPARTO_AVISO_DIA_LIMITE`, por omisión 18:00), EL SISTEMA crea un aviso del día por cada entrega `programada` que tenga un intento `pendiente` con `fecha_programada` igual a hoy y cuyo paciente tenga un buzón autorizado en la lista privada. No interviene ningún usuario ni hay botón. Fuera de esa franja no crea avisos del día.
- **RF-12-08 — Programadas durante el día.** SI una entrega se programa, se deriva desde mermas o se reasigna para hoy después de la hora del aviso y antes de la hora límite, ENTONCES su aviso del día se crea en la siguiente vuelta del procesador.
- **RF-12-09 — Uno por entrega y día.** EL SISTEMA crea como máximo un aviso del día por entrega y fecha, aunque el procesador corra varias veces o haya dos procesadores a la vez. Una reasignación a otro Encargado para la misma fecha no genera un segundo aviso del día. SI la entrega se reasigna a otra fecha, ENTONCES ese otro día corresponde un aviso del día nuevo. El aviso «en camino» sigue siendo uno por visita (RF-12-02).
- **RF-12-10 — Sin atrasadas.** Las visitas pendientes con fecha anterior a hoy no generan aviso del día, aunque sigan en la ruta del Encargado.
- **RF-12-11 — Vigencia hasta la hora límite.** Un aviso del día que no se alcanzó a enviar caduca a la hora límite de su fecha. También se descarta si, antes de preparar el envío, la entrega deja de estar `programada` o ya no tiene un intento pendiente para esa fecha. Si el procesador estuvo detenido a la hora del aviso y se enciende antes de la hora límite, los avisos del día se crean y se envían igual.
- **RF-12-12 — Destino y contenido.** El destino es el mismo buzón autorizado del RF-12-03, con la misma firma y revalidación antes del envío. Un paciente sin buzón no genera aviso del día; si se le asigna buzón más tarde, el aviso se crea en la siguiente vuelta, dentro de la franja. Cada correo tiene un solo destinatario. Asunto: «Hoy llega tu reparto de prueba». Cuerpo: «Tu reparto de prueba está programado para hoy. Te avisaremos cuando vaya en camino.» El mensaje y los registros excluyen nombres, RUT, domicilios, coordenadas, recetas, medicamentos, el Encargado y datos clínicos.
- **RF-12-13 — Configuración validada.** `REPARTO_AVISO_DIA_HORA` y `REPARTO_AVISO_DIA_LIMITE` se leen del `.env` en formato `HH:MM` de 24 horas. SI alguno no tiene ese formato o la hora del aviso no es anterior a la límite, ENTONCES `python manage.py check` informa un error claro. Vacíos, valen 08:00 y 18:00.

### Criterios de aceptación de la enmienda

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-12-07 | Reloj a las 07:59, 08:00 y 17:59 con tres entregas de hoy, dos con buzón. | A las 07:59 no hay avisos del día; a las 08:00 y a las 17:59 hay exactamente dos, uno por paciente con buzón. |
| RF-12-08 | Entrega programada para hoy a las 11:00. | La siguiente vuelta crea y envía su aviso del día. |
| RF-12-09 | Procesador ejecutado dos veces, dos procesadores simultáneos y reasignación a otro Encargado el mismo día. | Un solo aviso del día por entrega y fecha, sin envíos repetidos. Reasignada a mañana: mañana se crea otro. |
| RF-12-10 | Visita pendiente de ayer y otra de hoy. | Solo la de hoy recibe aviso del día. |
| RF-12-11 | Reloj a las 18:00 con un aviso pendiente; entrega registrada o anulada antes de preparar; procesador encendido a las 10:00. | El de las 18:00 queda obsoleto sin llamar al transporte; el de la entrega cerrada queda obsoleto; a las 10:00 se crean y se envían los del día. |
| RF-12-12 | Buzones distintos, paciente sin buzón, buzón cambiado antes del envío y buzón asignado a mediodía. | Cada correo llega solo a su buzón, con el asunto y el cuerpo indicados; el sin buzón no genera aviso; el cambiado queda omitido; el asignado a mediodía recibe el suyo. |
| RF-12-13 | Valores `8`, `25:00`, el par `18:00`/`08:00` y vacíos. | `check` informa error en los tres primeros; vacíos usan 08:00 y 18:00. |
| RF-12-06 ampliado | Prueba SMTP real del aviso del día con el conjunto de validación. | Se documenta la recepción en el buzón de cada paciente incluido y la ausencia de cruces. |

### Compatibilidad de la enmienda

- No cambia la interfaz, los permisos, `iniciar_traslado`, ni los servicios de programación, derivación, reasignación, anulación y registro del 08, 09 y 13 ni sus contratos de bloqueo: el aviso del día lo crea solo el procesador, fuera de las solicitudes web.
- Los avisos «en camino» ya guardados conservan su significado. Se requiere una migración aditiva en `AvisoReparto`.
- Si el procesador no está corriendo, no sale ningún aviso; en la demo se deja con `--continuo` o en el Programador de tareas de Windows.

### Decisiones de la enmienda

- 2026-11-18. La usuaria eligió las opciones recomendadas: mantener los dos avisos (el del día y el «en camino»), hora del aviso 08:00 configurable, no avisar las visitas atrasadas, enviar también las programadas durante el día, hora límite 18:00 configurable, un aviso del día por entrega y fecha, y el texto «Hoy llega tu reparto de prueba».
- El aviso del día lo genera el procesador y no los servicios de programación, para no tocar los contratos concurrentes del 08 y del 13, y porque una visita programada con días de anticipación debe avisarse ese día y no al programarla.
- Sin buzón no se crea aviso del día (a diferencia del «en camino», que queda `omitido`), para no llenar la bandeja con filas diarias sin destino y para que un buzón asignado durante la mañana alcance a recibir el suyo.
- Se descartó avisar la víspera, porque la ruta del día siguiente puede cambiar, y avisar las atrasadas, porque recibirían el correo varios días seguidos.
- La enmienda acerca la demo a la [HU-19](../../docs/Informe.md), que contempla avisar al iniciar el recorrido; sigue siendo correo SMTP y no SMS ni push.

### Revisión de la enmienda

Aprobada por la usuaria el 2026-11-18 («apruebo la enmienda, impleméntala») e implementada técnicamente el mismo día; ver [validation.md](validation.md). El título de esta sección conserva «Borrador» para no romper el enlace; manda la cabecera.

## Enmienda del 2026-11-18 — Destino desde el padrón (Borrador)

**Objetivo de la enmienda:** Enviar los avisos «en camino» y «del día» al «correo para avisos» que el padrón guarda para cada paciente, retirar la lista JSON privada y limitar los envíos de la demo a dominios de prueba autorizados.

### Problema y resultado

La lista JSON asocia cada buzón al identificador interno del paciente en una base concreta: si la base se reconstruye o el padrón se importa en otra, la lista queda apuntando a pacientes equivocados o deja de servir, y corregirla exige editar un archivo en el servidor. La usuaria prefirió que el correo viva en el padrón ([enmienda del SPEC 03](../03-padron-y-recetas/spec.md#enmienda-del-2026-11-18--correo-para-avisos-borrador)). Con esta enmienda, el procesador lee el destino del paciente; para que la demo no escriba a direcciones reales por error, solo envía a los dominios que el equipo autorice en la configuración.

### Alcance de la enmienda

Incluye leer el destino desde `Paciente.correo_avisos`, retirar `REPARTO_BUZONES_PRUEBA_ARCHIVO` y su lectura, agregar `REPARTO_CORREO_DOMINIOS_PERMITIDOS` con su comprobación, y adaptar la firma, la revalidación y las pruebas de ambos avisos.

Queda fuera: el campo, la importación y la edición del correo (spec 03), avisar a más de un correo por paciente, unificar en un solo correo los avisos de varios pacientes con el mismo cuidador, y los demás canales y exclusiones del spec.

### Requisitos de la enmienda

- **RF-12-14 — Destino desde el padrón.** EL SISTEMA envía cada aviso al `correo_avisos` del paciente de la entrega, leído en el momento de crear el aviso y otra vez antes de enviarlo. Ya no existe la lista JSON privada: `REPARTO_BUZONES_PRUEBA_ARCHIVO` deja de leerse y se retira de la configuración, del README y de las pruebas. *(Modifica RF-12-03 y RF-12-12: «configurado fuera del padrón» pasa a «guardado en el padrón».)*
- **RF-12-15 — Freno por dominios permitidos.** EL SISTEMA solo envía a direcciones cuyo dominio esté, sin distinguir mayúsculas y en coincidencia exacta (sin subdominios implícitos), en `REPARTO_CORREO_DOMINIOS_PERMITIDOS`, una lista separada por comas. SI la lista está vacía, ENTONCES no se envía ningún aviso. Un dominio no permitido se trata como falta de destino: el aviso «en camino» queda `omitido` con el código `dominio_no_permitido` y el traslado se guarda igual; el aviso del día no se crea.
- **RF-12-16 — Sin destino.** Un paciente sin correo para avisos se trata como hoy un paciente sin buzón: el «en camino» queda `omitido` con `sin_destino` y el del día no se crea. SI la Q.F. le agrega un correo permitido durante la franja, ENTONCES su aviso del día se crea en la siguiente vuelta.
- **RF-12-17 — Firma y revalidación.** La firma HMAC del aviso se calcula con el nombre de la base, el identificador del paciente y su correo del padrón. Antes de enviar, el procesador vuelve a leer el correo y el freno: SI el correo cambió o se borró, ENTONCES el aviso queda `omitido` con `destino_cambiado`; SI el dominio dejó de estar permitido, ENTONCES queda `omitido` con `dominio_no_permitido`. Varios pacientes con el mismo correo reciben un aviso cada uno, porque la restricción de direcciones únicas era propia de la lista y se retira.
- **RF-12-18 — Configuración y comando.** `python manage.py check` informa un error (`entregasapp.E008`) si algún dominio de la lista no es un nombre de dominio válido. `procesar_avisos_reparto --smtp` termina con un error claro si la lista de dominios está vacía, en lugar del error actual por falta de buzones. `--simular` respeta el mismo freno.
- **RF-12-06 (ampliado).** La validación real usa pacientes sintéticos de la base elegida con correos de prueba de dominios permitidos, cargados por importación o en la ficha, y comprueba que el aviso de un paciente no llegue a los otros buzones.

### Criterios de aceptación de la enmienda

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-12-14 | Paciente con correo permitido inicia traslado y tiene visita hoy; archivo JSON configurado en el `.env`. | Ambos avisos van a su correo del padrón; el JSON se ignora. |
| RF-12-15 | Lista vacía; dominio no permitido; dominio en mayúsculas; subdominio de un dominio permitido. | Lista vacía: nada se envía y `--smtp` falla con mensaje claro; no permitido: «en camino» `omitido` y sin aviso del día; mayúsculas: se envía; subdominio: no se envía. |
| RF-12-16 | Paciente sin correo; correo agregado a mediodía. | «En camino» `omitido` con `sin_destino` y sin aviso del día; a mediodía se crea y se envía su aviso del día. |
| RF-12-17 | Correo cambiado o borrado antes del envío; dominio retirado de la lista; dos pacientes con el mismo correo. | `omitido` con el código que corresponde; los dos pacientes reciben un aviso cada uno. |
| RF-12-18 | Lista con `example.invalid,prueba.cl` y con `no es dominio`. | El primero pasa `check`; el segundo da `entregasapp.E008`. |
| RF-12-06 ampliado | Prueba SMTP real con correos de prueba en el padrón. | Recepción en el buzón de cada paciente incluido y ningún cruce. |

### Compatibilidad de la enmienda

- No cambia la interfaz del Encargado, los permisos, la bandeja, los estados, los reintentos ni la franja del aviso del día. No requiere migración en `entregasapp`.
- Depende de la migración `recetasapp/0005_paciente_correo_avisos` de la enmienda del spec 03; se implementan juntas, primero la del 03.
- Los avisos ya creados con la lista conservan su estado. Un aviso pendiente firmado con la lista quedará `omitido` (`destino_cambiado`) si el correo del padrón es distinto.
- Quien tenga `REPARTO_BUZONES_PRUEBA_ARCHIVO` en su `.env` puede borrarla: ya no se lee.

### Decisiones de la enmienda

- 2026-11-18. La usuaria pidió llevar el correo al padrón y eligió las opciones recomendadas: un solo correo para avisos, importable y editable en la ficha, y que la celda vacía conserve el guardado. Para la lista JSON no marcó preferencia y se aplicó la recomendación: retirarla y usar el freno por dominios, para no mantener dos fuentes de verdad.
- El freno por dominios reemplaza a la lista como protección de la demo: la lista autorizaba buzones uno a uno; el freno autoriza los dominios de prueba del equipo y deja fuera cualquier dirección real que llegue por error en un archivo.
- Se descartó unificar avisos cuando dos pacientes comparten correo: cada aviso corresponde a una entrega distinta.
- Se revierte la exclusión «edición de correos en el padrón» de este spec.

### Revisión de la enmienda

Aprobada por la usuaria el 2026-11-18 («apruebo las dos enmiendas, impleméntalas») e implementada técnicamente el mismo día; ver [validation.md](validation.md). El título de esta sección conserva «Borrador» para no romper el enlace; manda la cabecera.

## Enmienda del 2026-11-18 — Envío a cualquier correo

**Objetivo de la enmienda:** Permitir que los avisos salgan a cualquier correo para avisos del padrón, sin exigir una lista de dominios permitidos.

### Problema y decisión

Al probar el envío real, `procesar_avisos_reparto --smtp` terminó con «SMTP requiere al menos un dominio en REPARTO_CORREO_DOMINIOS_PERMITIDOS.» y los avisos «en camino» quedaron omitidos. La usuaria decidió: «yo quiero que pueda enviarse a cualquier correo». Se le explicó el riesgo (si el padrón trae correos reales por error, recibirían avisos) y se le recomendó mantener el freno; la decisión es suya y se registra aquí.

### Requisitos que cambian

- **RF-12-15 (modificado) — Dominios opcionales.** SI `REPARTO_CORREO_DOMINIOS_PERMITIDOS` está vacía, ENTONCES EL SISTEMA envía a cualquier correo para avisos válido del padrón. SI tiene dominios, ENTONCES solo envía a esos, sin distinguir mayúsculas y en coincidencia exacta, como antes; un dominio no permitido sigue dejando el «en camino» `omitido` con `dominio_no_permitido` y sin aviso del día.
- **RF-12-18 (modificado) — Comando.** `procesar_avisos_reparto --smtp` ya no exige dominios. `check` sigue informando `entregasapp.E008` si la lista tiene un dominio inválido.
- Sin cambios: el destino sigue siendo el correo del padrón; un paciente sin correo deja el «en camino» `omitido` con `sin_destino`; la firma y la revalidación antes del envío se mantienen.

### Compatibilidad

- No hay migraciones ni cambios de interfaz. Los avisos ya omitidos con `dominio_no_permitido` no se reenvían solos.
- La regla de datos sintéticos sigue vigente: en la demo, los correos del padrón deben ser buzones de prueba del equipo, nunca correos de pacientes reales.

### Revisión

Aprobada e implementada el 2026-11-18; ver [validation.md](validation.md).

## Enmienda del 2026-11-18 — Avisos de reasignación y resultado

**Objetivo de la enmienda:** Avisar por correo al paciente o a su cuidador cuando su entrega se reasigna y cuando el Encargado la registra como entregada o no entregada.

### Problema y decisión

La usuaria pidió: «cuando la reasigne igual envia un correo, cuando marque entregada o no entregada igual». El spec dejaba fuera los avisos de entrega completada y de visita fallida; esta enmienda los incorpora junto con el de reasignación. Las opciones elegidas fueron las recomendadas: avisar en cada reasignación con la fecha, no incluir el motivo de la no entrega y una vigencia de 2 horas.

### Requisitos de la enmienda

- **RF-12-19 — Aviso de reasignación.** CUANDO la Q.F. reasigna una entrega, EL SISTEMA crea, en la misma transacción, un aviso «reprogramado» (`delivery.rescheduled`) para el intento nuevo, aunque la fecha sea la misma y solo cambie el Encargado. Asunto: «Reparto de prueba reprogramado». Cuerpo: «Tu reparto de prueba se reprogramó para el DD/MM.», o «para hoy.» si la fecha es la del envío. La fecha se lee del intento al enviar. No menciona al Encargado.
- **RF-12-20 — Aviso de entrega realizada.** CUANDO el Encargado registra «Entregada», EL SISTEMA crea en la misma transacción un aviso «entregado» (`delivery.delivered`). Asunto: «Reparto de prueba entregado». Cuerpo: «Tu reparto de prueba fue entregado.»
- **RF-12-21 — Aviso de no entrega.** CUANDO el Encargado registra «No entregada», EL SISTEMA crea en la misma transacción un aviso «no entregado» (`delivery.failed`), sin el motivo ni la nota. Asunto: «No pudimos entregar tu reparto de prueba». Cuerpo: «No pudimos entregar tu reparto de prueba. La farmacia coordinará una nueva visita.»
- **RF-12-22 — Unicidad, vigencia y revalidación.** Cada uno de estos avisos es único por intento y tipo; repetir la operación (mismo identificador) no crea otro. Vence a las 2 horas de creado. Antes de enviar, el procesador comprueba que el intento siga en el estado que originó el aviso: «reprogramado», que el intento nuevo siga pendiente y su entrega programada; «entregado» y «no entregado», que el intento conserve ese resultado. Si no, queda `obsoleto` con `visita_cambiada`. El destino, el freno opcional de dominios, la firma y los reintentos son los de los demás avisos; sin correo, el aviso queda `omitido` con `sin_destino` y el registro se guarda igual.
- **RF-12-23 — Independencia.** Un fallo de correo nunca impide reasignar ni registrar. La anulación de una entrega no genera aviso. El aviso del día y el «en camino» no cambian.

### Criterios de aceptación de la enmienda

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-12-19 | Reasignación a mañana, a hoy con otro Encargado y repetición con el mismo identificador. | Un aviso por reasignación con «para el DD/MM» o «para hoy»; la repetición no crea otro. |
| RF-12-20 | Registro «Entregada» y su repetición. | Un aviso con el texto de entrega realizada. |
| RF-12-21 | Registro «No entregada» con motivo y nota. | Un aviso sin el motivo ni la nota. |
| RF-12-22 | Paciente sin correo; aviso vencido a las 2 horas; reasignado ya registrado antes de enviar; fallo de la auditoría. | `omitido`/`sin_destino` con el registro guardado; `obsoleto`/`aviso_vencido`; `obsoleto`/`visita_cambiada`; sin aviso si la operación se revierte. |
| RF-12-23 | Anulación; registro y reasignación simultáneos. | Sin aviso de anulación; un solo ganador y solo su aviso. |

### Compatibilidad de la enmienda

- Migración `entregasapp/0006_avisoreparto_resultados`, que solo amplía las opciones de `AvisoReparto.tipo`.
- Los servicios `reasignar`, `registrar_entregada` y `registrar_no_entregada` agregan la creación del aviso dentro de su transacción y después de su UPDATE condicional, sin cambiar sus bloqueos ni sus respuestas.
- Los transportes reciben la fecha solo para el aviso «reprogramado» (`transporte(correo, tipo, fecha=...)`); los demás conservan `transporte(correo, tipo)`.

### Decisiones de la enmienda

- 2026-11-18. La usuaria pidió los tres avisos y eligió las opciones recomendadas: reasignación siempre con fecha, no entrega sin motivo y vigencia de 2 horas.
- El motivo de la no entrega no viaja por correo para no exponer información de la visita; queda en el sistema.
- Se mantiene fuera el aviso de anulación, que la usuaria no pidió.

### Revisión

Aprobada en el chat e implementada el 2026-11-18; ver [validation.md](validation.md).

## Enmienda del 2026-11-18 — Envío automático desde el servidor web

**Objetivo de la enmienda:** Que los avisos salgan solos al hacer clic, y el aviso del día en la mañana, mientras el servidor web esté encendido, sin ejecutar `procesar_avisos_reparto`.

### Problema y decisión

Para desplegar la demo (posiblemente en AWS o Railway), la usuaria pidió: «necesito que el correo se envie al hacer click en el boton, no por comandos». Eligió las opciones recomendadas: el correo se envía en segundo plano (la página no espera a Gmail) y el mismo servidor web crea el aviso del día y reintenta los pendientes.

### Requisitos de la enmienda

- **RF-12-24 — Despachador en el servidor web.** CUANDO arranca el servidor web (ASGI con Daphne, o WSGI), EL SISTEMA inicia en ese proceso un despachador de avisos en un hilo propio, uno por proceso. Los comandos de gestión (`migrate`, `shell`, `test`, etc.) no lo inician. Se configura con `REPARTO_AVISOS_AUTOMATICOS`: `smtp` (por omisión) envía por SMTP, `simular` usa el correo en memoria y `no` lo desactiva.
- **RF-12-25 — Envío al confirmar el clic.** CUANDO se confirma la transacción que crea un aviso pendiente (iniciar traslado, reasignar, entregada o no entregada), EL SISTEMA despierta al despachador, que lo envía en segundo plano, normalmente en pocos segundos. La respuesta web no espera a SMTP (RNF-05). Si la transacción se revierte, no se despierta a nadie ni se envía nada.
- **RF-12-26 — Vuelta periódica.** El despachador procesa la bandeja al arrancar y luego cada 60 segundos, aunque nadie haga clic: así crea el aviso del día dentro de su franja, recupera reservas y reintenta los fallos temporales. *(Modifica RF-12-05 y RF-12-07: ya no hace falta dejar el comando corriendo.)*
- **RF-12-27 — Seguridad entre procesos.** Varios procesos o servidores pueden despachar a la vez; las reservas con token, las restricciones únicas y los estados existentes garantizan que cada aviso se envíe una sola vez. El comando `procesar_avisos_reparto` se conserva para uso manual y puede convivir con el despachador.
- **RF-12-28 — Fallos aislados.** Un error de la base o de SMTP en el despachador no detiene el hilo ni afecta las solicitudes web; se registra solo el tipo de error, sin direcciones, cuerpos ni credenciales, y se reintenta en la siguiente vuelta. El hilo cierra sus conexiones a la base al terminar cada vuelta.

### Criterios de aceptación de la enmienda

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-12-24 | `REPARTO_AVISOS_AUTOMATICOS` con `smtp`, `simular`, `no` y un valor inválido. | Se inicia o no según el valor; el inválido da error en `check`; los comandos no lo inician. |
| RF-12-25 | Iniciar traslado con el despachador activo; operación revertida; paciente sin correo. | El aviso queda enviado en segundos sin comando; la revertida no despierta; el omitido no despierta. |
| RF-12-26 | Aviso pendiente sin clic posterior. | La vuelta periódica lo envía. |
| RF-12-27 | Despachador y comando a la vez. | Un solo envío por aviso. |
| RF-12-28 | Excepción simulada durante una vuelta. | El hilo sigue vivo y procesa en la vuelta siguiente; el registro no contiene datos personales. |

### Despliegue

- AWS (EC2 u otra VM) o Railway: el proceso web queda encendido y el despachador corre con él. En Railway hay que dejar desactivada la opción de dormir el servicio sin tráfico; si duerme, los avisos esperan en la bandeja y salen al despertar, salvo los que caducaron.
- Con varios procesos o réplicas, cada uno tiene su despachador; no se duplican envíos (RF-12-27).
- Las variables `EMAIL_*`, `DEFAULT_FROM_EMAIL` y, si se usa, `REPARTO_CORREO_DOMINIOS_PERMITIDOS` deben estar configuradas en el entorno del despliegue.

### Decisiones de la enmienda

- 2026-11-18. La usuaria eligió el envío en segundo plano y el aviso del día desde el mismo servidor web. Se descartó enviar dentro del mismo clic porque Gmail puede tardar varios segundos y la respuesta debe quedar en 2 s o menos.
- Se sigue el patrón del vigilante de la sala (spec 06): un trabajador por proceso, sin Redis ni colas externas, con la base como fuente de verdad.
- El ejecutor de pruebas fija `REPARTO_AVISOS_AUTOMATICOS = "no"` para que ninguna prueba envíe en segundo plano sin pedirlo.

### Revisión

Aprobada en el chat e implementada el 2026-11-18; ver [validation.md](validation.md).
