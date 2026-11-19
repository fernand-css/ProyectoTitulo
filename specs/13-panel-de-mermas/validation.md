# Validación — 13 / Panel de mermas

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).

Fecha: 2026-11-17 (implementación en `fdaza`) y 2026-11-18 (reverificación en `crojas-base` tras incorporar `fdaza`).
Referencia de código: commit `aa08f74` («Se agrego la spec 13: Panel de mermas»), hoy en `crojas-base@ee80ee8`.
Entorno aislado: `tools/verificar_spec_13_http.py` con SQLite temporal, 670 pacientes sintéticos y 3.600 preparaciones sintéticas en 90 días. Pruebas Django sobre la base PostgreSQL de pruebas que crea el ejecutor.
Estado: **verificación técnica ejecutada**. Navegador con axe, apertura real de los reportes, usabilidad y aceptación pendientes.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-13-01 | `test_mermas.EstadosTests` (cuatro estados, no preparada, entregada en la atención, cuatro cierres) | Merma y recuperadas según la spec | Cuatro estados y exclusiones correctas | Aprobado en pruebas |
| RF-13-02 | `test_mermas.FiltrosTests`, `test_vistas.PanelTests.test_filtro_invalido_muestra_error_y_omision` | 30 días por omisión; invertido, futuro y más de 366 días rechazados; 366 aceptado; tipo crónico | Según la spec | Aprobado en pruebas |
| RF-13-03 | `test_mermas.test_serie_por_dia_y_por_semana`, `test_graficos`, `test_vistas.test_periodo_vacio` | Cuatro gráficos con tabla o texto; texto de período vacío | Evolución, crónico/general, cierre del turno y blíster de recuperadas/perdidas, con tabla o leyenda escrita | Aprobado en pruebas |
| RF-13-04 | `test_mermas.test_detalle_por_paciente_ordenado_por_la_mas_antigua`, `test_vistas.test_detalle_con_derivar_solo_para_la_qf` | Orden por la más antigua; Director sin «Derivar a domicilio» | Según la spec | Aprobado en pruebas |
| RF-13-05 | `test_vistas.ReportesTests`; herramienta HTTP | Excel y PDF válidos, sin datos personales y auditados | Excel con cuatro gráficos nativos; el PDF no contiene ninguno de 200 RUT sintéticos; descarga auditada | Aprobado en pruebas; apertura en Excel y visor de PDF reales pendiente |
| RF-13-06 | `test_derivacion.DerivacionTests`, `test_vistas.DerivarVistaTests` | Excepción y entrega atómicas; idempotencia; solo Q.F./superusuario | Normal, no elegible con motivo, reversión, entrega abierta, sin preparadas e idempotencia correctos | Aprobado en pruebas |
| RF-13-07 | `test_derivacion.DespachoDeLoPreparadoTests` | Vigencia a la fecha de preparación; no descontada y anulada vuelven a «Sin retirar» | Según la spec; la ventanilla no entrega lo que está en despacho | Aprobado en pruebas |
| RF-13-08 | `test_vistas.AccesoTests`; herramienta HTTP | `demo_director`: `/` 200 con el panel; 403 en el resto | Inicio con el panel; 403 en Recetas, Atención, Entregas y Usuarios | Aprobado en pruebas y HTTP |
| RF-13-09 | `test_vistas.test_panel_por_rol`, `test_menu_del_director_solo_mermas_y_perfil` | Técnico 403; anónimo al inicio de sesión | Según la spec | Aprobado en pruebas |
| RF-13-10 | `test_concurrencia.ConcurrenciaDerivacionTests` (`TransactionTestCase` e hilos) | Un solo resultado coherente en cada escenario | Tres escenarios en verde: dos derivaciones del mismo paciente, derivación frente a retiro en ventanilla y derivación frente a `programar_lote` | Aprobado en pruebas |
| RNF-05 | `python tools/verificar_spec_13_http.py` | p95 ≤ 2 s en panel, reportes y derivación | p95 máximo 438,72 ms (Excel de 30 días) | Aprobado |

## Ejecuciones

| Fecha | Comando | Resultado |
|---|---|---|
| 2026-11-17 | `python manage.py test indicadoresapp` | 40 pruebas OK (37 + 3 concurrentes). |
| 2026-11-17 | `python tools/verificar_spec_13_http.py` | Aprobado; p95 máximo 485 ms (Excel de 30 días). |
| 2026-11-18 | `python manage.py test indicadoresapp --parallel 1` | **59 pruebas OK** (se suman `test_comando_mermas`, `test_entregas` y `test_graficos`). |
| 2026-11-18 | `python tools/verificar_spec_13_http.py` | Aprobado. Detalle abajo. |

Medición del 2026-11-18 (WSGI en loopback, carga secuencial, SQLite; 20 muestras para panel y derivación, 10 para reportes):

| Solicitud | 30 días | 90 días | 366 días |
|---|---|---|---|
| Panel | 172,38 ms | 245,41 ms | 231,91 ms |
| Reporte Excel | 438,72 ms | 195,71 ms | 197,03 ms |
| Reporte PDF | 266,97 ms | 213,93 ms | 250,73 ms |

Derivación: 20 derivaciones, p95 196,73 ms. Una ejecución anterior del mismo día dio un máximo de 588,46 ms (Excel de 30 días), también bajo 2 s.

## Regresión de la base

2026-11-18, `crojas-base@ee80ee8`: `python manage.py check` sin incidencias; `python manage.py makemigrations --check --dry-run` sin cambios; `python manage.py test --parallel 1` con **1164 pruebas OK** en 420 s.

## Revisión visual si aplica

- 2026-11-17: panel del Director revisado en el navegador integrado a 800 px con `tools/previsualizar_interfaz.py`.
- Pendiente: panel en computador y celular de la Q.F., gráficos y detalle con teclado, auditoría axe y apertura real de los reportes en Excel y en un visor de PDF.

## Límites y fallos

- La medición es secuencial, en loopback y sobre SQLite; no reemplaza una prueba de carga en el entorno de despliegue.
- El panel implementado agrega dos tarjetas que la spec no enumera en RF-13-03: «Cuánto llevan en el estante» (días sin retirar) y «Entregas confirmadas por día o semana» (`indicadoresapp/entregas.py`, con promedio de 7 días). Usan solo cifras agregadas y no reemplazan los cuatro gráficos exigidos; falta que la usuaria las confirme o se anoten en la spec.
- HU-22 (confirmación del paciente) sigue fuera: el panel no distingue entregas confirmadas por el paciente.

## Aplicación y reversión

Migración `entregasapp/0003_recetaentrega_preparacion` (reversible). En bases existentes, ejecutar `python manage.py crear_roles` para crear el grupo del Director. Aplicado en la base local de `crojas-base` el 2026-11-18, junto con `entregasapp` 0004–0006 y `recetasapp` 0005 del spec 12; `crear_roles` conservó cuentas y permisos.

## Aceptación funcional

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
