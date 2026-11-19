# Validación — 12 / Aviso de reparto en camino por correo

[Especificación](spec.md) · [Plan técnico](plan.md) · [Tareas](tasks.md)

Fecha del plan **2026-11-18**. Referencia de base `crojas-base@4b682422500c9662b9dc9bcc79e52f9f6a0c63bf`. Estado **Verificación técnica ejecutada**. Recepción SMTP y aceptación funcional pendientes.

## Resultados del 2026-11-18

- PostgreSQL desechable, con transportes simulados. La regresión de `entregasapp` y `usuariosapp` aprobó **428 pruebas**. La ejecución final de `entregasapp.tests.test_inicio_traslado` y `entregasapp.tests.test_avisos_reparto` aprobó **19 pruebas**, incluida la carrera entre dos procesadores. La regresión inicial se ejecutó antes de añadir esa prueba final.
- `check` pasó sin incidencias y `makemigrations --check --dry-run` informó que no había cambios de esquema pendientes. Django creó y eliminó bases de pruebas PostgreSQL de nombre único. La prueba de migración retrocedió a `0002_ordenruta`, creó un intento sintético histórico y volvió a la punta. El intento conservó vacíos sus campos de inicio y la bandeja quedó vacía. La base de uso cotidiano quedó fuera de estas pruebas.
- Edge sin ventana, HTTP real y SQLite temporal. A **1280 px y 390 px**, el Encargado activó «Iniciar traslado» con Enter y JavaScript deshabilitado. Django validó el formulario con CSRF, persistió ambos inicios y mostró el nuevo estado. Las dos visitas carecían de coordenadas.
- Los envíos se verificaron en memoria con destinos sintéticos distintos y mediante respuestas SMTP simuladas. La recepción SMTP real queda pendiente porque la lista privada de buzones y la base sintética asociada aún no están identificadas. La comprobación independiente de autenticación SMTP quedó sin ejecutar al rechazarse su ejecución con acceso externo.

## Integración en `fdaza` (2026-11-18)

- Código fusionado sobre el spec 13, con la migración renumerada a `entregasapp/0004_avisoreparto_traslado` (depende de `0003_recetaentrega_preparacion`). `check` sin incidencias, `makemigrations --check --dry-run` sin cambios y suite completa con **1079 pruebas OK** (PostgreSQL de pruebas, transporte simulado). La base local no se migró y la recepción SMTP real sigue pendiente.

## Cobertura por requisito

| RF | Escenario | Esperado | Estado |
|---|---|---|---|
| RF-12-01 | POST propio, visita sin coordenadas, otro Encargado, perfiles sin permiso, inactivo, futuro, CSRF ausente y consultas GET. | El inicio procede exclusivamente para el intento vigente y autorizado. | Aprobado en pruebas |
| RF-12-02 | Doble clic, dos dispositivos concurrentes y fallo inyectado al guardar la auditoría o el aviso. | Un inicio, una auditoría y un aviso, o rollback completo. | Aprobado en pruebas |
| RF-12-03 | Dos o más pacientes con buzones distintos, asignación ausente, lista de otra base y buzón modificado antes de preparar. | Salidas dirigidas exclusivamente a su buzón de prueba, omisión ante destino inválido y registros sin direcciones ni datos clínicos. | Aprobado en pruebas |
| RF-12-04 | Reloj controlado a 29:59 y 30:00, entrega exitosa, no entrega, reasignación y anulación antes de preparar. | A 29:59 se autoriza si sigue vigente. Desde los 30 minutos o al cambiar el intento, el aviso queda obsoleto. | Aprobado en pruebas |
| RF-12-05 | Dos consumidores, reserva vencida antes de autorizar, rechazo temporal explícito, rechazo definitivo, caída tras autorizar y respuesta perdida. | Sin autorizaciones duplicadas. Reintentos acotados para fallos seguros. Resultado incierto sin reenvío automático. | Aprobado en pruebas |
| RF-12-06 | Envío SMTP real, iniciado desde la interfaz, para cada paciente sintético con buzón autorizado del conjunto de validación. | Una recepción en el buzón asignado de cada paciente, asunto y cuerpo correctos, y ningún cruce de destinatarios. | Recepción real pendiente |

## Regresión, experiencia y esquema

- Ejecutar las nuevas pruebas y la regresión de registro, doble vía, permisos, reasignación, rutas y correo de cuentas con PostgreSQL desechable y backend de correo simulado. Registrar comandos y resultados una vez ejecutados.
- Revisar la tarjeta en navegador y vista móvil, con teclado y sin JavaScript. Confirmar que el rótulo muestra el inicio y que el resultado de visita se puede registrar aunque se haya omitido ese paso.
- Comprobar la migración desde `0002_ordenruta` y desde una base vacía, la ausencia de eventos retroactivos y la reversión con respaldo en la base de prueba.
- Para la prueba SMTP, iniciar los traslados de forma secuencial y registrar por código de caso el UUID interno del aviso, el estado de aceptación SMTP y la recepción observada. Revisar todos los buzones correspondientes y registrar el número de casos recibidos sobre el total. Excluir direcciones, credenciales, nombres y capturas con datos del buzón.

## Enmienda del 2026-11-18 — Aviso del día (Borrador)

Estado **Verificación técnica ejecutada el 2026-11-18** sobre `fdaza`, sin commit. Recepción SMTP real y aceptación funcional pendientes.

- `entregasapp/tests/test_aviso_del_dia.py` agrega **24 pruebas**: reloj simulado con `timezone.now` (franja, configuración, programadas durante el día, atrasadas, reasignaciones, vigencia, cierres, destino y textos), comprobaciones E006/E007, tres escenarios concurrentes con `TransactionTestCase` e hilos, y la migración de `0004` a `0005` y de vuelta. Junto con `test_avisos_reparto` y `test_inicio_traslado`: **43 pruebas OK**.
- Las pruebas del aviso «en camino» anulan `encolar_del_dia` para no depender de la hora en que corren, y sus aserciones pasaron a esperar `(correo, tipo)` porque los transportes ahora reciben el tipo. Su comportamiento no cambió.
- `python manage.py check` sin incidencias, `makemigrations --check --dry-run` sin cambios y suite completa con **1103 pruebas OK** en la base PostgreSQL de pruebas, con transporte simulado. La base local no se migró.

| RF | Escenario | Esperado | Estado |
|---|---|---|---|
| RF-12-07 | Reloj a las 07:59, 08:00 y 17:59; tres entregas de hoy, dos con buzón. | Ningún aviso del día a las 07:59; dos a las 08:00 y a las 17:59. | Aprobado en pruebas |
| RF-12-08 | Entrega programada para hoy a las 11:00. | Aviso creado y enviado en la siguiente vuelta. | Aprobado en pruebas |
| RF-12-09 | Doble ejecución, dos procesadores simultáneos, reasignación el mismo día y a otro día. | Un aviso del día por entrega y fecha; otro solo en la fecha nueva. | Aprobado en pruebas |
| RF-12-10 | Visita atrasada de ayer y otra de hoy. | Solo la de hoy recibe aviso del día. | Aprobado en pruebas |
| RF-12-11 | Reloj a las 18:00; entrega registrada o anulada antes de preparar; procesador encendido a las 10:00. | Obsoleto sin llamar al transporte; obsoleto por visita cambiada; avisos creados y enviados a las 10:00. | Aprobado en pruebas |
| RF-12-12 | Buzones distintos, sin buzón, buzón cambiado y buzón asignado a mediodía. | Un destinatario por correo, asunto y cuerpo del día, sin aviso para el que no tiene buzón, `omitido` si cambió y aviso para el asignado a mediodía. | Aprobado en pruebas |
| RF-12-13 | `8`, `25:00`, `18:00`/`08:00` y vacíos. | Error de `check` en los tres primeros; vacíos valen 08:00 y 18:00. | Aprobado en pruebas |
| RF-12-06 ampliado | SMTP real del aviso del día con el conjunto de validación. | Recepción en cada buzón incluido y ningún cruce. | No ejecutado |

Regresión prevista: suite completa, `check`, `makemigrations --check --dry-run`, migración de `0004` a `0005` y vuelta atrás en una base de pruebas, y las pruebas del aviso «en camino» sin cambios de comportamiento.

## Enmienda del 2026-11-18 — Destino desde el padrón (Borrador)

Estado **Verificación técnica ejecutada el 2026-11-18** sobre `fdaza`, sin commit. Recepción SMTP real y aceptación pendientes.

- `entregasapp/tests/test_destino_padron.py` agrega 7 pruebas: E008, `destino` (mayúsculas, subdominio, lista vacía), aviso al correo del padrón con la variable antigua configurada, correo cambiado en la ficha antes del envío y cambio de correo concurrente con la preparación (nunca a un tercero). `test_avisos_reparto` reemplaza las pruebas de la lista por las del freno (lista vacía con `--smtp`, dominio no permitido, sin correo, mayúsculas y subdominio, correo compartido, correo borrado y dominio retirado). Las tres pruebas del spec 12 ya no usan archivos JSON.
- `python manage.py check` sin incidencias, `makemigrations --check --dry-run` sin cambios y suite completa con **1134 pruebas OK** en la base PostgreSQL de pruebas, con transporte simulado.
- La base local de la usuaria quedó migrada (`recetasapp/0005` y `entregasapp/0005`) y, contra ella, la pestaña «Datos» respondió 200 con el formulario para el superusuario. La revisión en el navegador (escritorio, móvil, teclado y axe) sigue pendiente.

| RF | Escenario | Esperado | Estado |
|---|---|---|---|
| RF-12-14 | Ambos avisos con correo del padrón; archivo JSON configurado. | Salen al correo del padrón; el JSON se ignora. | Aprobado en pruebas |
| RF-12-15 | Lista vacía, dominio no permitido, mayúsculas y subdominio. | Nada se envía con lista vacía; no permitido se omite; mayúsculas se envía; subdominio no. | Aprobado en pruebas |
| RF-12-16 | Paciente sin correo; correo agregado a mediodía. | «En camino» `omitido`/`sin_destino`, sin aviso del día; a mediodía se crea y se envía. | Aprobado en pruebas |
| RF-12-17 | Correo cambiado o borrado, dominio retirado, correo compartido y cambio concurrente con la preparación. | `omitido` con su código; un aviso por paciente; nunca a un tercero. | Aprobado en pruebas |
| RF-12-18 | `check` con dominios válidos e inválidos; `--smtp` con lista vacía. | E008 solo con inválidos; error claro del comando. | Aprobado en pruebas |
| RF-12-06 ampliado | SMTP real con correos de prueba en el padrón. | Recepción en cada buzón incluido y ningún cruce. | No ejecutado |

## Enmienda del 2026-11-18 — Envío a cualquier correo

Estado **Verificación técnica ejecutada el 2026-11-18**. Recepción SMTP real pendiente.

- `test_avisos_reparto.test_sin_lista_de_dominios_se_envia_a_cualquier_correo` reemplaza a la prueba que exigía dominios: con la lista vacía, un correo de cualquier dominio genera el aviso y `--smtp` lo envía. `test_destino_padron.test_destino` cubre la lista vacía (cualquier correo) y la lista con dominios (sigue restringiendo). Las pruebas de dominio no permitido con lista configurada se mantienen.
- Pruebas de avisos y correo: **74 pruebas OK**; `check` sin incidencias.
- Suite completa: **1134 pruebas OK** en la base PostgreSQL de pruebas, con transporte simulado.

## Enmienda del 2026-11-18 — Avisos de reasignación y resultado

Estado **Verificación técnica ejecutada el 2026-11-18** sobre `fdaza`, sin commit. Recepción SMTP real y aceptación pendientes.

- `entregasapp/tests/test_avisos_resultado.py` agrega **17 pruebas**: reasignación a otra fecha («para el DD/MM») y el mismo día («para hoy»), repetición idempotente, «Entregada» una vez, «No entregada» sin motivo ni nota, no entrega seguida de reasignación, paciente sin correo, vencimiento a las 2 horas, reprogramado ya registrado antes de enviar, reversión si falla la auditoría, freno de dominios configurado, anulación sin aviso, mensajes sin datos del paciente ni del Encargado, y tres escenarios concurrentes con `TransactionTestCase` e hilos (registro contra reasignación, dos registros con la misma operación y dos reasignaciones).
- Las pruebas del «en camino» y del aviso del día anulan `encolar_resultado`, igual que ya anulaban el aviso del día, para seguir probando solo su tipo. `test_inicio_traslado` comprueba ahora que no exista un aviso «en camino» tras registrar «Entregada», porque ese registro crea su propio aviso.
- `check` sin incidencias, `makemigrations --check --dry-run` sin cambios (migración `entregasapp/0006_avisoreparto_resultados`) y pruebas de avisos: **68 pruebas OK**.
- Suite completa: **1150 pruebas, 1149 OK y 1 error ajeno a este cambio**. `turnosapp.tests.test_sala_servidor` (spec 06) falla de forma intermitente al borrar su SQLite temporal (`PermissionError` de Windows: el archivo sigue tomado unos instantes después de cerrar el servidor de prueba). Repetida tres veces por separado, falló 1 y pasó 2; la prueba en sí termina bien y no usa los avisos.

| RF | Estado |
|---|---|
| RF-12-19 a RF-12-23 | Aprobado en pruebas; recepción real pendiente |

## Enmienda del 2026-11-18 — Envío automático desde el servidor web

Estado **Verificación técnica ejecutada el 2026-11-18** sobre `fdaza`, sin commit. Recepción real desde el servidor desplegado y aceptación pendientes.

- `entregasapp/tests/test_despachador.py` agrega **14 pruebas**: modos `smtp`/`simular`/`no` y E009; el ejecutor de pruebas lo desactiva; los comandos no lo inician; un fallo no detiene el ciclo ni registra direcciones; el aviso pendiente despierta al confirmar y el omitido no; un registro repetido no despierta dos veces; y, con el hilo real en `TransactionTestCase`, el clic de «Iniciar traslado» y el de «Entregada» se envían sin comando, un pendiente previo sale al arrancar, hilo y comando a la vez envían una sola vez y el hilo sigue vivo tras un fallo.
- Corrección durante la implementación: el cierre de conexiones a la base pasó del ciclo al bucle del hilo, porque cerrar en el ciclo también cortaba la conexión del proceso principal cuando se llamaba desde fuera del hilo.
- `turnosapp.tests.test_sala_servidor` levanta su servidor con `REPARTO_AVISOS_AUTOMATICOS=no`, para que ninguna prueba use la configuración SMTP del `.env`.
- Pruebas de avisos y despachador: **82 pruebas OK**; `check` sin incidencias.
- Suite completa: **1164 pruebas, 1163 OK**; el único error es el intermitente ya registrado de `turnosapp.tests.test_sala_servidor` (`PermissionError` de Windows al borrar su SQLite temporal), ajeno a este cambio.
- En la base local de la usuaria (21:59): los últimos avisos de reasignación quedaron `omitido`/`sin_destino` porque esos pacientes no tienen correo para avisos, y un aviso del día quedó `fallido`/`smtp_sin_conexion` tras tres intentos; a las 21:59 la conexión TCP a `smtp.gmail.com:587` funcionaba. Antes, tres avisos «entregado» y dos del día habían sido aceptados por SMTP con el comando.
