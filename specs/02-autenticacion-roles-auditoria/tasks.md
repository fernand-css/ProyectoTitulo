# Tareas — 02 / Autenticación, roles y auditoría

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-01. Estado: implementación en curso. Implementación autorizada: SÍ, en `fdaza`, conservando cambios y con commit al terminar.

Las rutas indicadas son propuestas salvo los archivos que ya existen según el plan. No ejecutar tareas por el hecho de aparecer aquí.

- [x] **T-02-01 — Crear Perfil y migraciones de actualización.**
  - RF: RF-02-05, RF-02-06.
  - Depende de: ninguna; requiere spec 01 implementada.
  - Archivos previstos: `usuariosapp/models.py`, nuevas migraciones y `tests/test_perfil.py`.
  - Hecho cuando: base vacía y copia sintética previa migran; cuentas existentes conservan claves/roles y superusuario accede; no se verifica ningún correo por inferencia.
- [x] **T-02-02 — Preparar roles, habilitación y datos de demostración.**
  - RF: RF-02-02, RF-02-12.
  - Depende de: T-02-01.
  - Archivos previstos: `coreapp/roles.py`, `mixins.py`, contexto e inicio; nuevos servicios, comandos `crear_roles`/`crear_usuarios_demo` y pruebas.
  - Hecho cuando: dos ejecuciones no duplican ni cambian claves; un rol por cuenta ordinaria, perfiles ausentes y superusuario se comportan según la matriz; solo se usan datos sintéticos.
- [x] **T-02-03 — Ampliar eventos y consulta de auditoría.**
  - RF: RF-02-09, RF-02-10, RF-02-11.
  - Depende de: T-02-02.
  - Archivos previstos: `coreapp/auditoria.py`, `coreapp/admin.py`, nuevas señales y conexión en `usuariosapp/apps.py`, pruebas de auditoría/Admin.
  - Hecho cuando: se admiten eventos sin cuenta identificada sin guardar datos enviados; bitácora solo consultable por superusuario y no editable; los servicios soportan atomicidad y eventos sin duplicación.
- [x] **T-02-04 — Implementar perfil y verificación de correo.**
  - RF: RF-02-05, RF-02-06, RF-02-10.
  - Depende de: T-02-03.
  - Archivos previstos: formularios, servicios, vistas y URLs de `usuariosapp`, nuevas plantillas de perfil/correo y pruebas `test_perfil.py`/`test_correo.py`.
  - Hecho cuando: edición propia persiste sin privilegios; correo anterior sigue vigente hasta confirmar; tokens expirados/sustituidos/consumidos fallan y la prueba concurrente consume una sola vez; auditoría acompaña los cambios.
- [x] **T-02-05 — Completar autenticación, cambio y recuperación de contraseña.**
  - RF: RF-02-01, RF-02-03, RF-02-04, RF-02-09, RF-02-10.
  - Depende de: T-02-04.
  - Archivos previstos: formularios, vistas/URLs y señales, plantillas `registration/`, pruebas de login/recuperación y sesiones.
  - Hecho cuando: casos normales/negativos, CSRF, `next`, cuentas desactivadas, correo verificado y tokens están probados; la contraseña anterior deja de autenticar; se registra cada evento correspondiente sin secretos.
- [x] **T-02-06 — Implementar panel de Q.F. y administración superior.**
  - RF: RF-02-07, RF-02-08, RF-02-10.
  - Depende de: T-02-05.
  - Archivos previstos: servicios/formularios/vistas/URLs, `usuariosapp/admin.py`, nuevas plantillas `usuarios/gestion_*`, pruebas `test_gestion_usuarios.py`/`test_admin.py`.
  - Hecho cuando: Q.F. gestiona solo técnicos/encargados no privilegiados; no eleva permisos ni administra jefaturas; controles resisten manipulación y cambio concurrente de roles; Admin respeta invariantes y audita sin duplicados.
- [ ] **T-02-07 — Integrar navegación y verificar el alcance completo.**
  - RF: RF-02-01 a RF-02-12.
  - Depende de: T-02-06.
  - Archivos previstos: navbar, contexto/inicio y pruebas afectadas; `README.md`, `docs/estructura.md`, `CLAUDE.md`, documentos de esta carpeta e índice.
  - Hecho cuando: pruebas de la matriz y regresión, checks, migraciones y comandos sobre entorno aislado tienen resultados registrados; la revisión visual ejecutada y sus límites constan en `validation.md`; estados reflejan evidencia real y no aprobación funcional automática.
  - Avance: navegación por permisos, formularios y CSS integrados; 185 pruebas aprobadas; validación HTTP real y migraciones desde cero aprobadas. Pendiente: revisión visual en una ventana dedicada autorizada o aceptación explícita del límite por el usuario.

## Autorización posterior

El usuario marcó el documento Aprobado, invocó `spec-impl` y posteriormente indicó conservar cambios, no crear una nueva rama y hacer commit al terminar. Se trabaja en `fdaza`, sin commits intermedios. La revisión por pasos se mantiene según la skill.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-01 | Definición documental | Cuatro documentos e índice | Borrador; ninguna tarea de implementación ejecutada |
| 2026-11-01 | T-02-01 | `usuariosapp/models.py`, migraciones 0001/0002 y `tests/test_perfil.py`; pruebas focalizadas, suite, check y control de migraciones | 7 pruebas nuevas y 76 pruebas totales aprobadas; ver validación |
| 2026-11-01 | T-02-02 | Roles/mixins/contexto/inicio/403, servicios y comandos, pruebas y guías de uso | 42 pruebas focalizadas y 95 totales aprobadas; check y migraciones consistentes |
| 2026-11-01 | T-02-03 | Helper de eventos, Admin de auditoría, señales y conexión, integración transaccional en altas demo y pruebas | 26 pruebas focalizadas y 114 totales aprobadas; check y migraciones consistentes |
| 2026-11-01 | T-02-04 | Formulario/vista de perfil, servicios de correo, confirmación, rutas, plantillas y pruebas | 46 pruebas focalizadas y 136 totales aprobadas; consumo concurrente único, check y migraciones consistentes |
| 2026-11-01 | T-02-05 | Backend de personal, vistas/formulario/servicios de claves, rutas/plantillas, auditoría y pruebas | 47 pruebas focalizadas y 159 totales aprobadas; sesiones, tokens y concurrencia verificados; check y migraciones consistentes |
| 2026-11-01 | T-02-06 | Panel Q.F., servicios compartidos, formularios/Admin de cuentas y grupos de solo lectura, plantillas y pruebas | 46 pruebas focalizadas y 183 totales aprobadas; concurrencia, límites, M2M y auditoría verificados |
| 2026-11-01 | T-02-07, avance técnico | Navegación/formularios/CSS, `test_integracion.py`, `tools/verificar_spec_02_http.py`, checks y suite | 24 pruebas focalizadas y 185 totales aprobadas; 21 migraciones en SQLite nueva y flujos HTTP reales aprobados; visual pendiente por acceso al navegador |

## Reanudación

Fase actual: cierre técnico del paso 7 completado, revisión visual pendiente. El usuario autorizó ejecutar los siete pasos en `fdaza` y hacer commit al terminar. Las pruebas, migraciones y flujos HTTP reales están aprobados en bases temporales, con correo en memoria. No se modificó la SQLite local ni se enviaron correos reales.

El host de navegador está indisponible y la revisión automática rechazó vincular una ventana nativa con contenido ajeno al proyecto. Se prepararon vistas sintéticas temporales de solo lectura y se pidió una ventana de Firefox dedicada o aceptar explícitamente cerrar con el límite visual. Esperar esa respuesta para cerrar T-02-07 y hacer el commit final; no realizar un commit intermedio.

## Aceptación del usuario

Aceptación funcional pendiente. El documento está aprobado y la implementación autorizada; ello no implica aceptación del software completo ni de los pasos todavía pendientes.
