# Plan técnico — 03 / Padrón y recetas

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Evidencia: [validation.md](validation.md).
Fecha de definición: 2026-11-01. Actualización 2026-11-02: código de pasos 1 a 5, verificación técnica y documentación del 6 completados; revisión visual/móvil y axe pendientes por entorno. Autorización: todos los pasos sin pausas en `fdaza`, sin rama nueva y con commit al terminar.

## Inspección de la base

Consultados `CLAUDE.md`, `docs/Informe.md` (HU-21/HU-23 y RNF), `docs/estructura.md`, índice, plantillas y documentación de los specs 01 y 02. Inspeccionados los modelos y rutas vacíos de `recetasapp`, `usuariosapp/models.py`, `coreapp/models.py`, `roles.py` y generador de RUT sintéticos.

Existen `ModeloAuditado`, `RegistroAuditoria`, utilidades RUT, roles/habilitación y layouts compartidos. `recetasapp` no tiene modelos de dominio ni vistas funcionales. El árbol contiene un cambio previo en `specs/02-autenticacion-roles-auditoria/spec.md`; preservarlo. Las pruebas y capturas de los specs previos son evidencia histórica, no validación del 03.

## Diseño aprobado y avance real

Paso 1 realizado: cinco modelos en `recetasapp/models.py`, migración `0001_initial.py` y 15 pruebas en `tests/test_modelos.py`. Se incorporaron restricciones de unicidad, cupo, positivos, fechas, estados y autorrenovación; validación de RUT/nacimiento y vínculos de paciente; protección de referencias históricas. Se separaron los conteos de filas y objetos para la futura importación. La regeneración del esquema no detecta cambios pendientes. Ver evidencia en `validation.md`. Los servicios auditados y la garantía concurrente pertenecen al paso 2 y todavía no están implementados.

Avance final: los servicios, lector/importador, formularios, rutas, plantillas, comando y herramienta HTTP ya existen. `0002_resultadofilaimportacion_pacientes_actualizados_and_more.py` conserva los cuatro conteos de objetos en cada resultado de fila para reconstruir los totales tras una interrupción, sin inferirlos desde eventos de otra carga. `openpyxl 3.1.5` instalado y probado. Las referencias a «propuesta» en el diseño siguiente describen el contrato aprobado original; no representan trabajo pendiente de código. Las evidencias reales están en validation y no se infieren de este plan.

Extender `recetasapp`, sin nuevas apps. Mantener negocio en `services.py`, lectura de archivos en el nuevo `importacion.py`, validación de entradas en `forms.py`, vistas de clase con `RolRequeridoMixin` y plantillas privadas en `templates/recetas/`. Reutilizar roles, auditoría, layouts y estilos existentes.

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-03-01 | `recetasapp/models.py`; nuevos forms/services y pruebas | Paciente, normalización, búsqueda y paginación | Unicidad RUT, campos y permisos |
| RF-03-02/03/04/05 | Nuevo `recetasapp/importacion.py`, services y pruebas | Lectores CSV/XLSX, validación, conciliación por fila | Mezclas, duplicados, repetición e historial protegido |
| RF-03-06/10 | Modelos, services, `recetasapp/admin.py` | Bitácora y eventos transaccionales | Reportes privados, atomicidad y ausencia de datos en auditoría |
| RF-03-07/08/09 | Modelos, services, forms, views, urls | Recetas, renovaciones, elegibilidad y entregas | Fechas, permisos, idempotencia y concurrencia |
| RF-03-11 | Nuevo comando y pruebas | Generación explícita de archivos sintéticos | 670 pacientes en ambos formatos |
| RF-03-01 a 11 | Nuevas plantillas, navbar y docs | Integración y verificación final | Regresión, HTTP, móvil, accesibilidad y evidencia |

## Datos y contratos

### Modelos propuestos

Los modelos de dominio heredan `ModeloAuditado`. Usar claves técnicas, sin incorporar RUT a códigos de recetas ni a referencias de operación. FKs de historial con `PROTECT`; no registrar acciones de borrado de dominio en Admin.

| Modelo | Campos y restricciones propuestas |
|---|---|
| `Paciente` | `rut` único normalizado; `nombres`/`apellidos` (150 cada uno); `fecha_nacimiento`; `es_cronico`/`es_postrado`; `telefono` opcional (30); `direccion` opcional (500). |
| `Receta` | `paciente`; `codigo` único (64, sin espacios externos, sensible a mayúsculas); `fecha_inicio`; `vigencia_meses` y `max_entregas` enteros positivos; `fecha_fin_exclusiva`; `entregas_completadas` inicial 0; `receta_anterior` nullable, del mismo paciente. Restricción de contador entre cero y máximo. |
| `EntregaReceta` | `receta`; `numero` positivo; `operacion_id` UUID único; actor y fecha de creación heredados. Único `(receta, numero)`; registros inmutables desde interfaces. |
| `ImportacionPadron` | Actor/fecha heredados; UUID de referencia, SHA-256 de archivo, formato, estado (`procesando`, `completada`, `fallida`), totales de filas, creadas/actualizadas/sin cambios/omitidas/rechazadas y resumen técnico de fallo sin datos de entrada. |
| `ResultadoFilaImportacion` | `importacion`, `numero_fila`, estado, código de motivo y mensaje fijo; referencias técnicas opcionales a paciente/receta aceptados. Único por carga/fila. Sin copia de RUT, nombre ni valores inválidos. |

`entregas_completadas` es un contador transaccional para reservar cupo; debe coincidir con el número de eventos. Los usuarios no pueden editarlo ni importarlo. Una prueba verifica esta igualdad tras éxito, rechazo, fallo y concurrencia. El rol nunca se guarda en estos modelos: se consulta la habilitación del actor.

### Calendario y elegibilidad

Propuesta: añadir meses naturales a `fecha_inicio`, ajustando un día inexistente al último día del mes destino. Guardar esa fecha como límite exclusivo: `inicio <= fecha_local < fin_exclusiva`. Mostrar al usuario como último día válido `fin_exclusiva - 1 día`. Ejemplo: inicio 2026-01-31 más un mes → límite 2026-02-28, último día válido 2026-02-27. Documentar explícitamente esta convención y cubrir fin de mes y año bisiesto; no usar meses de 30 días.

El servicio `evaluar_elegibilidad(receta, fecha)` devuelve fechas, completadas, restantes, booleano y causas (aún no inicia, vencida, agotada), sin datos de pacientes en su salida técnica. La fecha por defecto proviene de `timezone.localdate()`. No seleccionar automáticamente una receta entre varias ni bloquear globalmente al paciente porque otra receta esté agotada. La futura spec de turnos decide la selección y consume esta regla.

### Contrato de archivos

Una fila representa un paciente y, opcionalmente, una receta. CSV UTF-8 con BOM opcional, separador coma, comillas estándar; `.xlsx` con una única hoja de datos llamada `padron`, sin macros. Encabezados exactos compartidos:

`rut,nombres,apellidos,fecha_nacimiento,es_cronico,es_postrado,telefono,direccion,codigo_receta,fecha_inicio,vigencia_meses,max_entregas`

Todas las columnas existen; teléfono/dirección admiten vacío. Fechas en texto ISO `AAAA-MM-DD`; booleanos `0`/`1`; enteros positivos sin decimales. Las cuatro celdas de receta pueden estar todas vacías para cargar solo padrón; si alguna tiene contenido, las cuatro son obligatorias. No hay columna de contador ni renovación: la renovación vinculada se registra mediante el formulario, no se deduce del archivo. Las plantillas explican esto con ejemplos sintéticos.

Propuesta de límites explícitos: 5 MiB por archivo y 10.000 filas de datos. Leer `.xlsx` con `openpyxl` en modo lectura, sin evaluar fórmulas; rechazar celdas con fórmulas y tipos incompatibles. Tratar RUT/código como texto. Limitar filas durante lectura y volumen descomprimido de XLSX antes de abrirlo (50 MiB y 1.000 entradas como topes iniciales); un archivo ilegible o fuera de límites es error estructural, sin cambios de dominio. Escapar todo texto al renderizar reportes; no producir archivos con fórmulas desde texto introducido.

Añadir `openpyxl>=3.1,<4` a `requirements.txt` solo durante implementación y registrar versión probada. No se requiere pandas. Esta dependencia es para `.xlsx`, no para `.xls` ni `.xlsm`. Generar plantillas y demostraciones bajo demanda; no conservar los archivos subidos.

### Conciliación y transacciones

1. Autorizar al actor; verificar límites y estructura completa antes de modificar dominio. Crear una bitácora para la carga con referencia/hash, nunca con nombre de archivo introducido por el usuario como texto de auditoría.
2. Normalizar y prevalidar filas. Comparar identidades en todo el archivo: filas idénticas se omiten salvo una; si un RUT tiene datos de paciente distintos, rechazar todas sus filas. Repetir el mismo RUT con recetas distintas y los mismos datos personales es válido. Si un código tiene contenido o paciente contradictorio, rechazar todas sus filas. Comprobar esto antes de escribir para no depender del orden.
3. Procesar cada fila aceptable en su propia transacción atómica: actualizar/crear paciente y receta, escribir sus eventos y resultado de fila juntos. Si una receta falla, revertir también el cambio al paciente de esa fila. Consultar la propiedad y las entregas actuales al escribir, no solo en prevalidación.
4. Registrar rechazos de validación conocidos fuera de la transacción revertida con motivos fijos, sin copiar valores. No tratar fallos internos de base/auditoría como datos inválidos: detener la carga, marcarla fallida cuando sea posible e informar si hubo filas previas confirmadas. Los conteos se reconstruyen desde resultados persistidos para no declarar éxito de filas revertidas.
5. Finalizar estado y conteos y registrar evento de finalización. Un archivo válido puede terminar completado con rechazos. Repetir su hash no impide otra carga: queda otra bitácora, con las mismas identidades sin duplicación. La bitácora de un error estructural no implica cambios de dominio.

Las actualizaciones de receta requieren controlar que el contador siga en cero al escribir si cambian fechas/cupo. No basta consultar antes de otra entrega concurrente. Aplicar actualización condicional sobre el estado observado y manejar conflictos mediante rollback/reintento acotado. Dos cargas simultáneas no crean duplicados: restricciones únicas, captura de `IntegrityError` fuera del bloque atómico fallido y relectura de identidad.

### Confirmación de entregas y auditoría

`registrar_entrega(actor, receta_id, operacion_id)` comprueba rol y elegibilidad en servidor. El formulario emite UUID por intento; una repetición usa el mismo UUID. Reservar un cupo con UPDATE condicional sobre contador y fechas en `transaction.atomic()`, crear `EntregaReceta` con su ordinal y auditar en la misma transacción. Ante operación ya existente, devolver la entrega previa solo si receta y actor coinciden; rechazar reutilización para otro destino o actor. No informar la entrega ajena.

SQLite no garantiza bloqueo con `select_for_update()`: usar restricciones/UPDATE condicional y reintento acotado ante conflictos transitorios. El agotamiento produce error de negocio; el bloqueo agotado tras reintentos produce mensaje recuperable sin éxito falso. Probar entrega/entrega y entrega/importación en `TransactionTestCase` con conexiones separadas.

Catálogo propuesto: `paciente.creado`, `paciente.actualizado`, `receta.creada`, `receta.actualizada`, `receta.renovada`, `receta.entrega`, `padron.carga_iniciada`, `padron.carga_completada`, `padron.carga_fallida`. Usar `registrar_accion` y referencias de objeto, sin valores personales. La renovación puede registrar creación y vínculo como transiciones distintas, una vez cada una. Una operación repetida sin cambio no produce otro evento de entrega. Admin no permite escritura/borrado directo de estos modelos; las vistas operativas usan los servicios.

## Permisos e interfaz

| Ruta propuesta bajo `/recetas/` | Uso |
|---|---|
| `pacientes/`, `pacientes/<pk>/` | Búsqueda paginada y detalle privado con recetas |
| `nueva/`, `<pk>/`, `<pk>/renovar/` | Alta, consulta e historial/renovación |
| `<pk>/entregas/confirmar/` | Formulario y POST idempotente de entrega |
| `importaciones/`, `importaciones/nueva/`, `importaciones/<uuid>/` | Bitácora, carga y reporte paginado |
| `plantillas/<formato>/` | Descarga privada de CSV/XLSX |

Aplicar matriz del spec a todas las rutas. GET muestra información/formulario; POST con CSRF realiza cambios. Búsqueda por RUT/nombre en POST, con paginación conservada en formulario, para no incluir identificadores de pacientes en URLs o logs de acceso. URLs de detalle solo con PK técnica. Reportes por fila muestran números y motivos, no el contenido rechazado. El reporte usa categorías de fila mutuamente excluyentes y conteos de objetos separados para distinguir una fila que crea paciente y receta.

Reutilizar `templates/components/Layout/base.html`, CSS, iconos y tipografías existentes. Añadir plantillas `templates/recetas/pacientes_lista.html`, `paciente_detalle.html`, `receta_detalle.html`, `receta_form.html`, `entrega_confirmar.html`, `importacion_lista.html`, `importacion_form.html`, `importacion_detalle.html`. La renovación reutiliza el formulario. Actualizar navbar e inicio solo con enlaces existentes y permitidos. Mostrar estado vacío, errores de carga/validación, confirmación y conflicto recuperable con texto claro y sin depender del color.

## Migraciones y reversión

Proponer `recetasapp/migrations/0001_initial.py` para modelos, índices y restricciones. No cargar pacientes desde migraciones ni al arrancar. Verificar desde base vacía y actualización de copia sintética con specs 01/02 aplicadas, conservando cuentas, grupos y auditoría. No ejecutar migraciones sobre la SQLite local durante la definición.

Antes de una aplicación autorizada, respaldar base y verificar restauración. Revertir el esquema elimina padrón, recetas e historial: restaurar copia consistente si deben conservarse; no ofrecer una reversión sin pérdida de datos. La creación documental no modifica ningún esquema.

## Plan de implementación

1. Modelar pacientes, recetas, entregas y cargas; migraciones y restricciones.
2. Implementar servicios de creación, renovación, elegibilidad y confirmación idempotente/concurrente con auditoría.
3. Implementar importación CSV/XLSX, conciliación y bitácoras, con actualización protegida y pruebas de carga mixta.
4. Incorporar plantillas descargables y comando `generar_padron_demo` para 670 pacientes reproducibles en ambos formatos, sin modificar la base.
5. Implementar formularios, vistas, rutas y pantallas privadas con permisos y navegación.
6. Verificar integralmente, incluyendo migraciones, regresión, HTTP/CSRF, accesibilidad/móvil y mediciones; actualizar documentación y evidencia.

Cada paso deja el proyecto ejecutable. El detalle y las dependencias están en `tasks.md`; aprobación, rama y ritmo de ejecución se resuelven al invocar `spec-impl`, sin heredar autorizaciones de otros specs.

## Plan de pruebas

Usar ejecutor de Django, SQLite temporal y datos sintéticos deterministas. Suites nuevas propuestas en `recetasapp/tests/`: `test_modelos.py`, `test_servicios.py`, `test_concurrencia.py`, `test_importacion.py`, `test_comandos.py`, `test_vistas.py`, `test_auditoria.py`. Ampliar pruebas de navegación existentes solo donde cambien sus enlaces.

Cubrir DV/normalización, edad, campos obligatorios, inicio/fin de mes/bisiesto, cupo, renovación del mismo paciente y prohibición de alterar historial; confirmar repetición de operación y último cupo concurrente. Incluir importación concurrente con entrega y entre cargas, fallos de auditoría y consistencia contador/eventos.

Para cada formato probar 670 pacientes, varias recetas por paciente, padrón sin receta, archivos repetidos, vacíos, inválidos, encabezados duplicados/faltantes, límites, fórmulas XLSX, receta incompleta, duplicados idénticos/conflictivos y rechazo de fila sin cambios parciales. Verificar conteos/reporte y ausencia de datos personales en auditoría y mensajes de error técnicos. Comprobar inactividad, falta de perfil, roles, superusuario, URL directa, IDs/POST manipulados y CSRF real.

Comandos previstos, aún no ejecutados para el 03: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py test --noinput`; migraciones y generación/importación solo en entornos aislados. Documentar versiones, cantidades y resultados reales en `validation.md`.

En navegador comprobar búsquedas, vacíos, detalles, creación/renovación, entrega y errores/reporte de carga; teclado, texto ampliado, móvil y axe para WCAG A/AA. Medir consultas interactivas con padrón sintético de 670 pacientes, indicando equipo, número de muestras y p95; medir importaciones por separado sin inventar un SLA para la carga masiva.

## Riesgos, alternativas y dependencias

- El contrato de archivo propio no asegura compatibilidad con exportaciones reales: documentar su condición de prototipo sintético.
- Importación parcial no es atomicidad de archivo: conservar resultados de filas confirmadas y distinguir interrupción de rechazo de datos.
- Un contador duplicado respecto del historial exige una única vía transaccional y pruebas de igualdad; se elige para controlar cupo concurrente sin bloqueos de fila en SQLite.
- Los detalles de medicamentos no forman parte del ciclo acordado; no añadir inventario mediante columnas adicionales.
- Fechas y límites de carga son propuestas técnicas visibles, sujetas a revisión; no usar intervalos de 30 días ni límites ocultos.
- `openpyxl` es la única dependencia nueva propuesta. Confirmar instalación/versiones durante implementación; no descargar ni instalar en definición.

## Documentos afectados

Ahora: cuatro documentos de la carpeta y `specs/README.md`. Durante implementación: `README.md` (formatos/comando), `docs/estructura.md` (modelos/servicios/plantillas), `CLAUDE.md` (base real), tasks/validation/índice. No actualizar acuerdos o evidencia histórica del spec 02 como parte de este trabajo.

## Decisiones para implementar

El estado canónico permanece Aprobado; usuario autorizó todos los pasos sin pausas, en `fdaza`, con commit al terminar. No quedan decisiones bloqueantes de código. La verificación visual/móvil y axe del módulo no pudo ejecutarse por limitación concreta del entorno; mantenerla pendiente junto con aceptación funcional, sin declarar cumplido íntegramente RNF-04. El cambio previo del spec 02 no pertenece al commit del 03.
