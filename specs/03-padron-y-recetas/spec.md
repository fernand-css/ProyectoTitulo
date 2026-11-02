# SPEC 03 — Padrón y recetas

> **Estado:** Aprobado
> **Depende de:** [SPEC 01 — Base del proyecto](../01-base-del-proyecto/spec.md) y [SPEC 02 — Autenticación, roles y auditoría](../02-autenticacion-roles-auditoria/spec.md)
> **Fecha:** 2026-11-01
> **Objetivo:** Permitir a la Q.F. importar el padrón sintético y sus recetas vigentes y crear recetas simuladas, y al Técnico consultar su vigencia y registrar las entregas del ciclo conservando el historial.

Módulo solicitado: `recetasapp`, con reutilización del núcleo y la autenticación existentes.
Fuente: respuestas del equipo 1A/2A/3A y confirmación expresa de las cuatro reglas; HU-21, HU-23, RNF-01 y RNF-07 de [Informe.md](../../docs/Informe.md).
Implementación autorizada: SÍ, mediante invocación de `spec-impl`, confirmación «comienza» y posterior instrucción de continuar todos los pasos sin pausas. Revisión documental: Aprobado. Código y verificación técnica completados; revisión visual/móvil y auditoría de accesibilidad en navegador pendientes por limitación del entorno. Aceptación funcional pendiente.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

Al definir este spec, `recetasapp` conservaba su esqueleto: no existían pacientes, recetas, importaciones ni entregas del ciclo. Farmacia necesita cargar el padrón sin volver a digitarlo, reconocer las recetas utilizables y conocer cuántas entregas se han completado y cuántas restan. La implementación incorpora ahora ese control interno con modelos, servicios, formularios, pantallas y pruebas.

La plataforma actúa como control interno simulado, separado del sistema clínico. Una entrega parcial significa una entrega del ciclo de la receta, por ejemplo «3 de 6»; no representa fracciones de cantidades de medicamentos.

## Actores y permisos

| Acción / datos | Anónimo / tótem | Técnico | Encargado de terreno | Q.F. | Superusuario activo |
|---|---|---|---|---|---|
| Consultar padrón, buscar paciente y consultar recetas e historial | No | Sí | No | Sí | Sí |
| Descargar plantillas, importar y consultar reportes de cargas | No | No | No | Sí | Sí |
| Crear receta simulada o renovación vinculada | No | No | No | Sí | Sí |
| Confirmar entrega del ciclo | No | Sí | No | No | Sí |
| Consultar auditoría genérica | No | No | No | No | Sí, según spec 02 |
| Borrar pacientes, recetas, entregas o bitácoras desde interfaces | No | No | No | No | No |

La matriz aplica a consultas, formularios, descargas y servicios, incluyendo acceso directo por URL e IDs manipulados. Mantener las reglas de cuenta activa, perfil y rol único de la spec 02 y la excepción del superusuario activo. El Encargado recibirá los datos necesarios para reparto en su propia spec; aquí no recibe acceso general al padrón.

## Alcance y exclusiones

Incluye HU-23 y el control interno de HU-21: padrón sintético, importación CSV y Excel `.xlsx` con plantillas propias, actualización de existentes, reporte de rechazos, bitácora de cargas, búsqueda y consulta, creación de recetas por Q.F., vigencia, renovación con historial y confirmación de entregas por Técnico. Incluye datos reproducibles para demostrar la carga de 670 pacientes sintéticos.

Se prepara un servicio de elegibilidad reutilizable por turnos. El bloqueo efectivo de emisión presencial de HU-07 se implementará y verificará con la spec de turnos; este módulo no crea turnos. La confirmación manual permite demostrar HU-21 mientras no exista ese flujo. Las integraciones futuras deben reutilizar el registro idempotente de entrega, evitando contar dos veces una misma atención.

Fuera: API o acceso a Rayén, archivos reales de pacientes, prescripción clínica, inventario y saldos por medicamento, preparación/no retiro de HU-17, turnos y ventanillas, georreferenciación, rutas y entregas domiciliarias, cuentas de pacientes, notificaciones, WebSocket, funcionamiento sin conexión, despliegue y carga automática programada. `EntregaReceta` no representa un despacho domiciliario.

## Historias y flujo

1. Q.F. descarga una plantilla y carga un CSV o `.xlsx` sintético. El sistema valida estructura, RUT y reglas antes de escribir cada fila; procesa las válidas aunque existan otras inválidas.
2. Al finalizar muestra totales, omisiones y rechazos por número de fila y motivo. Una carga queda identificada por su responsable, fecha, formato y referencia técnica del archivo.
3. Técnico o Q.F. busca por RUT o nombre y consulta las recetas del paciente: fechas, estado, entregas completadas y restantes.
4. Q.F. crea una receta simulada con código único, inicio, vigencia en meses y máximo de entregas. Una renovación es otra receta con código nuevo y vínculo a su antecedente; comienza con cero entregas.
5. Técnico confirma una entrega de una receta utilizable. Se guarda el evento con responsable y fecha/hora y se muestra el contador actualizado. Una receta vencida, aún no iniciada o agotada no admite entrega.

## Requisitos funcionales

- **RF-03-01 — Padrón:** identificar pacientes por RUT normalizado único y DV válido. Guardar nombres, apellidos, fecha de nacimiento, condiciones de crónico y postrado, y teléfono y dirección opcionales. Calcular la edad desde nacimiento, sin guardar una edad que se vuelva obsoleta. Buscar y paginar resultados privados.
- **RF-03-02 — Plantillas y estructura:** aceptar CSV y `.xlsx` con el mismo contrato de columnas documentado en el plan. Rechazar formatos o encabezados inválidos sin cambios de dominio. Admitir padrón sin receta y varias recetas para un mismo paciente mediante filas separadas.
- **RF-03-03 — Importación parcial:** validar cada fila completa, incluido RUT, fechas y receta cuando exista. Una fila rechazada no modifica ni el paciente ni la receta de esa fila; otras filas válidas continúan. Informar el número de fila y un motivo comprensible.
- **RF-03-04 — Duplicados y actualización:** actualizar pacientes por RUT y recetas por código único. Conservar siempre las entregas existentes. Omitir duplicados idénticos; rechazar las filas contradictorias del archivo para la misma identidad, sin elegir silenciosamente la primera o la última. Un código no puede pasar a otro paciente. Repetir un archivo no duplica pacientes, recetas ni entregas.
- **RF-03-05 — Historial protegido:** si una receta ya tiene entregas, no cambiar inicio, vigencia ni máximo al reimportar. Informar el rechazo y solicitar renovación con código nuevo. No importar un contador de entregas ni sobrescribir el historial local. Una receta sin entregas puede actualizar sus datos válidos por importación.
- **RF-03-06 — Bitácora:** conservar responsable, fecha/hora, formato, referencia técnica del archivo, estado, conteos y reporte de cada carga. Reportes privados para Q.F./superusuario; auditoría genérica sin RUT, nombres, contacto, contenido de filas ni datos clínicos.
- **RF-03-07 — Creación y renovación:** Q.F. crea recetas simuladas para pacientes existentes con código único, inicio, vigencia en meses y máximo positivos. Renovar creando una nueva receta del mismo paciente vinculada a la anterior, sin reiniciar ni alterar su historial. La interfaz no permite editar ni borrar recetas ya registradas; las actualizaciones por archivo se rigen por RF-03-05.
- **RF-03-08 — Consulta y elegibilidad:** mostrar fechas y estado de cada receta, completadas «N de máximo» y restantes. Una receta es utilizable si está dentro de vigencia y tiene cupo; informar todas las causas que la bloquean. Exponer esta regla como servicio para futuros turnos, sin abrir una consulta pública de pacientes.
- **RF-03-09 — Entregas del ciclo:** cada confirmación válida agrega exactamente una entrega con actor y fecha/hora. Rechazar receta agotada, vencida o futura. Impedir superar el máximo con confirmaciones concurrentes y no incrementar al reenviar la misma operación. Una entrega del ciclo no modifica otra receta del paciente.
- **RF-03-10 — Permisos y auditoría:** aplicar la matriz en servidor, POST con CSRF para cambios y auditoría de altas/actualizaciones de pacientes y recetas, renovaciones, entregas y cargas. Un cambio de dominio no queda confirmado si falla su auditoría. Denegar escrituras de dominio que eludan estos servicios desde Admin.
- **RF-03-11 — Demostración:** generar explícitamente un archivo sintético de 670 pacientes con RUT válidos y recetas de ejemplo, sin usar datos reales ni modificar silenciosamente la base. Permitir demostrar ambos formatos y la repetición sin duplicados.

## Datos y reglas

- RUT normalizado con utilidades existentes: sin puntos y con DV válido; no se reutiliza como cuenta de acceso. Nombres, apellidos y fecha de nacimiento obligatorios; no se admiten fechas de nacimiento futuras. Crónico y postrado son indicadores independientes.
- La dirección es texto descriptivo opcional, sin coordenadas ni promesa de normalización cartográfica. El teléfono es contacto opcional, no credencial ni canal de notificación en esta spec.
- El código de receta identifica globalmente una receta dentro del prototipo. No es un identificador real de Rayén ni se genera desde un RUT.
- Inicio, vigencia en meses y máximo pertenecen a cada receta. La regla de calendario propuesta figura en el plan para revisión. Vencimiento y agotamiento son condiciones independientes; el contador no sustituye la vigencia.
- Las entregas nacen exclusivamente de confirmaciones locales. El historial es acumulativo; no hay borrado, decremento ni anulación de entregas en este alcance.
- La nueva receta de una renovación tiene contador cero y conserva el vínculo con su antecedente. Renovar no concede entregas fuera de sus propias fechas ni elimina las restricciones de la anterior.
- No se eliminan pacientes ausentes de un archivo posterior. Un archivo es una actualización explícita de sus filas, no una sustitución completa del padrón.

## Criterios de aceptación

| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-03-01 | RUT con puntos y sin puntos; DV incorrecto; nacimiento futuro | Las formas equivalentes representan un paciente; los valores inválidos se rechazan. |
| RF-03-02/03 | Cada formato válido contiene filas válidas e inválidas | Se procesan las válidas; cada rechazo tiene fila y motivo y no deja cambios parciales de esa fila. |
| RF-03-02 | Faltan columnas o el archivo no es del formato permitido | Se informa el error sin modificar pacientes ni recetas. |
| RF-03-04 | Se repite archivo, hay duplicados idénticos o datos contradictorios | No hay duplicación; se omiten idénticos y se rechazan contradicciones sin depender del orden. |
| RF-03-04/05 | Código existente se asigna a otro RUT o se altera vigencia/cupo tras entregar | Se rechaza la fila; propietario, fechas, máximo y entregas se conservan. |
| RF-03-06 | Se completa una carga con rechazos | Existe bitácora con responsable, fecha, referencia, conteos y reporte privado sin datos personales en auditoría. |
| RF-03-07 | Q.F. crea y renueva; Técnico intenta lo mismo | Q.F. obtiene nueva receta vinculada con cero entregas; Técnico no modifica recetas. |
| RF-03-08 | Receta futura, vigente con cupo, vencida o agotada | Se muestran fechas, contador, restantes y causas correctas; solo la vigente con cupo es elegible. |
| RF-03-09 | Se registra una entrega, se reenvía y se disputa el último cupo | La operación repetida cuenta una vez; ninguna concurrencia supera el máximo. |
| RF-03-09 | Receta vencida/futura/agotada o entrega para otra receta | No se confirma una entrega inválida ni se cambia el contador de otra receta. |
| RF-03-10 | URL/POST directo con rol no permitido, sin perfil, inactivo o sin CSRF | Acceso rechazado sin cambios; superusuario activo conserva su excepción. |
| RF-03-10 | Falla escribir el evento de auditoría durante un cambio | Se revierte el cambio y no se informa éxito. |
| RF-03-11 | Se importa el padrón de 670 pacientes en ambos formatos y se repite | 670 identidades válidas sin digitación manual ni duplicación; sin entregas inventadas. |

## No funcionales

Solo datos sintéticos en archivos, pruebas, demostraciones y evidencias. No conservar copias de los archivos subidos ni valores de filas rechazadas en logs. Las pantallas son privadas; ningún dato de pacientes se incorpora al tótem o pantalla pública.

Reutilizar la identidad visual, tipografía ampliable, componentes y layouts existentes. Etiquetas visibles, navegación por teclado, errores asociados, estados con texto y revisión móvil. Verificar WCAG 2.1 AA con las herramientas disponibles y registrar los límites; no declarar realizada la prueba con cinco usuarios del RNF-04 por tener pruebas automáticas.

Usar ORM y transacciones compatibles con SQLite y futura PostgreSQL. El RNF-05 fija ≤ 2 s en el 95 % de solicitudes; medir consultas interactivas en entorno sintético descrito, separando el tiempo total de importación. No presentar resultados de otro módulo como evidencia de este.

## Compatibilidad

Conservar `auth.User`, habilitación y roles, un solo `settings.py`, auditoría sin datos personales y contratos de salud/service worker. No crear una app adicional: el padrón pertenece a `recetasapp` como base compartida para futuros módulos. No modificar el cierre ni los acuerdos de ejecución de los specs anteriores.

La dependencia 02 existe y su estado canónico actual es Implementado; sus documentos todavía registran pendientes de cierre. Estos pendientes no se dan por resueltos mediante la creación del 03.

## Decisiones tomadas y alternativas

- Equipo eligió ambas historias completas en el ámbito de recetas, CSV y `.xlsx` con plantillas propias, y formulario de recetas para Q.F. con registro de entregas por Técnico.
- Confirmó los datos del padrón y pospuso georreferenciación a logística.
- Confirmó contador por receta; se descarta inventario y saldo por medicamento.
- Confirmó renovación como nueva receta vinculada; se descarta reiniciar el contador de la anterior.
- Confirmó proteger vigencia/cupo tras entregar y rechazar contradicciones; se descarta sobrescribir historial por importación.
- La carga utiliza un contrato propio del prototipo; no se afirma compatibilidad con un exportador real de Rayén.

## Supuestos y decisiones pendientes

Las decisiones funcionales y el diseño de `plan.md` forman parte del documento aprobado. Calendario, formato, rutas, límites y concurrencia están implementados según ese contrato. La matriz no extiende a Q.F. el registro de entregas asignado al Técnico. Pendientes: revisión visual/móvil y axe del módulo cuando el entorno permita navegador, y aceptación funcional del usuario. Mantener el estado Aprobado hasta completar estas verificaciones, sin marcar automáticamente Implementado por pasar pruebas técnicas.

## Revisión y cambios

2026-11-01: respuestas 1A/2A/3A; solicitud de separar documentación siguiendo specs previas; confirmación posterior «Confirmo las 4 reglas». Se guarda el borrador en cuatro documentos y se actualiza el índice.

2026-11-02: el usuario marcó el estado Aprobado, invocó `spec-impl` e indicó «solo hacer commit, no crees una rama nueva». Luego confirmó «comienza» para el paso 1 y posteriormente «si, ahora continua todos los pasos solito». Se ejecutaron de corrido los pasos 2 a 6; código y verificación técnica completados. La evidencia y los límites de revisión visual están en `validation.md`.

## Acuerdo de ejecución

Trabajar en `fdaza` sin crear ni cambiar de rama. El commit está autorizado al terminar la implementación; no se realizan commits intermedios. Conservar el cambio previo del spec 02 y no incluirlo en el commit del 03. La instrucción posterior del usuario autoriza continuar todos los pasos sin pausas y reemplaza la revisión por pasos de la skill. Los límites de validación se registran sin atribuir aceptación funcional al usuario.
