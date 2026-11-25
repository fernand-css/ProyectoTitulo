# SPEC 13 — Panel de mermas

> **Estado:** Aprobado
> **Depende de:** [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 03](../03-padron-y-recetas/spec.md), [SPEC 05](../05-cola-ponderada-y-llamado/spec.md), [SPEC 07](../07-preparacion-y-tiempos-de-espera/spec.md) y [SPEC 08](../08-domicilios-y-entregas/spec.md)
> **Fecha:** 2026-11-17
> **Enmienda:** 2026-11-25, **Aprobada** por la usuaria el mismo día en el chat («pasa las enmiendas a aprobado e implementa») (ver [Enmienda del 2026-11-25](#enmienda-del-2026-11-25--dashboard-de-mermas-y-entregas-borrador)). Rehace el panel como dashboard: períodos de 1, 3, 7 y 14 días, Mes, Semestre, Año y Personalizado; cifras clave comparadas con el período anterior; tabla de entregas por canal (farmacia y domicilio); motivos de no entrega; entregas por día; lo que pasó con lo preparado; ausentes por día y hora, y descarga en CSV además de Excel y PDF. El detalle por paciente sale del panel y «Derivar a domicilio» pasa a «Pendientes de retiro». Modifica RF-13-02, RF-13-03, RF-13-04, RF-13-05 y RF-13-06 y agrega RF-13-11 a RF-13-22. Va junto con la [segunda enmienda del SPEC 05](../05-cola-ponderada-y-llamado/spec.md) (RF-05-14: causa de no entrega en lista cerrada) y la [enmienda del SPEC 07](../07-preparacion-y-tiempos-de-espera/spec.md) (RF-07-13: derivar desde «Pendientes de retiro»). Desde su aprobación, la enmienda reemplaza lo que se le opone de la versión del 2026-11-17; el título de su sección conserva «Borrador» para no romper los enlaces, y manda esta cabecera.
> **Objetivo:** Que la Q.F. y el Director del CESFAM vean, por rango de fechas y tipo de paciente, cuántas recetas preparadas no se retiraron (con gráficos, detalle por paciente y reportes descargables sin datos personales), y que la Q.F. derive a un paciente al reparto a domicilio con lo ya preparado.

Módulo solicitado: `indicadoresapp`, con cambios acotados en `coreapp`/`usuariosapp` (rol Director) y `entregasapp` (recetas preparadas en el reparto). Fuente: HU-20 del [informe](../../docs/Informe.md) y decisiones de la usuaria del 2026-11-17.
Implementación autorizada por la usuaria el 2026-11-17 («pasa la spec 13 a aprobado e implementa»), en `fdaza`, sin rama nueva. Revisión de la usuaria: aprobado el 2026-11-17, con los supuestos tal como están escritos.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

Hoy las recetas preparadas que nadie retira solo se ven, una a una, en «Pendientes de retiro» (spec 07). La Jefatura no puede saber cuánto se pierde en un período ni a quién conviene enviarle los medicamentos a domicilio. Además, el reparto (spec 08) excluye a propósito las recetas que esperan retiro, así que lo preparado no puede salir en un despacho.

El resultado se reconoce porque:

- la Q.F. y el Director abren «Mermas» y ven, para los últimos 30 días o el rango que elijan, el total de recetas no retiradas, cuántas se recuperaron después y cuatro gráficos;
- ven el detalle por paciente y descargan un reporte en Excel o PDF con cifras y gráficos, sin RUT ni nombres;
- la Q.F. pulsa «Derivar a domicilio» en un paciente y se programa una entrega que lleva lo ya preparado; al entregarse, esas recetas salen de la merma y figuran como «entregadas por despacho».

## Actores y permisos

| Acción | Anónimo / tótem | Técnico | Encargado de terreno | Director del CESFAM (nuevo) | Q.F. | Superusuario activo |
|---|---|---|---|---|---|---|
| Ver el panel, sus gráficos y el detalle por paciente | No | No | No | Sí | Sí | Sí |
| Descargar reportes (Excel o PDF) | No | No | No | Sí | Sí | Sí |
| Derivar un paciente al reparto | No | No | No | No | Sí | Sí |
| Crear, editar o desactivar cuentas de Director | No | No | No | No | No | Sí |
| Cualquier otra sección privada | — | (sin cambios) | (sin cambios) | No (403) | (sin cambios) | (sin cambios) |

Se revalidan en el servidor la cuenta activa, el perfil y el rol único (spec 02). Se conserva la excepción del superusuario, que actúa como Q.F.

## Alcance y exclusiones

Incluye:

- la definición única de «receta no retirada» y su clasificación (RF-13-01);
- el panel con filtros, cifras, cuatro gráficos y detalle por paciente;
- los reportes descargables en Excel y PDF, con gráficos y sin datos personales;
- la derivación al reparto con las recetas preparadas y las demás elegibles;
- el ajuste del reparto para llevar recetas preparadas y sacarlas de «Pendientes de retiro» al entregarse;
- el rol Director del CESFAM, de solo consulta y limitado al panel;
- auditoría, pruebas concurrentes y medición HTTP aislada.

No incluye:

- HU-11 (monitoreo de tiempos de espera): queda para otra spec;
- distinguir en el panel las entregas confirmadas por el paciente (HU-22): depende de las notificaciones (reserva 12); el panel deja preparado el lugar, sin dato;
- recetas que nunca se prepararon: no hubo medicamento perdido y no cuentan como merma;
- sumar recetas a una entrega ya abierta: se mantiene la regla del 08 de recetas fijadas al programar;
- incluir recetas preparadas en «Programar entrega» del 08 fuera de la derivación (ver supuestos);
- cifras de costo o de unidades de medicamento: el padrón no las trae;
- datos reales: solo el padrón sintético.

## Historias y flujo

1. **Consulta.** La Q.F. o el Director abre «Mermas». El panel muestra los últimos 30 días y «Todos» los pacientes. Puede elegir un atajo (hoy, 7 días, 30 días, mes anterior) o un rango propio, y el tipo Crónico o General. Ve las cifras, los cuatro gráficos (cada uno con su tabla de datos) y la lista de pacientes con recetas no retiradas.
2. **Reporte.** Con el mismo filtro, pulsa «Descargar Excel» o «Descargar PDF». El archivo trae el período, el filtro, las cifras y los gráficos, sin ningún dato de pacientes.
3. **Derivación.** La Q.F. pulsa «Derivar a domicilio» en un paciente. Elige la fecha (hoy o posterior) y el encargado. Si el paciente no es elegible para el reparto (no es postrado ni tiene 80 años o más), elige además un motivo de excepción en el mismo formulario. Al confirmar se programa la entrega con las recetas preparadas y no retiradas más las otras recetas elegibles ese día. Si ya tiene una entrega abierta, el sistema no deriva y muestra «Ya tiene una entrega abierta» con el enlace a ella.
4. **Despacho.** Mientras la entrega está abierta, esas recetas aparecen en «Pendientes de retiro» como «En despacho» y no se pueden entregar en ventanilla. Si el encargado registra «Entregada», salen de «Pendientes de retiro» y el panel las cuenta como «entregadas por despacho». Si no se entrega, siguen «En despacho» hasta que la entrega se reprograme o se anule; si se anula, vuelven a «Sin retirar».

## Requisitos funcionales

- **RF-13-01 — Receta no retirada:** una receta cuenta en el panel SI su preparación quedó lista (`PreparacionReceta.lista_en`) y su turno cerró como ausente, atendido, cerrado sin entrega o sin atención al cierre, igual que «Pendientes de retiro» del spec 07. Cada una está en uno solo de cuatro estados:
  - **Sin retirar:** sin entrega registrada y sin despacho abierto;
  - **En despacho:** sin entrega registrada y en una entrega a domicilio abierta;
  - **Retirada tarde en farmacia:** entregada después desde «Pendientes de retiro»;
  - **Entregada por despacho:** entregada por el reparto (RF-13-07).

  La **merma** del período es la suma de «Sin retirar» y «En despacho»; las **recuperadas** son las otras dos, en cifra aparte. El estado se calcula al momento de la consulta. Las recetas entregadas dentro de la misma atención no cuentan.
- **RF-13-02 — Filtros:** el rango se aplica sobre la fecha local de preparación. Por omisión son los últimos 30 días, hoy incluido, y el tipo «Todos». El tipo Crónico o General sale de `Paciente.es_cronico`. SI el inicio es posterior al fin, el fin es futuro o el rango supera 366 días, ENTONCES se rechaza con un mensaje claro y se muestra el filtro por omisión. Los filtros viajan en la URL (GET) y no llevan datos personales. *(Enmienda 2026-11-25: el rango libre con atajos pasa a ocho períodos y el de omisión pasa a ser el mes en curso; ver RF-13-11 y RF-13-12.)*
- **RF-13-03 — Cifras y gráficos:** el panel muestra la merma total, «Sin retirar», «En despacho», «Retiradas tarde» y «Entregadas por despacho», y cuatro gráficos:
  1. evolución de la merma por día (rango de 31 días o menos) o por semana de lunes a domingo (rango mayor);
  2. crónico frente a general;
  3. por cómo cerró el turno (ausente, atendido, cerrado sin entrega, sin atención al cierre);
  4. recuperadas frente a perdidas (los cuatro estados de RF-13-01).

  Cada gráfico tiene su tabla de datos y textos visibles; nada depende solo del color. SI el período no tiene recetas, ENTONCES se muestra «No hay recetas no retiradas en este período» en lugar de los gráficos. *(Enmienda 2026-11-25: los cuatro gráficos se reemplazan por el dashboard de RF-13-13 a RF-13-20; la evolución pasa a RF-13-15, «Cómo cerró el turno» a los motivos de RF-13-16, el blíster a RF-13-18 y se conserva «Crónico y general».)*
- **RF-13-04 — Detalle por paciente:** lista una fila por paciente con merma en el período: RUT, nombre, Crónico o General, cantidad «Sin retirar» y «En despacho», fecha de preparación más antigua, y si es elegible para el reparto (postrado, 80 años o más, excepción vigente o «No elegible»). Se ordena por la fecha más antigua y se pagina de a 50. La Q.F. ve el botón «Derivar a domicilio» en las filas con recetas «Sin retirar»; el Director no lo ve. *(Enmienda 2026-11-25: el detalle por paciente sale del panel, que queda sin datos personales; la derivación se inicia en «Pendientes de retiro»; ver RF-13-22 y RF-07-13.)*
- **RF-13-05 — Reportes descargables:** con el filtro vigente se descarga un Excel (`.xlsx`, hoja «Resumen» con cifras y los cuatro gráficos nativos, y hoja «Datos» con la serie por día o semana) o un PDF vertical tamaño carta con cifras, gráficos y sus tablas. Los reportes **nunca** incluyen RUT, nombres, fechas de nacimiento, direcciones, teléfonos ni identificadores internos de pacientes o recetas; solo cifras agregadas, el período, el filtro, la fecha y hora de generación y el rol de quien lo generó. El nombre del archivo es `mermas_<inicio>_<fin>.xlsx` o `.pdf`. La respuesta es `no-store` y queda auditada (actor, formato, rango y tipo). *(Enmienda 2026-11-25: se suma el CSV y cambian el contenido del Excel y del PDF; ver RF-13-21.)*
- **RF-13-06 — Derivación al reparto:** CUANDO la Q.F. confirma la derivación de un paciente con fecha y encargado válidos, EL SISTEMA, en una sola transacción e idempotente por operación:
  - si el paciente no es elegible a esa fecha, crea su excepción de reparto con el motivo elegido (exigido en ese caso);
  - programa la entrega con sus recetas «Sin retirar» y las demás recetas elegibles en esa fecha según el 08, y su primer intento;
  - deja ligada cada receta preparada a su preparación (RF-13-07) y audita la derivación.

  SI ya tiene una entrega abierta, ENTONCES no deriva y responde «Ya tiene una entrega abierta» con el enlace. SI ya no tiene recetas «Sin retirar» (se retiraron o derivaron mientras tanto), ENTONCES rechaza sin cambios. SI falla cualquier paso, no queda ni la excepción ni la entrega. *(Enmienda 2026-11-25: se inicia desde «Pendientes de retiro» y «Volver» regresa ahí; el servicio no cambia; ver RF-13-22.)*
- **RF-13-07 — Recetas preparadas en el reparto:** una receta derivada con su preparación:
  - mientras la entrega está abierta, figura «En despacho» en «Pendientes de retiro» y la ventanilla rechaza entregarla (bloqueo del 08, que se conserva);
  - al registrarse «Entregada», su vigencia y cupo se evalúan a la **fecha de preparación**, como el retiro tardío del 07; si se descuenta, la entrega queda ligada al vínculo del turno y la receta sale de «Pendientes de retiro»; si no puede descontarse, queda «no descontada» con su causa y vuelve a «Sin retirar»;
  - si la entrega se anula, vuelve a «Sin retirar».

  Las recetas no preparadas de la misma entrega siguen la regla del 08 (vigencia del día de la visita).
- **RF-13-08 — Rol Director del CESFAM:** existe un cuarto rol interno, de solo consulta. Inicia sesión con las mismas reglas del 02 (cuenta activa, perfil y rol único). Su menú tiene solo «Mermas» y «Mi perfil», y su inicio (`/`) muestra el panel con estado 200. Cualquier otra sección privada le responde 403. Solo el superusuario crea, edita, desactiva o restablece estas cuentas; la Q.F. no las ve en «Usuarios».
- **RF-13-09 — Acceso y menú:** «Mermas» aparece en el menú de la Q.F., el superusuario y el Director. Técnico, Encargado y anónimos reciben 403 o la redirección al inicio de sesión. Las páginas del panel son privadas y `no-store`.
- **RF-13-10 — Concurrencia:** la derivación toma la reserva de la jornada del 08 (`bloquear_cola`) y usa las restricciones existentes (una entrega abierta por paciente, una excepción vigente por paciente) más un UPDATE condicional o restricción que impida ligar la misma preparación a dos entregas abiertas. Una preparación nunca queda a la vez entregada en ventanilla y en un despacho, ni en dos despachos.

## Datos y reglas

- No se crea un modelo de merma: todo se calcula desde `PreparacionReceta`, `TurnoReceta`, `Turno`, `EntregaReceta`, `Paciente` y `RecetaEntrega`.
- `RecetaEntrega` gana un vínculo opcional a la preparación que lleva (`preparacion`); es lo único nuevo en el esquema de `entregasapp`.
- El rol se guarda como un grupo de Django más, como los otros tres, y lo crea `crear_roles`; no hay modelo nuevo.
- Los reportes se generan al vuelo y no se guardan en el servidor.
- La auditoría de descargas y derivaciones no guarda RUT, nombres ni texto libre; la nota de la excepción sigue las reglas del 08.

## Criterios de aceptación

| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-13-01 | Tres recetas preparadas en turnos ausentes: una sin retirar, una retirada luego en farmacia y una en un despacho abierto | Merma 2 (1 sin retirar, 1 en despacho); recuperadas 1 (retirada tarde). |
| RF-13-01 | Una receta de turno ausente que nunca se preparó | No aparece en el panel. |
| RF-13-02 | Se abre el panel sin filtros | Rango de los últimos 30 días, hoy incluido, tipo «Todos». |
| RF-13-02 | Rango con inicio posterior al fin, fin futuro o 400 días | Mensaje de error y filtro por omisión. |
| RF-13-02 | Filtro «Crónico» | Solo cuentan pacientes con `es_cronico`. |
| RF-13-03 | Rango de 10 días / de 90 días | Evolución por día / por semana; cada gráfico con su tabla. |
| RF-13-03 | Período sin recetas no retiradas | Texto «No hay recetas no retiradas en este período», sin gráficos vacíos. |
| RF-13-04 | El Director abre el detalle | Ve RUT, nombre y cifras, sin el botón «Derivar a domicilio». |
| RF-13-05 | La Q.F. o el Director descarga Excel y PDF | Archivos válidos con cifras y cuatro gráficos; al buscar en su contenido los RUT y nombres del padrón sintético, no aparece ninguno. Queda auditada la descarga. |
| RF-13-06 | La Q.F. deriva a un paciente de 85 años con 2 recetas sin retirar y 1 receta elegible más | Entrega programada con las 3 recetas; las 2 preparadas pasan a «En despacho». |
| RF-13-06 | Deriva a un paciente de 60 años sin elegir motivo | Rechazo; con motivo, se crean la excepción y la entrega juntas. |
| RF-13-06 | El paciente ya tiene una entrega abierta | «Ya tiene una entrega abierta» con enlace; sin cambios. |
| RF-13-07 | El encargado registra «Entregada» y una receta preparada venció entre la preparación y la visita | Se descuenta (vigente a la fecha de preparación), sale de «Pendientes de retiro» y cuenta como «Entregada por despacho». |
| RF-13-07 | Se anula la entrega derivada | Las recetas preparadas vuelven a «Sin retirar». |
| RF-13-07 | Un Técnico intenta entregar en ventanilla una receta «En despacho» | Rechazo sin cambios. |
| RF-13-08 | Una cuenta Director abre `/`, `/recetas/` y `/turnos/panel/` | 200 con el panel; 403; 403. |
| RF-13-08 | La Q.F. abre «Usuarios» | No ve cuentas de Director ni puede crearlas. |
| RF-13-09 | Un Técnico abre el panel o un reporte | 403. |
| RF-13-10 | Dos derivaciones simultáneas del mismo paciente | Una sola entrega y una sola excepción. |
| RF-13-10 | Derivación y retiro en ventanilla simultáneos de la misma preparación | Un solo resultado: o se retiró en farmacia, o quedó en el despacho. |

## No funcionales

- **Rendimiento (RNF-05):** el panel y cada reporte responden en 2 s o menos en el 95 % de las solicitudes, con el padrón sintético de 670 pacientes y al menos 90 días de preparaciones sintéticas.
- **Accesibilidad (RNF-04):** WCAG 2.1 AA; gráficos con tabla de datos y textos, contraste de 4,5:1, foco visible y uso por teclado; el PDF lleva título y textos legibles.
- **Privacidad (RNF-01):** solo datos sintéticos; el RUT y el nombre solo en pantalla, nunca en reportes, URL ni auditoría.
- **Concurrencia (RNF-02):** la derivación cambia la programación del 08, así que se exigen al menos tres escenarios con `TransactionTestCase`, hilos y conexiones separadas: dos derivaciones del mismo paciente; derivación frente a retiro en ventanilla; derivación frente a `programar_lote`.

## Compatibilidad

- Se conservan `pendientes_retiro` y el retiro tardío del 07; solo se agrega la marca «En despacho».
- «Programar entrega» del 08 sigue excluyendo recetas que esperan retiro; solo la derivación las incluye.
- `registrar_entregada` y `anular_entrega` del 08 conservan su contrato para las recetas no preparadas.
- Las pruebas de los specs 02, 03, 05, 07, 08 y 09 siguen en verde; las del 02 que cuentan tres roles se actualizan a cuatro.

## Decisiones tomadas y alternativas

Decisiones de la usuaria del 2026-11-17:

- **Merma = toda receta preparada y no retirada tras cerrar el turno**, sin importar cómo cerró. Se descartaron contar solo los turnos ausentes (literal del informe) y contar recetas nunca preparadas. Se aparta de la redacción de HU-20, que nombra solo los ausentes: lo que se pierde es lo preparado, y coincide con «Pendientes de retiro».
- **Derivar envía lo ya preparado** más las demás recetas elegibles, en un solo viaje. Se descartaron solo abrir «Programar entrega» y solo inscribir la excepción.
- **Si hay una entrega abierta, se avisa y se enlaza**; no se suman recetas a una entrega ya programada.
- **La vigencia de lo preparado se evalúa a la fecha de preparación**, como el retiro tardío del 07.
- **Ven el panel la Q.F. y un rol nuevo de Director del CESFAM**, que solo mira, solo ve el panel y solo lo administra el superusuario. Se descartaron usar la cuenta de la Q.F. para el Director y dar el panel al Técnico.
- **Reportes en Excel y PDF, con gráficos y nunca con datos personales**, para ambos roles.
- **Filtro por la marca crónico del padrón**; rango sobre la fecha de preparación; por omisión, los últimos 30 días.
- **Las recuperadas se muestran en cifra aparte** de la merma.
- **HU-11 queda fuera**, en otra spec.
- **Número 13:** primer número libre no reservado (11 y 12 están reservados).

## Supuestos y decisiones pendientes

Supuestos reversibles para revisar al aprobar:

1. La etiqueta visible del rol es «Dirección del CESFAM» (nombre interno «Director del CESFAM»), neutra en género como el resto de las etiquetas.
2. La cuenta demo es `demo_director`, creada por `crear_usuarios_demo` como las otras.
3. Solo la derivación del panel incluye recetas preparadas; «Programar entrega» del 08 no cambia.
4. «Mes anterior» es el mes calendario anterior completo; la semana del gráfico va de lunes a domingo.
5. Los gráficos del panel reutilizan la geometría SVG de `recetasapp/graficos.py`; los del Excel son gráficos nativos de openpyxl y los del PDF, de ReportLab. Sin dependencias nuevas.

Sin bloqueos críticos.

## Revisión y cambios

2026-11-17: borrador creado con las decisiones de la usuaria en cuatro bloques de preguntas. Sin código, migraciones ni aprobación.

2026-11-17 (aprobación): la usuaria indicó «pasa la spec 13 a aprobado e implementa». El documento pasa a **Aprobado** con los cinco supuestos tal como están escritos, y se autoriza la implementación en `fdaza`, sin rama nueva y sin commit.

2026-11-17 (implementación, `fdaza`, sin commit): T-13-01 a T-13-08 implementadas sin cambiar requisitos. Decisiones de implementación que se apartan del plan, con su motivo:

- **Sin restricción parcial nueva sobre la preparación.** Una preparación pertenece a la receta de un solo paciente y cada paciente tiene a lo más una entrega abierta (`entrega_abierta_unica` del 08), así que no puede quedar en dos despachos abiertos. Una restricción sobre `RecetaEntrega.resultado="pendiente"` habría impedido volver a derivar tras una anulación, porque las recetas de una entrega anulada conservan «pendiente». La migración `0003` solo agrega el campo.
- **«Derivar a domicilio» es una página, sin `<dialog>`.** Funciona sin JavaScript y vuelve al panel con el mismo filtro. El paciente va en la URL (`/indicadores/mermas/derivar/<id>/`) y el servidor revalida rol, elegibilidad, entrega abierta y preparaciones en cada envío; no hace falta firmarlo porque la Q.F. ya puede programar a cualquier paciente.
- **PDF sin compresión**, como el comprobante del tótem: el texto queda en claro y la prueba verifica que no contiene RUT ni nombres sin agregar dependencias.
- **Una preparación por receta en cada despacho:** si una receta tiene dos preparaciones sin retirar, viaja la más antigua (la restricción `receta_entrega_unica` admite una fila por receta); la otra sigue «Sin retirar».
- **Recetas en un turno activo** no se derivan: la ventanilla las está atendiendo.
- **La previsualización local** (`tools/previsualizar_interfaz.py`) suma la cuenta `revision_director` y 45 días de recetas sintéticas preparadas y sin retirar.
- **Dos tarjetas además de los cuatro gráficos de RF-13-03** (anotado en la revisión del 2026-11-18): «Cuánto llevan en el estante» (recetas sin retirar por días desde la preparación) y «Entregas confirmadas» por día o semana, con promedio de 7 días (`indicadoresapp/entregas.py`). Solo usan cifras agregadas y no reemplazan los gráficos exigidos; los cuatro gráficos se dibujan como blíster (recuperadas frente a perdidas), calendario o tabla semanal (evolución) y barras (crónico/general y cierre del turno), en `indicadoresapp/graficos.py`. Pendiente que la usuaria las confirme en la aceptación.

2026-11-17 (datos de demostración, pedido de la usuaria): `python manage.py generar_mermas_demo` (en `indicadoresapp/management/commands/`) crea, solo con `--aplicar --cuenta <Q.F.>`, días anteriores a hoy con turnos cerrados y recetas preparadas sin retirar sobre las recetas vigentes del padrón ya importado, y retira una parte después con `retirar_preparado` (por omisión 60 días, 20 por día y 15 % recuperadas). No toca la jornada de hoy ni programa entregas; numera después de los turnos existentes de cada día. El padrón sintético variado de 600 pacientes está en `datos_demo/padron_mermas_600.csv` (sin datos reales).

## Enmienda del 2026-11-25 — Dashboard de mermas y entregas (Borrador)

Pedida por la usuaria el 2026-11-25, después de revisar en el chat un boceto del panel en estilo dashboard (con cifras inventadas). Se redacta en `crojas-base`. Va junto con la [segunda enmienda del SPEC 05](../05-cola-ponderada-y-llamado/spec.md#segunda-enmienda-del-2026-11-25--causa-de-no-entrega-borrador) y la [enmienda del SPEC 07](../07-preparacion-y-tiempos-de-espera/spec.md#enmienda-del-2026-11-25--derivar-desde-pendientes-de-retiro-borrador). Aprobada por la usuaria el 2026-11-25; desde entonces reemplaza lo que se le opone de la versión del 2026-11-17.

**Objetivo de la enmienda:** Que la Q.F. y la Dirección vean en un dashboard, por períodos de 1, 3, 7 o 14 días, mes, semestre, año o un rango propio, cuántas recetas se entregaron y cuántas no en farmacia y a domicilio, por qué no se entregaron, cuándo y cuánto de lo preparado se perdió, y que descarguen esas cifras en Excel, CSV o PDF.

### Problema

El panel del 2026-11-17 describe solo la merma (lo preparado y no retirado). No dice cuántas recetas se entregaron y cuántas no en cada canal, ni por qué: en farmacia el motivo de no entrega se escribe como texto libre y no se puede agrupar. Los períodos son fechas libres con cuatro atajos, y el detalle por paciente mezcla una lista de trabajo de la Q.F. con un panel de consulta que también abre la Dirección.

### Qué cambia respecto del 2026-11-17

| Antes | Después | Motivo |
|---|---|---|
| Rango «Desde/Hasta» con atajos Hoy, 7 días, 30 días y Mes anterior; por omisión, los últimos 30 días | Ocho períodos; Mes, Semestre y Año son de calendario y se recorren con flechas; por omisión, el mes en curso (RF-13-11) | Pedido de la usuaria. El mes calendario calza con el calendario de merma y se compara con el mes anterior. |
| Cifras de los cuatro estados | Cuatro cifras clave comparadas con el período anterior (RF-13-12, RF-13-13) | Estilo dashboard. |
| Sin cifras por canal | Tabla «Entregas por canal»: farmacia, domicilio y total (RF-13-14) | Pedido de la usuaria. |
| Evolución por día o semana | Merma por día en calendario hasta 31 días; por semana o por mes en períodos más largos (RF-13-15) | Se conserva el calendario actual. |
| «Cómo cerró el turno» | Motivos de no entrega en farmacia y a domicilio (RF-13-16) | Los cierres del turno pasan a ser motivos («Paciente ausente», «Sin atención al cierre») junto con la causa del RF-05-14. |
| «Entregas confirmadas» por día o semana | Entregas por día en farmacia y a domicilio, en dos gráficos (RF-13-17) | Domicilio es cerca del 5 % del total y no se vería en el mismo gráfico. |
| Blíster de recuperadas y perdidas | Barra «Qué pasó con las recetas preparadas» (RF-13-18) | Decisión de la usuaria. |
| — | Ausentes por día y hora (RF-13-19) | Decisión de la usuaria. |
| Detalle por paciente con «Derivar a domicilio» | Sale del panel; se deriva desde «Pendientes de retiro» (RF-13-22, RF-07-13) | Decisión de la usuaria. El panel queda sin RUT ni nombres. |
| Excel y PDF | Excel, CSV y PDF (RF-13-21) | Pedido de la usuaria; el PDF se conserva. |

Se conservan «Cuánto llevan en el estante» y «Crónico y general».

### Alcance de la enmienda

Incluye:

- los ocho períodos, su navegación y la comparación con el período anterior;
- el dashboard: cifras clave, tabla por canal, merma por día, motivos, entregas por día, lo que pasó con lo preparado, ausentes por día y hora, y las dos tarjetas que se conservan;
- las descargas en Excel, CSV y PDF con el contenido nuevo;
- el traslado del punto de entrada de la derivación a «Pendientes de retiro»;
- la causa de no entrega en lista cerrada al cerrar la atención (enmienda del 05), que alimenta los motivos de farmacia;
- la ampliación de `generar_mermas_demo` y de `tools/verificar_spec_13_http.py` a un año de datos sintéticos.

No incluye:

- el diagrama de Pareto en los motivos, el reparto por sector y localidad, ni los tiempos de recuperación (días hasta el retiro, visitas por entrega, días hasta entregar): propuestos en el chat y dejados fuera por la usuaria;
- cambios en la definición de merma (RF-13-01), en el servicio de derivación (RF-13-06 y RF-13-07, salvo su punto de entrada), en el rol Director (RF-13-08) ni en los permisos (RF-13-09);
- cifras de costo o por medicamento: `Receta` no guarda medicamento ni precio;
- HU-11 y las entregas confirmadas por el paciente (HU-22), igual que antes;
- librerías de gráficos externas: los gráficos siguen siendo SVG o HTML propios, con su tabla de datos;
- datos reales: solo el padrón sintético.

### Requisitos de la enmienda

- **RF-13-11 — Períodos:** el panel ofrece ocho períodos como botones de una sola fila, con el elegido marcado también con texto o `aria-current` (no solo con color):
  - **1 día:** hoy. **3, 7 y 14 días:** los últimos N días, hoy incluido. Para otro día o rango se usa «Personalizado».
  - **Mes:** un mes calendario. **Semestre:** de enero a junio o de julio a diciembre. **Año:** de enero a diciembre. Al elegirlos se muestra el que contiene hoy, cortado en hoy. «‹» pasa al anterior y «›» al siguiente; «›» no aparece si el siguiente empezaría después de hoy.
  - **Personalizado:** «Desde» y «Hasta» con las reglas de RF-13-02: inicio no posterior al fin, fin no posterior a hoy y hasta 366 días.
  - Por omisión: «Mes» en curso y tipo «Todos». El filtro de tipo (Todos, Crónico, General) se conserva y se aplica a todo el panel; los turnos sin paciente del padrón solo cuentan en «Todos».
  - El título escribe el período completo, por ejemplo «Noviembre de 2026, del 1 al 25», «Segundo semestre de 2026, hasta el 25 de noviembre» o «Últimos 7 días: del 19 al 25 de noviembre».
  - Las series van por día hasta 31 días, por semana de lunes a domingo entre 32 y 186 días, y por mes con más de 186. Así, Mes va por día, Semestre por semana y Año por mes.
  - Los parámetros viajan por GET y no llevan datos personales. SI un parámetro no es válido, ENTONCES se muestra un mensaje claro y el «Mes» en curso. Un enlace antiguo con `desde` y `hasta` abre como «Personalizado».
- **RF-13-12 — Comparación con el período anterior:** cada cifra clave muestra la diferencia con el período anterior equivalente:
  - para 1, 3, 7 y 14 días y para «Personalizado», los N días inmediatamente anteriores;
  - para Mes, Semestre y Año, los mismos días contados desde el inicio del período anterior (del 1 al 25 de noviembre se compara con el 1 al 25 de octubre; si el mes anterior es más corto, hasta su último día).

  La diferencia se escribe con palabras y el período comparado («3,1 % más que del 1 al 25 de octubre»; en la merma, en puntos porcentuales). La flecha es decorativa y el color, si se usa, solo acompaña al texto. SI el período anterior no tiene datos, ENTONCES dice «Sin datos del período anterior».
- **RF-13-13 — Cifras clave:** cuatro cifras al comienzo del panel:
  1. **Recetas entregadas:** entregadas en farmacia más entregadas a domicilio, según RF-13-14.
  2. **Merma:** «Sin retirar» más «En despacho» (RF-13-01), con su porcentaje sobre las recetas preparadas del período cuyo turno cerró, se hayan entregado o no en la atención.
  3. **Efectividad a domicilio:** recetas entregadas a domicilio sobre el total a domicilio de RF-13-14, en porcentaje. Sin visitas en el período, dice «Sin visitas en el período».
  4. **En el estante más de 14 días:** recetas «Sin retirar» del período con más de 14 días desde su preparación. Para la Q.F. y el superusuario, la cifra enlaza a «Pendientes de retiro»; la Dirección la ve sin enlace, porque esa sección le responde 403.
- **RF-13-14 — Tabla «Entregas por canal»:** una tabla con filas Farmacia, Domicilio y Total, y columnas Entregadas, No entregadas, Total y «% entregado» (un decimal con coma). La unidad es la receta en los dos canales.
  - **Farmacia:** las recetas de los turnos del período (por fecha del turno) que ya cerraron como atendido, cerrado sin entrega, ausente o sin atención al cierre. Son **entregadas** las que se entregaron en esa atención y **no entregadas** las demás. Se suman a las entregadas las confirmadas desde la ficha de la receta sin turno, por su fecha. Bajo «No entregadas», la subfila «de ellas, retiradas después» cuenta las que se retiraron más tarde desde «Pendientes de retiro». Los turnos aún activos no cuentan; si los hay, una nota dice cuántas recetas esperan todavía su atención.
  - **Domicilio:** las recetas llevadas en visitas registradas en el período (por fecha local del registro) como «Entregada» o «No entregada». Son **entregadas** las descontadas y **no entregadas** las de visitas «No entregada» más las «no descontadas» de visitas entregadas. Una receta que falla en dos visitas cuenta dos veces, porque fueron dos viajes. Las visitas reasignadas o anuladas sin resultado no cuentan.
- **RF-13-15 — Merma por día:** la merma (RF-13-01) por fecha de preparación:
  - hasta 31 días, el calendario actual de lunes a domingo, con la cifra escrita en cada día, los días fuera del período vacíos y los días posteriores a hoy marcados «Aún no»; se conserva la frase del día de la semana que destaca;
  - con más días, columnas por semana o por mes según RF-13-11.

  Cada forma tiene su tabla de datos.
- **RF-13-16 — Motivos de no entrega:** dos listas de barras horizontales, ordenadas de mayor a menor, con la cantidad y el porcentaje escritos y su tabla de datos:
  - **Farmacia,** en recetas no entregadas de RF-13-14: «Paciente ausente» (turno ausente), «Sin atención al cierre» y las causas del RF-05-14 («Sin stock», «Paciente no la pide», «Receta no vigente o sin cupo», «Cambio de indicación» y «Otro»). Las recetas cerradas antes del RF-05-14, sin causa guardada, cuentan como «Otro».
  - **Domicilio,** en visitas «No entregada» del período: los seis motivos de `IntentoEntrega.Motivo`. Bajo la lista, una frase dice cuántas recetas no se descontaron en visitas entregadas.

  El texto libre de «Otro» nunca aparece en el panel ni en las descargas. SI no hay no entregas, ENTONCES cada lista dice «Sin recetas no entregadas en este período» o «Sin visitas fallidas en este período».
- **RF-13-17 — Entregas por día:** dos gráficos de columnas, cada uno con su escala y su tabla, con la granularidad de RF-13-11:
  - **Farmacia:** recetas entregadas en farmacia cada día, por la fecha de la entrega, en dos partes apiladas: «En la atención o desde la ficha» y «Retiradas después». Por día, se conserva la línea del promedio de 7 días.
  - **Domicilio:** recetas de visitas registradas cada día, en dos partes apiladas: «Entregadas» y «No entregadas».

  Por eso, la suma de la farmacia por día puede superar las entregadas de la tabla: el gráfico cuenta lo que salió cada día, también lo retirado después.
- **RF-13-18 — Qué pasó con las recetas preparadas:** una barra al 100 % con las preparaciones listas del período (por fecha de preparación) cuyo turno cerró, en cinco partes: «Entregadas en la atención», «Retiradas después», «Entregadas por despacho», «En despacho» y «Sin retirar». La leyenda escribe la cantidad y el porcentaje de cada parte (suman 100) y las partes se distinguen además por su orden y una textura o separación, no solo por el color. Reemplaza al blíster.
- **RF-13-19 — Ausentes por día y hora:** una grilla con una fila por día de la semana (lunes a viernes; sábado y domingo solo si hubo turnos) y una columna por hora, desde la primera hasta la última hora con turnos emitidos en el período (de 8 a 20 si no hay otros). Cada celda escribe cuántos turnos del período, emitidos en ese día y hora (hora local de emisión), están hoy «ausentes»; los reincorporados que se atendieron no cuentan. El tono sube con la cantidad y la cifra va escrita. La tabla de datos da, por celda, los turnos emitidos, los ausentes y su porcentaje. SI no hay ausentes, ENTONCES dice «Sin turnos ausentes en este período».
- **RF-13-20 — Composición del panel:** en este orden: período, tipo y descargas; cifras clave; entregas por canal; merma por día y motivos; entregas por día; qué pasó con lo preparado; cuánto llevan en el estante; crónico y general; ausentes por día y hora. En computador, las tarjetas forman una grilla de hasta dos columnas; en celular, una sola, sin desplazamiento horizontal. El panel no muestra RUT, nombres ni identificadores de pacientes o recetas. Cada tarjeta sin datos muestra su propio texto; si el período no tiene ningún dato, un solo texto lo dice.
- **RF-13-21 — Descargas:** con el período y el tipo vigentes se descarga:
  - **Excel (`.xlsx`):** hoja «Resumen» con el período, el filtro, las cifras clave y su comparación, la tabla por canal, los motivos y lo que pasó con lo preparado, con gráficos nativos; hoja «Por día» con las mismas columnas del CSV; hoja «Ausentes por hora» con la grilla de RF-13-19.
  - **CSV (`.csv`):** una fila por día del período, aunque el panel agrupe por semana o por mes, con columnas fijas: la fecha (AAAA-MM-DD), las cifras diarias de farmacia y de domicilio de RF-13-17, la merma por fecha de preparación y una columna por motivo de farmacia y de domicilio. Separador «;», UTF-8 con BOM y solo números enteros, para que Excel en español lo abra en columnas y con tildes. Las columnas exactas están en [plan.md](plan.md#enmienda-del-2026-11-25).
  - **PDF:** vertical, tamaño carta, con las cifras clave, la tabla por canal, los motivos, la merma por día y lo que pasó con lo preparado, cada gráfico con su tabla.

  Los tres siguen RF-13-05: sin RUT, nombres, fechas de nacimiento, direcciones, teléfonos ni identificadores; tampoco el texto libre de los motivos. El nombre es `mermas_<inicio>_<fin>.<xlsx|csv|pdf>`, la respuesta es `no-store` y cada descarga queda auditada con actor, formato, rango y tipo.
- **RF-13-22 — Derivación desde «Pendientes de retiro»:** el panel deja de listar pacientes (RF-13-04). «Derivar a domicilio» se ofrece en «Pendientes de retiro» a la Q.F. y al superusuario (RF-07-13). La página y el servicio de RF-13-06 no cambian, salvo que «Volver» regresa a «Pendientes de retiro». La Dirección sigue sin derivar.

Los permisos de RF-13-08 y RF-13-09 no cambian: ven el panel y descargan la Q.F., el superusuario y la Dirección.

### Criterios de aceptación de la enmienda

| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-13-11 | Se abre el panel sin parámetros el 25-11-2026 | «Mes»: del 1 al 25 de noviembre de 2026, tipo «Todos» y merma por día en calendario. |
| RF-13-11 | «Semestre» el 25-11-2026 | Del 1-7 al 25-11-2026, por semana, sin «›»; «‹» lleva del 1-1 al 30-6-2026. |
| RF-13-11 | «Año» / «7 días» el 25-11-2026 | Del 1-1 al 25-11-2026 por mes / del 19 al 25 de noviembre por día. |
| RF-13-11 | «Personalizado» con fin futuro, inicio posterior al fin o 400 días | Mensaje claro y «Mes» en curso. |
| RF-13-11 | Enlace antiguo `?desde=2026-10-01&hasta=2026-10-31` | Abre «Personalizado» con ese rango. |
| RF-13-12 | «Mes» del 1 al 25 de noviembre | Compara con el 1 al 25 de octubre; si octubre no tiene datos: «Sin datos del período anterior». |
| RF-13-13 | Tres recetas «Sin retirar» preparadas hace 20 días y una hace 3 | «En el estante más de 14 días»: 3; la Q.F. ve el enlace a «Pendientes de retiro» y la Dirección no. |
| RF-13-14 | Turno atendido con 3 recetas (2 entregadas) y turno ausente con 2 recetas, una retirada después | Farmacia: 2 entregadas, 3 no entregadas, total 5, 40,0 %; «de ellas, retiradas después»: 1. |
| RF-13-14 | Visita entregada con 2 recetas (1 no descontada) y visita no entregada con 3 | Domicilio: 1 entregada, 4 no entregadas, total 5, 20,0 %. |
| RF-13-14 | Un turno de hoy sigue en atención | No cuenta; la nota dice cuántas recetas esperan su atención. |
| RF-13-16 | Una receta cerrada con «Sin stock» y otra cerrada antes del RF-05-14 con motivo de texto libre | «Sin stock»: 1 y «Otro»: 1; el texto libre no aparece en el panel ni en las descargas. |
| RF-13-16 | Dos visitas «No entregada» por «Camino intransitable» | Domicilio: «Camino intransitable» 2 (100 %). |
| RF-13-17 | Una receta de un turno del 3 de noviembre retirada el 10 | La columna del 10 suma 1 en «Retiradas después». |
| RF-13-18 | 5 preparadas entregadas en la atención, 1 retirada después, 1 en despacho y 1 sin retirar | Barra con cuatro partes no vacías; porcentajes escritos que suman 100. |
| RF-13-19 | Cuatro turnos emitidos un lunes a las 10:xx, uno ausente y otro reincorporado y atendido | Celda lunes 10 h: 1; en la tabla, 4 emitidos, 1 ausente, 25 %. |
| RF-13-20 | La Dirección abre el panel | Ningún RUT ni nombre en el HTML y sin «Derivar a domicilio». |
| RF-13-21 | La Q.F. descarga el CSV de noviembre | Excel lo abre en columnas, con tildes, una fila por día del 1 al 25; no contiene RUT ni nombres sintéticos; la descarga queda auditada. |
| RF-13-21 | Descarga Excel y PDF del «Año» | Archivos válidos con las secciones de RF-13-21, sin datos personales y auditados. |
| RF-13-22 | La Q.F. pulsa «Derivar a domicilio» en «Pendientes de retiro» | Se abre la derivación de RF-13-06; «Volver» regresa a «Pendientes de retiro». |

### No funcionales de la enmienda

- **Rendimiento (RNF-05):** el panel y cada descarga responden en 2 s o menos en el 95 % de las solicitudes con el padrón de 670 pacientes y 366 días de datos sintéticos (preparaciones, turnos con ausentes y visitas a domicilio), incluido «Año».
- **Accesibilidad (RNF-04):** WCAG 2.1 AA. Cada gráfico tiene su tabla de datos y textos visibles; el calendario y la grilla de ausentes escriben su cifra en cada celda; nada depende solo del color. Los colores nuevos van en las dos paletas (`base.css` y `tema_oscuro.css`) y su contraste se prueba en `test_estaticos.py`. Los botones de período se usan con teclado y tienen foco visible.
- **Privacidad (RNF-01):** el panel y las descargas solo muestran cifras agregadas; ni RUT, ni nombres, ni el texto libre de los motivos.
- **Concurrencia (RNF-02):** el panel solo lee. La causa del RF-05-14 viaja en la misma transacción del cierre del 05, sin cambiar su control de concurrencia; las pruebas concurrentes del 05 y del 13 siguen en verde.

### Compatibilidad de la enmienda

- RF-13-01, RF-13-07, RF-13-08, RF-13-09 y RF-13-10 no cambian. RF-13-06 solo cambia su punto de entrada y su «Volver».
- `pendientes_retiro` y el retiro tardío del 07 no cambian; «Pendientes de retiro» solo suma el enlace (RF-07-13).
- El cierre del 05 conserva su `motivo` de texto; los registros anteriores siguen válidos y se muestran igual en el historial.
- Se conservan las rutas `/indicadores/mermas/` y la del reporte, que suma el formato `csv`.
- Las pruebas del 13 que revisan el detalle por paciente, el blíster y «Cómo cerró el turno» se reemplazan por las de la enmienda; las demás siguen en verde, junto con las de los specs 05, 07 y 08.

### Decisiones de la enmienda

Decisiones de la usuaria del 2026-11-25 en el chat:

- **Ocho períodos;** Mes, Semestre y Año son de calendario y se recorren con flechas. Se descartaron los períodos móviles de 30, 180 y 365 días.
- **Causa de no entrega en lista cerrada más «Otro»,** que enmienda el 05 (RF-05-14). Se descartó mantener el texto libre y graficar solo cómo cerró el turno.
- **Descargas en Excel, CSV y PDF.** Se descartó retirar el PDF.
- **De los extras propuestos, solo «Ausentes por día y hora».** Quedan fuera, por ahora, el Pareto en los motivos, el reparto por sector y localidad y los tiempos de recuperación.
- **Se conservan «Cuánto llevan en el estante» y «Crónico y general».** Salen el blíster (lo reemplaza la barra de lo preparado), «Cómo cerró el turno» (lo absorben los motivos) y el detalle por paciente.
- **«Derivar a domicilio» pasa a «Pendientes de retiro»** y el panel queda sin datos personales. Se descartó una lista corta de pacientes solo para la Q.F. al final del panel.
- **La receta es la unidad de la tabla en los dos canales,** y la visita, la de los motivos de domicilio, porque el motivo se registra por visita (recomendación aceptada en el chat).
- **Estilo dashboard** según el boceto revisado en el chat.

### Supuestos de la enmienda

Reversibles; se confirman al aprobar:

1. Por omisión se abre el «Mes» en curso.
2. Los períodos de 1 a 14 días terminan hoy y no tienen flechas; para otro día se usa «Personalizado».
3. Las series van por día hasta 31 días, por semana hasta 186 y por mes con más.
4. Los ausentes se ubican por la hora de emisión del número, no por la hora en que se marcaron.
5. Las causas son «Sin stock», «Paciente no la pide», «Receta no vigente o sin cupo», «Cambio de indicación» y «Otro», como en el boceto; se pueden ajustar antes de aprobar.
6. `generar_mermas_demo` suma causas de no entrega y turnos ausentes con su hora; las visitas a domicilio de la demostración siguen saliendo de los comandos y pantallas del 08. Generarlas también sería una tarea aparte, si la usuaria la pide.
7. La herramienta HTTP del 13 genera un año de datos sintéticos en su SQLite temporal, con visitas a domicilio, para medir «Año».

### Revisión de la enmienda

2026-11-25: borrador redactado con las decisiones de la usuaria en el chat (boceto, un bloque de cuatro preguntas y una de seguimiento sobre la derivación). Sin código, migraciones ni aprobación.

2026-11-25 (aprobación): la usuaria indicó «pasa las enmiendas a aprobado e implementa». Las tres enmiendas (13, 05 y 07) pasan a **Aprobada** con los siete supuestos tal como están escritos, y se autoriza implementar T-13-09 a T-13-16.

2026-11-25 (implementación, `crojas-base`, sin commit): T-13-09 a T-13-15 implementadas sin cambiar requisitos. Decisiones de implementación, con su motivo:

- **Granularidad por clase en Mes, Semestre y Año.** Mes va siempre por día, Semestre por semana y Año por mes, aunque estén recién empezando (un año al 5 de enero tiene una sola columna); 1 a 14 días y Personalizado siguen la regla por largo. Así se cumplen a la vez la regla de RF-13-11 y su frase «Así, Mes va por día…».
- **«Personalizado» abre con los últimos 30 días** cuando se elige desde los botones; luego se ajustan «Desde» y «Hasta».
- **Porcentajes de los motivos con un decimal** («33,3 %»), sin forzar que sumen 100: con el método del mayor resto, tres cantidades iguales salían 34/33/33 %. La barra al 100 % de lo preparado y «Crónico y general» siguen con enteros que suman 100.
- **El Excel tiene una cuarta hoja, «Datos de gráficos»,** con las tablas que alimentan los cinco gráficos nativos de «Resumen» (motivos de farmacia y de domicilio, lo preparado, la merma por período y el tipo de paciente), además de «Por día» y «Ausentes por hora».
- **Columnas de horas de la grilla de ausentes:** de 8 a 19 h y contiguas hasta la primera y la última hora con turnos; un turno emitido de madrugada (datos de prueba) agrega las columnas intermedias vacías.
- **Detalle de «Otro»:** el campo de texto conserva su nombre (`motivo` y `motivo_<receta>`) y pasa a ser el detalle; un detalle escrito sin elegir causa se guarda como «Otro», igual que las llamadas anteriores al servicio.
- **`filtros.py` y `entregas.py` se retiraron**, reemplazados por `periodos.py` y `canales.py`; sus pruebas se reemplazaron por `test_periodos.py` y `test_canales.py`. El formulario se lee con `elegido()`: un método llamado `periodo()` tapaba el campo `periodo` y Django lo ignoraba.
- **`tools/previsualizar_interfaz.py`** suma, en su base temporal, horas de emisión repartidas, causas, recetas entregadas en la atención y visitas a domicilio registradas, para revisar todo el dashboard.
