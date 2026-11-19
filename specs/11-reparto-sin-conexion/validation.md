# Validación — 11 / Reparto sin conexión

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-18. Rama: `crojas-base`, sin commit. Entornos: pruebas de Django sobre la base de pruebas de PostgreSQL que crea el ejecutor (con OSRM desactivado por `coreapp/ejecutor_pruebas.py`); pruebas de Node 24 con `dom_simulado.cjs` y el adaptador en memoria de `almacen.js`; medición HTTP en SQLite temporal con `tools/verificar_spec_11_http.py`. Solo datos sintéticos.
Estado: verificación técnica completa; navegador real, celular Android, axe, usabilidad y aceptación pendientes. No declarar Implementado.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-11-01 | `coreapp/tests/test_estaticos.py` (`test_service_worker_sin_cache_de_datos`, `test_version_de_la_cache_cambia_con_los_estaticos`) | Solo estáticos y página sin conexión; cachés viejas borradas | La lista del service worker tiene solo URL de `/static/` que existen; un solo `put` (la página sin conexión); `caches.delete` de las anteriores; la versión cambia con la lista; sin `/turnos/` ni `localStorage`. Revisión en DevTools pendiente | aprobado técnico |
| RF-11-02 | `test_sin_conexion_paquete.py` | Hoy y atrasadas en orden, sin RUT/fotos/coordenadas/correo; 403 a otros roles | Orden igual a `ruta_del_dia`; 3 de hoy + 1 atrasada; sin próximas ni registradas; claves exactas; sin RUT, coordenadas, correo ni códigos de receta; B solo lo suyo; Q.F., Técnico, Director y superusuario 403; anónimo 302; `no-store, private` | aprobado |
| RF-11-03 | `almacen.test.cjs`, `sin_conexion.test.cjs`, `pwa.test.cjs` | Paquete borrado por fecha, cuenta y salida | Paquete de ayer se borra al leerlo; al entrar otra cuenta se borra el de la anterior; al salir se borra; la vista sin paquete válido solo muestra «No hay una ruta guardada para hoy» | aprobado (Node) |
| RF-11-04 | `sin_conexion.test.cjs`; `test_sin_conexion_paquete.py` (`PaginaSinConexionTests`) | Vista sin conexión con las paradas | Dibuja las paradas del paquete con «Sin conexión»; la página guardada no lleva nombre de la cuenta, RUT, apellidos ni token CSRF. Red cortada en un navegador real: pendiente | aprobado técnico |
| RF-11-05 | `sin_conexion.test.cjs` | Validación del 08, cola, deshacer, un registro por intento | Sin motivo, «Otro» sin nota y nota de 201 caracteres se rechazan con los mensajes del 08; el válido queda «Registrada sin conexión · por enviar» con la hora; no se ofrece otro registro; «Deshacer» lo quita; «Entregada» exige confirmar; con el formulario de «Registrar visita», un fallo de red guarda el `operacion_id` del formulario | aprobado (Node) |
| RF-11-06 | `sincronizar.test.cjs`, `sin_conexion.test.cjs`, `test_sin_conexion_sincronizar.py` | Envío < 30 s, reintento, lotes de 50, botón | Lotes 50/50/20; CSRF por cabecera y `redirect: manual`; sin red, 302/403, 429 y 5xx dejan todo en la cola; `online` dispara el envío y hay reintento cada 30 000 ms; Background Sync se registra donde existe | aprobado (Node y Django) |
| RF-11-07 | `test_sin_conexion_sincronizar.py`, `test_concurrencia_sin_conexion.py` (escenario 1), HTTP | Una aplicación por registro; `ya_aplicado`; sin descuentos dobles | Reenvío da `ya_aplicado`; 4 hilos con el mismo lote: un `aplicado` por registro, recetas descontadas una vez; HTTP: 0 duplicados | aprobado |
| RF-11-08 | `test_sin_conexion_hora.py` | `hora_invalida`, `fuera_de_plazo`, cruce de medianoche aceptado | +10 min y fecha anterior a la programada: `hora_invalida`; +4 min aceptado; hace 3 días: `fuera_de_plazo`; hace 2 días aceptado; ayer 19:50 se aplica con `registrado_en` de ayer y descuenta una receta vencida hoy; lo preparado (13) se evalúa a su fecha de preparación | aprobado |
| RF-11-09 | `test_sin_conexion_sincronizar.py`, `test_concurrencia_sin_conexion.py` (escenarios 2 y 3) | Rechazo con código y auditoría sin nota | `reasignada`, `anulada`, `ya_registrada`, `no_asignada` con auditoría `intento.sincronizacion_rechazada` («intento:código»), sin la nota; frente a reasignar o anular gana exactamente una operación (3 vueltas cada uno) | aprobado |
| RF-11-10 | `sin_conexion.test.cjs` | «No se pudo enviar» con motivo hasta «Entendido» | El rechazo aparece con resultado, nombre, hora y el motivo en palabras; «Entendido» lo quita | aprobado (Node) |
| RF-11-11 | `test_sin_conexion_sincronizar.py`, `sincronizar.test.cjs`, `pwa.test.cjs` | `otro_usuario`; intento pendiente | Registro de otra cuenta: `rechazado/otro_usuario`, intento pendiente, sin `intento.entregado`; el celular solo envía la cola de la cuenta activa | aprobado |
| RF-11-12 | `test_avisos_resultado.py` | Vigencia desde el registro; `registro_tardio` | Hace 1 h: pendiente, vence a las 2 h del registro y se envía; hace 3 h (y no entregada hace 2 h 1 min): `omitido/registro_tardio`; sin correo conserva `sin_destino` | aprobado |
| RF-11-13 | `sin_conexion.test.cjs`; axe | Región `aria-live` con texto; sin errores AA | `role="status"` y `aria-live="polite"`; conexión, ruta guardada, pendientes y envío dichos con texto. Axe pendiente | aprobado técnico |
| RF-11-14 | `pwa.test.cjs` | Aviso con la cifra; cola conservada por cuenta | «Tienes 2 registros sin enviar…»; cancelar no sale; confirmar borra paquete, cuenta activa y token, y conserva la cola; la cola de más de 2 días se borra (`almacen.test.cjs`) | aprobado (Node) |
| RF-11-15 | `test_sin_conexion_hora.py` (`DetalleConDosHorasTests`) | Hora del registro y de llegada en el detalle | Detalle y «Pendientes de gestión» muestran «Registrada sin conexión a las HH:MM · recibida a las HH:MM»; con señal no aparece | aprobado |
| RF-11-16 | `sin_conexion.test.cjs`; regresión del 08 | Con señal, flujo del 08 sin cola | Con señal el formulario va al servidor (redirección → «Mis entregas»; error → página del servidor) y la cola queda vacía | aprobado (Node) |
| NS05 | `tools/verificar_spec_11_http.py` | 100 registros en ≤ 5 min, 0 duplicados | Ver «Medición HTTP» | aprobado (aislado) |
| RNF-05 | `tools/verificar_spec_11_http.py` | p95 ≤ 2 s en paquete y lotes | Ver «Medición HTTP»: paquete y lotes de un celular a la vez dentro del límite; lotes simultáneos fuera, aceptados como límite por la usuaria | aprobado con límite aceptado |

## Comandos ejecutados

- `python manage.py makemigrations entregasapp -n intentoentrega_sincronizado_en`: crea `0007` (campo y restricción).
- `python manage.py test entregasapp.tests.test_sin_conexion_hora entregasapp.tests.test_registro entregasapp.tests.test_avisos_resultado`: tras corregir una ayuda de la prueba (la receta vencida se fija después de programar), 14 + regresión OK.
- `python manage.py test entregasapp.tests.test_sin_conexion_paquete entregasapp.tests.test_sin_conexion_sincronizar`: 24 OK (antes, una aserción de la prueba confundía la clave `"ruta"` con `"rut`; se corrigió la prueba).
- `python manage.py test entregasapp.tests.test_concurrencia_sin_conexion`: 3 OK.
- `python manage.py test coreapp.tests.test_estaticos coreapp.tests.test_vistas`: 30 OK (la URL del service worker ahora va como JSON).
- `node --test entregasapp/tests/*.test.cjs`: 131 OK (32 nuevas, con «Actualizar la lista»); `turnosapp`: 71 OK; `recetasapp`: 7 OK. `node --check` de `pwa.js` y `static/js/entregas/*.js` y del service worker renderizado: sin errores.

## Medición HTTP

`python tools/verificar_spec_11_http.py` (SQLite temporal, 670 pacientes sintéticos, 6 encargados con rutas de 40 visitas, OSRM desactivado):

- Primera ejecución: NS05 aprobado, pero el p95 de los lotes enviados a la vez fue 3 560 ms y la herramienta falló su aserción de 2 s. Se agregó el reconocimiento de `ya_aplicado` sin tomar la cola del día (decisión 2 del spec) y la herramienta pasó a medir por separado los lotes de un celular a la vez (RNF-05) y los simultáneos del NS05 (informados sin límite).
- Segunda ejecución: paquete p95 109,99 ms (120 muestras); lote de un celular a la vez (40 registros) p95 1 633,54 ms (3 muestras); reenvío p95 91,32 ms (30 muestras). NS05: 100 registros de tres celulares a la vez, uno además desde dos pestañas, sincronizados en 4,775 s con 0 duplicados, 50 entregadas descontadas una vez, 4 vueltas con `reintentar` (10 registros reenviados, como hace el celular). Lotes simultáneos: p95 y máximo 4 367,9 ms (8 muestras), **fuera de los 2 s**.
- Ejecución final (con todo el código del spec): paquete p95 67,87 ms (120 muestras); lote de un celular a la vez p95 1 705,25 ms (3 muestras de 40 registros); reenvío p95 64,84 ms (30 muestras). NS05: 100 registros sincronizados en 5,709 s, 0 duplicados, 50 entregadas descontadas una vez, 5 vueltas con `reintentar` (19 registros reenviados). Lotes simultáneos: p95 y máximo 5 293,34 ms (9 muestras), **fuera de los 2 s**. La herramienta terminó «aprobado» porque solo exige los 2 s a los lotes de un celular a la vez.

## Regresión de la base

- Primera suite completa (`python manage.py test --parallel 1`): 1 210 pruebas, **1 fallo**: `coreapp.tests.test_plantillas` exige que toda plantilla renderice algo sin contexto y la parcial `_horas_sin_conexion.html` quedaba vacía. Se reemplazó por la etiqueta `{% horas_sin_conexion %}` (`entregasapp/templatetags/entregas_tags.py`).
- Segunda suite completa: **1 210 pruebas OK** (326,99 s). Después se agregó el botón «Actualizar la lista» y se volvieron a correr plantillas, estáticos, paquete y vistas del encargado: 59 OK.
- `python manage.py makemigrations --check --dry-run`: «No changes detected». `python manage.py check`: sin problemas.

## Revisión visual si aplica

2026-11-18, navegador del panel de la app (Chromium) contra `tools/previsualizar_interfaz.py` (SQLite temporal y datos sintéticos; se le agregaron 3 visitas de hoy para `revision_terreno`), en `localhost`. La falta de señal se simuló **deteniendo el servidor**, no con la red cortada en DevTools:

- «Mis entregas» con señal: «Conectado · Ruta guardada en este celular a las 22:54 · 3 visitas · No hay registros por enviar.»; consola sin errores; service worker `activated` y controlando la página; la caché `cesfam-…` contenía solo los 16 estáticos de la lista y `/entregas/mis/sin-conexion/`; IndexedDB con el paquete de la cuenta (13 claves por parada, sin RUT), `cuenta_activa` y `csrf`.
- Servidor detenido y recarga de `/`: el service worker mostró «Mis entregas sin conexión» con las 3 paradas desde IndexedDB. Sin motivo, «Elige el motivo de la no entrega.»; con motivo, «Registrada sin conexión · por enviar · No entregada · 22:55» y «1 registro por enviar»; «Sincronizar ahora» dijo «Sin señal: los registros se enviarán solos al volver la conexión.».
- **Fallo encontrado y corregido:** el aviso «No hay una ruta guardada para hoy» se veía aunque tenía `hidden` (`.message` usa `display: flex`). Se agregó en `entregas.css` la regla `[hidden] { display: none }` para la barra y la vista, como ya hacía `.fotos-form`; comprobado después (`display: none`).
- Servidor levantado de nuevo (base y clave nuevas, sesión vencida): la página pidió entrar; al volver a entrar con la misma cuenta, «Mis entregas» envió la cola sola («Se envió 1 registro.»). Recargada, «Registradas hoy (1)» mostró «Registrada sin conexión a las 22:55 · recibida a las 22:57»: se conservó la hora del celular.
- Al cambiar los estáticos, la caché pasó de `cesfam-36faaf16ba05b4aa` a `cesfam-d3d687b76a4bc7dd` y la anterior se borró (RF-11-01).
- Vista sin conexión a 375 × 812: sin desplazamiento horizontal (`scrollWidth` 375); abrir `/entregas/intentos/2/?resultado=entregada` sin señal abrió el formulario de esa parada.
- Se agregó «Actualizar la lista» en «Mis entregas» tras un envío aplicado (la lista del servidor se dibujó antes del envío), con su prueba de Node; no se volvió a revisar en el navegador.

Pendiente: red cortada en DevTools, Background Sync con la app cerrada, instalación de la PWA, celular Android real, axe de la vista sin conexión y de la barra de estado, y lector de pantalla.

## Límites y fallos

- **RNF-05 con envíos simultáneos:** cuando varios celulares recuperan la señal a la vez, cada registro toma la cola del día (contrato del 08) y la base atiende de a una escritura; en SQLite un lote de 40 llegó a 5,3 s. Con un celular a la vez el p95 es 1,7 s, cerca del límite. No se midió en PostgreSQL ni con red móvil. **Decisión de la usuaria (2026-11-18, «Dejarlo como límite»):** se acepta como límite conocido; el spec no cambia y los 2 s se exigen a los lotes de un celular a la vez.
- Background Sync solo existe en navegadores Chromium; en los demás, el envío depende de abrir la app. No se probó con un navegador real.
- El service worker y la vista sin conexión solo se probaron como plantilla renderizada y en Node: no se ejecutaron en un navegador.
- La medición HTTP usa WSGI en loopback y SQLite; no mide Service Worker, IndexedDB, red móvil ni un celular real.

## Aplicación y reversión

Migración `entregasapp/0007_intentoentrega_sincronizado_en` (campo opcional y restricción), creada y aplicada solo en las bases de prueba. **La base del proyecto no se migró**: aplicar con `python manage.py migrate`. Reversión: `python manage.py migrate entregasapp 0006` y restaurar `templates/pwa/sw.js` mínimo; los celulares borran la caché al activarse el service worker anterior porque cambia el nombre.

## Aceptación funcional

Pendiente.
