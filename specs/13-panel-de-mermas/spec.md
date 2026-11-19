# SPEC 13 — Panel de mermas

> **Estado:** Aprobado
> **Depende de:** [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 03](../03-padron-y-recetas/spec.md), [SPEC 05](../05-cola-ponderada-y-llamado/spec.md), [SPEC 07](../07-preparacion-y-tiempos-de-espera/spec.md) y [SPEC 08](../08-domicilios-y-entregas/spec.md)
> **Fecha:** 2026-11-17
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
- **RF-13-02 — Filtros:** el rango se aplica sobre la fecha local de preparación. Por omisión son los últimos 30 días, hoy incluido, y el tipo «Todos». El tipo Crónico o General sale de `Paciente.es_cronico`. SI el inicio es posterior al fin, el fin es futuro o el rango supera 366 días, ENTONCES se rechaza con un mensaje claro y se muestra el filtro por omisión. Los filtros viajan en la URL (GET) y no llevan datos personales.
- **RF-13-03 — Cifras y gráficos:** el panel muestra la merma total, «Sin retirar», «En despacho», «Retiradas tarde» y «Entregadas por despacho», y cuatro gráficos:
  1. evolución de la merma por día (rango de 31 días o menos) o por semana de lunes a domingo (rango mayor);
  2. crónico frente a general;
  3. por cómo cerró el turno (ausente, atendido, cerrado sin entrega, sin atención al cierre);
  4. recuperadas frente a perdidas (los cuatro estados de RF-13-01).

  Cada gráfico tiene su tabla de datos y textos visibles; nada depende solo del color. SI el período no tiene recetas, ENTONCES se muestra «No hay recetas no retiradas en este período» en lugar de los gráficos.
- **RF-13-04 — Detalle por paciente:** lista una fila por paciente con merma en el período: RUT, nombre, Crónico o General, cantidad «Sin retirar» y «En despacho», fecha de preparación más antigua, y si es elegible para el reparto (postrado, 80 años o más, excepción vigente o «No elegible»). Se ordena por la fecha más antigua y se pagina de a 50. La Q.F. ve el botón «Derivar a domicilio» en las filas con recetas «Sin retirar»; el Director no lo ve.
- **RF-13-05 — Reportes descargables:** con el filtro vigente se descarga un Excel (`.xlsx`, hoja «Resumen» con cifras y los cuatro gráficos nativos, y hoja «Datos» con la serie por día o semana) o un PDF vertical tamaño carta con cifras, gráficos y sus tablas. Los reportes **nunca** incluyen RUT, nombres, fechas de nacimiento, direcciones, teléfonos ni identificadores internos de pacientes o recetas; solo cifras agregadas, el período, el filtro, la fecha y hora de generación y el rol de quien lo generó. El nombre del archivo es `mermas_<inicio>_<fin>.xlsx` o `.pdf`. La respuesta es `no-store` y queda auditada (actor, formato, rango y tipo).
- **RF-13-06 — Derivación al reparto:** CUANDO la Q.F. confirma la derivación de un paciente con fecha y encargado válidos, EL SISTEMA, en una sola transacción e idempotente por operación:
  - si el paciente no es elegible a esa fecha, crea su excepción de reparto con el motivo elegido (exigido en ese caso);
  - programa la entrega con sus recetas «Sin retirar» y las demás recetas elegibles en esa fecha según el 08, y su primer intento;
  - deja ligada cada receta preparada a su preparación (RF-13-07) y audita la derivación.

  SI ya tiene una entrega abierta, ENTONCES no deriva y responde «Ya tiene una entrega abierta» con el enlace. SI ya no tiene recetas «Sin retirar» (se retiraron o derivaron mientras tanto), ENTONCES rechaza sin cambios. SI falla cualquier paso, no queda ni la excepción ni la entrega.
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
