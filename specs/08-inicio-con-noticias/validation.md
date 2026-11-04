# Validación — 08 / Inicio con noticias de San Nicolás

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-04.

## Verificado
| Qué | Cómo | Resultado |
|---|---|---|
| Lector, actualización, selección, vista y comando | `coreapp/tests/test_noticias.py` (24 pruebas, páginas sintéticas, sin red) | Aprobado |
| Hoja nueva sin colores propios | `test_libreta_del_padron_usa_solo_colores_de_la_paleta_y_variables_definidas` incluye `noticias.css` | Aprobado |
| Lector contra el sitio real | Páginas reales de `noticias.php`, `cargar_noticias.php` y `noticia.php?id=18` guardadas aparte: 8 + 8 tarjetas, fecha y resumen correctos, dos noticias de salud detectadas | Aprobado |
| Carga real a una SQLite temporal | `actualizar()` trajo 24 noticias; en una de dos corridas 7 quedaron sin fecha por respuestas fallidas del sitio (se añadió pausa de 0,5 s y se reintentan) | Aprobado con la pausa |
| Regresión | `manage.py test --parallel 4`: 604 pruebas; `check` y `makemigrations --check` sin cambios | Aprobado |
| Revisión visual | Firefox sin interfaz a 390, 1100 y 1440 px y Chrome a 1440 px, con noticias reales, perfiles superusuario y Técnico | Sin desbordes; la captura de Chrome a 390 px recorta por el ancho mínimo de su modo sin interfaz y no refleja el diseño |

## Límites (no declarar cumplido)
- No se ejecutó axe-core ni se probó el teclado a mano en esta spec.
- Las miniaturas con `loading="lazy"` no se ven en una captura instantánea; se comprobó que el navegador carga imágenes remotas con `referrerpolicy="no-referrer"`.
- No se migró la base PostgreSQL del proyecto: para verlo en ella hay que ejecutar `python manage.py migrate` y luego `python manage.py actualizar_noticias`.
- Falta la aceptación del equipo y la autorización del uso de las fotos de la Municipalidad.
- El lector depende del HTML actual del sitio municipal.
