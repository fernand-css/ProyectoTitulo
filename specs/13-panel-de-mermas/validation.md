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

## Enmienda del 2026-11-25

Implementada técnicamente el 2026-11-25 en `crojas-base`, sin commit, junto con la [segunda enmienda del 05](../05-cola-ponderada-y-llamado/spec.md#segunda-enmienda-del-2026-11-25--causa-de-no-entrega-borrador) (RF-05-14) y la [enmienda del 07](../07-preparacion-y-tiempos-de-espera/spec.md#enmienda-del-2026-11-25--derivar-desde-pendientes-de-retiro-borrador) (RF-07-13). Pruebas Django sobre la base PostgreSQL de pruebas; medición HTTP con SQLite temporal.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-05-14 | `turnosapp.tests.test_causa_no_entrega` (14), `test_panel`, concurrentes del 05 | Causa por receta y general; «Otro» exige detalle; texto libre = «Otro»; auditoría sin el detalle | Según la spec; las pruebas concurrentes del 05 siguen en verde | Aprobado en pruebas |
| RF-13-11 | `test_periodos.ClasesTests`, `FiltroTests`, `test_vistas.PanelTests` | Ocho clases, flechas, límites, enlaces antiguos, mes por omisión | Según la spec (con fecha fija 25-11-2026 en las pruebas unitarias) | Aprobado en pruebas |
| RF-13-12 | `test_periodos.ComparacionTests`, `test_canales.CifrasClaveTests` | Mismos días del período anterior; texto con palabras; sin datos | Según la spec | Aprobado en pruebas |
| RF-13-13 | `test_canales.CifrasClaveTests`, `test_vistas.test_enlace_a_pendientes_solo_para_la_qf` | Cuatro cifras; «más de 14 días» con enlace solo para la Q.F. | Según la spec | Aprobado en pruebas |
| RF-13-14 | `test_canales.FarmaciaTests`, `DomicilioTests` | Criterios 2/3/5 40,0 % y 1/4/5 20,0 %; turnos activos en la nota; ficha por su fecha | Según la spec | Aprobado en pruebas |
| RF-13-15 | `test_graficos.CalendarioTests`, `test_vistas.test_semestre_y_anio_van_en_columnas` | Calendario con «Aún no»; columnas por semana o mes | Según la spec | Aprobado en pruebas y en el navegador |
| RF-13-16 | `test_canales` (motivos, cierre antiguo = «Otro» sin su texto) | Motivos por receta y por visita; texto libre oculto | Según la spec | Aprobado en pruebas |
| RF-13-17 | `test_canales.test_retiro_posterior_cuenta_el_dia_del_retiro`, `test_graficos.ColumnasApiladasTests` | Retiro en el día del retiro; dos gráficos apilados | Según la spec | Aprobado en pruebas y en el navegador |
| RF-13-18 | `test_mermas.test_preparadas_incluyen_las_entregadas_en_la_atencion`, `test_graficos.test_barra_al_100_suma_cien_y_marca_las_vacias` | Cinco partes que suman 100 | Según la spec | Aprobado en pruebas |
| RF-13-19 | `test_canales.AusentesTests` | Celda lunes 10 h: 4 emitidos, 1 ausente, 25 %; fin de semana solo con turnos | Según la spec | Aprobado en pruebas y en el navegador |
| RF-13-20 | `test_vistas.test_dashboard_sin_datos_personales_para_ningun_rol` | Sin RUT ni nombres; sin blíster ni detalle | Según la spec | Aprobado en pruebas |
| RF-13-21 | `test_vistas.ReportesTests` y herramienta HTTP | CSV con BOM, «;», una fila por día; Excel con sus hojas; PDF; sin datos personales; auditados | Según la spec; el Excel suma la hoja «Datos de gráficos» (ver la revisión de la spec) | Aprobado en pruebas; Excel y visor de PDF reales pendientes |
| RF-13-22 y RF-07-13 | `test_derivar_desde_pendientes`, `test_vistas.test_deriva_y_redirige_a_la_entrega`, herramienta HTTP | Enlace solo en «Sin retirar» para Q.F. y superusuario, también en la búsqueda en vivo; «Volver» a Pendientes | Según la spec; 20 derivaciones por HTTP desde Pendientes | Aprobado en pruebas y HTTP |
| RNF-04 | `coreapp/tests/test_estaticos.py` (sin colores nuevos); navegador | Contraste AA, sin depender del color | Solo variables existentes; grilla de ausentes corregida a texto claro en los dos tonos oscuros; revisado en claro, oscuro y 375 px | Parcial: axe y usabilidad pendientes |
| RNF-05 | `python tools/verificar_spec_13_http.py` (366 días, 14.640 preparaciones, 4.758 visitas) | p95 ≤ 2 s | Panel: 1 día 98,77 ms; 7 días 125,63; mes 191,84; semestre 632,23; año 737,04; 366 días 800,09. Descargas del año: Excel 880,05; CSV 740,85; PDF 785,86. Derivar 179,88 | Aprobado |

Regresión: 1289 pruebas: 1288 OK y 1 falla en `coreapp.tests.test_estaticos` (la variable `--horas` de la grilla de ausentes no estaba definida en el CSS); corregida con un valor por omisión y vueltas a correr `coreapp.tests.test_estaticos` e `indicadoresapp`: 106 OK. `check` sin incidencias y `makemigrations --check --dry-run` sin cambios.

Límites: medición secuencial en loopback sobre SQLite, sin el volumen real del CESFAM (unas 1.200 recetas diarias; ver los riesgos del plan). Navegador revisado en la previsualización, sin axe. No se abrieron el Excel, el CSV ni el PDF en sus programas reales. `generar_mermas_demo` no crea entregas en la atención ni visitas (supuesto 6). La migración `turnosapp/0014` se aplicó en la base local (PostgreSQL) el 2026-11-25 por pedido de la usuaria («Sí, migra»); `migrate --plan` queda sin operaciones pendientes.

Aceptación funcional de la enmienda: pendiente; no marcarla automáticamente después de ejecutar pruebas.
