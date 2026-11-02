# Plan técnico — 02 / Autenticación, roles y auditoría

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Validación: [validation.md](validation.md).
Fecha: 2026-11-01. Estado: código y verificación técnica final completados; revisión visual y cierre de paso 7 pendientes. Autorización de implementación: concedida por el usuario, en `fdaza` y con commit al terminar.

## Inspección de la base

Leídos `CLAUDE.md`, el índice y los cuatro documentos de la spec 01, las plantillas SDD, HU-01/02/03/10 y RNF del informe. Se inspeccionaron `usuariosapp/urls.py`, modelos, vistas y Admin vacíos, pruebas de login, `coreapp/roles.py`, `mixins.py`, `models.py`, `auditoria.py`, `context_processors.py`, vistas, configuración y plantillas de login y navegación.

En la inspección inicial existían login/logout de Django, tres constantes de grupos, `RolRequeridoMixin`, utilidades de auditoría y correo configurable. Todavía no existían `Perfil`, recuperación, verificación ni panel de usuarios. El árbol tiene cambios previos sin commit; conservarlos. Las 69 pruebas de la spec 01 son evidencia histórica.

Paso 1: se incorporaron `Perfil`, `0001_initial.py`, `0002_perfiles_existentes.py` y siete pruebas en `usuariosapp/tests/test_perfil.py`. Se comprobaron migraciones sobre la base temporal de tests y actualización desde el esquema sin migraciones de usuarios. La suite de esta sesión pasó con 76 pruebas; detalle en [validation.md](validation.md). Los componentes de los pasos siguientes siguen pendientes.

Paso 2: se incorporaron `estado_acceso`, etiquetas, `CuentaHabilitadaMixin`, protección del inicio, aviso 403 y comandos `crear_roles`/`crear_usuarios_demo`, con servicios explícitos y pruebas de habilitación/conservación. El comando de demostración pide contraseña oculta con confirmación o recibe `CESFAM_DEMO_PASSWORD` por entorno para `--noinput`; valida cuentas nuevas y conserva íntegramente las existentes. Ambas operaciones admiten `--database`. La suite completa pasó con 95 pruebas; la SQLite local no fue modificada. Login y auditoría ampliados siguen en sus pasos posteriores.

Paso 3: `registrar_evento` añade un catálogo de acciones de cuenta y registro sin actor identificado para login fallido, conservando `registrar_accion`. Las señales de autenticación se conectan en `UsuariosappConfig.ready` con identificadores únicos. El login elimina la sesión preparada si falla auditar; logout continúa revocándola y registra un aviso técnico fijo si falla su evento. Las altas de demostración escriben creación/asignación de rol en su transacción; sin duplicar al repetir. `RegistroAuditoriaAdmin` solo permite consulta a superusuarios activos, con referencias técnicas y filtros de actor/acción/fecha/referencia. La suite pasó con 114 pruebas. La integración de cambios de perfil, correo, contraseña y panel/Admin de cuentas corresponde a los pasos siguientes.

## Diseño propuesto

Paso 7, avance técnico: navegación con enlaces solo a destinos autorizados, sección activa con `aria-current`, acceso a gestión desde el inicio de Q.F. y CSS para selectores, formularios y tarjetas adaptables. `test_integracion.py` recorre enlaces reales por rol y comprueba etiquetas, identificadores únicos y estructura de los formularios. La suite final pasó con 185 pruebas.

Se incorpora `tools/verificar_spec_02_http.py` como evidencia reproducible fuera del cliente de tests: crea una SQLite temporal, aplica migraciones, prepara cuentas sintéticas, arranca WSGI en loopback con puerto dinámico, recorre flujos con cookies/CSRF reales y cierra/elimina exclusivamente su entorno temporal. Repetir las cuentas demo conserva hashes. Correo solo en memoria. La ejecución aplicó 21 migraciones y pasó alta, confirmación, edición/rol, activación/desactivación, restricciones, bitácora y recuperación. La base local permanece sin modificar.

Revisión visual: el host de navegador no está disponible y el acceso a una ventana nativa existente fue rechazado automáticamente por contener información ajena al proyecto. Se preparó un entorno temporal de vistas sintéticas de solo lectura; está pendiente una ventana dedicada autorizada o la aceptación explícita del límite. No se han comprobado capturas de escritorio/móvil ni se afirma certificación WCAG.

Paso 6 implementado: panel paginado de cuentas operativas con `GestionUsuariosView`, alta/edición con `GestionCuentaView` y estado solo por POST. `cuentas_gestionables` exige un único rol Técnico/Encargado y excluye jefaturas, staff, superusuarios y la cuenta del actor. Los formularios del panel no contienen privilegios ni cambios de contraseña para cuentas existentes. Los servicios revalidan actor y destino después de adquirir la escritura de sus filas; en SQLite serializa las operaciones y evita administrar una cuenta ya promovida.

`CuentaAdmin` sustituye al Admin predeterminado de User y queda restringido al superusuario. Su formulario ofrece un rol único, flags, permisos individuales, grupos adicionales no operativos y contraseña opcional confirmada. Las altas/ediciones, relaciones M2M, estados y claves pasan por servicios auditados; `save_related` no vuelve a escribirlas. El correo vigente nunca se sustituye antes de verificar el solicitado. Para cuentas nuevas sin correo vigente se muestra el pendiente en los formularios, sin marcarlo como verificado.

Los grupos son de solo lectura en Admin, los perfiles no tienen una interfaz de edición directa y no hay borrado de cuentas ni acciones masivas. Esto cierra rutas que eludirían los contratos. El historial de User redirige a la bitácora técnica filtrada por cuenta; se evita duplicar datos personales en LogEntry. Los servicios registran actor y destino correctos, incluidas claves cambiadas por el superusuario sobre otra cuenta. Una promoción concurrente a Q.F. deja la cuenta fuera de la gestión posterior por Q.F. La suite final de este paso pasó con 183 pruebas.

Paso 5 implementado: `BackendPersonal` extiende `ModelBackend` y rechaza nuevas autenticaciones de cuentas sin habilitación; mantiene la carga de sesiones activas para que los mixins expliquen los casos de regularización. `IniciarSesionView` revalida cuenta/hash en una transacción antes de abrir sesión y auditar; una revocación intermedia recibe el error general y un evento fallido. `AUTHENTICATION_BACKENDS` sustituye el backend predeterminado: sesiones anteriores que guardaron su ruta necesitan volver a iniciar sesión.

`RecuperacionForm` selecciona por usuario exacto y correo vigente normalizado/verificado, sin imponer unicidad global de correo. Reutiliza vistas y tokens de Django. Errores de entrega producen solo un aviso técnico fijo y mantienen la respuesta pública general. La confirmación retira el token de la URL mediante el flujo estándar de sesión de Django; no inicia sesión automáticamente.

`cambiar_clave` y `restablecer_clave` serializan la escritura antes de consultar el estado actual, aplican validadores, exigen una clave distinta y guardan hash/evento juntos. El reset revalida el token contra la cuenta actual dentro de esa transacción. Cambio autenticado: conservar la sesión actual con `update_session_auth_hash` y revocar las demás. Recuperación: revocar sesiones anteriores y exigir login con la nueva clave. Una prueba concurrente de reset obtiene un solo consumo/evento. La suite pasó con 159 pruebas; panel/Admin de cuentas y revisión final siguen pendientes.

Paso 4 implementado: `PerfilForm` limita campos a nombres, apellidos y correo; vistas de perfil/reenvío requieren cuenta habilitada y las escrituras se autorizan también en servicios. Se agregan confirmación pública GET sin consumo y POST con CSRF, plantillas, correo de verificación y acceso «Mi perfil» en navegación. Los servicios serializan la edición antes de leer sus datos; la confirmación consume el UUID mediante el primer UPDATE condicional, audita y modifica el correo en la misma transacción. Los bloqueos transitorios de SQLite se reintentan hasta seis veces fuera de transacciones externas, con esperas breves acotadas. El envío ocurre dentro de la transacción: si falla el backend se revierten datos y auditoría. Una entrega externa seguida de fallo de commit podría dejar un correo con enlace inválido; no se garantiza entrega de email exactamente una vez.

La firma usa propósito propio, cuenta, destino pendiente y UUID, con `PASSWORD_RESET_TIMEOUT`. Perfil y confirmación impiden caché; la confirmación añade `Referrer-Policy: no-referrer`. La recuperación de contraseña y el panel todavía están pendientes. La suite actual pasó con 136 pruebas; detalle en la validación.

Extender `usuariosapp` y reutilizar `coreapp`, sin crear otra app ni cambiar `AUTH_USER_MODEL`.

- `usuariosapp/models.py`: `Perfil` y estado de verificación.
- Nuevos `usuariosapp/forms.py` y `services.py`: formularios con listas explícitas de campos, operaciones de cuentas, roles, perfil y correo dentro de transacciones.
- `usuariosapp/views.py` y `urls.py`: vistas de clase, autenticación existente extendida, recuperación, perfil y panel Q.F. Aplicar autorización tanto en vistas como en servicios y consultas de cuentas gestionables.
- Nuevo `usuariosapp/signals.py`, conectado una vez desde `apps.py`: eventos de autenticación. Los cambios administrativos se auditan explícitamente en servicios; evitar duplicar eventos por combinar señales y servicios.
- `usuariosapp/admin.py`: administración superior con las mismas reglas y servicios de cuentas/perfil. Los cambios de grupos o permisos hechos mediante Admin también deben auditarse; impedir que una edición M2M eluda la validación de rol único.
- `coreapp/roles.py`: conservar `JEFA = "Jefa de Farmacia"`, `TECNICO = "Técnico en Farmacia"` y `ENCARGADO = "Encargado de entrega"`; añadir el mapeo de presentación Q.F. / Técnico en Farmacia / Encargado de terreno. `TOTEM` continúa público.
- `coreapp/mixins.py`, contexto e inicio: control de cuenta activa/habilitada por petición y presentación según rol; el menú no sustituye controles del servidor.
- `coreapp/auditoria.py` y `admin.py`: eventos de autenticación con destino opcional y consulta de solo lectura de `RegistroAuditoria`.

## Mapa por requisito

Todas las rutas nuevas de esta tabla son propuestas.

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-02-01 | `usuariosapp/urls.py`, `views.py`, nuevo `forms.py`, login existente | Login y mensajes compatibles | Pruebas positivas, negativas y `next` |
| RF-02-02 | `coreapp/roles.py`, `mixins.py`, contexto, `coreapp/views.py`, nuevo `usuariosapp/services.py` | Grupos, habilitación y etiquetas | Matriz de roles y sesión previa |
| RF-02-03 | `usuariosapp/views.py`, `urls.py`, nuevas plantillas de contraseña | Logout y cambio de contraseña | CSRF y clave anterior inválida |
| RF-02-04 | Nuevos formularios/servicios de recuperación y plantillas `registration/` | Recuperación por usuario y correo verificado | Buzón de pruebas y tokens inválidos |
| RF-02-05/06 | `usuariosapp/models.py`, nuevos servicios/formularios, migración y plantillas | Perfil y verificación de correo | Persistencia, suplantación y confirmación concurrente |
| RF-02-07/08 | `usuariosapp/views.py`, servicios, Admin y nuevas plantillas `usuarios/` | Panel Q.F. y administración superior | IDs manipulados, privilegios y alcance de consulta |
| RF-02-09/10 | Nuevas señales, servicios y cambios en `coreapp/auditoria.py` | Eventos sin secretos y atomicidad | Conteo por acción y rollback |
| RF-02-11 | `coreapp/admin.py` | Registro consultable solo por superusuario | Consulta permitida; escritura y acceso ajeno denegados |
| RF-02-12 | Nuevos comandos `crear_roles` y `crear_usuarios_demo` | Preparación explícita e idempotente | Dos ejecuciones sin duplicados ni cambio de claves |

## Datos y contratos

`auth.User` conserva usuario, hash, nombres, apellidos, correo vigente, actividad y grupos. No se modifica el modelo de usuario de Django. Perfil propuesto:

| Campo | Contrato propuesto |
|---|---|
| `usuario` | OneToOne con `settings.AUTH_USER_MODEL`, relación inversa `perfil` |
| `correo_verificado_en` | Fecha/hora nullable; nulo impide recuperación por correo |
| `correo_pendiente` | EmailField vacío si no hay solicitud; nunca utilizado para recuperar antes de confirmar |
| `solicitud_correo` | UUID nullable que cambia en cada solicitud, no una credencial de autenticación por sí solo |

Nombres/apellidos se guardan en `auth.User`; el rol solo en `groups`. Formularios operativos requieren un único grupo de los tres y datos personales obligatorios. Mantener longitud y unicidad del `username` existentes. No imponer RUT, teléfono ni unicidad global de correo. Normalizar el correo del flujo eliminando espacios exteriores y comparando sin distinguir mayúsculas; conservar el destino validado para el envío.

La creación desde panel/Admin prepara `Perfil` explícitamente. Una migración de datos crea perfiles para cuentas existentes con verificación pendiente, sin inventar roles ni marcar correos como verificados. El login del superusuario anterior se conserva. Altas por otras vías sin perfil quedan sin habilitación operativa hasta regularizarlas.

La contraseña inicial se introduce dos veces y se valida/hashea mediante Django; no se envía por correo ni se guarda en bitácora. La verificación inicial puede solicitarse desde el perfil autenticado. Cambiar o confirmar correo siempre invalida cualquier solicitud anterior.

Para verificar correo, usar firma con marca temporal y un propósito propio, vinculada a usuario, correo pendiente y UUID vigente. Usar el plazo configurable `PASSWORD_RESET_TIMEOUT` también para esta confirmación y documentarlo; sin añadir un tiempo contractual nuevo. GET muestra confirmación y POST con CSRF consume el enlace. La confirmación realiza una actualización condicional dentro de `transaction.atomic()` para consumir el UUID una vez, incluso en SQLite; no basarse en `select_for_update()` como garantía allí.

Para recuperar contraseña, reutilizar las vistas/tokens de Django con formulario de selección por usuario y correo vigente verificado. No aceptar un correo pendiente. Enlaces de verificación y recuperación tienen propósitos distintos. La respuesta visible de solicitud es genérica para todos los casos; no se afirma resistencia temporal perfecta a enumeración. El cambio de contraseña utiliza los validadores existentes y los contratos de sesión de Django; no introducir almacenamiento propio de contraseñas.

Propuesta de rutas, conservando las existentes:

| Ruta bajo `/usuarios/` | Uso |
|---|---|
| `entrar/`, `salir/` | Login existente; logout POST |
| `perfil/`, `perfil/correo/solicitar/` | Consulta/edición propia y nueva confirmación |
| `verificar-correo/<token>/` | Confirmación del correo pendiente |
| `clave/cambiar/` | Cambio autenticado |
| `clave/recuperar/`, `clave/enviada/`, `clave/restablecer/<uidb64>/<token>/`, `clave/lista/` | Flujo de recuperación |
| `gestion/`, `gestion/nuevo/`, `gestion/<pk>/editar/`, `gestion/<pk>/estado/` | Panel de usuarios para Q.F. y superusuario |

Los cambios se realizan por POST con CSRF. Los endpoints de gestión filtran cuentas y vuelven a comprobar actor, destino, rol y campos permitidos dentro del servicio. No hay borrado físico ni edición de privilegios desde ese panel. Evitar que cambios concurrentes de rol permitan administrar una cuenta que acaba de convertirse en jefatura: la autorización del cambio y su escritura deben quedar protegidas en la misma operación transaccional, con actualización condicional de los datos de habilitación pertinentes o serialización de la operación y pruebas en SQLite.

Auditoría: reutilizar las columnas `usuario`, `accion`, `objeto_tipo`, `objeto_id`, `creado_en`. Mantener `registrar_accion` para objetos guardados y añadir un helper de evento sin objeto para intentos de autenticación. Un login fallido se registra con actor nulo y referencia `auth.User` / `no-identificado`, sin copiar los valores enviados. Catálogo propuesto: `auth.login`, `auth.login_fallido`, `auth.logout`, `usuario.creado`, `usuario.editado`, `usuario.activado`, `usuario.desactivado`, `usuario.rol_cambiado`, `perfil.editado`, `correo.confirmado`, `clave.cambiada` y `clave.restablecida`.

Cada evento describe una transición; una operación que cambia perfil y rol puede generar una vez cada evento distinto. No registrar solicitudes de recuperación como cambios de contraseña consumados. Actor es la cuenta responsable; referencia es la cuenta afectada. No almacenar contraseñas, tokens, identificadores introducidos al fallar login ni valores personales anteriores/nuevos. Admin utiliza estos mismos servicios y registra asignación/retiro de privilegios administrativos con acciones específicas, sin duplicar los eventos automáticos de login.

Los cambios persistentes y auditoría se confirman en la misma transacción. Si falla registrar un login exitoso, no dejar una nueva sesión autenticada. El logout siempre elimina la sesión aunque falle la auditoría; registrar el fallo técnico sin secretos y no presentar esa operación como evidencia de auditoría completa.

## Permisos e interfaz

Aplicar la matriz de [spec.md](spec.md). El panel propio no exige `is_staff`; Q.F. no puede abrir Admin por su rol. El superusuario conserva su excepción. Denegar acceso por URL/ID/POST manipulado, no solo ocultar enlaces. Cuentas inactivas o sin habilitación no acceden al panel ni al inicio operativo.

Reutilizar `templates/components/Layout/base.html` y `base_publica.html`. Añadir plantillas de perfil/panel en `templates/usuarios/` y de contraseña/correos en `templates/registration/`. Actualizar navbar con Mi perfil y Usuarios según permisos y usar el mapeo de etiquetas. Conservar los enlaces existentes y mostrar únicamente módulos que tengan vistas reales. Reutilizar CSS/Alpine de la base.

## Migraciones y reversión

Proponer `usuariosapp/migrations/0001_initial.py` para Perfil y una migración de datos posterior para perfiles existentes, ambas aún no creadas. Crear grupos mediante comando idempotente explícito; no asignar roles a cuentas existentes automáticamente. Verificar en una SQLite temporal tanto base vacía como actualización de una copia sintética de la base previa.

Antes de aplicar sobre un entorno autorizado, respaldar su SQLite. La reversión de las migraciones elimina el estado de verificación y sus solicitudes; exige exportarlo o restaurar el respaldo si debe conservarse. No borrar grupos/cuentas existentes al revertir código ni retirar trazas de auditoría. No ejecutar migraciones productivas en este flujo.

## Plan de implementación

1. Crear Perfil y migraciones de esquema/datos; comprobar acceso del superusuario y la actualización desde base 01.
2. Implementar roles, etiquetas, servicios de habilitación y comandos idempotentes; verificar las cuentas existentes sin asignaciones implícitas.
3. Ampliar auditoría y consulta de solo lectura; preparar integración de eventos de cuentas y autenticación.
4. Implementar perfil y confirmación de correo inicial/nuevo, incluidos consumo único y concurrencia.
5. Integrar login/logout, cambio y recuperación de contraseña, enlazando eventos reales y pruebas de sesión.
6. Implementar panel Q.F. y Admin superior, con límites de consulta, escritura y auditoría.
7. Integrar navegación e inicio por rol; completar regresión y revisión visual; actualizar documentación con resultados reales.

## Plan de pruebas

Usar el ejecutor de Django y SQLite temporal, correo `locmem` en tests y consola para demostración local. Nuevas suites propuestas en `usuariosapp/tests/`: `test_perfil.py`, `test_correo.py`, `test_recuperacion.py`, `test_gestion_usuarios.py`, `test_admin.py`, `test_comandos.py`, `test_auditoria.py`; ampliar login y las pruebas de núcleo afectadas.

Verificar la matriz completa con cuentas sintéticas, GET/POST directo, CSRF, URLs/IDs manipulados, campos extra, inactividad tras login y ausencia de perfil. Probar verificación y recuperación con token válido, alterado, caducado, consumido, sustituido y destinatario no verificado. Probar correos iguales en cuentas distintas sin restablecer otra cuenta. Casos concurrentes para consumo de confirmación y para el límite administrativo de Q.F.; rollback de cambios si falla auditoría.

Comandos previstos: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py test --noinput`; migraciones, comandos de preparación y sus repeticiones solo sobre base de pruebas. No ejecutar estos comandos como parte de la definición documental. Detalle de resultados en [validation.md](validation.md) cuando se ejecuten.

En navegador revisar login, errores, recuperación, confirmación de correo, perfil y panel para cada rol, teclado y ancho móvil. El buzón de pruebas demuestra generación del correo; no demuestra entrega SMTP real. La revisión visual pendiente de la base no se da por realizada aquí.

## Riesgos, alternativas y dependencias

- Cambiar `AUTH_USER_MODEL` después de la base obligaría a reestructurar migraciones: conservar `auth.User` y extenderlo con Perfil.
- Nombres internos de grupos y navbar ya tienen contratos: separar etiquetas visibles sin duplicar roles.
- Permisos mediante formulario o menú pueden eludirse: servicios y consultas autorizadas, con pruebas negativas.
- Verificar correo solo en la UI permitiría recuperar por un destino no confirmado: controlar el estado en servidor y en formularios de recuperación/Admin.
- Señales y servicios pueden duplicar auditoría: señales solo para autenticación; servicios para cambios y Admin.
- Admin puede eludir servicios mediante edición de grupos/permisos: adaptar sus formularios y operaciones, incluyendo M2M y acciones masivas, o deshabilitar aquellas que no preserven contratos.
- No añadir dependencias nuevas para los flujos de esta spec. El plazo real, transporte SMTP y HTTPS se configuran al preparar el entorno autorizado; no se declaran comprobados.

## Documentos afectados

Esta fase crea únicamente los cuatro documentos y actualiza el índice. Durante implementación deberán actualizarse `README.md`, `docs/estructura.md`, `CLAUDE.md`, las tareas, la validación y el estado del índice con los comandos y contratos realmente incorporados.

## Decisiones para implementar

El alcance fue aclarado y `spec.md` fue marcado Aprobado por el usuario. La instrucción específica del 02 autoriza conservar cambios e implementar en `fdaza`, sin crear otra rama, con commit al terminar. Los pasos 1 a 6 y las comprobaciones técnicas del 7 están completados. Falta resolver la revisión visual para cerrar la tarea y realizar el commit final autorizado.
