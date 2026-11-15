# Plan técnico — 08 / Domicilios y entregas a domicilio

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-11. Estado: propuesta; sin código.
Autorización de implementación: pendiente.
Ampliación del 2026-11-13 (RF-08-01 modificado, RF-08-16 y RF-08-17): **Borrador**, sin código; ver [la sección al final](#ampliación-del-2026-11-13-borrador).

## Inspección de la base

Revisados `CLAUDE.md`, el informe (HU-12 a HU-16, HU-19 a HU-22, RNF-03, IG03, IG04 y §2.1 «Trazabilidad de ruta»), el índice de specs, las plantillas y los cuatro documentos del 07. Del código real:

- `entregasapp/`: solo el esqueleto (`models.py`, `views.py` y `admin.py` vacíos; `urls.py` con `app_name = "entregasapp"` y sin rutas; `tests/` y `migrations/` vacías). Ya está montada en `/entregas/` en `cesfam/urls.py`.
- `recetasapp/models.py`: `Paciente` tiene `es_postrado`, `fecha_nacimiento`, `telefono` y `direccion` (500). La importación del 03 (`importacion.py`, `aplicar_fila`) sobrescribe `direccion` y `telefono` en cada carga. `EntregaReceta.turno_receta` es anulable y la confirmación del 03 ya crea entregas sin turno. `Receta` tiene la restricción `receta_contador_en_cupo`.
- `recetasapp/services.py`: `evaluar_elegibilidad(receta, fecha)` devuelve `elegible` y `causas`. `_registrar_entrega_sin_reintento(...)` acepta `fecha=` y `desde_preparado=`; autoriza `TECNICO` (o `JEFA` en el retiro del 07); toma el vínculo `llamado` si existe; descuenta con un UPDATE condicional (`entregas_completadas__lt=F("max_entregas")` y vigencia a `hoy`) y audita `receta.entrega`. `registrar_entrega` envuelve con `bloquear_cola(hoy)`, `OperacionAtencion` y `reintentar_conflictos` (marcadores «locked/busy»).
- `turnosapp/services.py`: `clasificar_atencion` rechaza con el código `domicilio` si `es_postrado or edad > 80`. `_emitir` bloquea la cola, reserva el correlativo, toma todas las recetas elegibles y crea `TurnoReceta` y `PreparacionReceta`. Sin elegibles, responde `sin_receta`.
- `turnosapp/cola.py`: `bloquear_cola(fecha)` serializa con un UPDATE de versión sobre `EstadoColaDiaria`. Es el orden común de escritura del 04, el 05 y el 07.
- `recetasapp/preparacion.py`: `pendientes_retiro()` deriva los preparados pendientes del 07.
- `coreapp/navegacion.py`: `ENTRADAS` con roles `CON_ACCESO`, `PERSONAL_DE_FARMACIA` y `GESTION`. La entrada `inicio` ya rotula «Entregas en terreno» para `ENCARGADO`. `templates/index.html` muestra al encargado «Las rutas y el registro de entregas se sumarán en las próximas versiones». Íconos disponibles: `i-mapa`, `i-ubicacion`, `i-calendario` y `i-cama`, entre otros.
- `coreapp/mixins.py`: `tiene_rol` devuelve verdadero para el superusuario con cualquier rol. Por eso las acciones exclusivas del encargado no pueden usarlo (ver servicios).
- `recetasapp/pestanas.py`: la ficha del paciente tiene las pestañas `recetas`, `entregas` y `datos`.
- `cesfam/settings.py`: `MEDIA_ROOT = BASE_DIR / "media"`. No se sirve `/media/` en `cesfam/urls.py`, y `media` está en `.gitignore`. **Pillow no está instalado**: `ModuleNotFoundError: No module named 'PIL'` en el venv.
- `static/js/alpine.min.js` es local; las pantallas con interacción lo usan, como `importacion.js` y `receta_previa.js`.
- Migraciones actuales: `recetasapp/0004_preparacionreceta` y `turnosapp/0003_anuncio_sala`.
- El spec 01 reservó `custom_image.py` para los domicilios (HU-12) y la carpeta `static/js/entregas/`.

## Diseño propuesto

Se completa `entregasapp`. Las demás apps solo reciben ganchos aditivos.

```text
Padrón (03) ──► Paciente ──┬─ InscripcionReparto (excepciones de la Q.F.)
                           └─ Domicilio ── FotoDomicilio (≤3, privadas)
                                 ▲ edita/verifica el encargado; la importación no lo toca

Q.F. ► programar ──► Entrega (abierta: 1 por paciente)
                       ├─ RecetaEntrega × N (fijadas al programar) ─► EntregaReceta (03) al descontar
                       └─ IntentoEntrega #1, #2, … (fecha, encargado, resultado)

Encargado ► Mis entregas ► «Entregada» ─► descuento con el servicio del 03 (vigencia en la visita)
                         └ «No entregada» ─► pendiente de gestión ─► Q.F.: reasignar / anular

Tótem (04) y confirmación (03) ─► omiten/rechazan recetas de una Entrega abierta
```

Responsabilidades:

- `entregasapp/models.py` (nuevo contenido): los seis modelos de «Datos y contratos».
- `entregasapp/consultas.py` (nuevo, sin escritura): `es_elegible`, `elegibles(buscar, sector, estado)`, `estado_domicilio`, `mis_entregas(encargado, hoy)`, `pendientes_gestion(filtros)`, `programadas(filtros)`, `no_descontadas()` y `recetas_con_despacho_abierto(ids)`.
- `entregasapp/services.py` (nuevo): todas las escrituras, auditadas y transaccionales.
- `entregasapp/fotos.py` (nuevo): el almacenamiento privado y el ciclo de vida de los archivos (escribir, borrar después del commit).
- `coreapp/utils/custom_image.py` (nuevo, nombre reservado por el 01): valida y recomprime una imagen con Pillow. Es genérico y no conoce domicilios.
- `recetasapp/models.py`: `Paciente.edad_en(fecha)` y `Paciente.requiere_despacho_en(fecha)` (postrado o `edad > 80`), la regla única que comparten el 04 y el 08.

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-08-01 | `recetasapp/models.py` (métodos de `Paciente`); `turnosapp/services.py` (`clasificar_atencion` los usa); `entregasapp/consultas.py` (`es_elegible`) | Regla única de postrado/edad; elegibilidad más excepción | `entregasapp/tests/test_elegibilidad.py`; suite del 04 sin cambios |
| RF-08-02 | `entregasapp/models.py` (`InscripcionReparto`), `services.py` | Inscribir y retirar con UPDATE condicional y restricción parcial | `test_excepciones.py` |
| RF-08-03 | `entregasapp/models.py` (`Domicilio`), `services.py` (`guardar_domicilio`), `forms.py` | Creación con `IntegrityError` y reintento; edición por versión | `test_domicilios.py`; concurrencia de edición |
| RF-08-04 | `services.py` (`verificar_domicilio`), `consultas.py` (`estado_domicilio`) | Marca, vuelta a pendiente y aviso de padrón cambiado (derivado) | `test_domicilios.py`; prueba con reimportación del 03 |
| RF-08-05 | `coreapp/utils/custom_image.py`, `entregasapp/fotos.py`, `services.py`, vista de foto; `requirements.txt` (Pillow); `cesfam/settings.py`; `.gitignore` | Validar, recomprimir, guardar privado, servir con rol, borrar tras el commit | `coreapp/tests/test_custom_image.py`, `entregasapp/tests/test_fotos.py` |
| RF-08-06 | `services.py` (`programar_entrega`), `consultas.py` | Elegibles a la fecha, exclusiones del 05/07, restricción de abierta única | `test_programacion.py`; concurrencia |
| RF-08-07 | `turnosapp/services.py` (`_emitir`), `recetasapp/services.py` (`_registrar_entrega_sin_reintento`), plantillas de confirmación | Omitir/rechazar recetas con entrega abierta; mensaje `despacho_abierto` del tótem | `test_doble_via.py`; pruebas del tótem y privacidad; concurrencia con la emisión |
| RF-08-08 | `consultas.py` (`mis_entregas`), vistas y plantillas `entregas/mis_entregas*.html` | Lista por encargado y fecha; tarjetas para celular | `test_vistas_encargado.py` |
| RF-08-09 | `services.py` (`registrar_entregada`); camino `desde_despacho=` en `_registrar_entrega_sin_reintento` | Resultado único por intento; descuento por receta; no descontadas con causa | `test_registro.py`; concurrencia |
| RF-08-10 | `services.py` (`registrar_no_entregada`), `forms.py` | Motivo de catálogo y nota; estado «pendiente de gestión» | `test_registro.py` |
| RF-08-11 | `services.py` (`reasignar`, `anular_entrega`), `consultas.py` (`pendientes_gestion`) | Intento nuevo inmutable; anulación con motivo | `test_gestion.py`; concurrencia reasignar/registrar |
| RF-08-12 | `services.py` (`marcar_revisada`), `consultas.py` (`no_descontadas`) | Revisión con autor y fecha | `test_gestion.py` |
| RF-08-13 | `coreapp/navegacion.py`, `templates/components/iconos.html` (si falta un ícono), `coreapp/views.py` (inicio del encargado), `templates/index.html`, `recetasapp/views.py` y `templates/recetas/paciente_detalle.html` (pestaña Datos) | Entrada, pestañas, redirección del inicio, resumen en la ficha | `coreapp/tests/test_navegacion.py`, `test_vistas.py` |
| RF-08-14 | Vistas con `RolRequeridoMixin`; servicios con `autorizar` y `_es_encargado` | Matriz, CSRF, `no-store`, auditoría sin datos personales y rollback | `test_permisos.py` |
| RF-08-15 | `entregasapp/tests/test_concurrencia.py`; suites del 03–07 | Seis escenarios con hilos | `test_concurrencia.py`; regresión completa |

## Datos y contratos

Todos los modelos heredan `ModeloAuditado` (`creado_en`, `modificado_en`, `creado_por`, `modificado_por`). No se registran en el Admin, como en el 04: la escritura es solo por servicios auditados.

### `Domicilio`

| Campo | Tipo | Regla |
|---|---|---|
| `paciente` | OneToOne a `recetasapp.Paciente`, `PROTECT`, `related_name="domicilio"` | Uno por paciente. |
| `sector` | Char(5), opciones `verde`, `azul`, `rojo`; en blanco permitido | Obligatorio para verificar. |
| `localidad` | Char(120), en blanco | Texto, por ejemplo «Dadinco». |
| `direccion` | Char(500) | Obligatoria. |
| `referencias` | Char(500), en blanco | «Portón verde junto al paradero». |
| `latitud`, `longitud` | Decimal(9, 6), nulos | Ambos o ninguno; rangos −90..90 y −180..180. |
| `precision_metros` | PositiveInteger, nulo | Solo con coordenadas. |
| `direccion_padron` | Char(500), en blanco | Dirección del padrón al crear o al guardar por última vez. |
| `verificado_en` | DateTime, nulo | Marca de verificación. |
| `verificado_por` | FK a usuario, nulo, `PROTECT` | Ambos o ninguno con `verificado_en`. |
| `version` | PositiveInteger, por defecto 1 | Control de edición concurrente. |

Restricciones: coordenadas juntas y en rango; precisión solo con coordenadas; verificación completa o vacía. **Estado derivado** (`consultas.estado_domicilio`): «verificado» si `verificado_en` existe y `paciente.direccion == direccion_padron`; si la marca existe pero la dirección difiere, «pendiente» con el aviso de padrón cambiado; sin marca, «pendiente»; sin domicilio, «sin registrar». Así, la importación del 03 no se modifica.

### `FotoDomicilio`

`domicilio` (FK, `PROTECT`, `related_name="fotos"`), `posicion` (1–3), `archivo` (FileField en el almacenamiento privado, nombre `domicilios/<uuid4>.jpg`), `descripcion` (Char 120, obligatoria), `ancho`, `alto` y `bytes`. Restricciones: `UniqueConstraint(domicilio, posicion)` y `CheckConstraint(posicion entre 1 y 3)`. La base garantiza el máximo de tres.

### `InscripcionReparto`

`paciente` (FK, `PROTECT`), `motivo` (opciones del spec), `nota` (Char 200, en blanco), `retirada_en` (nulo) y `retirada_por` (FK nulo). Restricciones: `UniqueConstraint(paciente, condition=Q(retirada_en__isnull=True), name="inscripcion_vigente_unica")`; nota obligatoria con `otro`; retiro completo o vacío.

### `Entrega`

`paciente` (FK, `PROTECT`, `related_name="despachos"`), `estado` (`programada`, `pendiente_gestion`, `entregada`, `anulada`), `operacion_id` (UUID único, idempotencia de la programación), `cerrada_en` (nulo), `motivo_anulacion` (opciones, en blanco), `nota_anulacion` (Char 200) y `anulada_por` (FK nulo). Restricciones:
- `UniqueConstraint(paciente, condition=Q(estado__in=["programada", "pendiente_gestion"]), name="entrega_abierta_unica")`;
- `cerrada_en` presente si y solo si el estado es `entregada` o `anulada`;
- campos de anulación presentes si y solo si el estado es `anulada`.

Índice en `(estado, paciente)`.

### `RecetaEntrega`

`entrega` (FK, `PROTECT`, `related_name="recetas"`), `receta` (FK a `recetasapp.Receta`, `PROTECT`, `related_name="despachos"`), `resultado` (`pendiente`, `descontada`, `no_descontada`), `entrega_receta` (OneToOne a `recetasapp.EntregaReceta`, nulo, `PROTECT`, `related_name="despacho"`), `causa` (Char 200, en blanco), `revisada_en` y `revisada_por` (nulos). Restricciones: `UniqueConstraint(entrega, receta)`; `entrega_receta` presente si y solo si el resultado es `descontada`; causa obligatoria si es `no_descontada`; revisión solo para `no_descontada`.

### `IntentoEntrega`

`entrega` (FK, `PROTECT`, `related_name="intentos"`), `numero` (≥ 1), `fecha_programada` (Date), `encargado` (FK a usuario, `PROTECT`), `resultado` (`pendiente`, `entregada`, `no_entregada`, `reasignado`, `anulado`), `motivo` (opciones de no entrega, en blanco), `nota` (Char 200, en blanco), `registrado_en` (nulo), `registrado_por` (FK nulo) y `operacion_id` (UUID único y nulo: el que envía el formulario de resultado). Restricciones:
- `UniqueConstraint(entrega, numero)`;
- `UniqueConstraint(entrega, condition=Q(resultado="pendiente"), name="intento_pendiente_unico")`;
- motivo obligatorio si y solo si el resultado es `no_entregada`, y nota obligatoria con `otro`;
- `registrado_en`, `registrado_por` y `operacion_id` presentes si y solo si el resultado no es `pendiente`.

Índices en `(encargado, resultado, fecha_programada)` y `(resultado, fecha_programada)`.

### Servicios (`entregasapp/services.py`)

Reglas comunes: `@reintentar_conflictos` y `@transaction.atomic` (reutilizados de `recetasapp.services`), autorización en el servidor y auditoría con `registrar_accion` (si falla, `RuntimeError` y rollback). Los UPDATE condicionales filtran solo campos propios. Las condiciones que cruzan tablas se leen dentro de la transacción después de `bloquear_cola(hoy)`, cuando la operación toca recetas o turnos.

- `_es_encargado(actor)`: `estado_acceso(actor) == (True, ENCARGADO)`. **No** usa `tiene_rol`, para que el superusuario no verifique ni registre resultados.
- `guardar_domicilio(actor, paciente_id, datos, version=None)`: autoriza `JEFA` y `ENCARGADO` (más el superusuario, vía `tiene_rol`) y exige paciente elegible. Sin domicilio, lo crea; un `IntegrityError` se convierte en `ConflictoOperacion` y se reintenta. Con domicilio, hace `filter(pk, version=version).update(..., version=F("version") + 1, direccion_padron=paciente.direccion)`. Si los datos de ubicación cambiaron, limpia la verificación en el mismo UPDATE. Si actualiza 0 filas, lanza `ValidationError("El domicilio cambió; revisa los datos nuevos.")`, sin reintento.
- `verificar_domicilio(actor, domicilio_id, version)`: exige `_es_encargado`, sector y dirección. Hace `filter(pk, version=version).update(verificado_en=ahora, verificado_por=actor, direccion_padron=paciente.direccion, version=F+1)`.
- `agregar_foto(actor, domicilio_id, archivo, descripcion)` y `eliminar_foto(actor, foto_id)`: ver «Fotos».
- `inscribir_excepcion(actor, paciente_id, motivo, nota)` y `retirar_excepcion(actor, inscripcion_id)`: autorizan `JEFA`. La restricción parcial impide la doble inscripción. El retiro es `filter(pk, retirada_en__isnull=True).update(...)`.
- `programar_entrega(actor, paciente_id, fecha, encargado_id, operacion_id)`: autoriza `JEFA`. Pasos:
  1. Idempotencia por `operacion_id`: si ya existe, devuelve esa entrega si coinciden el actor y el paciente.
  2. `bloquear_cola(hoy)`.
  3. Valida fecha ≥ hoy, encargado activo con rol `ENCARGADO` y paciente elegible a la fecha.
  4. Si ya hay una entrega abierta, lanza `ValidationError` con su identificador para enlazarla.
  5. Elige las recetas elegibles a la fecha y excluye las que tienen un `TurnoReceta` con turno `esperando` o `llamado` y las de `pendientes_retiro()`. Sin recetas, rechaza.
  6. Crea la `Entrega`, sus `RecetaEntrega` y el intento 1. Un `IntegrityError` de la restricción parcial se convierte en «ya tiene una entrega abierta».
  7. Audita `entrega.programada`.
- `registrar_entregada(actor, intento_id, operacion_id)`: exige `_es_encargado`. Pasos:
  1. Idempotencia: si un intento ya tiene ese `operacion_id`, devuelve su resultado.
  2. `bloquear_cola(hoy)`.
  3. Exige que `intento.encargado == actor` y `fecha_programada <= hoy`.
  4. `IntentoEntrega.filter(pk, resultado="pendiente").update(resultado="entregada", registrado_en=ahora, registrado_por=actor, operacion_id=…)`; con 0 filas, lee el estado y rechaza o devuelve.
  5. `Entrega.filter(pk, estado="programada").update(estado="entregada", cerrada_en=ahora)`.
  6. Por cada `RecetaEntrega` pendiente, evalúa `evaluar_elegibilidad(receta, hoy)`. Si es elegible, llama a `_registrar_entrega_sin_reintento(actor, receta_id, uuid5(operacion_id, receta_id), turno_receta_id=None, fecha=hoy, desde_despacho=receta_entrega)` y marca `descontada`; si no, marca `no_descontada` con las causas del 03. Una `ValidationError` de cupo agotado en ese instante también termina en `no_descontada`. Un `ConflictoOperacion` reintenta la unidad completa.
  7. Audita `intento.entregado`.
- `registrar_no_entregada(actor, intento_id, motivo, nota, operacion_id)`: igual hasta el paso 4, con `resultado="no_entregada"`; luego `Entrega.filter(pk, estado="programada").update(estado="pendiente_gestion")`. Sin descuento.
- `reasignar(actor, entrega_id, fecha, encargado_id, operacion_id)`: autoriza `JEFA`, fecha ≥ hoy y encargado activo. Con un intento pendiente, lo marca `reasignado` (UPDATE condicional `resultado="pendiente"`). Crea el intento `numero = máximo + 1` y deja la entrega `programada` (`filter(pk, estado__in=abiertas).update(...)`). La restricción `intento_pendiente_unico` y `(entrega, numero)` resuelven la carrera con un reintento.
- `anular_entrega(actor, entrega_id, motivo, nota)`: autoriza `JEFA`. `Entrega.filter(pk, estado__in=abiertas).update(estado="anulada", …)` y el intento pendiente queda `anulado`.
- `marcar_revisada(actor, receta_entrega_id)`: autoriza `JEFA`. `filter(pk, resultado="no_descontada", revisada_en__isnull=True).update(...)`.

### Cambios en servicios existentes (aditivos)

- **`recetasapp/services.py` › `_registrar_entrega_sin_reintento`:**
  - Parámetro nuevo `desde_despacho=None`. Con él, autoriza `ENCARGADO` (comprobación exacta, como `_es_encargado`), exige `turno_receta_id=None` y que no exista un vínculo `llamado` (no puede haberlo, por el bloqueo de doble vía), y usa `fecha=` de la visita.
  - Sin él, **antes de descontar** consulta `RecetaEntrega.objects.filter(receta_id=…, entrega__estado__in=abiertas).exists()` y, si existe, rechaza con «La receta tiene una entrega a domicilio abierta.». Esta lectura cruzada es segura porque todos los caminos que escriben entregas o turnos ya tienen tomada la cola del día (`bloquear_cola`); no es un UPDATE que filtre relaciones.
  - Para no importar `entregasapp` al cargar el módulo (evitar ciclos), la consulta vive en `entregasapp.consultas.recetas_con_despacho_abierto` y se importa de forma perezosa, como ya se hace con `turnosapp`.
- **`turnosapp/services.py` › `_emitir`:** después de calcular `elegibles`, quita las recetas con despacho abierto (la misma consulta perezosa). Si había elegibles pero todas estaban en despacho, lanza `ErrorEmision("despacho_abierto", "Tienes un despacho a domicilio programado. Consulta con el personal.")` antes de crear el turno. La reserva del correlativo se revierte con la transacción, como ya ocurre con `sin_receta`. `clasificar_atencion` pasa a usar `paciente.requiere_despacho_en(fecha)`, con el mismo resultado.
- **`recetasapp/views.py`, `entrega_confirmar.html` y `receta_detalle.html`:** muestran «En entrega a domicilio abierta» con un enlace a la entrega, y la confirmación desactivada con el motivo en texto.

### Fotos (`coreapp/utils/custom_image.py` y `entregasapp/fotos.py`)

- `procesar_imagen(archivo, *, max_bytes=5 MiB, lado_max=1600, max_pixeles=40_000_000) -> (bytes_jpeg, ancho, alto)`:
  1. Rechaza más de 5 MiB antes de abrir.
  2. Abre con Pillow con `Image.MAX_IMAGE_PIXELS` acotado, para evitar bombas de descompresión, y exige formato JPEG o PNG.
  3. `verify()`, reabre y aplica `ImageOps.exif_transpose`.
  4. Convierte a RGB y reduce con `thumbnail(1600)`.
  5. Guarda como JPEG de calidad 80 sin `exif`, `icc_profile` ni otros metadatos. Los errores se traducen a mensajes en español.
- Almacenamiento: `FileSystemStorage(location=settings.ARCHIVOS_PRIVADOS_ROOT, base_url=None)`, con el ajuste nuevo `ARCHIVOS_PRIVADOS_ROOT = BASE_DIR / "privado"` (sobrescribible por `.env`) y `privado/` en `.gitignore`. No se monta ninguna URL pública.
- `agregar_foto`: procesa **antes** de la transacción, elige la primera posición libre y crea la fila. Un `IntegrityError` (posición ocupada o cuarta foto) devuelve «Ya hay 3 fotos» y borra el archivo escrito. `transaction.on_commit` confirma; si la transacción se revierte, el archivo huérfano se elimina.
- `eliminar_foto`: borra la fila, audita y elimina el archivo en `on_commit`.
- Vista `GET /entregas/fotos/<pk>/` con `RolRequeridoMixin` (Técnico, Q.F., Encargado y superusuario): `FileResponse` con `Content-Type: image/jpeg`, `Cache-Control: no-store, private`, `X-Content-Type-Options: nosniff` y `Content-Disposition: inline`.
- Dependencia nueva: `Pillow` con versión fijada en `requirements.txt` (rango menor estable al implementar). Se justifica por la recompresión y la eliminación de metadatos, que no pueden hacerse con la biblioteca estándar.

### Rutas y vistas (`entregasapp/urls.py`)

| Ruta | Método | Roles | Resumen |
|---|---|---|---|
| `/entregas/` | GET | Técnico, Q.F., superusuario → Programación; Encargado → redirige a `mis/` | Índice por rol. |
| `/entregas/programacion/` | GET | Técnico, Q.F., superusuario | Entregas programadas por fecha y encargado; filtros. |
| `/entregas/programar/` | GET, POST | Q.F., superusuario | Buscar elegible (`?paciente=<pk>` opcional), vista previa de recetas y confirmación. |
| `/entregas/pendientes/` | GET | Técnico, Q.F., superusuario | Pendientes de gestión y recetas no descontadas; filtros. |
| `/entregas/<pk>/` | GET | Técnico, Q.F., superusuario y el encargado de un intento | Detalle con historial de intentos. |
| `/entregas/<pk>/reasignar/`, `/anular/` | POST | Q.F., superusuario | HU-16. |
| `/entregas/recetas/<pk>/revisada/` | POST | Q.F., superusuario | RF-08-12. |
| `/entregas/mis/` | GET | Encargado | Hoy, atrasadas y próximas. |
| `/entregas/intentos/<pk>/entregada/`, `/no-entregada/` | POST | Encargado asignado | HU-15 con conexión. |
| `/entregas/domicilios/` | GET | Todos los perfiles con acceso | Elegibles con estado del domicilio; búsqueda por RUT o apellido (POST de búsqueda, como en el 07, para no poner el RUT en la URL); filtros por sector y estado. |
| `/entregas/domicilios/paciente/<pk>/` | GET, POST | Ver: todos; guardar: Encargado, Q.F., superusuario | Ficha y formulario del domicilio. |
| `/entregas/domicilios/<pk>/verificar/` | POST | Encargado | RF-08-04. |
| `/entregas/domicilios/<pk>/fotos/`, `/entregas/fotos/<pk>/eliminar/` | POST | Encargado, Q.F., superusuario | Fotos. |
| `/entregas/fotos/<pk>/` | GET | Todos los perfiles con acceso | Imagen privada. |
| `/entregas/excepciones/` | GET, POST | Q.F., superusuario | Inscribir, listar y retirar. |

Todas las respuestas llevan `Cache-Control: no-store`. Los POST exigen CSRF y llevan un `operacion_id` generado al dibujar el formulario. Ningún RUT ni nombre va en una URL.

## Permisos e interfaz

- Matriz aplicada dos veces: en las vistas con `RolRequeridoMixin` y en los servicios con `autorizar` o `_es_encargado`. Ocultar un botón nunca es el control.
- **Menú** (`coreapp/navegacion.py`):
  - `Entrada("entregas", "Entregas", "entregasapp:indice", "i-mapa", grupo="Trabajo", roles=PERSONAL_DE_FARMACIA, …)`;
  - para el encargado, `Entrada("mis_entregas", "Mis entregas", "entregasapp:mis", "i-ubicacion", roles={ENCARGADO}, en_barra=True)` y `Entrada("domicilios", "Domicilios", …, roles={ENCARGADO})`.
  - Un contador opcional `mis_entregas` (intentos de hoy y atrasados) se calcula solo para el encargado, como las insignias del 07.
- **Inicio del encargado:** `InicioView` redirige al encargado a `entregasapp:mis`. Se quita el texto «se sumarán en las próximas versiones» de `index.html`.
- **Pestañas:** se reutiliza `components/_pestanas.html`. Para la farmacia: Programación, Pendientes de gestión (con cantidad) y Domicilios. Para el encargado: Mis entregas y Domicilios.
- **Ficha del paciente:** la pestaña Datos agrega el bloque «Domicilio de reparto», con estado, sector, localidad, referencias y enlaces a «Ver domicilio» y a la entrega abierta. La pestaña Entregas rotula «A domicilio» las `EntregaReceta` con `despacho`.
- **Estilo:** `static/css/entregas.css` (nuevo) con los tokens existentes y sin hexadecimales, una regla que hoy verifica una prueba para `recetas.css` y `tablero.css` y que se extiende a esta hoja. Los estados van con texto e ícono («Verificado el 10/11 por …», «Pendiente de verificar», «La dirección del padrón cambió», «Atrasada desde el 09/11»).
- **Coordenadas:** `static/js/entregas/ubicacion.js` (Alpine) llama a `navigator.geolocation.getCurrentPosition` solo al pulsar el botón. Rellena latitud, longitud y precisión, y anuncia el resultado en una región `aria-live`. Sin contexto seguro o con permiso denegado, explica con texto que se ingresen a mano.
- **Fotos:** `<input type="file" accept="image/jpeg,image/png" capture="environment">` con la descripción obligatoria y el aviso de no fotografiar personas ni patentes. Las miniaturas tienen `alt` igual a la descripción.
- Wireframe de «Mis entregas» (celular):

```text
Mis entregas · martes 11/11                     [ Domicilios ]
Hoy (3) · Atrasadas (1) · Próximas (2)

┌───────────────────────────────────────────┐
│ ATRASADA desde el 10/11                   │
│ Paciente sintético 12 · ☎ 9 1234 5678     │
│ Sector Verde · Dadinco                    │
│ Km 2, camino a Dadinco                    │
│ Ref.: casa roja, portón verde             │
│ Domicilio: Pendiente de verificar         │
│ 3 fotos · −36.512345, −72.211234 (±8 m)   │
│ Recetas: DEMO-0012 (entrega 4 de 12)      │
│ [ Entregada ]        [ No entregada ]     │
└───────────────────────────────────────────┘
```

- Wireframe de «Pendientes de gestión»:

```text
Entregas › Pendientes de gestión (4)        Filtros: [Motivo ▾] [Sector ▾] [Encargado ▾] [Desde–Hasta]
Paciente            Sector  Último intento         Motivo                    Intentos  Acciones
Paciente sint. 33   Azul    #2 · 10/11 · Encarg. B  Domicilio no encontrado  2         [Reasignar] [Anular]
…
Recetas no descontadas (1)
Paciente sint. 12 · DEMO-0012 · «La receta está vencida; requiere renovación.» · 10/11   [Marcar revisada]
```

## Migraciones y reversión

- `entregasapp/0001_initial`: crea las seis tablas con sus restricciones e índices. Depende de `recetasapp/0004_preparacionreceta` y del modelo de usuario. Sin datos iniciales: los domicilios nacen al guardarlos.
- No hay migraciones en `recetasapp` ni en `turnosapp`. Los métodos nuevos de `Paciente` no cambian el esquema.
- Reversión: elimina las tablas, y con ellas domicilios, intentos e historial. Las `EntregaReceta` creadas por despachos quedan en el 03 (con `PROTECT`, primero hay que retroceder la migración y conservar esas filas) y los contadores ya descontados no se revierten. Respaldar la base y la carpeta `privado/` antes de cualquier reversión.
- No se ejecuta nada en esta fase. La base del proyecto no se migra sin aprobación; las pruebas usan la base desechable de Django y la herramienta HTTP, una SQLite temporal con una carpeta privada temporal.

## Plan de pruebas

Pruebas de Django con su propio ejecutor (sin `pytest-django`):

- **Modelos:** cada restricción (coordenadas juntas, verificación completa, posición 1–3, inscripción vigente única, entrega abierta única, intento pendiente único, coherencia de resultado, motivo y nota).
- **Elegibilidad:** límites de 80 años y 364 días y de 81, postrado, excepción vigente y retirada; el tótem del 04 clasifica igual que antes.
- **Domicilios:** creación desde el padrón, edición por versión, vuelta a pendiente, verificación solo por el encargado (rechazo de la Q.F. y del superusuario), reimportación del 03 con otra dirección (aviso derivado, sin escritura en el domicilio).
- **Fotos:** JPEG con EXIF GPS (el resultado no tiene EXIF), PNG con transparencia, PDF renombrado, imagen truncada, 6 MB, demasiados píxeles, cuarta foto, borrado con archivo eliminado tras el commit, rollback sin archivo huérfano, vista con rol, `no-store` y `/media/` inexistente. Las imágenes se generan en memoria con Pillow.
- **Programación:** recetas elegibles a la fecha; exclusión de turno activo y de pendientes de retiro del 07; sin recetas; fecha pasada; encargado inactivo o sin rol; paciente no elegible; idempotencia del POST; enlace a la entrega abierta existente.
- **Doble vía:** el tótem omite recetas en despacho y responde `despacho_abierto` sin consumir número; la confirmación del 03 se rechaza; tras anular, ambos vuelven a funcionar; prueba de privacidad del mensaje público.
- **Registro:** entregada con una receta vencida y otra vigente; cupo agotado justo antes; idempotencia; intento de mañana; otro encargado; superusuario; no entregada con y sin motivo y nota.
- **Gestión:** filtros; reasignar un intento con resultado y uno pendiente; anular; marcar revisada; historial intacto.
- **Concurrencia** (`TransactionTestCase`, hilos y conexiones separadas):
  1. dos programaciones simultáneas del mismo paciente → una entrega abierta;
  2. emisión en el tótem frente a programación del mismo paciente de excepción → ninguna receta queda a la vez en un turno activo y en una entrega abierta;
  3. dos registros del mismo intento (doble toque o dos dispositivos) → un resultado y un descuento;
  4. «entregada» frente a la confirmación del 03 de la misma receta en su última entrega disponible → el cupo nunca se excede y no se dispensa dos veces;
  5. reasignar frente a registrar el mismo intento → gana exactamente una operación y la otra recibe un motivo claro;
  6. dos ediciones del mismo domicilio → ninguna se pierde en silencio.
- **Vistas y permisos:** matriz de roles contra cada URL, CSRF, `no-store`, sin RUT en URL ni auditoría, menú por perfil, redirección del inicio del encargado y bloque de la ficha del paciente.
- **JavaScript:** pruebas con Node y DOM simulado, como `cola.test.cjs`, para `ubicacion.js`: éxito, permiso denegado y contexto no seguro.
- **Herramienta HTTP:** `tools/verificar_spec_08_http.py`, con SQLite y carpeta privada temporales y 670 pacientes sintéticos. Recorre: domicilios con foto generada, verificación, 100 programaciones, «Mis entregas», registros entregada/no entregada, reasignación y consultas con filtros. Registra el p95 de cada escenario.
- **Navegador:** revisión visual (escritorio y celular), axe, teclado, zoom y ubicación real quedan pendientes salvo que el host las permita; no se declaran sin evidencia.

## Riesgos, alternativas y dependencias

- **Cambio en la emisión y en la confirmación (doble vía).** Toca dos servicios con pruebas concurrentes. Mitigación: una sola consulta perezosa compartida, lectura con la cola tomada, sin cambios de esquema en el 03/04 y la regresión completa del 03 al 07 sin cambiar aserciones.
- **El encargado crea `EntregaReceta`.** Amplía quién puede ser responsable de una entrega de receta, como ya ocurrió con la Q.F. en el 07. Mitigación: camino acotado `desde_despacho`, comprobación exacta del rol y actor real registrado.
- **Fotos de viviendas (datos personales).** Riesgos: filtración por URL pública, metadatos GPS y bombas de descompresión. Mitigación: almacenamiento fuera de `/media/`, vista con rol y `no-store`, recompresión sin metadatos, límites de tamaño y píxeles, y nada en el repositorio. Riesgo residual: la carpeta `privado/` requiere respaldo y protección en el entorno de demostración; se documenta en el README.
- **Pillow es una dependencia nueva** con historial de vulnerabilidades en decodificadores. Mitigación: versión fijada y actualizada, solo JPEG y PNG, y límite de píxeles.
- **Ubicación del navegador sin HTTPS.** En una demostración por red local sin TLS, el botón no funciona. Mitigación: ingreso manual y mensaje claro. Se registra como límite.
- **Superusuario fuera del registro de resultados.** Contradice el atajo general de `tiene_rol`. Mitigación: `_es_encargado` explícito y pruebas que lo comprueban.
- **Serializar con `bloquear_cola(hoy)`** suma el reparto al orden de escritura de la farmacia. Es una sola fila y las operaciones son breves; la herramienta HTTP mide el efecto.
- **PostgreSQL:** los UPDATE condicionales no filtran cruzando tablas. Se revisan los marcadores de `reintentar_conflictos` frente a PostgreSQL, como ya advierte CLAUDE.md.
- **Spec 11 (sin conexión):** el `operacion_id` del resultado ya es único e idempotente, pero hoy lo genera el servidor al dibujar. La reserva 11 deberá generarlo en el cliente y enviar la hora de la visita; este spec no lo hace.
- **Dependencias:** solo Pillow.

## Documentos afectados

Al implementar: `README.md` (Pillow, `ARCHIVOS_PRIVADOS_ROOT` y respaldo de `privado/`), `.env.example`, `docs/estructura.md` (app de entregas, rutas y contratos), `CLAUDE.md` (resumen del 08) y `specs/README.md` (estado). El 01 conserva su reserva histórica de `custom_image.py`. Las exclusiones históricas del 03, 04 y 07 no se reescriben; la nota de cambio vive en el 08. Hoy solo se guardan los cuatro documentos y el índice.

## Decisiones para implementar

Ninguna bloqueante. Por confirmar en la revisión: los catálogos de motivos, la versión de Pillow y que la programación masiva quede fuera. Esta fase termina antes del código.

## Notas de implementación (2026-11-11)

Ajustes tomados al implementar, sin cambiar los requisitos del spec:

- **`IntentoEntrega.creado_con`** (UUID único y nulo): identifica la operación que creó el intento (la programación o una reasignación) para que reenviar «Reasignar» devuelva el mismo intento sin crear otro. El `operacion_id` del plan sigue siendo solo el del registro del resultado.
- **`reasignar(..., intento_id, operacion_id, resultado_visto)`**: además del último intento, la pantalla envía el resultado que la Q.F. vio. El escenario concurrente 5 mostró que, sin él, una «no entregada» registrada justo antes y la reasignación se aceptaban ambas; ahora gana exactamente una (RF-08-15).
- **Reincorporación del 05** (`turnosapp/atencion.py`): se rechaza si una receta del turno ausente quedó en una entrega abierta («Anula la entrega antes de reincorporar»). Sin esto, un turno ausente reincorporado podía dejar una receta a la vez en un turno activo y en una entrega abierta. Es aditivo y no cambia aserciones del 05.
- **Guardar un domicilio cuyo padrón cambió** limpia también la verificación: quita el aviso y lo deja «pendiente de verificar» hasta que el encargado lo verifique en terreno. Crear exige paciente elegible; editar un domicilio existente se permite aunque la excepción se haya retirado.
- **Menú:** la entrada `inicio` deja de rotularse «Entregas en terreno» para el encargado; ese texto pasa a ser el título del grupo de «Mis entregas» y «Domicilios». En el dock del celular, «Domicilios» va en «Más» porque su nombre supera los nueve caracteres que admite la barra. El contador opcional del menú no se implementó (el menú del encargado sigue sin consultas); la cantidad aparece en la pestaña «Mis entregas».
- **Inicio del encargado sin redirección:** el plan proponía redirigir `/` a «Mis entregas». Se probó y rompía seis pruebas del 02, del 06 y del tablero de Recetas, que esperan 200 en `/` para todo perfil, y el spec exige no cambiar las aserciones del 03 al 07. `InicioView` muestra la vista «Mis entregas» en la misma dirección: el inicio abre «Mis entregas» (RF-08-13) y `/entregas/` sí redirige al encargado a `/entregas/mis/`.
- **Dependencia de la migración:** `entregasapp/0001_initial` depende de `recetasapp/0002` (no de `0004`): solo usa `Paciente`, `Receta` y `EntregaReceta`, que existen desde `recetasapp/0001`, y así las pruebas de migración del 04 y del 05, que retroceden recetas a `0002` con las demás apps en su última migración, siguen pasando sin cambios.
- **Excepciones de reparto** se abren con un botón de la cabecera de Entregas (Q.F. y superusuario), no como cuarta pestaña.
- **Programar** tiene dos pasos (revisar y confirmar); el paso de confirmación reenvía la fecha, el encargado y el `operacion_id` revisados.
- **Paginación:** las listas usan `components/paginator.html` (`?page=`), que conserva los filtros.
- **Pillow 12.3.0**, fijada como `Pillow>=12.3,<13`.
- **Pruebas del 01/02 ajustadas por RF-08-13:** `coreapp/tests/test_navegacion.py` (entradas, grupos, dock y páginas activas del 08), `test_inicio.py` (el inicio del encargado muestra «Mis entregas»), `test_plantillas.py` (las listas de `entregas/` se renderizan con una página vacía, como las de `recetas/`) y `test_estaticos.py` (la regla de paleta se extiende a `entregas.css`). Las pruebas del 03 al 07 no cambiaron.

## Ampliación del 2026-11-13 (Borrador)

Cambia RF-08-01 y agrega RF-08-16 y RF-08-17. Sin modelos ni migraciones nuevos. No toca el registro en terreno, la gestión ni los servicios del 09.

### Inspección del código actual

- `recetasapp/models.py` › `Paciente.requiere_despacho_en`: `self.es_postrado or self.edad_en(fecha) > 80`. La usan `turnosapp/services.py` › `clasificar_atencion` (bloqueo `domicilio` antes de clasificar; `edad >= 60` da preferencial) y `entregasapp/consultas.py` › `es_elegible`.
- `entregasapp/consultas.py`: `EDAD_DESPACHO = 80` y `limite_nacimiento(fecha)` (resta `EDAD_DESPACHO + 1`) alimentan `condicion_elegible`, la versión en consulta. `elegibles(fecha, buscar, sector, estado)` ya filtra por búsqueda, sector y estado; `filtrar_busqueda` acepta RUT exacto o nombre/apellido.
- `ProgramarView` (`entregasapp/views.py`): sin paciente, solo muestra la barra; la búsqueda es un POST `accion=buscar` que devuelve hasta 20 resultados y calcula `estado_domicilio` por paciente. Con `?paciente=` o POST, sigue el flujo individual (revisar → confirmar con `operacion_id`).
- `services.recetas_para_despacho(paciente, fecha)`: recorre las recetas del paciente con `evaluar_elegibilidad` (sin consultas) y hace dos consultas para excluir turnos activos y pendientes de retiro. `programar_entrega` es `@reintentar_conflictos` + `@transaction.atomic`, toma `_bloquear_jornada(hoy)` y es idempotente por `Entrega.operacion_id` (devuelve la previa si coinciden actor y paciente).
- Pruebas con el límite actual: `entregasapp/tests/test_elegibilidad.py` (80 años y 364 días no; 81 sí; 64 combinaciones contra `edad > 80`) y `turnosapp/tests/test_servicios.py` (`(80, …, "preferencial")`, `(81, …, None)`). Textos con «mayor(es) de 80» en `templates/entregas/` (`programar.html`, `programacion.html`, `domicilios.html`, `domicilio.html`, `excepciones.html`) y `templates/recetas/paciente_detalle.html`.
- JavaScript de entregas: `static/js/entregas/{ubicacion,mapa,ir_a}.js` con pruebas de Node en `entregasapp/tests/*.test.cjs`.
- El padrón demo nace en 1940 (86 años): el cambio de corte no altera los 670 elegibles de las herramientas.

### Mapa por requisito

| RF | Archivos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-08-01 | `recetasapp/models.py` (`requiere_despacho_en`: `>= 80`); `entregasapp/consultas.py` (`limite_nacimiento` resta `EDAD_DESPACHO`); comentario de `clasificar_atencion`; textos de las plantillas citadas | Una sola regla de 80 años o más para el tótem y el reparto | `test_elegibilidad.py` (79 años y 364 días no; 80 sí; comparación con `>= 80`, incluido el 29 de febrero); `turnosapp/tests/test_servicios.py` (80 → bloqueo; 79 → preferencial) |
| RF-08-16 | `consultas.elegibles` (nuevos `motivo`, `localidad`, sector «sin»; anotaciones), `consultas.localidades_elegibles`; `forms.FiltroProgramarForm`; `ProgramarView` y `ProgramarListaView`; `entregas/programar.html`, `_programar_lista.html`; `static/js/entregas/programar.js` | Lista completa paginada, filtros y actualización en vivo por POST | `test_programar_lista.py`; `test_permisos.py`; `programar.test.cjs`; herramienta HTTP |
| RF-08-17 | `services.programar_lote` y `services.recetas_para_despacho_lote`; `ProgramarVariosView` (revisar) y `ProgramarTramoView` (confirmar); `_programar_resumen.html`; `programar.js` | Revisión firmada, programación por paciente en tramos, resumen | `test_programar_lote.py`; escenarios concurrentes 7–10; herramienta HTTP |

### RF-08-01 — Corte de 80 años o más

- `Paciente.requiere_despacho_en(fecha)`: `self.es_postrado or self.edad_en(fecha) >= 80`. Docstring: «Postrado o con 80 años cumplidos o más».
- `consultas.limite_nacimiento(fecha)`: último día de nacimiento con 80 años cumplidos a `fecha` (`fecha.year - EDAD_DESPACHO`, con el mismo manejo del 29 de febrero). `condicion_elegible` no cambia de forma.
- `clasificar_atencion` no cambia de código: el bloqueo va antes y el preferencial queda de 60 a 79 años. Se actualiza el comentario.
- Textos: «mayor(es) de 80 años» → «de 80 años o más» en las plantillas citadas y en el README. El mensaje del tótem no cambia.
- Sin migración: es una regla derivada.

### RF-08-16 — Lista, filtros y búsqueda en vivo

- **Consultas** (`entregasapp/consultas.py`, sin escritura):
  - `elegibles(fecha=None, *, buscar="", sector="", estado="", motivo="", localidad="")`:
    - `sector="sin"` → `Q(domicilio__isnull=True) | Q(domicilio__sector="")`.
    - `motivo`: `postrado` → `es_postrado=True`; `edad` → `fecha_nacimiento__lte=limite_nacimiento(fecha)`; `excepcion` → `Exists(_excepcion_vigente())`.
    - `localidad` → `domicilio__localidad__iexact=<valor recortado>`.
    - Anota `tiene_abierta = Exists(Entrega abierta del paciente)` y `con_excepcion = Exists(_excepcion_vigente())` para mostrar el motivo sin consultas por fila.
    - Las llamadas existentes (Domicilios) siguen iguales.
  - `localidades_elegibles(fecha)`: localidades distintas de los domicilios de elegibles, sin vacías, agrupadas con `Lower(Trim(...))` y mostradas con la primera grafía.
  - `motivos_de(paciente, fecha)`: lista de rótulos (Postrado, 80 años o más, Excepción) a partir de los campos y anotaciones ya cargados.
- **Formulario** `FiltroProgramarForm(BusquedaForm)`: `sector` (Todos, Verde, Azul, Rojo, Sin sector), `motivo`, `estado` y `localidad` (opciones dinámicas de `localidades_elegibles`), más `page`.
- **Vistas:**
  - `ProgramarView.get` sin `?paciente=` dibuja la página completa con la primera página de resultados y el formulario de filtros. `ProgramarView.post` con `accion=buscar` (respaldo sin JavaScript) dibuja lo mismo con los filtros enviados. Se quita el corte actual de 20 resultados.
  - `ProgramarListaView` (`POST /entregas/programar/lista/`, Q.F. y superusuario, CSRF, `no-store`) devuelve solo el fragmento `_programar_lista.html`: cantidad, tabla, paginación y el valor `N` de «Seleccionar los N filtrados». Va por POST para que el RUT o el nombre buscado nunca queden en la URL ni en los registros del servidor.
  - Paginación de 50 con botones `name="page"` dentro del formulario, en lugar de enlaces GET (`components/paginator.html` usa `?page=` y llevaría la búsqueda a la URL).
  - Cada fila calcula `estado_domicilio` con el domicilio ya cargado, sin consultas extra.
- **Cliente** `static/js/entregas/programar.js` (Alpine, como `ubicacion.js`):
  - escucha `input` y `change` del formulario con espera de 300 ms;
  - cancela la solicitud anterior con `AbortController` y descarta respuestas viejas por número de secuencia;
  - envía `X-CSRFToken` y reemplaza solo el contenedor de la lista, sin mover el foco;
  - escribe «N pacientes del reparto» en una región `role="status"`;
  - con un error de red, muestra «No pudimos actualizar la lista. Reintentar» con texto.
  - Sin JavaScript, el botón «Buscar» envía el mismo formulario.
- **Fila:** casilla (`<label class="sr-only">Seleccionar a Apellido, Nombre</label>`), paciente y RUT, motivo(s), sector · localidad, estado del domicilio y acción («Elegir» o «Ya tiene una entrega abierta», con enlace y casilla desactivada).

### RF-08-17 — Programar varios

- **Selección (cliente):**
  - `seleccionados` (conjunto de ids) vive en el estado de Alpine y sobrevive al reemplazo del fragmento. Las casillas de cada fragmento nuevo se marcan según el conjunto.
  - «Seleccionar esta página» marca las casillas activas visibles.
  - «Seleccionar los N filtrados» activa el modo `todos` con una copia de los filtros vigentes. Cualquier cambio de búsqueda o filtro lo anula y lo anuncia: «Se quitó la selección de todos los filtrados porque cambiaste la búsqueda».
  - Barra fija inferior: «N seleccionados · [Quitar selección] [Programar seleccionados]».
  - Sin JavaScript, las casillas de la página visible y un botón «Seleccionar los N filtrados» envían el mismo formulario de revisión.
- **Revisión** `ProgramarVariosView` (`POST /entregas/programar/varios/`, Q.F. y superusuario):
  - Recibe `ids` o `todos=1` con los filtros, más `fecha` y `encargado`. En el primer paso solo hay ids o filtros; se dibuja el formulario de fecha (por defecto hoy) y encargado.
  - Con fecha y encargado válidos, resuelve la lista concreta en el servidor: con `todos`, `elegibles(...)` con los filtros, nunca los ids del navegador.
  - Clasifica a cada paciente con `consultas.es_elegible` en versión de lote (la misma condición), entrega abierta (`Exists`) y `services.recetas_para_despacho_lote(pacientes, fecha)`.
  - Dibuja `_programar_resumen.html`: fecha, encargado, «Se programarán P pacientes con R recetas», un `<details>` por paciente con sus recetas y «entrega n de m», y «No se programarán (k)» con el motivo.
  - Genera `lote = uuid4()` y firma `{"lote", "ids" (los P a programar), "fecha", "encargado", "actor"}` con `django.core.signing.dumps(..., salt="entregas.programar_lote", compress=True)`, como el formulario de recetas del 03/05 firma su contexto.
- **`services.recetas_para_despacho_lote(pacientes, fecha) -> dict[paciente_id, list[Receta]]`:** el mismo resultado que llamar `recetas_para_despacho` por paciente, con un número constante de consultas (`prefetch_related("recetas")` y las dos exclusiones con `receta_id__in` de todas). Una prueba compara ambos resultados y otra fija las consultas con `assertNumQueries`.
- **Confirmación** `ProgramarTramoView` (`POST /entregas/programar/varios/confirmar/`, Q.F. y superusuario):
  - Recibe el contexto firmado y `desde`/`hasta` (índices del tramo, de hasta 25).
  - Rechaza una firma inválida, un actor distinto del firmado o un tramo fuera de rango (400 con texto).
  - Llama a `services.programar_lote(actor, ids_del_tramo, fecha, encargado_id, lote)` y responde JSON sin RUT: por paciente, `programado` (con el id de la entrega y la cantidad de recetas) u `omitido` (con el motivo en texto).
  - Sin JavaScript, el botón «Confirmar» envía el lote completo en una sola solicitud y dibuja el resumen (más lenta; queda como límite).
- **`services.programar_lote(actor, paciente_ids, fecha, encargado_id, lote_id)`:**
  - Autoriza `JEFA` una vez.
  - Por cada paciente llama a `programar_entrega(actor, pid, fecha, encargado_id, uuid5(lote_id, str(pid)))`.
  - **No** envuelve el ciclo en una transacción: cada paciente es su propia transacción con `_bloquear_jornada`. Así el bloqueo de la cola dura lo que dura un paciente y un fallo no revierte a los demás.
  - Traduce los errores a resultados: `EntregaAbiertaExistente` → «Ya tiene una entrega abierta»; `ValidationError` → su mensaje; `ConflictoOperacion` agotado o `DatabaseError` → «No se pudo programar; vuelve a confirmar». Un reenvío no duplica.
  - Una entrega previa del mismo lote vuelve como `programado`, gracias a la idempotencia de `programar_entrega`. No agrega eventos de auditoría: cada entrega ya audita `entrega.programada`.
- **Cliente:**
  - `programar.js` envía los tramos en orden, actualiza `<progress>` y «Programando 50 de 118» en `role="status"`, y acumula los resultados.
  - Ante un error de red se detiene con «Se interrumpió en 50 de 118. [Reintentar]». Reintentar reenvía desde el primer tramo sin respuesta; si se reenvía algo ya hecho, es idempotente.
  - Al terminar muestra «Se programaron X de Y», la tabla de omitidos con su motivo y el enlace a «Programación» filtrada por esa fecha y ese encargado.
- **Wireframes:**

```text
Entregas › Programar entrega
Buscar paciente (RUT, nombre o apellido)  [ Gonz                     ] [Buscar]
Sector [Todos ▾]  Motivo [Todos ▾]  Domicilio [Todos ▾]  Localidad [Todas ▾]  [Quitar filtros]
124 pacientes del reparto                         [Seleccionar los 124 filtrados]
☐ │ Paciente                 │ Motivo     │ Sector · localidad │ Domicilio      │
☐ │ González, Ana · RUT …    │ 80 o más   │ Verde · Dadinco    │ Verificado     │ Elegir
– │ Gómez, Luis · RUT …      │ Postrado   │ Sin sector         │ Sin registrar  │ Ya tiene una entrega abierta
                                                   ‹ Anterior  Página 1 de 3  Siguiente ›
────────────────────────────────────────────────────────────────────────────────
12 seleccionados          [Quitar selección]          [Programar seleccionados]
```

```text
Programar 118 entregas
Fecha [14/11/2026]  Encargado [Encargado B ▾]  [Revisar]
Se programarán 114 pacientes con 231 recetas.
▸ González, Ana · Verde · Dadinco · 2 recetas
No se programarán (4): Gómez, Luis · Ya tiene una entrega abierta …
[Confirmar y programar 114]  [Volver a la lista]
Programando… 50 de 114  [██████░░░░]   →   Se programaron 113 de 114. No se programaron (1): …
```

### Pruebas previstas

- **Elegibilidad:** límites de 79 años y 364 días, 80 recién cumplidos y 81; 29 de febrero; comparación de `condicion_elegible` con `es_elegible` en las 64 combinaciones, ahora contra `>= 80`; tótem con 79 (preferencial), 80 y 81 (bloqueo `domicilio`).
- **Lista y filtros** (`test_programar_lista.py`):
  - cada filtro solo y combinado, con «Sin sector» y una localidad con distinta grafía;
  - un paciente con dos motivos aparece en ambos filtros;
  - con entrega abierta: rotulado y sin casilla;
  - paginación de 50 por POST;
  - número constante de consultas por página;
  - sin RUT en la URL ni en los enlaces del fragmento;
  - el respaldo sin JavaScript (`accion=buscar`) da los mismos resultados que el fragmento.
- **Lote** (`test_programar_lote.py`):
  - `recetas_para_despacho_lote` igual al cálculo por paciente;
  - resumen con programables y omitidos (entrega abierta, sin recetas, no elegible a la fecha);
  - confirmación por tramos;
  - reenvío de un tramo y del lote completo sin duplicados;
  - firma alterada, actor distinto, tramo fuera de rango, fecha pasada y encargado inactivo;
  - Técnico con 403;
  - un omitido no revierte a los demás;
  - auditoría: una `entrega.programada` por entrega y sin datos personales.
- **Concurrencia** (se agrega a `test_concurrencia.py`, con `TransactionTestCase`, hilos y conexiones separadas):
  7. dos lotes con pacientes en común al mismo tiempo → una sola entrega abierta por paciente; cada paciente sale `programado` en un lote y `omitido` en el otro;
  8. el mismo tramo enviado dos veces a la vez → sin duplicados; ambas respuestas lo dan por programado;
  9. un lote frente a la emisión del tótem de una excepción del lote → ninguna receta queda a la vez en un turno activo y en una entrega abierta;
  10. un lote frente a la programación individual del mismo paciente → una sola entrega abierta.
- **JavaScript** (`entregasapp/tests/programar.test.cjs`, Node con DOM simulado):
  - espera de 300 ms y cancelación;
  - las respuestas fuera de orden se descartan;
  - la selección se conserva al reemplazar el fragmento;
  - el modo `todos` se anula al cambiar un filtro;
  - tramos en orden, detención y reintento;
  - textos anunciados.
- **Herramienta HTTP** (`tools/verificar_spec_08_http.py`, se amplía):
  - p95 de la lista inicial y de 100 actualizaciones del fragmento con búsqueda y filtros;
  - tiempo de la revisión de un lote con todos los elegibles (670);
  - p95 de los tramos de 25 y tiempo total del lote completo;
  - reenvío de un tramo sin duplicados;
  - p95 del tótem mientras corre un lote.
- **Regresión:** suite completa; solo cambian las aserciones de edad del 04 y del 08 indicadas.

### Riesgos

- **Cambio del contrato del 04 (tótem):** una persona de 80 años deja de recibir número presencial. Mitigación: decisión anotada en este spec, aserciones de edad actualizadas solo en el límite, nota en el `spec.md` del 04 al implementar y aviso al equipo (el 04 se trabajó en `fdaza`).
- **Lote sin tope:** un error puede asignar cientos de visitas a un encargado. Mitigación: resumen obligatorio con las cantidades antes de confirmar y anulación individual existente. No hay deshacer en bloque: queda fuera, como la anulación masiva.
- **Bloqueo de la cola durante un lote grande:** cada paciente toma `bloquear_cola(hoy)` por poco tiempo. Un lote de 670 serializa unos cientos de transacciones breves con el tótem y la ventanilla intercaladas. Se mide el p95 del tótem durante un lote.
- **Revisión de un lote completo:** dibujar 670 pacientes con sus recetas pesa. Mitigación: cálculo por lotes con consultas constantes, `<details>` cerrados y medición en la herramienta. Si supera los 2 s, se informa como límite, sin prometer otro valor.
- **Contexto firmado grande:** 670 ids comprimidos caben en un campo oculto. La firma impide alterar la lista, y el servidor igual revalida todo al programar.
- **Búsqueda en vivo por POST:** no aprovecha la caché ni el historial del navegador. Es intencional por privacidad (RNF-01).

### Documentos afectados al implementar

- `specs/04-emision-de-turnos/spec.md` (nota de cambio en «Revisión y cambios» y en RF-04-02/04 con enlace aquí).
- `CLAUDE.md` (sección del 08: `edad >= 80`, lista con filtros y programación por lote).
- `README.md` (regla de edad).
- `docs/estructura.md` (consultas y rutas nuevas).
- `specs/README.md` (estado).

### Notas de implementación de la ampliación (2026-11-13)

Implementada en `crojas-base` sin cambiar requisitos. Ajustes técnicos respecto del diseño de arriba:

- **Paginación con `pagina`, no `page`:** `FiltroProgramarForm` hereda de `BusquedaForm`, que ya usa `pagina` (como Domicilios). Los botones «Anterior» y «Siguiente» son `<button name="pagina">` del mismo formulario.
- **Localidad por clave normalizada:** el valor del filtro es `Lower(Trim(localidad))` calculado por la base, y la consulta compara con la misma expresión. Así la agrupación y el filtro coinciden en PostgreSQL y en SQLite, también con letras acentuadas.
- **Anotaciones de la lista:** `elegibles` anota `abierta_id` (subconsulta de la entrega abierta, para enlazarla) además de `con_excepcion`. El número de consultas por página es constante.
- **Códigos en los rechazos de `programar_entrega`:** los `ValidationError` de no elegible y sin recetas llevan `code="no_elegible"` y `code="sin_recetas"`, para traducirlos a los motivos cortos del lote. Los mensajes de la programación individual no cambian.
- **`programar_lote` valida la fecha y el encargado una sola vez** antes del ciclo. Si no sirven, rechaza el tramo completo («Rechazo con motivo y sin cambios»), en vez de omitir a cada paciente con el mismo motivo.
- **Revisión:** `ProgramarVariosForm` (fecha y encargado, con su propio `auto_id`). El orden de clasificación imita el servicio: primero elegible, luego entrega abierta y por último recetas. Con «todos», la lista se resuelve con los elegibles a hoy y los filtros; los ids del navegador se ignoran. Un filtro inválido vuelve a la lista con aviso.
- **Contexto firmado:** además de lote, ids, fecha, encargado y actor, lleva los omitidos de la revisión con su motivo. Así el resumen final sin JavaScript informa «Se programaron X de Y» con todos los omitidos, sin guardar nada.
- **Respuesta de los tramos:** JSON con id del paciente, estado, entrega y cantidad de recetas, o el motivo. Sin RUT ni nombres: el navegador toma el nombre de los omitidos del resumen ya dibujado.
- **Cliente:** el formulario de la lista distingue los envíos por `submitter`:
  - «Programar seleccionados» escribe los ids ocultos (o `todos=1`) y envía de forma normal.
  - «Seleccionar los N filtrados», la paginación y «Buscar» se atienden sin recargar.

  Si el filtro cambió antes de que venza la espera de 300 ms, «todos» se anula antes de enviar. AbortController y el temporizador viven fuera del estado reactivo de Alpine.
- **Barra de selección:** fija al final solo en computador (`min-width: 70rem`). En celular queda al final de la lista para no tapar el dock del menú.
- **Herramienta HTTP:** el marcador «Hoy (» de «Mis entregas» estaba desactualizado desde el spec 09 (la lista pasó a «Por visitar en orden (»). Se corrigió al ampliar la herramienta.

## Enmienda del 2026-11-15 — diseño propuesto

Propuesta técnica para la [enmienda de spec.md](spec.md#enmienda-del-2026-11-15-borrador) (RF-08-18 a RF-08-20). El resto de la enmienda (tarjetas, arrastre, OSRM y «Usar mapa») está en el [plan del 09](../09-mapa-y-orden-de-visita/plan.md#enmienda-del-2026-11-15--diseño-propuesto). Sin código; la implementación requiere aprobación y autorización.

### Inspección del código actual

- `entregasapp/services.py`: `agregar_foto` procesa la imagen fuera de la transacción, escribe el archivo y llama a `_registrar_foto` (primera posición libre, `IntegrityError` → `ConflictoOperacion`, con `reintentar_conflictos`); `eliminar_foto` borra la fila, audita y elimina el archivo en `on_commit`.
- `entregasapp/fotos.py`: `guardar_jpeg`, `borrar` y `abrir` sobre el almacenamiento privado. `coreapp/utils/custom_image.py`: `procesar_imagen`.
- Vistas y rutas: `FotoAgregarView` (`domicilios/<pk>/fotos/`), `FotoEliminarView` (`fotos/<pk>/eliminar/`) y `FotoView` (`fotos/<pk>/`, privada y `no-store`).
- `templates/entregas/domicilio.html`: sección «Fotos del entorno» con un formulario por foto para borrar y otro para agregar. `_tarjeta_intento.html`: miniaturas como enlaces a la imagen.
- Textos: «Ver domicilio» en `_tarjeta_intento.html`, `ir_a.html`, `domicilios.html` y `recetas/paciente_detalle.html` (y en el resumen de los marcadores de `mapa.js`); «Localidad» en `DomicilioForm` y `FiltroProgramarForm` (`entregasapp/forms.py`) y en la ficha de `domicilio.html`.

### Servicio atómico de fotos (`entregasapp/services.py`)

`gestionar_fotos(actor, domicilio_id, *, mostradas, borrar, nuevas)`:
- `mostradas`: ids de las fotos que el modal mostró; `borrar`: ids marcados; `nuevas`: lista de `(archivo, descripcion)` en el orden del modal.
- `autorizar(actor, JEFA, ENCARGADO)`, como hoy (el superusuario pasa por su excepción general).
- **Antes de la transacción:** valida cada descripción (1 a 120 caracteres) y procesa cada imagen con `procesar_imagen`. El primer error lanza `ValidationError` con el índice («La foto 2 no se pudo procesar: …»), sin escribir nada. Luego escribe todos los JPEG con `fotos.guardar_jpeg`.
- **En `transaction.atomic()`:** comprueba que el conjunto actual de ids del domicilio sea igual a `mostradas` (si no, `ValidationError` con el aviso de cambio en otro dispositivo); que `borrar ⊆ mostradas`, y que `len(mostradas) − len(borrar) + len(nuevas) ≤ 3`. Borra las filas marcadas (comprobando la cantidad borrada), crea las nuevas en las posiciones libres y audita cada una (`domicilio.foto_eliminada`, `domicilio.foto_agregada`). Un `IntegrityError` en la posición única revierte todo y se informa como cambio concurrente.
- **Archivos:** si la transacción falla, se borran los JPEG nuevos; los de las fotos borradas se eliminan con `transaction.on_commit`.
- `agregar_foto` y `eliminar_foto` pueden quedar como envoltorios de `gestionar_fotos` o retirarse. Se decide al implementar, según las pruebas del 08 que los usan, y se anota.

### Vistas, rutas y plantillas

- `GET/POST /entregas/domicilios/<pk>/fotos/` (`FotosView`, reemplaza a `FotoAgregarView`): sin JavaScript, el GET muestra la página con el formulario del modal y el POST redirige a la página de origen (parámetro `volver` validado con `url_has_allowed_host_and_scheme`). Con JavaScript (`Accept: application/json`), el POST responde `{"ok": true, "fotos": [...]}` o `{"error": "texto", "foto": n}` con 400.
- Se retira `fotos/<pk>/eliminar/` (`FotoEliminarView`).
- `FotosForm` (nuevo, en `forms.py`): `mostradas` y `borrar` (ids), y hasta 3 pares `archivo_N`/`descripcion_N`. Cada archivo usa `accept="image/jpeg,image/png"`. «Sacar foto» es un segundo `<input type="file" capture="environment">` que llena el mismo espacio.
- Parciales nuevos: `_fotos_boton.html` («Registrar fotos» o «Gestionar fotos» según la cantidad), `_fotos_modal.html` (`<dialog>` con el formulario, la vista previa y la región de errores con `role="alert"`) y `_visor_foto.html` (`<dialog>` con la imagen, el pie y la X).
- `domicilio.html` usa el botón y el modal en lugar de sus formularios; las miniaturas de `domicilio.html` y `_tarjeta_intento.html` pasan a ser botones del visor, con el enlace como respaldo sin JavaScript.

### JavaScript

- `static/js/entregas/fotos.js` (nuevo): abre el modal con `showModal()`; marca y desmarca borrados; muestra y oculta los espacios nuevos según la cuenta; muestra la vista previa con `URL.createObjectURL` (y la libera al cerrar); envía con `fetch` y `FormData`; muestra el error junto a la foto indicada y mueve el foco a él; distingue la falta de red; al guardar, actualiza la tarjeta o recarga la página.
- `static/js/entregas/visor.js` (nuevo): abre la imagen en el `<dialog>`; cierra con la X, con Esc (comportamiento nativo) y con un clic sobre el fondo del diálogo fuera de la imagen; devuelve el foco a la miniatura.
- Pruebas de Node: `fotos.test.cjs` y `visor.test.cjs`.

### Textos (RF-08-20)

- Plantillas: `_tarjeta_intento.html`, `ir_a.html`, `domicilios.html` y `recetas/paciente_detalle.html` dicen «Detalles del domicilio»; `mapa.js` usa el mismo texto en el resumen de los marcadores.
- `DomicilioForm.localidad.label` y `FiltroProgramarForm.localidad.label` pasan a «Nombre de la localidad», al igual que el `<dt>` de la ficha en `domicilio.html`. No se toca `Domicilio.localidad.verbose_name`, para no generar una migración.

### Pruebas previstas

- `test_fotos.py`: guardado con borrado y dos nuevas; falla en la foto 2 sin cambios en la base ni en los archivos; descripción vacía o larga; conjunto cambiado; más de 3; archivos de las borradas eliminados solo tras confirmar; auditoría sin datos personales.
- `test_concurrencia.py` (escenarios nuevos con `TransactionTestCase` e hilos): dos guardados desde el mismo estado; guardado mientras otro borra; dos guardados que agregan con 2 fotos guardadas. En todos, nunca más de 3 fotos y ningún archivo huérfano.
- `test_vistas.py` y `test_permisos.py`: botón según la cantidad, página sin JavaScript, JSON con el índice del error, Técnico 403, CSRF y `volver` externo rechazado.
- `test_estructura.py`: diálogos con nombre accesible, botones con tipo y miniaturas con nombre.
- Búsqueda en las plantillas: no queda «Ver domicilio»; las etiquetas dicen «Nombre de la localidad».

### Riesgos

- **Tamaño de la solicitud:** tres fotos de 5 MB en una solicitud con mala señal pueden tardar o cortarse. El corte no aplica nada (todo o nada) y el aviso lo dice. Se mide y se informa aparte.
- **Archivos huérfanos:** si el proceso muere entre escribir los JPEG y la transacción, quedan archivos sin fila. Se acepta como hasta ahora y se anota en `validation.md`. Una limpieza periódica queda fuera.
- **`capture`:** algunos navegadores de escritorio lo ignoran y abren el selector de archivos, que es el comportamiento esperado.

### Pruebas del 08 que se ajustarán

Se listan al implementar: las que usan `foto_agregar` y `foto_eliminar` (`test_fotos.py`, `test_vistas.py` y `test_permisos.py`) y las que buscan los textos «Ver domicilio» o «Localidad».

### Documentos afectados al implementar

`CLAUDE.md` (sección del 08: servicio de fotos atómico), `docs/estructura.md` (rutas de fotos), `specs/README.md` y `validation.md`.
