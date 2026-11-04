# Plan — 08 / Inicio con noticias de San Nicolás

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Evidencia: [validation.md](validation.md).

## Decisiones técnicas
| Tema | Decisión | Motivo |
|---|---|---|
| Dónde vive | `coreapp` (inicio, modelos compartidos); sin app nueva | Se respetan las seis apps. |
| Fuente | Lectura de las páginas públicas del sitio municipal (`noticias.php`, `cargar_noticias.php?offset=`, `noticia.php?id=`) con la biblioteca estándar (`urllib`, `html.parser`) | No hay API ni RSS; no se suman dependencias. |
| Cuándo se lee | Solo en `actualizar_noticias`; el inicio lee la base | Igual que la regla de que un GET no procesa pendientes; cumple RNF-05 aunque el sitio esté lento o caído. |
| Persistencia | `NoticiaComuna` (migración `coreapp/0002_noticiacomuna`) | Fallback durable si cae el sitio. |
| Imágenes | Solo la dirección; el navegador la pide con `referrerpolicy="no-referrer"`; la destacada carga de inmediato y las miniaturas son `lazy` | No se guardan fotos de terceros ni de personas en el servidor o el repositorio. |
| Seguridad | Solo `https` y el dominio fijo; tamaño máximo por página; tiempo límite de 10 s | Evita imágenes o enlaces hacia otros sitios. |
| Elección | `noticias_del_inicio()`: salud vigente (180 días) o la más reciente, y cuatro más | Prioriza el trabajo de la unidad sin dejar una noticia vieja para siempre. |
| Presentación | `templates/index.html` y `static/css/noticias.css` (solo variables de `base.css`) | Mismo lenguaje visual; la prueba de colores propios cubre la hoja nueva. |

## Archivos
`coreapp/models.py`, `migrations/0002_noticiacomuna.py`, `noticias.py`, `management/commands/actualizar_noticias.py`, `views.py` (`InicioView`), `tests/test_noticias.py`, `tests/test_estaticos.py`; `templates/index.html`; `static/css/noticias.css`; `README.md`, `docs/estructura.md`, `specs/README.md`.

## Pasos
1. Modelo y migración. 2. Lector y `actualizar` con descarga inyectable. 3. Comando. 4. Selección y vista. 5. Plantilla y hoja de estilos de la opción B compacta. 6. Pruebas y revisión visual en Firefox y Chrome con noticias reales en SQLite temporal.

## Riesgos
El sitio cambia su HTML: el comando falla con mensaje claro y el inicio sigue con lo guardado. Las fotos pueden dejar de existir: el contenedor conserva su fondo y el texto sigue legible.
