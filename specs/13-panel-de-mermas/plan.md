# Plan técnico — 13 / Panel de mermas

Spec: [spec.md](spec.md). Estado: ejecutado; implementación técnica completa (commit `aa08f74`).
Autorización de implementación: otorgada por la usuaria el 2026-11-17 («pasa la spec 13 a aprobado e implementa»), en `fdaza`.

## Inspección de la base

Leídos el 2026-11-17:

- `recetasapp/preparacion.py`: `pendientes_retiro(buscar)` filtra preparaciones listas, sin `turno_receta__entrega` y con turno en los cuatro estados de cierre. Es la base de RF-13-01.
- `recetasapp/services.py`: `retirar_preparado` y `_registrar_entrega_sin_reintento(..., desde_preparado=, desde_despacho=)`; con `desde_despacho=None` rechaza recetas en despacho abierto (`recetas_con_despacho_abierto`).
- `recetasapp/graficos.py` y `static/js/graficos.js`: gráficos SVG sin librerías, con tabla de datos y ayuda por foco.
- `entregasapp/services.py`: `recetas_para_despacho` y `recetas_para_despacho_lote` excluyen las recetas en turno activo y las de `pendientes_retiro`; `programar_entrega` (autoriza `JEFA`, `_bloquear_jornada`, `EntregaAbiertaExistente`); `inscribir_excepcion`; `registrar_entregada` evalúa vigencia «hoy» y llama con `turno_receta_id=None`; `anular_entrega`.
- `entregasapp/models.py`: `RecetaEntrega` (entrega, receta, resultado, `entrega_receta`), `InscripcionReparto.Motivo`, `Entrega.Estado`.
- `coreapp/roles.py` (`JEFA`, `TECNICO`, `ENCARGADO`, `ROLES_INTERNOS`, `ETIQUETAS_ROLES`), `coreapp/mixins.py` (`RolRequeridoMixin`), `coreapp/navegacion.py` (`Entrada`).
- `usuariosapp/services.py` (`crear_roles`, cuentas demo, `cuentas_gestionables`) y los comandos `crear_roles` y `crear_usuarios_demo`. Los grupos se crean por comando, no por migración.
- `indicadoresapp`: esqueleto con `urlpatterns = []` y sin modelos.

## Diseño propuesto

`indicadoresapp` se llena con lectura pura; la única escritura nueva (la derivación) vive en `entregasapp/services.py`, dueño de la programación.

| Archivo | Responsabilidad |
|---|---|
| `indicadoresapp/mermas.py` (nuevo) | Consulta de RF-13-01 con anotación del estado (`Case`/`When` sobre `turno_receta__entrega`, su `recetaentrega` y `RecetaEntrega` abierta), filtros, cifras, series por día/semana y detalle por paciente. Sin escritura. |
| `indicadoresapp/filtros.py` (nuevo) | Formulario GET del rango y el tipo, atajos y validación de RF-13-02. |
| `indicadoresapp/reportes.py` (nuevo) | Excel con `openpyxl.chart` y PDF con `reportlab.graphics.charts`; recibe solo cifras agregadas (sin objetos `Paciente`), lo que hace imposible filtrar datos personales por descuido. |
| `indicadoresapp/views.py`, `urls.py` | `PanelMermasView`, `ReporteMermasView` (formato `xlsx`/`pdf`) y `DerivarMermaView` (GET formulario, POST). |
| `templates/indicadores/mermas.html`, `_derivar.html` | Panel con la base privada; gráficos con la geometría de `recetasapp/graficos.py`. |
| `static/css/indicadores.css` | Estilos con las variables de `base.css`. |
| `entregasapp/services.py` | `derivar_desde_merma(actor, paciente_id, fecha, encargado_id, motivo, nota, operacion_id)`; `recetas_para_despacho(..., con_preparadas=False)`; rama de preparadas en `registrar_entregada` y `anular_entrega`. |
| `entregasapp/models.py` | `RecetaEntrega.preparacion` (FK opcional a `PreparacionReceta`, `PROTECT`). |
| `recetasapp/preparacion.py` | `pendientes_retiro` anota `en_despacho`; la plantilla de pendientes muestra «En despacho». |
| `coreapp/roles.py`, `navegacion.py`, `iconos.html` | Rol `DIRECTOR`, entrada «Mermas» e ícono. |
| `usuariosapp/services.py` y comandos | `crear_roles` crea el cuarto grupo; `demo_director`; administración solo por superusuario. |

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-13-01 | `indicadoresapp/mermas.py` (nuevo) | Consulta y cuatro estados | Pruebas por estado y por cierre |
| RF-13-02 | `indicadoresapp/filtros.py` (nuevo) | Validación y atajos | Pruebas de límites (366 días, futuro, invertido) |
| RF-13-03 | `mermas.py`, `templates/indicadores/mermas.html` | Cifras y cuatro gráficos con tabla | Pruebas de serie día/semana y período vacío |
| RF-13-04 | `mermas.py`, plantilla | Detalle paginado, botón solo Q.F. | Pruebas por rol |
| RF-13-05 | `indicadoresapp/reportes.py` (nuevo), vista | Excel y PDF sin datos personales | Abrir archivos y buscar RUT/nombres sintéticos; auditoría |
| RF-13-06 | `entregasapp/services.py`, `DerivarMermaView` | Excepción + entrega atómicas | Pruebas normal, no elegible, abierta, sin recetas, idempotencia |
| RF-13-07 | `entregasapp/models.py`, `services.py`, `recetasapp/preparacion.py` | Vínculo, vigencia a fecha de preparación, anulación | Pruebas de entregada, vencida, anulada y ventanilla |
| RF-13-08 | `coreapp/roles.py`, `usuariosapp/*`, `coreapp/views.py` (inicio) | Cuarto rol, inicio con panel, 403 en el resto | Pruebas de acceso por URL |
| RF-13-09 | `coreapp/navegacion.py`, `iconos.html` | Entrada «Mermas» | Pruebas de menú por rol |
| RF-13-10 | `entregasapp/services.py`, pruebas | `bloquear_cola`, restricción de preparación | Tres escenarios con `TransactionTestCase` |

## Datos y contratos

- **`RecetaEntrega.preparacion`**: `ForeignKey("recetasapp.PreparacionReceta", null=True, blank=True, on_delete=PROTECT, related_name="despachos")`. Sin restricción nueva: una preparación no puede quedar en dos despachos abiertos porque cada paciente tiene a lo más una entrega abierta (`entrega_abierta_unica`); ver la nota de implementación en la spec.
- **Estado de una preparación** (anotación en `mermas.py`):
  - entregada con `EntregaReceta` ligada a una `RecetaEntrega` → «Entregada por despacho»;
  - entregada sin despacho → «Retirada tarde en farmacia» (las entregadas dentro de la misma atención no entran: su turno quedó «atendido» con `DetalleCierre.entregada=True` y la preparación ya no es pendiente; la consulta las excluye por `turno_receta__detalle_cierre__entregada=True`);
  - sin entrega y con `RecetaEntrega` pendiente de una entrega abierta → «En despacho»;
  - resto → «Sin retirar».
- **`derivar_desde_merma`**: `@reintentar_conflictos` + `transaction.atomic()`; `autorizar(actor, JEFA)`; `_bloquear_jornada(hoy)`; idempotencia por `operacion_id` igual que `programar_entrega`; si no es elegible y hay motivo, crea la `InscripcionReparto` dentro de la misma transacción (la lógica de `inscribir_excepcion` se extrae a una función interna sin su propia transacción); recetas = `recetas_para_despacho(paciente, fecha, con_preparadas=True)` y las preparaciones «Sin retirar» del paciente; `RecetaEntrega` con `preparacion` para las preparadas.
- **`registrar_entregada`**: para un vínculo con `preparacion`, evalúa `evaluar_elegibilidad(receta, fecha_preparacion)` y llama a `_registrar_entrega_sin_reintento(..., turno_receta_id=preparacion.turno_receta_id, fecha=fecha_preparacion, desde_preparado=preparacion, desde_despacho=vinculo)`, ajustando su validación para aceptar ambos orígenes juntos.
- **Formularios**: filtros por GET (`desde`, `hasta`, `tipo`, `pagina`); derivación por POST con CSRF, `operacion_id` UUID oculto y el paciente firmado con `signing` (como la revisión del lote del 08).
- **Reportes**: `HttpResponse` con `Content-Disposition: attachment`, `Cache-Control: no-store`; auditoría `auditar(actor, "mermas.reporte", None, ...)` con formato, rango y tipo.

## Permisos e interfaz

- `PanelMermasView` y `ReporteMermasView`: `RolRequeridoMixin` con `JEFA`, `DIRECTOR` y superusuario. `DerivarMermaView`: solo `JEFA` y superusuario.
- El Director entra a `/` y ve el panel (misma técnica que «Mis entregas» del encargado, sin redirigir). Las demás vistas privadas ya exigen sus roles, así que responden 403 sin cambios; se agregan pruebas que lo confirman.
- Menú: `Entrada("mermas", "Mermas", "indicadoresapp:mermas", "i-grafico", grupo="Equipo", roles=(JEFA, DIRECTOR))`.
- Mensajes en español de Chile; el formulario de derivar en un `<dialog>` con página sin JavaScript de respaldo, como las fotos del 08.

## Migraciones y reversión

- `entregasapp/0003_recetaentrega_preparacion`: campo nulo y restricción parcial; reversible sin pérdida (las filas antiguas tienen `NULL`).
- Sin migración para el rol: `crear_roles` lo crea de forma idempotente. En una base existente hay que ejecutar `python manage.py crear_roles`.
- No se migra la base local del proyecto sin instrucción del equipo.

## Plan de pruebas

- `indicadoresapp/tests/`: consulta y estados, filtros, gráficos, detalle, reportes (abrir el `.xlsx` con openpyxl y el PDF con el texto extraído; buscar los RUT y nombres de los pacientes de la prueba), permisos y menú.
- `entregasapp/tests/`: derivación (normal, no elegible con y sin motivo, abierta, sin recetas, idempotencia), entregada con vigencia a la fecha de preparación, no descontada, anulación, ventanilla rechazada.
- `usuariosapp/tests/`: cuarto rol, inicio de sesión, administración solo por superusuario, Q.F. sin acceso.
- Concurrencia (`TransactionTestCase`, hilos): las tres situaciones de RNF-02 de la spec.
- Regresión completa (`python manage.py test`) y `makemigrations --check --dry-run`.
- `tools/verificar_spec_13_http.py`: SQLite temporal aislada, 670 pacientes sintéticos, 90 días de preparaciones sintéticas, p95 del panel y de los dos reportes.

## Riesgos, alternativas y dependencias

- **Consulta pesada con rangos largos.** Mitigación: índice existente en `lista_en`, agregación en la base y paginación del detalle; medir con 366 días.
- **Cambio en el núcleo de entregas del 08.** `registrar_entregada` y `_registrar_entrega_sin_reintento` tienen pruebas concurrentes; el cambio se limita a la rama con `preparacion` y se corre toda la regresión del 07 y el 08.
- **PostgreSQL y UPDATE condicional entre tablas** (aviso de CLAUDE.md): no filtrar con `rel__campo=` en los UPDATE nuevos; usar la restricción parcial.
- **Fuga de datos personales en reportes.** Mitigación de diseño: `reportes.py` solo recibe cifras; prueba que busca los datos sintéticos en el archivo.
- Sin paquetes nuevos: openpyxl y ReportLab ya están en `requirements.txt`.

## Documentos afectados

- `specs/README.md` (índice), al crear y al cambiar de estado.
- `specs/08-domicilios-y-entregas/spec.md`: anotar que la derivación del 13 incluye recetas preparadas y su vigencia a la fecha de preparación.
- `specs/02-autenticacion-roles-auditoria/spec.md`: anotar el cuarto rol.
- `CLAUDE.md` y `docs/estructura.md` al implementar.

## Decisiones para implementar

Ninguna funcional pendiente; los supuestos de la spec se confirman al aprobarla.

## Enmienda del 2026-11-25

Diseño de la [enmienda del 2026-11-25](spec.md#enmienda-del-2026-11-25--dashboard-de-mermas-y-entregas-borrador) (RF-13-11 a RF-13-22), con la [segunda enmienda del 05](../05-cola-ponderada-y-llamado/spec.md#segunda-enmienda-del-2026-11-25--causa-de-no-entrega-borrador) (RF-05-14) y la [enmienda del 07](../07-preparacion-y-tiempos-de-espera/spec.md#enmienda-del-2026-11-25--derivar-desde-pendientes-de-retiro-borrador) (RF-07-13). Estado: **aprobado el 2026-11-25** («pasa las enmiendas a aprobado e implementa»); implementación autorizada.

### Inspección de la base

Leídos el 2026-11-25 en `crojas-base`:

- `indicadoresapp/mermas.py`: `preparaciones(periodo)` anota `entregada`, `por_despacho` y `en_despacho`; `resumir` agrega en Python por fecha local (serie, estados, crónico/general, cierres, estante, día de la semana) y arma el detalle por paciente; `pacientes_de_la_pagina` solo lo usa el panel.
- `indicadoresapp/filtros.py`: `FiltroMermasForm` (`desde`, `hasta`, `tipo`, `pagina`) y `atajos`.
- `indicadoresapp/entregas.py`: `EntregaReceta` por fecha de confirmación, por día con promedio de 7 días o por semana.
- `indicadoresapp/graficos.py`: blíster, calendario, barras y división; `recetasapp/graficos.py`: `columnas` (geometría SVG) y `promedio_movil`.
- `indicadoresapp/reportes.py`: `DatosReporte` agregado, Excel con openpyxl y PDF con ReportLab.
- `indicadoresapp/views.py`: `PanelMermasView`, `ReporteMermasView` (`mermas/reporte.<formato>`) y `DerivarMermaView`, cuyo «Volver» lleva al panel.
- `turnosapp/models.py`: `CierreAtencion` (`resultado`, `motivo` de 500) y `DetalleCierre` (`entregada`, `motivo`, `entrega`), con las restricciones `cierre_sin_entrega_motivo` y `detalle_cierre_entrega_coherente`; última migración `0013_evento_numero_anterior`. `Turno` hereda `creado_en` de `ModeloAuditado` (hora de emisión).
- `turnosapp/forms.py`: `FinalizarForm` con `motivo` general y `motivo_<receta>` de texto. `turnosapp/atencion.py`: `finalizar_atencion(actor, turno_id, operacion_id, *, recetas_entregadas, motivo="", motivos=None)` copia el motivo propio o el general a cada `DetalleCierre`.
- `recetasapp/views.py`: `PendientesRetiroView` (`recetasapp:preparacion_pendientes`) con búsqueda en vivo y parcial `_pendientes_resultados.html`.
- `entregasapp/models.py`: `IntentoEntrega` (`resultado`, `motivo` con seis opciones, `registrado_en`) y `RecetaEntrega` (`resultado` pendiente, descontada o no descontada; `preparacion`).

### Diseño propuesto

| Archivo | Cambio |
|---|---|
| `turnosapp/models.py` y `migrations/0014_causa_no_entrega.py` | `CausaNoEntrega` (TextChoices: `sin_stock`, `no_la_pide`, `no_vigente`, `cambio_indicacion`, `otro`) y el campo opcional `causa` (`max_length=20`, `blank=True`, `default=""`) en `CierreAtencion` y `DetalleCierre`. Sin tocar las restricciones. |
| `turnosapp/forms.py`, `turnosapp/atencion.py`, `templates/turnos/finalizar.html` | `causa` general y `causa_<receta>` como listas, y `detalle` de hasta 200 caracteres exigido con «Otro». `finalizar_atencion(..., causa="", causas=None)` guarda el código y arma un `motivo` legible («Sin stock», «Otro: …»); sin causa, el texto recibido se guarda como «Otro» (compatibilidad). |
| `indicadoresapp/periodos.py` (nuevo; reemplaza `filtros.py`) | `Periodo` con `clase` (`1d`, `3d`, `7d`, `14d`, `mes`, `semestre`, `anio`, `personalizado`), `anterior_equivalente()`, `anterior()` y `siguiente()` para las flechas, `granularidad` (día, semana o mes) y `titulo`; formulario GET `FiltroPanelForm` (`periodo`, `ref` con la fecha de inicio de Mes, Semestre o Año, `desde`, `hasta`, `tipo`) que acepta los enlaces antiguos con `desde` y `hasta`. |
| `indicadoresapp/mermas.py` | Conserva `preparaciones` y RF-13-01. `resumir` deja de armar el detalle por paciente, suma «más de 14 días» y la barra de lo preparado (preparaciones listas del período cuyo turno cerró, incluidas las entregadas en la atención) y agrupa la serie por la granularidad del período. Se retira `pacientes_de_la_pagina`. |
| `indicadoresapp/canales.py` (nuevo; absorbe `entregas.py`) | Tabla por canal (RF-13-14), entregas por día (RF-13-17) y motivos (RF-13-16). Lectura pura, agregada en Python por fecha local, con el filtro de tipo. |
| `indicadoresapp/ausentes.py` (nuevo) | Grilla día × hora de RF-13-19 desde `Turno.creado_en` y el estado actual del turno. |
| `indicadoresapp/tablero.py` (nuevo) | `armar(periodo, hoy)` devuelve un `Tablero` (dataclass solo con cifras) con todo el panel y la comparación con el período anterior. La vista y los reportes lo usan, así que los reportes siguen sin recibir objetos de pacientes. |
| `indicadoresapp/graficos.py` | Conserva calendario, barras y división; suma columnas por mes, columnas apiladas, barra al 100 % con textura y grilla de calor. Se retira el blíster. |
| `indicadoresapp/reportes.py` | `excel(tablero)` con hojas «Resumen», «Por día» y «Ausentes por hora»; `csv_por_dia(tablero)` nuevo; `pdf(tablero)` con las secciones de RF-13-21. |
| `indicadoresapp/views.py`, `urls.py` | `PanelMermasView` con `periodos` y `tablero`; `ReporteMermasView` acepta `csv` (`text/csv; charset=utf-8`); `DerivarMermaView` con «Volver» a `recetasapp:preparacion_pendientes`. Rutas sin cambios. |
| `templates/indicadores/mermas.html` (y parciales `_cifras.html`, `_canales.html`, `_motivos.html`, `_ausentes.html`) | Dashboard de RF-13-20, sin RUT ni nombres. |
| `static/css/indicadores.css`, `static/css/base.css`, `static/css/tema_oscuro.css` | Grilla de tarjetas, botones de período, celdas de calor y texturas; colores nuevos en las dos paletas. |
| `recetasapp/views.py`, `templates/recetas/_pendientes_resultados.html` | `puede_derivar` (Q.F. o superusuario) y enlace «Derivar a domicilio» en las filas «Sin retirar» (RF-07-13). |
| `indicadoresapp/management/commands/generar_mermas_demo.py` | Causas de no entrega y turnos ausentes con hora de emisión repartida en la jornada (UPDATE de `creado_en` después de crear, porque es `auto_now_add`). |
| `tools/verificar_spec_13_http.py` | 366 días sintéticos con visitas a domicilio registradas; mide el panel por período y las tres descargas. |

### Reglas de cálculo

- **Farmacia (RF-13-14):** `TurnoReceta` de turnos con `fecha` en el período y estado de cierre. Entregada en la atención: `detalle_cierre__entregada=True`. «Retiradas después»: sin entrega en la atención y con `EntregaReceta` ligada a la preparación, sin `RecetaEntrega` descontada. Se suman a las entregadas las `EntregaReceta` sin `turno_receta` y sin despacho, por fecha local de `creado_en`. Los turnos activos se cuentan aparte para la nota.
- **Domicilio (RF-13-14):** `RecetaEntrega` de `IntentoEntrega` con `registrado_en` en el período y resultado `entregada` o `no_entregada`. Entregada: intento entregado y receta `descontada`. No entregada: intento no entregado (todas sus recetas) o receta `no_descontada`.
- **Motivos (RF-13-16):** farmacia, por receta no entregada: turno `ausente` → «Paciente ausente»; `sin_atencion_cierre` → «Sin atención al cierre»; si no, `DetalleCierre.causa` (vacía → «Otro»). Domicilio, por intento `no_entregada`: `IntentoEntrega.motivo`.
- **Entregas por día (RF-13-17):** farmacia por fecha local de `EntregaReceta.creado_en` (sin las del reparto), separando las que vienen de un retiro posterior; domicilio por fecha local de `registrado_en`.
- **Ausentes (RF-13-19):** `Turno` con `fecha` en el período, por `weekday()` y hora local de `creado_en`; ausente = `estado="ausente"` al consultar.
- **Comparación (RF-13-12):** un segundo `Tablero` reducido (solo cifras clave) con `periodo.anterior_equivalente()`.

### Columnas del CSV

Una fila por día, en este orden, con encabezados sin tildes para que sirvan de nombre de columna:

`fecha;farmacia_entregadas_atencion_o_ficha;farmacia_retiradas_despues;farmacia_no_entregadas;domicilio_entregadas;domicilio_no_entregadas;merma;turnos_emitidos;turnos_ausentes;farmacia_paciente_ausente;farmacia_sin_atencion_al_cierre;farmacia_sin_stock;farmacia_paciente_no_la_pide;farmacia_receta_no_vigente;farmacia_cambio_de_indicacion;farmacia_otro;domicilio_sin_receptor;domicilio_domicilio_no_encontrado;domicilio_camino_intransitable;domicilio_rechazo;domicilio_paciente_ausente;domicilio_otro`

Base de fecha por columna: entregas de farmacia por fecha de la entrega; `farmacia_no_entregadas` y los motivos de farmacia por fecha del turno; domicilio por fecha del registro de la visita; `merma` por fecha de preparación; turnos por fecha del turno. La hoja «Por día» del Excel repite estas columnas con encabezados legibles.

### Migraciones y reversión

- `turnosapp/0014_causa_no_entrega`: dos campos opcionales con valor vacío; reversible sin pérdida (solo se pierde el código; el texto queda en `motivo`).
- Sin migraciones en `indicadoresapp`, `recetasapp` ni `entregasapp`. No se migra la base local sin instrucción del equipo.

### Plan de pruebas

- `indicadoresapp/tests/`: períodos (ocho clases, flechas, límites, enlaces antiguos, comparación con meses de distinto largo), canales (criterios de RF-13-14, incluidos turnos activos y recetas desde la ficha), motivos (causas y registros antiguos como «Otro»), entregas por día, lo preparado, ausentes (el reincorporado y atendido no cuenta), composición del panel por rol (sin RUT ni nombres en el HTML de la Dirección) y descargas (CSV con BOM, «;» y una fila por día; Excel con tres hojas; PDF; sin datos personales ni texto de «Otro»; auditoría).
- `turnosapp/tests/`: causa por receta y general, «Otro» con y sin detalle, compatibilidad de llamadas con solo texto e historial; las pruebas concurrentes del 05 sin cambios y en verde.
- `recetasapp/tests/`: enlace por rol y por estado de la fila, también en la respuesta de la búsqueda en vivo.
- `coreapp/tests/test_estaticos.py`: contraste de los colores nuevos en las dos paletas.
- Regresión completa, `makemigrations --check --dry-run` y `tools/verificar_spec_13_http.py` con 366 días.

### Riesgos de la enmienda

- **Volumen de un año.** La agregación en Python se mide con un año sintético; si «Año» supera 2 s, se agrega por fecha en la base con `TruncDate` y la zona local, comprobado en SQLite y PostgreSQL. Con el volumen real del CESFAM (unas 1.200 recetas diarias) habría que agregar en la base desde el inicio; se anota como límite del prototipo.
- **Bases de fecha distintas** (turno, entrega, registro y preparación): cada tarjeta dice cuál usa y el CSV lo documenta, para que no se lean como contradicciones.
- **Cambio en el cierre del 05,** que tiene pruebas concurrentes: el cambio se limita a validar y guardar la causa dentro de la misma transacción.
- **Detalle de «Otro» con datos de pacientes:** nunca sale del historial privado; las pruebas buscan ese texto en el panel y en las descargas.

### Documentos afectados

- `specs/README.md` (índice), al crear y al aprobar.
- Specs 05 y 07: sus enmiendas, ya redactadas.
- `CLAUDE.md` y `docs/estructura.md`, al implementar.
