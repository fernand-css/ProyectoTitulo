# SPEC 09 — Mapa y orden de visita

> **Estado:** Aprobado
> **Depende de:** [SPEC 01](../01-base-del-proyecto/spec.md), [SPEC 02](../02-autenticacion-roles-auditoria/spec.md), [SPEC 03](../03-padron-y-recetas/spec.md) y [SPEC 08](../08-domicilios-y-entregas/spec.md)
> **Fecha:** 2026-11-12
> **Enmienda:** 2026-11-15, **Aprobada** por el usuario el mismo día, tras revisar el lienzo de diseño («Apruebo todos los cambios»); implementación pendiente (ver [Enmienda del 2026-11-15](#enmienda-del-2026-11-15-borrador); el título de la sección conserva «Borrador» para no romper los enlaces, y manda esta cabecera). Revierte tres decisiones: el recorrido en línea recta (pasa a rutas por camino con un OSRM propio), la exclusión del arrastre y la exclusión de elegir coordenadas en el mapa. Modifica RF-09-02, RF-09-04, RF-09-05, RF-09-08, RF-09-09, RF-09-10, RF-09-12 y RF-09-14 y agrega RF-09-16 a RF-09-26. Desde su aprobación, la enmienda reemplaza lo que se le opone de la versión del 2026-11-12.
> **Objetivo:** Mostrar al encargado de terreno sus visitas del día en una lista numerada y en un mapa, con un orden de visita sugerido que puede ajustar y guardar y una guía hacia cada parada calculada solo en su celular, y permitir a la Q.F. consultar el mapa y el orden de cada encargado.

Módulo: `entregasapp` (orden de visita, mapa y rutas), con cambios acotados en `cesfam/settings.py` (origen y cartografía), `coreapp/navegacion.py` (páginas activas) y los estáticos (Leaflet local). Fuente: HU-14 y la parte de HU-12 que pide identificar los domicilios en un mapa; RNF-01/04/05/09; §2.1 y §5 del [informe](../../docs/Informe.md); respuestas del usuario del 2026-11-11 y 2026-11-12.
Implementación autorizada: sí, el 2026-11-12 (`/spec-impl 09-mapa-y-orden-de-visita` en `crojas-base`, todos los pasos). Revisión del usuario: Aprobado; aceptación funcional pendiente.

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
- Ruta por caminos y tiempos de viaje. Un motor de rutas propio u otro proveedor queda como mejora futura. *(Enmienda 2026-11-15: se revierte para las distancias y los tramos por camino, con un OSRM propio; ver RF-09-19 a RF-09-23. Los tiempos de viaje siguen fuera.)*
- Enviar o guardar en el servidor la posición del encargado, y el seguimiento de vehículos en tiempo real (fuera de alcance del informe).
- Ajustar las coordenadas tocando o arrastrando el mapa. Se siguen ingresando como en el 08. *(Enmienda 2026-11-15: se revierte con «Usar mapa» en el formulario del domicilio; ver RF-09-25. El mapa pequeño de la página del domicilio sigue siendo de solo lectura.)*
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
- **RF-09-02 — Orden sugerido:** CUANDO el encargado no tiene un orden guardado para hoy, EL SISTEMA ordena las paradas con coordenadas para reducir la longitud en línea recta de un recorrido que sale del punto de partida, pasa por todas y termina en el CESFAM. Usa la distancia haversine, el vecino más cercano y la mejora 2-opt. Desempata por el identificador del intento, de modo que los mismos datos dan siempre el mismo orden. El punto de partida es el domicilio con coordenadas de la última visita que el encargado registró hoy como «entregada» o «no entregada»; si no hay ninguna, es el CESFAM. La lista y el mapa muestran «Orden sugerido según distancia en línea recta; no considera caminos» y el total aproximado en km. *(Enmienda 2026-11-15: la distancia pasa a ser por camino, con la matriz de OSRM, y la línea recta queda solo como respaldo rotulado; ver RF-09-20.)*
- **RF-09-03 — Visitas sin coordenadas:** SI el paciente de una visita no tiene domicilio o su domicilio no tiene coordenadas, ENTONCES la visita no entra al cálculo. En el orden sugerido aparece después de las paradas numeradas, agrupada por sector y localidad y rotulada «Sin coordenadas: fuera del orden sugerido». El mapa indica con texto cuántas visitas no tienen marcador.
- **RF-09-04 — Orden manual:** CUANDO el encargado sube, baja o mueve a una posición una visita de su ruta de hoy, EL SISTEMA guarda el orden completo de esa ruta para ese encargado y ese día, con quién y cuándo. Puede ubicar las visitas sin coordenadas en cualquier posición; ahí quedan numeradas, sin marcador y con el rótulo «Sin coordenadas». Desde entonces manda ese orden: no se recalcula al registrar visitas, y las registradas salen de las paradas sin alterar el orden relativo de las demás. SI dos dispositivos guardan desde la misma versión, ENTONCES el segundo recibe «Tu orden cambió en otro dispositivo; revisa la lista.» y no sobrescribe nada. Repetir el mismo POST no mueve dos veces. El orden guardado vale solo ese día: al día siguiente, la ruta parte con la sugerencia. *(Enmienda 2026-11-15: se retira «Mover a la posición»; el orden se cambia con las flechas o con la franja de arrastre, por el mismo servicio y las mismas garantías; ver RF-09-17.)*
- **RF-09-05 — Visitas nuevas en un orden guardado:** SI la ruta de hoy tiene una visita que no está en el orden guardado (programada o reasignada después de guardarlo), ENTONCES EL SISTEMA la muestra en la posición donde menos alarga el recorrido en línea recta (inserción más barata), sin mover las demás, rotulada «Nueva: no estaba en tu orden». Si no tiene coordenadas, va al final con el mismo rótulo. Al guardar de nuevo el orden, las nuevas quedan incorporadas y pierden el rótulo. Las visitas del orden guardado que salieron de la ruta (registradas, reasignadas o anuladas) desaparecen de él. *(Enmienda 2026-11-15: la inserción más barata usa la distancia por camino; ver RF-09-20.)*
- **RF-09-06 — Volver al orden sugerido:** CUANDO el encargado confirma «Volver al orden sugerido», EL SISTEMA descarta su orden de hoy y la ruta vuelve a ordenarse según RF-09-02.
- **RF-09-07 — Registradas hoy:** EL SISTEMA muestra aparte al encargado las visitas que registró hoy, con su resultado («Entregada» o «No entregada: motivo») y la hora. En el mapa aparecen con un marcador sin número, de forma distinta a la de las paradas pendientes y con su resultado en texto. Las registradas otros días no aparecen.
- **RF-09-08 — Mapa:** EL SISTEMA muestra en la pestaña «Mapa»:
  - el mapa base configurado (por defecto, OpenStreetMap con su atribución visible);
  - el marcador del CESFAM;
  - los marcadores numerados de las paradas, con el mismo número de la lista, y los de las visitas registradas hoy;
  - una línea recta punteada desde el punto de partida, por las paradas en orden, hasta el CESFAM, con la leyenda «Recorrido en línea recta; no sigue los caminos» y el total aproximado en km.

  Cada marcador abre un resumen con número, estado, sector, localidad, dirección y referencias, y enlaces a «Registrar» (si corresponde), «Ir a esta parada» y «Ver domicilio». SI el mapa base no carga (sin señal o bloqueado), ENTONCES los marcadores y la línea se mantienen y un texto lo avisa. La lista sigue siendo la alternativa completa y accesible al mapa. *(Enmienda 2026-11-15: se quitan la línea recta punteada del recorrido completo y su leyenda; el total pasa a ser por camino y el mapa del encargado dibuja solo el tramo desde su posición; «Ver domicilio» pasa a «Detalles del domicilio». Ver RF-09-20, RF-09-21 y RF-08-20.)*
- **RF-09-09 — Ir a esta parada:** CUANDO el encargado pulsa «Mostrar mi posición» en una parada con coordenadas, EL NAVEGADOR pide la ubicación con ese gesto y la sigue hasta que pulsa «Detener» o sale de la página. Muestra su punto con su precisión, la línea recta hasta la parada, la distancia («850 m», «1,2 km») y la dirección en ocho rumbos («hacia el noreste»). La posición nunca se envía al servidor ni se guarda. El lector de pantalla recibe el aviso al iniciar, al pulsar «Leer distancia» y al quedar a menos de 100 m de la parada. SI no hay contexto seguro, el permiso fue denegado o no hay posición, ENTONCES lo explica con texto y quedan disponibles el enlace y las coordenadas. Siempre se ofrecen el enlace secundario «Abrir en app de navegación» (`geo:latitud,longitud`) y las coordenadas en texto. Una parada sin coordenadas no ofrece esta guía. *(Enmienda 2026-11-15: reemplazado por RF-09-23. La distancia es la del tramo por camino, se quitan la línea recta y el rumbo, y la posición se envía a Django solo para calcular el tramo.)*
- **RF-09-10 — Rutas de la Q.F.:** CUANDO la Q.F. o el superusuario eligen un encargado activo y una fecha igual o posterior a hoy, EL SISTEMA muestra, solo para consultar, la lista y el mapa de esa ruta tal como los vería el encargado: orden guardado o sugerido, con su rótulo, y para hoy también las atrasadas y las registradas hoy. No muestra acciones de cambio ni «Ir a esta parada». SI la fecha es pasada o el encargado no es válido, ENTONCES lo rechaza con texto. *(Enmienda 2026-11-15: tarjetas compactas en modo consulta y mapa solo con marcadores, sin línea ni tramos; ver RF-09-24.)*
- **RF-09-11 — Mapa del domicilio:** EL SISTEMA muestra en la página del domicilio del 08, si tiene coordenadas, un mapa pequeño de solo lectura con su marcador y su precisión. Sin coordenadas, mantiene el texto actual.
- **RF-09-12 — Origen y cartografía configurables:** EL SISTEMA lee de la configuración el origen del recorrido (latitud y longitud del CESFAM), la URL de las teselas, su atribución y el zoom máximo. Sin variables, usa los valores de demostración documentados. SI un valor configurado no es válido (coordenada fuera de rango o URL sin `{z}`, `{x}` e `{y}`), ENTONCES `python manage.py check` informa un error claro. Leaflet se sirve desde los estáticos del proyecto, sin CDN. *(Enmienda 2026-11-15: se agregan la dirección y el tiempo de espera de OSRM, con sus comprobaciones; ver RF-09-19.)*
- **RF-09-13 — Domicilios de demostración:** EL COMANDO `generar_domicilios_demo` crea domicilios sintéticos para los pacientes elegibles que aún no tienen uno. Cada domicilio tiene coordenadas aleatorias reproducibles dentro de un radio configurable alrededor del origen, más sector, localidad, dirección y referencias sintéticas. Solo escribe con la opción explícita `--aplicar` y una cuenta de Q.F. o superusuario indicada, y lo hace mediante el servicio auditado del 08. Sin `--aplicar`, solo informa lo que haría. No verifica domicilios, no modifica los existentes y no programa entregas.
- **RF-09-14 — Permisos, privacidad y auditoría:** EL SISTEMA:
  - aplica la matriz de permisos en el servidor;
  - exige POST con CSRF para todo cambio;
  - responde sin caché (`no-store`);
  - pone en las URL solo identificadores internos y fechas, nunca RUT ni nombres;
  - no incluye el RUT en los datos del mapa;
  - pide las teselas con un referente reducido al origen del sitio, sin la ruta de la página;
  - no envía a terceros nombres, direcciones ni coordenadas de pacientes; las teselas que pide el navegador solo revelan al proveedor el área visible del mapa.

  La auditoría registra quién guardó un orden y quién volvió al sugerido, con identificadores y sin datos personales. Si la auditoría falla, la operación se revierte. *(Enmienda 2026-11-15: Django envía coordenadas de domicilios, y la posición del encargado cuando él la pide, a su propio OSRM en la red interna, nunca a terceros; la posición no se guarda ni queda en registros. Ver RF-09-19.)*
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
- **Origen y cartografía:** `REPARTO_ORIGEN_LATITUD`, `REPARTO_ORIGEN_LONGITUD`, `MAPA_TESELAS_URL`, `MAPA_TESELAS_ATRIBUCION` y `MAPA_ZOOM_MAXIMO`, leídas de `.env`. Por defecto, el origen es el punto del CESFAM que entregó el usuario el 2026-11-12 (−36,4988773; −72,2123601); el `.env` puede reemplazarlo. Las teselas son las de OpenStreetMap, con la atribución «© colaboradores de OpenStreetMap».
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
- **Línea recta, vecino más cercano y 2-opt, con vuelta al CESFAM** (decisión del usuario, recomendada). Determinista y probado en el servidor. Se descarta un servicio de rutas por camino: suma un proveedor con clave o límites, envía coordenadas de pacientes a un tercero y cartografía mal los caminos rurales. También se descarta solo agrupar por sector, porque no reduce el recorrido. *(**Revertida por la enmienda del 2026-11-15**: distancias y tramos por camino con un OSRM propio. Motivo en [Decisiones que se revierten](#decisiones-del-2026-11-12-que-se-revierten).)*
- **Partida en el CESFAM y recálculo desde la última visita registrada** (decisión del usuario, recomendada). No usa la posición del celular para ordenar. Se descartan el orden fijo desde el CESFAM y el orden desde la ubicación del celular.
- **Pestaña «Mapa» y lista numerada como vista principal** (decisión del usuario, recomendada). Se descartan el mapa sobre la lista (más pesado con mala señal) y una página aparte.
- **Hoy y atrasadas en la ruta** (decisión del usuario, recomendada).
- **Sin coordenadas al final, rotuladas** (decisión del usuario, recomendada). Se descarta asignarles una ubicación aproximada, que puede inducir a error.
- **«Rutas» para la Q.F., por encargado** (decisión del usuario; se recomendaba solo el encargado). Consecuencia: una pestaña nueva de solo consulta para la Q.F. y el superusuario.
- **El Técnico no ve «Rutas»** (decisión del usuario; se recomendaba incluirlo como en el 08).
- **Mapa del domicilio solo para ver** (decisión del usuario, recomendada). Se descarta ajustar el punto arrastrando el marcador. *(**Revertida en parte por la enmienda del 2026-11-15**: el mapa pequeño de la página sigue siendo de solo lectura, pero el formulario suma «Usar mapa» para marcar el punto; ver RF-09-25.)*
- **Guía «Ir a esta parada» dentro de la PWA** (propuesta del usuario, que reemplaza el enlace `geo:` como única guía). La posición se obtiene en el celular con un gesto y nunca va al servidor. El encargado ve la distancia en línea recta y la dirección; el enlace `geo:` y las coordenadas en texto quedan como apoyo. La ruta por caminos con un motor propio queda como mejora futura. *(Enmienda 2026-11-15: esa mejora se incorpora; la guía usa el tramo por camino y la posición viaja a Django solo para calcularlo; ver RF-09-23.)* No contradice la exclusión del informe sobre la «geolocalización satelital en tiempo real de los vehículos», porque nadie fuera del celular conoce la posición: no hay seguimiento.
- **Seguir la posición hasta detenerla** (decisión del usuario, recomendada). Se descarta tomarla una vez por toque.
- **Orden manual guardado** (decisión del usuario; se recomendaba solo la sugerencia). Consecuencias: un modelo nuevo, una migración, pruebas concurrentes y reglas para las visitas que llegan después.
- **Visitas nuevas en el lugar más barato, con aviso** (decisión del usuario, que combina la inserción más barata con el rótulo «Nueva»). Se descarta agregarlas siempre al final.
- **Visitas sin coordenadas ubicables en el orden manual** (decisión del usuario, recomendada): el encargado conoce el lugar.
- **Origen en `.env`** (decisión del usuario, recomendada). Se descartan fijarlo en el código y una pantalla de configuración.
- **«Registradas hoy» aparte** (decisión del usuario, recomendada). Cumple el «registro de las entregas del día» y el «estado» de HU-14.
- **Línea recta punteada con total en km** (decisión del usuario, recomendada). *(**Revertida por la enmienda del 2026-11-15**: sin línea del recorrido completo; total por camino; ver RF-09-20 y RF-09-21.)*
- **Subir, Bajar y Mover a la posición** (decisión del usuario, recomendada). Funciona con teclado, lector de pantalla y sin JavaScript. Se descarta arrastrar y soltar. *(**Revertida por la enmienda del 2026-11-15**: flechas y franja de arrastre, sin «Mover a la posición»; ver RF-09-17.)*
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

No hay bloqueos críticos para redactar. El valor exacto del origen (el CESFAM) lo entregó el usuario el 2026-11-12: −36,4988773; −72,2123601.

## Enmienda del 2026-11-15 (Borrador)

Pedida por el usuario el 2026-11-15, junto con la [enmienda del spec 08](../08-domicilios-y-entregas/spec.md#enmienda-del-2026-11-15-borrador) (modal de fotos, visor y textos). Se trabaja en `crojas-base`. La versión aprobada del 2026-11-12 sigue vigente hasta que el usuario apruebe esta enmienda.

**Objetivo de la enmienda:** reemplazar las líneas rectas por distancias y tramos por camino calculados con un OSRM propio, compactar las tarjetas de «Mis entregas» con flechas y arrastre para reordenar, y permitir marcar en un mapa las coordenadas del domicilio.

### Decisiones del 2026-11-12 que se revierten

| Decisión revertida | Antes | Ahora | Motivo |
|---|---|---|---|
| Recorrido en línea recta | Orden, total, línea punteada y guía calculados con haversine. Se descartaba un servicio de rutas por camino porque sumaba un proveedor con clave o límites, enviaba coordenadas de pacientes a un tercero y cartografiaba mal los caminos rurales. | Distancias y tramos por camino con un OSRM propio. La línea recta solo queda como respaldo rotulado del orden cuando OSRM no responde. | Las dos primeras razones del descarte desaparecen: el OSRM es propio, sin clave ni límites de uso, y ningún dato sale a un tercero (el navegador habla solo con Django y Django con OSRM por la red interna). En una comuna con 57,9 % de ruralidad, la línea recta ignora ríos, cerros y caminos, y el usuario pidió dejar de considerarla. La tercera razón persiste como riesgo: la cartografía de OpenStreetMap de los caminos rurales puede estar incompleta (ver [plan.md](plan.md#riesgos-de-la-enmienda)). |
| Exclusión del arrastre | «Subir», «Bajar» y «Mover a la posición». Se descartaba arrastrar y soltar. | Flechas y una franja de arrastre en cada tarjeta. Se retira «Mover a la posición». | En el celular, reordenar con el pulgar es más rápido que elegir una posición en una lista. Las flechas se mantienen como alternativa con teclado, lector de pantalla y sin JavaScript, porque el arrastre no puede ser el único medio (WCAG 2.1, criterio 2.1.1). |
| Exclusión de elegir coordenadas en el mapa | Coordenadas solo con la ubicación del celular en el domicilio o escritas a mano. | «Usar mapa» en el formulario del domicilio. | Con direcciones como «Dadinco, km 2 casa roja», la Q.F. o el encargado pueden ubicar el domicilio desde la oficina, sin estar en el lugar. Los campos manuales y «Usar mi ubicación actual» se conservan. |

### Cambios en los permisos

| Acción / datos | Técnico | Encargado de terreno | Q.F. | Superusuario activo |
|---|---|---|---|---|
| Pedir un tramo por camino o la parada más cercana, enviando su posición | No | Solo hacia paradas de su ruta de hoy | No | No |
| Reordenar con flechas o arrastre | No | Solo su ruta de hoy | No | No |
| Tarjetas compactas con mapa pequeño y visor de fotos | No | En «Mis entregas» | En «Rutas», solo consulta | En «Rutas», solo consulta |
| «Usar mapa» en el formulario del domicilio | No (no edita domicilios) | Sí | Sí | Sí |

Para lo demás sigue la matriz del 2026-11-12. El tramo y la sugerencia usan la misma comprobación exacta del rol que el orden manual: el superusuario no los tiene.

### Alcance de la enmienda

**Incluye:**
- Tarjetas compactas y expandibles en «Mis entregas» y «Rutas», con mapa pequeño y fotos (RF-09-16, RF-09-18).
- Flechas y franja de arrastre para reordenar; se retira «Mover a la posición» (RF-09-17).
- Servidor de rutas OSRM propio, consultado solo por Django (RF-09-19).
- Orden sugerido, inserción de las visitas «Nuevas» y total del recorrido por camino (RF-09-20).
- Pestaña «Mapa» sin la línea del recorrido completo, con el tramo por camino desde la posición y «Sugerir parada más cercana» (RF-09-21 y RF-09-22).
- «Ir a esta parada» por camino, sin línea recta ni rumbo (RF-09-23).
- «Rutas» de la Q.F. con tarjetas compactas de consulta y un mapa solo con marcadores (RF-09-24).
- «Usar mapa» en el formulario del domicilio (RF-09-25).
- Comportamiento sin señal de mapas, tramo y modal de fotos (RF-09-26).
- Documentación: instalación y actualización de OSRM en `README.md` y esquema del despliegue en `docs/estructura.md`.
- Lienzo de diseño hecho con Claude Design, en celular y computador, antes de aprobar la enmienda.

**Fuera de la enmienda:**
- Modo sin conexión de mapas, tramos y modal de fotos: necesitan señal y quedan para la reserva 11.
- Indicaciones paso a paso («gira a la derecha»), voz de navegación y tiempos de viaje. El tramo es una línea y una distancia.
- Dibujar la ruta completa por camino: se pidió quitar la línea del recorrido completo.
- Guardar la posición del encargado, su historial o mostrarla a la Q.F. (fuera de alcance del informe).
- Que el navegador consulte a OSRM o exponerlo a internet; otros perfiles distintos del de auto; actualizar el mapa de OSRM de forma automática.
- Cambios en `OrdenRuta`, `ParadaRuta`, `mover_parada`, `restablecer_orden` y en las reglas, modelos y servicios del 08. La enmienda no tiene migraciones.

### Requisitos de la enmienda

- **RF-09-16 — Tarjetas compactas:** EL SISTEMA muestra cada visita de «Mis entregas» (por visitar, sin coordenadas y próximas) como una tarjeta compacta con:
  - el número de parada y los rótulos que correspondan («Atrasada desde el dd/mm», «Nueva: no estaba en tu orden», «Sin coordenadas»);
  - el nombre del paciente y la dirección;
  - los botones «Entregar», «No entregada» y «Expandir».

  «Entregar» y «No entregada» abren el registro del 08, como hoy. En «Próximas», en su lugar aparece «Programada para el dd/mm/aaaa». «Expandir» es un botón con `aria-expanded` y `aria-controls`; al pulsarlo, su texto pasa a «Contraer», el foco se queda en él y la tarjeta muestra el resto: teléfono, sector y nombre de la localidad, referencias, estado de verificación, coordenadas en texto, recetas con «entrega n de m», miniaturas de las fotos con su visor (RF-08-19), el botón de fotos (RF-08-18), el mapa pequeño (RF-09-18), «Ir a esta parada» y «Detalles del domicilio». Se pueden expandir varias tarjetas a la vez. Sin JavaScript, todas se muestran expandidas y sin el botón.
- **RF-09-17 — Reordenar con flechas y arrastre** *(modifica RF-09-04)*: CUANDO el encargado pulsa la flecha «Subir» o «Bajar» de la esquina superior derecha de una tarjeta, o mantiene presionada la franja vertical angosta del borde derecho y arrastra la tarjeta a otro lugar, EL SISTEMA guarda el orden nuevo con el servicio `mover_parada`. Se mantienen sus garantías: versión, operación idempotente y el aviso «Tu orden cambió en otro dispositivo; revisa la lista.».
  - El arrastre abarca todas las visitas de la ruta de hoy, incluidas las sin coordenadas, como el orden manual del RF-09-04.
  - Se retira «Mover a la posición».
  - Las flechas tienen 48 px o más y un nombre accesible («Subir parada 3: Nombre Apellido»). Sin JavaScript funcionan con un POST y recarga; con JavaScript, la lista se reordena sin recargar y conserva las tarjetas expandidas.
  - Mientras se arrastra, la tarjeta sigue al dedo o al puntero, un hueco muestra dónde caerá y la página se desplaza sola cerca de los bordes. Esc o soltar fuera de la lista cancela sin cambios.
  - Al soltar, la región `aria-live` anuncia «Parada movida a la posición 2». Si el guardado falla, la tarjeta vuelve a su lugar y se muestra el motivo.
  - La franja se oculta a los lectores de pantalla y no recibe foco, porque las flechas cumplen la misma función.
  - Solo el encargado ve flechas y franja, y solo en su ruta de hoy.
- **RF-09-18 — Mapa pequeño en la tarjeta:** CUANDO se expande una tarjeta cuyo domicilio tiene coordenadas, EL NAVEGADOR carga, recién entonces, un mapa pequeño de solo lectura con el punto del domicilio. Se ubica a la derecha de los datos en computador y debajo en celular. No captura el desplazamiento de la página: se acerca y se aleja con sus botones. Sin coordenadas, el recuadro dice «Domicilio sin coordenadas». Si las teselas no cargan, el punto se mantiene y un texto lo avisa. Los datos del mapa no incluyen el RUT.
- **RF-09-19 — Servidor de rutas propio (OSRM):** EL SISTEMA calcula las distancias y los tramos por camino con un OSRM propio (imagen oficial `ghcr.io/project-osrm/osrm-backend`, perfil de auto, algoritmo MLD y el mapa de Chile de Geofabrik recortado a Ñuble con osmium).
  - Solo Django consulta a OSRM. El navegador pide el tramo a Django, con sesión de encargado, y nunca conoce la dirección de OSRM.
  - La dirección se lee de `OSRM_URL` (por defecto `http://127.0.0.1:5000`) y el tiempo de espera, de `OSRM_TIEMPO_ESPERA`, en segundos (por defecto 1,0; entre 0,2 y 2,0, para respetar RNF-05). Si `OSRM_URL` está vacía, el servicio queda desactivado y todo funciona con su respaldo.
  - `python manage.py check` informa `entregasapp.E004` si la URL no es `http` o `https` con host, o si trae consulta o fragmento, y `entregasapp.E005` si el tiempo de espera está fuera de rango. No comprueba que el servidor responda.
  - Envía las coordenadas como `longitud,latitud`, con 6 decimales, y no usa los proxies del entorno.
  - Considera que OSRM no está disponible si no responde dentro del tiempo de espera, si hay un error de red, si el código no es `Ok` o si la respuesta está mal formada.
  - La posición del encargado llega a Django por POST, solo para calcular un tramo o la parada más cercana. No se guarda en la base, la sesión, la caché ni la auditoría, ni queda en los registros de Django; las respuestas son `no-store`. OSRM se ejecuta sin registrar las solicitudes (ver [plan.md](plan.md#osrm-sin-registros-de-solicitudes)).
  - En el despliegue, OSRM vive en la red interna y no se expone a internet. En local escucha solo en `127.0.0.1:5000`.
  - Las pruebas de Django simulan las respuestas de OSRM y no dependen de que el servidor esté corriendo.
- **RF-09-20 — Orden y total por camino** *(modifica RF-09-02 y RF-09-05)*: EL SISTEMA calcula el orden sugerido y la inserción de las visitas «Nuevas» con la matriz de distancias por camino que entrega OSRM entre la partida, las paradas con coordenadas y el CESFAM. Usa el mismo vecino más cercano, la mejora 2-opt (adaptada a distancias que pueden diferir de ida y de vuelta), el límite de 200 paradas y el desempate por identificador. La lista y el mapa dicen «Orden sugerido según distancia por camino» y «Recorrido aprox. por camino: 23,4 km» (desde la partida, por las paradas, hasta el CESFAM). SI OSRM no está disponible o rechaza la matriz, ENTONCES el orden se calcula con la distancia en línea recta, se muestra «Orden aproximado en línea recta: el servidor de rutas no respondió» y no se muestra el total. Un orden guardado (modo manual) no cambia por la disponibilidad de OSRM; solo cambia dónde se insertan las «Nuevas». La matriz se puede guardar en caché unos minutos: contiene solo distancias entre domicilios y el CESFAM, nunca la posición del encargado.
- **RF-09-21 — «Mapa» con el tramo por camino** *(modifica RF-09-08)*: EL SISTEMA quita la línea punteada del recorrido completo y su leyenda. Conserva los marcadores numerados, el CESFAM, las visitas registradas hoy y el orden sugerido.
  - CUANDO el encargado pulsa «Mostrar mi posición» y da permiso, EL NAVEGADOR sigue su posición y pide a Django el tramo por camino hasta la próxima parada (la primera de la lista con coordenadas) o hasta la que elija con «Trazar tramo hasta aquí», en el resumen del marcador o en la lista de paradas de la misma pestaña.
  - El mapa dibuja solo ese tramo, con la posición del encargado y su precisión, y dice «Parada 3: 1,2 km por camino».
  - El tramo se recalcula cuando el encargado se mueve más de 150 m y pasaron al menos 20 s desde el cálculo anterior. «Detener» termina el seguimiento y borra el tramo.
  - SI no hay permiso, contexto seguro o posición, o si OSRM no está disponible, ENTONCES solo se muestran los marcadores, sin línea, con un aviso de texto (por ejemplo, «No se pudo calcular el tramo: el servidor de rutas no respondió. Sigue el orden de la lista.»).
  - Django rechaza un tramo hacia una visita que no esté en la ruta de hoy del encargado o que no tenga coordenadas. El destino se lee de la base; el navegador solo envía el identificador de la visita y su posición.
- **RF-09-22 — Sugerir parada más cercana:** CUANDO el encargado pulsa «Sugerir parada más cercana» con su posición disponible, EL SISTEMA pide a OSRM las distancias por camino desde esa posición hasta cada parada con coordenadas de su ruta de hoy. Destaca la más cercana en el mapa, con forma y texto, no solo con color («La más cercana por camino es la parada 4, a 900 m»), dibuja el tramo hasta ella y ofrece «Mover al siguiente lugar». Al confirmar, la mueve a la posición 1 con `mover_parada`, con lo que el orden queda guardado como manual, y lo anuncia. SI ya es la primera, lo dice y no ofrece moverla. SI OSRM no está disponible, ENTONCES no sugiere ninguna parada y lo dice con texto: la sugerencia se mide solo por camino, nunca en línea recta. Sin posición, el botón explica que necesita el permiso de ubicación.
- **RF-09-23 — «Ir a esta parada» por camino** *(reemplaza RF-09-09 en lo que se le oponga)*: la guía muestra la posición del encargado, el tramo por camino hasta la parada y su distancia («La parada 3 está a 1,2 km por camino»), recalculado como en RF-09-21. Se quitan la línea recta, la distancia en línea recta y el rumbo en ocho direcciones. Se mantienen el seguimiento hasta «Detener» o hasta salir de la página, y los avisos al lector de pantalla al iniciar, al pulsar «Leer distancia» y al quedar a menos de 100 m por camino. La posición se envía a Django solo para calcular el tramo (RF-09-19). Sin OSRM, sin permiso o sin posición, la página lo explica con texto y ofrece el enlace «Abrir en app de navegación» y las coordenadas, sin distancia.
- **RF-09-24 — «Rutas» de la Q.F.** *(modifica RF-09-10)*: «Rutas» usa las tarjetas compactas del RF-09-16 en modo consulta. Se expanden y muestran el mapa pequeño y el visor de fotos, pero no tienen flechas, franja, «Entregar», «No entregada», botón de fotos ni «Ir a esta parada». Su mapa muestra solo los marcadores de las paradas, el CESFAM y las registradas hoy, sin línea, sin tramos y sin ninguna referencia a la posición del encargado. El orden y el total siguen el RF-09-20.
- **RF-09-25 — «Usar mapa» en el domicilio:** CUANDO quien edita un domicilio pulsa «Usar mapa» en Coordenadas, EL NAVEGADOR abre un diálogo con un mapa que se mueve y se acerca libremente.
  - Se centra en las coordenadas del formulario, marcadas, si son válidas; si no, en el CESFAM (`REPARTO_ORIGEN_*`).
  - Al tocar o hacer clic se marca un punto; otro toque lo reemplaza. Con teclado, el mapa se mueve con las flechas y «Marcar el centro del mapa» marca el punto bajo la mira central.
  - «Usar este punto» copia la latitud y la longitud con 6 decimales a sus campos, vacía «Precisión (metros)», que queda libre para escribirla a mano, y cierra el diálogo. «Cancelar», Esc o la X cierran sin cambios.
  - El foco queda dentro del diálogo y vuelve al botón al cerrar.
  - Los campos manuales y «Usar mi ubicación actual» siguen disponibles. Nada se guarda hasta pulsar «Guardar domicilio» y, como todo cambio de coordenadas, deja el domicilio pendiente de verificar (RF-08-04).
  - Sin JavaScript, el botón no aparece.
- **RF-09-26 — Mapas, tramo y fotos necesitan señal:** EL SISTEMA no tiene modo sin conexión para los mapas, el tramo por camino ni el modal de fotos; eso queda para la reserva 11. Sin señal, cada mapa conserva lo que ya cargó y muestra su aviso, el tramo y la sugerencia dicen «Sin conexión: no se pudo calcular», y el modal de fotos no guarda nada y dice «Sin conexión: no se guardó ningún cambio». La lista y el registro del 08 siguen exigiendo conexión, como hasta ahora.

### Criterios de aceptación de la enmienda

| RF | Escenario | Resultado verificable |
|---|---|---|
| RF-09-16 | Abrir «Mis entregas» con 3 paradas (una atrasada y una «Nueva») y 1 próxima; expandir dos tarjetas | Tarjetas compactas con número, rótulos, nombre, dirección y los tres botones (la próxima, con su fecha en lugar de los botones de registro); las dos expandidas a la vez, con `aria-expanded="true"` y el foco en su botón; sin JavaScript, todas expandidas. |
| RF-09-17 | Bajar la parada 1 con la flecha; arrastrar la parada 3 a la posición 1; cancelar un arrastre con Esc; arrastre que choca con un guardado desde otro dispositivo | El orden se guarda en los dos primeros casos y se anuncia; Esc no cambia nada; el choque devuelve la tarjeta a su lugar con «Tu orden cambió en otro dispositivo; revisa la lista.»; «Mover a la posición» ya no existe. |
| RF-09-17 | La Q.F. en «Rutas», el Técnico y otro encargado; POST de una flecha sin JavaScript | Sin flechas ni franja para los tres; el POST del encargado funciona con recarga. |
| RF-09-18 | Expandir una tarjeta con coordenadas y otra sin ellas; teselas que fallan | El mapa se carga solo al expandir; «Domicilio sin coordenadas»; con teselas caídas, el punto y el aviso. |
| RF-09-19 | Sin variables; `OSRM_URL=ftp://x`; `OSRM_URL=http://h:5000/?a=1`; `OSRM_TIEMPO_ESPERA=5`; `OSRM_URL` vacía | Valores por defecto; `E004`, `E004`, `E005`; servicio desactivado y respaldo en uso. |
| RF-09-19 | OSRM simulado que tarda más que el tiempo de espera, responde 500, responde `code: "NoRoute"` o un JSON mal formado | Cada caso se trata como «no disponible», en menos del tiempo de espera más un margen, sin excepciones sin manejar. |
| RF-09-19 | Pedir un tramo con una posición conocida; revisar la base, la auditoría, la sesión, la caché y los registros capturados | La URL enviada a OSRM lleva `longitud,latitud`; la posición no aparece en ninguna de esas fuentes; respuesta `no-store`. |
| RF-09-20 | OSRM simulado con una matriz en que A está más cerca de O en línea recta pero más lejos por camino | El orden sigue al camino; total «por camino» igual a la suma de la matriz; mismo orden en cada repetición. |
| RF-09-20 | Matriz asimétrica construida a mano; OSRM no disponible; orden manual guardado con OSRM caído | El 2-opt adaptado da el óptimo de la fuerza bruta; con OSRM caído, orden en línea recta con su rótulo y sin total; el orden manual no cambia. |
| RF-09-21 | Mostrar posición con OSRM simulado; elegir la parada 4; moverse 100 m y luego 200 m; «Detener»; permiso denegado; OSRM caído | Tramo hasta la primera con coordenadas y luego hasta la 4; no recalcula a 100 m y sí a 200 m pasados 20 s; «Detener» borra el tramo; sin permiso o sin OSRM, solo marcadores y el aviso; no existe la línea del recorrido completo. |
| RF-09-21 | POST de tramo hacia la visita de otro encargado, una sin coordenadas, una registrada o con coordenadas manipuladas en el cuerpo | Rechazo con texto; el destino nunca se toma del cuerpo. |
| RF-09-22 | Posición cerca de la parada 4; confirmar «Mover al siguiente lugar»; la más cercana ya es la 1; OSRM caído | Destaca la 4 con texto y tramo; tras confirmar es la parada 1 y el orden queda manual; «Ya es tu próxima parada»; sin sugerencia y con aviso. |
| RF-09-23 | Pruebas de JavaScript con posición y OSRM simulados; a 80 m por camino; OSRM caído | Distancia por camino en el texto; el aviso de llegada; sin distancia, con el enlace y las coordenadas; no hay rumbo ni línea recta. |
| RF-09-24 | La Q.F. consulta la ruta de hoy de un encargado que tiene su posición activa en otra pestaña | Tarjetas compactas expandibles sin acciones de cambio; mapa con marcadores sin línea ni tramo; los datos del mapa no tienen posición del encargado. |
| RF-09-25 | «Usar mapa» sin coordenadas; con coordenadas válidas; marcar con clic y con «Marcar el centro del mapa»; «Usar este punto»; «Cancelar» | Centra en el CESFAM; centra en el punto existente marcado; copia 6 decimales y vacía la precisión; cancelar no cambia los campos; el foco vuelve al botón; guardar deja el domicilio pendiente de verificar. |
| RF-09-26 | Simular sin red al expandir una tarjeta, al pedir el tramo y al guardar fotos | Avisos de texto en cada caso; nada se guarda; el resto de la página sigue usable. |

### No funcionales de la enmienda

- RNF-05: p95 de 2 s o menos para «Mis entregas», «Mapa», «Rutas», el tramo, la parada más cercana y el guardado de fotos sin archivos grandes, con 670 pacientes, unas 50 visitas por encargado y OSRM simulado. Se mide aparte, con el OSRM local real, la matriz de 52 puntos, la de 202 puntos y un tramo.
- WCAG 2.1 AA (RNF-04): botones de 48 px o más con nombre accesible; el arrastre tiene alternativa con las flechas; diálogos con foco contenido que vuelve al control que los abrió; la parada destacada y el tramo se comunican con texto y forma, con contraste de 3:1 o más; avisos con `aria-live="polite"`; sin desplazamiento horizontal en 320 px. La revisión de navegador, axe y la usabilidad con cinco personas requieren evidencia propia.
- Privacidad (RNF-01): la posición del encargado solo se usa para la solicitud en curso. Solo datos sintéticos en pruebas, herramientas y el lienzo de diseño.
- Seguridad: OSRM no se expone a internet; el tramo y la sugerencia exigen sesión de encargado, POST con CSRF y un límite de solicitudes por minuto.

### Compatibilidad de la enmienda

- Sin migraciones: `OrdenRuta`, `ParadaRuta` y los modelos del 08 no cambian.
- `entregasapp/ruta.py` sigue sin depender de Django: recibe una función o matriz de distancias en lugar de calcular siempre haversine.
- Se ajustan las pruebas del 09 que fijan la línea recta, la línea del recorrido, el rumbo, «Mover a la posición» y la ausencia de solicitudes de red en `ir_a.js`, y las del 08 que usan los formularios de fotos que reemplaza el modal. `plan.md` las lista al implementar. Las pruebas del 03 al 07 pasan sin cambios.
- La reserva 11 deberá decidir qué hacer sin señal con mapas, tramos y fotos pendientes.

### Decisiones de la enmienda

- **OSRM propio, consultado solo por Django** (decisión del usuario). Se descartan los proveedores externos y que el navegador consulte a OSRM.
- **«Más cercana» solo por camino** (decisión del usuario; se recomendaba usar la línea recta como respaldo rotulado). Sin OSRM, no se sugiere ninguna parada.
- **Sin líneas rectas en la guía** (decisión del usuario): «Ir a esta parada» usa la distancia del tramo por camino y se quita el rumbo (recomendada).
- **Orden por la matriz de OSRM, con respaldo en línea recta rotulado** (decisión del usuario, recomendada). Se descartan dejar la lista sin orden con OSRM caído y mantener haversine como cálculo principal.
- **Tramo recalculado al moverse, con límite** (decisión del usuario, recomendada): más de 150 m y al menos 20 s. Se descartan un botón manual y el cálculo continuo.
- **Total por camino, sin tiempo de viaje** (decisión del usuario, recomendada). Se descarta mostrar la duración, que suele ser optimista en caminos rurales.
- **Arrastre con código propio** (decisión del usuario; se recomendaba SortableJS local). Sin dependencia nueva; más casos de borde que probar.
- **Número de parada y rótulos visibles en la tarjeta compacta** (decisión del usuario, recomendada).
- **«Usar mapa» abre en el punto actual si existe** (decisión del usuario, recomendada); si no, en el CESFAM.
- **Lienzo de diseño antes de aprobar la enmienda** (decisión del usuario; se recomendaba hacerlo como primera tarea de `/spec-impl`).

### Supuestos de la enmienda

Supuestos técnicos reversibles, sujetos a la revisión del borrador:
- Los nombres `OSRM_URL` y `OSRM_TIEMPO_ESPERA` y los códigos `entregasapp.E004` y `E005` son propuestas de este spec.
- El contenedor se inicia con `--max-table-size` de al menos 300, para admitir 200 paradas más la partida y el CESFAM; si OSRM rechaza una matriz por tamaño, se usa el respaldo.
- Cerca de la parada (último tramo de menos de 500 m), el tramo se recalcula al moverse más de 30 m y con al menos 10 s entre cálculos, para que el aviso de 100 m llegue a tiempo.
- El tramo y la parada más cercana admiten 30 solicitudes por minuto por encargado; sobre ese límite responden con un texto y no consultan a OSRM.
- La matriz se guarda en la caché de Django durante 10 minutos, con una clave derivada de las coordenadas.
- El mapa pequeño pasa a la derecha desde 768 px de ancho.
- En pantallas táctiles, el arrastre empieza tras mantener presionada la franja unos 300 ms; con mouse, al presionarla.
- La «próxima parada» del tramo es la primera de la lista que tiene coordenadas.

### Revisión de la enmienda

2026-11-15: el usuario describió la enmienda y se hicieron tres bloques de preguntas:
1. Cómo medir «más cercana», qué pasa con «Ir a esta parada», cuándo recalcular el tramo y cómo sacar la foto con la cámara.
2. Orden sugerido sin líneas rectas, rumbo y aviso de llegada, un solo modal de fotos y momento del lienzo de diseño.
3. Centro de «Usar mapa», total del recorrido, implementación del arrastre y contenido de la tarjeta compacta.

Se guarda como Borrador, sin código ni migraciones.

## Revisión y cambios

2026-11-11 y 2026-11-12: cuatro bloques de preguntas.
1. Mapa base, cálculo del orden, punto de partida y pantalla.
2. Visitas incluidas, visitas sin coordenadas, vista de la Q.F. y mapa del domicilio.
3. Guía hacia la parada, orden manual, datos de demostración y permisos de «Rutas».
4. Seguimiento de la posición, visitas nuevas en un orden guardado, visitas sin coordenadas en el orden manual, origen, «Registradas hoy», línea del recorrido, controles para reordenar y alcance del comando.

Se guardan los cuatro documentos como Borrador, sin código ni migraciones.

2026-11-12 (implementación): el usuario cambió el estado a Aprobado, hizo el commit de los documentos (`5751ec5`) y entregó las coordenadas del CESFAM (−36,4988773; −72,2123601). El origen por defecto pasa a ser ese punto en lugar del valor aproximado del centro de San Nicolás.

2026-11-15 (enmienda, Borrador): el usuario pidió revertir tres decisiones (línea recta, arrastre y coordenadas en el mapa) y dejar el motivo anotado. Ver [Enmienda del 2026-11-15](#enmienda-del-2026-11-15-borrador). Las notas dentro de los requisitos del 2026-11-12 enlazan a los requisitos nuevos; la versión aprobada sigue vigente hasta que el usuario apruebe la enmienda.

2026-11-15 (aprobación de la enmienda): el usuario revisó el lienzo (T-09-10) y aprobó la enmienda («Apruebo todos los cambios»). Implementación pendiente: T-09-11 a T-09-18, después de T-08-14 a T-08-16.
