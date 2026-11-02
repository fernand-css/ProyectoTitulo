# Validación — 01 / Base del proyecto

Fecha: 2026-11-01. Rama: `fdaza`. El documento aprobado quedó guardado en el commit `fd686ec`; los cambios de implementación se dejan para revisión, sin commit.

Entorno usado: Windows, Python 3.13.15, Django 5.2.18, SQLite y `python-dotenv` en el venv del proyecto.

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).

Este registro se trasladó desde `docs/verificacion-spec-01.md` el 2026-11-01. Los resultados siguientes corresponden a la verificación original; no se volvieron a ejecutar pruebas de Django durante la reorganización documental.

## Comprobaciones ejecutadas

| Comprobación | Resultado |
|---|---|
| Instalación desde `requirements.txt` en el venv nuevo | Correcta; `pip check` sin dependencias incompatibles. |
| Codificación de `requirements.txt` | UTF-8 sin BOM, comprobado también en la suite. |
| `python manage.py check` | Sin problemas. |
| `python manage.py makemigrations --check --dry-run` | Sin cambios pendientes. |
| `python manage.py test --noinput` | **69 pruebas aprobadas**. |
| `migrate` con SQLite temporal nueva | 19 migraciones aplicadas; tabla de auditoría disponible, sin migraciones pendientes. La base temporal se retiró. |
| Falta de `SECRET_KEY` | `manage.py check` falla con un mensaje claro. También se prueban clave vacía y de solo espacios. |
| Configuración de desarrollo y valores seguros por defecto | Correo a consola en desarrollo, SMTP configurado por entorno fuera de él, cookies seguras y `DEBUG=False` por defecto. |
| ASGI y WSGI | Coinciden con las plantillas originales de Django 5.2; ambos callables arrancan. |
| `git check-ignore .env db.sqlite3 media` | Devuelve las tres rutas. |
| Archivos fuera de alcance y nombres anteriores en las guías | Ninguno encontrado en el código del proyecto; guías alineadas. |
| Sintaxis JavaScript | `node --check` pasa para Alpine, `pwa.js` y el service worker. Node solo se usó para esta comprobación; no es una dependencia del proyecto. |

## Cobertura de la suite

| Archivo | Casos principales |
|---|---|
| `coreapp/tests/test_rut.py` | Formatos, DV incorrecto, K, cero, entradas mal formadas, mensajes sin datos de entrada y 670 RUT únicos y reproducibles. |
| `coreapp/tests/test_auditoria.py` | Una fila por acción, campos sin datos del objeto, supervivencia de la referencia al borrar objeto y actor, acciones sin usuario, longitudes y modelo abstracto. |
| `coreapp/tests/test_mixins.py` | Anónimo, cuenta sin grupo, grupo incorrecto, grupo correcto, superusuario y denegación por defecto. |
| `coreapp/tests/test_configuracion.py` | Claves obligatorias, entorno seguro, hosts, correo, booleanos y codificación de dependencias. |
| `coreapp/tests/test_plantillas.py` | Roles y prioridad, filtros, todas las plantillas, idioma, salto al contenido, un único main, IDs únicos, mensajes escapados, paginación y error 500 independiente. |
| `coreapp/tests/test_estaticos.py` | Contraste de cada pareja texto/fondo ≥ 4,5:1, manifest, dimensiones y CRC de PNG, Alpine fijo con licencia y ausencia de caché en el worker. |
| `coreapp/tests/test_vistas.py` | Salud y fallo de base, MIME y alcance del worker, sesión, rol y errores 403/404/500 sin detalles de excepciones. |
| `usuariosapp/tests/test_login.py` | Login válido e inválido, cuenta inactiva, etiquetas, errores asociados, logout POST, CSRF, conservación de next interno y rechazo de destinos externos. |

## Prueba contra el servidor real

Se ejecutaron `createsuperuser --noinput` con una cuenta sintética temporal y `runserver 127.0.0.1:8000 --noreload`. Un cliente HTTP con cookies comprobó:

1. El inicio anónimo redirige al formulario de login.
2. El login con CSRF lleva a `/` y muestra el perfil **Administración** de la cuenta creada con `createsuperuser`.
3. Salud, service worker, manifest, iconos, CSS, Alpine y el script de registro responden correctamente.
4. El logout por POST con CSRF vuelve al login y el inicio vuelve a requerir sesión.

La cuenta sintética se eliminó y el servidor de prueba se detuvo. No se deja una cuenta con contraseña predefinida en la base local.

## Límite de esta verificación

La herramienta de navegador informó que el uso del navegador local está deshabilitado en la configuración de Work. No se hizo revisión visual ni instalación de la PWA desde un navegador. Se comprobaron sus archivos y respuestas HTTP, pero no la aparición de la opción de instalación.

Las pruebas de contraste y estructura no equivalen a una auditoría completa WCAG con navegador y usuarios. La evaluación de usabilidad con cinco usuarios del RNF-04 sigue siendo una actividad de validación del proyecto; no se da por realizada en este spec.

Los modelos de dominio, concurrencia de turnos, WebSocket, funcionamiento sin conexión, notificaciones y despliegue quedan en sus specs correspondientes.


## Aceptación funcional

No consta una confirmación posterior del usuario en la evidencia original. Estado: pendiente de registro; no se deduce de la suite aprobada.
