# Tareas — 08 / Domicilios y entregas a domicilio

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-11; ampliación del 2026-11-13. Estado: en implementación (técnica completa). Implementación autorizada: sí (ver «Autorización posterior»).

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

## Ampliación del 2026-11-13 (aprobada e implementada)

Diseño en [plan.md](plan.md#ampliación-del-2026-11-13-borrador). El usuario aprobó la ampliación (cabecera del spec y commit `6262cfe`) y autorizó T-08-09 a T-08-13 (ver «Autorización posterior»).

- [x] **T-08-09 — Corte de edad de 80 años o más.**
  - RF: RF-08-01 (modificado), RF-08-15.
  - Depende de: aprobación de la ampliación (hecha el 2026-11-13).
  - Archivos previstos: `recetasapp/models.py` (`requiere_despacho_en`), `entregasapp/consultas.py` (`limite_nacimiento`), `turnosapp/services.py` (solo el comentario), textos en `templates/entregas/{programar,programacion,domicilios,domicilio,excepciones}.html` y `templates/recetas/paciente_detalle.html`, `entregasapp/tests/test_elegibilidad.py`, `turnosapp/tests/test_servicios.py`.
  - Hecho cuando: el de 79 años y 364 días no es elegible y recibe preferencial en el tótem; el de 80 es elegible y el tótem lo bloquea con «Consulta tu despacho con el personal»; `condicion_elegible` coincide con `es_elegible` en todas las combinaciones (incluido el 29 de febrero); en el 04 solo cambian las aserciones del límite de edad; ningún texto dice «mayor de 80» para la regla.
- [x] **T-08-10 — Lista de elegibles con filtros (servidor).**
  - RF: RF-08-16, RF-08-14.
  - Depende de: T-08-09.
  - Archivos previstos: `entregasapp/consultas.py` (`elegibles` con `motivo`, `localidad` y sector «sin»; `localidades_elegibles`; `motivos_de`), `entregasapp/forms.py` (`FiltroProgramarForm`), `entregasapp/views.py` (`ProgramarView`, `ProgramarListaView`), `entregasapp/urls.py`, `templates/entregas/programar.html`, `_programar_lista.html`, `entregasapp/tests/test_programar_lista.py`, `test_permisos.py`.
  - Hecho cuando: la página abre con todos los elegibles en páginas de 50; cada filtro y sus combinaciones devuelven exactamente lo esperado; el fragmento por POST y el respaldo `accion=buscar` dan lo mismo; no hay RUT ni nombres en URL; el número de consultas por página es constante; el Técnico recibe 403; `no-store` y CSRF.
- [x] **T-08-11 — Programación por lote (servicio y concurrencia).**
  - RF: RF-08-17, RF-08-06, RF-08-15.
  - Depende de: T-08-09.
  - Archivos previstos: `entregasapp/services.py` (`recetas_para_despacho_lote`, `programar_lote`), `entregasapp/tests/test_programar_lote.py`, escenarios 7 a 10 de `test_concurrencia.py`.
  - Hecho cuando: `recetas_para_despacho_lote` coincide con el cálculo por paciente con consultas constantes; cada paciente se programa en su propia transacción; los omitidos llevan su motivo y no revierten a los demás; reenviar un tramo o el lote completo no duplica; los cuatro escenarios concurrentes pasan tres veces seguidas.
- [x] **T-08-12 — Pantallas de selección, revisión y avance.**
  - RF: RF-08-16, RF-08-17, RF-08-14.
  - Depende de: T-08-10 y T-08-11.
  - Archivos previstos: `entregasapp/views.py` (`ProgramarVariosView`, `ProgramarTramoView`), `entregasapp/urls.py`, `templates/entregas/_programar_resumen.html`, `static/js/entregas/programar.js`, `static/css/entregas.css`, `entregasapp/tests/test_programar_lote.py` (vistas), `entregasapp/tests/programar.test.cjs`, `test_estructura.py`.
  - Hecho cuando: la búsqueda y los filtros actualizan la lista sin recargar (espera y cancelación probadas en Node); la selección sobrevive a cambiar de página y de búsqueda; «Seleccionar los N filtrados» se anula al cambiar un filtro y lo avisa; el resumen muestra programables y omitidos; la firma alterada y un actor distinto se rechazan; los tramos avanzan con `<progress>` y se pueden reintentar; el resultado final informa «Se programaron X de Y»; la hoja de estilos cumple la regla de paleta; la revisión visual, axe y teclado queda como hecha o pendiente de host.
- [x] **T-08-13 — Integración, medición y documentación de la ampliación.**
  - RF: RF-08-01, RF-08-16, RF-08-17 (regresión de RF-08-01 a RF-08-15).
  - Depende de: T-08-09 a T-08-12.
  - Archivos previstos: `tools/verificar_spec_08_http.py`, `specs/04-emision-de-turnos/spec.md` (nota de cambio), `CLAUDE.md`, `README.md`, `docs/estructura.md`, `specs/08-domicilios-y-entregas/validation.md`, `specs/README.md`.
  - Hecho cuando: la herramienta mide la lista, el fragmento, la revisión de 670, los tramos de 25 (p95 ≤ 2 s), el lote completo (tiempo informado) y el tótem durante un lote; la suite completa, Node, `check` y `makemigrations --check --dry-run` (sin cambios) pasan; `validation.md` tiene resultados reales; el spec 04 anota el cambio de edad; el estado no pasa a Implementado sin navegador, usabilidad y aceptación.

## Enmienda del 2026-11-15 (Borrador, tareas propuestas)

Diseño en [plan.md](plan.md#enmienda-del-2026-11-15--diseño-propuesto). Requisitos en [spec.md](spec.md#enmienda-del-2026-11-15-borrador). Las tareas del 09 de la misma enmienda (T-09-10 a T-09-18) están en sus [tareas](../09-mapa-y-orden-de-visita/tasks.md#enmienda-del-2026-11-15-borrador-tareas-propuestas). El lienzo de diseño (T-09-10) incluye el modal de fotos y el visor. Todas esperan la aprobación de la enmienda y la autorización de `/spec-impl`.

- [ ] **T-08-14 — Servicio atómico de fotos.**
  - RF: RF-08-18 (modifica RF-08-05), RF-08-14 y RF-08-15.
  - Depende de: aprobación de la enmienda y autorización de implementación.
  - Archivos previstos: `entregasapp/services.py` (`gestionar_fotos`), `entregasapp/tests/test_fotos.py`, `entregasapp/tests/test_concurrencia.py`.
  - Hecho cuando: los borrados y las fotos nuevas se aplican juntos o no se aplica nada; el error indica el número de la foto; el conjunto cambiado se rechaza; nunca hay más de 3 fotos; los archivos de las borradas se eliminan después de confirmar y los nuevos se eliminan si falla; la auditoría no tiene datos personales; los tres escenarios concurrentes pasan tres veces seguidas.
- [ ] **T-08-15 — Modal de fotos y visor.**
  - RF: RF-08-18 y RF-08-19.
  - Depende de: T-08-14.
  - Archivos previstos: `entregasapp/views.py` (`FotosView`; se retiran `FotoAgregarView` y `FotoEliminarView`), `entregasapp/urls.py`, `entregasapp/forms.py` (`FotosForm`), `templates/entregas/_fotos_boton.html`, `_fotos_modal.html`, `_visor_foto.html`, `fotos.html` (página sin JavaScript), `domicilio.html`, `_tarjeta_intento.html`, `static/js/entregas/fotos.js`, `visor.js`, `static/css/entregas.css`, `fotos.test.cjs`, `visor.test.cjs`, `test_vistas.py`, `test_permisos.py`, `test_estructura.py`.
  - Hecho cuando: el botón dice «Registrar fotos» o «Gestionar fotos» según la cantidad; con 3 solo se borra hasta marcar una; «Sacar foto» usa `capture="environment"`; el error se muestra junto a la foto indicada y el modal sigue abierto; el visor se cierra con la X, con clic fuera y con Esc, y el foco vuelve a la miniatura; sin JavaScript funcionan la página aparte y el enlace a la imagen; el Técnico solo ve; la revisión visual, axe y teclado queda como hecha o pendiente de host.
- [ ] **T-08-16 — Textos «Detalles del domicilio» y «Nombre de la localidad».**
  - RF: RF-08-20.
  - Depende de: aprobación de la enmienda (se puede hacer junto con T-09-13).
  - Archivos previstos: `templates/entregas/_tarjeta_intento.html`, `ir_a.html`, `domicilios.html`, `domicilio.html`, `templates/recetas/paciente_detalle.html`, `static/js/entregas/mapa.js`, `entregasapp/forms.py`, pruebas que buscan esos textos.
  - Hecho cuando: no queda «Ver domicilio» en plantillas ni en JavaScript; el formulario, la ficha y el filtro dicen «Nombre de la localidad»; `makemigrations --check` no detecta cambios.

## Autorización posterior

2026-11-11: el usuario cambió el estado a Aprobado, hizo el commit de los documentos (`6032b7a`) y ejecutó `/spec-impl 08-domicilios-y-entregas` en `crojas-base`, sin rama nueva, con la instrucción «sigue con todos los pasos y coméntame si necesito intervenir». Quedan autorizadas T-08-01 a T-08-08. No autoriza migrar la base PostgreSQL del proyecto ni hacer commits.

2026-11-13: el usuario aprobó la ampliación en la cabecera del spec, hizo el commit de los documentos (`6262cfe`) y volvió a ejecutar `/spec-impl 08-domicilios-y-entregas` en `crojas-base`, sin rama nueva. Eligió «todos los pasos seguidos» y revisar el diff al final. Quedan autorizadas T-08-09 a T-08-13. No autoriza commits ni migrar la base del proyecto (la ampliación no trae migraciones).

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
| 2026-11-13 | Ampliación (definición) | `spec.md`, `plan.md`, `tasks.md`, `validation.md` del 08 e índice | Borrador de RF-08-01 (80 o más), RF-08-16 y RF-08-17 con T-08-09 a T-08-13 propuestas; sin código ni migraciones. |
| 2026-11-13 | Autorización | Ampliación en Aprobado, commit `6262cfe`, `/spec-impl` en `crojas-base` | Autorizadas T-08-09 a T-08-13; base de referencia: 834 pruebas (1 error previo de `test_sala_servidor`). |
| 2026-11-13 | T-08-09 | `requiere_despacho_en` (`>= 80`), `limite_nacimiento`, comentario de `clasificar_atencion`, textos de 7 plantillas | `test_elegibilidad` (7) y suite del 04 aprobadas; solo cambió la tupla de 80 en `test_servicios.py`. |
| 2026-11-13 | T-08-10 | `consultas.elegibles` (motivo, localidad, «sin»), `localidades_elegibles`, `motivos_de`, `FiltroProgramarForm`, `ProgramarListaView`, `programar.html`, `_programar_lista.html` | `test_programar_lista` (15) aprobadas. |
| 2026-11-13 | T-08-11 | `recetas_para_despacho_lote`, `programar_lote`, códigos `no_elegible`/`sin_recetas` | Pruebas de servicio de `test_programar_lote` y escenarios concurrentes 7 a 10, aprobados en 3 corridas. |
| 2026-11-13 | T-08-12 | `ProgramarVariosView`, `ProgramarTramoView`, `programar_varios.html`, `_programar_resumen.html`, `programar.js`, `entregas.css` | `test_programar_lote` (16), `test_estructura` (3) y `programar.test.cjs` (11) aprobadas. Revisión visual, axe y teclado: **pendientes** (no se abrió un navegador). |
| 2026-11-13 | T-08-13 | Herramienta HTTP, nota en el spec 04, CLAUDE.md, README, `docs/estructura.md`, `plan.md`, `validation.md`, índice | Herramienta aprobada (tramo de 25 con p95 de 845,89 ms; lote de 620 en 17,25 s); regresión de 871 pruebas aprobadas; Node 101; `check` y `makemigrations --check` sin cambios. |
| 2026-11-15 | Enmienda (definición) | `spec.md`, `plan.md`, `tasks.md`, `validation.md` del 08 y el 09 e índice | Borrador de RF-08-18 a RF-08-20 con T-08-14 a T-08-16 propuestas; sin código ni migraciones. |

## Reanudación

Última acción: T-08-01 a T-08-13 completas en `crojas-base` (ampliación del 2026-11-13 incluida), sin commit. Siguiente paso: revisión del diff por el usuario; aplicar `python manage.py migrate` en la base de demostración cuando el usuario lo decida; revisión de navegador (escritorio y celular, axe, teclado, zoom, ubicación y cámara reales), usabilidad con cinco personas y aceptación funcional. No pasar a Implementado sin esa evidencia.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
