# Estructura del proyecto

## Atención — spec 05

`turnosapp/cola.py` serializa selección y cursor global, respeta compatibilidad/FIFO, pesos configurables y prioridad por espera de 15 minutos. `atencion.py` concentra ocupación, inicio/pausa, ausencias/retorno y cierre atómico; UUID de operación ligados al actor y parámetros impiden repetir efectos. `PendienteSeleccion` sobrevive al cierre y permite recuperar el siguiente llamado sin revertir entregas. `preparar_ventanillas` prepara cuatro puestos explícitamente; `procesar_cola --continuo` recupera pendientes y cierra esperas de jornadas anteriores. No hay escrituras desde GET ni arranque implícito en migraciones.

`panel.py` proyecta solo lectura; `vistas_operacion.py` y formularios aplican roles/CSRF y mantienen UUID ante errores. Plantillas privadas de `templates/turnos/`, `cola.css` y `cola.js` presentan puesto, cola, configuración, cierre e historial. La consulta cada segundo preserva controles con foco y elimina el fragmento privado si se revoca la sesión. `/turnos/panel/` admite Técnico/Q.F.; `/turnos/gestion/`, Q.F. Las entregas reutilizan el servicio del 03 y su contexto firmado en `recetasapp/confirmacion.py`.

Migraciones: recetas 0003 y turnos 0002; conservan datos históricos, sin fabricar vínculos de entrega. Verificación: 411 pruebas Django, siete JavaScript y `tools/verificar_spec_05_http.py` con 670 pacientes sintéticos, cuatro puestos, tres escenarios concurrentes y recuperación en proceso nuevo. Navegador, axe y aceptación pendientes; la pantalla pública y voz quedan para 06. No se migró la base local durante esta implementación.

## Turnos — spec 04

`turnosapp` incorpora `ContadorTurnosDiario`, `Turno` y `TurnoReceta`, con migración `0001_initial` dependiente de recetas 0002. Unicidad diaria del número, activo por paciente/fecha y UUID de operación; relaciones protegidas. `services.emitir_turno` reserva el correlativo con UPDATE condicional, reintenta colisiones y confirma vínculos/auditoría en la misma transacción. Reutiliza `evaluar_elegibilidad`; no consume ni reserva entregas. Recuperar conserva selección y categoría originales.

`forms.py` valida RUT y UUID; las vistas `/turnos/totem/`, `/turnos/totem/finalizar/` y `/turnos/totem/continuar/` aplican contexto temporal, CSRF y `no-store`. El contexto guarda UUID, vencimiento, huella HMAC y señal de resultado, sin RUT en claro ni ficha. Solo las claves del tótem se limpian, preservando una sesión del personal. Las entradas se marcan sensibles para trazas y los fallos públicos no muestran excepciones.

`templates/turnos/` contiene entrada, resultado, aviso de tiempo y comprobante. `static/js/totem.js` controla teclado, limpieza, ampliación e impresión sin almacenamiento local. `static/css/turnos.css` reutiliza la paleta y prepara un comprobante de 72 mm útiles en rollo nominal de 80 mm; la altura y papel los define el controlador, sin altura fija en CSS. Solo se imprime el fragmento mínimo, sin tipo de atención ni identidad. El cierre del diálogo no confirma papel. No hay endpoint público para enumerar turnos o recetas.

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
│   │   ├── Layout/           base.html           base_publica.html
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

`venv/`, `.env`, `db.sqlite3` (base antigua), `media/` y `staticfiles/` se generan localmente y no se versionan.

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

## Spec 03 — Padrón y recetas

El árbol inicial del 01 se amplía en `recetasapp` con estos componentes:

| Archivo / carpeta | Responsabilidad |
|---|---|
| `models.py` | Paciente, Receta, EntregaReceta, ImportacionPadron y ResultadoFilaImportacion; restricciones y protección de historial. |
| `migrations/0001_initial.py`, `0002_resultadofilaimportacion_pacientes_actualizados_and_more.py` | Esquema y conteos de objetos por fila para reconstruir bitácoras. |
| `services.py` | Autorización, calendario, elegibilidad, creación/renovación, confirmación idempotente y aplicación atómica de fila; auditoría y reintentos por colisiones SQLite. |
| `importacion.py` | Contrato de doce columnas, CSV/XLSX limitado, prevalidación de contradicciones, procesamiento parcial y bitácoras; generación de plantillas y archivos sintéticos. |
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

Rediseño de plantillas y estilos a partir del escudo comunal: campo de gules, tres espigas de oro y un sol naciente. No cambia vistas, URLs, formularios ni servicios; solo la presentación. El login y las pantallas sin sesión comparten un panel de paisaje (sol saliendo sobre surcos que convergen en el horizonte, con las tres espigas); las pantallas con sesión usan un menú lateral (tarjeta clara con cabecera ladrillo; barra superior y dock inferior en celular), migas de pan, azulejos de acceso y paneles planos.

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

El menú reemplaza «Padrón y recetas» por dos entradas: **Padrón** (pacientes, ficha, importaciones y plantillas) y **Recetas** (`recetasapp:recetas`, en `/recetas/`; detalle, creación, renovación y confirmación de entrega). Cada una marca «página actual» por sí sola; `test_cada_pantalla_marca_una_sola_entrada_como_pagina_actual` recorre las pantallas. «Crear receta» está en Recetas. No hay una entrada «Resumen»: el resumen es el tablero con que abre Recetas.

| Archivo | Responsabilidad |
|---|---|
| `recetasapp/tablero.py` | Arma el tablero (solo lectura): cifras, anillo, línea, barras, ranking y última carga. Valida el periodo (7, 30 o 90 días; cualquier otro valor vuelve a 30). |
| `recetasapp/graficos.py` | Geometría pura de los gráficos: porcentajes que suman 100, arcos del anillo sobre un círculo de largo 100, curva con tangentes horizontales (no se pasa del rango), techo redondo del eje y barras. Todo número hacia un atributo SVG sale como texto con punto decimal: con es-cl, Django escribiría coma y el atributo quedaría inválido. |
| `templates/recetas/_tablero.html`, `static/css/tablero.css` | Dibujo y estilos. Sin librerías ni CDN. `tablero.css` no declara colores (una prueba lo exige, igual que `recetas.css`). |

- **Tablero:** cuatro cifras (vigentes, por vencer, pacientes sin receta vigente y entregas del mes, cada una con su enlace), entregas por día (línea con selector de periodo y tabla de datos desplegable), situación de las recetas (anillo con leyenda en texto que enlaza a la lista filtrada), vencimientos por mes (seis barras), «Vencen primero» (ranking de seis, con aviso si no hay) y la tarjeta oscura de la última carga. «Por vencer» es parte de las vigentes, por eso no es un arco del anillo. Sin datos, cada tarjeta explica qué falta en vez de dibujar un gráfico vacío.
- **Movimiento:** una sola secuencia al cargar (el anillo se traza, la línea se dibuja, las barras suben, escalonados) y el latido de «Por vencer». Todas las animaciones parten de su estado final y `base.css` las apaga con «reducir movimiento»; una prueba lo comprueba.
- **Accesibilidad de los gráficos:** el SVG lleva título y descripción con el total y el máximo; la leyenda, las barras y la tabla de datos repiten las cifras en texto, así que nada depende solo del color. El mes actual se distingue por relleno y subrayado. Hay un contraste de 3:1 comprobado para los colores de los gráficos; los arcos naranjas van delimitados por tinta.
- **Lista** (debajo del tablero, en `#listado`): pestañas con cantidad por situación, hechas con botones que envían el formulario para conservar la búsqueda. El botón «Buscar» va primero en el documento y lleva la situación actual, de modo que Enter en el campo no la pierde. Buscar o paginar vuelve a `#listado` y no al comienzo. El RUT o nombre viaja por POST; solo la situación y el periodo pueden ir en la URL.
- **Padrón:** filtro «Sin receta vigente», con el mismo patrón de botones.
- **Estáticos versionados:** `coreapp/storage.py` agrega `?v=<fecha de modificación>` a las URL de `.css` y `.js` (no a fuentes ni iconos). El servidor de desarrollo no envía `Cache-Control` y el navegador podía seguir con una hoja vieja (botones sin estilo tras un cambio). En producción, el equivalente completo es `ManifestStaticFilesStorage` con `collectstatic`.

## Menú principal: columna lateral y dock del celular

Reemplaza la cabecera ladrillo con ocho enlaces en fila, que ya no cabían (el botón «Cerrar sesión» bajaba a una segunda fila) y que seguirían creciendo con cada spec. Una sola lista alimenta dos presentaciones: en computador (más de 70 rem), una tarjeta lateral con grupos y una zona de cuenta, que se pliega a una columna angosta; en celular y tableta (hasta 70 rem), una barra superior con la marca y un dock flotante abajo con los cuatro destinos de trabajo y «Más», que abre una hoja con el resto y la cuenta. Es solo presentación: no cambia vistas, URLs, permisos ni servicios, y cada vista sigue validando el rol en el servidor.

| Archivo | Responsabilidad |
|---|---|
| `coreapp/navegacion.py` | La lista del menú (`ENTRADAS`, más `PERFIL`): etiqueta, ruta, ícono, grupo, perfiles que la ven, regla de «página actual», nombre corto y si va en el dock. `armar_menu()` la resuelve para un perfil y una página. Para sumar la sección de una spec basta una `Entrada` nueva. |
| `coreapp/context_processors.py` | `menu_principal` entrega el menú ya resuelto (y nombre e iniciales de la persona) a toda plantilla; `rol_actual` no cambia. |
| `templates/components/navbar.html`, `_menu_enlace.html`, `barra_superior.html`, `dock.html` | Columna lateral, opción compartida, marca del celular y dock con la hoja «Más» (un `<details>`). `Layout/base.html` los ordena; `base_publica.html` y `base_sala.html` siguen llevando la franja superior y ninguna navegación. |
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
| `views.py`, `urls.py`, `base_sala.html`, `sala.html` | `/turnos/sala/`: GET/HEAD, `no-store`, sin cookies. Tarjetas, seis recientes (20 en estado), hasta 40 números en espera/restantes y hora del servidor. Sin navegación privada ni estimación de espera. |
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

## Inicio con noticias — spec 08

| Archivo | Responsabilidad |
|---|---|
| `coreapp/models.py`, `migrations/0002_noticiacomuna.py` | `NoticiaComuna`: texto, fecha, resumen, enlaces y marca de salud; sin imágenes. Las noticias sin fecha van al final. |
| `coreapp/noticias.py` | Lector del sitio municipal (`urllib` + `html.parser`), `actualizar()` con descarga inyectable, `noticias_del_inicio()` (salud vigente a 180 días o la más reciente, más cuatro) y `ultima_actualizacion()`. Solo acepta direcciones `https` del sitio. |
| `coreapp/management/commands/actualizar_noticias.py` | Copia las noticias; falla con mensaje y conserva lo guardado si el sitio no responde. |
| `coreapp/views.py` (`InicioView`) | Entrega destacada y lista leyendo solo la base; nunca sale a Internet. |
| `templates/index.html`, `static/css/noticias.css` | Opción «B compacta»: franja de saludo baja, noticia destacada con foto chica, lista con miniaturas, accesos y paneles por perfil. Sin tarjeta ni panel de Administración (sigue en el menú). |
| `coreapp/tests/test_noticias.py` | 24 pruebas con páginas sintéticas. |
