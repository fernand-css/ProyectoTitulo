# Validación — 02 / Autenticación, roles y auditoría

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-01. Estado: **verificación técnica final aprobada; revisión visual pendiente**.
Entorno: Windows, Python del venv y SQLite temporal creada por el ejecutor de pruebas de Django. La SQLite local de trabajo no fue migrada. En el paso 4 se usó correo en memoria, sin envío real.
Referencia de código: cambios de la spec 02 en el árbol de trabajo de `fdaza`; commit previsto al terminar la implementación completa. El commit anterior del spec aprobado 01 es `fd686ec`.

## Evidencia ejecutada — paso 1

| Comando con `venv/Scripts/python.exe` | Resultado real |
|---|---|
| `manage.py test usuariosapp.tests.test_perfil --noinput` | 7 pruebas aprobadas, 2,114 s; base de pruebas creada y destruida |
| `manage.py check` | Sin problemas |
| `manage.py makemigrations --check --dry-run` | Sin cambios detectados |
| `manage.py test --noinput` | 76 pruebas aprobadas, 5,904 s; base de pruebas creada y destruida |
| `git diff --check` | Sin errores de espacios; avisos de conversión LF/CRLF en archivos previos |

Las siete pruebas nuevas verifican relación única de Perfil, estado inicial sin verificar ni solicitud, persistencia del estado de correo sin reemplazar el vigente, ausencia de asignaciones implícitas, acceso del superusuario sin Perfil, actualización desde la base sin migraciones de `usuariosapp` conservando cuentas/hashes/grupos y acceso del superusuario, y reaplicación de datos preservando perfiles verificados o con solicitud pendiente.

El test de actualización usa `MigrationExecutor` y cuentas sintéticas dentro de la base de pruebas; no una copia de datos locales. Las nuevas migraciones también se aplicaron durante la creación de la base de tests vacía. La migración de datos usa el alias de base del ejecutor y no modifica cuentas ni grupos.

## Evidencia ejecutada — paso 2

| Comando con `venv/Scripts/python.exe` | Resultado real |
|---|---|
| `manage.py test usuariosapp.tests.test_roles usuariosapp.tests.test_comandos coreapp.tests.test_mixins coreapp.tests.test_plantillas --noinput` | 42 pruebas aprobadas, 6,469 s |
| `manage.py check` | Sin problemas |
| `manage.py makemigrations --check --dry-run` | Sin cambios detectados |
| `manage.py test --noinput` | 95 pruebas aprobadas, 12,304 s; base temporal creada y destruida |
| `git diff --check` | Sin errores de espacios; avisos LF/CRLF de archivos previos |

Se agregaron nueve pruebas de habilitación, nueve de comandos y una de contexto, adaptando las pruebas anteriores al rol único y a las etiquetas acordadas. Se verifica acceso para cada rol, rechazo por perfil ausente, rol ausente/múltiple y desactivación, revocación en la siguiente petición con sesión abierta, lectura fresca pese a grupos/flags en caché y conservación del acceso de superusuario activo sin perfil.

Los tests de comandos los ejecutan sobre la SQLite temporal: tres grupos sin tótem, permisos existentes conservados, cuentas sintéticas con un rol y correo sin verificar, repetición sin cambios en hashes/perfiles/grupos, colisión de nombres sin alterar la cuenta previa, ausencia/contraseña débil y fallo en la segunda cuenta sin escrituras parciales, entrada oculta confirmada y cancelación si no coincide. No se ejecutaron comandos de alta sobre la SQLite local ni se enviaron correos.

## Evidencia ejecutada — paso 3

| Comando con `venv/Scripts/python.exe` | Resultado real |
|---|---|
| `manage.py test usuariosapp.tests.test_auditoria usuariosapp.tests.test_admin coreapp.tests.test_auditoria --noinput` | 26 pruebas aprobadas, 4,998 s; se detectó un aviso de fecha sin zona en una prueba y se corrigió antes de la suite final |
| `manage.py check` | Sin problemas |
| `manage.py makemigrations --check --dry-run` | Sin cambios detectados |
| `manage.py test --noinput` | 114 pruebas aprobadas, 16,860 s, sin el aviso anterior; base temporal creada y destruida |
| `git diff --check` | Sin errores de espacios; avisos LF/CRLF de archivos previos |

Las 19 pruebas nuevas cubren login exitoso/fallido, anonimización de intentos fallidos, logout válido frente a GET/CSRF inválido, conexión repetida sin duplicación, catálogo de eventos, limpieza de sesión ante fallo de auditoría y cierre de sesión con aviso técnico sin detalles de excepción. También cubren transacciones de altas demo: dos eventos distintos por cuenta nueva, ninguno al repetir, y rollback de cuentas/perfiles/grupos/eventos si falla una escritura o un alta posterior.

En Admin se comprueban consulta y detalle por superusuario sin datos personales del actor, filtros y búsqueda, entradas inválidas, rechazo de alta/cambio/borrado y ausencia de borrado masivo. Los tres roles operativos no consultan la bitácora ni teniendo `is_staff` y permisos explícitos del modelo; superusuario inactivo y anónimo tampoco acceden. Se usó el cliente de pruebas HTTP de Django; no se realizó inspección visual en navegador.

## Evidencia ejecutada — paso 4

| Comando con `venv/Scripts/python.exe` | Resultado real |
|---|---|
| `manage.py test usuariosapp.tests.test_perfil usuariosapp.tests.test_correo coreapp.tests.test_plantillas --noinput` | 46 pruebas aprobadas, 2,518 s |
| `manage.py check` | Sin problemas |
| `manage.py makemigrations --check --dry-run` | Sin cambios detectados |
| `manage.py test --noinput` | 136 pruebas aprobadas, 17,034 s; base temporal creada y destruida |
| `git diff --check` | Sin errores de espacios; avisos LF/CRLF de archivos previos |

Las 22 pruebas nuevas cubren perfil propio, persistencia de nombres, campos inválidos y errores accesibles, ausencia de cambios por GET, rechazo de campos extra de privilegios/otras cuentas, sesión/habilitación y CSRF, y creación explícita de Perfil de superusuario al guardar. No se crea ese perfil al consultar.

Correo: verificación inicial y nueva, normalización, conservación del correo vigente, reenvío que sustituye el UUID anterior, token alterado/caducado/usado/de otro propósito, rechazo de cuentas inactivas o sin rol, mensajes públicos sin reflejar token, ausencia de login automático al confirmar y rollback ante fallo de envío o auditoría. Las trazas se comprueban sin valores personales ni token.

Una prueba con `TransactionTestCase`, barrera y dos conexiones/hilos contra SQLite temporal confirma el mismo token simultáneamente: un resultado exitoso, un rechazo por consumo previo, un único correo vigente y un único evento `correo.confirmado`. Se verifica GET sin consumo y POST con CSRF usando el cliente HTTP de Django. Los correos permanecen en `locmem`; no se demuestra entrega SMTP ni revisión visual.

## Evidencia ejecutada — paso 5

| Comando con `venv/Scripts/python.exe` | Resultado real |
|---|---|
| `manage.py test usuariosapp.tests.test_login usuariosapp.tests.test_recuperacion usuariosapp.tests.test_auditoria --noinput` | 47 pruebas aprobadas, 305,810 s |
| `manage.py check` | Sin problemas |
| `manage.py makemigrations --check --dry-run` | Sin cambios detectados |
| `manage.py test --noinput --durations 10` | 159 pruebas aprobadas, 41,224 s; incluye el caso adicional de revocación intermedia y rechazo de nueva clave idéntica a la anterior |
| `git diff --check` | Sin errores de espacios; avisos LF/CRLF de archivos previos |

El paso incorpora 23 pruebas nuevas: acceso por cada rol sin exigir correo verificado para login, rechazo de perfil/rol ausente, multirrol o inactividad, fallo de auditoría sin sesión ni fecha de acceso persistida, enlace de recuperación y revocación entre validar y abrir sesión. Los casos previos de `next`, CSRF, logout y auditoría siguen aprobados.

Cambio de clave: contraseña actual, confirmación, validadores, rechazo de la misma clave, conservación de sesión actual, revocación de otra sesión, evento único sin claves y rollback al fallar la auditoría. Recuperación: recorrido por HTTP, respuesta pública idéntica para casos válidos/inexistentes/no coincidentes, correo pendiente sin capacidad de recuperar, correo compartido sin afectar otra cuenta, cuentas inactivas/sin verificar/sin perfil/sin rol/con clave inutilizable, tokens alterados/caducados/usados y UID inválido, CSRF y ausencia de login automático.

Se comprueba que el fallo de entrega no copie el detalle privado al log y mantenga la respuesta general; que un fallo de auditoría revierta hash y deje el token sin consumir; y que recuperar revoque sesiones anteriores. La prueba concurrente con dos conexiones consume un token una vez y escribe un evento. Esta última usa un hasher rápido solo en el test para aislar la concurrencia; las demás conservan la configuración de hashes normal.

Las duraciones corresponden a ejecuciones distintas; no se atribuye aquí la diferencia a una causa comprobada. `--durations` informa casos completos con varias operaciones y no es una prueba del percentil 95 ni de los niveles de servicio del informe. Correo exclusivamente en memoria y base temporal; no se afirma entrega SMTP real ni revisión visual.

## Evidencia ejecutada — paso 6

| Comando con `venv/Scripts/python.exe` | Resultado real |
|---|---|
| `manage.py test usuariosapp.tests.test_gestion_usuarios usuariosapp.tests.test_admin coreapp.tests.test_plantillas --noinput` | 46 pruebas aprobadas, 5,576 s |
| `manage.py check` | Sin problemas |
| `manage.py makemigrations --check --dry-run` | Sin cambios detectados |
| `manage.py test --noinput --durations 10` | 183 pruebas aprobadas, 46,988 s; incluye historial redirigido a bitácora |
| `manage.py test --noinput` | 183 pruebas aprobadas, 45,548 s, tras reforzar rechazo de actores anónimos y mostrar el correo pendiente en cuentas nuevas |
| `git diff --check` | Sin errores de espacios; avisos LF/CRLF de archivos previos |

Las 24 pruebas nuevas cubren listado limitado, alta con clave validada y correo pendiente, edición sin cambiar identificador/clave/privilegios desde el panel, cambio de rol único y estado idempotente, revocación de sesión al desactivar, rechazo de jefaturas/staff/superusuarios/cuenta propia por ID y exclusión de multirrol, rol/cuenta del actor obsoletos, escritura con CSRF y estado explícito, rollback ante fallo de auditoría o envío, y denegación del panel a Técnico/Encargado/anónimo.

Admin: creación de jefatura, rol/grupos adicionales/permisos auditados una vez, rechazo de verificación de correo por POST, cambio de clave de otra cuenta con actor correcto y revocación de sesión, rechazo de rol ausente o grupo operativo como adicional, restricciones incluso a staff con permisos explícitos, grupos de solo lectura, ausencia de borrado directo/masivo, rollback de datos y M2M ante fallo de auditoría, y bitácora técnica en lugar de LogEntry personal. El historial redirigido se comprueba por HTTP.

La prueba concurrente usa dos conexiones/hilos y enfrenta promoción de Técnico a Q.F. por superusuario con edición por Q.F.: si la edición ocurre antes de la promoción puede completarse; si ocurre después se deniega. El estado final es la jefatura y una edición posterior por Q.F. siempre se rechaza. Se comprueban también los campos iniciales del correo pendiente en panel, perfil y Admin sin confirmar silenciosamente el destino.

Estas son pruebas de servicios y cliente HTTP de Django; la revisión visual por navegador y la integración final siguen en el paso 7. SQLite temporal y correo en memoria; no se modificó la base local ni se entregaron correos externos.

## Evidencia ejecutada — paso 7, verificación técnica final

| Comando con `venv/Scripts/python.exe` | Resultado real |
|---|---|
| `manage.py test usuariosapp.tests.test_integracion coreapp.tests.test_plantillas coreapp.tests.test_estaticos --noinput` | 24 pruebas aprobadas, 0,305 s |
| `manage.py check` | Sin problemas |
| `manage.py makemigrations --check --dry-run` | Sin cambios detectados |
| `manage.py test --noinput` | 185 pruebas aprobadas, 43,635 s; base temporal creada y destruida |
| `tools/verificar_spec_02_http.py` | 21 migraciones aplicadas sobre SQLite nueva; repetición demo conserva hashes; flujos HTTP y estáticos aprobados; entorno temporal eliminado |
| `git diff --check` | Sin errores de espacios; avisos LF/CRLF de archivos previos |

Las dos pruebas nuevas verifican navegación por cada rol —incluida una cuenta Técnica con `is_staff`, que no recibe enlace a Admin— y siguen los enlaces locales ofrecidos comprobando destinos existentes/autorizados. También comprueban formularios de login, recuperación, perfil, clave y gestión: una región principal, etiquetas asociadas, identificadores únicos y enlace activo.

La herramienta HTTP ejecutada sobre servidor WSGI en `127.0.0.1` y puerto dinámico usa cookies y CSRF reales. Recorre login Q.F., alta de operador, confirmación del correo, cambio a Encargado, rechazo de gestión para el personal, desactivación/reactivación, bitácora solo consultable, rechazo de edición de trazas, recuperación con clave anterior inválida y token consumido. Comprueba CSS, Alpine y service worker con respuesta 200. No envía correos reales, no muestra claves y no toca la base local; genera sus credenciales sintéticas temporalmente.

El intento de revisión visual quedó bloqueado: el host de navegador informó `The browser access host is unavailable` y la aprobación automática rechazó vincular una ventana existente con contenido ajeno al proyecto. No se inspeccionó ese contenido. Se prepararon vistas sintéticas temporales con formularios sin envío y se solicitó una ventana dedicada o aceptación explícita del límite. Esta revisión y el cierre final siguen pendientes.

## Matriz de comprobaciones previstas

La evidencia automatizada y HTTP real cubre los flujos e integración del módulo. La revisión visual sigue pendiente; no se deduce de que la suite pase.

| RF | Prueba / pasos / comando previsto | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-02-01 | Pruebas de login por rol, errores y `next` | Acceso autorizado y redirección segura | Verificado en `test_login.py`, incluidos rechazos y revocación intermedia | Verificado |
| RF-02-02 | Matriz, perfil ausente, rol ausente/múltiple y excepción administrativa | Denegación por defecto y acceso de superusuario conservado | Verificado en helpers, mixins, inicio, login y panel/Admin | Verificado |
| RF-02-03 | CSRF, logout, cambio de clave y desactivación con sesión abierta | Sesión/contraseña dejan de permitir acceso según spec | Verificado en pruebas de login, roles y cambio de clave | Verificado |
| RF-02-04 | Recuperación en buzón de pruebas; tokens válidos, inválidos, caducados y repetidos | Solo recupera cuenta activa con su correo verificado | Verificado por HTTP y servicios, incluida concurrencia | Verificado |
| RF-02-05 | Edición propia y formulario con campos adicionales | Datos persisten; privilegios no cambian | Verificado en pruebas de perfil, incluidas sesión y CSRF | Verificado |
| RF-02-06 | Confirmación inicial/nuevo correo, sustitución, replay y consumo concurrente | Cambio solo al confirmar; consumo una vez | Verificado en `test_correo.py` con buzón en memoria y concurrencia SQLite | Verificado |
| RF-02-07 | Crear, editar, reasignar y desactivar Técnico/Encargado desde Q.F. | Cuenta válida con un rol y trazabilidad | Verificado en `test_gestion_usuarios.py` | Verificado |
| RF-02-08 | URLs/IDs/POST manipulados y cambios concurrentes; Admin | Sin administración no autorizada de jefaturas ni privilegios | Verificado en gestión/Admin y promoción concurrente | Verificado |
| RF-02-09 | Login exitoso/fallido y logout | Eventos sin credenciales ni identificadores intentados | Verificado nuevamente con el backend y login ampliados | Verificado |
| RF-02-10 | Cambios de cada tipo y desde Admin; simular fallo al auditar | Eventos sin duplicados; cambios persistentes revierten ante fallo | Verificado en demo, perfil, correo, claves, panel y Admin, incluidos permisos/M2M y rollback | Verificado |
| RF-02-11 | Acceso directo y modificación del registro desde Admin por cada rol | Solo consulta por superusuario; sin edición/borrado | Verificado en `test_admin.py`, incluidos permisos explícitos y acciones masivas | Verificado |
| RF-02-12 | Comandos de preparación ejecutados dos veces | Sin duplicados ni cambio de claves existentes | Verificado por `test_comandos.py` en base temporal | Verificado |

## Regresión de la base

Ejecutados check, control de migraciones y suite final con **185** pruebas aprobadas, frente a las 69 históricas de la base. Cubre esquema, actualización, habilitación, preparación, auditoría, perfil, correo, claves, gestión y navegación. La verificación HTTP adicional aplica 21 migraciones en una SQLite nueva. La revisión visual y el cierre del paso 7 siguen pendientes.

La spec 01 conserva su [evidencia histórica](../01-base-del-proyecto/validation.md) de 69 pruebas y 19 migraciones; no se reutiliza como aprobación de la spec 02.

## Revisión visual si aplica

Pendientes capturas de escritorio/móvil, recorrido visual, teclado y adaptación en navegador. El acceso al navegador quedó bloqueado según la evidencia anterior. Navegación, estructura de formularios y contraste tienen comprobación automatizada; no equivalen a revisión visual, auditoría integral WCAG ni evaluación con cinco usuarios. El buzón de pruebas no demuestra entrega SMTP real.

## Límites y fallos

El código y su verificación técnica están completados; sigue pendiente revisión visual y cierre. Si falla registrar logout se elimina la sesión y se informa por log técnico, sin afirmar auditoría completa de esa operación. No se enviaron correos reales ni se modificó la base local. El correo externo no es transaccional con la base y no se garantiza entrega exactamente una vez. Los grupos en Admin son de solo lectura y no existe edición directa de Perfil ni borrado de cuentas para evitar escrituras fuera de los servicios. No hubo despliegue ni commit final todavía.

## Aplicación y reversión

Las migraciones solo se ejecutaron en el entorno de pruebas, incluyendo retroceso y reaplicación de la migración de datos. No hubo despliegue ni aplicación sobre la base local. La migración de datos revierte con una operación vacía para conservar estados existentes; deshacer la migración de esquema elimina Perfil, como se advierte en [plan.md](plan.md). No se afirma recuperación de datos comprobada mediante respaldo.

## Aceptación funcional

Pendiente. Las respuestas del equipo aclararon requisitos; no representan aceptación del funcionamiento ni aprobación automática del borrador.
