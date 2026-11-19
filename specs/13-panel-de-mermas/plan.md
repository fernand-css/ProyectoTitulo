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
