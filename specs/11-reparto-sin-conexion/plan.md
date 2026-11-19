# Plan técnico — 11 / Reparto sin conexión

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Validación: [validation.md](validation.md).
Estado: implementado técnicamente el 2026-11-18 en `crojas-base` (autorizado por `/spec-impl`). Las diferencias con este plan están en «Decisiones de implementación» del [spec](spec.md): sin código `fecha_futura` (manda RF-11-08), reenvío `ya_aplicado` sin tomar la cola, página sin conexión en `/entregas/mis/sin-conexion/` guardada por mensaje, JavaScript sin Alpine y cuenta activa para Background Sync.

## Inspección de la base

Archivos leídos el 2026-11-18 en `crojas-base` (limpio, `067b0f7`):

- `templates/pwa/sw.js`: solo `install`/`activate`, sin caché ni `fetch` («La estrategia sin conexión llega en el spec 11»). `coreapp/views.py` (`ServiceWorkerView`, `Service-Worker-Allowed: /`, `Cache-Control: no-cache`). `static/js/pwa.js` lo registra con alcance `/`. `static/manifest.webmanifest` ya es instalable.
- `coreapp/tests/test_estaticos.py::test_service_worker_sin_cache_de_datos` exige que el service worker no guarde datos: se actualiza para exigir que guarde solo estáticos y la página sin conexión.
- `cesfam/settings.py`: `STORAGES["staticfiles"] = coreapp.storage.EstaticosVersionados` (nombres con huella, útiles para versionar la caché). Sin `SESSION_COOKIE_AGE` propio (dos semanas de Django).
- `entregasapp/services.py`: `registrar_entregada` y `registrar_no_entregada` ya reciben `operacion_id` (el modelo lo anota: «la reserva 11 lo generará en el cliente»), usan `timezone.now()` para `registrado_en`, comparan `fecha_programada > hoy` y evalúan la vigencia a `hoy` (o a la fecha de preparación, spec 13). `_intento_para_registrar` devuelve `repetido` para el mismo `operacion_id`.
- `entregasapp/notificaciones.py::encolar_resultado(intento, tipo, ahora)`: vigencia `ahora + VIGENCIA_RESULTADO` (2 h).
- `entregasapp/views.py`: `MisEntregasView`, `RegistroView`, `EntregadaView`, `NoEntregadaView` (`SoloEncargadoView`, `never_cache`). `entregasapp/consultas.py::ruta_del_dia(encargado, hoy=…)` arma el orden (puede consultar OSRM, con caché de 10 min y caída a línea recta).
- `templates/entregas/mis_entregas.html`, `registro.html`, `detalle.html`, `pendientes.html`, `_tarjeta_intento.html`; salida en `templates/components/navbar.html` y `dock.html`.
- Pruebas de JavaScript con Node (`entregasapp/tests/*.test.cjs`, `dom_simulado.cjs`), sin dependencias nuevas.
- Herramientas `tools/verificar_spec_0X_http.py` con SQLite temporal aislada.

## Diseño propuesto

Extensión de `entregasapp` (dominio del reparto) y de `coreapp` (service worker compartido); sin app nueva.

1. **Servidor.**
   - `entregasapp/sin_conexion.py` (nuevo): `paquete_del_dia(encargado, ahora)` arma el diccionario del RF-11-02 desde `consultas.ruta_del_dia` (solo lectura) y `sincronizar(actor, registros, ahora)` valida cada registro, llama a los servicios del 08 y devuelve un resultado por registro. Los códigos de rechazo viven en una sola enumeración (`Rechazo`).
   - `entregasapp/services.py`: `registrar_entregada` y `registrar_no_entregada` aceptan `registrado_en=None`. Si viene, `_hora_del_registro` aplica RF-11-08 (tolerancia, fecha programada, plazo de 2 días), la fecha de evaluación pasa a ser la fecha local de esa hora y se guarda `sincronizado_en=ahora`. La comparación `fecha_programada > hoy` usa esa misma fecha. Sin el parámetro, todo queda igual.
   - `entregasapp/notificaciones.py::encolar_resultado` recibe `registrado_en` opcional: vigencia desde esa hora; si pasaron más de 2 h, el aviso se crea `omitido` con `codigo_resultado="registro_tardio"`.
   - Vistas nuevas en `entregasapp/views.py`: `PaqueteView` (GET JSON, `no-store, private`), `SincronizarView` (POST JSON con CSRF por cabecera `X-CSRFToken`, hasta 50 registros, 413 si son más, límite de 30 solicitudes por minuto por cuenta como el tramo del 09) y `SinConexionView` (página sin datos personales que el service worker guarda; la dibuja Alpine desde IndexedDB).
2. **Service worker** (`templates/pwa/sw.js`, plantilla de Django): lista de estáticos con `{% static %}` (con huella) y la URL de la página sin conexión; `CACHE = "cesfam-v<huella de la lista>"`. Estrategias: estáticos de la lista, caché primero; navegaciones bajo `/entregas/` y `/`, red primero y, si falla la red, la página sin conexión; todo lo demás (JSON, POST, fotos, WebSocket de la sala, `/turnos/`), sin intervenir. Evento `sync` con etiqueta `cesfam-registros`: lee la cola de IndexedDB y llama a la misma función de envío que la página.
3. **Cliente** (`static/js/entregas/`):
   - `almacen.js`: envoltorio de IndexedDB (`paquete`, `cola`) con un adaptador en memoria para las pruebas de Node.
   - `sincronizar.js`: compartido por la página y el service worker (`importScripts`); envía en lotes, aplica respuestas, reintenta cada 30 s, escucha `online` y registra Background Sync si existe.
   - `sin_conexion.js`: descarga el paquete al abrir «Mis entregas» con señal, intercepta el envío de los formularios de registro solo si falla la red (RF-11-16) y dibuja la vista sin conexión (ruta, registro, «por enviar», «No se pudo enviar», estado `aria-live`).
   - `pwa.js`: aviso de salida con pendientes (RF-11-14) y borrado del paquete al salir y al detectar otra cuenta o fecha.
4. **Plantillas:** `templates/entregas/sin_conexion.html` (nueva, extiende la base privada sin datos), barra de estado en `mis_entregas.html`, marca «Registrada sin conexión» en `detalle.html`, `pendientes.html` y `_tarjeta_intento.html`; estilos en `static/css/entregas.css` con las variables de `base.css`.

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-11-01 | `templates/pwa/sw.js`, `coreapp/views.py`, `coreapp/tests/test_estaticos.py` | Caché versionada de estáticos y página sin conexión; borrado de cachés viejas | Prueba de plantilla del SW; revisión en DevTools |
| RF-11-02 | `entregasapp/sin_conexion.py` (nuevo), `views.py`, `urls.py` | `PaqueteView` y `paquete_del_dia` | `test_sin_conexion_paquete.py`: contenido, orden, campos prohibidos, permisos |
| RF-11-03 | `static/js/entregas/almacen.js`, `sin_conexion.js` (nuevos) | Paquete por cuenta y fecha; borrado | `sin_conexion.test.cjs` |
| RF-11-04 | `templates/entregas/sin_conexion.html` (nuevo), `sw.js`, `sin_conexion.js` | Vista desde IndexedDB; respaldo de navegación | `sin_conexion.test.cjs`; prueba en navegador con red cortada |
| RF-11-05 | `sin_conexion.js`, `registro.html`, `mis_entregas.html` | Cola local, validación del 08 en el celular, deshacer | `sin_conexion.test.cjs` |
| RF-11-06 | `sincronizar.js` (nuevo), `sw.js`, `SincronizarView` | Lotes, reintento, `online`, Background Sync, botón | `sincronizar.test.cjs`; `test_sin_conexion_sincronizar.py` |
| RF-11-07 | `sin_conexion.py`, `services.py` | Idempotencia por `operacion_id` | Prueba de reenvío y `test_concurrencia_sin_conexion.py` |
| RF-11-08 | `services.py` (`_hora_del_registro`), migración `0007` | `registrado_en` del celular, `sincronizado_en`, límites, fecha de evaluación | `test_sin_conexion_hora.py` |
| RF-11-09 | `sin_conexion.py`, `coreapp/auditoria.py` (uso) | Códigos y auditoría del rechazo | `test_sin_conexion_sincronizar.py` |
| RF-11-10 | `sin_conexion.js`, `sin_conexion.html` | Lista «No se pudo enviar» | `sin_conexion.test.cjs` |
| RF-11-11 | `sin_conexion.py`, `almacen.js` | Cuenta en el registro y en la cola | Pruebas Python y Node |
| RF-11-12 | `notificaciones.py` | Vigencia desde el registro; `registro_tardio` | `test_avisos_resultado.py` (casos nuevos) |
| RF-11-13 | `sin_conexion.html`, `mis_entregas.html`, `entregas.css` | Región `aria-live` con texto | Node + axe |
| RF-11-14 | `pwa.js`, `navbar.html`, `dock.html` | Aviso al salir; cola conservada por cuenta | `pwa.test.cjs` (nuevo) |
| RF-11-15 | `detalle.html`, `pendientes.html`, `_tarjeta_intento.html` | Texto con las dos horas | `test_vistas.py` (caso nuevo) |
| RF-11-16 | `sin_conexion.js` | Solo intercepta ante fallo de red | Node; regresión del 08 |

## Datos y contratos

- **Migración** `entregasapp/0007_intentoentrega_sincronizado_en`: `IntentoEntrega.sincronizado_en = DateTimeField(null=True, blank=True)` y la restricción `intento_sincronizado_con_registro` (`sincronizado_en IS NULL OR registrado_en IS NOT NULL`). Reversible; sin datos que migrar.
- **GET `/entregas/mis/paquete/`** → `200 application/json`, `Cache-Control: no-store, private`:
  `{"formato": 1, "fecha": "2026-11-18", "generado_en": "<ISO>", "cuenta": <id>, "motivos": [[valor, texto], …], "paradas": [{"intento": 41, "numero": 1, "fecha_programada": "…", "atrasada": false, "nombre": "…", "direccion": "…", "referencias": "…", "localidad": "…", "sector": "…", "telefono": "…", "recetas": 3, "traslado_iniciado": false, "seccion": "ruta|sin_coordenadas"}]}`.
- **POST `/entregas/mis/sincronizar/`** (JSON, `X-CSRFToken`): `{"registros": [{"operacion_id": "<uuid>", "intento": 41, "resultado": "entregada|no_entregada", "motivo": "", "nota": "", "registrado_en": "<ISO con zona>", "cuenta": <id>}]}` → `200 {"resultados": [{"operacion_id": "…", "estado": "aplicado|ya_aplicado|rechazado", "codigo": "", "mensaje": "…"}]}`. 400 si el JSON no es válido; 413 con más de 50; 403 sin rol; 302 a la entrada si no hay sesión (el cliente lo trata como «inicia sesión»).
- **Proceso por registro:** cada uno en su propia transacción (los servicios ya son `@transaction.atomic` con `@reintentar_conflictos`), para que un rechazo no detenga a los demás. `ValidationError`/`PermissionDenied` se traducen al código; `DatabaseError` deja el registro sin respuesta definitiva (`estado: "reintentar"`) para que el cliente lo conserve.
- **Códigos de rechazo:** `otro_usuario`, `no_asignada`, `reasignada`, `anulada`, `ya_registrada`, `hora_invalida` (también para una visita programada después de la fecha del registro, como pide RF-11-08; el `fecha_futura` propuesto aquí no se implementó), `fuera_de_plazo`, `invalido` (motivo, nota u operación no válidos).
- **Concurrencia:** sin cambios en el mecanismo del 08 (`_bloquear_jornada(hoy)` con la fecha del servidor, UPDATE condicional sobre `resultado="pendiente"`, `operacion_id` único). La fecha de evaluación de recetas no cambia el bloqueo.

## Permisos e interfaz

- `PaqueteView`, `SincronizarView` y `SinConexionView` heredan de `SoloEncargadoView` (comprobación exacta). `SinConexionView` no trae datos: lo que dibuja sale de IndexedDB, que es del mismo origen.
- Sin entrada nueva en el menú: la vista sin conexión aparece sola al fallar la red; con señal, la barra de estado va en «Mis entregas».
- Textos: «Sin conexión», «Ruta guardada en este celular a las HH:MM», «N registros por enviar», «Sincronizar ahora», «Registrada sin conexión · por enviar», «No se pudo enviar», «Entendido». Botones de al menos 44 px, foco visible, contraste AA.

## Migraciones y reversión

Una migración (`0007`), reversible. Para volver atrás: revertir la migración y restaurar `sw.js` mínimo; los celulares borran la caché al activarse el service worker anterior porque cambia el nombre de la caché. No se migra la base del proyecto sin instrucción.

## Plan de pruebas

- **Python (`entregasapp/tests/`):** `test_sin_conexion_paquete.py` (contenido, orden, sección sin coordenadas, sin RUT/fotos/coordenadas/correo, permisos para B, Q.F., Técnico, Director, superusuario, anónimo), `test_sin_conexion_hora.py` (límites del RF-11-08, cruce de medianoche, evaluación a la fecha del registro y a la de preparación), `test_sin_conexion_sincronizar.py` (lote mixto, `ya_aplicado`, cada código, 400/413, auditoría sin nota, `otro_usuario`), casos nuevos en `test_avisos_resultado.py` (vigencia y `registro_tardio`) y `test_vistas.py` (RF-11-15).
- **Concurrencia (`test_concurrencia_sin_conexion.py`, `TransactionTestCase` e hilos):** mismo lote en paralelo; sincronización frente a `reasignar`; sincronización frente a `anular_entrega`. Gana exactamente una operación y no hay descuentos dobles.
- **Node:** `almacen.test.cjs`, `sincronizar.test.cjs`, `sin_conexion.test.cjs`, `pwa.test.cjs` con el adaptador en memoria y `dom_simulado.cjs`.
- **Regresión:** suite completa de Django y `makemigrations --check`.
- **HTTP aislado:** `tools/verificar_spec_11_http.py` con SQLite temporal, 670 pacientes, 3 encargados y 40 visitas por encargado: p95 del paquete y de los lotes; 100 registros en cola enviados en lotes, medición del tiempo total (≤ 5 min) y comprobación de 0 duplicados.
- **Navegador (pendiente de host):** red cortada en DevTools, instalación de la PWA, celular Android real, axe de la vista sin conexión.

## Riesgos, alternativas y dependencias

- **Reloj del celular equivocado:** mitigado con la tolerancia y la fecha programada; el resto es confianza en el dispositivo del personal.
- **Background Sync solo en Chromium:** en otros navegadores el envío ocurre al abrir la app; el aviso de «N por enviar» lo hace visible.
- **Sesión vencida en terreno:** la cola se conserva y se envía al volver a entrar; la sesión de Django dura dos semanas por omisión.
- **Caché vieja tras desplegar:** el nombre de la caché depende de la huella de los estáticos; `skipWaiting` + `clients.claim()` ya están en el 01.
- **Alternativa descartada — guardar en caché el HTML de «Mis entregas»:** tendría datos personales en la caché del service worker, un token CSRF viejo y estado desactualizado; se prefiere el paquete JSON y una página sin datos.
- **Alternativa descartada — cifrar IndexedDB:** la clave tendría que vivir en el mismo navegador; no protege frente al celular desbloqueado y complica la recuperación.
- **Sin paquetes nuevos:** IndexedDB, Service Worker y Background Sync son del navegador; Alpine ya está.

## Documentos afectados

Al implementar: `specs/README.md` (estado), `docs/estructura.md` (service worker y archivos nuevos), `README.md` (HTTPS para el service worker en el despliegue), `CLAUDE.md` (resumen del 11), nota de compatibilidad en `specs/08-domicilios-y-entregas/spec.md` y `specs/09-mapa-y-orden-de-visita/spec.md` (RF-09-26 sigue igual) y en `specs/12-notificaciones-reparto/spec.md` (vigencia desde el registro).

## Decisiones para implementar

Ninguna bloqueante. Los supuestos técnicos del spec (tolerancia, lote, CSRF en la cola, cola conservada al salir, sin cifrado) se confirman al aprobar.
