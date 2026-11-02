# Validación — 03 / Padrón y recetas

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha de definición: 2026-11-01. Ejecución: 2026-11-02.
Entorno: Windows, Python 3.13 del venv, Django 5.2.18, openpyxl 3.1.5 y SQLite temporal. Referencia: implementación del 03 en `fdaza`; commit de cierre de esta entrega.
Estado: **verificación técnica completada; visual/móvil/axe y aceptación funcional pendientes**. No se declara completado todo RNF-04.

## Comandos y resultados reales

| Comando | Resultado obtenido |
|---|---|
| `.\venv\Scripts\python.exe manage.py makemigrations recetasapp` | Creó 0001 con cinco modelos; una ejecución posterior creó 0002 con conteos de objetos por fila. |
| `.\venv\Scripts\python.exe -m pip install -r requirements.txt` | Instaló openpyxl 3.1.5 y et-xmlfile 2.0.0 en el venv. |
| `.\venv\Scripts\python.exe manage.py check` | Sin problemas. |
| `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run` | `No changes detected`. |
| `.\venv\Scripts\python.exe manage.py test recetasapp.tests.test_modelos --noinput` | Paso 1: 15 aprobadas; última ejecución focalizada 0,552 s. |
| `.\venv\Scripts\python.exe manage.py test recetasapp coreapp.tests.test_plantillas --noinput` | Integración inicial: 64 aprobadas en 19,629 s, tras corregir colisión de bitácoras. |
| `.\venv\Scripts\python.exe manage.py test recetasapp.tests.test_vistas coreapp.tests.test_plantillas --noinput` | Corrección final del mensaje de UUID oculto: 26 aprobadas en 0,944 s. |
| `.\venv\Scripts\python.exe manage.py test --noinput` | **238 pruebas aprobadas en 62,150 s**, incluidas 51 del 03; system check sin problemas; base temporal creada y destruida. |
| `.\venv\Scripts\python.exe tools/verificar_spec_03_http.py --preview` | 23 migraciones sobre SQLite nueva; 670 pacientes; CSV/XLSX, permisos, CSRF, idempotencia, renovación e historial aprobados por HTTP real. Preparó doce copias HTML sintéticas de solo lectura. |
| `git diff --check` | Sin errores de espacios; advertencias de normalización LF/CRLF del entorno Windows. |

La suite de paso 1 pasó previamente con 202 pruebas y una regresión intermedia con 237. Son ejecuciones históricas de esta implementación, no el resultado final. No se atribuyen al 03 pruebas o capturas de specs anteriores. El sandbox bloqueó inicialmente el intérprete instalado; las ejecuciones posteriores se realizaron con la aprobación requerida, sin tratar ese bloqueo como fallo de código.

## Matriz de comprobaciones ejecutadas

| RF | Evidencia | Resultado | Estado |
|---|---|---|---|
| RF-03-01 | test_modelos y test_vistas: normalización/DV, nacimiento, edad calculada, búsqueda privada | Identidad única, rechazo de inválidos y consulta por POST sin RUT en URL | Aprobado técnico |
| RF-03-02/03 | test_importacion: CSV mixto, XLSX con fórmula y fila válida, receta incompleta | Las válidas continúan; rechazadas con número/motivo fijo; sin cambios parciales | Aprobado técnico |
| RF-03-02 | Formato/encabezados, UTF-8, hoja incorrecta, archivo vacío/ilegible, tamaño y filas | Rechazo estructural sin cambios de dominio | Aprobado técnico |
| RF-03-04 | Archivo repetido en ambos formatos; duplicados idénticos y contradictorios en orden inverso | Sin duplicación; omisión/rechazo conforme a contrato | Aprobado técnico |
| RF-03-04/05 | test_importacion y test_concurrencia: reasignación de código, cambios con entregas, importación/entrega | Propiedad e historial protegidos; cupo preservado | Aprobado técnico |
| RF-03-06 | Carga completada/con rechazos/fallida e interrupción tras primera fila | Conteos reconstruidos desde resultados confirmados; responsable, fecha y referencia | Aprobado técnico |
| RF-03-07 | Modelos/servicios/vistas y HTTP: creación, renovación, paciente manipulado y roles | Nueva receta vinculada, contador cero, antecedente conservado; Técnico no crea | Aprobado técnico |
| RF-03-08 | test_servicios: límites, meses cortos, bisiestos, overflow y causas simultáneas | Fechas, contador, restantes y elegibilidad según contrato | Aprobado técnico |
| RF-03-09 | Conexiones separadas: tres confirmaciones por último cupo y doble UUID; HTTP repite POST | Una entrega por operación, sin exceder máximo | Aprobado técnico |
| RF-03-09/10 | Fallos de auditoría en alta/entrega/fila y auditoría que lanza ValidationError | Rollback; interrupción distinguida del rechazo de datos; sin éxito falso | Aprobado técnico |
| RF-03-10 | Matriz GET/POST, perfil ausente, inactividad, superusuario, CSRF real e IDs manipulados | Permisos comprobados en servidor; Admin sin escritura de dominio | Aprobado técnico |
| RF-03-10 | Inspección de eventos y reportes con datos sintéticos inválidos | Sin RUT/nombres ni valores rechazados en auditoría/motivos | Aprobado técnico |
| RF-03-11 | Comando y carga/repetición de 670 en ambos formatos; HTTP real | 670 identidades y recetas sin digitación, duplicación ni entregas importadas | Aprobado técnico |

## Concurrencia y migraciones

Cuatro escenarios usan `TransactionTestCase`, barrera e hilos con conexiones independientes: último cupo disputado por tres confirmaciones; UUID repetido concurrente; entrega frente a cambio de cupo por importación; cargas simultáneas de la misma identidad. Se comprueba contador frente a eventos y ausencia de duplicación.

La primera ejecución detectó `database table is locked` al crear dos bitácoras: se corrigió con reintentos acotados en inicio, resultados, lectura, total y cierre, manteniendo transacciones por fila. Las suites posteriores pasaron. No se confía en `select_for_update()` en SQLite. No se afirma validación ejecutada sobre PostgreSQL.

El runner migra desde cero. La prueba con `MigrationExecutor` retira el esquema de recetas de la base temporal, prepara una cuenta/grupo/perfil y auditoría sintéticos y migra nuevamente: conserva cuenta, hash, perfil, grupo y evento sin sembrar pacientes/recetas/cargas. La herramienta HTTP aplicó 23 migraciones desde cero. No se aplicaron las migraciones a `db.sqlite3` local.

## HTTP real y rendimiento

Herramienta: `tools/verificar_spec_03_http.py`, WSGI en loopback con SQLite temporal, correo en memoria y claves aleatorias efímeras. Comprueba login por rol, POST multipart, CSRF sin token rechazado, Q.F. sin permiso de entrega, Encargado sin acceso al padrón, renovación con paciente manipulado, entrega repetida y rechazo de cambio de cupo tras entregar. Estado final: 670 pacientes, 671 recetas (incluye renovación de QA), una entrega confirmada.

Resultados de la ejecución local:

- Importación CSV inicial de 670 pacientes: **10,880 s**.
- Importación Excel de las mismas identidades, sin duplicarlas: **6,961 s**.
- 40 consultas HTTP de detalle sobre ese padrón: **p95 0,0366 s**, percentil de rango más próximo (muestra ordenada 38 de 40).

Es una medición local del detalle de receta, sin carga de múltiples usuarios; no demuestra por sí sola el p95 de todas las rutas ni el rendimiento de despliegue. La importación masiva se mide separada y no tiene SLA contractual adicional.

## Presentación y accesibilidad

Ejecutado: renderizado de plantillas, escape de HTML, etiquetas de campos visibles, IDs únicos, un solo main, estados de formulario y mensaje visible de UUID inválido. Las pruebas existentes de contraste de estilos compartidos pasan dentro de la regresión. Se reutiliza la identidad y CSS existentes.

No ejecutado: revisión visual en escritorio/móvil, teclado real, texto ampliado en navegador y axe del módulo. Se intentó inventario con `cua`: devolvió `The browser access host is unavailable`. Se intentó vincular Firefox y recuperarlo mediante lanzamiento de la app; ambas ventanas devolvieron `window is minimized; call activate_window, refresh with get_window, then retry get_window_state`. La interfaz disponible no permitió recuperar una ventana capturable. No se usaron ventanas de Word u otras apps para eludir ese límite.

La herramienta preparó doce copias HTML sintéticas para revisión: padrón, paciente, receta, alta, renovación, entrega, carga, bitácora, reporte y tres formularios con errores. Su preparación no cuenta como captura ni auditoría visual. Se cerró el servidor y se verificó que ya no escuchaba el puerto; tras terminar la sesión de ejecución, se eliminó explícitamente su SQLite y carpeta temporal exacta, previamente inspeccionadas.

Quedan pendientes la revisión visual/móvil y axe del 03, y la prueba de usabilidad con al menos cinco participantes del RNF-04. No se declara esa prueba realizada por contar con pruebas automáticas.

## Aplicación, reversión y límites

Se instalaron dependencias en el venv y se añadieron dos migraciones. La SQLite local y sus datos no fueron modificados. La aplicación futura requiere `python manage.py migrate` en el entorno autorizado; respaldar antes. La reversión que elimina tablas pierde padrón/historial y requiere restaurar copia consistente si se deben conservar.

Sin API con Rayén ni archivos reales, despliegue, HTTPS final, turnos HU-07 o preparación/no retiro HU-17. Se prueba la elegibilidad y confirmación manual de recetas; no se declara implementado el bloqueo de emisión en una app de turnos todavía vacía.

## Aceptación y reanudación

Documento: Aprobado. Implementación de código y continuación sin pausas: autorizadas por el usuario. Commit al terminar: autorizado en `fdaza`, excluyendo el cambio previo del spec 02. Aceptación funcional del software: pendiente.

T-03-01 a T-03-05 completadas; T-03-06 tiene comprobaciones técnicas y documentación completadas, con revisión visual/móvil/axe pendiente por entorno. Mantener estado Aprobado hasta cerrar esas comprobaciones y registrar aceptación real, sin marcar Implementado automáticamente.
