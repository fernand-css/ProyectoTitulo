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

## Enmienda del 2026-11-25

Tareas de la [enmienda del 2026-11-25](spec.md#enmienda-del-2026-11-25--dashboard-de-mermas-y-entregas-borrador). Diseño en [plan.md](plan.md#enmienda-del-2026-11-25). Autorizadas el 2026-11-25: la usuaria aprobó las tres enmiendas (13, 05 y 07) e indicó implementarlas («pasa las enmiendas a aprobado e implementa»).

- [x] T-13-09 — Causa de no entrega en el cierre (enmienda del 05).
  - RF: RF-05-14 (para RF-13-16).
  - Depende de: ninguna.
  - Archivos: `turnosapp/models.py`, `turnosapp/migrations/0014_causa_no_entrega.py`, `turnosapp/forms.py`, `turnosapp/atencion.py`, `templates/turnos/finalizar.html`, `turnosapp/tests/`.
  - Hecho cuando: los criterios RF-05-14 del 05 pasan, las llamadas con solo texto siguen funcionando, las pruebas concurrentes del 05 siguen en verde y `makemigrations --check` no detecta cambios pendientes.
- [x] T-13-10 — Períodos y comparación.
  - RF: RF-13-11, RF-13-12.
  - Depende de: ninguna.
  - Archivos: `indicadoresapp/periodos.py` (reemplaza `filtros.py`), `indicadoresapp/tests/test_periodos.py`.
  - Hecho cuando: los ocho períodos, las flechas, los límites, los enlaces antiguos y la comparación con meses de distinto largo tienen pruebas en verde.
- [x] T-13-11 — Cálculos del dashboard.
  - RF: RF-13-13, RF-13-14, RF-13-15, RF-13-16, RF-13-17, RF-13-18, RF-13-19.
  - Depende de: T-13-09 (causas) y T-13-10.
  - Archivos: `indicadoresapp/mermas.py`, `indicadoresapp/canales.py` (absorbe `entregas.py`), `indicadoresapp/ausentes.py`, `indicadoresapp/tablero.py`, `indicadoresapp/tests/`.
  - Hecho cuando: los criterios de aceptación de RF-13-13 a RF-13-19 pasan como pruebas, con el filtro de tipo.
- [x] T-13-12 — Panel en estilo dashboard.
  - RF: RF-13-20 (y la presentación de RF-13-13 a RF-13-19).
  - Depende de: T-13-11.
  - Archivos: `indicadoresapp/views.py`, `indicadoresapp/graficos.py`, `templates/indicadores/mermas.html` y sus parciales, `static/css/indicadores.css`, `static/css/base.css`, `static/css/tema_oscuro.css`, `coreapp/tests/test_estaticos.py`.
  - Hecho cuando: el panel muestra las secciones en el orden de RF-13-20, cada gráfico con su tabla, sin RUT ni nombres para ningún rol, sin blíster ni detalle por paciente, y los colores nuevos pasan el contraste en las dos paletas.
- [x] T-13-13 — Descargas en Excel, CSV y PDF.
  - RF: RF-13-21.
  - Depende de: T-13-11.
  - Archivos: `indicadoresapp/reportes.py`, `indicadoresapp/views.py`, `indicadoresapp/tests/`.
  - Hecho cuando: el CSV tiene BOM, «;», las columnas del plan y una fila por día; el Excel tiene sus tres hojas; el PDF tiene sus secciones; ninguno contiene RUT, nombres ni el texto de «Otro», y cada descarga queda auditada.
- [x] T-13-14 — Derivar desde «Pendientes de retiro».
  - RF: RF-13-22, RF-07-13.
  - Depende de: ninguna.
  - Archivos: `recetasapp/views.py`, `templates/recetas/_pendientes_resultados.html`, `indicadoresapp/views.py` («Volver»), `recetasapp/tests/`, `indicadoresapp/tests/test_vistas.py`.
  - Hecho cuando: el enlace aparece solo en las filas «Sin retirar» para la Q.F. y el superusuario, también tras la búsqueda en vivo, y «Volver» regresa a «Pendientes de retiro».
- [x] T-13-15 — Datos de demostración y medición HTTP de un año.
  - RF: RNF-05 de la enmienda.
  - Depende de: T-13-09, T-13-12 y T-13-13.
  - Archivos: `indicadoresapp/management/commands/generar_mermas_demo.py`, `tools/verificar_spec_13_http.py`.
  - Hecho cuando: el generador crea causas y ausentes con hora, y la herramienta mide con 366 días sintéticos un p95 de 2 s o menos en el panel de cada período y en las tres descargas.
- [x] T-13-16 — Regresión, validación y documentación.
  - Depende de: T-13-09 a T-13-15.
  - Archivos: `validation.md` (13, 05 y 07), `specs/README.md`, `CLAUDE.md`, `docs/estructura.md`.
  - Hecho cuando: la suite completa está en verde, la evidencia está registrada y quedan anotados como pendientes el navegador con axe, la apertura real de las descargas, la usabilidad y la aceptación.

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
| 2026-11-25 | T-13-09 | `python manage.py test turnosapp --parallel 1` | 295 pruebas; una falla de la prueba nueva del historial (faltaba iniciar sesión), corregida y vuelta a correr: `test_causa_no_entrega` 14 OK. |
| 2026-11-25 | T-13-10 a T-13-14 | `python manage.py test indicadoresapp --parallel 1` | 81 pruebas OK tras corregir el método `periodo()` que tapaba el campo, la causa obligatoria de las recetas no descontadas en la prueba y el cierre coherente de los turnos de prueba; luego 3 de `test_derivar_desde_pendientes` y 5 de `test_comando_mermas` OK. |
| 2026-11-25 | T-13-15 | `python tools/verificar_spec_13_http.py` | Aprobado con 366 días: p95 máximo 880,05 ms (Excel del año); panel del año 737,04 ms y de 366 días 800,09 ms. |
| 2026-11-25 | T-13-16 | Navegador integrado con `tools/previsualizar_interfaz.py` | Dashboard de la Q.F. en computador, celular (375 px, sin desplazamiento horizontal) y modo oscuro, y «Pendientes de retiro» con el enlace; corregidos el contraste de la grilla de ausentes y los porcentajes 34/33/33. Sin axe. |
| 2026-11-25 | T-13-16 | `python manage.py test --parallel 1`, `check`, `makemigrations --check --dry-run` | 1289 pruebas: 1288 OK y 1 falla en `coreapp.tests.test_estaticos` (la variable `--horas` de la grilla de ausentes no estaba definida en el CSS); corregida con un valor por omisión y vueltas a correr `coreapp.tests.test_estaticos` e `indicadoresapp`: 106 OK. `check` sin incidencias y `makemigrations --check --dry-run` sin cambios. |

## Reanudación

Última acción real: enmienda del 2026-11-25 implementada técnicamente en `crojas-base`, sin commit (T-13-09 a T-13-16). Siguiente paso: revisión de la usuaria, axe y apertura real de Excel, CSV y PDF.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
