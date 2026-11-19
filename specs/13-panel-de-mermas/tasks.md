# Tareas — 13 / Panel de mermas

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Validación: [validation.md](validation.md).
Estado: implementadas técnicamente el 2026-11-17 en `fdaza` (commit `aa08f74`) e incorporadas a `crojas-base` el 2026-11-18. Aceptación de la usuaria pendiente.

- [x] T-13-01 — Rol Director del CESFAM.
  - RF: RF-13-08.
  - Depende de: ninguna.
  - Archivos: `coreapp/roles.py`, `usuariosapp/services.py` (`CUENTAS_DEMO`), `usuariosapp/management/commands/crear_roles.py`.
  - Hecho: `crear_roles` crea cuatro grupos; `demo_director`; la Q.F. no lo ve en «Usuarios» (`cuentas_gestionables` ya limitaba a Técnico y Encargado); el formulario del superusuario lo ofrece por `ROLES_INTERNOS`.
- [x] T-13-02 — Consulta de mermas y filtros.
  - RF: RF-13-01, RF-13-02.
  - Archivos: `indicadoresapp/mermas.py`, `indicadoresapp/filtros.py`, `indicadoresapp/tests/test_mermas.py`.
  - Hecho: cuatro estados, exclusiones y límites del rango con pruebas en verde.
- [x] T-13-03 — Panel, gráficos, detalle, menú e inicio del Director.
  - RF: RF-13-03, RF-13-04, RF-13-08, RF-13-09.
  - Archivos: `indicadoresapp/views.py`, `indicadoresapp/urls.py`, `templates/indicadores/mermas.html`, `indicadoresapp/graficos.py` (blíster, calendario y barras), `indicadoresapp/entregas.py` (entregas confirmadas por día o semana), `static/css/indicadores.css`, `coreapp/navegacion.py` (entrada «Mermas», campo `excepto`), `coreapp/views.py`, `templates/components/iconos.html` (`i-grafico`).
  - Hecho: panel con cifras, cuatro gráficos con tabla o leyenda escrita y detalle paginado; el Director ve el panel en `/` y 403 en el resto. Los gráficos se dibujan en la misma `mermas.html` (no hay `_segmentos.html`). El panel suma dos tarjetas que la spec no enumera («Cuánto llevan en el estante» y «Entregas confirmadas»), anotadas en [validation.md](validation.md#límites-y-fallos).
- [x] T-13-04 — Reportes Excel y PDF.
  - RF: RF-13-05.
  - Archivos: `indicadoresapp/reportes.py`, `coreapp/auditoria.py` (`registrar_referencia`).
  - Hecho: Excel con cuatro gráficos nativos y PDF sin compresión; sin RUT ni nombres; descarga auditada.
- [x] T-13-05 — Recetas preparadas en el reparto.
  - RF: RF-13-07, RF-13-10.
  - Archivos: `entregasapp/models.py`, `entregasapp/migrations/0003_recetaentrega_preparacion.py`, `entregasapp/services.py` (`registrar_entregada`), `recetasapp/services.py` (`_registrar_entrega_sin_reintento`), `recetasapp/preparacion.py`, `templates/recetas/preparacion_pendientes.html`.
  - Hecho: «En despacho» en pendientes; descuento a la fecha de preparación; no descontada y anulación vuelven a «Sin retirar».
- [x] T-13-06 — Derivación desde el panel.
  - RF: RF-13-06, RF-13-10.
  - Archivos: `entregasapp/services.py` (`preparaciones_para_derivar`, `derivar_desde_merma`), `indicadoresapp/views.py` (`DerivarMermaView`), `templates/indicadores/derivar.html`, `indicadoresapp/tests/test_derivacion.py`.
  - Hecho: casos normal, no elegible con y sin motivo, entrega abierta, sin recetas, idempotencia y permisos en verde.
- [x] T-13-07 — Pruebas concurrentes.
  - RF: RF-13-10.
  - Archivos: `indicadoresapp/tests/test_concurrencia.py`.
  - Hecho: tres escenarios con `TransactionTestCase` e hilos, en verde.
- [x] T-13-08 — Medición HTTP aislada, validación y documentación.
  - Archivos: `tools/verificar_spec_13_http.py`, `tools/previsualizar_interfaz.py`, `.claude/launch.json`, `validation.md`, `specs/README.md`, notas en las specs 02 y 08, `CLAUDE.md`, `docs/estructura.md`.
  - Hecho: medición con p95 bajo 2 s; regresión completa registrada en `validation.md`.

## Autorización posterior

2026-11-17: la usuaria indicó «pasa la spec 13 a aprobado e implementa». Se autorizan T-13-01 a T-13-08 en `fdaza`, sin rama nueva y sin commit.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-17 | T-13-01 a T-13-07 | `python manage.py test indicadoresapp` | 40 pruebas OK (37 + 3 concurrentes). |
| 2026-11-17 | T-13-08 | `python tools/verificar_spec_13_http.py` | Aprobado; p95 máximo 485 ms (Excel de 30 días). |
| 2026-11-17 | T-13-08 | `python manage.py test` | Ver [validation.md](validation.md#regresión-de-la-base). |
| 2026-11-17 | T-13-08 | Navegador integrado con `tools/previsualizar_interfaz.py` | Panel del Director revisado a 800 px; axe no ejecutado (ver validación). |
| 2026-11-18 | Reverificación en `crojas-base` | `python manage.py test indicadoresapp --parallel 1`; `python tools/verificar_spec_13_http.py`; suite completa | 59 pruebas OK; HTTP aprobado con p95 máximo 438,72 ms; 1164 pruebas OK. |

## Reanudación

Última acción real: reverificación técnica en `crojas-base` y validación rellenada (2026-11-18); el código está en el commit `aa08f74`. Siguiente paso: revisión de la usuaria (incluidas las dos tarjetas que la spec no enumera), axe y apertura real de los reportes.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
