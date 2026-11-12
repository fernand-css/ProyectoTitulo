# Plan técnico — 09 / Mapa y orden de visita

Spec: [spec.md](spec.md). Tareas: [tasks.md](tasks.md). Evidencia: [validation.md](validation.md).
Fecha: 2026-11-12. Estado: propuesta; sin código.
Autorización de implementación: pendiente.

## Inspección de la base

Revisados `CLAUDE.md`, el informe (HU-12, HU-14, RNF-03, RNF-09, §2.1 sobre «trazabilidad de ruta», §5 sobre servicios externos y cartografía), el índice de specs, las plantillas y los cuatro documentos del 08 (y el encabezado del 07). Del código real en `crojas-base` (`f882935`):

- **`entregasapp/models.py`:**
  - `Domicilio` tiene `latitud` y `longitud` Decimal(9, 6) (ambas o ninguna), `precision_metros`, `sector` (`verde`, `azul`, `rojo` o en blanco) y `localidad`;
  - `IntentoEntrega` tiene `entrega`, `numero`, `fecha_programada`, `encargado`, `resultado` (`pendiente`, `entregada`, `no_entregada`, `reasignado`, `anulado`), `motivo`, `nota`, `registrado_en` y `registrado_por`;
  - todos los modelos heredan `ModeloAuditado` y no están en el Admin;
  - la única migración es `0001_initial`.
- **`entregasapp/consultas.py`:**
  - `mis_entregas(encargado, hoy)` devuelve `MisEntregas(hoy, atrasadas, proximas)`, ordenadas por `fecha_programada`, sector, localidad y `pk`, a partir de `_intentos_con_contexto()`;
  - `contar_mis_entregas` alimenta la cantidad de la pestaña;
  - `encargados_activos()` ya existe.
- **`entregasapp/services.py`:**
  - `es_encargado(actor)` hace la comprobación exacta, sin el atajo del superusuario; `autorizar(actor, *roles)` y `_bloquear_jornada(hoy)` completan el control;
  - `auditar` y `reintentar_conflictos` vienen de `recetasapp.services`;
  - `guardar_domicilio(actor, paciente_id, datos, version=None)` crea domicilios: exige un paciente elegible y autoriza a la Q.F., al encargado y al superusuario.
- **`entregasapp/views.py`:**
  - `EntregasView.render` pone `Referrer-Policy: same-origin` y arma `pestanas(actual)`: el encargado tiene «Mis entregas» y «Domicilios»; el resto, «Programación», «Pendientes de gestión» y «Domicilios»;
  - `MisEntregasView(SoloEncargadoView)` dibuja `mis_entregas.html` con `_preparar_intentos`;
  - el registro (`EntregadaView` y `NoEntregadaView`) redirige a `entregasapp:mis`.
- **Plantillas y estáticos de entregas:**
  - `templates/entregas/mis_entregas.html` y `_tarjeta_intento.html` muestran las coordenadas solo en texto;
  - `static/js/entregas/ubicacion.js` usa la ubicación del navegador con un gesto y tiene su prueba de Node, `entregasapp/tests/ubicacion.test.cjs`;
  - `static/css/entregas.css` está sujeta a la regla de paleta de `coreapp/tests/test_estaticos.py`.
- **`coreapp/tests/test_estaticos.py`:**
  - `test_html_sin_dependencias_en_cdn` prohíbe `src` y `href` hacia `http(s)://` en las plantillas;
  - Alpine se copió localmente (`static/js/alpine.min.js` y `alpine.LICENSE.md`) y una prueba verifica su versión y su licencia;
  - `test_service_worker_sin_cache_de_datos` exige que `templates/pwa/sw.js` no tenga `caches.` ni un manejador `fetch`.
- **`coreapp/navegacion.py`:** la entrada `mis_entregas` (rol `ENCARGADO`) marca como activas `mis`, `registro`, `intento_entregada`, `intento_no_entregada` y `detalle`.
- **`cesfam/settings.py`:**
  - lee `.env` con `os.getenv` y define `ARCHIVOS_PRIVADOS_ROOT` con un valor por defecto;
  - `TIME_ZONE = "America/Santiago"`;
  - no hay CSP; `SecurityMiddleware` está activo.
- **`recetasapp/management/commands/generar_padron_demo.py`:** genera un archivo CSV o XLSX reproducible (`--semilla`) sin tocar la base.
- **No hay** librería de mapas, proveedor de teselas, motor de rutas ni comandos en `entregasapp`.

## Diseño propuesto

Se extiende `entregasapp`. No se modifican los modelos ni los servicios del 08.

```text
IntentoEntrega (08) ──► consultas.ruta_del_dia(encargado, fecha) ──► RutaDelDia
   + Domicilio.latitud/longitud (08)        │  usa ruta.py (puro): haversine, vecino más cercano,
   + última visita registrada hoy           │  2-opt con extremos fijos, inserción más barata
   + OrdenRuta/ParadaRuta (nuevo, opcional) ┘
                                             ├─► Mis entregas (lista numerada, registradas, próximas)
                                             ├─► Mapa (Leaflet local + teselas OSM, datos en json_script)
                                             ├─► Ir a esta parada (posición solo en el navegador)
                                             └─► Rutas (Q.F./superusuario, solo consulta)

Encargado ► Subir/Bajar/Mover a ► services.mover_parada ─► OrdenRuta (versión) + ParadaRuta (reemplazo)
          ► Volver al sugerido  ► services.restablecer_orden
```

Responsabilidades:

- `entregasapp/ruta.py` (nuevo, sin ORM ni Django):
  - `Punto(clave, latitud, longitud)`, `distancia_m(a, b)` (haversine, R = 6.371.000 m) y `longitud_m(recorrido)`;
  - `ordenar(partida, destino, paradas)`: vecino más cercano y luego 2-opt sobre un camino con extremos fijos (partida y CESFAM), con desempate por `clave` y un límite de 200 paradas para el 2-opt;
  - `insertar(secuencia, partida, destino, nueva)`: devuelve el índice de inserción más barata.

  Es determinista y se prueba sin base de datos.
- `entregasapp/consultas.py`:
  - nueva `ruta_del_dia(encargado, fecha, hoy=None) -> RutaDelDia`;
  - nueva `registradas_hoy(encargado, hoy)`;
  - nueva `partida_del_dia(encargado, hoy)`, que devuelve el domicilio con coordenadas de la última visita registrada hoy, o el origen.
- `entregasapp/models.py`: `OrdenRuta` y `ParadaRuta` (ver «Datos y contratos»).
- `entregasapp/services.py`: nuevas `mover_parada` y `restablecer_orden`. El resto no cambia.
- `entregasapp/checks.py` (nuevo) y `apps.py` (`ready`): comprobación de sistema de la configuración del mapa.
- `entregasapp/mapa.py` (nuevo): arma el diccionario de datos del mapa a partir de `RutaDelDia`, con campos mínimos y sin RUT, para `json_script`.
- `entregasapp/management/commands/generar_domicilios_demo.py` (nuevo).
- Estáticos:
  - `static/vendor/leaflet/` (Leaflet 1.9.4: `leaflet.js`, `leaflet.css`, `LICENSE` e imágenes de la distribución);
  - `static/js/entregas/mapa.js` e `ir_a.js` (nuevos), con ayudas puras exportables para Node;
  - estilos del mapa en `static/css/entregas.css`, con las variables de la paleta.

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-09-01 | `entregasapp/consultas.py` (`ruta_del_dia`) | Intentos pendientes de hoy y atrasados, o de una fecha futura; nunca de otro encargado | `entregasapp/tests/test_ruta_consultas.py` |
| RF-09-02 | `entregasapp/ruta.py` (nuevo); `consultas.partida_del_dia` | Vecino más cercano y 2-opt con extremos fijos; recálculo desde la última visita registrada | `test_ruta.py` (puro, con fuerza bruta para n ≤ 7); `test_ruta_consultas.py` |
| RF-09-03 | `consultas.ruta_del_dia`; plantillas | Visitas sin coordenadas aparte, agrupadas y rotuladas; contador en el mapa | `test_ruta_consultas.py`; `test_vistas_mapa.py` |
| RF-09-04 | `models.py` (`OrdenRuta`, `ParadaRuta`), `migrations/0002_ordenruta.py`, `services.mover_parada`, vista POST | Guardar el orden completo con versión, idempotencia y comprobación exacta del encargado | `test_orden_manual.py`; `test_concurrencia_ruta.py` |
| RF-09-05 | `ruta.insertar`; `consultas.ruta_del_dia` | Inserción más barata al mostrar, con la marca `nueva`; intersección con la ruta vigente | `test_ruta.py`; `test_ruta_consultas.py` |
| RF-09-06 | `services.restablecer_orden`, vista POST | Vacía las paradas y sube la versión | `test_orden_manual.py` |
| RF-09-07 | `consultas.registradas_hoy`; plantillas; `mapa.py` | Resultado, motivo y hora; marcador distinto sin número | `test_ruta_consultas.py`; `test_vistas_mapa.py` |
| RF-09-08 | `views.MapaView`, `templates/entregas/mapa.html`, `_mapa.html`, `mapa.py`, `static/js/entregas/mapa.js`, `static/vendor/leaflet/` | Datos en `json_script`, marcadores numerados, línea punteada, total en km, aviso si fallan las teselas | `test_vistas_mapa.py`; `entregasapp/tests/mapa.test.cjs` |
| RF-09-09 | `views.IrAView`, `templates/entregas/ir_a.html`, `static/js/entregas/ir_a.js` | `watchPosition` con un gesto, distancia, rumbo, `aria-live`, detención y enlace `geo:` | `entregasapp/tests/ir_a.test.cjs`; `test_vistas_mapa.py` |
| RF-09-10 | `views.RutasView`, `templates/entregas/rutas.html`, `forms.RutaForm`, `EntregasView.pestanas` | Selector de encargado y fecha; solo consulta; pestaña solo para la Q.F. y el superusuario | `test_vistas_mapa.py`; `test_permisos_mapa.py` |
| RF-09-11 | `templates/entregas/domicilio.html`, `_mapa_punto.html`, `views.DomicilioView` (contexto) | Mapa pequeño de solo lectura | `test_vistas_mapa.py` |
| RF-09-12 | `cesfam/settings.py`, `.env.example`, `entregasapp/checks.py`, `apps.py` | Variables con valores por defecto; error de `check` si no son válidas; Leaflet local | `test_configuracion_mapa.py`; `coreapp/tests/test_estaticos.py` |
| RF-09-13 | `entregasapp/management/commands/generar_domicilios_demo.py` | Simulación sin `--aplicar`; creación mediante `guardar_domicilio`, reproducible | `test_generar_domicilios_demo.py` |
| RF-09-14 | Vistas con `RolRequeridoMixin` y `SoloEncargadoView`; `services` con `es_encargado`; `mapa.js` (`referrerPolicy`) | Matriz, CSRF, `no-store`, sin RUT, auditoría sin datos personales y rollback | `test_permisos_mapa.py`; `mapa.test.cjs` |
| RF-09-15 | `test_concurrencia_ruta.py`; regresión del 03 al 08 | Tres escenarios con hilos; suites existentes | `test_concurrencia_ruta.py`; regresión completa |

## Datos y contratos

### `OrdenRuta` (hereda `ModeloAuditado`)

| Campo | Tipo | Regla |
|---|---|---|
| `encargado` | FK a usuario, `PROTECT`, `related_name="ordenes_ruta"` | Dueño del orden. |
| `fecha` | Date | Jornada (`America/Santiago`). |
| `version` | PositiveInteger, por defecto 1 | Control de edición concurrente. |
| `ultima_operacion` | UUID, nulo | Idempotencia del último POST aplicado. |

Restricción: `UniqueConstraint(encargado, fecha, name="orden_ruta_unico")`. El orden es manual si tiene paradas; sin paradas, vale la sugerencia.

### `ParadaRuta`

| Campo | Tipo | Regla |
|---|---|---|
| `orden` | FK a `OrdenRuta`, `CASCADE`, `related_name="paradas"` | — |
| `intento` | FK a `IntentoEntrega`, `PROTECT`, `related_name="paradas_ruta"` | Los intentos nunca se borran (08). |
| `posicion` | PositiveSmallInteger | 1..n. |

Restricciones: `UniqueConstraint(orden, intento)`, `UniqueConstraint(orden, posicion)` y `CheckConstraint(posicion >= 1)`. Al guardar se reemplazan todas las paradas del orden dentro de la transacción, después de subir la versión. Así no hay estados intermedios con posiciones repetidas.

### `RutaDelDia` (consulta, sin persistencia)

`fecha`, `modo` (`sugerido` o `manual`), `guardado_en` y `version` (0 si no hay orden), `origen` y `partida` (`Punto`), `paradas` (lista de `Parada`: `numero`, `intento`, `punto` o `None`, `atrasada`, `nueva`), `sin_coordenadas` (solo en modo sugerido, agrupadas por sector y localidad), `registradas` (solo si la fecha es hoy), `proximas` (solo para el encargado), `total_m`, `segundos_calculo` (para la herramienta de medición) y `limite_2opt_excedido`.

Algoritmo de `ruta_del_dia`:
1. Lee los intentos pendientes de la ruta: si la fecha es hoy, los de `fecha_programada <= hoy`; si es futura, los de esa fecha. Usa `_intentos_con_contexto()` con domicilio y recetas.
2. Calcula `partida`: si la fecha es hoy, el domicilio con coordenadas de la última visita del encargado con `resultado in (entregada, no_entregada)` y `registrado_en` dentro de hoy, ordenada por `registrado_en` descendente; si no hay, el origen.
3. Si la fecha es hoy y existe un `OrdenRuta` con paradas:
   - conserva, en su orden, las paradas cuyo intento sigue en la ruta;
   - inserta las visitas pendientes que faltan, con `ruta.insertar` si tienen coordenadas (calculado sobre las paradas con coordenadas, de `partida` a `origen`) o al final si no las tienen, marcadas `nueva`;
   - numera todas, incluidas las que no tienen coordenadas.
4. Si no, ordena con `ruta.ordenar(partida, origen, con_coordenadas)` y deja `sin_coordenadas` aparte.
5. `total_m` es la longitud de partida → paradas con coordenadas → origen.

Consultas constantes: intentos con contexto, última registrada, orden y paradas, registradas hoy. El cálculo es O(n²) por pasada del 2-opt; con n ≤ 200 se espera muy por debajo de 100 ms (se mide).

### Servicios (`entregasapp/services.py`)

Reglas comunes del 08: `@reintentar_conflictos`, `@transaction.atomic`, `auditar` (si falla, `RuntimeError` y rollback) y UPDATE condicionales que solo filtran campos propios.

- `mover_parada(actor, intento_id, destino, version, operacion_id)`:
  1. Exige `es_encargado(actor)`; no usa `tiene_rol`, así que el superusuario y la Q.F. quedan fuera. `destino` es `"subir"`, `"bajar"` o una posición entera; `operacion_id` debe ser un UUID válido.
  2. Idempotencia: si `OrdenRuta(encargado=actor, fecha=hoy).ultima_operacion == operacion_id`, devuelve la ruta actual sin cambios.
  3. Si no existe un `OrdenRuta` para hoy y la versión enviada es 0, lo crea con la versión 1. Un `IntegrityError` de `orden_ruta_unico` se traduce en `ConflictoOperacion` y se reintenta; en el reintento, la versión ya no coincide y el resultado es el mensaje de conflicto. Si ya existe, aplica `OrdenRuta.objects.filter(pk=…, version=version).update(version=F("version") + 1, ultima_operacion=…, modificado_por=…, modificado_en=…)`. Con 0 filas, lanza `ValidationError("Tu orden cambió en otro dispositivo; revisa la lista.")`, sin reintento.
  4. Calcula `ruta_del_dia(actor, hoy)` dentro de la transacción. En modo sugerido, la secuencia de partida son las paradas numeradas seguidas de las visitas sin coordenadas. Exige que el intento esté en la secuencia y que el destino sea válido: no se sube la primera ni se baja la última, y la posición va de 1 a n. Si no se cumple, lanza `ValidationError` con texto.
  5. Aplica el movimiento, borra las `ParadaRuta` del orden y crea la secuencia nueva con `bulk_create`, solo con intentos pendientes de la ruta.
  6. Audita `ruta.ordenada` con `{orden_id, version, paradas}` (identificadores y cantidad).
- `restablecer_orden(actor, version, operacion_id)`: aplica las mismas comprobaciones 1 a 3, borra las paradas y audita `ruta.restablecida`. Si no hay orden, no hace nada.
- Lectura cruzada segura: el registro y la reasignación del 08 no tocan `OrdenRuta`. Si una carrera deja guardada una parada cuyo intento cambió, la lectura la descarta porque `ruta_del_dia` cruza siempre el orden con la ruta vigente. No se agrega `bloquear_cola`, porque el orden no toca recetas ni turnos.

### Configuración (`cesfam/settings.py`)

| Variable | Por defecto | Uso |
|---|---|---|
| `REPARTO_ORIGEN_LATITUD`, `REPARTO_ORIGEN_LONGITUD` | Valor de demostración aproximado del centro de San Nicolás (alrededor de −36,50 y −72,21; se verifica y rotula al implementar) | Origen y destino final del recorrido; marcador «CESFAM». |
| `MAPA_TESELAS_URL` | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | Mapa base. |
| `MAPA_TESELAS_ATRIBUCION` | `© colaboradores de OpenStreetMap` (con enlace a la página de derechos de autor de OSM, dibujado por Leaflet) | Atribución visible. |
| `MAPA_ZOOM_MAXIMO` | 19 | Límite del proveedor. |

`entregasapp/checks.py` registra `entregasapp.E001` (origen no numérico o fuera de rango), `E002` (URL sin `{z}`, `{x}` o `{y}`, o sin `https://`) y `E003` (zoom fuera de 1–22). Los valores se parsean en `settings.py` sin lanzar errores, para que `check` pueda informarlos.

### Datos del mapa (`entregasapp/mapa.py` → `json_script`)

```json
{
  "origen": {"lat": -36.5, "lon": -72.21, "etiqueta": "CESFAM"},
  "partida": {"lat": …, "lon": …, "etiqueta": "Última visita registrada"},
  "teselas": {"url": "…", "atribucion": "…", "zoom_maximo": 19},
  "paradas": [{"numero": 1, "intento": 41, "lat": …, "lon": …, "atrasada": "10/11", "nueva": false,
               "titulo": "Nombre del paciente", "sector": "Verde", "localidad": "…", "direccion": "…",
               "referencias": "…", "url_registrar": "/entregas/intentos/41/", "url_ir": "/entregas/mis/ir/41/",
               "url_domicilio": "/entregas/domicilios/paciente/7/"}],
  "registradas": [{"intento": 39, "lat": …, "lon": …, "resultado": "No entregada", "motivo": "…", "hora": "10:15", "titulo": "…"}],
  "linea": [[lat, lon], …],
  "total_km": "23,4",
  "sin_marcador": 1
}
```

No incluye el RUT, el teléfono, las notas ni las fotos. En «Rutas», las URL de registrar y de «Ir a» van vacías.

### Rutas y vistas (`entregasapp/urls.py`)

| Ruta | Método | Roles | Resumen |
|---|---|---|---|
| `/entregas/mis/` | GET | Encargado | Ruta numerada, sin coordenadas, registradas hoy y próximas; controles de orden. |
| `/entregas/mis/mapa/` | GET | Encargado | Mapa de su ruta de hoy. |
| `/entregas/mis/ir/<pk>/` | GET | Encargado asignado; intento pendiente de su ruta de hoy con coordenadas | «Ir a esta parada». |
| `/entregas/mis/orden/mover/` | POST | Encargado | `intento`, `destino`, `version` y `operacion_id`; redirige a `mis/#parada-<pk>`. |
| `/entregas/mis/orden/sugerido/` | POST | Encargado | Volver al orden sugerido, con confirmación. |
| `/entregas/rutas/` | GET | Q.F. y superusuario | `?encargado=<pk>&fecha=AAAA-MM-DD`; lista y mapa de solo consulta. |
| `/entregas/domicilios/paciente/<pk>/` | GET | Los mismos del 08 | Agrega el mapa pequeño. |

Todas las respuestas llevan `Cache-Control: no-store`. Los POST exigen CSRF y llevan un `operacion_id` que se genera al dibujar la página. Las vistas del encargado heredan `SoloEncargadoView` y «Rutas» usa `RolRequeridoMixin` con `JEFA`. Por `tiene_rol`, eso incluye al superusuario y excluye al Técnico.

## Permisos e interfaz

- **Pestañas** (`EntregasView.pestanas`):
  - encargado: Mis entregas, Mapa y Domicilios;
  - Q.F. y superusuario: Programación, Pendientes de gestión, Rutas y Domicilios;
  - Técnico: sin cambios.
- **Menú:** `coreapp/navegacion.py` suma `mapa`, `ir_a`, `orden_mover` y `orden_sugerido` a las páginas activas de «Mis entregas». No hay entradas nuevas, así que el dock del celular no cambia.
- **Lista** (`mis_entregas.html` y `_tarjeta_intento.html`):
  - número de parada visible («Parada 3») y rótulos en texto: «Atrasada desde el dd/mm», «Nueva: no estaba en tu orden» y «Sin coordenadas»;
  - controles por tarjeta: «Subir» y «Bajar», que son formularios POST con botones de 48 px y nombre accesible («Subir parada 3: Nombre»), y «Mover a la posición» (`<select>` y botón);
  - los controles se ocultan cuando no aplican (primera y última posición) y no aparecen en «Rutas»;
  - «Volver al orden sugerido» pide confirmación en una página o un `<details>` sin JavaScript obligatorio.
- **Mapa** (`mapa.html` y el parcial `_mapa.html`, compartido con «Rutas»):
  - un contenedor con `role="region"`, nombre accesible y el enlace «Saltar el mapa» hacia la lista;
  - Leaflet se carga solo en estas páginas;
  - marcadores `L.divIcon` con el número en texto, borde oscuro y contraste de 3:1 o más; las registradas usan otra forma (cuadrado con ✓ o ✗ y texto oculto para el lector de pantalla); el CESFAM, una forma propia;
  - `keyboard: true`, título y texto alternativo en cada marcador;
  - la línea es una `L.polyline` punteada con la leyenda en texto;
  - `tileerror` y `load` controlan el aviso «No se pudo cargar el mapa base. Los puntos y la lista siguen disponibles.»;
  - la capa de teselas usa `referrerPolicy: "strict-origin"` (ver riesgos).
- **Ir a esta parada** (`ir_a.html` e `ir_a.js`):
  - un mapa con el destino y un botón «Mostrar mi posición» (con su gesto, `watchPosition` con `enableHighAccuracy`);
  - cada actualización mueve un `circleMarker` con el círculo de precisión y la línea punteada, y actualiza un texto visible: «La parada 3 está a 1,2 km hacia el noreste (precisión ±15 m)»;
  - la región `aria-live="polite"` solo recibe el aviso al iniciar, al pulsar «Leer distancia» y al quedar a menos de 100 m;
  - «Detener» llama a `clearWatch`, igual que `pagehide` y `visibilitychange` a oculto;
  - sin `isSecureContext`, sin permiso o con `POSITION_UNAVAILABLE` muestra textos claros;
  - el módulo no usa `fetch`, `XMLHttpRequest` ni `sendBeacon`;
  - debajo van «Abrir en app de navegación» (`geo:lat,lon`), las coordenadas en texto y «Registrar» y «Ver domicilio».
- **Rutas:** un formulario GET con `<select>` de encargados activos y una fecha (por defecto hoy, mínimo hoy). Debajo, en escritorio, la lista de solo consulta y el mapa lado a lado; en celular, uno después del otro.
- **Domicilio:** el parcial `_mapa_punto.html`, con un marcador y su círculo de precisión, sin interacción de edición.
- **Estilo:** las reglas nuevas van en `entregas.css`, con variables de `base.css`, y la prueba de paleta sigue aplicando. `leaflet.css` se sirve tal cual desde `static/vendor/` y queda fuera de esa regla.

Wireframe de «Mis entregas» (celular):

```text
Mis entregas · miércoles 12/11         [Mis entregas] [Mapa] [Domicilios]
Orden sugerido desde el CESFAM, según distancia en línea recta; no considera caminos.
Recorrido aprox.: 23,4 km · Por visitar (5)

┌ Parada 1 · ATRASADA desde el 10/11 ───────┐
│ Paciente sintético 12 · ☎ 9 1234 5678     │
│ Sector Verde · Localidad demo 3           │
│ [Entregada] [No entregada]                │
│ [Ir a esta parada]   Ver domicilio        │
│ [↓ Bajar]   Mover a [1 ▾] [Mover]         │
└───────────────────────────────────────────┘
…
Sin coordenadas: fuera del orden sugerido (1)
  Sector Azul · Localidad demo 1 — Paciente sintético 40   [Subir]
Registradas hoy (2)
  ✓ Entregada · 09:40 · Paciente sintético 7
  ✗ No entregada · 10:15 · Domicilio no encontrado · Paciente sintético 9
Próximas (2)
```

Wireframe de «Ir a esta parada»:

```text
← Mis entregas · Parada 3 · Paciente sintético 21
[ mapa: destino ◉, mi posición ●, línea punteada ]
La parada 3 está a 1,2 km hacia el noreste (precisión ±15 m).
[ Mostrar mi posición ]  [ Leer distancia ]  [ Detener ]
Abrir en app de navegación · −36.512345, −72.211234
[Entregada] [No entregada] · Ver domicilio
```

## Migraciones y reversión

- `entregasapp/0002_ordenruta`: crea `OrdenRuta` y `ParadaRuta` con sus restricciones. Depende de `entregasapp/0001_initial` y del modelo de usuario. No tiene datos iniciales.
- Sin migraciones en otras apps.
- Reversión: elimina las dos tablas. Solo se pierden los órdenes manuales; las entregas, los intentos y los domicilios no cambian.
- El comando de demostración escribe domicilios con el servicio del 08. Para revertirlo hay que restaurar un respaldo de la base de demostración: no se borran domicilios, porque el 08 no lo permite.
- No se ejecuta nada en esta fase. La base PostgreSQL del proyecto no se migra sin aprobación.

## Plan de pruebas

Pruebas de Django con su propio ejecutor (sin `pytest-django`) y pruebas de Node con DOM simulado, como `ubicacion.test.cjs`:

- **`test_ruta.py` (puro):**
  - distancias conocidas: 1° de latitud ≈ 111,19 km, ida y vuelta simétrica y punto consigo mismo = 0;
  - 0, 1 y 2 paradas;
  - paradas colineales;
  - un caso con cruce que el 2-opt corrige;
  - conjuntos aleatorios reproducibles con n ≤ 7: el resultado nunca es más largo que el vecino más cercano y coincide con el óptimo por fuerza bruta en los casos construidos;
  - extremos fijos (partida ≠ destino), desempate por clave y determinismo;
  - inserción más barata (al inicio, en medio y al final);
  - límite de 200 paradas.
- **`test_ruta_consultas.py`:**
  - composición de la ruta (hoy, atrasadas, próximas, otro encargado, reasignados y anulados);
  - partida desde la última visita registrada con coordenadas (y una sin coordenadas, que se ignora);
  - visitas sin coordenadas;
  - registradas hoy y no las de ayer;
  - orden manual cruzado con la ruta vigente;
  - visitas nuevas por inserción y rótulo;
  - fecha futura para la Q.F.;
  - número de consultas constante (`assertNumQueries`).
- **`test_orden_manual.py`:**
  - subir, bajar y mover a una posición;
  - bordes inválidos;
  - mover una visita sin coordenadas;
  - idempotencia;
  - conflicto de versión;
  - el día siguiente vuelve a la sugerencia;
  - restablecer;
  - rechazo de otro encargado, de la Q.F., del superusuario y del Técnico;
  - auditoría sin datos personales y rollback si falla.
- **`test_concurrencia_ruta.py`** (`TransactionTestCase`, hilos y conexiones separadas):
  1. dos primeras ediciones simultáneas → un `OrdenRuta` y una sola edición aplicada;
  2. tres ediciones desde la misma versión → una gana y dos reciben el aviso;
  3. reordenar mientras se registra «entregada» y se reasigna otra visita → cada intento pendiente aparece una sola vez y no se pierde ninguno.
- **`test_vistas_mapa.py`:**
  - «Mis entregas» con secciones y números;
  - datos del mapa: números iguales a la lista, sin RUT ni teléfono, atribución, línea y total;
  - «Ir a esta parada» solo para paradas de la ruta de hoy con coordenadas;
  - «Rutas» con filtros válidos e inválidos;
  - mapa del domicilio;
  - pestañas por perfil y `no-store`.
- **`test_permisos_mapa.py`:** matriz contra cada URL (anónimo, cuenta inactiva o sin perfil, Técnico, encargado, Q.F. y superusuario), CSRF y URL solo con enteros y fechas.
- **`test_configuracion_mapa.py`:** `E001`, `E002` y `E003` con `override_settings`; valores por defecto.
- **`test_generar_domicilios_demo.py`:**
  - simulación sin escritura;
  - `--aplicar` con una cuenta Q.F.: domicilios dentro del radio, sin verificar y auditados;
  - repetir con la misma semilla no toca los existentes;
  - una cuenta Técnico se rechaza.
- **`coreapp/tests/test_estaticos.py`:** versión y licencia de Leaflet; ninguna plantilla carga recursos desde un CDN; `entregas.css` sigue la paleta; el service worker no cambia.
- **`coreapp/tests/test_navegacion.py`:** páginas activas del encargado.
- **Node:**
  - `mapa.test.cjs`: conversión de datos en marcadores con un `L` simulado, aviso por `tileerror` y `referrerPolicy`;
  - `ir_a.test.cjs`: distancia y rumbo en puntos conocidos, formato «850 m» y «1,2 km», `geo:`, inicio y detención del seguimiento, `pagehide`, permiso denegado, contexto no seguro, aviso a menos de 100 m y ausencia de solicitudes de red.
- **Herramienta HTTP:** `tools/verificar_spec_09_http.py`, con SQLite temporal, 670 pacientes sintéticos, `generar_domicilios_demo --aplicar` y 4 encargados con unas 50 visitas cada uno, programadas con el servicio del 08. Mide el p95 de «Mis entregas», «Mapa», «Ir a esta parada», «Rutas», mover y restablecer, además del tiempo del cálculo con 200 paradas. Comprueba que los datos del mapa no traen RUT y que la auditoría no tiene datos personales.
- **Regresión:** la suite completa del proyecto. Las pruebas del 08 que fijan el orden o las secciones de «Mis entregas» se ajustan y se listan; las del 03 al 07 no cambian.
- **Navegador:** quedan pendientes, salvo que el host lo permita, la revisión visual en escritorio y celular, axe, el teclado en el mapa, el zoom al 200 %, la carga real de teselas y la ubicación real en contexto seguro. No se declaran sin evidencia.

## Riesgos, alternativas y dependencias

- **Política de teselas de OpenStreetMap:** pide atribución, un referente válido y un uso moderado, y prohíbe la descarga masiva. `EntregasView` envía `Referrer-Policy: same-origin`, así que las teselas saldrían sin referente y OSM podría bloquearlas. Mitigación: `referrerPolicy: "strict-origin"` en la capa, que envía solo el origen del sitio y nunca la ruta de la página; atribución visible; sin precarga. Para una implementación real, el DESAMU elige un proveedor (o teselas propias) con la URL configurable.
- **Privacidad de las teselas:** el proveedor ve la IP del celular y el área visible del mapa, aunque no reciba nombres ni coordenadas exactas. Queda documentado en el README; es aceptable para un prototipo con datos sintéticos.
- **La línea recta engaña en zonas rurales** (río Ñuble, Ruta N-50, caminos sin salida). Mitigación: rótulos explícitos, orden manual y el enlace a la aplicación de navegación.
- **Accesibilidad de Leaflet:** el mapa es difícil de usar con teclado y lector de pantalla. Mitigación: la lista es la vista completa, el mapa se puede saltar, los marcadores tienen nombre y el estado va en texto.
- **Ubicación sin HTTPS:** en una demostración por red local sin TLS, «Ir a esta parada» no funciona. Mitigación: texto explicativo, enlace y coordenadas; es el mismo límite del 08.
- **Batería con `watchPosition`:** se detiene con «Detener», con `pagehide` y al ocultarse la página.
- **Orden manual frente a reasignaciones:** la lectura siempre cruza el orden con la ruta vigente, así que no aparecen paradas fantasma.
- **Cambia la presentación de «Mis entregas»:** las pruebas del 08 afectadas se ajustan y se listan; las del 03 al 07 no cambian.
- **Comando de demostración en una base real:** solo escribe con `--aplicar` y una cuenta explícita, y su ayuda advierte que es solo para la base de demostración.
- **Dependencias:** Leaflet 1.9.4 (BSD-2-Clause), copiado con su licencia. No hay dependencias nuevas de Python.
- **Reserva 11:** guardar en caché el mapa base choca con la política de OSM; se deja anotado para ese spec.

## Documentos afectados

Al implementar se actualizan:
- `README.md`: variables del mapa, atribución, privacidad de las teselas y comando de demostración;
- `.env.example`;
- `docs/estructura.md`: `ruta.py`, `mapa.py`, rutas y contratos;
- `CLAUDE.md`: resumen del 09;
- `specs/README.md`: estado.

En esta fase solo se guardan los cuatro documentos y el índice.

## Decisiones para implementar

Ninguna bloqueante. Quedan por confirmar en la revisión el valor exacto del origen y los supuestos del spec: el rótulo «Nueva», «Volver al orden sugerido», el límite de 200 paradas y el radio de demostración. Esta fase termina antes del código.
