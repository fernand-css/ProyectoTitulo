# SPEC 01 — Base del proyecto (estructura MVC y núcleo compartido)

> **Estado:** Implementado
> **Depende de:** ninguno
> **Fecha:** 2026-11-01
> **Objetivo:** Dejar creado y ejecutable el proyecto Django `cesfam` con sus carpetas ordenadas en Modelo–Vista–Controlador, las seis apps registradas, el núcleo compartido `coreapp`, los layouts base de la PWA y un login mínimo, sin lógica de dominio.

Documentos: [plan técnico](plan.md) · [tareas](tasks.md) · [validación](validation.md) · [índice](../README.md).

La reorganización documental del 2026-11-01 conserva el estado, alcance, acuerdos y criterios del spec original. La descripción del repositorio sin código corresponde a su punto de partida, anterior a la implementación.

## Acuerdo de ejecución

- Por instrucción del equipo del 2026-11-01, este spec se implementa en la rama actual `fdaza`.
- La creación de una rama por spec de `spec-impl` se reemplaza por un commit que guarda este spec aprobado antes de implementar.
- Por instrucción posterior del equipo, los pasos restantes se implementan de corrido, con pruebas y verificación final, sin pausas entre pasos. Los commits de implementación requieren una instrucción explícita del equipo.

## Verificación de la implementación

Completada el 2026-11-01: `check` sin problemas, `makemigrations --check --dry-run` sin cambios, 69 pruebas aprobadas y 19 migraciones aplicadas sobre una SQLite nueva. El flujo de login y logout se verificó por HTTP contra `runserver` con una cuenta temporal creada con `createsuperuser`, eliminada al terminar.

El navegador local está deshabilitado en Work: no se realizó revisión visual ni instalación de la PWA desde su interfaz. Los criterios funcionales se comprobaron mediante pruebas y HTTP real. El detalle y los límites de la verificación están en [validation.md](validation.md).

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

El árbol acordado está en [plan.md](plan.md#estructura-que-deja-este-spec); el árbol actual completo está en [docs/estructura.md](../../docs/estructura.md).

---

## Modelo de datos

El modelo aprobado y sus convenciones se conservan en [plan.md](plan.md#modelo-de-datos).

---

## Plan de implementación

Los doce pasos acordados se conservan en [plan.md](plan.md#plan-de-implementación); su seguimiento está en [tasks.md](tasks.md).

---

## Criterios de aceptación

**Arranque**

- [x] `pip install -r requirements.txt` funciona en un venv nuevo, y `requirements.txt` está en UTF-8 sin BOM.
- [x] `python manage.py check` no informa problemas.
- [x] `python manage.py makemigrations --check --dry-run` no detecta cambios pendientes.
- [x] `python manage.py migrate` aplica todo sobre una base vacía.
- [x] `python manage.py test` pasa completo.
- [x] Sin `SECRET_KEY` en el entorno, `python manage.py check` falla con un error claro.

**Navegación**

- [x] `GET /salud/` sin sesión responde 200 con `{"estado": "ok"}`.
- [x] `GET /sw.js` responde 200 con `Content-Type: application/javascript` y la cabecera `Service-Worker-Allowed: /`.
- [x] `GET /` sin sesión responde 302 a la página de login.
- [x] Con una cuenta de `createsuperuser`, entrar por el login lleva a `index.html`, que muestra el nombre del rol.
- [x] Cerrar sesión se hace por POST y vuelve al login.
- [x] Una URL inexistente muestra `404.html` con `DEBUG` falso.

**Seguridad y datos**

- [x] `git check-ignore .env db.sqlite3 media` lista las tres rutas.
- [x] `RolRequeridoMixin`: el anónimo es redirigido al login; el usuario sin el rol recibe 403; el usuario con el grupo correcto recibe 200; el superusuario recibe 200.
- [x] `validar_rut` acepta `12345678-5` y `12.345.678-5`, rechaza `12345678-9` y acepta un RUT cuyo dígito es `K`.
- [x] `registrar_accion` crea exactamente una fila de `RegistroAuditoria` y ningún campo del modelo guarda RUT ni nombre.
- [x] Los RUT de `sinteticos.py` pasan `validar_rut` y, con la misma semilla, son siempre los mismos.

**Accesibilidad y PWA**

- [x] Una prueba confirma que cada par texto/fondo de `base.css` tiene una razón de contraste de al menos 4,5:1.
- [x] `base.html` declara `lang="es-CL"`, tiene un enlace «Saltar al contenido» y un único `<main>`.
- [x] `static/manifest.webmanifest` es JSON válido y declara iconos de 192 y 512 px que existen.
- [x] `500.html` no contiene `{% extends %}`.

**Estructura y guías**

- [x] No existen en el repositorio `consumers.py`, `routing.py`, `custom_image.py`, `signals.py` ni `decorators.py`.
- [x] `grep -r "servicios.py" CLAUDE.md .claude/agents` no devuelve resultados.
- [x] `CLAUDE.md` ya no contiene «Todavía no hay código» y lista los comandos `runserver`, `test` y `migrate`.

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

Los riesgos y mitigaciones originales se conservan en [plan.md](plan.md#riesgos-identificados).

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
