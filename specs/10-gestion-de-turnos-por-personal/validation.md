# Validación — 10 / Gestión de turnos por personal

Fecha: 2026-11-15. Entorno aislado: por definir al implementar (SQLite temporal o base de pruebas de PostgreSQL, con padrón sintético de 670).
Referencia de código: ninguna.
Estado: no ejecutada. Una plantilla rellenada con planes no es evidencia.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-10-01 | Término de turno con turno llamado de hoy | Ventanilla deshabilitada con hora; turno de vuelta en la cola con su antigüedad | — | pendiente |
| RF-10-02 | Desactivar cuenta con ventanilla ocupada; forzar fallo | Ventanilla terminada; rollback completo ante fallo | — | pendiente |
| RF-10-03 | Término con turno llamado de ayer | `sin_atencion_cierre`, no vuelve a la cola | — | pendiente |
| RF-10-04 | Reclasificar en espera y ya llamado | Cambio con historial; rechazo si ya fue llamado | — | pendiente |
| RF-10-05 | Marcar urgencia con cola mixta | Número U nuevo, primer llamado compatible y comprobante PDF a pantalla completa en el equipo del personal | — | pendiente |
| RF-10-06 | Tres escenarios concurrentes con `TransactionTestCase` e hilos | Sin doble asignación ni números repetidos | — | pendiente |
| RF-10-07 | Revisar historial, auditoría y sala | Sin datos personales; sin anuncio de reclasificación | — | pendiente |

## Regresión de la base

Cero pruebas nuevas. Al implementar: suite completa, con atención especial a las pruebas concurrentes de los specs 04, 05 y 06.

## Revisión visual si aplica

Pendiente: panel del Técnico y configuración de la Q.F. en escritorio y móvil, teclado, foco, axe.

## Límites y fallos

Nada ejecutado. Documento aprobado el 2026-11-15; implementación no autorizada.

## Aplicación y reversión

Sin migraciones creadas.

## Aceptación funcional

Pendiente.
