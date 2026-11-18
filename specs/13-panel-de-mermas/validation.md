# Validación — 13 / Panel de mermas

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).

Fecha: 2026-11-17 (creación). Entorno aislado: por definir al implementar (SQLite temporal con 670 pacientes sintéticos y 90 días de preparaciones sintéticas).
Referencia de código: ninguna; no hay implementación.
Estado: no ejecutada. Una plantilla rellenada con planes no es evidencia.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-13-01 | Pruebas de la consulta con los cuatro estados y una receta no preparada | Merma y recuperadas según la spec | — | pendiente |
| RF-13-02 | Pruebas de filtros: omisión, invertido, futuro, 400 días, crónico | Rango y errores según la spec | — | pendiente |
| RF-13-03 | Pruebas de serie por día y por semana, y período vacío | Gráficos con tabla; texto de vacío | — | pendiente |
| RF-13-04 | Pruebas del detalle por rol | Director sin «Derivar a domicilio» | — | pendiente |
| RF-13-05 | Abrir Excel y PDF y buscar RUT y nombres del padrón de la prueba | Archivos válidos sin datos personales; descarga auditada | — | pendiente |
| RF-13-06 | Pruebas de derivación (normal, no elegible, abierta, sin recetas, idempotencia) | Excepción y entrega atómicas | — | pendiente |
| RF-13-07 | Pruebas de entregada, vencida tras preparar, anulada y ventanilla | Vigencia a fecha de preparación; estados correctos | — | pendiente |
| RF-13-08 | Pruebas de acceso de `demo_director` a `/`, `/recetas/`, `/turnos/panel/` | 200, 403, 403 | — | pendiente |
| RF-13-09 | Pruebas de menú y acceso de Técnico y anónimo | 403 / inicio de sesión | — | pendiente |
| RF-13-10 | Tres escenarios con `TransactionTestCase` e hilos | Un solo resultado coherente en cada uno | — | pendiente |
| RNF-05 | `tools/verificar_spec_13_http.py` | p95 ≤ 2 s en panel y reportes | — | pendiente |

## Regresión de la base

Cero pruebas nuevas ejecutadas. Pendiente `python manage.py test` y `python manage.py makemigrations --check --dry-run` al implementar.

## Revisión visual si aplica

Pendiente: panel en computador y celular, gráficos con teclado, auditoría axe y apertura real de los reportes en Excel y en un visor de PDF.

## Límites y fallos

Sin ejecución. HU-22 (confirmación del paciente) queda fuera hasta la reserva 12.

## Aplicación y reversión

Migración prevista `entregasapp/0003_recetaentrega_preparacion` (reversible). En bases existentes, ejecutar `python manage.py crear_roles` para crear el grupo del Director. No ejecutado.

## Aceptación funcional

Pendiente.
