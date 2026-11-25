# Estructura del proyecto

## Atención — spec 05

`turnosapp/cola.py` serializa selección y cursor global, respeta compatibilidad/FIFO, pesos configurables y prioridad por espera de 15 minutos. La urgencia (U) es el cuarto tipo de ventanilla y se llama antes que el rescate y el ciclo, por orden de entrada y sin mover el cursor (RF-05-13). `atencion.py` concentra ocupación, inicio/pausa, ausencias/retorno y cierre atómico (un turno sin recetas vinculadas se cierra sin entrega con el motivo fijo `MOTIVO_SIN_RECETAS`); UUID de operación ligados al actor y parámetros impiden repetir efectos. `PendienteSeleccion` sobrevive al cierre y permite recuperar el siguiente llamado sin revertir entregas. `preparar_ventanillas` prepara cuatro puestos explícitamente; `procesar_cola --continuo` recupera pendientes y cierra esperas de jornadas anteriores. No hay escrituras desde GET ni arranque implícito en migraciones.

`panel.py` proyecta solo lectura; `vistas_operacion.py` y formularios aplican roles/CSRF y mantienen UUID ante errores. Plantillas privadas de `templates/turnos/`, `cola.css` y `cola.js` presentan puesto, cola, configuración, cierre e historial. La consulta cada segundo preserva controles con foco y elimina el fragmento privado si se revoca la sesión. `/turnos/panel/` admite Técnico/Q.F.; `/turnos/gestion/`, Q.F. Las entregas reutilizan el servicio del 03 y su contexto firmado en `recetasapp/confirmacion.py`.

Migraciones: recetas 0003 y turnos 0002; conservan datos históricos, sin fabricar vínculos de entrega. Verificación: 411 pruebas Django, siete JavaScript y `tools/verificar_spec_05_http.py` con 670 pacientes sintéticos, cuatro puestos, tres escenarios concurrentes y recuperación en proceso nuevo. Navegador, axe y aceptación pendientes; la pantalla pública y voz quedan para 06. No se migró la base local durante esta implementación.

## Turnos — spec 04

`turnosapp` incorpora `ContadorTurnosDiario`, `Turno` y `TurnoReceta`, con migración `0001_initial` dependiente de recetas 0002. Unicidad diaria del número, activo por paciente/fecha y UUID de operación; relaciones protegidas. `services.emitir_turno` reserva el correlativo con UPDATE condicional, reintenta colisiones y confirma vínculos/auditoría en la misma transacción. Reutiliza `evaluar_elegibilidad`; no consume ni reserva entregas. Recuperar conserva selección y categoría originales.

`forms.py` valida RUT y UUID; las vistas `/turnos/totem/`, `/turnos/totem/finalizar/` y `/turnos/totem/continuar/` aplican contexto temporal, CSRF y `no-store`. El contexto guarda UUID, vencimiento, huella HMAC y señal de resultado, sin RUT en claro ni ficha. Solo las claves del tótem se limpian, preservando una sesión del personal. Las entradas se marcan sensibles para trazas y los fallos públicos no muestran excepciones.

`templates/turnos/` contiene entrada, resultado, aviso de tiempo y comprobante. `static/js/totem.js` controla teclado, limpieza, ampliación e impresión sin almacenamiento local. Desde el 2026-11-23 da formato al RUT mientras se escribe (el último carácter es el dígito verificador: `123-4`, `12.345.678-5`; K solo al final; «Borrar» quita un número, nunca solo el guion o un punto), también con teclado físico; el servidor lo acepta con o sin formato. Pruebas en `turnosapp/tests/totem.test.cjs`. `static/css/turnos.css` reutiliza la paleta y prepara un comprobante de 72 mm útiles en rollo nominal de 80 mm; la altura y papel los define el controlador, sin altura fija en CSS. Solo se imprime el fragmento mínimo, sin tipo de atención ni identidad. El cierre del diálogo no confirma papel. No hay endpoint público para enumerar turnos o recetas.

Pruebas: `turnosapp/tests/` cubre esquema, migración, servicios, cinco escenarios concurrentes, HTTP/CSRF y estructura semántica. `impresion.test.cjs` usa Node para probar el JavaScript con diálogo simulado. `tools/verificar_spec_04_http.py` aplica 24 migraciones en SQLite temporal, genera 670 pacientes sintéticos y valida HTTP real y p95 por escenario. No usa la base local.

Pendientes de aceptación: navegador/móvil/teclado, vista previa, auditoría WCAG A/AA, impresora física y cinco usuarios representativos. El host de navegador y el control nativo no estuvieron disponibles durante la validación del 04. El spec conserva Aprobado; llamados, ventanillas, urgencia, discapacidad y logística real siguen fuera de alcance.

## Base y módulos anteriores

El spec 01 crea esta base. Se usa un único `cesfam/settings.py`; `asgi.py` y `wsgi.py` conservan las plantillas de Django. El usuario es `auth.User`, sin `AUTH_USER_MODEL` propio.

```text
proyecto/
├── manage.py                 requirements.txt    .env.example    .gitignore
├── README.md                 CLAUDE.md
├── cesfam/
│   ├── __init__.py            settings.py         urls.py
│   └── asgi.py                wsgi.py
├── coreapp/
│   ├── __init__.py            apps.py             admin.py
│   ├── models.py              auditoria.py        roles.py
│   ├── mixins.py              context_processors.py
│   ├── views.py               urls.py
│   ├── migrations/           __init__.py         0001_initial.py
│   ├── utils/                __init__.py         rut.py          sinteticos.py
│   ├── templatetags/         __init__.py         core_tags.py
│   └── tests/
│       ├── __init__.py        test_rut.py         test_auditoria.py
│       ├── test_mixins.py     test_configuracion.py
│       ├── test_plantillas.py test_estaticos.py    test_vistas.py
├── usuariosapp/
│   ├── __init__.py            apps.py             admin.py
│   ├── models.py              views.py            urls.py
│   ├── migrations/           __init__.py
│   └── tests/                __init__.py         test_login.py
├── recetasapp/               turnosapp/          entregasapp/    indicadoresapp/
│   └── Cada una: __init__.py, apps.py, admin.py, models.py, views.py, urls.py,
│                  migrations/__init__.py y tests/__init__.py
├── templates/
│   ├── index.html            403.html            404.html        500.html
│   ├── components/
│   │   ├── Layout/           base.html           base_publica.html   base_acceso.html
│   │   ├── navbar.html       barra_superior.html dock.html       _menu_enlace.html
│   │   └── footer.html       paginator.html      mensajes.html
│   ├── registration/         login.html
│   └── pwa/                  sw.js
├── static/
│   ├── manifest.webmanifest
│   ├── css/                  base.css            menu.css
│   ├── js/                   alpine.min.js       alpine.LICENSE.md   pwa.js    menu.js
│   └── icons/                icon-192.png        icon-512.png
├── docs/                     Informe.md          estructura.md   verificacion-spec-01.md
└── specs/
    ├── README.md             00-indice.md        .spec-config.yml
    ├── 01-base-del-proyecto.md                   Acceso compatible
    ├── _templates/           spec.md             plan.md         tasks.md        validation.md
    └── 01-base-del-proyecto/
        ├── spec.md           plan.md
        └── tasks.md          validation.md
```

El índice central de funcionalidades es [specs/README.md](../specs/README.md); `specs/00-indice.md` conserva el acceso anterior. Cada carpeta `specs/NN-slug/` mantiene un número de dos dígitos y separa el contrato funcional (`spec.md`), el diseño y los pasos (`plan.md`), el avance de las tareas (`tasks.md`) y la evidencia de verificación (`validation.md`). `specs/_templates/` contiene las cuatro plantillas para los siguientes specs. La reorganización conserva el estado implementado y el acuerdo de ejecución sobre `fdaza` del spec 01.

## Archivos y specs responsables

| Archivo o conjunto | Spec que lo crea | Responsabilidad |
|---|---|---|
| `manage.py`, `requirements.txt`, `.env.example`, `.gitignore`, `cesfam/*` | 01 | Entorno, configuración y rutas raíz. |
| Esqueleto común de las seis apps, `migrations/__init__.py` y `tests/__init__.py` | 01 | Registro y separación por responsabilidad. |
| `coreapp/roles.py`, `mixins.py`, `context_processors.py` | 01 | Nombres de roles, autorización y presentación. |
| `coreapp/models.py`, `auditoria.py`, `migrations/0001_initial.py` | 01 | Modelo abstracto auditado y registro explícito sin datos de pacientes. |
| `coreapp/utils/*` | 01 | RUT y generación reproducible de identificadores ficticios. |
| `coreapp/templatetags/*` | 01 | Formato de RUT y minutos. |
| `coreapp/views.py`, `coreapp/urls.py` | 01 | Inicio, salud y service worker. |
| `usuariosapp/urls.py`, `registration/login.html` | 01 | Login mínimo y logout POST con vistas de Django. |
| Layouts, componentes, inicio y errores de `templates/` | 01 | Presentación compartida. `500.html` es independiente. |
| `static/*`, `templates/pwa/sw.js` | 01 | Contraste, Alpine 3.14.9 local, manifest, iconos y registro PWA. |
| `coreapp/tests/test_*.py`, `usuariosapp/tests/test_login.py` | 01 | Contratos y criterios de aceptación de la base. |
| `README.md`, este archivo, `verificacion-spec-01.md`, `specs/README.md`, `specs/00-indice.md` | 01 y organización documental | Instalación, arquitectura, evidencia y mapa de specs. |
| `docs/Informe.md`, guías y skills | Anteriores al 01 | Fuentes del proyecto; el 01 alinea las guías con el árbol acordado. |

`venv/`, `.env`, `db.sqlite3` (base antigua), `media/`, `privado/` (fotos de domicilios, spec 08) y `staticfiles/` se generan localmente y no se versionan.

## Modelo–Vista–Controlador en Django

| Capa | Ubicación | Regla |
|---|---|---|
| Modelo | `<app>/models.py` | Datos y restricciones; solo ORM. |
| Controlador | `<app>/views.py` | Vistas de clase: permisos, entrada HTTP y respuesta. |
| Negocio | `<app>/services.py` | Funciones explícitas y transacciones; llegan con el spec del módulo. |
| Vista | `templates/` y `static/` | Presentación accesible, sin lógica de dominio. |

`coreapp` depende solo de Django. `usuariosapp` usa el núcleo. Las apps de dominio usarán `coreapp` y los datos de `recetasapp` según su spec. Ninguna app de negocio importa vistas de otra. Los indicadores son de lectura.

Las clases `InicioView`, `ServiceWorkerView` y `SaludView` exponen los callables `inicio`, `sw_js` y `salud`. El inicio requiere sesión; las futuras acciones por rol usan `RolRequeridoMixin`. Los prefijos están en `cesfam/urls.py`, con espacios de nombres iguales a los nombres de app.

## Contratos compartidos

- Una auditoría guarda `usuario`, `accion`, `objeto_tipo`, `objeto_id` y `creado_en`. No hay FK al objeto auditado, de modo que su eliminación conserva la referencia textual.
- `crear_roles` prepara los tres grupos de `ROLES_INTERNOS` explícitamente. Una cuenta operativa requiere perfil y exactamente uno de ellos, sin elegir un rol por prioridad cuando hay varios. Se conservan nombres internos y se presentan Q.F., Técnico en Farmacia y Encargado de terreno. El superusuario activo mantiene su excepción; `TOTEM` continúa público.
- Las utilidades RUT aceptan cadenas con o sin puntos y guion; validan el DV antes de normalizar o formatear. Los errores no repiten el dato recibido.
- `condicion_busqueda_rut(texto, campo)` (2026-11-23) es la búsqueda por RUT de Pacientes, Todas las recetas, Pendientes de retiro, Domicilios, Programar entrega y Excepciones de reparto: quita puntos y espacios, busca exacto el RUT completo y válido y, además, como comienzo del RUT guardado, para que la búsqueda en vivo encuentre mientras se escribe y el RUT sin dígito verificador encuentre al paciente. Devuelve `None` si el texto no parece un RUT (queda la búsqueda por nombre). Pruebas en `coreapp/tests/test_rut.py` y `test_busqueda_rut.py`.
- `sinteticos.py` exige un `random.Random` del llamador y usa cuerpos numéricos ficticios en el intervalo 90.000.000–99.999.999. La generación de listas evita duplicados.
- `rut` devuelve texto vacío ante una entrada inválida. `minutos` convierte segundos a minutos hacia arriba, limita negativos a cero y muestra `—` para valores no numéricos o no finitos.
- La navegación solo enlaza vistas existentes. Las opciones por rol comparten el inicio hasta que sus specs agreguen las pantallas correspondientes.
- Desde el spec 11, el service worker (`templates/pwa/sw.js`, plantilla de Django) guarda en una caché versionada solo los estáticos de `coreapp.views.ESTATICOS_SIN_CONEXION` y la vista sin conexión del reparto; ver la sección del spec 11.

## Archivos que llegan después

El spec 02 ya incorpora perfiles y preparación de grupos/cuentas; la autenticación completa y el panel de usuarios siguen en sus pasos restantes. Los siguientes specs crean modelos de dominio y sus `services.py`; el 06 incorpora WebSocket; el 11, funcionamiento sin conexión; el 12, notificaciones. Esos archivos no se crean como marcadores vacíos en el 01.

## Avance de la spec 02 — pasos 1 a 6

El árbol anterior describe la base del 01. Sobre ella se incorporaron `usuariosapp/models.py` con Perfil, migraciones `0001_initial.py`/`0002_perfiles_existentes.py`, `usuariosapp/services.py` y los comandos `management/commands/crear_roles.py` y `crear_usuarios_demo.py`. Las pruebas están en `usuariosapp/tests/test_perfil.py`, `test_roles.py` y `test_comandos.py`, junto con la adaptación de pruebas del núcleo.

`coreapp.roles.estado_acceso` consulta cuenta activa, perfil y rol único en la base. `CuentaHabilitadaMixin` protege el inicio privado y `RolRequeridoMixin` añade restricciones por rol. La plantilla 403 explica la regularización pendiente y permite cerrar sesión. Uso de los comandos en [README.md](../README.md#roles-y-cuentas-de-demostración).

El paso 3 incorpora `usuariosapp/signals.py`, conectado desde `apps.py`, el helper `coreapp.auditoria.registrar_evento` y `coreapp/admin.py` para consulta técnica de solo lectura de la bitácora por superusuario. Los eventos de creación/asignación demo se escriben en su transacción. Las pruebas nuevas están en `usuariosapp/tests/test_auditoria.py` y `test_admin.py`; se conserva la compatibilidad de las pruebas genéricas del núcleo.

El paso 4 incorpora `usuariosapp/forms.py`, vistas/URLs de perfil y correo, servicios transaccionales en `services.py`, plantillas `templates/usuarios/perfil.html`, `verificar_correo.html` y `templates/registration/verificar_correo_email.txt`, además del enlace Mi perfil. El estado usa los campos de Perfil ya migrados: no requiere nuevas migraciones. La firma vincula usuario, destino pendiente y UUID; GET no consume y POST realiza UPDATE condicional con auditoría. Las pruebas se amplían en `test_perfil.py` y el nuevo `test_correo.py`, incluida concurrencia SQLite.

El paso 5 agrega `usuariosapp/backends.py` y lo configura en `AUTHENTICATION_BACKENDS`. Amplía formulario/vistas/servicios/URLs de login y claves, con las plantillas `registration/password_change_form.html`, `password_reset_{form,done,confirm,complete}.html`, correo/asunto de recuperación y el parcial de campos. Reutiliza tokens/vistas de Django y escribe hash/evento en transacción. Pruebas en `test_login.py` y el nuevo `test_recuperacion.py`, con sesiones y consumo concurrente.

El paso 6 incorpora formularios/vistas/servicios de gestión, rutas bajo `/usuarios/gestion/`, plantillas `usuarios/gestion_lista.html` y `gestion_form.html` y enlace Usuarios. `usuariosapp/admin.py` sustituye el Admin de User, restringe su escritura al superusuario y deja grupos de solo lectura; Perfil no se registra para edición directa. Todas las relaciones y eventos se escriben desde servicios; no hay escrituras M2M posteriores desde Admin ni borrado de cuentas. El historial usa la bitácora filtrada. Pruebas nuevas en `test_gestion_usuarios.py` y ampliación de `test_admin.py`, incluida promoción concurrente. La revisión final del paso 7 sigue pendiente.

## Límite de intentos de inicio de sesión — 2026-11-24

`usuariosapp/limite_acceso.py` y el modelo `IntentoAcceso` (migración `0003_intentoacceso`, sin Admin) limitan el login (RF-02-13): `IniciarSesionView.post` reserva un intento con `limite_acceso.reservar` antes de comprobar la contraseña (5 por usuario en el equipo y 20 por equipo en ventanas de 15 minutos, UPDATE condicional y restricción única) y, con el cupo agotado, responde 429 con `error_limite` en `registration/login.html` sin autenticar. `ingreso_correcto` devuelve el cupo del equipo y borra los fallos del usuario en el equipo. Las claves son huellas `salted_hmac` del usuario sin mayúsculas más la IP (`REMOTE_ADDR`) y de la IP sola; la auditoría `auth.limite_intentos` se escribe una vez por huella y ventana. Pruebas en `usuariosapp/tests/test_limite_acceso.py`, con tres escenarios concurrentes.

## Integración final de la spec 02 — revisión visual pendiente

Se integraron enlaces por permisos y sección activa, accesos desde el inicio y CSS para formularios/selectores/tarjetas adaptables. `usuariosapp/tests/test_integracion.py` comprueba destinos reales y estructura accesible de formularios. La suite completa pasó con 185 pruebas.

`tools/verificar_spec_02_http.py` prepara y elimina exclusivamente una SQLite temporal, aplica 21 migraciones y recorre flujos sobre WSGI real en localhost con datos sintéticos, cookies/CSRF y correo en memoria. No usa la base local. La revisión por navegador está pendiente por indisponibilidad del host y rechazo de acceso a una ventana con contenido ajeno al proyecto. El commit final se reserva para resolver el cierre.

## Spec 03 — Padrón y recetas

El árbol inicial del 01 se amplía en `recetasapp` con estos componentes:

| Archivo / carpeta | Responsabilidad |
|---|---|
| `models.py` | Paciente, Receta, EntregaReceta, ImportacionPadron y ResultadoFilaImportacion; restricciones y protección de historial. |
| `migrations/0001_initial.py`, `0002_resultadofilaimportacion_pacientes_actualizados_and_more.py` | Esquema y conteos de objetos por fila para reconstruir bitácoras. |
| `services.py` | Autorización, calendario, elegibilidad, creación/renovación, confirmación idempotente y aplicación atómica de fila; auditoría y reintentos por colisiones SQLite. `actualizar_correo_avisos` (enmienda del 03, 2026-11-18) guarda o borra el correo para avisos desde la ficha con UPDATE condicional sobre el valor leído (`CorreoCambiado` si cambió) y auditoría `paciente.correo_actualizado` sin la dirección. |
| `importacion.py` | Contrato de doce columnas (o trece, con `correo` opcional al final: la celda vacía conserva el correo guardado), CSV/XLSX limitado, prevalidación de contradicciones, procesamiento parcial y bitácoras; generación de plantillas y archivos sintéticos. |
| `forms.py`, `views.py`, `urls.py` | Búsqueda privada por POST, padrón, recetas, entregas y cargas protegidas por rol. Respuestas sin caché; referente limitado al mismo origen para compatibilidad con CSRF. |
| `admin.py` | No registra escritura de dominio; las operaciones pasan por servicios. |
| `management/commands/generar_padron_demo.py` | Exportación explícita de 670 pacientes sintéticos reproducibles, sin modificar la base. |
| `tests/test_modelos.py`, `test_servicios.py`, `test_importacion.py`, `test_concurrencia.py`, `test_comandos.py`, `test_vistas.py` | Integridad/migración, negocio, importación, colisiones con conexiones separadas, archivos, roles/CSRF y accesibilidad estructural. `ayudas.py` prepara exclusivamente datos sintéticos. |
| `presentacion.py` | Datos de solo lectura para dibujar la libreta: situación de la receta, casillas, línea de vigencia, resumen por paciente y categorías de una carga. No escribe ni decide permisos. |
| `templates/recetas/`, `static/css/recetas.css`, `static/js/receta_previa.js`, `static/js/importacion.js` | Base y campos compartidos, padrón/detalle, receta/renovación, confirmación, carga, bitácora y reporte paginado, con la identidad «libreta de control» (sección siguiente a la de identidad visual). |
| `tools/verificar_spec_03_http.py` | SQLite temporal, WSGI real, cookies/CSRF, importación de 670, renovación e idempotencia; medición p95 y vista HTML sintética opcional de solo lectura. |

La navegación del inicio y el menú principal (`coreapp/navegacion.py`) enlazan el padrón para Q.F., Técnico y superusuario; Encargado no accede. No se añaden rutas públicas de pacientes ni API con Rayén. Los formatos y comandos están en [README](../README.md#padrón-y-recetas--spec-03); evidencia y límites en [validation.md](../specs/03-padron-y-recetas/validation.md).

La ejecución técnica del 03 quedó verificada con 238 pruebas y HTTP real sobre 23 migraciones nuevas. La revisión visual/móvil y axe del módulo quedaron pendientes en esa ejecución porque el host de navegador no estaba disponible; se hicieron después con el rediseño descrito en la sección «Padrón y recetas: la libreta de control». Las comprobaciones de presentación de specs previas no se atribuyen al 03.

## Identidad visual de la presentación

Rediseño de plantillas y estilos con una paleta azul institucional, la marca de cruz de farmacia y una ilustración de mostrador en las pantallas de acceso; los nombres de las variables CSS (trigo, arena, naranja, ladrillo) vienen de la paleta anterior y se conservaron para no tocar cada hoja. No cambia vistas, URLs, formularios ni servicios; solo la presentación. El login, la recuperación de clave, la verificación de correo y los avisos 403, 404 y 500 son una tarjeta con el formulario a la izquierda y la ilustración de un mostrador de farmacia (estantes con frascos, bolsa, cruz y recibo) a la derecha; en pantallas angostas o con el texto muy ampliado la ilustración baja bajo el formulario. El tótem conserva su layout de dos paneles; las pantallas con sesión usan un menú lateral (columna azul marino con los grupos Trabajo y Equipo; barra superior y dock inferior en celular), migas de pan, azulejos de acceso y paneles planos.

| Archivo | Responsabilidad |
|---|---|
| `static/css/base.css` | Tokens y componentes. Paleta azul institucional: `--trigo` azul muy claro `#E3EDF9`, `--arena` `#C3D6EE`, `--ladrillo` azul de marca `#1F5FAE`, `--naranja` ámbar `#DE9230` (único acento cálido), tinta `#0B2545`, fondo de página `#F4F7FB`; `--serie-*` y `--neutro-*` son los colores de los gráficos. El aviso sigue amarillo. Cada pareja `--x-texto`/`--x-fondo` se verifica en `coreapp/tests/test_estaticos.py` (mínimo 4,5:1). |
| `static/fonts/` | Figtree (títulos) y Atkinson Hyperlegible Next (texto y formularios), WOFF2 locales con licencia OFL (`LICENSE.md`). Sin CDN: la prueba de plantillas lo prohíbe y el reparto debe cargar sin señal. |
| `static/js/preferencias.js` | Control de tamaño de texto (normal, grande, muy grande: 18, 21 y 24 px) guardado solo en `localStorage`; sin datos personales. Se carga sin `defer` para no producir un salto al pintar. |
| `static/css/admin.css`, `templates/admin/base_site.html` | Piel de la administración de Django con las mismas variables que ella expone. |
| `static/icons/marca.svg`, `icon-192.png`, `icon-512.png` | Marca y iconos PWA. Se regeneran con `tools/generar_iconos_pwa.py`, que necesita Pillow (no es dependencia del proyecto); deben seguir siendo PNG RGB sin transparencia. |
| `templates/components/iconos.html` | Sprite SVG único por página: marca (cruz), mostrador de farmacia e iconos de trazo (`<svg class="icono"><use href="#i-nombre"/></svg>`). Los iconos son decorativos: siempre acompañan a un texto. |
| `templates/components/preferencias.html`, `paisaje.html`, `Layout/base_publica.html`, `Layout/base_acceso.html` | Preferencias de lectura (desde el 2026-11-22, sin franja de demostración): tamaño del texto y modo oscuro (`static/js/preferencias.js`, paleta en `static/css/tema_oscuro.css`, con su contraste verificado en `test_estaticos.py`). Con sesión van en «Configuración › Accesibilidad» del menú lateral y a la derecha de la persona en la hoja «Más»; sin sesión (acceso, tótem y sala, marcadas `data-solo-claro`) solo el tamaño, en una cápsula arriba a la derecha. Panel de identidad y layout partido del tótem (`base_publica.html`, `paisaje.html`); tarjeta de acceso con formulario e ilustración (`base_acceso.html`, clases `.entrada-*` de `base.css`). `500.html` repite la tarjeta por su cuenta porque no puede depender de otras plantillas. |

Reglas para las vistas que lleguen después:

- Tamaños en `rem` (el control de texto escala todo hasta 150 %); texto de 1 rem como mínimo.
- Acción principal: píldora azul con texto blanco (`.boton`); secundaria: contorno (`.boton-secundario`); destructiva: contorno ladrillo (`.boton-peligro`).
- Nada depende solo del color ni del sonido: los mensajes llevan icono y texto, y los estados una insignia con icono.
- El `id="…_error"` de un campo lo aporta el `<ul class="errorlist">` de Django; el contenedor solo lleva `role="alert"` (repetirlo duplica el id).
- Las etiquetas del login no llevan clases (una prueba compara su HTML exacto); se estilan por contexto.
- `500.html` no extiende ni incluye plantillas: debe verse aunque falle lo demás.
- Los datos públicos del pie (Departamento de Salud Municipal, Arturo Prat s/n) provienen del listado público del Servicio de Salud Ñuble; confirmarlos con el CESFAM antes de la demostración.

Verificación realizada: capturas en Chrome a 1280 px y a 390 px (incluido texto «muy grande») y auditoría con axe-core 4.10 sobre 21 pantallas (login y sus errores, recuperación, 403/404/500, inicio por cada rol, perfil, claves y gestión de usuarios): **0 violaciones de WCAG 2.1 A/AA**. Axe deja como «incompletas» tres comprobaciones de contraste (texto sobre el SVG del paisaje, sobre un pseudo-elemento o bajo la flecha de un `select`); se calcularon a mano (blanco sobre `#BC4F4F` = 4,81:1; tinta sobre trigo/blanco ≥ 15:1). Pendientes: la aceptación del equipo y la prueba de usabilidad con al menos cinco personas representativas que exige el informe (RNF-04).

## Padrón y recetas: la libreta de control

Rediseño de las nueve pantallas de `templates/recetas/` sobre la identidad anterior. Idea: en el CESFAM el paciente crónico lleva una libreta que se timbra en cada retiro. Cada receta es una libreta con una casilla por entrega, y cada entrega confirmada es un **sello** con el sol sobre surcos del escudo. Los colores son solo los de la paleta; las referencias de Pinterest no pudieron consultarse (la página exige sesión y carga con JavaScript), así que el diseño se apoya en patrones abiertos de tarjetas de sellos: casillas vacías que muestran lo que falta y movimiento solo al completar algo.

| Archivo | Responsabilidad |
|---|---|
| `recetasapp/consultas.py` | Consultas de solo lectura del tablero y de la lista de recetas. Expresa en SQL la misma regla que `presentacion.situacion` (vencida, agotada, aún no inicia, vigente) y «por vencer» (vigente que vence en 30 días o menos); una prueba comprueba que ambas coinciden en los bordes. Sus filtros no cruzan tablas en los `UPDATE` (ver nota de PostgreSQL más abajo). |
| `recetasapp/presentacion.py` | Situación única de cada receta (vigente, aún no inicia, vencida, agotada) calculada con la misma regla que `services.evaluar_elegibilidad`; casillas, línea de vigencia («hoy» entre el inicio y el último día válido), resumen por paciente y categorías de una carga. Solo lee. |
| `static/css/recetas.css` | Estilos del módulo. No declara colores: usa las variables de `base.css` (una prueba lo exige) y todas las animaciones parten de su estado final. |
| `static/js/receta_previa.js` | «Así quedará la libreta» en crear/renovar: dibuja las casillas y calcula el último día válido mientras se escribe. Es una ayuda; el servidor recalcula y valida. Repite `services.calcular_fin` (comprobado contra Python en fin de mes y año bisiesto). |
| `static/js/importacion.js` | Muestra el archivo elegido y deduce el formato por la extensión. El servidor vuelve a validar. |
| `templates/recetas/_sellos.html`, `_libreta.html`, `_vigencia.html`, `_situacion.html`, `_barra_carga.html` | Piezas compartidas. `test_plantillas` renderiza cada archivo con un contexto mínimo, así que los parciales deben tolerar variables ausentes. |

Comportamiento que conviene conocer antes de tocar estas pantallas:

- **Padrón:** banda de búsqueda y filas (no tarjetas). Cada fila resume la receta que importa: la vigente más reciente o, si no hay, la más reciente con el motivo. La búsqueda y la paginación siguen viajando por POST para que el RUT no quede en la URL; el campo desactiva autocompletar y corrector.
- **Sello nuevo:** `ConfirmarEntregaView` envía el mensaje de éxito con la etiqueta `entrega-sellada`; la receta se estampa solo el sello recién confirmado y solo en esa carga. No usar `sello` como etiqueta de mensaje: choca con la clase `.sello` de la casilla.
- **Confirmar entrega** muestra el nombre y RUT del paciente, la casilla que se va a sellar y no ofrece el formulario si la receta no admite entregas.
- **Reporte de carga:** barra proporcional con leyenda en texto (nunca solo color) y filtro `?estado=rechazada`, que se conserva al paginar.
- **Movimiento:** estampado del sello nuevo, sol que recorre el surco al abrir una receta, casillas que aparecen en la vista previa, latido de la próxima casilla (3 repeticiones, 3,9 s, menos de los 5 s de WCAG 2.2.2) y barras del reporte que crecen una vez. Con «reducir movimiento» todo queda en su estado final.
- Cupos mayores a 24 entregas se dibujan como barra en lugar de casillas.

Verificación realizada (2026-11-02, Chrome headless y datos sintéticos inventados en una base temporal): capturas a 1280 px y 390 px, también con texto «muy grande», sin desbordes horizontales; auditoría con axe-core 4.10.2 sobre 28 pantallas (padrón y búsquedas, ficha del paciente, recetas en cada situación, crear/renovar con errores, confirmación, cargas, reporte y filtro) con Q.F. y Técnico: **0 violaciones de WCAG 2.1 A/AA**. Axe deja como «incompletas» tres comprobaciones de contraste sobre los `select` con flecha de fondo (tinta sobre blanco, ≥ 15:1). Comportamiento comprobado en el navegador: vista previa, detección de formato, animaciones y su ausencia fuera del momento de confirmar. Suite: 278 pruebas aprobadas; `tools/verificar_spec_02_http.py` y `tools/verificar_spec_03_http.py` aprobados. Pendientes: aceptación del equipo, prueba de usabilidad con al menos cinco personas (RNF-04) y, si se quiere, registrar este rediseño en un spec propio o cerrar con él la revisión visual de [validation.md](../specs/03-padron-y-recetas/validation.md) del 03.

## Recetas como tablero y Padrón aparte

El menú reemplaza «Padrón y recetas» por dos entradas: **Pacientes** (pacientes, ficha, importaciones y plantillas) y **Recetas** (`recetasapp:recetas`, en `/recetas/`; detalle, creación, renovación y confirmación de entrega). Cada una marca «página actual» por sí sola; `test_cada_pantalla_marca_una_sola_entrada_como_pagina_actual` recorre las pantallas. «Crear receta» está en Recetas. No hay una entrada «Resumen»: el resumen es el tablero con que abre Recetas.

| Archivo | Responsabilidad |
|---|---|
| `recetasapp/tablero.py` | Arma el tablero (solo lectura): cifras, barra de situación, ranking y última carga. Sin selector de periodo: las tendencias en el tiempo (entregas por día) están en el panel de Indicadores. |
| `recetasapp/graficos.py` | Geometría pura de los gráficos: porcentajes que suman 100, arcos del anillo sobre un círculo de largo 100, curva con tangentes horizontales (no se pasa del rango), techo redondo del eje y barras. Todo número hacia un atributo SVG sale como texto con punto decimal: con es-cl, Django escribiría coma y el atributo quedaría inválido. |
| `templates/recetas/_tablero.html`, `static/css/tablero.css` | Dibujo y estilos. Sin librerías ni CDN. `tablero.css` no declara colores (una prueba lo exige, igual que `recetas.css`). |

- **Tablero:** solo lo que sirve para trabajar: cuatro cifras (vigentes, por vencer y pacientes sin receta vigente, con su enlace; entregas en 7 días, con su tendencia), «Vencen primero» (ranking de seis, con aviso si no hay), situación de las recetas (barra segmentada con leyenda en texto que enlaza a la lista filtrada) y la tarjeta oscura de la última carga. «Por vencer» es parte de las vigentes, por eso no es un tramo de la barra. «Entregas por día» se movió al panel de Indicadores, con el período y el tipo de su filtro; el calendario de vencimientos se retiró porque repetía «Vencen primero». Sin datos, cada tarjeta explica qué falta en vez de dibujar un gráfico vacío.
- **Movimiento:** una sola secuencia al cargar (el anillo se traza, la línea se dibuja, las barras suben, escalonados) y el latido de «Por vencer». Todas las animaciones parten de su estado final y `base.css` las apaga con «reducir movimiento»; una prueba lo comprueba.
- **Accesibilidad de los gráficos:** el SVG lleva título y descripción con el total y el máximo; la leyenda, las barras y la tabla de datos repiten las cifras en texto, así que nada depende solo del color. El mes actual se distingue por relleno y subrayado. Hay un contraste de 3:1 comprobado para los colores de los gráficos; los arcos naranjas van delimitados por tinta.
- **Lista** (debajo del tablero, en `#listado`): pestañas con cantidad por situación, hechas con botones que envían el formulario para conservar la búsqueda. El botón «Buscar» va primero en el documento y lleva la situación actual, de modo que Enter en el campo no la pierde. Buscar o paginar vuelve a `#listado` y no al comienzo. El RUT o nombre viaja por POST; solo la situación puede ir en la URL.
- **Padrón:** filtro «Sin receta vigente», con el mismo patrón de botones.
- **Estáticos versionados:** `coreapp/storage.py` agrega `?v=<fecha de modificación>` a las URL de `.css` y `.js` (no a fuentes ni iconos). El servidor de desarrollo no envía `Cache-Control` y el navegador podía seguir con una hoja vieja (botones sin estilo tras un cambio). En producción, el equivalente completo es `ManifestStaticFilesStorage` con `collectstatic`.

## Menú principal: columna lateral y dock del celular

Reemplaza la cabecera ladrillo con ocho enlaces en fila, que ya no cabían (el botón «Cerrar sesión» bajaba a una segunda fila) y que seguirían creciendo con cada spec. Una sola lista alimenta dos presentaciones: en computador (más de 70 rem), una tarjeta lateral con grupos y una zona de cuenta, que se pliega a una columna angosta; en celular y tableta (hasta 70 rem), una barra superior con la marca y un dock flotante abajo con los cuatro destinos de trabajo y «Más», que abre una hoja con el resto y la cuenta. Es solo presentación: no cambia vistas, URLs, permisos ni servicios, y cada vista sigue validando el rol en el servidor.

| Archivo | Responsabilidad |
|---|---|
| `coreapp/navegacion.py` | La lista del menú (`ENTRADAS`, más `PERFIL`): etiqueta, ruta, ícono, grupo, perfiles que la ven, regla de «página actual», nombre corto y si va en el dock. `armar_menu()` la resuelve para un perfil y una página. Para sumar la sección de una spec basta una `Entrada` nueva. |
| `coreapp/context_processors.py` | `menu_principal` entrega el menú ya resuelto (y nombre e iniciales de la persona) a toda plantilla; `rol_actual` no cambia. |
| `templates/components/navbar.html`, `_menu_enlace.html`, `barra_superior.html`, `dock.html` | Columna lateral, opción compartida, marca del celular y dock con la hoja «Más» (un `<details>`). `Layout/base.html` los ordena; `base_publica.html`, `base_acceso.html` y `base_sala.html` no llevan navegación; solo la cápsula del tamaño del texto (bloque `preferencias_global`). |
| `static/css/menu.css` | Estilos. No declara colores: todo sale de `base.css`, donde se verifica el contraste (una prueba lo exige, igual que `recetas.css`). Incluye unas pocas compensaciones para pantallas cuyos cortes asumen la ventana completa (cifras del tablero, portada del inicio). |
| `static/js/menu.js`, `preferencias.js` | Plegar la columna y recordarlo («farmacia.menu»; `preferencias.js` lo aplica antes de pintar, sin salto), y cerrar la hoja «Más». `turnosapp/tests/menu.test.cjs` lo prueba con `node --test`. |
| `coreapp/tests/test_navegacion.py`, `test_estaticos.py` | Qué ve cada perfil, reparto entre columna y dock, página actual, íconos y nombres cortos, contraste del menú y reglas de la hoja de estilos. |

- **Computador.** Tarjeta blanca de 2 px de borde (como los paneles) con cabecera ladrillo y el «horizonte» de la marca (tres franjas de surco, las de la portada del inicio), opciones agrupadas con títulos en minúscula («Atención», «Pacientes y recetas», «Equipo»), la opción activa en una píldora ladrillo con texto blanco (ícono, texto y negrita: nada depende solo del color) y una zona de cuenta crema con nombre, perfil, «Mi perfil» y «Cerrar sesión». La lista tiene su propio scroll si la ventana es baja. Plegada, cada opción muestra el ícono con su nombre corto debajo; no hay íconos sin texto ni ayudas que dependan del mouse, y el nombre completo sigue en el árbol de accesibilidad. «Pantalla de sala» lleva un ícono de «abre en otra pestaña» y el aviso para lectores de pantalla. El botón de plegar es el primer control de la columna para el teclado.
- **Celular y tableta.** Los botones del dock miden al menos 52 × 65 px a 320 px de ancho. El texto de sus etiquetas se ajusta al ancho de la pantalla (un quinto de ella) y no crece con el control de tamaño de texto; crecen el ícono, la altura y la hoja «Más». Las etiquetas del dock y de la columna plegada (0,78 rem como máximo) son la excepción a «texto de 1 rem como mínimo» de las reglas de arriba: no caben a 1 rem; WCAG 2.1 no fija un tamaño mínimo y se compensa con ícono, píldora y áreas grandes. Una prueba exige que el nombre de cada destino del dock tenga 8 letras o menos. En tableta el dock queda centrado (34 rem como máximo). «Más» muestra una marca si la página actual está dentro de la hoja.
- **Orden y permisos.** Q.F.: Inicio de farmacia, Turnos, Pantalla de sala, Recetas, Padrón y Usuarios. Técnico: igual, sin Usuarios. Encargado de terreno: Entregas en terreno y su cuenta. Superusuario: todo más «Administración». Una cuenta sin perfil asignado solo ve el inicio. Preparación vive dentro de Recetas y marca «Recetas» como página actual (antes no marcaba ninguna entrada).
- **Agregar una sección.** Una `Entrada` en `coreapp/navegacion.py` (con su ícono en `iconos.html` si hace falta). A lo más cuatro destinos por perfil van en el dock (`en_barra`); el resto pasa solo a «Más». Las pruebas exigen una ruta existente, un ícono del sprite distinto a los demás y nombre corto cuando la etiqueta es larga.
- **Cortes.** 70 rem (1 120 px): el mismo valor en `menu.css` y `menu.js`. Más abajo la columna apretaría el contenido (con el menú desplegado quedan unos 315 px menos de ancho).

Verificación realizada (2026-11-04, datos sintéticos en una SQLite temporal; la base del proyecto no se tocó):

- Chrome sin interfaz, manejado por su protocolo de depuración: capturas a 1440, 1366, 1280, 1100, 1024, 768, 412, 390, 360 y 320 px, con texto normal, grande y muy grande; sin desborde horizontal en ninguna. 28 comprobaciones de comportamiento aprobadas: plegar, recordar al recargar y desplegar; la hoja «Más» con clic, Enter, Espacio, Escape (devuelve el foco), toque en el velo y elección de una opción; orden de teclado; y dock sin texto cortado con botones de 44 px o más de 320 a 768 px con los tres tamaños de texto.
- axe-core 4.10.2 (WCAG 2.0, 2.1 y 2.2 A y AA) sobre 16 estados (columna desplegada y plegada, cuatro perfiles, texto muy grande, dock, hoja abierta y tableta): **0 violaciones**. Encontró y se corrigió un caso real: el botón de plegar quedaba parcialmente tapado por la cabecera (tamaño de objetivo, WCAG 2.5.8). Las comprobaciones «incompletas» de contraste son las de siempre: texto blanco sobre el horizonte ladrillo (4,81:1 calculado), el SVG de la portada y el contenido bajo el velo de la hoja.
- Firefox sin interfaz: siete capturas (columna desplegada y plegada, recetas, inicio, hoja «Más», 320 px y tableta) sin diferencias visibles respecto de Chrome.
- 580 pruebas de Django (26 nuevas del menú), 63 de Node, `manage.py check`, `makemigrations --check` y `tools/verificar_spec_02_http.py` aprobados.
- Pendientes: probar en un celular y un iPad reales (Safari de iOS, Chrome de Android), con un lector de pantalla (NVDA, TalkBack o VoiceOver) y la prueba de usabilidad con al menos cinco personas (RNF-04). No se activó `viewport-fit=cover`: `env(safe-area-inset-bottom)` queda previsto para cuando se active. Las compensaciones de `menu.css` cubren las pantallas vistas (inicio, tablero de Recetas); revisar otras si se agregan diseños de varias columnas.

Cambios que acompañaron al paso a PostgreSQL y conviene conocer:

- **`UPDATE` condicional sin cruzar tablas.** Con un filtro como `usuario__is_active=True`, Django genera `id IN (subconsulta)` y PostgreSQL no vuelve a evaluar la subconsulta tras esperar el bloqueo: dos confirmaciones simultáneas de correo pasaban. `confirmar_correo` ya no cruza la relación y comprueba la cuenta activa dentro de la misma transacción. Cualquier `UPDATE` condicional nuevo debe filtrar solo por campos propios de la tabla.
- **`procesar_cola`** llama a `close_old_connections()` solo con `--continuo`: en una transacción (pruebas) PostgreSQL sí cierra la conexión.
- Las herramientas `tools/verificar_spec_0X_http.py` siguen usando una SQLite temporal, para no tocar la base real.

## Pantalla pública y voz — spec 06

| Archivo | Responsabilidad |
|---|---|
| `turnosapp/models.py`, `migrations/0003_anuncio_sala.py` | `AnuncioSala`: copia de número, ventanilla, acción e instante, con id global y vínculo único/protegido al evento privado. Sin relación directa con paciente/receta/turno. |
| `turnosapp/sala.py`, `cola.py`, `atencion.py` | Registro atómico e idempotente del llamado y re-llamado; proyección explícita del estado público de la jornada chilena. Si falla el anuncio, se revierte el llamado. |
| `turnosapp/vigilante.py` | Una tarea por proceso solo con pantallas conectadas; seis consultas cada 0,5 s, cursor más repaso de 30 s y deduplicación por conexión. Envía ids en orden por lectura, incluyendo el menor que confirma tarde. Un error reintenta sin exponer detalles; saturación cierra 1013 para recuperar estado. |
| `consumers.py`, `routing.py`, `cesfam/asgi.py` | Canal `/ws/sala/` de salida con origen validado, 20 conexiones totales/5 por dirección, límite de 4096 bytes entrantes y latido de 15 s. Sin sesiones ni permisos privados. HTTP continúa en Django; `runserver` sirve ASGI y estáticos con Daphne. |
| `views.py`, `urls.py`, `base_sala.html`, `sala.html` | `/turnos/sala/`: GET/HEAD, `no-store`, sin cookies. Tarjetas, seis recientes (20 en estado), cantidad en espera por letra (P, G, C, U, sin números; RF-06-13), códigos P-014 en tarjetas/recientes y hora del servidor. Sin navegación privada ni estimación de espera. |
| `static/js/sala.js` | Pintado con nodos/texto, ids vistos en memoria de la jornada, reconexión 1–10 s del WebSocket (sin respaldo HTTP), reloj monotónico desde el servidor y limpieza a medianoche. Sonido por gesto, voz es-CL/es, tono y dos repeticiones con 1,5 s; cinco pendientes sin cortar el actual, vigencia 60 s, sin pronunciar historial inicial. |
| `static/css/sala.css`, `coreapp/navegacion.py` | Texto ampliable, contraste de la paleta, foco y región viva, sin destellos; enlace público solo visible para Técnico/Q.F./superusuario, en otra pestaña con `noopener`. |
| `tools/verificar_spec_06_http.py` | Coordinador sin Django propietario del temporal; emisor/cliente en otro proceso y servidor ASGI separado. 670 pacientes/turnos, 100 anuncios a dos clientes websockets y 96 cierres reales del 05; cuatro paneles privados consultan durante la medición. Cierra procesos antes de eliminar SQLite en Windows. |

No se agrega un servicio de mensajes: la base durable comunica procesos y la capa de canales en memoria distribuye solo en el proceso web propio. No exponer el evento/UUID interno en serialización pública. Mantener `procesar_cola --continuo` según el 05; el GET y el vigilante nunca recuperan ni escriben pendientes.

Medición final aislada: p95 confirmación → recepción en ambas pantallas **444,12 ms**, máximo **536,66 ms**; 100 muestras por pantalla. HTTP de la sala (medido antes de retirar `/turnos/sala/estado/`) y panel privado también bajo 2 s. Ver `specs/06-pantalla-sala-y-voz/validation.md` para carga, regresión y límites. La voz/televisor reales, navegador/axe, usabilidad y aceptación siguen pendientes; no se declara Implementado ni se migra automáticamente la base del proyecto.

## Preparación y tiempos de espera — spec 07

| Archivo | Responsabilidad |
|---|---|
| `recetasapp/models.py`, `migrations/0004_preparacionreceta.py` | `PreparacionReceta`, una por cada `TurnoReceta`, con recepción, marca, actor e intervalo de trabajo. La relación protege el historial. |
| `turnosapp/services.py` | Crea la preparación dentro de la misma transacción de emisión; los reintentos recuperados no duplican. El resultado incluye la frase de espera recalculada. |
| `recetasapp/services.py` | Marcar/corregir «Lista», retiro posterior idempotente y auditoría. El retiro conserva el vínculo y cierre originales; valida vigencia a la fecha de preparación y cupo actual. |
| `recetasapp/preparacion.py` | Cola de preparación y pendientes de retiro derivados; promedio de intervalos de trabajo, con ventana de 14 días, mínimo 5 muestras y descarte sobre 30 minutos. |
| `turnosapp/espera.py`, `turnosapp/panel.py` | Estimación compartida en minutos, frase única y conteo de ventanillas activas; el panel expone pendientes, promedio/muestras y enlace a Recetas. |
| `recetasapp/views.py`, `forms.py`, `urls.py`, `templates/recetas/preparacion*.html` | Páginas privadas de preparación y retiro, búsqueda de pendientes por POST, formularios CSRF y respuestas `no-store`. |
| `static/css/preparacion.css`, `static/js/preparacion.js` | Estados de texto y filas adaptables; consulta cada 5 s y reemplaza solo el fragmento de lista si cambió. |
| `tools/verificar_spec_07_http.py` | SQLite temporal, HTTP real en loopback, 670 pacientes sintéticos, cuatro ventanillas y 100 recorridos de emisión, marca, ausencia y retiro; p50/p95/máximo por acción y panel. |

La sección vive en Recetas y no agrega entrada al menú. La cifra de trabajo mide tiempo desde la recepción o la marca anterior del mismo usuario ese día, la que sea posterior; no equivale al tiempo total de espera del paciente. HU-18 se cubre parcialmente: la estimación actualiza la interfaz del personal, pero no la sala, el tótem ya emitido ni el comprobante impreso. El p95 HTTP de loopback con SQLite sintética fue menor de 110 ms en cada escenario; ver `specs/07-preparacion-y-tiempos-de-espera/validation.md` para valores detallados y límites. Revisión visual/axe y usabilidad siguen pendientes; no declarar el spec Implementado ni migrar la base del proyecto automáticamente.

## Domicilios y entregas a domicilio — spec 08

| Archivo | Responsabilidad |
|---|---|
| `entregasapp/models.py`, `migrations/0001_initial.py` | `Domicilio` (uno por paciente, versión para edición concurrente), `FotoDomicilio` (posición 1–3 única), `InscripcionReparto` (una vigente por paciente), `Entrega` (una abierta por paciente, restricción parcial), `RecetaEntrega` (recetas fijadas y su resultado) e `IntentoEntrega` (un pendiente por entrega, resultado inmutable, `operacion_id` del registro y `creado_con` de la operación que lo creó). Sin registro en el Admin. |
| `entregasapp/services.py` | Única vía de escritura: domicilios, verificación (solo el encargado, comprobación exacta sin `tiene_rol`), fotos (`gestionar_fotos`, enmienda del 2026-11-15: borrados y fotos nuevas en una transacción, todo o nada, con la lista de fotos vistas y un UPDATE sin cambio sobre la fila del domicilio que ordena los guardados simultáneos; errores numerados con `ErrorFoto`; archivos nuevos borrados si falla y los borrados eliminados al confirmar), excepciones, programación (individual y por lote: `recetas_para_despacho_lote`, `programar_lote`, una transacción por paciente y operación derivada del lote con `uuid5`), registro, reasignación, anulación y revisión. UPDATE condicional sobre campos propios, restricciones, reintentos y auditoría sin datos personales; la programación y el ciclo de la entrega toman `bloquear_cola(hoy)`. |
| `entregasapp/notificaciones.py` | Bandeja de avisos por correo del spec 12: «en camino» (al iniciar el traslado) y «del día» (`encolar_del_dia`, entre `REPARTO_AVISO_DIA_HORA` y `REPARTO_AVISO_DIA_LIMITE`, uno por entrega y fecha). El destino es `Paciente.correo_avisos`, filtrado por `REPARTO_CORREO_DOMINIOS_PERMITIDOS` (`destino`), con firma HMAC y revalidación antes del envío; reserva con token, reintentos acotados y estado incierto sin reenvío. El comando `procesar_avisos_reparto` la procesa fuera de las solicitudes web. |
| `entregasapp/consultas.py` | Lectura: elegibilidad (postrado, `edad >= 80` desde el 2026-11-13, o excepción), lista de «Programar entrega» con filtros de motivo, localidad y «Sin sector» (`elegibles`, `localidades_elegibles`, `motivos_de`), estado derivado del domicilio (con aviso de padrón cambiado), «Mis entregas», pendientes de gestión y programadas con su último intento (una consulta), recetas no descontadas y `recetas_con_despacho_abierto`, que usan el 03, el 04 y el 05 para el bloqueo de doble vía. |
| `entregasapp/fotos.py`, `coreapp/utils/custom_image.py` | Almacenamiento privado en `ARCHIVOS_PRIVADOS_ROOT`, sin URL pública; validación JPEG/PNG, límites de 5 MB y 40 MP, orientación, aplanado, lado mayor de 1600 px y JPEG nuevo sin metadatos. |
| `entregasapp/views.py`, `forms.py`, `urls.py`, `templates/entregas/*.html` | Pantallas privadas `no-store` con la matriz de permisos del spec. Búsquedas por RUT en POST; los filtros sin datos personales van en GET. Las URL solo llevan identificadores internos. «Programar entrega» (ampliación del 2026-11-13): `programar/lista/` (fragmento por POST para la búsqueda en vivo), `programar/varios/` (fecha, encargado y revisión con contexto firmado por `django.core.signing`) y `programar/varios/confirmar/` (tramos de hasta 25 en JSON sin RUT ni nombres, o el lote completo sin JavaScript); plantillas `_programar_lista.html`, `programar_varios.html` y `_programar_resumen.html`. Fotos (enmienda del 2026-11-15): `domicilios/<id>/fotos/` (`FotosView`, `FotosForm`) atiende el modal con `Accept: application/json` y, sin JavaScript, la página `fotos.html`; `volver` solo admite rutas del mismo sitio. Parciales `_fotos_boton.html` (botón «Registrar fotos» o «Gestionar fotos» y su `<dialog>`), `_fotos_formulario.html`, `_miniatura_foto.html` y `_visor_foto.html` (uno por página, en `entregas/base.html`). Se retiraron `foto_agregar` y `foto_eliminar`. |
| `static/css/entregas.css`, `static/js/entregas/ubicacion.js`, `programar.js`, `fotos.js`, `visor.js` | Tarjetas de «Mis entregas» para celular, estados con texto e ícono, sin colores propios. La ubicación se pide solo al pulsar el botón y se anuncia en una región `aria-live`. `programar.js` (Alpine): búsqueda en vivo con espera de 300 ms, cancelación y descarte de respuestas viejas, selección que sobrevive a páginas y filtros, y confirmación del lote por tramos con `<progress>` y reintento; pruebas en `entregasapp/tests/programar.test.cjs`. `fotos.js` (modal de fotos: espacios según las marcadas para borrar, vista previa, envío único y error junto a la foto indicada; sin red no envía) y `visor.js` (imagen ampliada en `<dialog>`, cierre con X, clic fuera o Esc y foco de vuelta en la miniatura), con `fotos.test.cjs` y `visor.test.cjs`. |
| `recetasapp/models.py` (`edad_en`, `requiere_despacho_en`), `turnosapp/services.py`, `recetasapp/services.py`, `turnosapp/atencion.py` | Regla única de edad/postración compartida con el tótem; el tótem omite las recetas en despacho (`despacho_abierto` sin consumir número); la confirmación del 03/05 rechaza la receta con entrega abierta y acepta el camino `desde_despacho` del encargado; la reincorporación del 05 se rechaza si una receta del turno está en una entrega abierta. |
| `coreapp/navegacion.py`, `coreapp/views.py`, `templates/index.html`, `templates/components/iconos.html` | Entrada «Entregas» para la farmacia; «Mis entregas» y «Domicilios» (ícono `i-casa`) para el encargado (íconos `i-camara` e `i-cerrar` para el modal de fotos y el visor), cuyo inicio (`/`) muestra «Mis entregas» sin redirigir. |
| `recetasapp/views.py`, `templates/recetas/paciente_detalle.html`, `receta_detalle.html`, `entrega_confirmar.html` | Bloque «Domicilio de reparto» en la pestaña Datos, rótulo «A domicilio» en Entregas y aviso «En entrega a domicilio abierta» sin botón de confirmar. |
| `tools/verificar_spec_08_http.py` | SQLite y carpeta privada temporales, 670 pacientes sintéticos, 10 excepciones, cuatro encargados; recorre el ciclo completo por HTTP y mide p50/p95/máximo por escenario; desde el 2026-11-13 mide también la lista y su fragmento, la revisión del lote completo, los tramos de 25 y el tótem durante un lote (40 pacientes presenciales); desde el 2026-11-15, el guardado de fotos del modal (p95) y tres fotos de casi 5 MB aparte. |

Las fotos (`privado/`) son datos personales: nunca se versionan ni se sirven por `/media/`. La parte sin conexión de HU-15 está en el spec 11; el mapa y el orden de visita, en el 09. Ver `specs/08-domicilios-y-entregas/validation.md` para la evidencia y los límites.

## Mapa y orden de visita — spec 09

| Archivo | Responsabilidad |
|---|---|
| `entregasapp/ruta.py` | Módulo puro, sin Django: `ordenar` (vecino más cercano y 2-opt con extremos fijos, hasta 200 paradas; desempate por la clave del intento), `insertar` (inserción más barata), `longitud_m` y `formatear_distancia`. Reciben una función `distancia(a, b)`: desde la enmienda del 2026-11-15, la de la matriz de OSRM, que puede diferir de ida y de vuelta (el 2-opt suma las calles internas invertidas con sumas acumuladas); sin ella, `distancia_m` (haversine). Determinista y probado sin base. |
| `entregasapp/osrm.py` | Cliente del OSRM propio (RF-09-19), solo con la biblioteca estándar y sin proxies del entorno: `tabla` (matriz por camino; la de la ruta, sin la posición, se guarda 10 minutos en la caché) y `tramo` (distancia y geometría `[lat, lon]`). Coordenadas como `longitud,latitud` con 6 decimales. Tiempo agotado, error de red, código distinto de `Ok`, JSON mal formado o distancia nula dan `OsrmNoDisponible`, sin coordenadas en el mensaje. `OSRM_URL` vacía lo desactiva. |
| `entregasapp/consultas.py` (`ruta_del_dia`, `partida_del_dia`, `registradas_hoy`, `orden_guardado`, `distancia_por_camino`) | La ruta se calcula en cada lectura y no escribe nada: hoy y atrasadas sin resultado, partida desde la última visita registrada con coordenadas (o el CESFAM), orden guardado cruzado con la ruta vigente y visitas nuevas por inserción más barata. Orden, «Nuevas» y total por camino (`RutaDelDia.distancia = "camino"`); si OSRM no responde, línea recta (`"recta"`) sin total, y un orden guardado no cambia. Número de consultas a la base constante. `mis_entregas` y `contar_mis_entregas` del 08 se conservan. |
| `entregasapp/models.py` (`OrdenRuta`, `ParadaRuta`), `migrations/0002_ordenruta.py` | Un orden por encargado y día (`orden_ruta_unico`), con `version` y `ultima_operacion`; paradas con intento y posición únicos por orden. Es una preferencia: se reemplaza o se vacía. |
| `entregasapp/services.py` (`mover_parada`, `restablecer_orden`) | Solo el encargado (comprobación exacta). El primer guardado crea el orden (restricción y reintento); los siguientes suben la versión con un UPDATE condicional sobre campos propios. Versión distinta: «Tu orden cambió en otro dispositivo; revisa la lista.». Auditoría `ruta.ordenada` y `ruta.restablecida` con el tipo y el id del orden. No toma `bloquear_cola`: no toca recetas ni turnos. |
| `entregasapp/mapa.py` | Datos del mapa para `json_script`: coordenadas, número, estado, nombre, sector, localidad, dirección y referencias; nunca RUT, teléfono, notas, fotos ni la posición del encargado. Sin línea del recorrido; `distancia`, `total_km` (None en el respaldo) y, solo para el encargado hoy, las rutas de Django del tramo, la parada más cercana y mover. En «Rutas», sin enlaces de acción. `datos_usar_mapa` (CESFAM y teselas) para «Usar mapa». |
| `entregasapp/checks.py`, `apps.py`, `cesfam/settings.py`, `coreapp/ejecutor_pruebas.py` | `REPARTO_ORIGEN_*`, `MAPA_*`, `OSRM_URL` y `OSRM_TIEMPO_ESPERA` con valores por defecto; `check` informa `entregasapp.E001` (origen), `E002` (URL de teselas), `E003` (zoom), `E004` (dirección de OSRM) y `E005` (tiempo de espera). `TEST_RUNNER` desactiva OSRM en las pruebas; cada prueba que lo necesita usa `entregasapp/tests/osrm_simulado.py`. |
| `entregasapp/views.py`, `forms.py`, `urls.py` | `/entregas/mis/` (tarjetas compactas, flechas, franja y «Volver al orden sugerido»), `/mis/mapa/`, `/mis/ir/<pk>/`, POST `/mis/orden/mover/` (con `Accept: application/json` responde el orden, la versión, el rótulo y el total; 409 en conflicto) y `/mis/orden/sugerido/`, POST JSON `/mis/tramo/` y `/mis/cercana/` (solo el encargado, CSRF, 30 por minuto por cuenta, destino leído de la ruta en la base, `no-store`; 400, 403, 404, 429 y 503 con `{"error"}`), y `/entregas/rutas/` (Q.F. y superusuario, `?encargado=&fecha=`). Pestañas: el encargado suma «Mapa»; la Q.F. y el superusuario, «Rutas». |
| `templates/entregas/_ruta.html`, `_ruta_rotulo.html`, `_ruta_resumen.html`, `_tarjeta_intento.html`, `_orden_controles.html`, `mis_entregas.html`, `mapa.html`, `_mapa.html`, `ir_a.html`, `rutas.html`, `_mapa_punto.html`, `domicilio.html`, `_dialogo_usar_mapa.html` | Lista como vista principal y accesible, con tarjetas compactas (`data-compacta`, detalle visible sin JavaScript) y flechas como formularios POST sin JavaScript; se retiró «Mover a la posición». El mapa con enlace para saltarlo, leyenda en texto y aviso si falla el mapa base; los controles del tramo solo para el encargado. «Usar mapa» es un `<dialog>` con mira central. |
| `static/vendor/leaflet/`, `static/js/entregas/mapa.js`, `tramo.js`, `ir_a.js`, `tarjetas.js`, `orden.js`, `usar_mapa.js`, `static/css/entregas.css` | Leaflet 1.9.4 local con licencia BSD-2-Clause; las teselas usan `referrerPolicy: "strict-origin"`. `mapa.js`: marcadores con nombre y teclado, resumen con `textContent`, tramo como línea continua, parada más cercana con otra forma y la guía del «Mapa». `tramo.js`: umbrales de recálculo (150 m y 20 s; 30 m y 10 s cerca), cliente con `AbortController` y descarte de respuestas viejas, y seguimiento con `watchPosition` que se detiene con «Detener», `pagehide` u ocultar la página. `ir_a.js`: la guía de una parada por camino, sin rumbo. `tarjetas.js`: «Expandir»/«Contraer» y mapa pequeño al expandir. `orden.js`: flechas por `fetch` y arrastre propio (Pointer Events, toque largo, hueco, desplazamiento en los bordes, Esc, reversión). `usar_mapa.js`: marcar el domicilio en un diálogo. Pruebas de Node con un DOM simulado (`dom_simulado.cjs`). |
| `entregasapp/management/commands/generar_domicilios_demo.py` | Solo para la base de demostración: domicilios sintéticos reproducibles dentro de un radio del origen, mediante `guardar_domicilio`; simulación sin `--aplicar`; exige una cuenta Q.F. o superusuario. |
| `coreapp/navegacion.py` | «Mis entregas» marca activas sus páginas nuevas y «Entregas» marca «Rutas»; sin entradas nuevas en el menú. Íconos `i-arriba`, `i-abajo` e `i-brujula` en `iconos.html`. |
| `tools/verificar_spec_09_http.py` | SQLite temporal, 670 pacientes, 660 domicilios generados y 10 sin coordenadas, cuatro encargados con 50 visitas y un OSRM simulado; p50/p95/máximo por escenario (incluidos el tramo y la parada más cercana) y cálculo con 200 paradas; con `--osrm-real`, matriz de 52 y 202 puntos y un tramo contra el OSRM local. |

Despliegue previsto (enmienda del 2026-11-15):

```text
Celular o computador ──HTTPS──▶ Django (Daphne/ASGI) ──red interna──▶ OSRM (osrm-routed, MLD, Ñuble)
        │                              │
        │                              └──────────────▶ PostgreSQL
        └──HTTPS (teselas, sin datos de pacientes)──▶ OpenStreetMap
```

Solo Django habla con OSRM; el navegador nunca conoce su dirección. La posición del encargado llega a Django solo para calcular un tramo o la parada más cercana, y no se guarda en la base, la sesión, la caché, la auditoría ni los registros; OSRM corre con `--verbosity WARNING` para no registrar las URL con coordenadas. Si OSRM no responde, el orden cae a la línea recta rotulada y sin total. Mapas, tramos y el modal de fotos necesitan señal (el spec 11 no los lleva al celular). Instalación de OSRM en `README.md`; evidencia y límites en `specs/09-mapa-y-orden-de-visita/validation.md`.

## Gestión de turnos por personal (spec 10)

| Archivo | Contrato |
|---|---|
| `turnosapp/atencion.py` | `terminar_turno_ventanilla`, `reclasificar_turno` y `marcar_urgencia` usan `_operar`: `bloquear_cola`, operación idempotente por UUID y roles por tipo (`ROLES`). El término devuelve el llamado de hoy a la fila con su `entrada_cola` o cierra el de otro día; deshabilita la ventanilla y cierra la ocupación. |
| `turnosapp/models.py`, migración `0013` | `EventoTurno.letra_anterior` y `numero_anterior`, con restricción de coherencia. Eventos `devuelto_a_cola`, `reclasificado` y `urgencia`. |
| `usuariosapp/services.py` | `cambiar_estado_cuenta` termina la ventanilla del Técnico que se desactiva, en la misma transacción. |
| `turnosapp/vistas_operacion.py`, `terminar.html`, `historial.html`, `comprobante_personal.html` | Término de turno con confirmación (Q.F. desde Ventanillas, Técnico desde su panel); cambio de fila y urgencia desde el historial; comprobante PDF a pantalla completa solo para quien hizo el cambio, 15 minutos, sin impresión. |
| `turnosapp/comprobante.py` | Campo opcional `reemplaza`: recuadro «Reemplaza a tu número anterior» con el código anterior. |
| `tools/verificar_spec_10_http.py` | SQLite temporal, 670 pacientes, cuatro ventanillas: 30 urgencias, 30 cambios de fila, PDF y término de turno con p95. |

## Panel de mermas (spec 13)

Desde la enmienda del 2026-11-25 es un dashboard de mermas y entregas, sin datos personales; la derivación al reparto se inicia en «Pendientes de retiro».

| Archivo | Contrato |
|---|---|
| `indicadoresapp/periodos.py` | Ocho períodos por GET (`periodo`, `ref`, `desde`, `hasta`, `tipo`): 1, 3, 7 y 14 días (terminan hoy), Mes, Semestre y Año de calendario (con «‹ ›») y Personalizado (hasta 366 días). Por omisión, el mes en curso; `desde`/`hasta` sin clase abren como Personalizado. Granularidad: Mes por día, Semestre por semana, Año por mes; el resto, por largo (31/186 días). `anterior_equivalente()` para la comparación. El método del formulario es `elegido()` (no `periodo()`, que taparía el campo). |
| `indicadoresapp/mermas.py` | Lectura pura. Una receta cuenta si su preparación quedó lista y su turno cerró sin entregarla en esa atención (sin `DetalleCierre.entregada`). Cuatro estados: `sin_retirar`, `en_despacho`, `tarde` y `despacho`; la merma es la suma de los dos primeros. Suma `en_atencion` (preparadas y entregadas en su atención), `merma_por_dia` y «más de 14 días». Rango por fecha local de preparación; tipo por `Paciente.es_cronico`. Agrega en Python (igual en SQLite y PostgreSQL). |
| `indicadoresapp/canales.py` | Tabla por canal en recetas: farmacia por fecha del turno (entregadas en la atención, más las de la ficha por su fecha; «retiradas después»), domicilio por fecha del registro de la visita (descontadas frente a visitas fallidas y no descontadas). Motivos: farmacia por receta (ausente, sin atención al cierre y `DetalleCierre.causa`, vacía = «Otro»), domicilio por visita (`IntentoEntrega.Motivo`). `por_dia` alimenta los gráficos diarios y el CSV; `promedios_farmacia` lee los 6 días previos. |
| `indicadoresapp/ausentes.py` | Grilla día × hora por la hora local de emisión (`Turno.creado_en`); ausente = estado actual «ausente». |
| `indicadoresapp/tablero.py` | `armar(periodo)` junta todo en un `Tablero` solo con cifras y arma las cuatro cifras clave con su comparación escrita (`tendencia` y `sentido` solo para color y flecha). |
| `indicadoresapp/reportes.py` | Excel (hojas «Resumen», «Datos de gráficos», «Por día» y «Ausentes por hora»; cinco gráficos nativos), CSV por día (`;`, UTF-8 con BOM; columnas en `canales.columnas_csv`) y PDF (ReportLab, sin compresión). Solo reciben `DatosReporte` con cifras agregadas: nunca RUT, nombres, identificadores ni el texto de «Otro». |
| `indicadoresapp/views.py`, `templates/indicadores/` | Dashboard (Q.F., superusuario y Dirección), descargas auditadas con `coreapp.auditoria.registrar_referencia` y página «Derivar a domicilio» (Q.F. y superusuario), cuyo «Volver» lleva a «Pendientes de retiro». Los gráficos (calendario con «Aún no», columnas simples o apiladas, barras con porcentaje, barra al 100 % con textura y grilla de calor) se calculan en `indicadoresapp/graficos.py` y se dibujan en HTML/SVG; la ayuda al pasar el puntero es `static/js/graficos.js`. Estilos en `static/css/indicadores.css`, solo con variables de `base.css` y `tema_oscuro.css`. |
| `turnosapp/models.py`, migración `0014` | RF-05-14: `CausaNoEntrega` y `causa` en `CierreAtencion` y `DetalleCierre`; `motivo` sigue con el texto legible («Sin stock», «Otro: …»). `finalizar_atencion(..., causa=, causas=)`; sin código, el texto libre se guarda como «Otro». |
| `entregasapp/services.py` | `derivar_desde_merma`: excepción (si hace falta) y entrega en una transacción, bajo `bloquear_cola`, idempotente por UUID; lleva las preparaciones «Sin retirar» y las otras recetas elegibles. `registrar_entregada` evalúa lo preparado a su fecha de preparación y liga la entrega al vínculo del turno. |
| `entregasapp/models.py`, migración `0003` | `RecetaEntrega.preparacion` (opcional). Una preparación no queda en dos despachos abiertos porque cada paciente tiene a lo más una entrega abierta. |
| `recetasapp/preparacion.py`, `_pendientes_resultados.html` | `pendientes_retiro` anota `en_despacho`; «Pendientes de retiro» muestra «En despacho» sin botón de retiro y, para la Q.F. y el superusuario, «Derivar a domicilio» en las filas «Sin retirar» (RF-07-13). |
| `coreapp/roles.py`, `navegacion.py`, `views.py` | Rol `DIRECTOR` («Dirección del CESFAM»), solo consulta: menú con «Mermas» y «Mi perfil», inicio `/` con el dashboard y 403 en el resto. Solo el superusuario administra sus cuentas. |
| `tools/verificar_spec_13_http.py` | SQLite temporal, 670 pacientes y 366 días sintéticos (preparaciones, causas, ausentes por hora y visitas): dashboard en seis períodos, Excel/CSV/PDF del mes y del año, acceso del Director y 20 derivaciones desde «Pendientes de retiro», con p95. |
| `indicadoresapp/management/commands/generar_mermas_demo.py` | Solo demostración: historial de días anteriores con recetas preparadas sin retirar (y una parte retirada después con el servicio del 07), con hora de emisión y causa de no entrega, sobre el padrón importado. No crea entregas en la atención ni visitas. Sin `--aplicar --cuenta <Q.F.>` solo simula. |

## Reparto sin conexión — spec 11

| Archivo | Contrato |
|---|---|
| `entregasapp/sin_conexion.py` | `paquete_del_dia` (solo lectura de `consultas.ruta_del_dia`: hoy y atrasadas, en el orden de la ruta, sin RUT, fotos, coordenadas, correo ni medicamentos) y `sincronizar` (cada registro con `registrar_entregada`/`registrar_no_entregada` en su propia transacción; respuestas `aplicado`, `ya_aplicado`, `rechazado` con código de `Rechazo`, o `reintentar`). Los rechazos se auditan como `intento.sincronizacion_rechazada` con `objeto_id` «intento:código», sin la nota. |
| `entregasapp/services.py` | `registrar_entregada`/`registrar_no_entregada` aceptan `registrado_en` (hora del celular): `_hora_del_registro` aplica 5 min de tolerancia y 2 días de plazo, la vigencia se evalúa a la fecha local del registro y se guarda `IntentoEntrega.sincronizado_en` (migración `0007`). Sin el parámetro, todo sigue como en el 08. |
| `entregasapp/notificaciones.py` | `encolar_resultado(..., registrado_en=)`: vigencia de 2 h desde el registro; si ya pasó, «omitido» con `registro_tardio`. |
| `entregasapp/views.py`, `urls.py` | `PaqueteView` (`GET /entregas/mis/paquete/`), `SincronizarView` (`POST /entregas/mis/sincronizar/`, JSON con `X-CSRFToken`, hasta 50 registros, 413 si son más, 30 por minuto por cuenta) y `SinConexionView` (`/entregas/mis/sin-conexion/`, sin datos). Solo el encargado (comprobación exacta); otras cuentas, 403 en JSON. |
| `templates/pwa/sw.js`, `coreapp/views.py` | Caché `cesfam-<huella de las URL de los estáticos>`; borra las anteriores al activarse. Estáticos de la lista: caché primero. Navegaciones de `/` y `/entregas/…`: red primero y, sin red, la vista sin conexión. JSON, POST, fotos, `/turnos/`, tótem y sala: sin intervenir. Mensaje `guardar-sin-conexion` y evento `sync` (`cesfam-registros`). |
| `static/js/entregas/almacen.js` | IndexedDB `cesfam-reparto` con `paquete` (por cuenta, solo de hoy), `cola` (clave `operacion_id`; uno por intento y cuenta; se borra a los 2 días) y `meta` (cuenta activa y token CSRF). Adaptador en memoria para Node. |
| `static/js/entregas/sincronizar.js` | Envío compartido por la página y el service worker: lotes de 50, sin seguir redirecciones, solo la cuenta activa. |
| `static/js/entregas/sin_conexion.js`, `templates/entregas/_estado_sin_conexion.html`, `sin_conexion.html` | Barra de estado (`aria-live`), descarga del paquete en «Mis entregas», intercepción del formulario de «Registrar visita» solo ante fallo de red, vista sin conexión con validación del 08, «Deshacer», «No se pudo enviar» y «Entendido»; reintento cada 30 s y al volver la señal. |
| `static/js/pwa.js`, `templates/components/Layout/base.html` | Registro del service worker; con `data-cuenta`, cuenta activa y limpieza de la ruta de otra cuenta u otro día; al salir con pendientes, aviso con la cifra y confirmación; borra la ruta y conserva la cola. |

Pruebas: `test_sin_conexion_hora.py`, `test_sin_conexion_paquete.py`, `test_sin_conexion_sincronizar.py`, `test_concurrencia_sin_conexion.py`, casos nuevos en `test_avisos_resultado.py` y `coreapp/tests/test_estaticos.py`; Node: `almacen.test.cjs`, `sincronizar.test.cjs`, `sin_conexion.test.cjs`, `pwa.test.cjs`. Medición aislada: `tools/verificar_spec_11_http.py`. Evidencia y límites en `specs/11-reparto-sin-conexion/validation.md`.

## Búsqueda instantánea en las listas

Las listas con buscador se actualizan mientras se escribe o se cambia un filtro, como «Programar entrega» (que conserva su propio `programar.js` por la selección de varios pacientes): Pacientes, Todas las recetas, Pendientes de retiro, Domicilios y Excepciones de reparto. El RUT o el nombre siguen viajando solo por POST y sin JavaScript todo funciona como antes, con «Buscar» y la paginación.

| Archivo | Contrato |
|---|---|
| `coreapp/busqueda.py`, `templates/components/busqueda_en_vivo.html` | Un POST con la cabecera `X-Busqueda-En-Vivo: 1` recibe solo las zonas de la página, dibujadas con el mismo contexto; un GET o un POST sin la cabecera, la página completa. `FarmaciaView.render` y `EntregasView.render` aceptan `zonas=(...)`. |
| `templates/recetas/_pacientes_*.html`, `_recetas_*.html`, `_pendientes_*.html`, `templates/entregas/_domicilios_*.html`, `_excepciones_resultados.html` | Zonas (`data-zona`): resultados, filtros o «Quitar filtros»/«Limpiar». La página las incluye en su lugar; el fragmento las devuelve juntas. El texto con `data-anuncio` (cantidad o lista vacía) es lo que se anuncia. |
| `static/js/busqueda_en_vivo.js` | Sin Alpine. `form[data-en-vivo="busqueda"]`: espera de 300 ms al escribir o cambiar una lista desplegable; «Buscar», Enter y los botones de filtro, al instante; cancela la solicitud anterior y descarta respuestas viejas; una búsqueda nueva vuelve a la primera página. `form[data-en-vivo="pagina"]`: cambia de página sin recargar y lleva el foco al resumen. Reemplaza solo las zonas (el campo nunca está en una), devuelve el foco al botón equivalente, anuncia en una región `role="status"` y, si falla, muestra el aviso con «Reintentar»; si la sesión venció, sigue a la página de inicio de sesión. Pruebas en `coreapp/tests/busqueda_en_vivo.test.cjs`. |
| `static/css/base.css` | `.zona-en-linea` (`display: contents`) para «Quitar filtros» junto a «Buscar», y el aviso de error. Desde el 2026-11-23 los buscadores no muestran la ayuda «La lista se actualiza mientras escribes»; `busqueda_en_vivo.js` sigue mostrando y asociando al campo cualquier ayuda `data-solo-js` que se agregue. |

En Pacientes y Recetas, «Buscar» lleva el filtro vigente para que Enter no lo pierda; al pulsar un botón de filtro en vivo, el script le copia ese valor. Excepciones de reparto ya no muestra «No encontramos pacientes» con el campo vacío: sin texto, la zona queda vacía.

Verificación (2026-11-19, vista previa con SQLite temporal y datos sintéticos): Chrome (panel del navegador) y Firefox 160 sin interfaz por WebDriver BiDi, con teclado y clics reales. Una sola solicitud al escribir de corrido, foco y cursor en el campo, filtro con el foco de vuelta en su botón, paginación con el foco en el resumen, lista desplegable con teclado e inscripción de una excepción desde un formulario llegado en vivo (CSRF válido); sin errores en la consola. axe-core 4.10.2 (WCAG 2.0, 2.1 y 2.2 A y AA) sobre las cinco pantallas después de una actualización en vivo, y con el aviso de error visible: **0 violaciones**. Pruebas: `coreapp/tests/test_busqueda_en_vivo.py` (las cinco pantallas, que la página y el fragmento muestren lo mismo en cada zona, permisos y sesión) y 13 de Node. Se corrigió de paso el plural «preparacións» del resumen de Pendientes de retiro, que ahora también se anuncia. Pendientes: lector de pantalla real (NVDA, TalkBack o VoiceOver), celular real y la prueba de usabilidad (RNF-04).
