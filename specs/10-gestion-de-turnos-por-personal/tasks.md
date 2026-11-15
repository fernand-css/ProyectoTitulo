# Tareas — 10 / Gestión de turnos por personal

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md).
Estado: en implementación. Autorizada el 2026-11-15.

- [x] T-10-01 — Esquema: eventos nuevos, letra y número anteriores, tipo de ventanilla urgencia.
  - RF: RF-10-04, RF-10-05, RF-10-07.
  - Depende de: T-04-06 (enmienda del spec 04).
  - Archivos previstos: `turnosapp/models.py`, migración, `turnosapp/tests/test_modelos.py`.
  - Hecho cuando: migración aplicada en base temporal; `makemigrations --check` limpio.
  - Resultado: `EventoTurno.letra_anterior` y `numero_anterior` con restricción de coherencia (migración `0013`); el tipo de ventanilla urgencia ya venía de RF-05-13. `makemigrations --check` limpio.
- [x] T-10-02 — Término de turno de ventanilla y llamado de un día anterior.
  - RF: RF-10-01, RF-10-03, RF-10-06.
  - Depende de: T-10-01.
  - Archivos previstos: `turnosapp/atencion.py`, `turnosapp/tests/test_atencion.py`, `test_concurrencia.py`.
  - Hecho cuando: los criterios de RF-10-01 y RF-10-03 pasan, incluido el escenario concurrente frente al cierre de la atención.
  - Resultado: `terminar_turno_ventanilla` en `atencion.py`; pruebas de servicio y escenario concurrente frente al cierre (3 vueltas) aprobados.
- [x] T-10-03 — Desactivación de cuenta con término de ventanilla.
  - RF: RF-10-02.
  - Depende de: T-10-02.
  - Archivos previstos: `usuariosapp/services.py`, sus pruebas.
  - Hecho cuando: la desactivación termina la ventanilla y un fallo revierte ambas cosas.
  - Resultado: `cambiar_estado_cuenta` termina la ventanilla en la misma transacción; prueba de fallo forzado sin desactivar.
- [x] T-10-04 — Reclasificación y urgencia.
  - RF: RF-10-04, RF-10-05, RF-10-06.
  - Depende de: T-10-01 y RF-05-13 implementado.
  - Archivos previstos: `turnosapp/atencion.py`, pruebas de servicio y concurrencia.
  - Hecho cuando: los criterios pasan, con urgencia frente a selección y dos urgencias simultáneas.
  - Resultado: `reclasificar_turno` y `marcar_urgencia`; urgencia frente a selección y tres urgencias simultáneas aprobadas (5 de 5 corridas).
- [x] T-10-05 — Interfaz: botones, confirmación y comprobante PDF del número nuevo.
  - RF: RF-10-01, RF-10-04, RF-10-05.
  - Depende de: T-10-02, T-10-04 y T-04-09 (comprobante en PDF).
  - Archivos previstos: `turnosapp/views.py`, `forms.py`, `templates/turnos/_estado.html`, plantilla de configuración, `turnosapp/comprobante.py` (reutilizado), pruebas de vistas.
  - Hecho cuando: permisos, CSRF, textos y confirmación verificados; el PDF a pantalla completa solo lo abre personal autorizado, sin impresión ni archivo guardado.
  - Resultado: pantalla de término de turno, enlaces en Ventanillas y en el panel, cambio de fila y urgencia en el historial (no en la lista del panel, ver spec) y comprobante PDF del personal con «Reemplaza a tu número anterior». Permisos, CSRF y GET sin cambios probados.
- [x] T-10-06 — Validar y actualizar documentación.
  - RF: RF-10-01 a RF-10-07.
  - Depende de: T-10-01 a T-10-05.
  - Hecho cuando: resultados reales en `validation.md`, tareas y estado actualizados.
  - Resultado: 942 pruebas Django y cinco suites JS aprobadas; herramienta HTTP aprobada; `validation.md`, `CLAUDE.md`, `docs/estructura.md` e índice actualizados. Navegador, visor real y aceptación pendientes.

## Autorización posterior

2026-11-15: documento aprobado por la usuaria. Después, «sigamos con la siguiente spec» autoriza la implementación en `fdaza`, sin rama nueva y sin commit hasta que la usuaria lo pida.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-15 | Definición documental | Cuatro documentos e índice | Borrador guardado; ninguna tarea de código iniciada. |
| 2026-11-15 | T-10-01 a T-10-06 | Modelos, migración 0013, `atencion.py`, `usuariosapp/services.py`, vistas, plantillas, comprobante, 20 pruebas nuevas y herramienta HTTP | 942 Django y 5 JS aprobadas; HTTP aprobado. |

## Reanudación

Última acción: T-10-01 a T-10-06 completadas técnicamente el 2026-11-15. Siguiente: revisión en navegador (incluido el visor de PDF), axe, usabilidad y aceptación. No marcar Implementado por las pruebas automatizadas.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
