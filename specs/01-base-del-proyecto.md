# SPEC 01 — Base del proyecto (estructura MVC y núcleo compartido)

> **Estado:** Aprobado
> **Depende de:** ninguno
> **Fecha:** 2026-11-01
> **Objetivo:** Dejar creado y ejecutable el proyecto Django `cesfam` con sus carpetas ordenadas en Modelo–Vista–Controlador, las seis apps registradas, el núcleo compartido `coreapp`, los layouts base de la PWA y un login mínimo, sin lógica de dominio.

## Acuerdo de ejecución

- Por instrucción del equipo del 2026-11-01, este spec se implementa en la rama actual `fdaza`.
- La creación de una rama por spec de `spec-impl` se reemplaza por un commit que guarda este spec aprobado antes de implementar.
- Se mantiene la revisión del diff al terminar cada paso del plan. Los commits de implementación requieren una instrucción explícita del equipo.

---

## Por qué existe este spec

El repositorio no tiene código: solo `docs/Informe.md`, `CLAUDE.md`, los agentes de `.claude/agents/` y las skills. Todos los specs posteriores (autenticación, turnos, recetas, entregas, indicadores) cuelgan de una estructura común. Si cada uno la inventa, hay que reordenar después. Este spec fija esa estructura una sola vez.

En Django el patrón se llama MTV. Aquí se corresponde así con MVC, y los specs siguientes lo respetan:

| MVC | En el proyecto | Dónde |
|---|---|---|
| Modelo | Tablas y reglas de la base | `<app>/models.py` |
| Controlador | Vistas (clases) y lógica de negocio | `<app>/views.py` y `<app>/services.py` |
| Vista | Lo que ve el usuario | `templates/` y `static/` |

---

## Alcance

**Dentro:**

- Proyecto `cesfam/` con un único `settings.py`: `es-cl`, `America/Santiago`, SQLite, secretos desde `.env` con `python-dotenv`, `asgi.py` y `wsgi.py` tal como los genera Django.
- Seis apps registradas: `coreapp`, `usuariosapp`, `recetasapp`, `turnosapp`, `entregasapp`, `indicadoresapp`. Solo `coreapp` y `usuariosapp` llevan contenido; las otras cuatro quedan vacías, con su `urls.py` montado.
- `coreapp` con contenido real y probado: `roles.py`, `mixins.py`, `models.py` (`ModeloAuditado` y `RegistroAuditoria`), `auditoria.py`, `context_processors.py`, `templatetags/core_tags.py`, `views.py` (inicio, `/sw.js`, `/salud/`) y `utils/` (`rut.py`, `sinteticos.py`).
- Login mínimo de Django en `usuariosapp` (entrar y salir), para poder recorrer el esqueleto con una cuenta de `createsuperuser`.
- Plantillas base: `components/Layout/base.html`, `components/Layout/base_publica.html`, `navbar.html`, `footer.html`, `paginator.html`, `mensajes.html`, `index.html`, `403.html`, `404.html`, `500.html`, `pwa/sw.js` y `registration/login.html`.
- PWA instalable sin caché sin conexión: `static/manifest.webmanifest`, iconos de 192 y 512 px, y un `sw.js` mínimo que solo se registra.
- `static/css/base.css` con colores y tipografía de contraste AA, y `static/js/alpine.min.js` copiado en local.
- Documentación: `README.md`, `docs/estructura.md`, `specs/00-indice.md` y `specs/.spec-config.yml`.
- Actualizar `CLAUDE.md` y los agentes `django-architect` y `django-builder` para que usen los nombres de este árbol.

**Fuera de alcance (para otros specs):**

- Autenticación completa (HU-01 a 03): restablecer contraseña, perfil, `Perfil`, `signals.py`, grupos por rol y `crear_usuarios_demo` → spec 02.
- Modelos de dominio: pacientes, recetas, turnos, ventanillas, domicilios, entregas.
- WebSocket: `consumers.py`, `routing.py`, `channels`, `daphne` → spec 06.
- Caché y modo sin conexión del service worker, `offline.js`, `api.py` → spec 11.
- Notificaciones y `notificaciones.py` → spec 12.
- `custom_image.py`: llega con los domicilios (HU-12).
- Las 20 plantillas de `pages/` y las 5 de recuperación de contraseña de `registration/`: cada una llega con el spec de su HU.
- `totem.css`, `sala.css`, `aviso.mp3`, `static/js/turnos/` y `static/js/entregas/`.
- `generar_padron_sintetico`, `importacion.py`, `services.py` de turnos y entregas, `consultas.py` de indicadores.
- Despliegue, HTTPS real, servir estáticos en producción, Docker, CI y PostgreSQL.

### Estructura que deja este spec

```text
pwa-farmacia-cesfam/
├── CLAUDE.md  README.md  manage.py  requirements.txt  .env.example  .gitignore
├── docs/        Informe.md  estructura.md
├── specs/       00-indice.md  01-base-del-proyecto.md  .spec-config.yml
├── cesfam/      settings.py  urls.py  asgi.py  wsgi.py
├── coreapp/     models.py  auditoria.py  roles.py  mixins.py  context_processors.py
│                views.py  urls.py  templatetags/core_tags.py
│                utils/{rut.py, sinteticos.py}  tests/
├── usuariosapp/ urls.py            (solo login y logout)
├── recetasapp/  turnosapp/  entregasapp/  indicadoresapp/   (apps vacías con urls.py)
├── templates/   index.html  403.html  404.html  500.html
│                pwa/sw.js  registration/login.html
│                components/{Layout/base.html, Layout/base_publica.html,
│                            navbar.html, footer.html, paginator.html, mensajes.html}
└── static/      manifest.webmanifest  css/base.css  js/alpine.min.js  icons/icon-{192,512}.png
```

---

## Modelo de datos

Este spec crea solo dos modelos, ambos en `coreapp/models.py`, con la migración `coreapp/migrations/0001_initial.py`.

```python
class ModeloAuditado(models.Model):          # abstracto: lo heredan los modelos de dominio
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    modificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="+")
    class Meta:
        abstract = True

class RegistroAuditoria(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                on_delete=models.SET_NULL, related_name="+")
    accion = models.CharField(max_length=60)       # p. ej. "turno.llamado"
    objeto_tipo = models.CharField(max_length=100) # p. ej. "turnosapp.Turno"
    objeto_id = models.CharField(max_length=40)    # clave primaria como texto
    creado_en = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [models.Index(fields=["objeto_tipo", "objeto_id"], name="audit_objeto_idx"),
                   models.Index(fields=["creado_en"], name="audit_fecha_idx")]
        ordering = ["-creado_en"]
```

Convenciones:

- `RegistroAuditoria` **nunca** guarda RUT, nombre ni ningún dato del paciente: solo quién, qué acción, sobre qué objeto y cuándo.
- Los roles son nombres de grupos de Django, definidos en `coreapp/roles.py` como constantes: `JEFA = "Jefa de Farmacia"`, `TECNICO = "Técnico en Farmacia"`, `ENCARGADO = "Encargado de entrega"`. `TOTEM` existe como constante, pero no es un grupo: el tótem es público y no inicia sesión. Los grupos se crean en el spec 02.
- Este spec usa el `auth.User` de Django, sin `AUTH_USER_MODEL` propio.
- El RUT se normaliza como `12345678-5` (sin puntos, `K` mayúscula) y se valida con módulo 11 en `coreapp/utils/rut.py`: `validar_rut`, `normalizar_rut`, `formatear_rut`.
- Prefijos de URL: `/` → `coreapp`; `/usuarios/` → `usuariosapp`; `/recetas/`, `/turnos/`, `/entregas/`, `/indicadores/` → su app.
- Los datos sintéticos de `utils/sinteticos.py` reciben una semilla (`random.Random`) para que las pruebas sean repetibles.

---

## Plan de implementación

Cada paso deja el sistema ejecutable y se puede subir a git por separado.

1. **Entorno y archivos raíz.** Crear `.gitignore` (`venv/`, `.env`, `db.sqlite3`, `media/`, `staticfiles/`, `__pycache__/`), `requirements.txt` en UTF-8 sin BOM (`Django>=5.2,<5.3`, `python-dotenv`) y `.env.example` (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `EMAIL_*`, `SMS_*`). Crear el venv e instalar. Prueba: `python -c "import django; print(django.get_version())"` imprime `5.2.x`.
2. **Proyecto y settings.** `django-admin startproject cesfam .` y editar `cesfam/settings.py`: lee `.env`, `SECRET_KEY` obligatoria, `DEBUG` falso por defecto, `ALLOWED_HOSTS` desde el entorno, idioma, zona horaria, `TEMPLATES["DIRS"]`, `STATICFILES_DIRS`, `MEDIA_ROOT`, correo (consola con `DEBUG`, SMTP desde `EMAIL_*` sin él) y cookies seguras cuando `DEBUG` es falso. Prueba: `python manage.py check` y `migrate` sin errores.
3. **Seis apps.** `startapp` de cada una, con `tests/` como paquete en lugar de `tests.py`. Registrarlas en `INSTALLED_APPS`. En las cuatro de dominio, `urls.py` con `app_name` y `urlpatterns = []`. Montar los prefijos en `cesfam/urls.py`. Prueba: `check` sin errores.
4. **RUT, roles y datos sintéticos.** `coreapp/roles.py`, `coreapp/utils/rut.py`, `coreapp/utils/sinteticos.py` y `coreapp/tests/test_rut.py`. Prueba: `python manage.py test coreapp.tests.test_rut`.
5. **Modelos de auditoría.** `ModeloAuditado`, `RegistroAuditoria`, `coreapp/auditoria.py` (`registrar_accion(usuario, accion, objeto)`), migración `0001` y `test_auditoria.py`. Prueba: `makemigrations --check --dry-run` sin cambios pendientes y las pruebas en verde.
6. **Control de acceso por rol.** `coreapp/mixins.py` con `tiene_rol(usuario, *roles)` y `RolRequeridoMixin` (atributo `roles_permitidos`): anónimo → redirige al login; con sesión pero sin el rol → 403; `is_superuser` pasa siempre. Prueba: `test_mixins.py` con una vista de prueba.
7. **Contexto y filtros de plantilla.** `context_processors.py` (entrega `rol` y `nombre_rol`) y `templatetags/core_tags.py` (`|rut` y `|minutos`), registrados en `TEMPLATES`. Prueba: `test_plantillas.py`.
8. **Estáticos y PWA.** `static/css/base.css` (variables de color y tamaños con contraste AA), `static/js/alpine.min.js` (versión fija, anotada en el `README.md`), `static/manifest.webmanifest` e iconos provisorios de 192 y 512 px. Prueba: una prueba calcula la razón de contraste de cada par texto/fondo declarado en `base.css`.
9. **Plantillas base.** `base.html` (`lang="es-CL"`, enlace «Saltar al contenido», `<main>`, manifest, registro del service worker), `base_publica.html`, `navbar.html` (menú según rol), `footer.html`, `paginator.html`, `mensajes.html` (`role="alert"`), `403.html`, `404.html`, `500.html` (sin `{% extends %}`) e `index.html`. Prueba: renderizar cada una sin errores en `test_plantillas.py`.
10. **Vistas del núcleo.** `coreapp/views.py`: `inicio` (requiere sesión), `sw_js` (sirve `pwa/sw.js` con `Content-Type: application/javascript` y `Service-Worker-Allowed: /`) y `salud` (JSON `{"estado": "ok"}` tras comprobar la conexión a la base). Rutas en `coreapp/urls.py`, `handler403/404/500` en `cesfam/urls.py` y `templates/pwa/sw.js` mínimo. Prueba: `test_vistas.py`.
11. **Login mínimo.** `usuariosapp/urls.py` con `LoginView` y `LogoutView` (POST), `registration/login.html` accesible (etiquetas visibles, errores con `role="alert"`) y `LOGIN_URL`, `LOGIN_REDIRECT_URL` y `LOGOUT_REDIRECT_URL` en settings. Prueba manual: `createsuperuser`, `runserver`, entrar y ver `index.html`; y `test_login.py`.
12. **Documentación y guías.** `README.md` (instalación, variables de entorno, cómo correr y probar, versión de Alpine), `docs/estructura.md` (el árbol final y qué spec crea cada archivo), `specs/00-indice.md` y `specs/.spec-config.yml` si falta. Reemplazar en `CLAUDE.md` «Todavía no hay código» por comandos y arquitectura reales, y alinear `django-architect` y `django-builder` con: apps `*app`, `services.py`, un solo `settings.py`, vistas de clase con mixins y `coreapp`.

---

## Criterios de aceptación

**Arranque**

- [ ] `pip install -r requirements.txt` funciona en un venv nuevo, y `requirements.txt` está en UTF-8 sin BOM.
- [ ] `python manage.py check` no informa problemas.
- [ ] `python manage.py makemigrations --check --dry-run` no detecta cambios pendientes.
- [ ] `python manage.py migrate` aplica todo sobre una base vacía.
- [ ] `python manage.py test` pasa completo.
- [ ] Sin `SECRET_KEY` en el entorno, `python manage.py check` falla con un error claro.

**Navegación**

- [ ] `GET /salud/` sin sesión responde 200 con `{"estado": "ok"}`.
- [ ] `GET /sw.js` responde 200 con `Content-Type: application/javascript` y la cabecera `Service-Worker-Allowed: /`.
- [ ] `GET /` sin sesión responde 302 a la página de login.
- [ ] Con una cuenta de `createsuperuser`, entrar por el login lleva a `index.html`, que muestra el nombre del rol.
- [ ] Cerrar sesión se hace por POST y vuelve al login.
- [ ] Una URL inexistente muestra `404.html` con `DEBUG` falso.

**Seguridad y datos**

- [ ] `git check-ignore .env db.sqlite3 media` lista las tres rutas.
- [ ] `RolRequeridoMixin`: el anónimo es redirigido al login; el usuario sin el rol recibe 403; el usuario con el grupo correcto recibe 200; el superusuario recibe 200.
- [ ] `validar_rut` acepta `12345678-5` y `12.345.678-5`, rechaza `12345678-9` y acepta un RUT cuyo dígito es `K`.
- [ ] `registrar_accion` crea exactamente una fila de `RegistroAuditoria` y ningún campo del modelo guarda RUT ni nombre.
- [ ] Los RUT de `sinteticos.py` pasan `validar_rut` y, con la misma semilla, son siempre los mismos.

**Accesibilidad y PWA**

- [ ] Una prueba confirma que cada par texto/fondo de `base.css` tiene una razón de contraste de al menos 4,5:1.
- [ ] `base.html` declara `lang="es-CL"`, tiene un enlace «Saltar al contenido» y un único `<main>`.
- [ ] `static/manifest.webmanifest` es JSON válido y declara iconos de 192 y 512 px que existen.
- [ ] `500.html` no contiene `{% extends %}`.

**Estructura y guías**

- [ ] No existen en el repositorio `consumers.py`, `routing.py`, `custom_image.py`, `signals.py` ni `decorators.py`.
- [ ] `grep -r "servicios.py" CLAUDE.md .claude/agents` no devuelve resultados.
- [ ] `CLAUDE.md` ya no contiene «Todavía no hay código» y lista los comandos `runserver`, `test` y `migrate`.

---

## Decisiones tomadas y descartadas

- **Sí:** el árbol del equipo como estructura final, con los nombres `*app` y `services.py`. **No:** los nombres `cuentas`, `recetas`, `turnos`, `reparto`, `indicadores` y `servicios.py` que usaban los agentes; se cambian los agentes, no el árbol.
- **Sí:** Django 5.2 LTS, con soporte de seguridad hasta abril de 2028, y un venv propio. **No:** Django 6.1.x, que es la que hay instalada globalmente pero no es LTS.
- **Sí:** vistas de clase con `RolRequeridoMixin` en `coreapp/mixins.py`. **No:** el `decorators.py` del árbol ni la mezcla de ambos. Un solo estilo evita decidir en cada spec.
- **Sí:** un único `settings.py` con secretos en `.env`; lo que cambia por entorno sale de variables. **No:** separar en `base/dev/prod`, que el árbol descarta.
- **Sí:** `python-dotenv`. **No:** `django-environ` ni un lector propio.
- **Sí:** login mínimo con las vistas de Django en este spec, para que el esqueleto se pueda recorrer. **No:** una portada pública sin acceso, ni dejar `/` redirigiendo a un login que da 404.
- **Sí:** PWA instalable con un service worker que solo se registra. **No:** cachear el shell ahora; eso exige una estrategia de versiones de caché que pertenece al spec 11.
- **Sí:** `RegistroAuditoria` con `objeto_tipo` y `objeto_id` de texto. **No:** `GenericForeignKey`, porque la fila queda huérfana si se borra el objeto.
- **Sí:** solo ASGI estándar; `channels` y `consumers.py` se difieren al spec 06, que elige la librería y la capa de canales. **No:** instalar Channels ahora ni crear archivos vacíos.
- **Sí:** crear desde cero `custom_image.py` y `signals.py` cuando su spec los necesite. **No:** depender del código del taller, que no está en este repositorio.
- **Sí:** solo las plantillas base, los errores y el login. **No:** crear las ~30 plantillas de `pages/` como marcadores sin vista ni prueba.
- **Decisión de diseño de este spec (revisar):** `is_superuser` pasa el control de roles, porque los grupos no existen hasta el spec 02 y, sin eso, nadie podría entrar con la cuenta de `createsuperuser`.
- **Decisión de diseño de este spec (revisar):** los prefijos de URL son `/usuarios/`, `/recetas/`, `/turnos/`, `/entregas/` e `/indicadores/`; el informe no los define.
- **Decisión de diseño de este spec (revisar):** Alpine.js 3.14.9, la misma versión de la implementación anterior del equipo, copiada de su distribución oficial.

---

## Riesgos identificados

| Riesgo | Mitigación |
|---|---|
| Usar `auth.User` y un `Perfil` aparte hace costoso cambiar a un usuario propio con RUT como identificador una vez aplicadas las migraciones iniciales. | El spec 02 decide cómo se inicia sesión (RUT o nombre de usuario) antes de que existan datos reales; si se elige RUT, se resuelve con un backend de autenticación sobre `Perfil.rut` y no con `AUTH_USER_MODEL`. |
| `pip freeze > requirements.txt` desde PowerShell 5.1 escribe UTF-16 y `pip` falla al leerlo. | El archivo se crea con el editor, en UTF-8 sin BOM; un criterio de aceptación lo comprueba. |
| Django 6.1.2 instalado globalmente se usa por error en lugar del 5.2 del venv. | El `README.md` indica activar el venv; las pruebas arrancan con `python manage.py`, y el paso 1 imprime la versión. |
| Un único `settings.py` mezcla desarrollo y producción. | Todo lo que difiere sale de variables de entorno; con `DEBUG` falso se activan las cookies seguras y falta de `SECRET_KEY` detiene el arranque. |
| Un `sw.js` mal servido (tipo MIME o alcance) impide instalar la PWA. | La vista `sw_js` fija `Content-Type` y `Service-Worker-Allowed`; ambos están en los criterios. |
| Cambiar a PostgreSQL más adelante. | Solo ORM, sin SQL crudo; `/salud/` usa `connection.ensure_connection()`, no una consulta propia de SQLite. |

---

## Lo que **no** está en este spec

- Autenticación completa, perfiles y grupos por rol (spec 02).
- Cualquier modelo de pacientes, recetas, turnos, ventanillas, domicilios o entregas.
- WebSocket y tiempo real (spec 06).
- Modo sin conexión y caché del service worker (spec 11).
- Notificaciones (spec 12).
- Las plantillas de `pages/` y las de recuperación de contraseña.
- Despliegue, HTTPS real, Docker, CI y PostgreSQL.

Cada uno, cuando llegue, va en su propio spec.
