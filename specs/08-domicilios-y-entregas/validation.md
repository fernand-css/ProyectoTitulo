# Validación — 08 / Domicilios y entregas a domicilio

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-11. Entorno aislado previsto: base de pruebas desechable de Django; SQLite y carpeta privada temporales para `tools/verificar_spec_08_http.py`; padrón sintético de 670 pacientes y fotos generadas en memoria.
Referencia de código: no existe; spec en Borrador.
Estado: **no ejecutada**. Una plantilla rellenada con planes no es evidencia.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-08-01 | `test_elegibilidad.py`; suite del 04 | Límites de edad (`> 80`), postrado y excepción; el tótem clasifica igual | — | pendiente |
| RF-08-02 | `test_excepciones.py` | Una inscripción vigente por paciente; retiro con autor; rechazo si ya es elegible | — | pendiente |
| RF-08-03 | `test_domicilios.py`; escenario concurrente 6 | Creación desde el padrón; importación sin efecto; edición por versión sin pérdidas | — | pendiente |
| RF-08-04 | `test_domicilios.py` | Solo el encargado verifica; los cambios vuelven a pendiente; aviso de padrón cambiado | — | pendiente |
| RF-08-05 | `test_custom_image.py`, `test_fotos.py` | JPEG sin metadatos; rechazos; máximo de 3; vista privada con `no-store`; sin huérfanos | — | pendiente |
| RF-08-06 | `test_programacion.py`; escenario concurrente 1 | Recetas elegibles y exclusiones; una entrega abierta; idempotencia | — | pendiente |
| RF-08-07 | `test_doble_via.py`; escenarios concurrentes 2 y 4; privacidad del tótem | Tótem `despacho_abierto` sin número ni datos; confirmación del 03 rechazada | — | pendiente |
| RF-08-08 | `test_vistas_encargado.py` | Hoy, atrasadas y próximas del propio encargado | — | pendiente |
| RF-08-09 | `test_registro.py`; escenarios concurrentes 3 y 4 | Un resultado; descuento solo de las válidas; cupo intacto; idempotencia | — | pendiente |
| RF-08-10 | `test_registro.py` | Motivo obligatorio, nota con «Otro»; pendiente de gestión sin descuento | — | pendiente |
| RF-08-11 | `test_gestion.py`; escenario concurrente 5 | Intentos inmutables; reasignar y anular; filtros exactos | — | pendiente |
| RF-08-12 | `test_gestion.py` | Lista de no descontadas y revisión con autor | — | pendiente |
| RF-08-13 | `test_navegacion.py`, `test_vistas*.py` | Menú, pestañas, inicio del encargado y ficha del paciente por perfil | — | pendiente |
| RF-08-14 | `test_permisos.py` | Matriz, CSRF, `no-store`, sin RUT en URL ni auditoría; rollback | — | pendiente |
| RF-08-15 | `test_concurrencia.py` (6 escenarios); regresión completa | Invariantes de concurrencia; suites del 03 al 07 sin cambiar aserciones | — | pendiente |

## Regresión de la base

No ejecutada. Al implementar: `manage.py test --noinput`, `node --test` de las pruebas `.cjs`, `manage.py check` y `manage.py makemigrations --check --dry-run`, con el número real de pruebas.

## Rendimiento HTTP

No ejecutado. `tools/verificar_spec_08_http.py` deberá registrar el p50, el p95 y el máximo de cada escenario: domicilios, foto, programación, «Mis entregas», registro, reasignación y consultas con filtros.

## Revisión visual si aplica

No ejecutada. Pendiente: escritorio y celular, axe, teclado, zoom, ubicación real del navegador en contexto seguro y toma de foto desde un celular.

## Límites y fallos

- La parte sin conexión de HU-15 (RNF-03, NS05) queda para la reserva 11. HU-14 (mapa y orden de visita) queda para el 09, y HU-19 y HU-22, para la reserva 12.
- La ubicación del navegador requiere HTTPS o `localhost`.
- La usabilidad con cinco personas y la aceptación funcional requieren evidencia propia.

## Aplicación y reversión

Sin ejecutar. Migración prevista: `entregasapp/0001_initial`. No migrar la base del proyecto sin aprobación. Respaldar la base y `privado/` antes de una reversión.

## Aceptación funcional

Pendiente.
