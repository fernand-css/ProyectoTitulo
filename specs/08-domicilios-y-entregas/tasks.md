# Tareas — 08 / Domicilios y entregas a domicilio

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-11. Estado: en implementación. Implementación autorizada: sí (ver «Autorización posterior»).

- [x] **T-08-01 — Esquema y regla de elegibilidad.**
  - RF: RF-08-01, RF-08-15.
  - Depende de: aprobación del 08 y autorización de implementación; base 01–07 disponible.
  - Archivos previstos: `entregasapp/models.py`, `entregasapp/migrations/0001_initial.py`, `recetasapp/models.py` (`edad_en`, `requiere_despacho_en`), `turnosapp/services.py` (solo `clasificar_atencion`), `entregasapp/consultas.py` (`es_elegible`), `entregasapp/tests/test_modelos.py`, `test_elegibilidad.py`.
  - Hecho cuando: las seis tablas y sus restricciones se crean en una base desechable; cada restricción tiene su prueba; la elegibilidad cumple los límites de edad, postración y excepción; **las pruebas del 04 pasan sin cambios**; `makemigrations --check` no detecta cambios pendientes.
- [x] **T-08-02 — Domicilios, verificación y excepciones.**
  - RF: RF-08-02, RF-08-03, RF-08-04, RF-08-14.
  - Depende de: T-08-01.
  - Archivos previstos: `entregasapp/services.py`, `entregasapp/consultas.py` (`estado_domicilio`, `elegibles`), `entregasapp/forms.py`, `entregasapp/tests/test_domicilios.py`, `test_excepciones.py` y el escenario 6 de `test_concurrencia.py`.
  - Hecho cuando: crear y editar respetan la versión sin perder ediciones; un cambio de ubicación devuelve el domicilio a pendiente; solo el encargado verifica (la Q.F. y el superusuario se rechazan); una reimportación del 03 con otra dirección deja el aviso derivado sin escribir el domicilio; excepciones con una vigente por paciente; auditoría sin datos personales y rollback si falla.
- [x] **T-08-03 — Fotos privadas.**
  - RF: RF-08-05, RF-08-14.
  - Depende de: T-08-02.
  - Archivos previstos: `requirements.txt` (Pillow), `cesfam/settings.py` (`ARCHIVOS_PRIVADOS_ROOT`), `.gitignore`, `.env.example`, `coreapp/utils/custom_image.py`, `entregasapp/fotos.py`, servicios y vista de foto, `coreapp/tests/test_custom_image.py`, `entregasapp/tests/test_fotos.py`.
  - Hecho cuando: JPEG y PNG válidos se guardan como JPEG sin metadatos (comprobado al releer el archivo); se rechazan archivos que no son imagen, dañados, de más de 5 MB, con demasiados píxeles y la cuarta foto; el borrado y el rollback no dejan archivos huérfanos; la vista exige sesión y rol y responde con `no-store`; no existe ruta pública.
- [x] **T-08-04 — Programación y bloqueo de doble vía.**
  - RF: RF-08-06, RF-08-07, RF-08-15.
  - Depende de: T-08-02.
  - Archivos previstos: `entregasapp/services.py` (`programar_entrega`), `entregasapp/consultas.py` (`recetas_con_despacho_abierto`), `turnosapp/services.py` (`_emitir`), `recetasapp/services.py` (validación en `_registrar_entrega_sin_reintento`), `entregasapp/tests/test_programacion.py`, `test_doble_via.py` y los escenarios 1, 2 y 4 de `test_concurrencia.py`.
  - Hecho cuando: la programación fija solo las recetas elegibles y excluye turnos activos y pendientes de retiro; hay una entrega abierta por paciente aun con solicitudes simultáneas; el tótem responde `despacho_abierto` sin consumir número ni mostrar datos; la confirmación del 03 se rechaza con su motivo y vuelve a funcionar tras anular; **las pruebas del 03, 04, 05 y 07 pasan sin cambiar sus aserciones**.
- [x] **T-08-05 — Registro de resultado y descuento.**
  - RF: RF-08-09, RF-08-10, RF-08-15.
  - Depende de: T-08-04.
  - Archivos previstos: `entregasapp/services.py` (`registrar_entregada`, `registrar_no_entregada`), `recetasapp/services.py` (camino `desde_despacho`), `entregasapp/tests/test_registro.py` y los escenarios 3 y 4 de `test_concurrencia.py`.
  - Hecho cuando: un intento tiene un solo resultado; «entregada» descuenta solo las recetas elegibles en la fecha de la visita y deja las demás «no descontadas» con causa; el cupo nunca se excede; repetir el POST no descuenta otra vez; solo el encargado asignado registra, desde la fecha programada; «no entregada» exige motivo (y nota con «Otro») y deja la entrega pendiente de gestión.
- [x] **T-08-06 — Gestión: reasignar, anular y revisar.**
  - RF: RF-08-11, RF-08-12, RF-08-15.
  - Depende de: T-08-05.
  - Archivos previstos: `entregasapp/services.py` (`reasignar`, `anular_entrega`, `marcar_revisada`), `entregasapp/consultas.py` (`pendientes_gestion`, `no_descontadas`, `programadas`), `entregasapp/tests/test_gestion.py` y el escenario 5 de `test_concurrencia.py`.
  - Hecho cuando: reasignar crea un intento nuevo sin modificar los anteriores y también cierra como «reasignado» un intento pendiente; anular libera las recetas; los filtros por motivo, sector, encargado y fechas devuelven valores exactos con un número constante de consultas; marcar revisada es idempotente; reasignar frente a registrar deja exactamente un ganador.
- [x] **T-08-07 — Pantallas, menú e inicio del encargado.**
  - RF: RF-08-03, RF-08-04, RF-08-05, RF-08-06, RF-08-08, RF-08-11, RF-08-12, RF-08-13, RF-08-14.
  - Depende de: T-08-03 y T-08-06.
  - Archivos previstos: `entregasapp/views.py`, `urls.py`, `forms.py`, `templates/entregas/*.html`, `static/css/entregas.css`, `static/js/entregas/ubicacion.js`, `coreapp/navegacion.py`, `templates/components/iconos.html` (solo si falta un ícono), `coreapp/views.py`, `templates/index.html`, `recetasapp/views.py`, `templates/recetas/paciente_detalle.html`, `entrega_confirmar.html`, `receta_detalle.html`, `entregasapp/tests/test_vistas*.py`, `test_permisos.py`, `coreapp/tests/test_navegacion.py`, `coreapp/tests/test_estaticos.py`, `static/js/entregas/ubicacion.test.cjs`.
  - Hecho cuando: cada URL cumple la matriz en el servidor, exige CSRF en los POST y responde con `no-store`; el menú y las pestañas cambian por perfil; el inicio del encargado abre «Mis entregas»; la ficha del paciente muestra el domicilio; la hoja de estilos cumple las reglas de color del proyecto; las pruebas de Node de la ubicación pasan; la revisión visual, móvil y axe queda registrada como hecha o como pendiente de host.
- [x] **T-08-08 — Integración, medición y documentación.**
  - RF: RF-08-01 a RF-08-15 (regresión).
  - Depende de: T-08-01 a T-08-07.
  - Archivos previstos: `tools/verificar_spec_08_http.py`, `README.md`, `.env.example`, `docs/estructura.md`, `CLAUDE.md`, `specs/08-domicilios-y-entregas/validation.md`, `specs/README.md`.
  - Hecho cuando: la herramienta recorre el ciclo completo por HTTP con SQLite y carpeta privada temporales y 670 pacientes sintéticos, y registra el p95 de cada escenario; la suite completa, las pruebas de Node, `check` y `makemigrations --check --dry-run` pasan; `validation.md` tiene resultados reales y sus límites; el estado no pasa a Implementado sin revisión de navegador, usabilidad y aceptación del usuario.

## Autorización posterior

2026-11-11: el usuario cambió el estado a Aprobado, hizo el commit de los documentos (`6032b7a`) y ejecutó `/spec-impl 08-domicilios-y-entregas` en `crojas-base`, sin rama nueva, con la instrucción «sigue con todos los pasos y coméntame si necesito intervenir». Quedan autorizadas T-08-01 a T-08-08. No autoriza migrar la base PostgreSQL del proyecto ni hacer commits.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-11 | Definición | Cuatro documentos del 08 e índice | Borrador guardado, sin código, migraciones ni dependencias instaladas. |
| 2026-11-11 | Autorización | Estado Aprobado, commit `6032b7a`, `/spec-impl` en `crojas-base` | Autorizadas T-08-01 a T-08-08; base de referencia: 642 pruebas (1 error previo de `test_sala_servidor`). |
| 2026-11-11 | T-08-01 | Modelos, `0001_initial`, `Paciente.edad_en`/`requiere_despacho_en`, `clasificar_atencion`, `consultas.es_elegible` | `test_modelos` (9) y `test_elegibilidad` (6) aprobadas; suite del 04 sin cambios. |
| 2026-11-11 | T-08-02 | `services.py` (domicilios, verificación, excepciones), `consultas.estado_domicilio` | `test_domicilios` (10) y `test_excepciones` (4) aprobadas; escenarios concurrentes 6 y 6b. |
| 2026-11-11 | T-08-03 | Pillow 12.3.0, `ARCHIVOS_PRIVADOS_ROOT`, `custom_image.py`, `fotos.py` | `test_custom_image` (8) y `test_fotos` (6) aprobadas. |
| 2026-11-11 | T-08-04 | `programar_entrega`, bloqueo en `_emitir`, `_registrar_entrega_sin_reintento` y reincorporación del 05 | `test_programacion` (6) y `test_doble_via` (5) aprobadas; escenarios 1, 2 y 4. |
| 2026-11-11 | T-08-05 | `registrar_entregada`, `registrar_no_entregada`, camino `desde_despacho` | `test_registro` (8) aprobadas; escenarios 3 y 4. |
| 2026-11-11 | T-08-06 | `reasignar` (con resultado visto), `anular_entrega`, `marcar_revisada`, consultas con filtros | `test_gestion` (11) aprobadas; escenario 5 (corrigió una carrera real). |
| 2026-11-11 | T-08-07 | Vistas, plantillas, `entregas.css`, `ubicacion.js`, menú, inicio, ficha y recetas | `test_vistas` (16), `test_vistas_encargado` (6), `test_permisos` (8), `test_estructura` (2), Node (5) aprobadas. Revisión visual, axe y teclado: **pendientes** (no se abrió un navegador). |
| 2026-11-11 | T-08-08 | `tools/verificar_spec_08_http.py`, README, `.env.example`, `docs/estructura.md`, `CLAUDE.md`, índice | Herramienta aprobada (p95 máximo 137,71 ms); regresión 755 (754 aprobadas + error previo); Node 75; `check` y `makemigrations --check` sin cambios. |

## Reanudación

Última acción: T-08-01 a T-08-08 completas en `crojas-base`, sin commit. Siguiente paso: revisión del diff por el usuario; aplicar `python manage.py migrate` en la base de demostración cuando el usuario lo decida; revisión de navegador (escritorio y celular, axe, teclado, zoom, ubicación y cámara reales), usabilidad con cinco personas y aceptación funcional. No pasar a Implementado sin esa evidencia.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
