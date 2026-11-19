# Tareas — 09 / Mapa y orden de visita

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-12. Estado: tareas implementadas, incluida la enmienda del 2026-11-15 (T-09-11 a T-09-18, el 2026-11-16); revisión de navegador y aceptación pendientes. Implementación autorizada: sí (ver «Autorización posterior»).

- [x] **T-09-01 — Algoritmo de orden (puro).**
  - RF: RF-09-02, RF-09-05.
  - Depende de: aprobación del 09 y autorización de implementación; base 01–08 disponible.
  - Archivos previstos: `entregasapp/ruta.py`, `entregasapp/tests/test_ruta.py`.
  - Hecho cuando:
    - las distancias haversine coinciden con valores conocidos;
    - el vecino más cercano y el 2-opt con extremos fijos son deterministas, nunca empeoran al vecino más cercano y coinciden con la fuerza bruta en los casos construidos;
    - la inserción más barata elige el índice correcto;
    - el límite de 200 paradas se respeta;
    - el módulo no importa Django.
- [x] **T-09-02 — Configuración del mapa y Leaflet local.**
  - RF: RF-09-12, RF-09-14.
  - Depende de: T-09-01.
  - Archivos previstos: `cesfam/settings.py`, `.env.example`, `entregasapp/checks.py`, `entregasapp/apps.py`, `static/vendor/leaflet/` (Leaflet 1.9.4 y su licencia), `entregasapp/tests/test_configuracion_mapa.py`, `coreapp/tests/test_estaticos.py`.
  - Hecho cuando:
    - las variables tienen los valores de demostración por defecto;
    - `check` informa `entregasapp.E001`, `E002` y `E003` con valores no válidos;
    - Leaflet se sirve localmente y una prueba verifica su versión y su licencia;
    - ninguna plantilla carga recursos desde un CDN.
- [x] **T-09-03 — Modelo del orden manual.**
  - RF: RF-09-04, RF-09-15.
  - Depende de: T-09-01.
  - Archivos previstos: `entregasapp/models.py` (`OrdenRuta`, `ParadaRuta`), `entregasapp/migrations/0002_ordenruta.py`, `entregasapp/tests/test_modelos.py`.
  - Hecho cuando:
    - las dos tablas y sus restricciones (`orden_ruta_unico`, intento único y posición única por orden, posición ≥ 1) se crean en una base desechable y cada una tiene su prueba;
    - `makemigrations --check` no detecta cambios pendientes;
    - las pruebas de migración del 04, del 05 y del 08 siguen pasando.
- [x] **T-09-04 — Ruta del día (consulta).**
  - RF: RF-09-01, RF-09-02, RF-09-03, RF-09-05, RF-09-07, RF-09-10.
  - Depende de: T-09-01 y T-09-03.
  - Archivos previstos: `entregasapp/consultas.py` (`ruta_del_dia`, `partida_del_dia`, `registradas_hoy`), `entregasapp/mapa.py`, `entregasapp/tests/test_ruta_consultas.py`.
  - Hecho cuando:
    - la ruta incluye solo los intentos pendientes del encargado (hoy y atrasados, o la fecha futura);
    - parte de la última visita registrada con coordenadas;
    - aparta las visitas sin coordenadas en el modo sugerido;
    - cruza el orden manual con la ruta vigente e inserta las nuevas con su rótulo;
    - muestra solo las registradas de hoy;
    - los datos del mapa no traen RUT, teléfono, notas ni fotos;
    - el número de consultas es constante.
- [x] **T-09-05 — Servicios del orden manual.**
  - RF: RF-09-04, RF-09-06, RF-09-14, RF-09-15.
  - Depende de: T-09-04.
  - Archivos previstos: `entregasapp/services.py` (`mover_parada`, `restablecer_orden`), `entregasapp/tests/test_orden_manual.py`, `entregasapp/tests/test_concurrencia_ruta.py`.
  - Hecho cuando:
    - subir, bajar y mover a una posición guardan el orden completo;
    - los bordes inválidos se rechazan con texto;
    - el mismo `operacion_id` no mueve dos veces;
    - dos ediciones desde la misma versión dejan una ganadora y el aviso;
    - restablecer vuelve a la sugerencia;
    - solo el encargado (comprobación exacta) puede reordenar;
    - la auditoría no tiene datos personales y una falla revierte la operación;
    - los tres escenarios concurrentes pasan tres veces seguidas.
- [x] **T-09-06 — Pantallas del encargado: lista, mapa e «Ir a esta parada».**
  - RF: RF-09-01 a RF-09-09, RF-09-14.
  - Depende de: T-09-02 y T-09-05.
  - Archivos previstos: `entregasapp/views.py`, `entregasapp/urls.py`, `entregasapp/forms.py`, `templates/entregas/mis_entregas.html`, `_tarjeta_intento.html`, `mapa.html`, `_mapa.html`, `ir_a.html`, `static/js/entregas/mapa.js`, `ir_a.js`, `static/css/entregas.css`, `coreapp/navegacion.py`, `entregasapp/tests/test_vistas_mapa.py`, `test_permisos_mapa.py`, `mapa.test.cjs`, `ir_a.test.cjs`, `coreapp/tests/test_navegacion.py`.
  - Hecho cuando:
    - «Mis entregas» muestra las paradas numeradas, las visitas sin coordenadas, las registradas hoy y las próximas, con los controles de orden;
    - el mapa trae los mismos números, la línea punteada, el total, la atribución, el aviso si fallan las teselas y `referrerPolicy` de solo origen;
    - «Ir a esta parada» sigue la posición solo en el navegador, sin solicitudes de red, y la detiene;
    - cada URL cumple la matriz, exige CSRF en los POST y responde `no-store`;
    - las pruebas de Node pasan;
    - las pruebas del 08 afectadas quedan ajustadas y listadas en `plan.md`;
    - la revisión visual, móvil y axe queda registrada como hecha o como pendiente de host.
- [x] **T-09-07 — «Rutas» de la Q.F. y mapa del domicilio.**
  - RF: RF-09-10, RF-09-11, RF-09-14.
  - Depende de: T-09-06.
  - Archivos previstos: `entregasapp/views.py` (`RutasView`, contexto de `DomicilioView`), `entregasapp/forms.py` (`RutaForm`), `templates/entregas/rutas.html`, `_mapa_punto.html`, `domicilio.html`, pruebas en `test_vistas_mapa.py` y `test_permisos_mapa.py`.
  - Hecho cuando:
    - la Q.F. y el superusuario consultan la ruta de un encargado para hoy (igual a la que él ve) o para una fecha futura (sugerida desde el CESFAM), sin acciones;
    - una fecha pasada o un encargado no válido se rechazan con texto;
    - el Técnico y el encargado no acceden;
    - el domicilio con coordenadas muestra su mapa pequeño, y sin coordenadas, el texto.
- [x] **T-09-08 — Comando de domicilios de demostración.**
  - RF: RF-09-13.
  - Depende de: T-09-02.
  - Archivos previstos: `entregasapp/management/__init__.py`, `entregasapp/management/commands/__init__.py`, `generar_domicilios_demo.py`, `entregasapp/tests/test_generar_domicilios_demo.py`.
  - Hecho cuando:
    - sin `--aplicar` no escribe nada;
    - con `--aplicar` y una cuenta Q.F. o superusuario crea, mediante `guardar_domicilio`, domicilios sintéticos reproducibles dentro del radio, sin verificar y auditados, solo para elegibles sin domicilio;
    - una cuenta sin permiso se rechaza.
- [x] **T-09-09 — Integración, medición y documentación.**
  - RF: RF-09-01 a RF-09-15 (regresión).
  - Depende de: T-09-01 a T-09-08.
  - Archivos previstos: `tools/verificar_spec_09_http.py`, `README.md`, `.env.example`, `docs/estructura.md`, `CLAUDE.md`, `specs/09-mapa-y-orden-de-visita/validation.md`, `specs/README.md`.
  - Hecho cuando:
    - la herramienta recorre la ruta por HTTP con una SQLite temporal, 670 pacientes sintéticos y 4 encargados con unas 50 visitas, y registra el p95 de cada escenario y el tiempo del cálculo con 200 paradas;
    - la suite completa, las pruebas de Node, `check` y `makemigrations --check --dry-run` pasan;
    - `validation.md` tiene resultados reales y sus límites;
    - el estado no pasa a Implementado sin revisión de navegador, usabilidad y aceptación del usuario.

## Enmienda del 2026-11-15 (aprobada; tareas implementadas el 2026-11-16)

Diseño en [plan.md](plan.md#enmienda-del-2026-11-15--diseño-propuesto). Requisitos en [spec.md](spec.md#enmienda-del-2026-11-15-borrador). Las tareas del 08 de la misma enmienda (T-08-14 a T-08-16: fotos, visor y textos) están en sus [tareas](../08-domicilios-y-entregas/tasks.md#enmienda-del-2026-11-15-borrador-tareas-propuestas). Solo T-09-10 se hace antes de aprobar, por decisión del usuario; las demás esperan la aprobación y la autorización de `/spec-impl`.

- [x] **T-09-10 — Lienzo de diseño (previo a la aprobación).** *(Hecha el 2026-11-15; el usuario la revisó y aprobó.)*
  - RF: RF-09-16 a RF-09-18, RF-09-21, RF-09-22, RF-09-24, RF-09-25 y RF-08-18 a RF-08-20.
  - Depende de: borrador de la enmienda guardado.
  - Archivos previstos: ninguno del repositorio. Es un lienzo de Claude Design (artefacto privado), con la paleta y la tipografía de `static/css/` y solo datos sintéticos.
  - Hecho cuando: el lienzo muestra, en celular y computador, «Mis entregas» con tarjetas compactas y expandidas, el modal de fotos (también con el error «La foto 2 no se pudo procesar»), el visor de imagen, el «Mapa» con el tramo y la sugerencia, «Rutas» de la Q.F. y «Registrar domicilio» con «Usar mapa»; el usuario lo revisó.
- [x] **T-09-11 — Cliente de OSRM y configuración.**
  - RF: RF-09-19.
  - Depende de: aprobación de la enmienda y autorización de implementación.
  - Archivos previstos: `entregasapp/osrm.py`, `cesfam/settings.py`, `.env.example`, `entregasapp/checks.py`, `entregasapp/tests/test_osrm.py`, `entregasapp/tests/test_configuracion_mapa.py`.
  - Hecho cuando: las consultas de tabla y de ruta usan `longitud,latitud`, sin proxy y con el tiempo de espera; los errores (tiempo, red, código, JSON y distancia nula) dan `OsrmNoDisponible` sin coordenadas en el mensaje; `check` informa `E004` y `E005`; la URL vacía desactiva el servicio; ninguna prueba necesita un OSRM real.
- [x] **T-09-12 — Orden y total por camino.**
  - RF: RF-09-20 (modifica RF-09-02 y RF-09-05).
  - Depende de: T-09-11.
  - Archivos previstos: `entregasapp/ruta.py`, `entregasapp/consultas.py`, `entregasapp/tests/test_ruta.py`, `entregasapp/tests/test_ruta_consultas.py`.
  - Hecho cuando: el 2-opt con matriz asimétrica coincide con la fuerza bruta; el orden y las «Nuevas» siguen la matriz; el total es por camino; con OSRM caído, el orden en línea recta va rotulado y sin total; el orden manual no cambia; la matriz se guarda en caché sin la posición; `ruta.py` sigue sin importar Django; la cantidad de consultas a la base no cambia.
- [x] **T-09-13 — Tarjetas compactas, flechas y arrastre.**
  - RF: RF-09-16, RF-09-17 (modifica RF-09-04) y RF-09-18.
  - Depende de: T-09-12 y T-08-15 (botón de fotos y visor).
  - Archivos previstos: `templates/entregas/_tarjeta_intento.html`, `_orden_controles.html`, `_ruta.html`, `_ruta_rotulo.html`, `mis_entregas.html`, `entregasapp/views.py` (`MoverParadaView` con JSON), `static/js/entregas/tarjetas.js`, `orden.js`, `static/css/entregas.css`, `entregasapp/tests/test_vistas_mapa.py`, `tarjetas.test.cjs`, `orden.test.cjs`.
  - Hecho cuando: las tarjetas abren compactas con número, rótulos, nombre, dirección y los tres botones; se expanden varias con `aria-expanded`; el mapa pequeño se carga solo al expandir y dice «Domicilio sin coordenadas» cuando corresponde; las flechas funcionan con y sin JavaScript; el arrastre se prueba en Node (toque largo, hueco, desplazamiento, Esc, reversión al fallar y anuncio); «Mover a la posición» ya no existe; solo el encargado ve los controles.
- [x] **T-09-14 — «Mapa»: sin línea, con tramo y sugerencia.**
  - RF: RF-09-21, RF-09-22 y RF-09-26.
  - Depende de: T-09-12.
  - Archivos previstos: `entregasapp/views.py` (`TramoView`, `ParadaCercanaView`), `entregasapp/urls.py`, `entregasapp/mapa.py`, `templates/entregas/_mapa.html`, `mapa.html`, `static/js/entregas/tramo.js`, `mapa.js`, `entregasapp/tests/test_tramo.py`, `tramo.test.cjs`, `mapa.test.cjs`, `coreapp/navegacion.py` (páginas activas).
  - Hecho cuando: no queda la línea del recorrido completo; el tramo se dibuja hasta la próxima parada o la elegida y se recalcula con los umbrales; la sugerencia elige por camino y mueve a la posición 1 al confirmar; sin permiso, sin señal o sin OSRM solo hay marcadores y el aviso; el destino se toma de la base; el límite de solicitudes responde 429; la posición no queda en la base, la auditoría, la sesión, la caché ni los registros; respuestas `no-store`.
- [x] **T-09-15 — «Ir a esta parada» por camino.**
  - RF: RF-09-23 (reemplaza RF-09-09 en lo que se le oponga).
  - Depende de: T-09-14.
  - Archivos previstos: `templates/entregas/ir_a.html`, `static/js/entregas/ir_a.js`, `entregasapp/mapa.py` (`datos_ir_a`), `entregasapp/tests/ir_a.test.cjs`, `test_vistas_mapa.py`.
  - Hecho cuando: la distancia es la del tramo por camino; no hay línea recta ni rumbo; el aviso de 100 m usa la distancia por camino; sin OSRM, sin permiso o sin posición quedan el texto, el enlace y las coordenadas; las únicas solicitudes de red van a la ruta del tramo de Django.
- [x] **T-09-16 — «Rutas» de la Q.F.**
  - RF: RF-09-24 (modifica RF-09-10).
  - Depende de: T-09-13 y T-09-14.
  - Archivos previstos: `templates/entregas/rutas.html`, `entregasapp/views.py` (`RutasView`), `entregasapp/mapa.py`, `test_vistas_mapa.py`, `test_permisos_mapa.py`.
  - Hecho cuando: tarjetas compactas expandibles sin acciones de cambio; el mapa solo tiene marcadores, sin línea ni tramo, y sus datos no traen posición ni RUT; el orden y el total siguen el RF-09-20.
- [x] **T-09-17 — «Usar mapa» en el domicilio.**
  - RF: RF-09-25.
  - Depende de: T-09-11 (solo la configuración del origen ya existente) y T-08-16 (etiqueta «Nombre de la localidad» en el mismo formulario).
  - Archivos previstos: `templates/entregas/domicilio.html`, `_dialogo_usar_mapa.html`, `static/js/entregas/usar_mapa.js`, `static/css/entregas.css`, `entregasapp/tests/usar_mapa.test.cjs`, `test_vistas_mapa.py`.
  - Hecho cuando: abre en el punto del formulario o en el CESFAM; marca con clic, con toque y con «Marcar el centro del mapa»; «Usar este punto» copia 6 decimales y vacía la precisión; «Cancelar», Esc y la X no cambian nada; el foco vuelve al botón; sin JavaScript no aparece el botón; guardar deja el domicilio pendiente de verificar.
- [x] **T-09-18 — Integración, medición y documentación.**
  - RF: RF-09-16 a RF-09-26 (regresión de RF-09-01 a RF-09-15 y de la enmienda del 08).
  - Depende de: T-09-11 a T-09-17 y T-08-14 a T-08-16.
  - Archivos previstos: `tools/verificar_spec_09_http.py` (OSRM simulado y opción `--osrm-real`), `README.md` (sección «Servidor de rutas (OSRM)»), `docs/estructura.md` (esquema del despliegue), `.env.example`, `CLAUDE.md`, `specs/09-mapa-y-orden-de-visita/validation.md`, `specs/README.md`.
  - Hecho cuando: la herramienta mide el p95 de «Mis entregas», «Mapa», «Rutas», el tramo y la parada más cercana con el OSRM simulado, y la matriz de 52 y 202 puntos y un tramo con el OSRM local; `docker logs osrm` no muestra solicitudes tras pedir un tramo; el README explica el recorte con osmium en WSL, los tres pasos de preparación, el contenedor (`--algorithm mld`, `--max-table-size 300`, `--verbosity WARNING`, solo en `127.0.0.1:5000`), la actualización y una consulta de prueba; la suite completa, Node, `check` y `makemigrations --check --dry-run` (sin cambios) pasan; las pruebas ajustadas del 08 y el 09 quedan listadas en `plan.md`; el estado no pasa a Implementado sin navegador, usabilidad y aceptación.

## Autorización posterior

2026-11-12: el usuario cambió el estado a Aprobado, hizo el commit de los documentos (`5751ec5`) y ejecutó `/spec-impl 09-mapa-y-orden-de-visita` en `crojas-base`, sin rama nueva, con la instrucción «Realiza todos los pasos, interrumpe solo cuando necesites que intervenga en algo. Al final veré los detalles.» Entregó además las coordenadas del CESFAM (−36,4988773; −72,2123601). Quedan autorizadas T-09-01 a T-09-09. No autoriza migrar la base PostgreSQL del proyecto ni hacer commits.

2026-11-16: con la enmienda aprobada y las tareas del 08 (T-08-14 a T-08-16) en el commit `72208b8`, el usuario ejecutó `/spec-impl 09-mapa-y-orden-de-visita` en `crojas-base` (sin rama nueva, acuerdo vigente del 08 y el 09) y eligió «Todos seguidos». Quedan autorizadas T-09-11 a T-09-18. No autoriza commits, migrar la base del proyecto ni tocar el contenedor de OSRM.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-12 | Definición | Cuatro documentos del 09 e índice | Borrador guardado, sin código, migraciones ni dependencias. |
| 2026-11-12 | Línea base | `python manage.py test --noinput --parallel 1` sobre `5751ec5` | 755 pruebas: 754 aprobadas y el error previo de `test_sala_servidor` (`WinError 32`). |
| 2026-11-12 | T-09-01 | `entregasapp/ruta.py`, `tests/test_ruta.py` | 17 pruebas aprobadas sin base; 200 paradas en decenas de milisegundos. |
| 2026-11-12 | T-09-02 | `cesfam/settings.py`, `.env.example`, `entregasapp/checks.py`, `apps.py`, `static/vendor/leaflet/` (npm `leaflet@1.9.4`), `tests/test_configuracion_mapa.py`, `coreapp/tests/test_estaticos.py` | 7 pruebas de configuración y la de Leaflet local aprobadas; `check` sin problemas con los valores por defecto. |
| 2026-11-12 | T-09-03 | `models.py` (`OrdenRuta`, `ParadaRuta`), `migrations/0002_ordenruta.py`, `tests/test_modelos.py` | 3 pruebas nuevas de restricciones; pruebas de migración del 03 al 05 aprobadas; `makemigrations --check` sin cambios. |
| 2026-11-12 | T-09-04 | `consultas.py` (`ruta_del_dia`, `partida_del_dia`, `registradas_hoy`, `orden_guardado`), `mapa.py`, `tests/test_ruta_consultas.py`, `tests/ayudas.py` | 12 pruebas aprobadas, incluida la cantidad constante de consultas. |
| 2026-11-12 | T-09-05 | `services.py` (`mover_parada`, `restablecer_orden`), `tests/test_orden_manual.py`, `tests/test_concurrencia_ruta.py` | 10 pruebas de servicio; los 3 escenarios concurrentes aprobados en 3 corridas seguidas. |
| 2026-11-12 | T-09-06 | Vistas, formularios, URL, plantillas, `mapa.js`, `ir_a.js`, `entregas.css`, `navegacion.py`, íconos; `tests/test_vistas_mapa.py`, `test_permisos_mapa.py`, `mapa.test.cjs`, `ir_a.test.cjs`, `coreapp/tests/test_navegacion.py` | Pruebas de vistas, permisos, estructura y Node aprobadas; una prueba del 08 ajustada (ver `plan.md`). Revisión de navegador, móvil y axe: pendiente (no se ejecutó en este host). |
| 2026-11-12 | T-09-07 | `RutasView`, `RutaForm`, `rutas.html`, `_mapa_punto.html`, `domicilio.html` | Cubierto por `test_vistas_mapa.py` (`RutasTests`, `MapaDomicilioTests`) y `test_permisos_mapa.py`. |
| 2026-11-12 | T-09-08 | `management/commands/generar_domicilios_demo.py`, `tests/test_generar_domicilios_demo.py` | 4 pruebas aprobadas. |
| 2026-11-12 | T-09-09 | `tools/verificar_spec_09_http.py`, `README.md`, `.env.example`, `docs/estructura.md`, `CLAUDE.md`, `validation.md`, `specs/README.md` | Herramienta HTTP aprobada (p95 máximo 515,67 ms); suite completa: 834 pruebas, 833 aprobadas y el error previo de `test_sala_servidor`; 90 pruebas de Node aprobadas. |
| 2026-11-15 | Enmienda (definición) | `spec.md`, `plan.md`, `tasks.md`, `validation.md` del 08 y el 09 e índice | Borrador de RF-09-16 a RF-09-26 con T-09-10 a T-09-18 propuestas; sin código ni migraciones. |
| 2026-11-15 | T-09-10 (lienzo) | Lienzo privado de Claude Design: <https://claude.ai/artifact/PtUciJRaCWTAunW2pJTwN1> | 12 pantallas en celular y computador con datos sintéticos y el mapa base dibujado a mano. El usuario lo revisó y aprobó la enmienda el mismo día. |
| 2026-11-15 | Aprobación | Cabeceras del 08 y el 09 e índice | Enmienda aprobada; T-08-14 a T-08-16 y T-09-11 a T-09-18 esperan `/spec-impl` (primero el 08). |
| 2026-11-16 | T-09-11 | `entregasapp/osrm.py`, `cesfam/settings.py` (`OSRM_URL`, `OSRM_TIEMPO_ESPERA`, `TEST_RUNNER`), `coreapp/ejecutor_pruebas.py`, `.env.example`, `checks.py` (E004, E005), `tests/osrm_simulado.py`, `test_osrm.py`, `test_configuracion_mapa.py` | 11 pruebas del cliente y 6 de configuración aprobadas, contra un OSRM simulado. |
| 2026-11-16 | T-09-12 | `ruta.py` (función de distancia, 2-opt asimétrico, `formatear_distancia`), `consultas.py` (`distancia_por_camino`, `RutaDelDia.distancia`) | `test_ruta.py` 21 y `test_ruta_consultas.py` 18 aprobadas. |
| 2026-11-16 | T-09-13 | `_tarjeta_intento.html`, `_orden_controles.html`, `_ruta.html`, `_ruta_rotulo.html`, `_ruta_resumen.html`, `mis_entregas.html`, `MoverParadaView` (JSON), `tarjetas.js`, `orden.js`, `entregas.css`, `tests/dom_simulado.cjs` | Vistas y Node (`tarjetas` 6, `orden` 13) aprobadas. |
| 2026-11-16 | T-09-14 | `TramoView`, `ParadaCercanaView`, rutas `tramo` y `cercana`, `mapa.py`, `_mapa.html`, `mapa.html`, `tramo.js`, `mapa.js`, `navegacion.py` | `test_tramo.py` 11, `tramo.test.cjs` 9 y `mapa.test.cjs` 16 aprobadas. |
| 2026-11-16 | T-09-15 | `ir_a.html`, `ir_a.js`, `mapa.py` (`datos_ir_a`) | `ir_a.test.cjs` 6 aprobadas. |
| 2026-11-16 | T-09-16 | `rutas.html`, `RutasView` | `RutasTests` aprobadas. |
| 2026-11-16 | T-09-17 | `domicilio.html`, `_dialogo_usar_mapa.html`, `usar_mapa.js`, `mapa.py` (`datos_usar_mapa`), `entregas.css` | `usar_mapa.test.cjs` 7 y `UsarMapaTests` 2 aprobadas. |
| 2026-11-16 | T-09-18 | `tools/verificar_spec_09_http.py`, `README.md` (sección OSRM), `docs/estructura.md`, `CLAUDE.md`, `spec.md`, `plan.md`, `validation.md`, `specs/README.md` | Suite: 1013 pruebas, 1012 aprobadas y el error previo de `test_sala_servidor`; Node 166; `check` y `makemigrations --check` sin cambios; herramienta HTTP aprobada (p95 máximo 523,63 ms) y OSRM real medido; `docker logs osrm` sin solicitudes. |
| 2026-11-16 | Revisión de navegador | Navegador integrado con SQLite temporal y datos sintéticos; `mis_entregas.html`, `entregas.css`, `osrm.py`, `mapa.js`, `usar_mapa.js`, `_mapa.html`, `test_osrm.py`, `test_ruta_consultas.py`, `mapa.test.cjs` | 8 defectos corregidos (ver `validation.md`); 413 pruebas de `entregasapp` y `coreapp`, 167 de Node y herramienta HTTP con OSRM real aprobadas. Celular real, axe y usabilidad pendientes. |

## Reanudación

Última acción: T-09-11 a T-09-18 (enmienda del 2026-11-15) implementadas y verificadas técnicamente el 2026-11-16, más una revisión en el navegador integrado con 8 defectos corregidos; guardadas en el commit `4b68242` de `crojas-base`. Siguiente paso: revisión en un celular real (tarjetas, arrastre con el dedo, tramo y «Sugerir parada más cercana» con ubicación real en contexto seguro, «Usar mapa», axe, teclado, zoom al 200 % y 320 px); usabilidad con cinco personas y aceptación funcional. Bloqueos: ninguno.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
