# Plan técnico — 01 / Base del proyecto

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Evidencia: [validation.md](validation.md).

Estado: implementado según la verificación registrada el 2026-11-01. Este documento separa el diseño y los doce pasos del spec original; no constituye una nueva propuesta ni una autorización adicional.

## Inspección de la base

El punto de partida del spec tenía el informe, las guías de agentes y las skills, sin código Django. La implementación creó `cesfam`, seis apps y el núcleo compartido. La reorganización documental conserva los cambios locales de `fdaza`; el spec aprobado está en `fd686ec`.

El árbol que sigue refleja las nuevas rutas documentales. Los pasos conservan la redacción del plan original, incluido el índice `00-indice.md`, que ahora remite al índice central.

## Estructura que deja este spec

```text
pwa-farmacia-cesfam/
├── CLAUDE.md  README.md  manage.py  requirements.txt  .env.example  .gitignore
├── docs/        Informe.md  estructura.md
├── specs/       README.md  00-indice.md  .spec-config.yml
│                _templates/{spec,plan,tasks,validation}.md
│                01-base-del-proyecto/{spec,plan,tasks,validation}.md
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

## Riesgos identificados

| Riesgo | Mitigación |
|---|---|
| Usar `auth.User` y un `Perfil` aparte hace costoso cambiar a un usuario propio con RUT como identificador una vez aplicadas las migraciones iniciales. | El spec 02 decide cómo se inicia sesión (RUT o nombre de usuario) antes de que existan datos reales; si se elige RUT, se resuelve con un backend de autenticación sobre `Perfil.rut` y no con `AUTH_USER_MODEL`. |
| `pip freeze > requirements.txt` desde PowerShell 5.1 escribe UTF-16 y `pip` falla al leerlo. | El archivo se crea con el editor, en UTF-8 sin BOM; un criterio de aceptación lo comprueba. |
| Django 6.1.2 instalado globalmente se usa por error en lugar del 5.2 del venv. | El `README.md` indica activar el venv; las pruebas arrancan con `python manage.py`, y el paso 1 imprime la versión. |
| Un único `settings.py` mezcla desarrollo y producción. | Todo lo que difiere sale de variables de entorno; con `DEBUG` falso se activan las cookies seguras y falta de `SECRET_KEY` detiene el arranque. |
| Un `sw.js` mal servido (tipo MIME o alcance) impide instalar la PWA. | La vista `sw_js` fija `Content-Type` y `Service-Worker-Allowed`; ambos están en los criterios. |
| Cambiar a PostgreSQL más adelante. | Solo ORM, sin SQL crudo; `/salud/` usa `connection.ensure_connection()`, no una consulta propia de SQLite. |

## Permisos e interfaz

Se conservan las reglas y criterios de [spec.md](spec.md): login mínimo, logout por POST, control de grupos mediante `RolRequeridoMixin` y acceso de superusuario. Los grupos y perfiles completos pertenecen al spec 02. Las plantillas y estáticos compartidos quedan en las rutas del árbol.

## Migraciones y reversión

La implementación creó `coreapp/migrations/0001_initial.py`; la verificación previa registró 19 migraciones aplicadas en una SQLite temporal nueva. Esta reorganización cambia documentación y skills; no exige migraciones de datos ni de esquema. La referencia documental aprobada se conserva en `fd686ec` y los antiguos puntos de entrada remiten a los documentos actuales.

## Verificación

Cada paso incluye su comprobación prevista. Los comandos realmente ejecutados, los archivos de pruebas y las limitaciones se conservan en [validation.md](validation.md). La revisión visual, instalación de la PWA desde navegador y usabilidad siguen pendientes según ese registro.
