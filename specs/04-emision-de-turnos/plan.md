# Plan técnico — 04 / Emisión de turnos

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Validación: [validation.md](validation.md).
Fecha: 2026-11-02. Estado: diseño aprobado; código y verificación técnica completos. Vista previa, navegador, accesibilidad integral, papel y aceptación pendientes; ver `validation.md`. Acuerdo: `fdaza`, sin rama nueva y un único commit de cierre técnico; ver [spec.md](spec.md#acuerdo-de-ejecución).

## Inspección de la base

Se revisaron `CLAUDE.md`, informe, índice, documentos de los specs 02/03 y cuatro plantillas. `turnosapp/models.py` y `views.py` son esqueletos; `turnosapp/urls.py` tiene lista vacía y ya está montado bajo `/turnos/` en `cesfam/urls.py`.

`recetasapp.models` ofrece `Paciente`, `Receta` y `EntregaReceta`; el paciente dispone de nacimiento, `es_cronico` y `es_postrado`. No hay discapacidad y no se agregará. `recetasapp.services.evaluar_elegibilidad(receta, fecha)` devuelve elegibilidad y causas, fechas y cupo; la confirmación idempotente de entregas ya existe. `coreapp` ofrece normalización de RUT, `ModeloAuditado` y `registrar_accion`; el actor de auditoría admite nulo. Los layouts son `templates/components/Layout/base.html` y `base_publica.html`. La zona configurada es `America/Santiago` con fechas conscientes de zona.

Al inspeccionar había cambios ajenos: eliminación de `docs/verificacion-spec-01.md` y modificación de `specs/02-autenticacion-roles-auditoria/spec.md`. Preservarlos. La base local, el código y los acuerdos de ejecución anteriores no se modifican al escribir este plan.

Al comenzar la implementación también había una modificación del encabezado del spec 03; se conserva como cambio ajeno. T-04-01 incorpora `ContadorTurnosDiario`, `Turno`, `TurnoReceta`, `0001_initial.py` y 13 pruebas en `test_modelos.py`/`test_migraciones.py`. La relación turno-receta comprueba pertenencia en `clean()`; el servicio deberá verificarla también, pues no es una restricción entre tablas de la base. La migración depende de `recetasapp.0002_resultadofilaimportacion_pacientes_actualizados_and_more` y del usuario intercambiable. No se ha aplicado a la SQLite local. Ver resultados en `validation.md`.

## Diseño propuesto

Avance T-04-02: existe `turnosapp/services.py` con `emitir_turno(rut, operacion_id)` y resultado inmutable mínimo (`numero`, `fecha`, `creado_en`, `recuperado`), sin modelos clínicos serializados. La recuperación consulta nuevamente el bloqueo domiciliario, conserva la selección original y no vuelve a auditar. La reserva usa UPDATE condicional; un hallazgo de turno después de reservar provoca rollback de esa reserva. Auditoría y vínculos se confirman en la misma transacción. Doce intentos con espera exponencial limitada y variación aleatoria evitan reintentos sincronizados de SQLite; solo se reintentan bloqueos y colisiones conocidas. Admin deja expresamente sin registrar los tres modelos. Los casos de auditoría están en `test_servicios.py`, sin archivo separado. La vinculación del UUID a la sesión se implementará en T-04-03 y es requisito de las futuras vistas públicas.

Extender `turnosapp`; no crear otra app ni reconstruir padrón/autenticación. `services.py` concentrará normalización, reglas, emisión transaccional y recuperación idempotente. Formularios y vistas adaptarán el servicio al tótem, sin admitir selección pública de prioridad o recetas. La impresión se realiza sobre el resultado mínimo de la misma operación, sin abrir un listado ni una URL pública enumerable de turnos.

No se añade dependencia Python ni biblioteca de impresión. Usar Alpine y estáticos locales existentes para teclado, limpieza y botón imprimir; validación y correlativo siempre en servidor. El formulario seguirá siendo utilizable con teclado físico y sin depender de la validación JavaScript.

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-04-01 | Existente `coreapp/utils/rut.py`; nuevos `turnosapp/forms.py`, `services.py` | Reutilizar RUT; formulario sin datos en URL | Casos DV/K, vacíos y entrada manipulada |
| RF-04-02, RF-04-03, RF-04-04 | Existentes `recetasapp/models.py`, `services.py` en lectura; nuevo `turnosapp/services.py` | Bloqueo, elegibilidad colectiva y categoría | Límites de edad, combinaciones de recetas y ausencia de datos |
| RF-04-05, RF-04-06 | Existente `turnosapp/models.py`; nuevos `migrations/0001_initial.py`, `services.py` | Numeración, unicidad y relaciones | Restricciones, reinicio por fecha y concurrencia |
| RF-04-07, RF-04-08 | Existentes `turnosapp/views.py`, `urls.py`; nuevos `templates/turnos/totem.html`, `resultado.html`, `comprobante.html`, `static/css/turnos.css`, `static/js/totem.js` | Interfaz pública y estilos térmicos | Navegador, teclado, impresión y reimpresión |
| RF-04-09 | Existentes `coreapp/auditoria.py` (reutilización), `turnosapp/admin.py`; nuevo servicio | Evento con actor nulo; impedir escritura directa | Rollback y privacidad/CSRF |
| RF-04-10 | Nuevas pruebas de integración en `turnosapp/tests/` | Comprobar entrega independiente | Contadores e historial de recetas intactos |

`comprobante.html` será un fragmento del resultado, no un endpoint abierto por PK. Los archivos nuevos son propuesta; no se crean en esta fase.

## Datos y contratos

### Modelos propuestos

| Modelo | Datos y restricciones |
|---|---|
| `ContadorTurnosDiario` | `fecha` única, `ultimo_numero` entero no negativo. Una fila por día; nace con la primera emisión, sin comando de apertura. |
| `Turno` | Hereda `ModeloAuditado`; `paciente` FK PROTECT; `fecha` local; `numero` positivo; `tipo_atencion` (`general`, `preferencial`, `cronicos`); `estado` (`esperando`); `operacion_id` UUID único. Único `(fecha, numero)` y único condicional `(paciente, fecha)` en estado `esperando`; CHECK de número positivo y valores admitidos. Índice para fecha/estado/tipo. |
| `TurnoReceta` | `turno` y `receta` con PROTECT; único `(turno, receta)`. Representa la selección al emitir; servicio garantiza que ambas entidades pertenecen al mismo paciente. No contiene contador ni entrega. |

No duplicar RUT/nombre/nacimiento ni guardar diagnóstico, discapacidad o listado clínico en el comprobante. Auditar con `turno.emitido`, objeto `Turno`, PK técnica, actor nulo para autoservicio. No inferir que una cuenta de personal abierta en el mismo navegador sea responsable clínico de esa emisión. La acción fija identifica el origen de autoservicio sin introducir texto libre ni un usuario ficticio.

El ciclo de vida futuro agregará transiciones y adaptará restricciones; en este spec solo se crea `esperando`. No implementar caducidad automática, anulaciones ni un estado atendido para probar el modelo. Proteger historial frente a borrado de paciente/receta y no registrar modelos con escritura directa en Admin.

### Contrato de emisión y recuperación

Servicio propuesto `emitir_turno(rut, operacion_id)`: el RUT y el UUID son los únicos datos de entrada del dominio público; nunca aceptar tipo, número, fecha ni IDs de recetas del cliente como autoridad. El UUID se genera para el formulario y se vincula en servidor al contexto de operación del navegador; se conserva al reintentar. Un resultado se representa por código técnico y, en éxito, número/fecha/hora mínimos; no serializar objetos completos de paciente/receta.

1. Validar UUID y RUT. Capturar una fecha local y un instante de referencia por intento transaccional; usar esa fecha en edad, elegibilidad, contador y turno, evitando mezclar días alrededor de medianoche.
2. Buscar al paciente y aplicar bloqueo domiciliario antes de ofrecer resultado presencial. Un paciente no registrado no se crea.
3. Si el UUID ya identifica una operación, comprobar correspondencia con el paciente y devolver el original permitido en ese contexto, sin alterarlo. No aceptar UUID como credencial pública de consulta de otro turno. Reutilizar UUID con otro paciente se rechaza.
4. Consultar turno activo del paciente/fecha; devolver el existente aunque otra solicitud use distinto UUID. La consulta por RUT pasa de nuevo por el formulario, no por una URL enumerable. Recuperar no modifica relaciones, clasificación ni auditoría de emisión.
5. Para un turno nuevo, evaluar todas sus recetas con `evaluar_elegibilidad` y la misma fecha. Si ninguna es elegible, devolver código de negocio, sin consumir correlativo. Si hay elegibles, clasificar según las reglas del spec.
6. Dentro de `transaction.atomic()`, crear/obtener contador del día, reservar el siguiente valor con UPDATE condicional sobre el valor observado, crear turno y relaciones y registrar auditoría. La selección debe releerse dentro de la operación confirmada; no confiar en una lista enviada desde la pantalla.
7. Si existe conflicto de unicidad o de actualización, revertir y reabrir la transacción antes de releer/reintentar. La restricción por paciente protege dos UUID distintos. Usar reintentos acotados para `locked`/`busy` de SQLite y conflictos conocidos; otros errores no son reintentables indiscriminadamente. Tras agotarlos, respuesta recuperable que conserva el UUID y no afirma éxito.

La implementación debe ordenar las escrituras y relecturas para que la reserva del contador serialice emisores del día, sin pretender bloquear con `select_for_update()` en SQLite. Volver a comprobar existencia de turno/operación después de adquirir la reserva antes de confirmar, revirtiendo reservas que no se usan. No usar `MAX(numero)+1` sin protección ni contadores solo en memoria. No capturar `IntegrityError` y continuar dentro de una transacción rota. Las restricciones son la última garantía incluso al migrar a PostgreSQL.

Emitir no reserva cupo de receta: la selección representa un momento de evaluación, y otra entrega puede modificar su disponibilidad después. No prometer elegibilidad hasta la atención. Las pruebas de concurrencia con entregas/importación verificarán integridad y reintentos, sin bloquear legítimas entregas por la sola existencia de un turno.

### HTTP y contexto del tótem

| Ruta propuesta | Método / uso |
|---|---|
| `/turnos/totem/` | GET: formulario vacío y nuevo contexto de operación. POST: emitir o recuperar con CSRF y respuesta mínima renderizada. |
| `/turnos/totem/finalizar/` | POST con CSRF: limpiar contexto de operación y regresar al formulario. No cambia el turno persistente. |

Para recuperar una respuesta perdida se reenvía el formulario con la misma operación; no se incluye el RUT en redirecciones. Reimprimir opera sobre el fragmento del resultado ya obtenido, sin llamar otra vez a la emisión. No existe endpoint de ficha pública, estado clínico o listado por RUT.

Propuesta de interfaz: limpiar el RUT al mostrar resultado; botón «Nueva atención» para finalizar; resultado de éxito se limpia tras 30 s de inactividad con aviso visible y opción de ampliar; formulario en edición se limpia tras 120 s con aviso y opción de continuar. Son valores técnicos revisables durante validación de usabilidad. Al terminar o expirar, invalidar el contexto recuperable y limpiar DOM/campos. Tras volver de impresión, reanudar la limpieza y no usar el evento de impresión como confirmación del papel. `pageshow` debe limpiar un resultado restaurado por navegación; usar `no-store` y no persistir datos del paciente en almacenamiento del navegador. Mantener el mínimo contexto técnico en sesión de servidor, nunca una ficha.

Si ya existe sesión de personal en el equipo, limpiar únicamente las claves del tótem; no cerrar arbitrariamente su sesión. Se recomienda un navegador/perfil dedicado durante la demostración, sin crear autenticación nueva para el dispositivo.

## Permisos e interfaz

Avance T-04-03: existen `EmisionTurnoForm`, vistas públicas de entrada/finalización/ampliación, `totem.html`, `resultado.html`, fragmento `tiempo.html`, `turnos.css` y `totem.js`. Se reutiliza el layout público y la paleta; la entrada alinea instrucciones y teclado, y el resultado centra el número. No se incorpora aún impresión (T-04-04). La sesión guarda UUID, vencimiento, huella HMAC del RUT y señal de resultado; nunca el RUT, nombre o recetas. La huella vincula reintentos al mismo paciente sin guardar el identificador en claro. Se guarda el vínculo antes de emitir para recuperar respuestas perdidas. El servicio continúa siendo la única autoridad para categoría, recetas y correlativo.

La ruta adicional POST `/turnos/totem/continuar/` extiende el contexto vigente con CSRF, sin volver a emitir ni revivir operaciones expiradas. El aviso aparece 20 segundos antes del vencimiento; el formulario renueva el plazo ante actividad, como máximo una vez cada 30 segundos, y el botón permite ampliación explícita. Al devolver un formulario con error se renueva su plazo de 120 segundos y se borra la entrada; el resultado dura 30 segundos. Sin JavaScript se ofrece entrada física y recarga de limpieza mediante `noscript`. La finalización de una pestaña antigua no borra un contexto más reciente. La revisión real de JavaScript, navegación atrás, foco, móvil y usabilidad queda en T-04-05; las pruebas HTTP y `node --check` no la sustituyen.

Base pública existente, paleta y tipografías locales; número como elemento principal, instrucciones breves y teclado con K, borrar y limpiar. Mantener foco, etiquetas, regiones de estado y mensajes asociados. No mostrar nombre/RUT tras enviar ni tipo de atención si revela una condición del paciente. La categoría es interna para la futura cola.

Pantallas de error diferenciadas: formato inválido; consulta al personal por paciente no encontrado; aviso acordado para domicilio; sin receta utilizable; operación ocupada; fallo técnico sin éxito. La interfaz no muestra stack traces ni códigos clínicos. No añadir enlaces públicos al padrón ni botones de urgencia/discapacidad.

### Comprobante térmico

Avance T-04-04: `comprobante.html` se incluye como hijo directo de `body` en el bloque de scripts del resultado, sin endpoint adicional. En pantalla está oculto; en impresión se ocultan todos los hijos del cuerpo excepto ese fragmento. Así el formulario de entrada/error tampoco imprime RUT, botones ni campos ocultos. El comprobante tiene contenido útil de 72 mm para rollo nominal de 80 mm con márgenes de 4 mm por lado. `@page` conserva tamaño automático y no impone altura; se selecciona papel de 80 mm en el controlador. Incluye solo número, fecha/hora e instrucción genérica, sin categoría ni identidad.

El botón habilitado por JavaScript renueva el contexto antes de abrir `window.print()`; después ofrece «Volver a imprimir número». Cancelar no modifica turno, auditoría ni recetas. `beforeprint` pausa limpieza y `afterprint` solo reanuda temporizador y comprueba vigencia del contexto; no certifica salida física. Si caducó mientras estaba abierto, se limpia y se recupera el turno mediante un nuevo ingreso de RUT. Sin JavaScript se puede usar la opción Imprimir del navegador. El CSS está preparado para 80 mm, pero no se ha verificado visualmente todavía. Las pruebas del diálogo son simuladas con Node, no con impresora/navegador real; vista previa y papel quedan en T-04-05.

Fragmento HTML con número grande, fecha/hora local y «Espera el llamado de tu número». CSS `@media print` oculta teclado, botones, menú, entradas y mensajes de error. Diseñar para rollo nominal de 80 mm con márgenes interiores ajustables al área imprimible; no fijar una altura que corte el contenido. Desactivar encabezados/pies del navegador en la configuración de prueba y seleccionar el tamaño de papel correspondiente en el controlador.

`window.print()` abre el diálogo y no confirma salida física; CSS permite adaptar la presentación impresa. Referencias: [MDN — Window.print](https://developer.mozilla.org/en-US/docs/Web/API/Window/print) y [MDN — Printing](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Printing). No usar `afterprint` para marcar un estado «impreso» ni interpretar cancelar como fallo de emisión. No prometer detección web de falta de papel. El mensaje de éxito confirma turno registrado y ofrece volver a imprimir si hace falta.

El modelo y conexión de impresora no están definidos. El contrato es usar una térmica de 80 mm instalada y reconocida por el sistema operativo. No contempla comandos ESC/POS, USB directo, impresión silenciosa ni instalación remota de controladores. La impresión física queda como comprobación separada y pendiente si el hardware no está disponible.

## Migraciones y reversión

Proponer `turnosapp/migrations/0001_initial.py` con dependencia de la migración vigente de `recetasapp` (`0002`, comprobar nombre exacto al implementar) y usuario intercambiable si lo requiere `ModeloAuditado`. Sin migraciones ni columnas nuevas en recetas, importaciones o usuarios; sin pacientes/turnos demo en migración ni escrituras al arrancar.

Probar base vacía y actualización desde specs 01/02/03 con pacientes y recetas sintéticos, conservando contadores e historial previos. No migrar la SQLite local durante definición o validación aislada. Revertir la migración elimina los turnos y relaciones: antes de una aplicación real autorizada, respaldar y comprobar restauración consistente. No anunciar reversión sin pérdida de datos.

## Plan de implementación

1. Crear esquema, restricciones y pruebas de migración.
2. Implementar clasificación, selección, contador, idempotencia y auditoría; probar concurrencia antes de exponer emisión.
3. Incorporar formulario, vistas, contexto temporal, limpieza y teclado accesible.
4. Incorporar comprobante de 80 mm, diálogo y reimpresión.
5. Verificar integración/regresión, HTTP real, accesibilidad, rendimiento e impresión disponible y documentar resultados y límites.

Cada tarea deja el proyecto ejecutable. El primer cambio ejecutable es el esquema probado en base temporal; el último paso es registrar la validación real y pendientes, sin convertir pruebas planeadas en aceptación.

## Plan de pruebas

Ejecutor de Django y SQLite temporal; nuevos módulos propuestos: `turnosapp/tests/test_modelos.py`, `test_migraciones.py`, `test_servicios.py`, `test_concurrencia.py`, `test_vistas.py`, `test_auditoria.py`, `test_integracion.py`. No usar pytest ni datos reales.

Cubrir todos los RF, cumpleaños 60/80/81, postrados menores de 60, crónicos en ambos lados del umbral, RUT con K, varias recetas, sin recetas, agotadas/futuras/vencidas, receta de otro paciente manipulada, repetición desde dos navegadores, operación reutilizada para otro paciente y cambio de fecha con reloj controlado. Comprobar que recuperar conserva selección y que nuevas recetas no se agregan retroactivamente.

Escenarios mínimos con `TransactionTestCase`, barreras e hilos/conexiones separados: (1) varios emisores para un paciente con el mismo UUID; (2) mismo paciente con UUID distintos; (3) varios pacientes disputando el contador diario. Añadir emisión frente a entrega/importación y fallo de auditoría. Tras cada escenario: cero números duplicados, un activo por paciente/día, relaciones del paciente correcto, contador coherente y un evento por emisión. Registrar hilos, iteraciones, resultados y errores recuperables, no solo «sin excepciones».

Pruebas HTTP con CSRF real, GET sin escritura de dominio, campos manipulados, ausencia de RUT en URL/logs/respuesta final, acceso al comprobante ajeno, expiración/finalización y navegación atrás. Verificar Admin sin escritura, sesión de personal conservada y contadores/entregas del spec 03 intactos. Proponer `tools/verificar_spec_04_http.py` siguiendo el aislamiento de la herramienta del 03, con SQLite sintética temporal y credenciales de demostración no expuestas.

Comandos previstos para implementación: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py test turnosapp --noinput`, `python manage.py test --noinput`, `python tools/verificar_spec_04_http.py` y `git diff --check`. No se han ejecutado como validación funcional del 04.

En navegador: escritorio, móvil, teclado, zoom, mensajes y limpieza, auditoría A/AA, vista previa/archivo impreso de 80 mm y, cuando exista equipo, papel real sin recortes, número legible, cancelar y reimprimir. Registrar impresora, controlador, navegador, tamaño/márgenes y evidencia sintética. La usabilidad con cinco usuarios no se sustituye con axe.

Medir al menos 100 solicitudes por escenario con padrón de 670 pacientes, indicando equipo, solicitudes simultáneas, muestras exitosas/conflictos y método de p95. Separar emisión nueva, recuperación y rechazo; evitar que una muestra de recuperaciones o el tiempo del diálogo oculte la latencia de escritura. El objetivo es ≤ 2 s p95 según RNF-05, no una garantía basada en el rendimiento histórico de recetas.

## Riesgos, alternativas y dependencias

- SQLite serializa escrituras; la carga puede agotar reintentos. Responder recuperable, conservar identidad del intento y medir bajo concurrencia.
- El tótem valida un RUT, no la identidad física. Limitar respuesta al número y orientación mínima; no exponer una consulta pública del padrón o de recetas.
- Sin validación automatizada de discapacidad ni urgencia, la clasificación no cubre todas las preferencias del servicio. Es un límite explícito solicitado, para resolver con personal en una definición posterior.
- Sin logística ni ventanillas, no hay estado real de despacho ni destino asignado. No fabricar datos para aparentar HU-07 completa.
- El navegador no certifica salida de papel. Vista previa y PDF no verifican controlador, impresora ni recortes reales.
- La disponibilidad de receta puede cambiar después de emitir; conservar separación entre llegada y dispensación, con revalidación futura.

## Documentos afectados

En esta definición: cuatro documentos del 04 e índice. Durante la implementación: actualizar `docs/estructura.md`, `README.md` y memoria del proyecto con rutas/contratos realmente existentes; registrar evidencia en `validation.md` y avance en `tasks.md`. No modificar retrospectivamente los acuerdos ni la evidencia del 02/03.

## Decisiones para implementar

Diseño técnico del spec aprobado y arranque de T-04-01 confirmado. Compatibilidad física pendiente del equipo disponible. Rige el acuerdo de ejecución propio del 04: rama `fdaza`, sin cambios de rama y un commit al finalizar. Los pasos posteriores requieren las pausas de revisión acordadas.
