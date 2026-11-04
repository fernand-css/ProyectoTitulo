# Validación — 07 / Preparación y tiempos de espera

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-03. Código en `fdaza`. Estado: **verificación técnica aprobada; aceptación funcional, revisión visual/axe y usabilidad pendientes**.
La base de desarrollo no se migró. La suite Django usó una base de pruebas independiente de PostgreSQL; la herramienta HTTP usó una SQLite temporal y la eliminó al salir.

## Requisitos funcionales

| RF | Prueba / pasos / comando | Resultado obtenido | Estado |
|---|---|---|---|
| RF-07-01 | `test_preparacion_modelos.py`, `test_emision_preparacion.py`, emisión concurrente y suite completa | Una preparación por cada vínculo, `recibida_en` igual a la emisión, fallo de preparación revierte turno y correlativo, recuperación idempotente y emisión concurrente sin duplicados. La migración se aplicó en las bases de prueba desechables. | Aprobado |
| RF-07-02 | `test_preparacion_servicios.py`, `test_concurrencia_preparacion.py` | Marcar es idempotente y concurrente; mide desde la recepción o la marca anterior del mismo usuario en la jornada. Los permisos, el estado activo, la auditoría sin datos personales y el rollback se comprueban. | Aprobado |
| RF-07-03 | `test_preparacion_servicios.py` | Corregir descarta la medición y vuelve a recibida solo mientras el turno está activo y sin entrega; rechaza fuera de regla y deja auditoría. | Aprobado |
| RF-07-04 | `test_preparacion_vistas.py`, prueba JavaScript `preparacion.test.cjs` | Lista ordenada, estados textuales, respuestas privadas `no-store`, cambio con POST/CSRF y consulta cada 5 s que reemplaza solo si el contenido cambió. No agrega entrada al menú. | Código probado; revisión visual/axe pendiente por host |
| RF-07-05 | `test_preparacion_consultas.py`, `test_preparacion_vistas.py` | Incluye ausente, cierre sin atención y cierre con receta no entregada; excluye activo/reincorporado/retirado; búsqueda por RUT con/sin puntos y apellido sin distinguir mayúsculas ni tildes. | Aprobado |
| RF-07-06 | `test_retiro.py`, `test_concurrencia_preparacion.py` | Crea una entrega del vínculo original, evalúa vigencia al preparar, conserva el cierre histórico, aplica cupo actual e idempotencia; el retiro no supera el cupo. | Aprobado |
| RF-07-07 | `test_preparacion_promedio.py`, `test_preparacion_servicios.py` | Promedio móvil de 14 días, mínimo de 5, valor inicial de 5 min y exclusión de intervalos sobre 30 min. La segunda marca del mismo actor inicia en su marca anterior. | Aprobado |
| RF-07-08 | `test_espera.py` | Verifica fórmula, redondeo al siguiente tramo de 5 min, texto «menos de 5 minutos», caso sin ventanillas y cantidad constante de consultas. | Aprobado |
| RF-07-09 | `test_vistas.py`, pruebas de privacidad del tótem y comprobante | Resultado, recuperación y comprobante comparten la frase; la respuesta pública no incorpora identidad ni recetas del paciente sintético. | Aprobado |
| RF-07-10 | `test_panel.py`, `test_preparacion_vistas.py` | El panel periódico muestra carga, promedio, muestras y enlace a Preparación para Técnico/Q.F. La consulta devuelve la estimación vigente. | Aprobado |
| RF-07-11 | `test_preparacion_vistas.py`, `test_preparacion_servicios.py` | Matriz de roles, cuenta inactiva/sin perfil, CSRF, `no-store`, auditoría y rollback ante error cubiertos. RUT, nombres y texto libre no entran a la auditoría genérica. | Aprobado |
| RF-07-12 | `test_concurrencia_preparacion.py`, `test_atencion.py` y regresión completa | Cinco escenarios concurrentes de emisión, doble marca, doble retiro, retiro frente a entrega 03 y retiro frente a reincorporación; rechaza reincorporar si todo el turno ya se retiró. Las suites anteriores pasan con la única adaptación documentada al borrado del fixture protegido. | Aprobado |

## Regresión y estado del proyecto

- `.\venv\Scripts\python.exe manage.py test --noinput`: **550 pruebas aprobadas** en 160,447 s. Django creó y destruyó la base de pruebas PostgreSQL. El ejecutor indicó `System check identified no issues`.
- `node --test turnosapp/tests/*.test.cjs`: **58 pruebas aprobadas**, incluidas las dos pruebas nuevas de actualización de Preparación.
- `.\venv\Scripts\python.exe manage.py check`: sin problemas.
- `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: `No changes detected`.
- Las cuatro acciones concurrentes de emisión, llamado y selección conservan la cobertura existente. Ninguna migración se aplicó a la base de desarrollo.

## Rendimiento HTTP

`.\venv\Scripts\python.exe tools/verificar_spec_07_http.py` recorrió 100 emisiones y retiros por HTTP real en loopback, con 670 pacientes sintéticos, cuatro ventanillas y SQLite temporal. Cada medición contiene 100 muestras. Los valores están en milisegundos:

| Escenario | p50 | p95 | Máximo |
|---|---:|---:|---:|
| Emisión con estimación | 40,91 | 57,02 | 86,10 |
| Lista de preparación | 25,67 | 48,20 | 51,12 |
| Marcar «Lista» | 46,46 | 72,55 | 126,83 |
| Marcar ausente | 75,20 | 102,78 | 130,29 |
| Consultar pendientes de retiro | 14,11 | 35,80 | 38,98 |
| Retirar preparado | 38,44 | 76,75 | 158,69 |
| Panel del 05 | 23,48 | 47,03 | 49,10 |

Todos los p95 quedaron por debajo de 2 s en este entorno. Es una medición de servidor WSGI local sobre SQLite sintética, no un pronóstico de producción. Para no esperar un minuto real, el guion adelanta `ultimo_llamado` en cada fixture antes de invocar por HTTP la acción normal de ausencia. No mide navegador, red del CESFAM ni hardware.

## Revisión visual y accesibilidad

Intenté consultar el navegador disponible para revisar escritorio y móvil, pero el host informó `Browsers: Error: The browser access host is unavailable`. No se pudieron inspeccionar la sección, el tótem, el comprobante ni el panel en navegador; axe, teclado y zoom quedan pendientes hasta que ese host vuelva a estar disponible. La prueba automatizada estructural y los estilos con tokens existentes sí pasan. La usabilidad con cinco personas y la aceptación funcional requieren revisión del equipo.

## Cobertura parcial y límites

- **HU-18 se cubre parcialmente:** la estimación cambia con la consulta periódica del personal. No se actualiza continuamente en el resultado ya abierto del tótem, el comprobante impreso ni la pantalla pública de sala, de acuerdo con el alcance acordado.
- Una ventanilla activa equivale a una persona que puede preparar; los valores iniciales del promedio son parámetros del prototipo, no una política acordada por el CESFAM.
- Los turnos activos que existían antes de aplicar la migración no tienen una preparación histórica y no entran a la estimación.
- La revisión automática y visual de accesibilidad, la validación con usuarios y la aceptación del equipo no se infieren de las pruebas automatizadas.
- El spec permanece **Aprobado** y no se cambia a **Implementado** mientras falten esas revisiones y la aceptación.

## Migración

`recetasapp/0004_preparacionreceta` se aplicó solo al preparar bases desechables para pruebas. No se migró la base PostgreSQL del proyecto. Revertirla elimina el registro de preparación y los tiempos medidos; respáldese la base antes de cualquier reversión en un entorno de demostración.
