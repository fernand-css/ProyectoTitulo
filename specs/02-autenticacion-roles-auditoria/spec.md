# SPEC 02 — Autenticación, roles y auditoría

> **Estado:** Implementado
> **Depende de:** [SPEC 01 — Base del proyecto](../01-base-del-proyecto/spec.md)
> **Fecha:** 2026-11-01
> **Objetivo:** Permitir el acceso del personal según su rol, la recuperación y edición segura de su cuenta y la administración de usuarios por la Q.F., dejando registro de sus operaciones.

Módulo solicitado: `usuariosapp`, con integración en `coreapp`.
Fuente: solicitud y respuestas del equipo del 2026-11-01; HU-01, HU-02, HU-03 y RNF-01 de [Informe.md](../../docs/Informe.md).
Implementación autorizada: SÍ, mediante invocación de `spec-impl` y la instrucción de ejecución registrada abajo. Revisión documental del usuario: Aprobado.

Avance: código funcional y verificación técnica final completados; cierre de T-02-07, revisión visual y commit final pendientes. La aceptación funcional del usuario sigue pendiente.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

La base tiene login y logout mínimos, constantes de roles, un mixin de autorización y un registro genérico de auditoría. Todavía no existen perfiles, creación de grupos, recuperación de contraseña, edición de datos ni administración de usuarios desde la aplicación.

El personal debe ingresar con usuario y contraseña; la Q.F. debe administrar las cuentas operativas desde un panel propio. Cada acción protegida debe comprobar permisos en el servidor y las operaciones de este módulo deben quedar vinculadas a su actor y fecha.

## Actores y permisos

Los tres roles operativos son **Q.F.**, **Técnico en Farmacia** y **Encargado de terreno**. Q.F. corresponde a la Jefa de Farmacia del informe. Cada cuenta operativa tiene exactamente uno. El superusuario es una condición administrativa de Django y el tótem es público; no son roles operativos adicionales.

| Acción / datos | Anónimo | Técnico | Encargado de terreno | Q.F. | Superusuario |
|---|---|---|---|---|---|
| Iniciar sesión / solicitar recuperación | Sí | Sí, sin sesión | Sí, sin sesión | Sí, sin sesión | Sí, sin sesión |
| Consultar y editar el perfil propio | No | Sí | Sí | Sí | Sí |
| Cambiar la contraseña propia / cerrar sesión | No | Sí | Sí | Sí | Sí |
| Listar, crear y editar cuentas operativas gestionables | No | No | No | Sí | Sí |
| Activar/desactivar y asignar rol Técnico o Encargado | No | No | No | Sí | Sí |
| Administrar jefaturas y privilegios de Django | No | No | No | No | Sí, en Django Admin |
| Consultar la bitácora de auditoría | No | No | No | No | Sí, en Django Admin |
| Modificar o borrar la bitácora desde las interfaces | No | No | No | No | No |

Una cuenta gestionable por Q.F. tiene rol Técnico o Encargado, sin `is_staff`, `is_superuser` ni rol Q.F. No puede modificar otras jefaturas, su propia cuenta desde el panel administrativo, permisos individuales ni grupos arbitrarios. El perfil propio tiene un formulario separado sin campos de privilegios.

Las cuentas inactivas no acceden a vistas privadas, incluso con una sesión previa. Una cuenta operativa sin perfil o sin un único rol válido no accede a funciones privadas y recibe una explicación de acceso pendiente de regularización. Se conserva el acceso del superusuario de la base aunque todavía no tenga perfil; para recuperar su contraseña por correo debe registrar y verificar ese correo.

## Alcance y exclusiones

Incluye HU-01, HU-02 y HU-03; logout por POST; cambio de contraseña propia; perfil con nombres, apellidos y correo; verificación de correo; grupos e inicio según rol; panel de usuarios para Q.F.; administración de jefaturas por superusuario; comando de datos sintéticos; auditoría de autenticación y gestión de cuentas.

La edición de perfil se extiende al Encargado de terreno para mantener un flujo común del personal, conforme a la selección del equipo de editar el perfil del funcionario. Esta extensión respecto de los actores de HU-03 queda propuesta para revisión en este borrador.

La gestión de ventanillas pertenece a **HU-10, en una spec de turnos**. Se registra que corresponde a Q.F.; aquí no se crean sus modelos, pantallas, asignaciones ni algoritmo. Los permisos de recetas, turnos, entregas e indicadores se concretarán en sus propias specs. «Administrar y demás» no concede permisos técnicos de superusuario.

Quedan fuera: registro público, login con RUT, cuentas de pacientes, teléfono y RUT del funcionario, integración con Rayén, MFA/SSO, sesiones sin conexión, WebSocket, notificaciones de negocio, despliegue y configuración real de correo o HTTPS. La verificación de correo necesaria para cuentas pertenece a este módulo, sin depender de la futura spec de notificaciones.

## Historias y flujo

1. El personal ingresa usuario y contraseña; una cuenta activa y habilitada accede al inicio con su rol. Los datos inválidos muestran un error general.
2. Desde «¿Olvidaste tu contraseña?» ingresa usuario y correo verificado. La respuesta pública es la misma para coincidencia y ausencia de cuenta; si corresponde, recibe un enlace de un solo uso y confirma una contraseña válida.
3. En «Mi perfil» modifica nombre y apellidos. Un cambio de correo queda pendiente hasta abrir el enlace enviado al nuevo correo; el anterior continúa sirviendo para recuperar la cuenta hasta la confirmación.
4. La Q.F. entra a «Usuarios», crea o modifica técnicos y encargados, asigna un rol y activa/desactiva cuentas. Las jefaturas se administran en Django Admin por el superusuario.
5. El superusuario consulta registros de auditoría sin poder editarlos desde las interfaces.

## Requisitos funcionales

- **RF-02-01 — Autenticación:** con usuario y contraseña válidos de una cuenta activa y habilitada, iniciar sesión y mostrar su rol; rechazar campos vacíos, credenciales incorrectas y cuentas inactivas sin revelar la causa específica de autenticación. Conservar `next` solo para destinos internos seguros.
- **RF-02-02 — Roles:** crear idempotentemente los tres grupos y exigir un único rol operativo a cuentas internas ordinarias. Validar permisos en cada petición, incluidos accesos directos y formularios manipulados; conservar el acceso administrativo del superusuario y el tótem público.
- **RF-02-03 — Sesión y contraseña:** cerrar sesión exclusivamente por POST con CSRF. Permitir cambiar la contraseña propia con la actual y confirmación de la nueva, aplicando los validadores de Django. Una cuenta desactivada pierde el acceso privado en la siguiente petición.
- **RF-02-04 — Recuperación:** ofrecer el enlace desde el login y enviar la recuperación solo al correo vigente verificado de la cuenta indicada. Rechazar enlaces alterados, caducados o reutilizados, confirmar la nueva contraseña e invalidar la anterior. No revelar si existe la cuenta en la respuesta de solicitud.
- **RF-02-05 — Perfil propio:** consultar y editar nombres y apellidos y solicitar cambio de correo. Validar obligatoriedad de nombres, apellidos y correo para nuevas cuentas operativas y formularios de edición. Nunca permitir cambiar usuario, rol o privilegios desde este formulario.
- **RF-02-06 — Correo verificado:** registrar el correo inicial como no verificado y enviar su confirmación. Para un cambio, conservar el correo vigente hasta verificar el nuevo. Una solicitud posterior sustituye la anterior; un enlace caducado, alterado, anterior o utilizado no modifica el correo. Permitir solicitar otro enlace desde el perfil autenticado. La falta de verificación impide recuperar por correo, pero no el login de una cuenta habilitada.
- **RF-02-07 — Panel Q.F.:** listar y crear cuentas gestionables; editar sus nombres, apellidos y correo; asignar Técnico o Encargado y activar/desactivar. La creación incluye usuario único, contraseña inicial con confirmación y validadores, y correo pendiente de verificación. Un cambio administrativo de correo también requiere verificación y no sustituye silenciosamente el vigente. No borrar cuentas físicamente ni otorgar a Q.F. acceso a Django Admin por este rol.
- **RF-02-08 — Administración superior:** permitir al superusuario administrar jefaturas y cuentas desde Django Admin, manteniendo un único rol para cuentas operativas ordinarias. Impedir que la Q.F. acceda a cuentas o campos administrativos fuera de su matriz, incluso cambiando IDs, URLs o enviando campos adicionales.
- **RF-02-09 — Auditoría de acceso:** registrar login exitoso y fallido y logout con acción, actor cuando pueda identificarse sin ambigüedad, referencia de cuenta cuando corresponda y fecha. Un intento fallido desconocido se registra sin guardar el usuario escrito ni credenciales.
- **RF-02-10 — Auditoría de cambios:** registrar creación/edición/activación/desactivación de cuentas, asignación de roles, cambios de perfil, confirmación de correo y cambios/restablecimientos de contraseña, incluidos los realizados desde Admin. Los cambios persistentes y su evento deben confirmarse juntos, sin eventos duplicados para la misma operación.
- **RF-02-11 — Consulta de auditoría:** permitir solo al superusuario consultar la bitácora en Admin, con filtros por acción, fecha y actor y búsqueda por referencia técnica. No exponer contraseñas, tokens, enlaces, correo, nombres, datos de pacientes ni valores de campos cambiados en los registros de auditoría.
- **RF-02-12 — Demostración reproducible:** proporcionar un comando explícito e idempotente para preparar grupos y cuentas sintéticas de los tres roles. No crear usuarios ni asignar roles silenciosamente durante el arranque; no restablecer contraseñas de cuentas existentes ni incluir claves fijas en el repositorio.

## Datos y reglas

Se conserva `auth.User`, con su nombre de usuario único y contraseña con hash. Nombres, apellidos y correo se reutilizan de ese modelo; el nuevo `Perfil` guarda exclusivamente el estado de verificación y la solicitud de correo pendiente. No se duplica el rol en `Perfil`: los grupos son su fuente de verdad.

La recuperación solicita **usuario y correo** para identificar una cuenta sin imponer una nueva unicidad global sobre `auth.User.email`. Se valida el formato del correo y se compara normalizado para este flujo. No se migran correos existentes ni se dan por verificados automáticamente. La definición de normalización y tokens está propuesta en [plan.md](plan.md).

La desactivación conserva la cuenta y su historial. Los cambios de rol se comprueban en cada acceso, sin depender solo del menú o de datos guardados en la sesión. Se mantienen los nombres internos de grupos existentes; las etiquetas visibles acordadas se traducen en la presentación.

## Criterios de aceptación

| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-02-01 | Cada rol ingresa credenciales válidas; luego prueba error, campos vacíos e inactividad | Acceso correcto por rol; los casos inválidos no crean una sesión habilitada. |
| RF-02-01 | Se proporciona `next` externo | No se redirige fuera del sitio. |
| RF-02-02 | Cuenta sin perfil, sin rol o con dos roles; superusuario existente sin perfil | Las tres primeras no acceden a funciones privadas; el superusuario conserva acceso administrativo. |
| RF-02-03 | Logout GET, POST sin CSRF y POST válido | Se rechazan los dos primeros; el último elimina la sesión. |
| RF-02-03 | Se cambia contraseña o se desactiva una cuenta con sesión abierta | La clave anterior deja de autenticar; la cuenta inactiva no accede en la siguiente petición. |
| RF-02-04 | Solicitud de cuenta válida, inexistente, inactiva o con correo sin verificar | Misma respuesta pública; solo la válida recibe recuperación. |
| RF-02-04 | Enlace válido, alterado, caducado o reutilizado | Solo el válido permite una nueva contraseña confirmada; el resto no cambia la cuenta. |
| RF-02-05 | Se guarda perfil válido o se envían campos de privilegios | Los datos válidos persisten; ningún campo de privilegios enviado altera la cuenta. |
| RF-02-06 | Se solicita correo nuevo y luego se confirma | Antes sigue vigente el anterior; después se usa el nuevo, verificado. |
| RF-02-06 | Se usa un enlace anterior, caducado, alterado o ya consumido | No cambia el correo ni habilita recuperación con un destino pendiente. |
| RF-02-07 | Q.F. crea un Técnico, lo cambia a Encargado y lo desactiva | Se conserva un único rol; la cuenta pierde acceso y queda su historial. |
| RF-02-08 | Q.F. intenta alterar jefatura, cuenta staff, superusuario, su rol o campos técnicos | La operación se rechaza sin cambios; técnicos y encargados tampoco acceden al panel. |
| RF-02-09 | Login exitoso, fallido conocido/desconocido y logout válido | Existen eventos sin credenciales ni identificadores introducidos en intentos fallidos. |
| RF-02-10 | Cada cambio se ejecuta desde panel, perfil o Admin; se simula fallo de auditoría | Se registra una vez; los cambios persistentes no quedan confirmados sin su evento. |
| RF-02-11 | Q.F., Técnico y Encargado intentan consultar bitácora; superusuario consulta | Solo el superusuario obtiene resultados; ninguna interfaz permite editarlos o borrarlos. |
| RF-02-12 | Se ejecuta dos veces el comando de demostración | No duplica cuentas/grupos ni cambia claves existentes; solo hay datos sintéticos. |

## No funcionales

Reutilizar las plantillas accesibles de la base, etiquetas visibles, errores asociados, navegación por teclado y confirmaciones en español de Chile. Revisar móvil y contraste conforme al RNF-04; las comprobaciones de este módulo no equivalen a una auditoría integral ni a la prueba con cinco usuarios.

Mantener CSRF, hashes y validadores de Django y cookies seguras fuera de desarrollo. Usar correo de consola en desarrollo y buzón de pruebas en tests; no enviar correos reales durante esta fase. HTTPS del entorno final sigue pendiente de despliegue; no se declara cumplido RNF-01 en su totalidad.

## Compatibilidad

Preservar las URLs de login/logout, el acceso del superusuario, `auth.User`, SQLite y un único `cesfam/settings.py`. Mantener los contratos públicos de salud y service worker. Reutilizar `ModeloAuditado`, `RegistroAuditoria` y `registrar_accion` sin incorporar datos personales al registro.

El endurecimiento para cuentas operativas sin perfil/rol es deliberado; deberá reflejarse en las pruebas. No asignar roles por inferencia a usuarios existentes.

## Decisiones tomadas y alternativas

- Usuario y contraseña; se descarta login con RUT para este alcance.
- HU-01, HU-02 y HU-03 juntas; recuperación por correo y verificación del correo nuevo.
- Panel propio para Q.F.; se descarta otorgarle privilegios generales de Django Admin.
- Un rol operativo por cuenta; Q.F. administra técnicos y encargados y el superusuario administra jefaturas.
- Etiquetas visibles Q.F., Técnico en Farmacia y Encargado de terreno, conservando los nombres internos ya existentes para compatibilidad.
- Auditoría completa de este módulo, consultable solo por superusuario; operaciones de negocio y ventanillas se integran en sus propias specs.

## Supuestos y decisiones pendientes

No quedan decisiones bloqueantes sobre el alcance conversado. La extensión de edición de perfil al Encargado y las precisiones de seguridad descritas son propuestas de este borrador, sujetas a revisión. Las rutas, estructura de datos de verificación y descomposición técnica de `plan.md` son diseño propuesto, no componentes ya implementados.

## Revisión y cambios

2026-11-01: equipo seleccionó 1A/2A/4C/5A y precisó que la Q.F. administra usuarios. En el segundo bloque eligió panel propio, administración limitada a técnicos/encargados y ventanillas en la spec de turnos. Indicó los tres nombres de rol visibles. La elección inicial 3A queda ajustada por esas precisiones posteriores.

Aprobación del documento: Aprobado por el usuario antes de invocar `spec-impl`. Aceptación funcional: pendiente.

## Acuerdo de ejecución

Por instrucción del usuario del 2026-11-01: conservar los cambios existentes, implementar en la rama actual `fdaza` sin crear una nueva y hacer commit cuando termine la implementación completa. No se realizan commits intermedios. El ritmo de revisión por pasos de `spec-impl` se mantiene mientras no se indique otro.
