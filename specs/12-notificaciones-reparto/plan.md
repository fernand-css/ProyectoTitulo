# Plan técnico — 12 / Aviso de reparto en camino por correo

[Especificación](spec.md) · [Tareas](tasks.md) · [Validación](validation.md)

Estado **Aprobado**. Base `crojas-base@4b682422500c9662b9dc9bcc79e52f9f6a0c63bf`. Implementación, migraciones de prueba y envíos de prueba autorizados el 2026-11-18.

## Inspección de la base

- `entregasapp/consultas.py` (`ruta_del_dia`), `views.py` (`MisEntregasView`, `MapaView` e `IrAView`) y `templates/entregas/_tarjeta_intento.html` presentan los intentos y la navegación actual. La vista de «Ir a esta parada» exige coordenadas. La tarjeta permite ofrecer el inicio también cuando faltan.
- `entregasapp/models.py` distingue `Entrega`, `IntentoEntrega` y `RecetaEntrega`. Los servicios del spec 08 serializan escrituras con `_bloquear_jornada` y actualizaciones condicionales, y auditan mediante `auditar`. Reasignar un intento pendiente crea otro y cierra el anterior como `REASIGNADO`.
- `recetasapp/models.py` no define correo en `Paciente`. La copia local configura Gmail SMTP con TLS en `cesfam/settings.py`. La base remota selecciona consola en desarrollo y SMTP en otros entornos. El diseño usa el backend SMTP de Django con la configuración de correo disponible y conserva el comportamiento de los correos de cuentas. La conectividad SMTP sigue pendiente de verificación real.

## Diseño y datos

| Elemento | Propuesta |
|---|---|
| Inicio de traslado | Campos nulos `traslado_iniciado_en` y `traslado_iniciado_por` en `IntentoEntrega`, con ambos presentes o ambos vacíos. Servicio `iniciar_traslado(actor, intento_id)` en `entregasapp/services.py`. |
| Bandeja de salida | Modelo `AvisoReparto` en `entregasapp/models.py` con UUID, FK a intento, tipo, fecha de creación, vencimiento, estado, firma del destino, contador de intentos, próxima ejecución, token y vencimiento de reserva, fecha de aceptación y código técnico de resultado. Restricción única por intento y tipo. Índice para estado y próxima ejecución. |
| Lista de prueba | Ruta privada `REPARTO_BUZONES_PRUEBA_ARCHIVO`, vacía por defecto. Archivo JSON fuera del repositorio con el nombre de la base de demostración y una lista de pares `paciente_id` interno / `correo`. Se validan base, IDs positivos, direcciones válidas y unicidad de paciente y dirección. El equipo genera la lista a partir de pacientes sintéticos verificados y la revisa si reconstruye la base o cambia los buzones. El padrón conserva su esquema. |
| Vínculo de destino | En el inicio se guarda una firma HMAC de la base, el ID del paciente y el buzón vigente. Antes del envío se vuelve a leer la lista, se valida la asignación y se compara la firma. Una asignación ausente, retirada o modificada termina como `omitido`. No se guarda la dirección en la bandeja. Una lista declarada e inválida se reporta con un código técnico y se impide procesar por SMTP hasta corregirla. Si falla su lectura al confirmar el inicio, se guarda el traslado y se omite su aviso. |
| Interfaz | `POST /entregas/intentos/<int:pk>/iniciar-traslado/` desde la tarjeta de «Mis entregas». `SoloEncargadoView` y el servicio aplican el permiso. El servicio valida intento vigente, asignación, fecha local y entrega programada. La vista usa CSRF y redirige a «Mis entregas». Los textos de interfaz reflejan el inicio guardado. |
| Transporte | `entregasapp/notificaciones.py` y el comando `procesar_avisos_reparto` con modos explícitos `--simular` y `--smtp`, y opción `--continuo` para la demo. La simulación usa un transporte en memoria en una base separada de la prueba SMTP. `--smtp` usa `EmailMessage` con el backend SMTP de Django, remitente y configuración `EMAIL_*` existentes. No se agregan dependencias externas. |

## Contratos de escritura y procesamiento

1. **Confirmar.** El servicio toma `_bloquear_jornada`, valida el intento y registra el inicio mediante un UPDATE condicional sobre la fila del intento. En la misma transacción crea el evento y la auditoría `intento.traslado_iniciado`. El campo `operacion_id` del resultado actual queda disponible para el registro de la visita. Un inicio previo válido devuelve el estado guardado.
2. **Reservar.** El procesador toma un aviso pendiente con una actualización condicional, asigna token y vencimiento y libera la transacción. Usa `reservado` antes de autorizar el envío. Una reserva vencida en ese estado puede recuperarse.
3. **Preparar.** Justo antes de autorizar SMTP, comprueba el plazo, el intento pendiente, la entrega programada y el destino firmado. Para serializar con los escritores del reparto, toma primero la fila del intento mediante actualización condicional y después actualiza la fila del aviso con el token vigente. Marca `obsoleto` o `omitido` cuando corresponda. Si sigue válido, pasa una sola vez a `en_envio`. La ventana entre esta transición y la llamada SMTP se mantiene corta. El envío ya iniciado puede quedar en manos del servidor aunque la visita cambie inmediatamente después.
4. **Enviar y registrar.** La conexión y el envío se ejecutan fuera de la transacción. Se registra `aceptado_smtp` al confirmar el envío en el backend o `simulado` en pruebas. Se reintenta un fallo temporal comprobable antes de enviar o un rechazo SMTP explícito temporal, con un máximo de tres intentos y esperas de 60 y 120 segundos, siempre antes de los 30 minutos. Fallos definitivos o límite agotado pasan a `fallido`. Si se desconecta durante el envío o expira una reserva en `en_envio`, el resultado es `incierto`. Un resultado tardío inequívoco solo puede actualizar su propio token. No se devuelve un resultado incierto a la cola automáticamente.
5. **Trazar.** Registrar solamente UUID, estado de procesamiento y códigos técnicos acotados. Evitar volcar excepciones SMTP completas, cuerpos, destinatarios, datos del paciente o credenciales. La aceptación SMTP se conserva aunque falle el cierre de la conexión después del envío confirmado.

## Mapa de archivos y pruebas

| RF | Archivos previstos | Verificación |
|---|---|---|
| RF-12-01 y RF-12-02 | `entregasapp/{models,services,views,urls}.py`, `templates/entregas/_tarjeta_intento.html`, migración y `entregasapp/tests/test_inicio_traslado.py`. | Permisos, CSRF, validación de fecha/asignación, doble clic, carrera y rollback. |
| RF-12-03 a RF-12-05 | `entregasapp/notificaciones.py`, `entregasapp/management/commands/procesar_avisos_reparto.py`, `cesfam/settings.py`, `.env.example` y `entregasapp/tests/test_avisos_reparto.py`. | Enrutamiento entre buzones distintos, obsolescencia, reservas, fallos y recuperación sin reenvíos inciertos. |
| RF-12-06 | `README.md` y [validation.md](validation.md). | Simulación, prueba de navegador y recepción real por cada paciente de validación. |

## Migración, riesgos y despliegue de prueba

- Migración aditiva dependiente de `entregasapp/0002_ordenruta` e historial de usuarios vigente. **Integración en `fdaza` (2026-11-18):** como el spec 13 ya ocupaba `entregasapp/0003_recetaentrega_preparacion`, la migración quedó como `0004_avisoreparto_traslado`, dependiente de esa `0003`, con el mismo contenido; su prueba de migración retrocede a esa `0003`. Agrega los campos nulos y la tabla, sin rellenar datos históricos. Verificar instalación limpia y actualización desde el esquema anterior en PostgreSQL desechable.
- Para revertir una prueba migrada, detener el procesador y respaldar antes de revertir el esquema. Al revertir se pierde el historial nuevo de avisos e inicios. La reversión no retira correos que SMTP ya aceptó.
- La mayor exposición es un mapeo errado o desactualizado. Usar una base sintética explícita, lista privada autorizada, revalidación de destino y prueba de cruce entre buzones. El proceso SMTP debe validar su configuración de prueba antes de reclamar avisos.
- Usar tiempo de espera finito para SMTP y mantener la red fuera de las transacciones. Los ensayos automáticos usan transporte simulado incluso si la copia local tiene SMTP habilitado.
- AWS y otros canales quedan para otra evaluación. La prueba real usa la configuración existente y solo los buzones ya autorizados.

## Enmienda del 2026-11-18 — Aviso del día (Borrador)

Diseño de RF-12-07 a RF-12-13 de la [enmienda](spec.md#enmienda-del-2026-11-18--aviso-del-día-borrador). Se implementa sobre `fdaza`, donde el spec 12 ya está integrado con su migración `entregasapp/0004_avisoreparto_traslado`.

### Diseño y datos de la enmienda

| Elemento | Propuesta |
|---|---|
| Tipo nuevo | `AvisoReparto.Tipo.DEL_DIA = "delivery.scheduled_today"`. Como tiene 24 caracteres, `tipo` pasa de `max_length=20` a `32`. |
| Campos nuevos en `AvisoReparto` | `entrega` (FK nula a `Entrega`, `PROTECT`, `related_name="avisos"`) y `fecha` (`DateField` nula). El aviso del día guarda además en `intento` el intento pendiente que lo originó, para conservar la trazabilidad. Los avisos «en camino» dejan ambos campos vacíos. |
| Restricciones | `UniqueConstraint(fields=["entrega", "fecha"], condition=Q(tipo="delivery.scheduled_today"), name="aviso_reparto_dia_unico")`, que cumple RF-12-09 aunque haya dos procesadores. `CheckConstraint`: un aviso del día lleva `entrega` y `fecha`; uno «en camino» los deja vacíos (`aviso_reparto_dia_completo`). Se conserva la restricción única por intento y tipo. |
| Migración | `entregasapp/0005_avisoreparto_del_dia`, aditiva y dependiente de `0004_avisoreparto_traslado`: cambia el largo de `tipo` y sus opciones, agrega los dos campos nulos y las dos restricciones, sin rellenar datos. |
| Configuración | `REPARTO_AVISO_DIA_HORA` y `REPARTO_AVISO_DIA_LIMITE` en `cesfam/settings.py`, leídas como texto `HH:MM` (por omisión `08:00` y `18:00`), y en `.env.example`. `entregasapp/checks.py` agrega `entregasapp.E006` (formato) y `entregasapp.E007` (la hora del aviso no es anterior a la límite). |
| Textos | En `notificaciones.py`, un diccionario `TEXTOS` por tipo con asunto y cuerpo. «En camino» conserva los suyos; el del día usa «Hoy llega tu reparto de prueba» y «Tu reparto de prueba está programado para hoy. Te avisaremos cuando vaya en camino.». Los transportes `enviar_simulado` y `enviar_smtp` reciben el tipo además del correo. |

### Contratos de la enmienda

1. **Encolar del día.** `notificaciones.encolar_del_dia(ahora, buzones)` se llama al comienzo de cada lote de `procesar_avisos`, antes de recuperar y reclamar. Si la hora local no está en la franja `[hora del aviso, hora límite)`, no hace nada. Si está, busca intentos `pendiente` con `fecha_programada = hoy`, entrega `programada` y paciente presente en `buzones`, y deja fuera las entregas que ya tienen aviso del día para hoy. Crea un aviso por entrega con `estado=pendiente`, `fecha=hoy`, `vence_en` igual a la hora límite de hoy (hora local de `TIME_ZONE`), `proximo_en=ahora` y la misma firma HMAC del RF-12-03. Cada creación va en su propio `transaction.atomic()`; un `IntegrityError` en la restricción única significa que otro procesador ya lo creó y se ignora. Las fechas anteriores nunca se consideran (RF-12-10). No toma `bloquear_cola` ni `_bloquear_jornada`: solo lee el reparto y escribe en la bandeja.
2. **Preparar según el tipo.** `_preparar` conserva la rama «en camino». Para el aviso del día comprueba el plazo, que la entrega siga `programada` y que tenga un intento `pendiente` con `fecha_programada = aviso.fecha`, sin importar el Encargado. Para serializar con los escritores del reparto toma esa fila de intento con la misma actualización condicional sin cambio que ya usa la rama «en camino». Si no hay intento vigente, el aviso queda `obsoleto` con `visita_cambiada`; si el buzón cambió, `omitido` con `destino_cambiado`.
3. **Envío, reintentos, caducidad y estado incierto.** Sin cambios: valen los contratos 2 a 5 del plan original. `_recuperar` ya marca como obsoleto cualquier aviso pendiente vencido, con lo que se cumple la hora límite (RF-12-11).
4. **Comando.** `procesar_avisos_reparto` no cambia sus opciones. En modo `--continuo` cada vuelta de cinco segundos crea los avisos del día que falten, y con eso se cumple RF-12-08 sin tocar los servicios de programación.

### Mapa de archivos y pruebas de la enmienda

| RF | Archivos previstos | Verificación |
|---|---|---|
| RF-12-07 a RF-12-11 | `entregasapp/models.py`, `entregasapp/migrations/0005_avisoreparto_del_dia.py`, `entregasapp/notificaciones.py` y la prueba nueva `entregasapp/tests/test_aviso_del_dia.py`. | Reloj simulado con `patch("entregasapp.notificaciones.timezone.now")` a las 07:59, 08:00, 17:59 y 18:00; programada a las 11:00; atrasada; reasignación el mismo día y a otro día; entrega cerrada o anulada antes de preparar; doble ejecución. |
| RF-12-09 concurrente | `entregasapp/tests/test_aviso_del_dia.py` (`TransactionTestCase` con hilos). | Tres escenarios de carga: dos procesadores que encolan a la vez, dos que procesan el mismo lote, y encolar mientras se reasigna la entrega. Se exige un solo aviso del día y un solo envío. |
| RF-12-12 | `entregasapp/notificaciones.py` y pruebas. | Asunto y cuerpo por tipo, un destinatario, sin buzón no hay aviso, buzón cambiado da `omitido`, buzón asignado a mediodía genera el aviso. |
| RF-12-13 | `cesfam/settings.py`, `.env.example`, `entregasapp/checks.py` y `entregasapp/tests/test_configuracion_mapa.py` (o una prueba nueva de configuración). | `8`, `25:00` y el par `18:00`/`08:00` dan error; vacíos usan los valores por omisión. |
| RF-12-06 ampliado | `README.md` y [validation.md](validation.md). | Recepción real del aviso del día en cada buzón del conjunto de validación y ausencia de cruces. |

### Riesgos de la enmienda

- **Zona horaria.** La franja se evalúa con `timezone.localtime()` en `America/Santiago`; las pruebas cubren los bordes de las 08:00 y las 18:00. El cambio de horario de verano no altera la franja, porque se compara la hora local.
- **Procesador detenido.** Si no corre entre la hora del aviso y la límite, ese día no sale el aviso. Se documenta en el README cómo dejarlo con `--continuo` o en el Programador de tareas de Windows.
- **Volumen.** Con ~70 pacientes postrados y unos pocos cientos de mayores de 80 años, los avisos de un día caben en pocos lotes de 25. La consulta de encolado usa el índice de `fecha_programada` y la restricción única.
- **Lista de buzones desactualizada.** Igual que en el aviso «en camino», la firma y la revalidación antes del envío evitan mandar a un buzón retirado.

## Enmienda del 2026-11-18 — Destino desde el padrón (Borrador)

Diseño de RF-12-14 a RF-12-18 de la [segunda enmienda](spec.md#enmienda-del-2026-11-18--destino-desde-el-padrón-borrador). Requiere antes la migración `recetasapp/0005_paciente_correo_avisos` de la [enmienda del spec 03](../03-padron-y-recetas/plan.md#enmienda-del-2026-11-18--correo-para-avisos-borrador).

### Diseño de la enmienda

| Elemento | Propuesta |
|---|---|
| Configuración | Se retira `REPARTO_BUZONES_PRUEBA_ARCHIVO` de `cesfam/settings.py` y `.env.example`. Se agrega `REPARTO_CORREO_DOMINIOS_PERMITIDOS`: texto separado por comas, convertido en `settings` a una tupla de dominios en minúsculas, sin espacios ni elementos vacíos; vacía por omisión. |
| Comprobación | `entregasapp/checks.py` agrega `entregasapp.E008` si algún elemento no es un nombre de dominio válido (etiquetas de letras, dígitos y guiones separadas por puntos, con al menos un punto). |
| Destino | `notificaciones.destino(paciente_id, correo)` devuelve el correo si no está vacío y su dominio (lo que sigue a la última `@`, en minúsculas) está exactamente en la lista; si no, devuelve el código `sin_destino` o `dominio_no_permitido`. Se elimina `cargar_buzones` y `ListaBuzonesInvalida`. |
| Aviso «en camino» | `encolar_salida(intento, ahora)` lee `intento.entrega.paciente.correo_avisos` dentro de la misma transacción de `iniciar_traslado` y crea el aviso `pendiente` con la firma, u `omitido` con el código de `destino`. |
| Aviso del día | `encolar_del_dia(ahora)` ya no recibe buzones: filtra en la consulta los pacientes con `correo_avisos` distinto de vacío, trae el correo con `values_list` y aplica `destino` en Python antes de crear cada aviso. Los sin destino válido no generan fila. |
| Preparación | `_preparar(aviso_id, token)` vuelve a leer `Paciente.correo_avisos` con la entrega (en la misma consulta que hoy obtiene `paciente_id`), aplica `destino` y compara la firma. Cambiado o borrado: `omitido`/`destino_cambiado`; dominio retirado: `omitido`/`dominio_no_permitido`. |
| Comando | `procesar_avisos_reparto --smtp` lanza `CommandError("SMTP requiere al menos un dominio en REPARTO_CORREO_DOMINIOS_PERMITIDOS.")` si la tupla está vacía. `procesar_avisos` deja de cargar la lista en cada vuelta. |
| Documentación | `README.md`: se reemplaza la sección de la lista JSON por la del correo del padrón y el freno de dominios, con ejemplo `example.invalid`. |

### Pruebas de la enmienda

- `test_avisos_reparto`, `test_inicio_traslado` y `test_aviso_del_dia` dejan de escribir el archivo JSON: los pacientes sintéticos reciben `correo_avisos` en `example.invalid` y las pruebas fijan `REPARTO_CORREO_DOMINIOS_PERMITIDOS=("example.invalid",)`. Las pruebas que validaban la lista (otra base, direcciones duplicadas) se reemplazan por las del freno.
- Nuevas: lista vacía (nada se envía; `--smtp` falla), dominio no permitido, mayúsculas, subdominio, paciente sin correo, correo borrado o cambiado antes del envío, dominio retirado de la lista, dos pacientes con el mismo correo y E008.
- Concurrencia: la Q.F. cambia el correo mientras el procesador prepara el envío (`TransactionTestCase` con hilos): o sale al correo firmado o queda `omitido`, nunca a un tercero. Se conservan los escenarios concurrentes existentes.

### Riesgos de la enmienda

- **Dirección real en el padrón.** El freno de dominios impide enviarle. El equipo debe usar dominios de prueba propios y no agregar dominios públicos (por ejemplo, `gmail.com`) a la lista, salvo buzones de prueba creados para la demo; el README lo advierte.
- **Avisos firmados con la lista anterior.** Se omiten si el correo del padrón no coincide; es el comportamiento seguro.
