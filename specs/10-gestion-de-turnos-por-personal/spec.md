# SPEC 10 — Gestión de turnos por personal

> **Estado:** Aprobado
> **Depende de:** [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 04](../04-emision-de-turnos/spec.md), [SPEC 05](../05-cola-ponderada-y-llamado/spec.md) y [SPEC 06](../06-pantalla-sala-y-voz/spec.md)
> **Fecha:** 2026-11-15
> **Objetivo:** Permitir que la Q.F. termine el turno de cualquier ventanilla sin perder al paciente llamado, y que el personal reclasifique un turno en espera o lo marque como urgencia (U), con auditoría.

Módulo solicitado: `turnosapp` (extensión), con un cambio acotado en `usuariosapp` (desactivación de cuentas). Fuente: revisión de los specs 01–07 del 2026-11-14 (hallazgos A2, A3 y A4), decisiones de la usuaria del 2026-11-14 y 2026-11-15, HU-07 y HU-10 del [informe](../../docs/Informe.md).
Implementación autorizada: NO. Revisión de la usuaria: aprobado el 2026-11-15 («pasa todo a aprobado»).

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

- **Ventanilla bloqueada (A3):** hoy una ventanilla ocupada solo la libera su propio Técnico. Si falta o se le desactiva la cuenta, nadie puede liberarla, y su turno llamado queda abierto indefinidamente, incluso al día siguiente (A2). HU-10 pide un «Término de turno» que registre la hora y deshabilite la ventanilla, y ningún spec lo cubre.
- **Sin urgencia ni reclasificación (A4):** el tótem clasifica solo por edad y crónico. HU-07 y HU-10 piden atender urgencias, y el spec 04 dejó la urgencia y la validación de otras preferencias (por ejemplo, discapacidad) para el personal, que hoy no tiene cómo hacerlo.

El resultado se reconoce porque:

- la Q.F. termina el turno de cualquier ventanilla y el paciente que estaba llamado vuelve a la cola sin perder su antigüedad;
- desactivar a un Técnico libera su ventanilla de la misma forma;
- el personal cambia la letra de un turno en espera o lo marca urgente; el turno urgente recibe un número U y es el siguiente en ser llamado.

## Actores y permisos

| Acción | Anónimo / tótem | Técnico | Encargado de terreno | Q.F. | Superusuario activo |
|---|---|---|---|---|---|
| Terminar el turno de su propia ventanilla | No | Sí (equivale a liberar, spec 05) | No | No opera ventanillas | Sí |
| Terminar el turno de una ventanilla ajena | No | No | No | Sí | Sí |
| Reclasificar un turno en espera entre P, G y C | No | Sí | No | Sí | Sí |
| Marcar un turno en espera como urgencia (U) | No | Sí | No | Sí | Sí |
| Quitar la urgencia o elegir posición en la fila | No | No | No | No | No |

Se revalidan en el servidor la cuenta activa, el perfil y el rol único (spec 02). Se conserva la excepción del superusuario.

## Alcance y exclusiones

Incluye:

- término de turno de una ventanilla, propia o ajena, con hora de término, deshabilitación y devolución a la cola del turno llamado;
- liberación automática de la ventanilla al desactivar la cuenta de su operador;
- cierre de un turno llamado de un día anterior al terminar el turno de la ventanilla;
- reclasificación de un turno en espera entre P, G y C;
- marca de urgencia, con número nuevo de la serie U, prioridad sobre toda la cola y comprobante nuevo;
- auditoría, historial y pruebas concurrentes.

No incluye:

- emitir turnos desde el panel del personal: el tótem ya emite a todo RUT válido (enmienda del spec 04);
- agregar discapacidad u otras condiciones al padrón;
- quitar la urgencia una vez asignada, o elegir manualmente qué turno sigue;
- el diseño visual de la sala, que se trabaja aparte.

## Historias y flujo

1. **Término de turno.** La Q.F. abre la configuración de ventanillas y pulsa «Término de turno» en una de ellas. Si hay un paciente llamado, el sistema pide confirmación. Al confirmar:
   - queda registrada la hora de término y se cierra la ocupación del operador;
   - la ventanilla queda deshabilitada;
   - el turno llamado vuelve a «esperando» con su hora original de entrada a la cola, y la selección automática lo ofrece a otra ventanilla compatible.
2. **Desactivación de cuenta.** Si la Q.F. o el superusuario desactiva la cuenta de un Técnico que ocupa una ventanilla, en la misma operación se aplica el paso 1 a esa ventanilla.
3. **Turno de un día anterior.** Si el turno llamado es de un día anterior, al terminar el turno de la ventanilla se cierra como `sin_atencion_cierre`, igual que las esperas antiguas del spec 05, y no vuelve a la cola.
4. **Reclasificación.** El Técnico o la Q.F. elige un turno en espera y una nueva letra entre P, G y C. El turno recibe un número nuevo de la serie de esa letra, cambia de fila conservando su antigüedad y queda registrado el cambio.
5. **Urgencia.** El Técnico o la Q.F. marca un turno en espera como urgente. El turno recibe el siguiente número de la serie U del día y se llama antes que cualquier otro. El equipo del personal muestra a pantalla completa el mismo comprobante en PDF del tótem con el número nuevo, para que el paciente lo vea; no se imprime. La reclasificación (paso 4) muestra el comprobante de la misma forma.

## Requisitos funcionales

- **RF-10-01 — Término de turno de ventanilla:** CUANDO la Q.F. (o el Técnico sobre la propia) confirma el término de turno de una ventanilla, EL SISTEMA, en una sola transacción:
  - registra la hora de término y cierra la ocupación vigente;
  - deshabilita la ventanilla;
  - devuelve a «esperando» el turno llamado de la jornada, conservando su `entrada_cola` original, y deja auditado quién lo hizo.

  SI hay un turno llamado, ENTONCES exige confirmación explícita. Repetir la operación no duplica efectos.
- **RF-10-02 — Desactivación de cuenta:** CUANDO se desactiva la cuenta de un operador con ventanilla ocupada, EL SISTEMA aplica RF-10-01 a esa ventanilla en la misma transacción que la desactivación. SI falla, ENTONCES no se desactiva la cuenta.
- **RF-10-03 — Llamado de un día anterior:** SI el turno llamado de la ventanilla que termina su turno es de una fecha anterior, ENTONCES se cierra como `sin_atencion_cierre` y no vuelve a la cola. Si la persona regresa, saca un número nuevo en el tótem.
- **RF-10-04 — Reclasificación P/G/C:** CUANDO el personal autorizado cambia la letra de un turno en «esperando», EL SISTEMA:
  - le asigna el siguiente número diario de la serie de la nueva letra, para que la letra del comprobante coincida con la fila;
  - conserva su antigüedad en la cola;
  - registra la letra y el número anteriores (que no se reutilizan);
  - muestra el comprobante nuevo según RF-10-05.

  SI el turno ya fue llamado o cerrado, o la letra nueva es la misma, ENTONCES rechaza el cambio.
- **RF-10-05 — Urgencia (U):** CUANDO el personal autorizado marca como urgente un turno en «esperando», EL SISTEMA:
  - le asigna el siguiente número diario de la serie U, que reemplaza al anterior;
  - registra la letra y el número anteriores, el actor y el instante;
  - lo deja primero en la fila U, que la selección del spec 05 atiende antes que cualquier P, C o G (RF-05-13);
  - abre en el equipo del personal, a pantalla completa, el mismo comprobante en PDF del tótem (RF-04-08) con el número nuevo y el aviso «Reemplaza a tu número anterior», para mostrárselo al paciente. No se imprime ni se guarda; el personal vuelve al panel con «Listo, volver al panel».

  SI el turno ya fue llamado o cerrado, ENTONCES rechaza la marca. La urgencia no se puede quitar desde la aplicación.
- **RF-10-06 — Concurrencia:** la reclasificación y la urgencia usan UPDATE condicional sobre el estado «esperando» y la versión del turno, y reservan el número U con la misma técnica del contador por letra del spec 04. Un turno que se llama mientras se reclasifica queda en un solo estado coherente: o se llamó con la letra anterior, o se reclasificó y espera. Nunca queda asignado a dos ventanillas ni con dos números.
- **RF-10-07 — Historial y auditoría:** cada término de turno, reclasificación y urgencia queda en el historial del turno y en la auditoría, sin RUT, nombres, datos clínicos ni texto libre. La sala no anuncia las reclasificaciones; solo cambia la cantidad por letra de «En espera» (RF-06-13).

## Datos y reglas

- La hora de término es el cierre de la ocupación de la ventanilla (`cierre`), que ya existe en el spec 05. No se crea otra tabla para el término de turno.
- El número anterior de un turno reclasificado o urgente se conserva en su evento de historial; no se reutiliza en la serie anterior.
- La urgencia no exige motivo: basta con el actor y el instante registrados, y así no se guarda ningún dato clínico.
- Una ventanilla terminada se rehabilita con el flujo normal del spec 05 (habilitación por la Q.F. y activación por un Técnico).
- Las reglas de compatibilidad no cambian: un U solo se asigna a una ventanilla que admita urgencia.

## Criterios de aceptación

| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-10-01 | La Q.F. termina el turno de la ventanilla 2, que tiene el turno G-031 llamado desde hace 3 min | La ventanilla queda deshabilitada con hora de término; G-031 vuelve a esperar con su entrada original y otra ventanilla lo llama. |
| RF-10-01 | Termina sin confirmar, o un Técnico intenta terminar una ventanilla ajena | Rechazo sin cambios. |
| RF-10-02 | Se desactiva la cuenta de un Técnico con ventanilla y turno llamado | La cuenta queda inactiva, su ventanilla terminada y el turno de vuelta en la cola. |
| RF-10-03 | La ventanilla tiene llamado un turno de ayer | Al terminar su turno, ese turno queda `sin_atencion_cierre` y no vuelve a la cola. |
| RF-10-04 | Reclasificar C-009 en espera a P | Recibe el siguiente número P del día, pasa a la fila P con su antigüedad y queda el registro con C-009. |
| RF-10-04 | Reclasificar un turno ya llamado | Rechazo sin cambios. |
| RF-10-04 | Reclasificar C-009 a la misma letra C | Rechazo sin cambios. |
| RF-10-05 | Marcar urgente G-040 con P, C y G en cola | Recibe U-001 (o el siguiente U del día), es el próximo llamado compatible y el equipo del personal muestra el comprobante PDF a pantalla completa. |
| RF-10-06 | Marcar urgente un turno mientras una ventanilla lo selecciona | Un solo resultado coherente; sin doble asignación ni doble número. |
| RF-10-06 | Dos personas marcan urgentes dos turnos a la vez | Números U distintos y consecutivos. |
| RF-10-07 | Se inspeccionan el historial, la auditoría y la sala | Historial con letra y número anteriores; auditoría sin datos personales; la sala no pronuncia la reclasificación. |

## No funcionales

- **Concurrencia (RNF-02):** cambian el llamado, la asignación y la numeración, así que se exigen al menos tres escenarios con `TransactionTestCase`, hilos y conexiones separadas: término de turno frente a cierre de la atención; urgencia frente a selección; dos urgencias simultáneas.
- **Rendimiento (RNF-05):** 2 s o menos en el 95 % de las acciones, con el padrón sintético de 670 y cuatro ventanillas.
- **Accesibilidad (RNF-04):** WCAG 2.1 AA en el panel; la confirmación del término de turno y el número U nuevo se comunican con texto, no solo con color.
- **Privacidad (RNF-01):** solo datos sintéticos; el RUT solo en vistas privadas.

## Compatibilidad

Se conservan los contratos concurrentes del spec 05 (`cola.py`, `atencion.py`) y sus pruebas, el anuncio público del 06 y la emisión del 04 con su enmienda. `liberar` del spec 05 sigue funcionando para el propio Técnico. `cambiar_estado_cuenta` del spec 02 gana el efecto de RF-10-02 sin cambiar sus permisos.

## Decisiones tomadas y alternativas

- **El turno llamado vuelve a la cola conservando su antigüedad** (decisión de la usuaria, 2026-11-14). Se descartaron que la Q.F. elija caso a caso y que se marque ausente.
- **La urgencia da un número nuevo de la serie U y pasa primero** (decisión de la usuaria, 2026-11-15). Se descartaron conservar el número y entrar con un peso alto.
- **El personal no emite turnos;** el tótem abierto lo hace (decisión de la usuaria, 2026-11-14).
- **Número 10:** primer número libre no reservado según el índice; la propuesta sin documento de mermas pasa al 13.

## Supuestos y decisiones pendientes

No quedan decisiones funcionales pendientes. Resueltas el 2026-11-15:

1. Reclasifican y marcan urgencia el Técnico y la Q.F. (y el superusuario).
2. La reclasificación entre P, G y C da un número nuevo de la serie de la nueva letra.
3. La urgencia no exige motivo.
4. El comprobante nuevo es el mismo PDF del tótem, a pantalla completa en el equipo del personal, sin impresión.
5. Se confirma RF-10-03: el llamado de un día anterior se cierra y no vuelve a la cola.

Supuesto técnico: el equipo del personal tiene un navegador que muestra PDF incrustado (el mismo riesgo del visor que en el tótem).

## Revisión y cambios

2026-11-15: borrador creado a partir de la revisión del 2026-11-14 y de las decisiones de la usuaria sobre A3 (devolver a la cola), A4 (tótem abierto, reclasificación y urgencia) y las letras P/G/C/U. Sin código, migraciones ni aprobación.

2026-11-15 (posterior): la usuaria eligió las propuestas recomendadas para las decisiones 1, 2, 3 y 5. En la decisión 4 eligió mostrar el mismo comprobante en PDF del tótem, a pantalla completa en el equipo del personal, en vez de imprimirlo. Se quitan los rótulos de propuesta.

2026-11-15 (aprobación): la usuaria indicó «pasa todo a aprobado». El documento pasa a **Aprobado**. La aprobación es documental: la implementación requiere autorización aparte mediante `/spec-impl 10-gestion-de-turnos-por-personal`.
