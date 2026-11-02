# Estructura del proyecto

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
│   │   ├── Layout/           base.html           base_publica.html
│   │   └── navbar.html       footer.html         paginator.html  mensajes.html
│   ├── registration/         login.html
│   └── pwa/                  sw.js
├── static/
│   ├── manifest.webmanifest
│   ├── css/                  base.css
│   ├── js/                   alpine.min.js       alpine.LICENSE.md   pwa.js
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

`venv/`, `.env`, `db.sqlite3`, `media/` y `staticfiles/` se generan localmente y no se versionan.

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
- `sinteticos.py` exige un `random.Random` del llamador y usa cuerpos numéricos ficticios en el intervalo 90.000.000–99.999.999. La generación de listas evita duplicados.
- `rut` devuelve texto vacío ante una entrada inválida. `minutos` convierte segundos a minutos hacia arriba, limita negativos a cero y muestra `—` para valores no numéricos o no finitos.
- La navegación solo enlaza vistas existentes. Las opciones por rol comparten el inicio hasta que sus specs agreguen las pantallas correspondientes.
- El service worker no contiene caché ni manejador `fetch`; el spec 11 define ese comportamiento.

## Archivos que llegan después

El spec 02 ya incorpora perfiles y preparación de grupos/cuentas; la autenticación completa y el panel de usuarios siguen en sus pasos restantes. Los siguientes specs crean modelos de dominio y sus `services.py`; el 06 incorpora WebSocket; el 11, funcionamiento sin conexión; el 12, notificaciones. Esos archivos no se crean como marcadores vacíos en el 01.

## Avance de la spec 02 — pasos 1 a 6

El árbol anterior describe la base del 01. Sobre ella se incorporaron `usuariosapp/models.py` con Perfil, migraciones `0001_initial.py`/`0002_perfiles_existentes.py`, `usuariosapp/services.py` y los comandos `management/commands/crear_roles.py` y `crear_usuarios_demo.py`. Las pruebas están en `usuariosapp/tests/test_perfil.py`, `test_roles.py` y `test_comandos.py`, junto con la adaptación de pruebas del núcleo.

`coreapp.roles.estado_acceso` consulta cuenta activa, perfil y rol único en la base. `CuentaHabilitadaMixin` protege el inicio privado y `RolRequeridoMixin` añade restricciones por rol. La plantilla 403 explica la regularización pendiente y permite cerrar sesión. Uso de los comandos en [README.md](../README.md#roles-y-cuentas-de-demostración).

El paso 3 incorpora `usuariosapp/signals.py`, conectado desde `apps.py`, el helper `coreapp.auditoria.registrar_evento` y `coreapp/admin.py` para consulta técnica de solo lectura de la bitácora por superusuario. Los eventos de creación/asignación demo se escriben en su transacción. Las pruebas nuevas están en `usuariosapp/tests/test_auditoria.py` y `test_admin.py`; se conserva la compatibilidad de las pruebas genéricas del núcleo.

El paso 4 incorpora `usuariosapp/forms.py`, vistas/URLs de perfil y correo, servicios transaccionales en `services.py`, plantillas `templates/usuarios/perfil.html`, `verificar_correo.html` y `templates/registration/verificar_correo_email.txt`, además del enlace Mi perfil. El estado usa los campos de Perfil ya migrados: no requiere nuevas migraciones. La firma vincula usuario, destino pendiente y UUID; GET no consume y POST realiza UPDATE condicional con auditoría. Las pruebas se amplían en `test_perfil.py` y el nuevo `test_correo.py`, incluida concurrencia SQLite.

El paso 5 agrega `usuariosapp/backends.py` y lo configura en `AUTHENTICATION_BACKENDS`. Amplía formulario/vistas/servicios/URLs de login y claves, con las plantillas `registration/password_change_form.html`, `password_reset_{form,done,confirm,complete}.html`, correo/asunto de recuperación y el parcial de campos. Reutiliza tokens/vistas de Django y escribe hash/evento en transacción. Pruebas en `test_login.py` y el nuevo `test_recuperacion.py`, con sesiones y consumo concurrente.

El paso 6 incorpora formularios/vistas/servicios de gestión, rutas bajo `/usuarios/gestion/`, plantillas `usuarios/gestion_lista.html` y `gestion_form.html` y enlace Usuarios. `usuariosapp/admin.py` sustituye el Admin de User, restringe su escritura al superusuario y deja grupos de solo lectura; Perfil no se registra para edición directa. Todas las relaciones y eventos se escriben desde servicios; no hay escrituras M2M posteriores desde Admin ni borrado de cuentas. El historial usa la bitácora filtrada. Pruebas nuevas en `test_gestion_usuarios.py` y ampliación de `test_admin.py`, incluida promoción concurrente. La revisión final del paso 7 sigue pendiente.

## Integración final de la spec 02 — revisión visual pendiente

Se integraron enlaces por permisos y sección activa, accesos desde el inicio y CSS para formularios/selectores/tarjetas adaptables. `usuariosapp/tests/test_integracion.py` comprueba destinos reales y estructura accesible de formularios. La suite completa pasó con 185 pruebas.

`tools/verificar_spec_02_http.py` prepara y elimina exclusivamente una SQLite temporal, aplica 21 migraciones y recorre flujos sobre WSGI real en localhost con datos sintéticos, cookies/CSRF y correo en memoria. No usa la base local. La revisión por navegador está pendiente por indisponibilidad del host y rechazo de acceso a una ventana con contenido ajeno al proyecto. El commit final se reserva para resolver el cierre.

## Identidad visual de la presentación

Rediseño de plantillas y estilos a partir del escudo comunal: campo de gules, tres espigas de oro y un sol naciente. No cambia vistas, URLs, formularios ni servicios; solo la presentación. El login y las pantallas sin sesión comparten un panel de paisaje (sol saliendo sobre surcos que convergen en el horizonte, con las tres espigas); las pantallas con sesión usan cabecera ladrillo, migas de pan, azulejos de acceso y paneles planos.

| Archivo | Responsabilidad |
|---|---|
| `static/css/base.css` | Tokens y componentes. Paleta del equipo: trigo `#FEF2A0`, arena `#F3CD97`, naranja `#E98B50`, ladrillo `#BC4F4F`, más tinta `#2A1613`. Cada pareja `--x-texto`/`--x-fondo` se verifica en `coreapp/tests/test_estaticos.py` (mínimo 4,5:1). |
| `static/fonts/` | Bitter (títulos) y Atkinson Hyperlegible Next (texto y formularios), WOFF2 locales con licencia OFL (`LICENSE.md`). Sin CDN: la prueba de plantillas lo prohíbe y el reparto debe cargar sin señal. |
| `static/js/preferencias.js` | Control de tamaño de texto (normal, grande, muy grande: 18, 21 y 24 px) guardado solo en `localStorage`; sin datos personales. Se carga sin `defer` para no producir un salto al pintar. |
| `static/css/admin.css`, `templates/admin/base_site.html` | Piel de la administración de Django con las mismas variables que ella expone. |
| `static/icons/marca.svg`, `icon-192.png`, `icon-512.png` | Marca y iconos PWA. Se regeneran con `tools/generar_iconos_pwa.py`, que necesita Pillow (no es dependencia del proyecto); deben seguir siendo PNG RGB sin transparencia. |
| `templates/components/iconos.html` | Sprite SVG único por página: marca, sol, espiga e iconos de trazo (`<svg class="icono"><use href="#i-nombre"/></svg>`). Los iconos son decorativos: siempre acompañan a un texto. |
| `templates/components/franja.html`, `paisaje.html`, `Layout/base_publica.html` | Aviso de entorno de demostración y tamaño de texto; panel de identidad (composición alta para escritorio y ancha para celular); layout partido de las pantallas sin sesión. |

Reglas para las vistas que lleguen después:

- Tamaños en `rem` (el control de texto escala todo hasta 150 %); texto de 1 rem como mínimo.
- Acción principal: píldora naranja con texto y borde tinta (`.boton`); secundaria: contorno (`.boton-secundario`); destructiva: contorno ladrillo (`.boton-peligro`).
- Nada depende solo del color ni del sonido: los mensajes llevan icono y texto, y los estados una insignia con icono.
- El `id="…_error"` de un campo lo aporta el `<ul class="errorlist">` de Django; el contenedor solo lleva `role="alert"` (repetirlo duplica el id).
- Las etiquetas del login no llevan clases (una prueba compara su HTML exacto); se estilan por contexto.
- `500.html` no extiende ni incluye plantillas: debe verse aunque falle lo demás.
- Los datos públicos del pie (Departamento de Salud Municipal, Arturo Prat s/n) provienen del listado público del Servicio de Salud Ñuble; confirmarlos con el CESFAM antes de la demostración.

Verificación realizada: capturas en Chrome a 1280 px y a 390 px (incluido texto «muy grande») y auditoría con axe-core 4.10 sobre 21 pantallas (login y sus errores, recuperación, 403/404/500, inicio por cada rol, perfil, claves y gestión de usuarios): **0 violaciones de WCAG 2.1 A/AA**. Axe deja como «incompletas» tres comprobaciones de contraste (texto sobre el SVG del paisaje, sobre un pseudo-elemento o bajo la flecha de un `select`); se calcularon a mano (blanco sobre `#BC4F4F` = 4,81:1; tinta sobre trigo/blanco ≥ 15:1). Pendientes: la aceptación del equipo y la prueba de usabilidad con al menos cinco personas representativas que exige el informe (RNF-04).
