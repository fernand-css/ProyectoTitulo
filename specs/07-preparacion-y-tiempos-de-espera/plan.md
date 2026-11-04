# Plan técnico — 07 / Preparación y tiempos de espera

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-03. Estado: implementación, verificación técnica y documentación completas. Revisión visual/usabilidad y aceptación pendientes.
Autorización de implementación: otorgada por el usuario el 2026-11-03.

## Inspección de la base

Revisados `CLAUDE.md`, el informe (HU-06, HU-17, HU-18, HU-20, HU-21), el índice de specs, las plantillas y los documentos del 05 y del 06. Del código real:

- `turnosapp/models.py`: `TurnoReceta` une un `Turno` con una `Receta` (restricción única por par). `Turno.Estado` incluye `esperando`, `llamado`, `atendido`, `ausente`, `cerrado_sin_entrega` y `sin_atencion_cierre`. `DetalleCierre` guarda por vínculo `entregada` y `entrega` (OneToOne a `recetasapp.EntregaReceta`), con motivo obligatorio si no se entregó.
- `recetasapp/models.py`: `EntregaReceta.turno_receta` es OneToOne anulable a `TurnoReceta`, así que un vínculo admite **una sola** entrega. `Receta` tiene la restricción `receta_contador_en_cupo` (`entregas_completadas <= max_entregas`).
- `recetasapp/services.py`: `_registrar_entrega_sin_reintento(...)` ya acepta `fecha=` y evalúa elegibilidad a esa fecha, pero (a) autoriza solo `TECNICO` y (b) exige que el turno del vínculo esté en `llamado` («La atención ya no está vigente»). `registrar_entrega` envuelve con `bloquear_cola(hoy)`, idempotencia por `OperacionAtencion` y reintentos.
- `turnosapp/services.py`: `_emitir` bloquea la cola del día, reserva el correlativo con UPDATE condicional, crea `Turno` y un `TurnoReceta` por receta elegible, audita y pide la selección. `ResultadoEmision` (número, fecha, creado_en, recuperado) alimenta `resultado.html` y `comprobante.html`.
- `turnosapp/atencion.py`: `ausente` cambia el turno a `ausente` y `reincorporar` lo devuelve a `esperando`. No hay hook de preparación y no hace falta uno para los pendientes, que se derivan.
- `turnosapp/cola.py`: `cerrar_esperas_anteriores` cierra como `sin_atencion_cierre` los turnos `esperando` de días anteriores.
- `turnosapp/panel.py` y `_estado.html` arman el panel del 05; su consulta periódica (`static/js/cola.js`) trae el HTML del estado.
- `recetasapp/views.py`: `FarmaciaView` con `roles_permitidos = (JEFA, TECNICO)`; `RecetasView` abre con el tablero; la plantilla base es `templates/recetas/base.html`. `recetas.css` y `tablero.css` no pueden declarar colores hexadecimales (lo impone un test).
- Migraciones actuales: `recetasapp/0003_entregareceta_turno_receta`, `turnosapp/0003_anuncio_sala`.
- Cambios locales ajenos a preservar: el árbol tiene cambios sin commitear de otras tareas. No incluirlos ni revertirlos.

## Diseño propuesto

Se extiende `recetasapp` con la preparación y se compone la estimación en `turnosapp`. No se crea una app nueva.

```text
Emisión (04)  ──► _emitir: Turno + TurnoReceta + PreparacionReceta (misma transacción)
                                │
Técnico / Q.F. ► Marcar «Lista» ┘  → UPDATE condicional; guarda intervalo de trabajo
                                │
Turno ausente / cierre / jornada ► Pendiente de retiro (derivado, sin tabla)
                                │
Personal ► Retiro ──► EntregaReceta del mismo vínculo (vigencia a la fecha de preparación)

Estimación = pendientes × promedio ÷ ventanillas en atención
   ├─ tótem: resultado.html y comprobante.html (al emitir o recuperar)
   └─ panel del 05 y sección Preparación (consulta periódica)
```

Responsabilidades:

- `recetasapp/preparacion.py` (nuevo): consultas puras y sin escritura. `por_preparar`, `pendientes_retiro`, `promedio_preparacion`, constantes de parámetros.
- `recetasapp/services.py`: `marcar_lista`, `deshacer_lista`, `retirar_preparado`, y un camino acotado en `_registrar_entrega_sin_reintento` para el retiro.
- `turnosapp/espera.py` (nuevo): `estimar_espera()` compone la cola de preparación, el promedio y las ventanillas en atención, y devuelve minutos y frase. Vive en `turnosapp` porque conoce las ventanillas; `recetasapp` no importa `turnosapp` en el nivel de módulo (ya lo hace de forma perezosa).
- `turnosapp/services.py`: `_emitir` crea las preparaciones y `ResultadoEmision` incorpora la estimación.

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-07-01 | `recetasapp/models.py` (nuevo `PreparacionReceta`); `turnosapp/services.py` (`_emitir`); migración `recetasapp/0004_*` | Una preparación por `TurnoReceta` dentro de la transacción de emisión | `test_preparacion_modelos.py`, `test_emision_preparacion.py`; concurrencia de emisión |
| RF-07-02 | `recetasapp/services.py` (`marcar_lista`) | UPDATE condicional sobre `lista_en IS NULL`, intervalo de trabajo, auditoría | `test_preparacion_servicios.py`; concurrencia de marca |
| RF-07-03 | `recetasapp/services.py` (`deshacer_lista`) | UPDATE condicional inverso, solo con turno activo y sin entrega | `test_preparacion_servicios.py` |
| RF-07-04 | `recetasapp/views.py`, `urls.py`, `forms.py`; `templates/recetas/preparacion_*.html`; `static/css/preparacion.css` | Sección con pestañas y consulta periódica | `test_preparacion_vistas.py`; revisión visual |
| RF-07-05 | `recetasapp/preparacion.py` (`pendientes_retiro`); vista y plantilla de pendientes | Consulta derivada con búsqueda por RUT o apellido | `test_preparacion_consultas.py` |
| RF-07-06 | `recetasapp/services.py` (`retirar_preparado`, camino de retiro en `_registrar_entrega_sin_reintento`) | Entrega del vínculo original, vigencia a la fecha de preparación, cupo duro | `test_retiro.py`; concurrencia de retiro |
| RF-07-07 | `recetasapp/preparacion.py` (`promedio_preparacion`); `PreparacionReceta.duracion_segundos` | Promedio de 14 días, tope de 30 min, mínimo de 5 muestras | `test_preparacion_promedio.py` |
| RF-07-08 | `turnosapp/espera.py` | Fórmula, redondeo de 5 min y casos sin estimar | `test_espera.py` |
| RF-07-09 | `turnosapp/services.py` (`ResultadoEmision`), `templates/turnos/resultado.html`, `comprobante.html`, `static/js/impresion*` solo si la frase cambia el diseño del papel | Frase de espera en pantalla y papel | pruebas de vista y de privacidad; `impresion.test.cjs` si aplica |
| RF-07-10 | `turnosapp/panel.py`, `templates/turnos/_estado.html` | Línea de carga y estimación; enlace a la sección | `test_panel.py` (5 casos nuevos) |
| RF-07-11 | `recetasapp/views.py` (mixin de roles ampliado a Q.F. y Técnico), auditoría | Matriz, CSRF, `no-store`, auditoría sin datos personales | `test_preparacion_permisos.py` |
| RF-07-12 | `turnosapp/atencion.py` (`reincorporar`), pruebas de concurrencia | Rechazar reincorporar si todas las recetas ya se retiraron; ≥3 escenarios de hilos | `test_concurrencia_preparacion.py`; suites del 03–06 sin cambios |

## Datos y contratos

### `PreparacionReceta` (nuevo, `recetasapp`, hereda `ModeloAuditado`)

| Campo | Tipo | Regla |
|---|---|---|
| `turno_receta` | OneToOne a `turnosapp.TurnoReceta`, `PROTECT`, `related_name="preparacion"` | Una por vínculo. |
| `recibida_en` | DateTime | Instante de emisión del turno. |
| `lista_en` | DateTime, nulo | Marca «Lista». |
| `lista_por` | FK a usuario, nulo, `PROTECT` | Quien marcó. |
| `inicio_medido` | DateTime, nulo | Inicio del intervalo de trabajo (RF-07-07). |
| `duracion_segundos` | PositiveInteger, nulo | `lista_en − inicio_medido`. |

Restricciones: `lista_en`, `lista_por`, `inicio_medido` y `duracion_segundos` quedan todos nulos o todos con valor; `inicio_medido <= lista_en`; `duracion_segundos >= 0`. Índices en `lista_en` (promedio) y `recibida_en`. No se guarda estado ni «pendiente»: se derivan (spec, «Datos y reglas»).

No se agrega ninguna tabla para el retiro: reutiliza `EntregaReceta` con el `turno_receta` original y la restricción OneToOne existente impide dos entregas por vínculo.

### Servicios (`recetasapp/services.py`)

- `marcar_lista(actor, preparacion_id)`: `autorizar(actor, JEFA, TECNICO)`; transacción con `bloquear_cola(hoy)` para ordenarse con las operaciones del 05; comprueba turno activo y de hoy; calcula `inicio_medido = max(recibida_en, última lista_en del mismo actor hoy)` y hace `PreparacionReceta.objects.filter(pk=…, lista_en__isnull=True).update(...)`. Si no cambia ninguna fila y ya está lista, devuelve el resultado original; si el turno dejó de estar activo, rechaza.
- `deshacer_lista(actor, preparacion_id)`: UPDATE condicional inverso con `turno__estado` en `esperando` o `llamado` y sin `EntregaReceta`. **Cuidado PostgreSQL:** un filtro que cruza relaciones en un UPDATE se traduce a subconsulta y no se reevalúa tras esperar un bloqueo (regla del proyecto). Por eso la condición cruzada (estado del turno y entrega) se verifica dentro de la transacción protegida por `bloquear_cola`, y el UPDATE condicional solo filtra sobre campos propios (`lista_en__isnull=False`).
- `retirar_preparado(actor, preparacion_id, operacion_id)`: `autorizar(actor, JEFA, TECNICO)`; idempotencia por `operacion_id` igual que `registrar_entrega`; exige preparación lista, sin entrega y turno en estado pendiente de retiro; delega en `_registrar_entrega_sin_reintento` con un camino acotado.
- **Camino acotado en `_registrar_entrega_sin_reintento`:** un parámetro nuevo (por ejemplo `desde_preparado=<preparación>`) que (1) usa `fecha = fecha local de lista_en`, (2) acepta un vínculo cuyo turno está cerrado en vez de exigir `llamado`, (3) permite también el rol `JEFA`. El resto del flujo (UPDATE condicional del contador con `entregas_completadas__lt=F("max_entregas")`, restricción única, `ConflictoOperacion`) no cambia. El camino actual del 05 queda idéntico y solo para `TECNICO`.

### Consultas (`recetasapp/preparacion.py`, sin escritura)

- `por_preparar(hoy)`: preparaciones de turnos `esperando` o `llamado` de hoy, ordenadas por `entrada_cola` y turno.
- `pendientes_retiro(buscar=None)`: derivada, con `select_related`; búsqueda por RUT normalizado con `normalizar_rut` de `coreapp` (con o sin puntos) o por apellido sin distinguir mayúsculas ni tildes, siguiendo el patrón del padrón del 03.
- `promedio_preparacion(ahora)`: una agregación sobre `duracion_segundos` con `lista_en >= ahora − 14 días` y `duracion_segundos <= 1800`, devuelve `(segundos, muestras)`; con menos de 5 muestras devuelve el valor por defecto y su origen.

### Estimación (`turnosapp/espera.py`)

`estimar_espera(ahora=None)` devuelve un objeto con `minutos`, `frase`, `pendientes`, `ventanillas`, `promedio` y `muestras`. `ventanillas` cuenta las `Ventanilla` habilitadas, no retiradas, con operador, `automatico=True` y `fecha_activacion` de hoy. Redondeo: `ceil(minutos / 5) * 5`. Frases:

| Caso | Frase |
|---|---|
| 0 ventanillas | «No podemos estimar el tiempo de espera. Consulta con el personal.» |
| resultado < 5 min | «Tiempo aproximado de espera: menos de 5 minutos.» |
| resultado ≥ 5 min | «Tiempo aproximado de espera: unos N minutos.» |

La frase sale de una única función y se reutiliza en pantalla, papel y panel para que no diverjan.

### Rutas y vistas (`recetasapp`)

| Ruta | Método | Resumen |
|---|---|---|
| `/recetas/preparacion/` | GET | «Por preparar», con consulta periódica. |
| `/recetas/preparacion/pendientes/` | GET | «Pendientes de retiro» con búsqueda. |
| `/recetas/preparacion/<pk>/lista/` | POST | Marcar «Lista». |
| `/recetas/preparacion/<pk>/deshacer/` | POST | Corregir la marca. |
| `/recetas/preparacion/<pk>/retirar/` | POST | Registrar el retiro. |

`roles_permitidos = (JEFA, TECNICO)` (el mixin ya admite superusuario). Todas las respuestas llevan `Cache-Control: no-store`; los POST exigen CSRF y llevan un `operacion_id` generado al renderizar. Los identificadores en URL son los de la preparación, nunca RUT ni nombres.

### Interfaz

- Se reutiliza `templates/recetas/base.html` y la identidad «libreta de control». La banda de Recetas gana el enlace «Preparación»; dentro, las pestañas «Por preparar» y «Pendientes de retiro» con contador. No se toca `navbar.html`.
- `static/css/preparacion.css` (nuevo) respeta la regla de no declarar hexadecimales y usa los tokens de `recetas.css`. Estados con texto («Lista a las 10:42 por …», «Pendiente desde el 02/11 · 1 día»), nunca solo color.
- Wireframe de «Por preparar»:

```text
Recetas › Preparación      [ Por preparar (6) ] [ Pendientes de retiro (2) ]
Espera aproximada hoy: unos 15 minutos · 6 recetas por preparar · promedio 4 min (12 muestras)

 N° 41  Preferencial · espera 08:12
   RC-0123 · entrega 2 de 6        [ Marcar lista ]
   RC-0456 · entrega 1 de 3        Lista 10:42 · Técnico …   [ Corregir ]
 N° 42  General · espera 03:40
   RC-0789 · entrega 4 de 6        [ Marcar lista ]
```

- «Pendientes de retiro» muestra una tabla accesible (paciente, receta, turno de origen, motivo, preparada el, días) y el botón «Registrar retiro» por fila. En móvil cada fila pasa a tarjeta.
- Panel del 05: una línea compacta («6 recetas por preparar · unos 15 minutos») dentro de `_estado.html`, con el mismo `no-store`.
- Tótem: la frase aparece bajo el número de turno en `resultado.html` y en `comprobante.html`, en el mismo bloque de texto; no se añade lógica de JavaScript.

## Permisos e interfaz

La matriz del spec se aplica en servidor con `RolRequeridoMixin`; el enlace «Preparación» solo aparece para Técnico, Q.F. y superusuario. Cuenta inactiva o sin perfil se rechaza en servidor, no solo por ocultar el enlace. El tótem y el comprobante solo reciben la frase de estimación; la prueba de privacidad recorre cada salida pública con un paciente sintético y busca RUT, nombres, categoría y códigos de receta.

## Migraciones y reversión

- `recetasapp/0004_preparacionreceta`: crea la tabla con sus restricciones e índices. Sin datos iniciales y sin relleno: los turnos activos al aplicarla no tendrán preparación (se documenta; conviene aplicarla fuera de horario de atención).
- La migración depende de `turnosapp/0003_anuncio_sala` para resolver la clave foránea a `TurnoReceta`.
- Reversión: elimina la tabla y con ella los tiempos medidos; se recomienda respaldo antes de retroceder. La entrega registrada por un retiro no se pierde porque vive en `EntregaReceta`.
- No se ejecuta nada en esta fase. La base del proyecto no se migra sin aprobación; las pruebas usan la base desechable de Django y las herramientas usan SQLite temporal.

## Plan de pruebas

Pruebas de Django con el ejecutor de Django (sin `pytest-django`):

- **Modelo y emisión:** una preparación por vínculo; restricciones de coherencia; emisión crea N preparaciones; falla forzada revierte turno y número; recuperación idempotente.
- **Servicios:** marcar, repetir, marcar turno ausente o de otra jornada, corregir, corregir ya entregada; intervalo de trabajo con dos marcas seguidas del mismo usuario y de usuarios distintos; auditoría sin datos personales y rollback si falla.
- **Promedio:** 4 y 5 muestras, tope de 30 min, ventana de 14 días (límites de 13, 14 y 15), sin datos.
- **Estimación:** casos de la tabla de criterios; redondeo; sin ventanillas; cola vacía; frase única reutilizada.
- **Pendientes y retiro:** los tres cierres; reincorporación; búsqueda por RUT y apellido; retiro vigente a la fecha de preparación y vencido hoy; cupo agotado; repetición del POST; actor Q.F.; rechazo del Encargado.
- **Integración con 03/05:** la confirmación del 03 y el cierre del 05 siguen idénticos; reincorporar con todo retirado se rechaza; `DetalleCierre` no cambia.
- **Concurrencia** (`TransactionTestCase`, hilos y conexiones separadas, al menos tres escenarios): (1) emisión simultánea de varios turnos sin preparaciones duplicadas ni correlativos repetidos; (2) dos marcas «Lista» de la misma preparación; (3) dos retiros de la misma preparación; (4) retiro frente a una entrega del 03 sobre la última entrega de la receta; (5) retiro frente a reincorporación.
- **Vistas y privacidad:** matriz de roles contra cada URL, CSRF, `no-store`, y ninguna salida pública con datos personales.
- **JavaScript:** si se agrega consulta periódica nueva, pruebas Node con DOM simulado como `cola.test.cjs`; si se reutiliza `cola.js`, las existentes.
- **Herramienta HTTP:** `tools/verificar_spec_07_http.py` con SQLite temporal y 670 pacientes sintéticos: emisión, marca, ausente, retiro, estimación en tótem y panel, y p95 de 2 s o menos.
- **Navegador:** revisión visual (escritorio y móvil), axe, teclado y papel quedan pendientes salvo que el host las permita; no se declaran sin evidencia.

## Riesgos, alternativas y dependencias

- **Vigencia a la fecha de preparación (decisión del usuario).** Toca el servicio de entregas del 03, que tiene pruebas concurrentes. Mitigación: camino acotado y aditivo; las pruebas del 03 pasan sin cambios. Riesgo residual: una receta vencida puede entregarse con la fecha de preparación; queda trazado por el actor y la fecha real.
- **La Q.F. registra entregas (decisión del usuario).** Cambia quién puede ser responsable de una entrega. Mitigación: limitarlo al camino de retiro y conservar actor y fecha reales.
- **Retiro frente a reincorporación.** Si el ausente se reincorpora justo antes de un retiro, el turno volvería a la cola con una receta ya entregada. Mitigación: ambas operaciones usan `bloquear_cola`, el retiro exige turno en estado pendiente y reincorporar rechaza si todas las recetas están retiradas. El 05 ya ignora entregas existentes al finalizar (`asociada`).
- **Estimación imprecisa con pocos datos.** Con menos de 5 muestras usa 5 min por receta; se rotula «aproximado». No se afirma una reducción real de la espera (el informe lo excluye de la validación académica).
- **Promedio con intervalos largos** (almuerzo, interrupciones): el tope de 30 min los descarta y los conserva para análisis.
- **Turnos activos al migrar** sin preparación. Documentado; no se rellena para no inventar tiempos.
- **PostgreSQL:** los UPDATE condicionales no filtran cruzando tablas (ver servicios). Se revisan los marcadores de bloqueo de `reintentar_conflictos` frente a PostgreSQL, como ya advierte CLAUDE.md.
- **Dependencias:** no se agregan paquetes.

## Documentos afectados

Al implementar: `README.md`, `docs/estructura.md` y `CLAUDE.md` (sección de la sala o de recetas) para describir la preparación, las rutas y los límites; `specs/README.md` para el estado. `specs/05-.../spec.md` conserva sus exclusiones históricas; la nota de cambio vive en el 07. Hoy solo se guardan los cuatro documentos y el índice.

## Decisiones para implementar

Ninguna bloqueante. A confirmar en la revisión: el cálculo del intervalo de trabajo, los parámetros iniciales y que el panel del Técnico sea el `/turnos/panel/` del 05. Esta fase termina antes del código.
