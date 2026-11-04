# Validación — 07 / Preparación y tiempos de espera

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-03. Entorno aislado: por definir al implementar (base de pruebas desechable de Django sobre PostgreSQL y SQLite temporal para la herramienta HTTP, con datos sintéticos).
Referencia de código: ninguna; no hay implementación.
Estado: **no ejecutada**. Esta tabla contiene planes, no evidencia.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-07-01 | `test_emision_preparacion.py`; falla forzada; recuperación del mismo turno | Una preparación por receta; sin turno ni número ante falla; sin duplicados al recuperar | — | pendiente |
| RF-07-02 | `test_preparacion_servicios.py`; dos marcas simultáneas | Una marca y una medición; el segundo recibe el resultado original | — | pendiente |
| RF-07-03 | Corregir con turno activo y con entrega existente | La primera vuelve a «recibida»; la segunda se rechaza | — | pendiente |
| RF-07-04 | `test_preparacion_vistas.py`; revisión visual | Orden de llegada, estados con texto, actualización sin recargar | — | pendiente |
| RF-07-05 | `test_preparacion_consultas.py` | Tres cierres incluidos; activos y reincorporados excluidos; búsqueda por RUT y apellido | — | pendiente |
| RF-07-06 | `test_retiro.py`; concurrencia de retiro | Una entrega; vigencia a la fecha de preparación; cupo nunca excedido | — | pendiente |
| RF-07-07 | `test_preparacion_promedio.py` | Ventana de 14 días, tope de 30 min, mínimo de 5 muestras, intervalo de trabajo | — | pendiente |
| RF-07-08 | `test_espera.py` | 6 recetas × 4 min ÷ 2 ventanillas = «unos 15 minutos»; sin ventanillas no estima; menos de 5 min | — | pendiente |
| RF-07-09 | Pruebas de vista y de privacidad del tótem y el comprobante | Misma frase en pantalla y papel; sin datos personales | — | pendiente |
| RF-07-10 | `test_panel.py`; panel abierto durante el avance | Carga y estimación se actualizan sin recargar | — | pendiente |
| RF-07-11 | `test_preparacion_permisos.py` | Encargado, anónimo, cuentas inválidas y POST sin CSRF rechazados; auditoría sin datos personales | — | pendiente |
| RF-07-12 | `test_concurrencia_preparacion.py`; regresión 03–06 | Al menos tres escenarios sin duplicados; reincorporar con todo retirado se rechaza; suites previas sin cambios | — | pendiente |

## Regresión de la base

Pendiente. Se registrará la suite completa de Django (hoy 249 pruebas en `turnosapp` y `coreapp` y el resto del proyecto), las pruebas de JavaScript (`node --test turnosapp/tests/*.test.cjs`), `manage.py check` y `makemigrations --check --dry-run`. Las pruebas del 03, 04, 05 y 06 deben pasar sin modificarse.

## Rendimiento

Pendiente. `tools/verificar_spec_07_http.py` medirá emisión con estimación, marca, retiro y panel con 670 pacientes sintéticos; objetivo de p95 de 2 s o menos (RNF-05).

## Revisión visual si aplica

Pendiente: escritorio y móvil de la sección Preparación, el resultado del tótem, el comprobante de 80 mm y el panel; axe, teclado y zoom. Si el host de navegador no está disponible, se registrará como no realizado, sin declararlo cumplido.

## Límites y fallos

Ninguno medido todavía. Límites ya conocidos por diseño:
- HU-18 quedará cubierta de forma parcial: la estimación se actualiza continuamente solo para el personal; el resultado del tótem dura segundos y el comprobante es papel, y la pantalla de sala queda fuera por decisión del usuario.
- La estimación supone que cada ventanilla en atención representa a una persona que prepara, y depende de parámetros iniciales no acreditados por el CESFAM.
- Los turnos activos al aplicar la migración no tendrán preparación.
- La prueba de usabilidad con cinco personas y la aceptación funcional no se pueden sustituir por pruebas automáticas.

## Aplicación y reversión

No ejecutadas. La migración `recetasapp/0004_*` creará una tabla; la base del proyecto no se migra sin aprobación expresa. La reversión elimina la tabla y los tiempos medidos; se recomienda respaldo antes de retroceder.

## Aceptación funcional

Pendiente.
