# Farmacia · CESFAM San Nicolás

PWA de la Unidad de Farmacia, con autenticación del personal, perfiles, correo verificado, recuperación de claves, administración de cuentas y auditoría. Usa Django 5.2, SQLite y Alpine.js local. El prototipo trabaja exclusivamente con datos sintéticos; la revisión visual y aceptación funcional de la spec 02 siguen pendientes.

El spec 01 incorpora estructura, auditoría, utilidades, layouts PWA y login mínimo. El spec 03 añade padrón sintético, importación CSV/Excel y control de vigencia y entregas de recetas. El spec 04 incorpora emisión en tótem y comprobante térmico; reparto e indicadores conservan su esqueleto.

## Instalación local

Probado en Windows con Python 3.13 y Django 5.2.18. Desde la raíz, para una instalación nueva:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copia la clave generada en `SECRET_KEY` dentro de `.env`. Para desarrollo local, conserva `DEBUG=True` y los hosts de `.env.example`. `.env` y la base local están excluidos de Git.

Si Python no está en el PATH, usa la ruta de tu instalación para crear el venv; en el equipo donde se verificó el proyecto es `C:\Users\HP\AppData\Local\Programs\Python\Python313\python.exe`. También puedes ejecutar todos los comandos con `.\venv\Scripts\python.exe` sin activar el entorno.

```powershell
python -c "import django; print(django.get_version())"
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Crea una cuenta ficticia para probar. Abre <http://127.0.0.1:8000/> e inicia sesión: el inicio mostrará el perfil **Administración**. El botón «Cerrar sesión» envía un POST. La administración de Django está en `/admin/`.

## Variables de entorno

Las variables del proceso prevalecen sobre `.env`.

| Variable | Uso y valor por defecto |
|---|---|
| `SECRET_KEY` | Obligatoria; una clave local aleatoria. Una clave ausente, vacía o de solo espacios impide arrancar. |
| `DEBUG` | `False`; con `True` se usa correo a consola y cookies para desarrollo HTTP local. |
| `ALLOWED_HOSTS` | Hosts separados por comas; lista vacía por defecto. |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP fuera de desarrollo; `localhost` y `587`. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Credenciales SMTP; vacías por defecto. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | `True` y `False`. Selecciona solo uno según el servidor. |
| `DEFAULT_FROM_EMAIL` | `farmacia@example.invalid`. |
| `SMS_PROVIDER`, `SMS_API_KEY`, `SMS_SENDER` | Reservadas en la plantilla para el spec 12; todavía no se usan. |

Los booleanos aceptan `true/false`, `1/0`, `yes/no` y `on/off`, sin distinguir mayúsculas. Valores desconocidos producen un error claro. Con `DEBUG=False` las cookies de sesión y CSRF usan `Secure`. HTTPS y el servicio de estáticos en producción corresponden al despliegue, fuera del spec 01.

## Pruebas

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

La comprobación de servidor real se puede repetir con:

```powershell
python tools/verificar_spec_02_http.py
```

Esta herramienta crea una base temporal nueva, aplica las migraciones, genera credenciales sintéticas y recorre los flujos sobre un servidor WSGI en localhost con cookies/CSRF reales. Usa correo en memoria y cierra/elimina su entorno temporal; no modifica `db.sqlite3`. La suite final tiene 185 pruebas aprobadas y la herramienta verificó 21 migraciones desde cero. Evidencia y límites en [validation.md de la spec 02](specs/02-autenticacion-roles-auditoria/validation.md).

Se usa el ejecutor de Django, con una base temporal independiente. Las pruebas cubren RUT, datos reproducibles, auditoría, roles, configuración, filtros, renderizado y accesibilidad estructural, contraste WCAG, manifest e iconos, salud, páginas de error, login, redirecciones y CSRF.

La evidencia y los límites de la verificación del spec 01 están en [docs/verificacion-spec-01.md](docs/verificacion-spec-01.md).

Para ejecutar un área:

```powershell
python manage.py test coreapp.tests.test_rut
python manage.py test usuariosapp.tests.test_login
```

## Rutas y PWA

| Ruta | Comportamiento |
|---|---|
| `/` | Inicio con sesión obligatoria. |
| `/usuarios/entrar/` | Login de Django. |
| `/usuarios/salir/` | Logout por POST con CSRF. |
| `/salud/` | Pública: `{"estado": "ok"}`; devuelve 503 si no se puede abrir la conexión a la base. |
| `/sw.js` | Service worker público, MIME JavaScript y alcance `/`. |
| `/recetas/pacientes/` | Padrón privado y consulta de recetas para Q.F., Técnico y superusuario. |
| `/recetas/importaciones/` | Bitácora y carga CSV/XLSX para Q.F. y superusuario. |
| `/recetas/nueva/` | Creación de receta simulada para Q.F. y superusuario. |
| `/turnos/totem/` | Emisión pública por RUT y recuperación del turno activo. |
| `/entregas/`, `/indicadores/` | Prefijos montados, todavía sin vistas. |

El manifest declara iconos PNG de 192 y 512 px. El service worker se registra, pero no intercepta solicitudes ni guarda datos en caché. La instalación depende del navegador y requiere un contexto seguro: `localhost` sirve para desarrollo. El funcionamiento sin conexión se implementará en el spec 11.

## Padrón y recetas — spec 03

Q.F. importa y consulta el padrón, crea recetas simuladas y registra renovaciones como recetas nuevas vinculadas a sus antecedentes. Técnico consulta y confirma entregas del ciclo (por ejemplo, «3 de 6»). La Q.F. no confirma entregas por su rol; el superusuario activo conserva acceso a ambas funciones. El Encargado no tiene acceso general al padrón en este módulo. No existen cuentas de pacientes ni prescripción clínica o inventario por medicamento.

Tras aplicar las migraciones del proyecto, entra a «Padrón y recetas» y, como Q.F., a «Importaciones». Descarga una plantilla CSV o `.xlsx`. Las doce columnas, en este orden, son:

```text
rut,nombres,apellidos,fecha_nacimiento,es_cronico,es_postrado,telefono,direccion,codigo_receta,fecha_inicio,vigencia_meses,max_entregas
```

CSV: UTF-8 con BOM opcional, comas y comillas estándar. Excel: una única hoja `padron`, sin macros ni fórmulas. Fechas como texto `AAAA-MM-DD`, indicadores `0`/`1` y vigencia/cupo enteros positivos. Teléfono y dirección son opcionales. Para cargar solo padrón, dejar vacías las cuatro columnas de receta; si se completa una, completar las cuatro. Un paciente puede tener varias recetas en filas separadas con los mismos datos personales. Límites: 5 MiB y 10.000 filas; XLSX descomprimido hasta 50 MiB y 1.000 entradas. El lector usa `openpyxl` (versión probada: 3.1.5).

Cada fila válida se confirma completa, con auditoría; los rechazos no detienen las válidas. Los duplicados idénticos se omiten y las identidades contradictorias dentro del archivo se rechazan. Reimportar actualiza por RUT/código sin duplicar ni borrar ausentes. Una receta con entregas conserva fechas, cupo e historial: su cambio exige renovación con código nuevo. La carga no importa contadores de entrega ni deduce vínculos de renovación. El reporte privado guarda número de fila y motivo, sin copiar valores rechazados ni conservar el archivo subido.

El inicio es inclusivo y el fin exclusivo se calcula sumando meses naturales, ajustando días inexistentes al último día del mes destino. El último día válido es el anterior a ese límite. Ejemplo: inicio 2026-01-31 y un mes → límite 2026-02-28; último día válido 2026-02-27. Se bloquean entregas antes del inicio, tras vencimiento o por cupo agotado; reenviar una misma confirmación no duplica. El servicio de elegibilidad está preparado para integrarse con turnos en su propia spec.

Generar un padrón reproducible de 670 pacientes sin modificar la base:

```powershell
python manage.py generar_padron_demo padron-sintetico.csv --formato csv --inicio 2026-11-02
python manage.py generar_padron_demo padron-sintetico.xlsx --formato xlsx --inicio 2026-11-02
```

La semilla por defecto es 3; el inicio por defecto, 2026-01-01. Elegir `--inicio` de acuerdo con la fecha de la demostración. No se sobrescribe un archivo existente salvo con `--sobrescribir`. Usar una carpeta de trabajo para estas salidas; no son archivos para versionar.

Verificación aislada reproducible:

```powershell
python manage.py test recetasapp --noinput
python tools/verificar_spec_03_http.py
python tools/verificar_spec_03_http.py --preview
```

La herramienta usa otra SQLite temporal, migraciones desde cero, credenciales efímeras y HTTP real con CSRF. Comprueba 670 pacientes en ambos formatos, repetición, renovación, entrega idempotente, historial y permisos; mide 40 consultas de detalle. `--preview` sirve en localhost doce copias HTML sintéticas de solo lectura para revisión visual; Ctrl+C cierra el servidor. No modifica `db.sqlite3`. Evidencia: [validación del spec 03](specs/03-padron-y-recetas/validation.md). Regresión actual: 238 pruebas aprobadas; revisión visual/móvil, axe del módulo y aceptación del usuario pendientes por acceso al navegador.

## Convenciones compartidas

- `normalizar_rut` valida y devuelve `12345678-5`; una entrada inválida lanza `ValidationError` con un mensaje genérico. `validar_rut` devuelve un booleano y `formatear_rut` agrega puntos.
- `generar_rut(Random(semilla))` y `generar_ruts(cantidad, Random(semilla))` producen identificadores ficticios reproducibles; la lista no repite RUT. No crean pacientes.
- `registrar_accion(usuario, accion, objeto)` conserva actor, acción, tipo de modelo, clave y fecha. No copia el nombre, RUT ni representación del objeto. El objeto debe estar guardado.
- `RolRequeridoMixin.roles_permitidos` es una tupla de constantes de `coreapp.roles`. El acceso exige cuenta activa, `Perfil` y un único rol operativo; el superusuario activo conserva su excepción sin perfil ni grupos. El tótem no es un grupo.
- Los nombres internos de grupos se conservan y sus etiquetas son Q.F., Técnico en Farmacia y Encargado de terreno. Cuentas sin perfil, sin rol o con varios roles muestran «Acceso pendiente de regularización» y no acceden al inicio privado. La actividad y los roles se consultan en la base, sin confiar en valores en caché.
- El filtro `rut` se reserva para pantallas internas. `minutos` recibe segundos o `timedelta`, redondea hacia arriba y muestra `—` para entradas inválidas.

## Roles y cuentas de demostración

Con el venv activo y las migraciones aplicadas al entorno de desarrollo elegido:

```powershell
python manage.py crear_roles
python manage.py crear_usuarios_demo
```

`crear_roles` prepara los tres grupos sin asignar usuarios ni modificar permisos existentes. `crear_usuarios_demo` prepara además `demo_qf`, `demo_tecnico` y `demo_terreno`, con un perfil y un único rol cada uno. Solicita y confirma una contraseña inicial mediante entrada oculta, aplicando los validadores de Django. Sus correos sintéticos terminan en `@example.invalid` y comienzan sin verificar.

Para automatización, el comando admite `--noinput` y toma la contraseña inicial de `CESFAM_DEMO_PASSWORD` del proceso. No hay contraseñas predeterminadas ni argumentos de línea de comandos para la clave. Ambos comandos admiten `--database`.

Las cuentas que ya existan con esos nombres se conservan íntegramente: no se cambian sus claves, roles, perfiles, actividad ni privilegios. Si faltan cuentas y no se aporta una contraseña válida, el comando falla sin dejar altas parciales. Si todas existen, la repetición no necesita contraseña. Ningún comando se ejecuta automáticamente al arrancar.

Los comandos y el acceso por rol corresponden al paso 2 de la spec 02. Los pasos 3 a 6 incorporan auditoría, perfil/correo, autenticación/claves y administración de cuentas. La integración y regresión final están verificadas; la revisión visual quedó pendiente por acceso al navegador.

## Mi perfil y correo verificado

Desde «Mi perfil» (`/usuarios/perfil/`), una cuenta habilitada puede editar nombres, apellidos y solicitar un nuevo correo. El correo vigente permanece hasta confirmar el destino solicitado. Un correo inicial sin verificar también puede confirmarse desde el perfil; el superusuario sin Perfil lo crea explícitamente al guardar, sin perder acceso a su administración.

El enlace enviado muestra una pantalla de confirmación; abrirlo no cambia datos. Confirmar requiere POST con CSRF. Cada enlace está firmado para la cuenta, el correo pendiente y un identificador de solicitud, con el plazo de `PASSWORD_RESET_TIMEOUT` de Django. Reenviar sustituye la solicitud anterior; enlaces alterados, caducados o consumidos no cambian la cuenta. La confirmación no inicia sesión automáticamente.

El backend configurado envía el mensaje: consola con `DEBUG=True`, SMTP fuera de desarrollo y memoria en las pruebas. Un fallo de envío revierte la operación del perfil; el correo externo y el commit de la base no ofrecen entrega exactamente una vez. Las pruebas de la spec solo comprobaron el buzón en memoria.

## Cambio y recuperación de contraseña

El login usa `BackendPersonal` para comprobar credenciales y habilitación de la cuenta. El correo sin verificar no impide ingresar, pero sí recuperar por correo. Las sesiones anteriores que guardaron la ruta del backend predeterminado de Django necesitan volver a iniciar sesión después de este cambio de configuración.

Desde Mi perfil se cambia la clave indicando la actual y confirmando una nueva válida y distinta. Se conserva la sesión actual y las demás pierden acceso. Desde «¿Olvidaste tu contraseña?» se solicitan usuario y correo vigente verificado; una respuesta general no informa si la cuenta existe. El correo pendiente no sirve para recuperar y compartir correo con otra cuenta no permite restablecerla sin su identificador.

Los enlaces usan los tokens y el plazo `PASSWORD_RESET_TIMEOUT` de Django; al abrirlos se guarda el token en sesión y se redirige a una URL sin él. Tokens alterados, caducados o utilizados no cambian la clave. Restablecerla revoca las sesiones anteriores y exige iniciar sesión nuevamente. El hash y su evento de auditoría se confirman juntos; si falla el registro, se revierte el cambio.

Rutas: `/usuarios/clave/cambiar/`, `/usuarios/clave/recuperar/`, `/usuarios/clave/enviada/`, `/usuarios/clave/restablecer/<uidb64>/<token>/` y `/usuarios/clave/lista/`. El envío de recuperación fallido mantiene la respuesta general y deja un aviso técnico sin datos privados; las pruebas no demuestran entrega real.

## Administración de usuarios

La Q.F. accede a «Usuarios» (`/usuarios/gestion/`) para listar, crear y editar técnicos y encargados, asignar uno de esos dos roles y activar/desactivar cuentas. No administra otras jefaturas, staff, superusuarios ni su propia cuenta desde ese panel. La edición conserva el nombre de usuario y la clave; la contraseña inicial solo se solicita al crear. La desactivación conserva el historial y revoca el acceso en la siguiente petición.

Las cuentas nuevas reciben un enlace para confirmar su correo. Al editar una dirección, la vigente sigue en uso hasta confirmar la solicitada. Si una cuenta todavía no tiene correo vigente, sus formularios muestran el pendiente para facilitar la edición sin darlo por verificado.

Solo el superusuario administra jefaturas, flags de Django, permisos individuales y grupos adicionales desde Django Admin. Cada cuenta ordinaria tiene un rol operativo; los grupos adicionales excluyen los tres roles operativos. Los cambios se validan y auditan en los mismos servicios que usa el panel. El cambio administrativo de correo también requiere verificación y el cambio de clave registra al administrador como actor.

Los grupos se consultan en Admin, pero su creación/edición/borrado y las acciones masivas no están habilitados allí; tampoco hay edición directa de Perfil ni borrado físico de cuentas. Así se evitan rutas que eludan los contratos de roles y correo. «Historial» de una cuenta abre su bitácora técnica filtrada.

## Consulta de auditoría

El superusuario activo puede consultar la bitácora en Django Admin (`/admin/coreapp/registroauditoria/`), filtrando por acción, fecha o actor técnico y buscando referencias. La bitácora no permite altas, cambios, borrados ni acciones masivas, incluso al superusuario. Q.F., Técnico y Encargado no pueden consultarla, aunque se les concedan permisos del modelo por otra vía.

Se registran login exitoso/fallido y logout mediante señales conectadas una vez. Las altas de demostración registran creación de cuenta y asignación de rol en su misma transacción. Los registros contienen acción, ID de actor cuando corresponde, referencia de objeto y fecha; no guardan credenciales, valores personales cambiados ni el identificador introducido en un login fallido. La interfaz muestra referencias técnicas del actor.

Si falla auditar un login, la sesión preparada se elimina y la operación falla. Si falla auditar un logout, el cierre continúa y se emite un aviso técnico fijo, sin detalles privados. Perfil, correo, claves, panel y Admin se auditan en sus transacciones, incluidas las relaciones de grupos y permisos.

## Tótem y comprobante térmico (spec 04)

Abrir `/turnos/totem/`. La base debe tener el padrón y recetas sintéticas del spec 03. El tótem valida RUT y recetas, reúne todas las elegibles en un turno y no descuenta entregas. Repetir el RUT recupera su turno activo del día. Postrados y mayores de 80 reciben orientación para consultar su despacho; no hay consulta real de logística. Discapacidad y urgencia no se clasifican en este módulo.

Para imprimir, instalar la térmica en el equipo, elegir papel de 80 mm en su controlador, desactivar encabezados/pies del navegador y usar «Imprimir número». El comprobante prepara un área útil de 72 mm con márgenes de 4 mm y altura libre. Cancelar o reimprimir conserva el mismo número; el sistema no certifica salida física ni detecta papel. La compatibilidad y los márgenes deben verificarse con la impresora disponible; todavía no hay prueba física.

Validación aislada: `python tools/verificar_spec_04_http.py` crea 670 pacientes sintéticos y SQLite temporal, recorre HTTP/CSRF y mide 100 solicitudes por escenario, y al cerrar elimina su base. No modifica la SQLite local. `node --test turnosapp/tests/impresion.test.cjs` verifica el control del diálogo simulado. Ver [evidencia y límites](specs/04-emision-de-turnos/validation.md): navegador, WCAG integral, papel y usabilidad pendientes; no declarar el spec completamente aceptado.

## Recursos de Alpine.js

Se distribuye **Alpine.js 3.14.9** en `static/js/alpine.min.js`, descargado del [paquete con versión fija](https://cdn.jsdelivr.net/npm/alpinejs@3.14.9/dist/cdn.min.js), siguiendo su [instalación por script](https://alpinejs.dev/essentials/installation). La [licencia MIT original](https://github.com/alpinejs/alpine/blob/v3.14.9/LICENSE.md) se conserva en `static/js/alpine.LICENSE.md`. El navegador carga todos los recursos desde este proyecto.

Consulta [docs/estructura.md](docs/estructura.md) para el árbol y los contratos de cada módulo.

## Organización de specs

El índice central está en [specs/README.md](specs/README.md); [specs/00-indice.md](specs/00-indice.md) conserva el acceso anterior. Cada funcionalidad usa una carpeta `specs/NN-slug/`, con números de dos dígitos y cuatro documentos:

- `spec.md`: objetivo, alcance, requisitos, criterios de aceptación y decisiones.
- `plan.md`: diseño técnico y pasos de implementación.
- `tasks.md`: tareas y seguimiento de su ejecución.
- `validation.md`: verificaciones, resultados y límites de la evidencia.

La base implementada está en [specs/01-base-del-proyecto/spec.md](specs/01-base-del-proyecto/spec.md). La [spec 02 de autenticación, roles y auditoría](specs/02-autenticacion-roles-auditoria/spec.md) tiene código y verificación técnica final completados; revisión visual y cierre pendientes. Las plantillas están en `specs/_templates/`. Se mantienen las reservas 06 para WebSocket, 11 para funcionamiento sin conexión y 12 para notificaciones.
