# Tareas — 11 / Reparto sin conexión

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Validación: [validation.md](validation.md).
Estado: en ejecución. Implementación autorizada el 2026-11-18 (`/spec-impl 11-reparto-sin-conexion`).

- [x] T-11-01 — Hora del registro y llegada en el servidor.
  - RF: RF-11-08, RF-11-15.
  - Depende de: ninguna.
  - Archivos previstos: `entregasapp/models.py`, `entregasapp/migrations/0007_intentoentrega_sincronizado_en.py`, `entregasapp/services.py` (`_hora_del_registro`, parámetro `registrado_en`), `templates/entregas/detalle.html`, `pendientes.html`, `_tarjeta_intento.html`, `entregasapp/tests/test_sin_conexion_hora.py`.
  - Hecho cuando: los límites, el cruce de medianoche y la evaluación a la fecha del registro (y a la de preparación) pasan sus pruebas; sin el parámetro, la suite del 08 y del 13 sigue en verde; `makemigrations --check` limpio.
- [x] T-11-02 — Avisos tardíos.
  - RF: RF-11-12.
  - Depende de: T-11-01.
  - Archivos previstos: `entregasapp/notificaciones.py`, `entregasapp/tests/test_avisos_resultado.py`.
  - Hecho cuando: vigencia desde el registro y `registro_tardio` probados; avisos del 12 sin cambios para registros con señal.
- [x] T-11-03 — Paquete de la ruta.
  - RF: RF-11-02.
  - Depende de: ninguna.
  - Archivos previstos: `entregasapp/sin_conexion.py`, `entregasapp/views.py` (`PaqueteView`), `entregasapp/urls.py`, `entregasapp/tests/test_sin_conexion_paquete.py`.
  - Hecho cuando: contenido, orden, campos prohibidos y permisos probados; respuesta `no-store`.
- [x] T-11-04 — Sincronización en el servidor.
  - RF: RF-11-06, RF-11-07, RF-11-09, RF-11-11.
  - Depende de: T-11-01, T-11-02.
  - Archivos previstos: `entregasapp/sin_conexion.py` (`sincronizar`, `Rechazo`), `entregasapp/views.py` (`SincronizarView`), `entregasapp/urls.py`, `entregasapp/tests/test_sin_conexion_sincronizar.py`.
  - Hecho cuando: lote mixto, `ya_aplicado`, cada código de rechazo, 400/413/403, auditoría sin nota y límite de solicitudes probados.
- [x] T-11-05 — Pruebas concurrentes.
  - RF: RF-11-07, RF-11-09.
  - Depende de: T-11-04.
  - Archivos previstos: `entregasapp/tests/test_concurrencia_sin_conexion.py`.
  - Hecho cuando: tres escenarios con `TransactionTestCase` e hilos (lote duplicado, frente a reasignar, frente a anular) en verde, sin descuentos dobles.
- [x] T-11-06 — Service worker y página sin conexión.
  - RF: RF-11-01, RF-11-04.
  - Depende de: T-11-03.
  - Archivos previstos: `templates/pwa/sw.js`, `coreapp/views.py`, `entregasapp/views.py` (`SinConexionView`), `templates/entregas/sin_conexion.html`, `coreapp/tests/test_estaticos.py`.
  - Hecho cuando: la plantilla del SW lista solo estáticos y la página sin conexión, versiona la caché, borra las anteriores y no intercepta JSON, POST, `/turnos/` ni el WebSocket; pruebas actualizadas en verde.
- [x] T-11-07 — Almacén, cola y sincronización en el cliente.
  - RF: RF-11-03, RF-11-05, RF-11-06, RF-11-10, RF-11-11, RF-11-13, RF-11-16.
  - Depende de: T-11-04, T-11-06.
  - Archivos previstos: `static/js/entregas/almacen.js`, `sincronizar.js`, `sin_conexion.js`, `templates/entregas/mis_entregas.html`, `registro.html`, `static/css/entregas.css`, `entregasapp/tests/almacen.test.cjs`, `sincronizar.test.cjs`, `sin_conexion.test.cjs`.
  - Hecho cuando: las pruebas de Node cubren paquete por cuenta y fecha, cola, validación del 08, deshacer, lotes, reintento, rechazos, `aria-live` y que con señal no se use la cola.
- [x] T-11-08 — Salida con pendientes.
  - RF: RF-11-03, RF-11-14.
  - Depende de: T-11-07.
  - Archivos previstos: `static/js/pwa.js`, `templates/components/navbar.html`, `dock.html`, `entregasapp/tests/pwa.test.cjs`.
  - Hecho cuando: aviso con la cifra, borrado del paquete, cola conservada por cuenta y borrada a los 2 días, probados en Node.
- [x] T-11-09 — Medición HTTP aislada, validación y documentación.
  - RF: todos; NS05, RNF-05.
  - Depende de: T-11-01 a T-11-08.
  - Archivos previstos: `tools/verificar_spec_11_http.py`, `validation.md`, `specs/README.md`, `docs/estructura.md`, `README.md`, `CLAUDE.md`, notas en los specs 08, 09 y 12.
  - Hecho cuando: 100 registros sincronizados en 5 min o menos con 0 duplicados, p95 ≤ 2 s, suite completa y resultados reales anotados en `validation.md`; navegador, celular real, axe, usabilidad y aceptación anotados como pendientes si no se pudieron hacer.

## Autorización posterior

2026-11-18: la usuaria ejecutó `/spec-impl 11-reparto-sin-conexion` con el spec en Aprobado y eligió «crojas-base (actual)», «Seguir con ellos así» (documentos sin commit) y «Todo sin pausas». Autoriza T-11-01 a T-11-09 en el entorno de desarrollo; no autoriza commits ni migrar la base del proyecto.

## Ejecución

| Fecha | Tarea | Archivos / comando | Resultado / pendiente |
|---|---|---|---|
| 2026-11-18 | T-11-01 | `models.py` (`sincronizado_en`, restricción `intento_sincronizado_con_registro`), migración `0007`, `services.py` (`_hora_del_registro`, `registrado_en`), `_horas_sin_conexion.html` en detalle, pendientes y «Registradas hoy»; `test_sin_conexion_hora.py` | 14 pruebas OK; límites, medianoche, preparación (13) y detalle de la Q.F. |
| 2026-11-18 | T-11-02 | `notificaciones.encolar_resultado(..., registrado_en=)`, `REGISTRO_TARDIO`; 4 casos en `test_avisos_resultado.py` | 20 pruebas del archivo OK |
| 2026-11-18 | T-11-03 | `sin_conexion.paquete_del_dia`, `PaqueteView`, ruta `mis/paquete/`; `test_sin_conexion_paquete.py` | 10 pruebas OK (con la página sin conexión) |
| 2026-11-18 | T-11-04 | `sin_conexion.sincronizar` y `Rechazo`, `SincronizarView`, ruta `mis/sincronizar/`; `test_sin_conexion_sincronizar.py` | 14 pruebas OK |
| 2026-11-18 | T-11-05 | `test_concurrencia_sin_conexion.py` | 3 escenarios OK (PostgreSQL de pruebas) |
| 2026-11-18 | T-11-06 | `templates/pwa/sw.js`, `coreapp/views.py` (`ESTATICOS_SIN_CONEXION`, versión), `SinConexionView`, `sin_conexion.html`, `_estado_sin_conexion.html`; `coreapp/tests/test_estaticos.py` | 30 pruebas de `coreapp` (estáticos y vistas) OK |
| 2026-11-18 | T-11-07 | `static/js/entregas/almacen.js`, `sincronizar.js`, `sin_conexion.js`, `mis_entregas.html`, `registro.html`, `entregas.css`; `almacen.test.cjs`, `sincronizar.test.cjs`, `sin_conexion.test.cjs` | 6 + 6 + 15 pruebas de Node OK |
| 2026-11-18 | T-11-08 | `static/js/pwa.js`, `base.html` (`data-cuenta`, `data-salir`, almacen.js); `pwa.test.cjs` | 6 pruebas de Node OK |
| 2026-11-18 | T-11-09 | `tools/verificar_spec_11_http.py`, `tools/previsualizar_interfaz.py` (3 visitas sintéticas para el encargado), documentos | Ver `validation.md` |

## Reanudación

Última acción real: implementación técnica de T-11-01 a T-11-09 (2026-11-18), sin commit. Siguiente paso: revisión del diff por la usuaria, navegador real (red cortada en DevTools, instalación de la PWA, celular Android), axe, usabilidad y aceptación. La base del proyecto no se migró (`0007` pendiente con `python manage.py migrate`). Bloqueos: ninguno.

## Aceptación del usuario

Pendiente; no marcarla automáticamente después de ejecutar tests.
