# Tareas — 08 / Inicio con noticias de San Nicolás

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-04. Estado: implementación y verificación técnica completas; aceptación pendiente. Implementación autorizada por la usuaria el 2026-11-04.

- [x] **T-08-01 — Modelo y migración.** RF-08-01. `NoticiaComuna` y `coreapp/0002_noticiacomuna`; las noticias sin fecha van al final.
- [x] **T-08-02 — Lector y actualización.** RF-08-01, 08-02, 08-05. `coreapp/noticias.py`; pruebas con páginas sintéticas y revisión contra las páginas reales.
- [x] **T-08-03 — Comando `actualizar_noticias`.** RF-08-01, 08-02. Informa nuevas, conocidas y sin fecha; falla con mensaje y no borra nada.
- [x] **T-08-04 — Selección y vista.** RF-08-03. `noticias_del_inicio` e `InicioView` (solo lectura de la base).
- [x] **T-08-05 — Plantilla y estilos (opción B compacta).** RF-08-04, 08-06, 08-07. Franja baja, destacada con foto chica, lista de miniaturas, accesos y paneles; sin tarjeta ni panel de Administración.
- [x] **T-08-06 — Pruebas y documentación.** Todos. Suite completa, `check`, `makemigrations --check`, README, `docs/estructura.md` y este índice.
- [ ] **T-08-07 — Aceptación.** Revisión del equipo, axe y navegación por teclado, y autorización del uso de las fotos.

## Ejecución
| Fecha | Tarea | Resultado |
|---|---|---|
| 2026-11-04 | T-08-01 a T-08-06 | Ver [validation.md](validation.md). |
