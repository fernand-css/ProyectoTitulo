# Tareas — 10 / Gestión de turnos por personal

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md).
Estado: propuestas. Implementación autorizada: NO.
No ejecutar tareas de código por el hecho de aparecer aquí.

- [ ] T-10-01 — Esquema: eventos nuevos, letra y número anteriores, tipo de ventanilla urgencia.
  - RF: RF-10-04, RF-10-05, RF-10-07.
  - Depende de: T-04-06 (enmienda del spec 04).
  - Archivos previstos: `turnosapp/models.py`, migración, `turnosapp/tests/test_modelos.py`.
  - Hecho cuando: migración aplicada en base temporal; `makemigrations --check` limpio.
- [ ] T-10-02 — Término de turno de ventanilla y llamado de un día anterior.
  - RF: RF-10-01, RF-10-03, RF-10-06.
  - Depende de: T-10-01.
  - Archivos previstos: `turnosapp/atencion.py`, `turnosapp/tests/test_atencion.py`, `test_concurrencia.py`.
  - Hecho cuando: los criterios de RF-10-01 y RF-10-03 pasan, incluido el escenario concurrente frente al cierre de la atención.
- [ ] T-10-03 — Desactivación de cuenta con término de ventanilla.
  - RF: RF-10-02.
  - Depende de: T-10-02.
  - Archivos previstos: `usuariosapp/services.py`, sus pruebas.
  - Hecho cuando: la desactivación termina la ventanilla y un fallo revierte ambas cosas.
- [ ] T-10-04 — Reclasificación y urgencia.
  - RF: RF-10-04, RF-10-05, RF-10-06.
  - Depende de: T-10-01 y RF-05-13 implementado.
  - Archivos previstos: `turnosapp/atencion.py`, pruebas de servicio y concurrencia.
  - Hecho cuando: los criterios pasan, con urgencia frente a selección y dos urgencias simultáneas.
- [ ] T-10-05 — Interfaz: botones, confirmación y comprobante PDF del número nuevo.
  - RF: RF-10-01, RF-10-04, RF-10-05.
  - Depende de: T-10-02, T-10-04 y T-04-09 (comprobante en PDF).
  - Archivos previstos: `turnosapp/views.py`, `forms.py`, `templates/turnos/_estado.html`, plantilla de configuración, `turnosapp/comprobante.py` (reutilizado), pruebas de vistas.
  - Hecho cuando: permisos, CSRF, textos y confirmación verificados; el PDF a pantalla completa solo lo abre personal autorizado, sin impresión ni archivo guardado.
- [ ] T-10-06 — Validar y actualizar documentación.
  - RF: RF-10-01 a RF-10-07.
  - Depende de: T-10-01 a T-10-05.
  - Hecho cuando: resultados reales en `validation.md`, tareas y estado actualizados.

## Autorización posterior

2026-11-15: documento aprobado por la usuaria. Implementación pendiente de autorización.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-15 | Definición documental | Cuatro documentos e índice | Borrador guardado; ninguna tarea de código iniciada. |

## Reanudación

Última acción: documento aprobado el 2026-11-15. Siguiente paso: autorizar la implementación, después de la enmienda del spec 04 y de RF-05-13.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
