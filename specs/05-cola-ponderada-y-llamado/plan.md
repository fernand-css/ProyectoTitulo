# Plan técnico — 05 / Cola ponderada y llamado

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-02. Estado: diseño aprobado; T-05-01 a T-05-04 completados y verificados. Panel y configuración visual pendientes. Rama `fdaza`, sin rama nueva y un único commit al finalizar.

## Inspección de la base

Revisados memoria del proyecto, informe, specs 03/04, índice y plantillas. `turnosapp.models` tiene contador diario, `Turno` solo `esperando`, `TurnoReceta` y restricciones. `services.emitir_turno` recupera únicamente esperando, selecciona todas las recetas elegibles y audita con actor nulo. Las vistas públicas guardan contexto temporal y nunca muestran ficha. El 04 no incluye ventanilla ni ciclo de atención.

`recetasapp.services.registrar_entrega(actor, receta_id, operacion_id)` exige Técnico/superusuario, revalida vigencia/cupo y reserva contador con UPDATE condicional; el UUID es único. Sus reintentos actuales envuelven transacciones individuales: para el cierre de varias recetas hay que extraer/reutilizar una operación interna sin reintentos locales y reintentar toda la transacción de cierre. No continuar sobre una transacción rota.

La auditoría y habilitación del 02 ya existen. No registrar modelos nuevos con escritura libre en Admin. Cambios ajenos observados: eliminación de `docs/verificacion-spec-01.md` y encabezados de specs 02/03 modificados; preservarlos. No usar la SQLite local ni alterar sus datos al definir/probar.

## Diseño propuesto

Avance T-05-04: `finalizar_atencion` valida selección/motivos y confirma cierre, detalles, nuevas entregas y evento en la transacción de `_operar`. Solo después se procesa su pendiente de selección; la respuesta lleva referencia persistida para consultar si la continuación está pendiente. Un reenvío conserva el resultado original sin tocar el turno siguiente. Las entregas previas vinculadas del 03 se consideran ya confirmadas, conservan actor/fecha y no pueden convertirse en «no entregadas» desmarcando una casilla. El futuro formulario las mostrará como realizadas, sin opción de deshacerlas.

`recetasapp.services` separa `_registrar_entrega_sin_reintento` de la entrada pública `registrar_entrega`, que reserva la cola y mantiene la operación independiente del 03 si no hay atención vinculada. El cierre usa la función interna para reintentar la unidad completa; un `ConflictoOperacion` revierte todo el cierre. Cuando se recupera una entrega asociada con otro UUID del 03, `OperacionAtencion` registra esa identidad como alias técnico ligado a actor/receta/turno, evitando reutilizarla después para otro destino sin duplicar el evento de entrega.

El formulario del 03 agrega `contexto` firmado (`recetasapp/confirmacion.py`) con actor, receta, UUID, vínculo de atención y contador observado. No contiene RUT/nombre. Protege el formulario que permanece abierto mientras se cierra desde el 05: recupera su entrega ligada o detecta cambio de contador sin emitir otra. Los clientes anteriores sin contexto conservan el flujo independiente cuando no hay atención llamada; si hay una, se solicita volver a abrir el formulario. El contexto de atención es explícito en las llamadas que deben recuperar una entrega tras el cierre; una nueva operación independiente sin contexto no se vincula retrospectivamente a historia cerrada.

Avance T-05-03: `atencion.py` implementa ocupación, inicio/pausa/liberación, configuración/creación de ventanillas y pesos, re-llamado, ausencia y retorno. Todas las acciones reservan el mismo estado diario que el planificador, revalidan rol/ocupación y guardan UUID, huella de parámetros y resultado. El reenvío exige mismo actor/acción/destino/payload; devuelve el resultado original aunque el turno haya cambiado después. Configuración y pesos están disponibles como servicios para las futuras pantallas, no como endpoints públicos.

`cola.bloquear_cola` comparte la serialización con emisión/operación. `cerrar_esperas_anteriores` conserva llamado y cierra esperando antiguos con evento/auditoría de sistema; el procesador lo intenta incluso sin pendientes de selección. `services._anterior` recupera llamado de otra fecha que siga vigente, y rechaza reenvío de UUID de un turno terminal; una operación nueva sin activo puede emitir normalmente. La emisión captura un solo instante/fecha y serializa con reincorporación. El Técnico puede reincorporar ausente del día sin otro activo y respetando bloqueo domiciliario; número/categoría/recetas originales se conservan, pero entrada de cola se renueva.

Pausa y deshabilitación preservan llamado vigente y desactivan automatismo. Q.F. confirma si hay atención; volver a habilitar no reactiva llamadas. Re-llamado reinicia el minuto sin tocar cursor/entregas. Ausencia guarda evento y pendiente de selección en su transacción; el intento de llamar al siguiente es posterior al commit. Las acciones de cierre clínico y su integración con entregas aún son T-05-04. No se crearon migraciones en este paso.

Avance T-05-02: `cola.py` implementa selección, cálculo de advertencia/prioridad, disparadores y recuperación; `procesar_cola` procesa una pasada por defecto o usa `--continuo --intervalo 1` como respaldo del servidor. El límite es de 100 pendientes por pasada por defecto. La emisión guarda un pendiente con UUID derivado de su operación y registra un intento posterior al commit; recuperar no crea otro pendiente. La búsqueda de activo incluye llamado para recuperar una emisión que el planificador ya asignó. Sin configuración, el turno sigue confirmado y el pendiente queda con código fijo `sin_configuracion`, sin inventar pesos antes de la preparación explícita.

Los intervalos de pesos se recorren sin construir una lista del tamaño de sus valores. La selección serializa con UPDATE condicional de `EstadoColaDiaria.version`, reserva la versión de ventanilla y comprueba operador habilitado/ocupación vigente; el cambio de turno, cursor, evento, operación automática y auditoría comparten transacción. El fallo revierte el llamado y conserva el pendiente con código técnico, sin copiar excepción. Un pendiente procesado no se vuelve a usar para llamar otro turno. Solo se consideran turnos de la fecha actual y ventanillas activadas para ella; el cierre material de jornadas y los disparadores de otras acciones se implementarán en T-05-03/04.

Avance T-05-01: modelos de ventanillas/tipos, ocupación, configuración/estado diario, operación/evento, cierre/detalle y pendientes incorporados. `Turno` incluye seis estados, entrada actual a cola y asignación/cierre coherentes, con unicidad de llamado por ventanilla y por paciente. `EntregaReceta.turno_receta` es nullable y única; no se asocian entregas previas por inferencia. `preparar_ventanillas --database` crea tres tipos, pesos 2/1/1 y cuatro ventanillas con todos los tipos, auditando en una transacción. Repetir no cambia configuración ni crea eventos adicionales; no activa automatismo ni crea cuentas, turnos o entregas. No se ejecutó contra la base local.

Extender `turnosapp` y adaptar el servicio de entregas existente. Separar `cola.py` (selección y activación), `atencion.py` (ocupación, llamado/re-llamado, ausencia, retorno y cierre) y `services.py` (emisión pública que dispara selección después de confirmar). Mantener reglas en servicios; vistas/forms no eligen candidato ni escriben estados directamente.

No crear otra app ni depender de Celery, Redis, WebSocket o un sistema de voz en este spec. Generar pendientes durables de selección en la misma transacción que libera capacidad o agrega cola. Intentar resolverlos tras commit; un comando de Django procesa pendientes como respaldo tras reinicios y mientras haya automatismo activado. El panel consulta estado privado por GET y ofrece reintentar pendiente mediante POST con CSRF; no esconder escrituras dentro de GET/polling.

El proceso de selección es parte de la operación del servidor, no depende de que el Técnico tenga que pulsar otro botón ni de que el emisor del tótem tenga permisos de personal. Cada selección valida operador habilitado y activación de jornada persistidos. Cerrar una pestaña no equivale a pausar: la interfaz debe explicar que se pausa antes de abandonar la ventanilla. No inferir presencia física por una pestaña abierta.

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio | Evidencia prevista |
|---|---|---|---|
| RF-05-01 | Existente `turnosapp/models.py`; nuevos `atencion.py`, comandos de preparación | Ventanillas, ocupaciones e historial | Ocupación simultánea y conservación de historia |
| RF-05-02, RF-05-03 | Nuevos `turnosapp/cola.py`, configuración/estado de cola | Ciclo global, compatibilidad y espera | Secuencias deterministas, vacíos y umbrales |
| RF-05-04, RF-05-08 | `services.py`; nuevos `cola.py`, comando de pendientes | Disparadores y recuperación automática | Llegadas/fin/ausencia/reinicio y concurrencia |
| RF-05-05, RF-05-06 | Nuevos `atencion.py`, eventos e historial | Re-llamado, minuto y retorno | Reloj servidor y misma asignación |
| RF-05-07 | `recetasapp/services.py`, `models.py`; `turnosapp/models.py`, `atencion.py` | Cierre atómico y entrega asociada al turno | Reenvío, cupo disputado y 03/05 simultáneos |
| RF-05-09, RF-05-10 | `atencion.py`, `cola.py`, comandos | Pausa, deshabilitación y cierre diario | Carreras de cierre/llamado y medianoche |
| RF-05-11 | Existentes `services.py`, restricciones y pruebas del tótem | Activos esperando/llamado; nuevo turno tras terminal | Recuperación y reincorporación frente a emisión |
| RF-05-12 | Forms/vistas/URLs/Admin y nuevos tests | Matriz, CSRF y auditoría | Accesos directos, revocación y rollback |

## Datos y contratos

### Modelos propuestos

| Modelo | Datos / restricciones |
|---|---|
| `Ventanilla` | Número único positivo, habilitada, retirada, tipos admitidos mediante catálogo/relación, operador actual nullable, automatismo activo, fecha de activación, versión para UPDATE condicional, instante desde que quedó disponible. Operador actual único si no nulo. Retirada/habilitación/automatismo deben ser coherentes. |
| `OcupacionVentanilla` | Ventanilla, Técnico, apertura/cierre y motivo técnico; historial conservado. Una ocupación vigente por ventanilla y por Técnico, con restricciones únicas condicionales. |
| `ConfiguracionCola` | Fila única, pesos enteros positivos por tipo, versión y responsable/fecha. Valores iniciales 2/1/1. No usar peso cero para deshabilitar categorías. |
| `EstadoColaDiaria` | Fecha única, cursor de ciclo, versión de configuración y contador/versionado de selección. Serializa el turno del planificador con UPDATE condicional. |
| `Turno` ampliado | Estados `esperando`, `llamado`, `atendido`, `ausente`, `cerrado_sin_entrega`, `sin_atencion_cierre`; entrada actual a cola, ventanilla/operador actuales cuando llamado, último llamado y cierre. Conservar número/fecha y emisión original. Restricciones de estado y asignación coherentes; activo por paciente/fecha incluye esperando/llamado; único llamado por ventanilla. |
| `EventoTurno` | UUID de evento, turno, secuencia única por turno, acción, instante, actor, ventanilla y referencia técnica de operación. Eventos inmutables. Datos clínicos y motivos libres quedan fuera del contenido destinado al 06. |
| `OperacionAtencion` | UUID único, actor, tipo, turno/ventanilla destino, huella de parámetros y resultado técnico persistido. Repetición exige mismo actor, tipo y destino; otro payload con el UUID se rechaza. |
| `CierreAtencion` y `DetalleCierre` | Un cierre por turno; actor/instante, resultado, receta vinculada, entregada/no entregada, motivo cuando no se entrega y vínculo a entrega. Un detalle por turno/receta. No sustituye `EntregaReceta`. |
| `PendienteSeleccion` | Identidad única por disparador, fecha, estado pendiente/procesado, versión/intentado y motivo técnico de fallo fijo. No copiar excepción ni entrada de paciente. Procesamiento repetido no duplica asignación/evento. |

`TurnoReceta` conserva selección de emisión. Proponer relación nullable única desde `EntregaReceta` hacia `TurnoReceta` (o asociación equivalente con unicidad en ambos extremos) para identificar una entrega de esa atención. No cambiar ni relacionar retroactivamente entregas históricas por conjetura.

Al confirmar desde el formulario del 03, si la receta tiene una atención llamada vigente, resolver su `TurnoReceta` y asociar la entrega de esa operación; si ya existe, mostrarla sin incrementar otra vez. Al cerrar desde 05, reutilizar esa entrega vinculada, sin adjudicarla a un actor distinto del registrado. Sin turno llamado relacionado, el flujo independiente del 03 sigue funcionando como antes. Esta integración se implementa en el servicio compartido, nunca solo en una pantalla. Probar expresamente 03/05 simultáneos y dos confirmaciones del 03 contra la misma atención.

### Selección determinista y compatible

1. Capturar fecha/instante del servidor. Resolver cierre de jornada antes de seleccionar; no aplicar cursor de otro día. Para la fecha nueva, el cursor arranca al inicio del ciclo. Cambiar configuración reinicia su cursor para futuras selecciones.
2. Considerar ventanillas habilitadas, no retiradas, con operador habilitado y automatismo activado para la fecha, sin turno llamado. Ordenarlas por instante disponible y número para desempate estable.
3. Para cada ventanilla, construir candidatos esperando de la fecha y tipos compatibles, sin otro turno del mismo paciente ya llamado. Orden dentro del tipo: entrada actual a cola, número y PK. No usar orden de emisión original para un reincorporado.
4. Si hay candidatos con espera actual ≥15 minutos, tomar el más antiguo compatible, sin avanzar cursor. Antes de ese umbral mostrar advertencia desde los 12 minutos.
5. En otro caso, recorrer el ciclo desde el cursor hasta una categoría compatible con candidatos. Elegir su primero y avanzar al puesto siguiente al consumido. Saltar huecos sin acumular crédito. Si no hay candidatos compatibles, no avanzar cursor ni crear llamado.
6. Reservar candidato con UPDATE condicional desde esperando a llamado y reservar ventanilla libre/habilitada con su versión. Guardar evento/auditoría junto a cursor y asignación dentro de la misma transacción. Si cambió estado, operador o habilitación, rollback/reintento desde estado fresco.

La proporción 2:1:1 es verificable con cola abastecida, ventanas compatibles y sin rescates por espera; no prometer exactamente esa proporción cuando hay tipos vacíos, restricciones de ventanilla o rescate a los 15 minutos. Una ventanilla no espera un tipo que no puede atender mientras haya otro compatible.

### Disparadores, continuidad y persistencia

Guardar `PendienteSeleccion` al emitir/reincorporar, activar/reanudar, cambiar capacidad/pesos o liberar por cierre/ausencia. `transaction.on_commit` solo intenta procesarlo; no es su única garantía. Si la base confirma el turno del tótem y falla el llamado, el tótem conserva el número y la emisión; no informa fracaso de emisión por ese fallo posterior.

Proponer `procesar_cola` como comando idempotente, modo una pasada o bucle con intervalo de un segundo, para recuperar pendientes tras reinicio. Documentar que el prototipo necesita ese proceso de respaldo además del servidor cuando se exige recuperación automática de fallos. No introducir un servicio externo. El comando verifica permisos/fecha de activación del operador persistido antes de cada asignación; no ejecuta acciones clínicas por el solo hecho de tener un pendiente.

Al abrir la ventanilla y al inicio de jornada, resolver asignaciones en servidor. GET de estado del panel es solo lectura; propuesta de actualización privada cada segundo sin WebSocket. Respuestas en curso no pisan versiones más nuevas del panel. Botón de reintentar pendiente no selecciona manualmente un paciente.

### Operaciones, atomicidad e idempotencia

Servicios propuestos: `ocupar_ventanilla`, `iniciar_automatico`, `pausar_ventanilla`, `configurar_ventanilla`, `configurar_pesos`, `rellamar`, `marcar_ausente`, `reincorporar`, `finalizar_atencion`, `procesar_pendientes`, `cerrar_jornada_anterior`.

Toda mutación del personal lleva UUID emitido por servidor, validado por acción/actor/destino y guardado con el resultado. Distinguir re-llamar intencionalmente (nuevo UUID) de reenvío del mismo botón. La confirmación de cierre de un turno anterior no actúa sobre «el turno actual» de la ventanilla si ya cambió.

`finalizar_atencion(actor, turno_id, operacion_id, seleccion, motivos)` revalida ocupación, estado, vínculo y elegibilidad en una sola transacción externa. Usa UUID de entrega derivados establemente de operación/receta o identidades guardadas previamente. Extraer la operación interna de `registrar_entrega` para que un conflicto reintente todo el cierre y no una parte anidada. Si falla una seleccionada o la auditoría, revertir todas las entregas nuevas y el cierre; conservar las entregas previas ya confirmadas desde 03, sin revertir historia ajena. Reutilizar las asociadas y generar detalles de no entrega para las restantes; no inferir que una receta recibió medicamentos porque el turno se cerró.

Al confirmar, guardar cierre y pendiente de selección; después intentar resolverlo en otra transacción. Un fallo del siguiente llamado no cambia el éxito del cierre. La respuesta distingue «atención finalizada; próximo llamado pendiente» de «no se confirmó el cierre». La reanudación de pendiente conserva asignaciones ya confirmadas.

SQLite: reintentos acotados de bloqueos/colisiones conocidas, sin capturar y seguir dentro de `atomic()` roto. Restricciones de turno/ocupación/entrega/eventos como garantía final. No confiar en mutex de proceso ni `select_for_update()`. Usar orden consistente de escrituras entre estado de cola, ventanilla, turno y recetas para reducir conflictos; probar con el patrón de reintentos del 03/04 y futura PostgreSQL sin SQL propietario.

### Jornadas y compatibilidad del tótem

Cerrar esperando anteriores en operación auditada e idempotente antes de emitir/seleccionar/reincorporar en la nueva fecha. Si nadie usa el sistema a medianoche, el comando de cola realiza el cierre al siguiente ciclo; su efecto es lógico por fecha, sin arrastrar candidatos mientras no se haya materializado el cierre. Un llamado anterior conserva ventanilla/operador hasta cerrar o marcar ausencia cuando proceda; requiere inicio explícito para que después se llame a la jornada nueva.

La emisión consulta activos esperando/llamado, incluido un llamado del paciente que continúe desde la fecha anterior. No crear otro simultáneo. Actualizar la restricción de activo del 04 para incluir llamado y proteger también emisión frente a reincorporación. Una reemisión tras ausente/atendido usa UUID nuevo y correlativo nuevo; un reenvío de la operación original sigue siendo la misma operación y no crea otro turno. La pantalla del tótem para un UUID terminal original no debe presentar un turno cerrado como si estuviera esperando: indicar iniciar nueva atención, sin ficha pública.

El historial del ausente no se borra si el paciente elige obtener otro número. Reincorporar solo ausentes del día y sin otro activo, después de revalidar las condiciones de atención presencial y paciente habilitado por las reglas del 04. No reincorporar al retirar una condición de domicilio mediante un parámetro del cliente.

## Permisos e interfaz

| Rutas propuestas bajo `/turnos/` | Uso |
|---|---|
| `panel/`, `estado/` | Cola privada, espera y ventanilla propia; GET sin mutación |
| `ventanillas/<pk>/ocupar/`, `iniciar/`, `pausar/`, `liberar/` | POST del operador; no liberar con atención vigente |
| `gestion/`, `gestion/ventanillas/`, `gestion/pesos/` | Q.F./superusuario: configuración y estado operativo |
| `<pk>/rellamar/`, `ausente/`, `reincorporar/`, `finalizar/` | Acciones idempotentes; formulario de cierre con recetas reales del turno |
| `pendientes/reintentar/` | POST de recuperación autorizada, sin elegir paciente |

Separar permisos de supervisor y operador. Q.F. ve estado/espera, no botones de entrega. Técnico ve identificación mínima privada para dispensar; público y eventos del 06 solo número/fecha/ventanilla/instante/UUID, nunca categoría, nombre o RUT. Motivos en formularios privados, con límites de longitud/escape; auditoría solo referencia técnica y acción fija.

Reutilizar `base.html`, navbar e identidad existentes. Plantillas propuestas `templates/turnos/panel.html`, `gestion.html`, `ventanilla_form.html`, `pesos_form.html`, `finalizar.html`, `historial.html`; nuevos estáticos `cola.css` y `cola.js` cuando sea necesario. Botones de inicio/pausa visibles y estados explícitos: libre, automática disponible, paciente llamado, pausa solicitada, cerrada, llamada pendiente de recuperar. No ofrecer botón «elegir siguiente» ni comunicar que ya hubo voz pública.

## Migraciones y reversión

Migraciones reales del paso 1: `recetasapp.0003_entregareceta_turno_receta` depende de recetas 0002 y turnos 0001; `turnosapp.0002_cierreatencion_configuracioncola_detallecierre_and_more` depende de recetas 0003 y turnos 0001. El grafo no tiene ciclo: `TurnoReceta` ya existía en turnos 0001 y permite agregar primero el vínculo de entrega. No se alteran migraciones históricas del 03/04. La migración de turnos inicializa `entrada_cola` desde `creado_en` usando modelos históricos y alias de base, sin crear datos operativos. La reversión de esa copia de fecha es no-op; retroceso con estados nuevos/historia real requiere respaldo y no se presenta como reversión sin pérdida.

Se adapta la prueba de migración anterior del 04 para fijar la versión de recetas previa al nuevo vínculo (0002): antes tomaba el último nodo de recetas y construía un estado histórico con una columna ya revertida por la dependencia de turnos. La corrección mantiene la comprobación de cuentas, grupos, perfiles, recetas, entregas y auditoría originales.

Crear migración posterior a `turnosapp.0001` y una posterior a `recetasapp.0002` para el vínculo de entrega si se adopta. Evitar ciclo de dependencias: primero ampliar turnos y crear modelos de atención que no dependan de la nueva relación; después agregar relación desde recetas a `TurnoReceta`. Consultar nombres reales antes de generar.

Preservar turnos/números/UUID y entregas históricos; inicializar entrada actual a cola desde emisión para esperando existentes. No fabricar llamadas, cierres ni asociaciones clínicas históricas. Validar estados/ocupaciones previos y migración de restricciones. Preparación explícita e idempotente de cuatro ventanillas, tres tipos y pesos 2/1/1, auditada con origen técnico claro; no crear usuarios ni llamar desde migraciones/`ready()`. Las ventanillas no quedan con automatismo activo al preparar.

Comprobar base vacía y actualización de base sintética con 03/04 y turnos de distintas fechas. Retroceso elimina configuración/historia nueva: no prometer rollback sin pérdida; restaurar respaldo consistente para preservar datos. No migrar la SQLite local durante definición o pruebas aisladas.

## Plan de implementación

1. Ampliar esquema, restricciones y migraciones; preparar datos operativos explícitos.
2. Implementar cola ponderada, rescate por espera, asignación compatible y pendientes durables con pruebas concurrentes.
3. Implementar ocupación, inicio/pausa, re-llamado, ausencia, retorno y jornada; integrar emisión del tótem.
4. Integrar cierre/entregas atómicos e idempotencia entre 03/05 y continuidad recuperable.
5. Incorporar panel, gestión de Q.F., formularios, historial, permisos y estados de error.
6. Validar migraciones, servicios, HTTP real, carga, navegador y accesibilidad; actualizar documentos con evidencia real y límites.

Primer paso ejecutable: esquema y migraciones probados en base temporal. Último: comprobación del flujo automático con varias ventanillas/tótem y registro de criterios/pendientes. Cada paso debe dejar la base ejecutable; las tareas y aprobación controlan qué se puede ejecutar.

## Plan de pruebas

Ejecutor Django y datos sintéticos. Nuevos tests propuestos en `turnosapp/tests/`: `test_cola.py`, `test_ventanillas.py`, `test_atencion.py`, `test_jornada.py`, `test_cierre.py`, `test_concurrencia_cola.py`, `test_panel.py`; ampliar `test_migraciones.py`, tests del tótem, entregas y navegación afectados. Verificar un solo `main`, etiquetas, estados y referencias accesibles; no confundir estructura HTML con auditoría integral.

Casos de algoritmo: P,P,C,G con colas abastecidas; distinto número de ventanillas; tipos restringidos/vacíos; cambio de pesos; varios turnos a 15 minutos; desempate; umbrales 11:59/12:00/14:59/15:00; retorno al final sin conservar antigüedad de rescate; ausencia de ventanilla compatible. Comprobar cursor persistente tras reinicio y que re-llamar no lo consume.

Concurrencia mínima con `TransactionTestCase`, hilos/barreras y conexiones reales: dos operadores ocupan la misma; varias ventanillas disputan el mismo turno/cursor; pausa/deshabilitación frente a selección; cierre doble frente a autoasignación; emisión frente a reincorporación; último cupo de receta entre 03/05; dos cierres con varias recetas y fallo intermedio. Afirmar invariantes, estados, eventos y contadores, no solo ausencia de excepción. Al menos tres escenarios de carga con número de hilos/iteraciones registrado.

Simular fallo después de confirmar cierre y antes del siguiente llamado; reiniciar procesador; volver a procesar evento/POST; demostrar una sola entrega por receta/atención y un solo llamado vigente. Validar error de auditoría en cada frontera. Probar revocación de actor, falta de perfil, rol ajeno, operación de otro turno/actor/payload, CSRF ausente y fechas controladas alrededor de medianoche.

Proponer `tools/verificar_spec_05_http.py` siguiendo 04: SQLite temporal, 670 pacientes sintéticos y WSGI loopback; abrir varias ventanillas, emitir, re-llamar, ausentar/retornar, confirmar seleccionadas, forzar fallo recuperable y cerrar jornada. Medir p95 por tipo de operación con ≥100 muestras y carga concurrente descrita, separando respuesta del cierre de recuperación del próximo llamado. No afirmar NS03 hasta integrar el 06.

Comandos previstos: `manage.py check`, `makemigrations --check --dry-run`, `test turnosapp recetasapp --noinput`, suite completa, herramienta HTTP y `git diff --check`; preparación/migraciones solo en entorno temporal. En navegador: Q.F./Técnico, teclado, zoom, móvil, estados automáticos, conflictos/recuperación y axe A/AA. Registrar si el host sigue indisponible, sin copiar evidencia de otro spec. Prueba de usabilidad con cinco usuarios y aceptación son comprobaciones separadas.

## Riesgos, alternativas y dependencias

- SQLite serializa escrituras: cola, entregas y emisión compiten; reintentar toda operación y conservar éxito anterior. No introducir dependencias externas solo para ocultar conflictos.
- El automático puede continuar con pestaña cerrada mientras siga activado: mostrar obligación de pausar y estado persistente. Revalidar operador antes de cada llamado; cuenta revocada no recibe nuevas asignaciones.
- La proporción puede diferir por rescate/compatibilidad; explicar la razón en el panel privado e historial, sin ofrecer una expectativa falsa de orden fijo por número.
- HU-17/18 y comunicación pública quedan fuera; guardar datos útiles no equivale a implementarlas.
- El servicio de entregas del 03 requiere refactor transaccional cuidadoso; probar compatibilidad y no perder entregas históricas ni sumar dos veces por pantallas distintas.
- Sin proceso de pendientes operativo no se demuestra recuperación autónoma tras un fallo; documentar arranque y prueba de reinicio. Una llamada en `on_commit` sola es insuficiente.

## Documentos afectados

En esta fase: cuatro documentos del 05 e índice. En implementación: `README.md`, `docs/estructura.md`, memoria del proyecto y contratos de 03/04 afectados por nuevas reglas, sin reescribir sus evidencias históricas ni cerrar sus pendientes visuales.

## Decisiones para implementar

Las respuestas funcionales y diseño forman parte del spec aprobado por el usuario. No se elige ni instala tecnología de WebSocket/voz. Los seis pasos fueron autorizados y completados técnicamente; revisión visual y aceptación pendientes según `validation.md`. Conservar `fdaza`, un único commit al finalizar y cambios ajenos del índice sin incluirlos en ese commit; ver acuerdo de ejecución del spec.
