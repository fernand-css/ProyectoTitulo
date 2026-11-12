# SPEC 09 — Mapa y orden de visita

> **Estado:** Aprobado
> **Depende de:** [SPEC 01](../01-base-del-proyecto/spec.md), [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 03](../03-padron-y-recetas/spec.md) y [SPEC 08](../08-domicilios-y-entregas/spec.md)
> **Fecha:** 2026-11-12
> **Objetivo:** Mostrar al encargado de terreno sus visitas del día en una lista numerada y en un mapa, con un orden de visita sugerido que puede ajustar y guardar y una guía hacia cada parada calculada solo en su celular, y permitir a la Q.F. consultar el mapa y el orden de cada encargado.

Módulo: `entregasapp` (orden de visita, mapa y rutas), con cambios acotados en `cesfam/settings.py` (origen y cartografía), `coreapp/navegacion.py` (páginas activas) y los estáticos (Leaflet local). Fuente: HU-14 y la parte de HU-12 que pide identificar los domicilios en un mapa; RNF-01/04/05/09; §2.1 y §5 del [informe](../../docs/Informe.md); respuestas del usuario del 2026-11-11 y 2026-11-12.
Implementación autorizada: NO. Revisión del usuario: pendiente.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md), [índice](../README.md).

## Problema y resultado

El 08 dejó a cada paciente del reparto con un domicilio que puede tener coordenadas, y a cada encargado con su lista «Mis entregas», ordenada por fecha, sector y localidad. No hay mapa ni orden de visita: el encargado decide el recorrido de memoria, en una comuna con un 57,9 % de ruralidad y direcciones como «Dadinco, km 2 casa roja». HU-14 pide ver en un mapa y en un registro las entregas del día, con íconos de los domicilios, la ubicación y el estado de cada entrega, y un orden de visita sugerido que priorice reducir el tiempo total de ruta, sin seguimiento GPS en tiempo real y desde la misma PWA.

Resultado esperado:

- En «Mis entregas», las visitas de hoy y las atrasadas aparecen numeradas en un orden sugerido. Ese orden reduce el recorrido en línea recta que sale del CESFAM y vuelve a él. Las visitas ya registradas hoy aparecen aparte, con su resultado.
- La pestaña «Mapa» muestra los mismos números como marcadores sobre OpenStreetMap, el CESFAM, las visitas registradas y una línea recta punteada con el recorrido.
- El encargado puede subir, bajar o mover paradas. Su orden queda guardado para el día y reemplaza a la sugerencia.
- Con «Ir a esta parada», el encargado ve su posición, la distancia en línea recta y la dirección hacia la parada. La posición se calcula solo en su celular y nunca llega al servidor. Como apoyo, un enlace abre su aplicación de navegación.
- La Q.F. elige un encargado y una fecha y consulta su lista y su mapa, sin poder cambiarlos.
- La página del domicilio muestra su punto en un mapa pequeño.

## Actores y permisos

| Acción / datos | Anónimo / tótem | Técnico | Encargado de terreno | Q.F. | Superusuario activo |
|---|---|---|---|---|---|
| Ver su lista ordenada, su mapa y «Registradas hoy» | No | No | Solo las suyas | No | No |
| Reordenar su ruta de hoy o volver al orden sugerido | No | No | Solo la suya | No | No |
| «Ir a esta parada» (posición calculada en el celular) | No | No | Solo sus paradas | No | No |
| Consultar la lista y el mapa de un encargado por fecha («Rutas») | No | **No** | No | Sí, solo consulta | Sí, solo consulta |
| Ver el mapa pequeño de un domicilio | No | Sí | Sí | Sí | Sí |

Como en el 02, el servidor revalida en cada solicitud que la cuenta esté activa, que tenga perfil y que tenga un solo rol. Como en el 08, el superusuario actúa como la Q.F.: no tiene «Mis entregas» ni reordena rutas, porque esas acciones son del encargado asignado (comprobación exacta del rol). **El Técnico no ve «Rutas», por decisión del usuario.** Esto difiere de la matriz del 08, donde el Técnico consulta las entregas. Sí ve el mapa del domicilio, que forma parte de una página que ya consulta.

## Alcance y exclusiones

**Incluye:**
- Orden sugerido calculado en el servidor:
  - distancia en línea recta (haversine), vecino más cercano y mejora 2-opt;
  - el recorrido sale del punto de partida, pasa por todas las paradas con coordenadas y vuelve al CESFAM;
  - tras cada visita registrada hoy, el orden se recalcula desde ese domicilio.
- Ruta del día del encargado: sus visitas de hoy y las atrasadas, sin resultado. Las que no tienen coordenadas van al final, rotuladas.
- Orden manual guardado por encargado y día. Las visitas que se agregan después entran en el lugar que menos alarga el recorrido, con un aviso. Incluye «Volver al orden sugerido».
- Sección «Registradas hoy» con el resultado de cada visita.
- Pestaña «Mapa»:
  - Leaflet copiado en el proyecto y teselas de OpenStreetMap configurables;
  - marcadores numerados, el CESFAM y las visitas registradas;
  - la línea recta punteada y el total aproximado en km.
- «Ir a esta parada»: sigue la posición en el celular hasta que el encargado la detiene. Muestra la distancia en línea recta y la dirección. Ofrece un enlace `geo:` secundario y las coordenadas en texto.
- Pestaña «Rutas» para la Q.F. y el superusuario, solo de consulta, por encargado y fecha (hoy o posterior).
- Mapa pequeño de solo lectura en la página del domicilio del 08.
- Origen del recorrido (CESFAM) y cartografía configurables en `.env`.
- Comando `generar_domicilios_demo`, que crea domicilios sintéticos con coordenadas para la demostración.

**Fuera de este spec:**
- Ruta por caminos y tiempos de viaje. Un motor de rutas propio u otro proveedor queda como mejora futura.
- Enviar o guardar en el servidor la posición del encargado, y el seguimiento de vehículos en tiempo real (fuera de alcance del informe).
- Ajustar las coordenadas tocando o arrastrando el mapa. Se siguen ingresando como en el 08.
- Mapa base sin conexión, caché de teselas y registro sin conexión: reserva 11. Además, la política de uso de OpenStreetMap prohíbe las descargas masivas.
- Imagen satelital y otros proveedores. La URL de las teselas es configurable, pero el spec solo prueba OpenStreetMap.
- Orden manual de días futuros, reordenamiento por la Q.F. y reparto automático de entregas por zona entre encargados.
- Notificación de «en camino» (reserva 12) y panel de mermas (spec 10).
- Programar entregas de demostración: el comando solo crea domicilios.
- Cambios en las reglas, modelos y servicios del 08 (programación, registro, doble vía y domicilios). Integración con Rayén (RNF-07).

## Historias y flujo

1. **Lista ordenada (HU-14).** El encargado abre «Mis entregas». Ve un rótulo que dice de dónde sale el orden: «Orden sugerido desde el CESFAM, según distancia en línea recta; no considera caminos» o «Tu orden de hoy, guardado a las 08:12». Le siguen las paradas numeradas (hoy y atrasadas juntas; la atrasada conserva su rótulo) y las visitas sin coordenadas, agrupadas por sector y localidad. Al final aparecen «Registradas hoy» y «Próximas», estas últimas sin número, como en el 08.
2. **Recálculo.** El encargado registra una visita con el flujo del 08 y vuelve a la lista. Si no guardó un orden propio, las paradas pendientes se recalculan desde el domicilio que acaba de registrar.
3. **Orden propio.** Con «Subir», «Bajar» o «Mover a la posición», el encargado cambia el orden y se guarda. Desde ese momento manda su orden: registrar visitas ya no lo recalcula. Si la Q.F. le agrega una visita para hoy, aparece donde menos alarga el recorrido, rotulada «Nueva: no estaba en tu orden». Con «Volver al orden sugerido» descarta su orden.
4. **Mapa.** La pestaña «Mapa» muestra la ruta con marcadores numerados y la línea punteada. Cada marcador abre un resumen con enlaces a «Registrar», «Ir a esta parada» y «Ver domicilio».
5. **Ir a esta parada.** El encargado pulsa «Mostrar mi posición». Ve su punto, la línea recta hasta la parada y un texto como «La parada 3 está a 1,2 km hacia el noreste». Al llegar, o con «Detener», el seguimiento termina. Si prefiere indicaciones por camino, usa «Abrir en app de navegación».
6. **Rutas (Q.F.).** En **Entregas › Rutas**, la Q.F. elige un encargado y una fecha. Ve la misma lista y el mismo mapa que vería el encargado, con el rótulo del tipo de orden, sin botones de cambio. Para hoy, incluye también las atrasadas y las registradas hoy.
7. **Domicilio.** En la página de un domicilio con coordenadas aparece un mapa pequeño con su punto.

## Requisitos funcionales

- **RF-09-01 — Ruta del día:** EL SISTEMA arma la ruta de hoy de un encargado con sus intentos sin resultado y fecha programada igual o anterior a hoy (hoy y atrasadas). Los intentos de fechas posteriores siguen en «Próximas», sin número ni marcador. Para una fecha futura, que solo consulta la Q.F., la ruta tiene los intentos sin resultado programados para esa fecha. Nunca incluye intentos de otro encargado ni intentos reasignados o anulados.
- **RF-09-02 — Orden sugerido:** CUANDO el encargado no tiene un orden guardado para hoy, EL SISTEMA ordena las paradas con coordenadas para reducir la longitud en línea recta de un recorrido que sale del punto de partida, pasa por todas y termina en el CESFAM. Usa la distancia haversine, el vecino más cercano y la mejora 2-opt. Desempata por el identificador del intento, de modo que los mismos datos dan siempre el mismo orden. El punto de partida es el domicilio con coordenadas de la última visita que el encargado registró hoy como «entregada» o «no entregada»; si no hay ninguna, es el CESFAM. La lista y el mapa muestran «Orden sugerido según distancia en línea recta; no considera caminos» y el total aproximado en km.
- **RF-09-03 — Visitas sin coordenadas:** SI el paciente de una visita no tiene domicilio o su domicilio no tiene coordenadas, ENTONCES la visita no entra al cálculo. En el orden sugerido aparece después de las paradas numeradas, agrupada por sector y localidad y rotulada «Sin coordenadas: fuera del orden sugerido». El mapa indica con texto cuántas visitas no tienen marcador.
- **RF-09-04 — Orden manual:** CUANDO el encargado sube, baja o mueve a una posición una visita de su ruta de hoy, EL SISTEMA guarda el orden completo de esa ruta para ese encargado y ese día, con quién y cuándo. Puede ubicar las visitas sin coordenadas en cualquier posición; ahí quedan numeradas, sin marcador y con el rótulo «Sin coordenadas». Desde entonces manda ese orden: no se recalcula al registrar visitas, y las registradas salen de las paradas sin alterar el orden relativo de las demás. SI dos dispositivos guardan desde la misma versión, ENTONCES el segundo recibe «Tu orden cambió en otro dispositivo; revisa la lista.» y no sobrescribe nada. Repetir el mismo POST no mueve dos veces. El orden guardado vale solo ese día: al día siguiente, la ruta parte con la sugerencia.
- **RF-09-05 — Visitas nuevas en un orden guardado:** SI la ruta de hoy tiene una visita que no está en el orden guardado (programada o reasignada después de guardarlo), ENTONCES EL SISTEMA la muestra en la posición donde menos alarga el recorrido en línea recta (inserción más barata), sin mover las demás, rotulada «Nueva: no estaba en tu orden». Si no tiene coordenadas, va al final con el mismo rótulo. Al guardar de nuevo el orden, las nuevas quedan incorporadas y pierden el rótulo. Las visitas del orden guardado que salieron de la ruta (registradas, reasignadas o anuladas) desaparecen de él.
- **RF-09-06 — Volver al orden sugerido:** CUANDO el encargado confirma «Volver al orden sugerido», EL SISTEMA descarta su orden de hoy y la ruta vuelve a ordenarse según RF-09-02.
- **RF-09-07 — Registradas hoy:** EL SISTEMA muestra aparte al encargado las visitas que registró hoy, con su resultado («Entregada» o «No entregada: motivo») y la hora. En el mapa aparecen con un marcador sin número, de forma distinta a la de las paradas pendientes y con su resultado en texto. Las registradas otros días no aparecen.
- **RF-09-08 — Mapa:** EL SISTEMA muestra en la pestaña «Mapa»:
  - el mapa base configurado (por defecto, OpenStreetMap con su atribución visible);
  - el marcador del CESFAM;
  - los marcadores numerados de las paradas, con el mismo número de la lista, y los de las visitas registradas hoy;
  - una línea recta punteada desde el punto de partida, por las paradas en orden, hasta el CESFAM, con la leyenda «Recorrido en línea recta; no sigue los caminos» y el total aproximado en km.

  Cada marcador abre un resumen con número, estado, sector, localidad, dirección y referencias, y enlaces a «Registrar» (si corresponde), «Ir a esta parada» y «Ver domicilio». SI el mapa base no carga (sin señal o bloqueado), ENTONCES los marcadores y la línea se mantienen y un texto lo avisa. La lista sigue siendo la alternativa completa y accesible al mapa.
- **RF-09-09 — Ir a esta parada:** CUANDO el encargado pulsa «Mostrar mi posición» en una parada con coordenadas, EL NAVEGADOR pide la ubicación con ese gesto y la sigue hasta que pulsa «Detener» o sale de la página. Muestra su punto con su precisión, la línea recta hasta la parada, la distancia («850 m», «1,2 km») y la dirección en ocho rumbos («hacia el noreste»). La posición nunca se envía al servidor ni se guarda. El lector de pantalla recibe el aviso al iniciar, al pulsar «Leer distancia» y al quedar a menos de 100 m de la parada. SI no hay contexto seguro, el permiso fue denegado o no hay posición, ENTONCES lo explica con texto y quedan disponibles el enlace y las coordenadas. Siempre se ofrecen el enlace secundario «Abrir en app de navegación» (`geo:latitud,longitud`) y las coordenadas en texto. Una parada sin coordenadas no ofrece esta guía.
- **RF-09-10 — Rutas de la Q.F.:** CUANDO la Q.F. o el superusuario eligen un encargado activo y una fecha igual o posterior a hoy, EL SISTEMA muestra, solo para consultar, la lista y el mapa de esa ruta tal como los vería el encargado: orden guardado o sugerido, con su rótulo, y para hoy también las atrasadas y las registradas hoy. No muestra acciones de cambio ni «Ir a esta parada». SI la fecha es pasada o el encargado no es válido, ENTONCES lo rechaza con texto.
- **RF-09-11 — Mapa del domicilio:** EL SISTEMA muestra en la página del domicilio del 08, si tiene coordenadas, un mapa pequeño de solo lectura con su marcador y su precisión. Sin coordenadas, mantiene el texto actual.
- **RF-09-12 — Origen y cartografía configurables:** EL SISTEMA lee de la configuración el origen del recorrido (latitud y longitud del CESFAM), la URL de las teselas, su atribución y el zoom máximo. Sin variables, usa los valores de demostración documentados. SI un valor configurado no es válido (coordenada fuera de rango o URL sin `{z}`, `{x}` e `{y}`), ENTONCES `python manage.py check` informa un error claro. Leaflet se sirve desde los estáticos del proyecto, sin CDN.
- **RF-09-13 — Domicilios de demostración:** EL COMANDO `generar_domicilios_demo` crea domicilios sintéticos para los pacientes elegibles que aún no tienen uno. Cada domicilio tiene coordenadas aleatorias reproducibles dentro de un radio configurable alrededor del origen, más sector, localidad, dirección y referencias sintéticas. Solo escribe con la opción explícita `--aplicar` y una cuenta de Q.F. o superusuario indicada, y lo hace mediante el servicio auditado del 08. Sin `--aplicar`, solo informa lo que haría. No verifica domicilios, no modifica los existentes y no programa entregas.
- **RF-09-14 — Permisos, privacidad y auditoría:** EL SISTEMA:
  - aplica la matriz de permisos en el servidor;
  - exige POST con CSRF para todo cambio;
  - responde sin caché (`no-store`);
  - pone en las URL solo identificadores internos y fechas, nunca RUT ni nombres;
  - no incluye el RUT en los datos del mapa;
  - pide las teselas con un referente reducido al origen del sitio, sin la ruta de la página;
  - no envía a terceros nombres, direcciones ni coordenadas de pacientes; las teselas que pide el navegador solo revelan al proveedor el área visible del mapa.

  La auditoría registra quién guardó un orden y quién volvió al sugerido, con identificadores y sin datos personales. Si la auditoría falla, la operación se revierte.
- **RF-09-15 — Concurrencia y compatibilidad:** EL SISTEMA:
  - mantiene un solo orden guardado por encargado y día, aun con primeras ediciones simultáneas;
  - acepta una sola de dos ediciones hechas desde la misma versión;
  - no duplica ni pierde visitas al reordenar mientras se registra o se reasigna una visita;
  - no cambia las reglas del 08: programación, registro, doble vía y domicilios.

  Las pruebas del 03 al 07 pasan sin cambios. Las del 08 que fijan el orden o las secciones de «Mis entregas» solo se ajustan por RF-09-01 a RF-09-07, y el plan las lista.

## Datos y reglas

- **Ruta del día:** se calcula en cada consulta a partir de los intentos del 08 y del orden guardado, si existe. El orden sugerido no se guarda.
- **Orden guardado:** uno por encargado y fecha, con la secuencia de intentos (posiciones 1..n), una versión para la edición concurrente, el identificador de la última operación aplicada y quién lo guardó y cuándo. No guarda coordenadas ni datos del paciente. Se puede reemplazar o vaciar. El principio del 08 de no borrar nada protege el historial de entregas e intentos, no esta preferencia de orden.
- **Distancia:** haversine con radio terrestre de 6.371 km. Bajo 1 km se muestra en metros, redondeada a 10 m; desde 1 km, en km con un decimal y coma decimal.
- **Rumbo:** ocho direcciones desde la posición hacia la parada: norte, noreste, este, sureste, sur, suroeste, oeste y noroeste.
- **Coordenadas:** las del domicilio del 08 (6 decimales). Este spec no las modifica.
- **Jornada:** «hoy» y «registradas hoy» usan `America/Santiago`, como el 08.
- **Origen y cartografía:** `REPARTO_ORIGEN_LATITUD`, `REPARTO_ORIGEN_LONGITUD`, `MAPA_TESELAS_URL`, `MAPA_TESELAS_ATRIBUCION` y `MAPA_ZOOM_MAXIMO`, leídas de `.env`. Por defecto, el origen es un valor de demostración aproximado del centro de San Nicolás, rotulado como tal, que el equipo reemplaza por el punto exacto del CESFAM. Las teselas son las de OpenStreetMap, con la atribución «© colaboradores de OpenStreetMap».
- **Datos sintéticos:** el padrón de 670 pacientes de demostración y domicilios generados con coordenadas aleatorias. Una coordenada sintética no representa ninguna vivienda real.

## Criterios de aceptación

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-09-01 | Un encargado con 3 intentos de hoy, 1 de ayer sin resultado y 1 de mañana; otro encargado con 2 de hoy | La ruta tiene 4 paradas (la de ayer, rotulada «Atrasada desde el dd/mm»); la de mañana está en «Próximas» sin número; no aparecen las del otro encargado. |
| RF-09-02 | Origen O y paradas A, B y C sobre una línea, a 3, 1 y 2 km de O | Orden B, C, A; total = ida y vuelta en línea recta. |
| RF-09-02 | Un caso de prueba en que el vecino más cercano cruza su recorrido | La mejora 2-opt da un recorrido más corto, sin cruces; igual al óptimo calculado por fuerza bruta. |
| RF-09-02 | Repetir el cálculo; registrar B como «entregada» | Mismo orden en cada repetición; después, el resto se ordena desde B. |
| RF-09-03 | Una visita con domicilio sin coordenadas y otra sin domicilio | Ambas después de las numeradas, agrupadas y rotuladas; el mapa dice «2 visitas sin marcador». |
| RF-09-04 | Bajar la parada 1; luego registrar la nueva parada 1 | Se guarda el orden; registrar no lo recalcula y las demás conservan su orden relativo. |
| RF-09-04 | Dos guardados desde la misma versión; repetir el mismo POST; mover una visita sin coordenadas a la posición 1 | Uno gana y el otro recibe el aviso; el reenvío no mueve otra vez; la visita sin coordenadas queda primera, numerada y sin marcador. |
| RF-09-04 | Al día siguiente; POST de otro encargado, de la Q.F., del superusuario y del Técnico | La ruta vuelve a la sugerencia; los cuatro POST se rechazan sin cambios. |
| RF-09-05 | Orden guardado A, B, C; la Q.F. reasigna a este encargado, para hoy, una visita D ubicada entre A y B; luego una visita E sin coordenadas; luego anula B | Se muestra A, D («Nueva»), B, C, E («Nueva»); tras anular, B desaparece; al guardar de nuevo, sin rótulos. |
| RF-09-06 | Volver al orden sugerido | La ruta se muestra en el orden sugerido; queda en la auditoría. |
| RF-09-07 | Registrar una «entregada» y una «no entregada» hoy; existe una registrada ayer | «Registradas hoy» muestra las dos de hoy con resultado, motivo y hora, sin número; la de ayer no aparece. |
| RF-09-08 | Abrir «Mapa» con 5 paradas, 1 sin coordenadas y 2 registradas | Los datos del mapa traen 4 paradas numeradas como la lista, 2 registradas, el CESFAM, la línea y el total en km, sin RUT; la atribución es visible; con teselas que fallan, aparece el aviso y los marcadores siguen. |
| RF-09-09 | Pruebas de JavaScript con posición simulada; permiso denegado; contexto no seguro; «Detener»; salir de la página | Distancia y rumbo correctos en puntos conocidos; textos de error; el seguimiento termina; el módulo no hace ninguna solicitud de red con la posición. |
| RF-09-10 | La Q.F. elige al encargado X para hoy, para mañana y para ayer; el Técnico y un encargado abren «Rutas» | Hoy: mismo orden y rótulo que ve X; mañana: sugerido desde el CESFAM solo con las de esa fecha; ayer: rechazo con texto; Técnico y encargado: acceso rechazado. |
| RF-09-11 | Domicilio con coordenadas; domicilio sin coordenadas | Mapa pequeño con el marcador; texto «Sin coordenadas». |
| RF-09-12 | Sin variables; latitud 95; URL sin `{z}` | Valores de demostración; `check` informa un error claro en los dos últimos casos; ningún HTML carga recursos desde un CDN. |
| RF-09-13 | Ejecutar sin `--aplicar`; con `--aplicar` y una cuenta Q.F. dos veces con la misma semilla; con una cuenta Técnico | Sin cambios; domicilios sintéticos creados una sola vez (la segunda no toca los existentes), dentro del radio, no verificados y auditados; rechazo. |
| RF-09-14 | Anónimo, cuenta inactiva o sin perfil, POST sin CSRF y URL de «Rutas» manipulada | Acceso rechazado; ninguna acción se ejecuta; respuestas `no-store`; las teselas usan `referrerPolicy` de solo origen; auditoría sin RUT, nombres, direcciones ni coordenadas. |
| RF-09-15 | Al menos tres escenarios concurrentes con hilos y conexiones separadas | Un orden por encargado y día; una edición ganadora; ninguna visita duplicada ni perdida al reordenar mientras se registra o reasigna; las pruebas del 03 al 07 pasan sin cambios. |

## No funcionales

- Solo datos sintéticos y ORM de Django, sin SQL crudo. Compatible con PostgreSQL y con la SQLite temporal de las herramientas. La concurrencia no usa `select_for_update()`, sino un UPDATE condicional por versión, restricciones únicas, transacciones y reintentos acotados (RNF-02). Los UPDATE condicionales filtran solo campos propios (regla de PostgreSQL de `CLAUDE.md`).
- Respuesta de 2 s o menos en el p95 (RNF-05) para «Mis entregas», «Mapa», «Ir a esta parada», «Rutas» y las acciones de orden, con el padrón de 670 pacientes y al menos 50 visitas por encargado. Se mide aparte el tiempo del cálculo con 200 paradas.
- WCAG 2.1 AA (RNF-04):
  - la lista numerada es la vista principal y accesible, y el mapa la complementa;
  - el mapa tiene un enlace para saltarlo, nombre accesible y marcadores accesibles por teclado con nombre («Parada 3, pendiente»);
  - número, estado y tipo se comunican con texto y forma, no solo con color, y marcadores y línea tienen un contraste de 3:1 o más con el fondo;
  - botones de 48 px o más, foco visible, sin desplazamiento horizontal y avisos con `aria-live="polite"`.

  La revisión de navegador, axe y la usabilidad con cinco personas requieren evidencia propia.
- Privacidad (RNF-01): la posición del encargado vive solo en su navegador y el seguimiento se detiene al salir de la página. Los datos del mapa solo aparecen en vistas privadas autorizadas.
- Compatibilidad (RNF-09): navegadores actuales de escritorio y de celular. La ubicación del navegador exige HTTPS o `localhost`; sin ello, «Ir a esta parada» lo explica y deja el enlace y las coordenadas.
- Cartografía: Leaflet 1.9.4 se copia con su licencia (BSD-2-Clause) en los estáticos. Las teselas son la primera solicitud del navegador a un tercero. Se cumple la política de uso de OpenStreetMap: atribución visible, sin descarga masiva y referente de origen. Para una implementación real, el DESAMU elige el proveedor.

## Compatibilidad

Este spec no cambia los modelos, servicios ni reglas del 08. Agrega una consulta de ruta, un modelo de orden manual y sus servicios, y cambia la presentación de «Mis entregas»:

- `entregasapp`:
  - la vista «Mis entregas» pasa a presentar la ruta numerada, «Registradas hoy» y «Próximas»;
  - `consultas.mis_entregas` y `contar_mis_entregas` se conservan;
  - el registro de resultados, la programación, la reasignación y la anulación siguen igual;
  - la página del domicilio suma el mapa pequeño.
- `coreapp/navegacion.py`: las páginas nuevas del encargado marcan activa la entrada «Mis entregas»; no hay entradas nuevas en el menú.
- `cesfam/settings.py` y `.env.example`: variables nuevas con valores por defecto.

Las pruebas del 03 al 07 pasan sin cambios. Las del 08 que comprueban el orden o las secciones de «Mis entregas» se ajustan solo por este spec y quedan listadas en `plan.md` al implementar.

Preparación para otros specs:
- **Reserva 11 (sin conexión):** deberá decidir cómo guardar en caché la página de la ruta y su mapa base. La política de OpenStreetMap limita la descarga de teselas, así que probablemente haga falta otro proveedor o teselas propias.
- **Reserva 12 (notificaciones):** podrá usar el orden de la ruta para avisar «en camino».

Las dependencias existen en `specs/`. Sus pendientes de aceptación visual y funcional no se dan por cerrados aquí.

## Decisiones tomadas y alternativas

- **Leaflet y OpenStreetMap** (decisión del usuario, recomendada). Gratis, sin clave y con URL configurable. Se descartan la imagen satelital (condiciones más restrictivas, cuenta o clave) y un plano SVG propio (sin caminos ni referencias).
- **Línea recta, vecino más cercano y 2-opt, con vuelta al CESFAM** (decisión del usuario, recomendada). Determinista y probado en el servidor. Se descarta un servicio de rutas por camino: suma un proveedor con clave o límites, envía coordenadas de pacientes a un tercero y cartografía mal los caminos rurales. También se descarta solo agrupar por sector, porque no reduce el recorrido.
- **Partida en el CESFAM y recálculo desde la última visita registrada** (decisión del usuario, recomendada). No usa la posición del celular para ordenar. Se descartan el orden fijo desde el CESFAM y el orden desde la ubicación del celular.
- **Pestaña «Mapa» y lista numerada como vista principal** (decisión del usuario, recomendada). Se descartan el mapa sobre la lista (más pesado con mala señal) y una página aparte.
- **Hoy y atrasadas en la ruta** (decisión del usuario, recomendada).
- **Sin coordenadas al final, rotuladas** (decisión del usuario, recomendada). Se descarta asignarles una ubicación aproximada, que puede inducir a error.
- **«Rutas» para la Q.F., por encargado** (decisión del usuario; se recomendaba solo el encargado). Consecuencia: una pestaña nueva de solo consulta para la Q.F. y el superusuario.
- **El Técnico no ve «Rutas»** (decisión del usuario; se recomendaba incluirlo como en el 08).
- **Mapa del domicilio solo para ver** (decisión del usuario, recomendada). Se descarta ajustar el punto arrastrando el marcador.
- **Guía «Ir a esta parada» dentro de la PWA** (propuesta del usuario, que reemplaza el enlace `geo:` como única guía). La posición se obtiene en el celular con un gesto y nunca va al servidor. El encargado ve la distancia en línea recta y la dirección; el enlace `geo:` y las coordenadas en texto quedan como apoyo. La ruta por caminos con un motor propio queda como mejora futura. No contradice la exclusión del informe sobre la «geolocalización satelital en tiempo real de los vehículos», porque nadie fuera del celular conoce la posición: no hay seguimiento.
- **Seguir la posición hasta detenerla** (decisión del usuario, recomendada). Se descarta tomarla una vez por toque.
- **Orden manual guardado** (decisión del usuario; se recomendaba solo la sugerencia). Consecuencias: un modelo nuevo, una migración, pruebas concurrentes y reglas para las visitas que llegan después.
- **Visitas nuevas en el lugar más barato, con aviso** (decisión del usuario, que combina la inserción más barata con el rótulo «Nueva»). Se descarta agregarlas siempre al final.
- **Visitas sin coordenadas ubicables en el orden manual** (decisión del usuario, recomendada): el encargado conoce el lugar.
- **Origen en `.env`** (decisión del usuario, recomendada). Se descartan fijarlo en el código y una pantalla de configuración.
- **«Registradas hoy» aparte** (decisión del usuario, recomendada). Cumple el «registro de las entregas del día» y el «estado» de HU-14.
- **Línea recta punteada con total en km** (decisión del usuario, recomendada).
- **Subir, Bajar y Mover a la posición** (decisión del usuario, recomendada). Funciona con teclado, lector de pantalla y sin JavaScript. Se descarta arrastrar y soltar.
- **Comando de demostración solo para domicilios** (decisión del usuario, recomendada). Las entregas de la demostración se programan con la pantalla del 08.

## Supuestos y decisiones pendientes

Supuestos técnicos reversibles, sujetos a la revisión del borrador:
- El rótulo «Nueva» se quita la próxima vez que el encargado guarda su orden (cualquier movimiento). No hay un botón «Dejar aquí».
- «Volver al orden sugerido» existe aunque la opción elegida para las visitas nuevas no lo mencionaba, porque sin él no se podría salir del orden manual hasta el día siguiente.
- La inserción más barata se calcula al mostrar la ruta, sobre las paradas pendientes del orden guardado, desde el punto de partida hasta el CESFAM. No se escribe en un GET ni en los servicios del 08. Por eso, la posición sugerida de una visita «Nueva» puede cambiar después de registrar otra visita.
- El orden manual existe solo para hoy. La Q.F. no reordena. «Rutas» no muestra días pasados porque el orden sugerido no se guarda.
- El resumen de cada marcador incluye el nombre y la dirección del paciente, igual que la lista, pero nunca el RUT.
- La mejora 2-opt se aplica hasta 200 paradas; con más, se usa solo el vecino más cercano y se indica con texto.
- «Ir a esta parada» es una página por parada (`/entregas/mis/ir/<intento>/`) para las paradas de la ruta de hoy con coordenadas.
- El radio por defecto del comando de demostración es de 15 km alrededor del origen, con localidades sintéticas rotuladas como de demostración, no nombres reales de lugares.
- Leaflet 1.9.4; nombres de modelos, rutas y archivos son propuestas de `plan.md`.

No hay bloqueos críticos para redactar. Queda por confirmar el valor exacto del origen (el CESFAM) antes de la demostración.

## Revisión y cambios

2026-11-11 y 2026-11-12: cuatro bloques de preguntas.
1. Mapa base, cálculo del orden, punto de partida y pantalla.
2. Visitas incluidas, visitas sin coordenadas, vista de la Q.F. y mapa del domicilio.
3. Guía hacia la parada, orden manual, datos de demostración y permisos de «Rutas».
4. Seguimiento de la posición, visitas nuevas en un orden guardado, visitas sin coordenadas en el orden manual, origen, «Registradas hoy», línea del recorrido, controles para reordenar y alcance del comando.

Se guardan los cuatro documentos como Borrador, sin código ni migraciones.
