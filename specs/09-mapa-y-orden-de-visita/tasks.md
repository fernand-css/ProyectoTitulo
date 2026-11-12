# Tareas — 09 / Mapa y orden de visita

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-12. Estado: tareas implementadas; revisión de navegador y aceptación pendientes. Implementación autorizada: sí (ver «Autorización posterior»).

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

## Autorización posterior

2026-11-12: el usuario cambió el estado a Aprobado, hizo el commit de los documentos (`5751ec5`) y ejecutó `/spec-impl 09-mapa-y-orden-de-visita` en `crojas-base`, sin rama nueva, con la instrucción «Realiza todos los pasos, interrumpe solo cuando necesites que intervenga en algo. Al final veré los detalles.» Entregó además las coordenadas del CESFAM (−36,4988773; −72,2123601). Quedan autorizadas T-09-01 a T-09-09. No autoriza migrar la base PostgreSQL del proyecto ni hacer commits.

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

## Reanudación

Última acción: T-09-01 a T-09-09 implementadas y verificadas técnicamente (2026-11-12), sin commit. Siguiente paso: revisión del diff por el usuario, revisión de navegador (escritorio y celular, axe, teclado en el mapa, zoom al 200 %, teselas reales y ubicación en contexto seguro), migrar la base de demostración cuando el usuario lo apruebe y aceptación funcional. Bloqueos: ninguno.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar pruebas.
