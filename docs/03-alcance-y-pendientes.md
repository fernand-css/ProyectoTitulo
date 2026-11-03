# 03. Alcance y pendientes

Fecha de actualización: 2026-11-03.

## Alcance autorizado de la actualización

F-17 autoriza actualizar exclusivamente `AGENTS.md`, `README.md` y los cinco documentos 00–04 de `docs/` para registrar el stack completo aprobado por F-16–17, su historial, las responsabilidades de PostgreSQL/Redis y las configuraciones pendientes. F-07 corresponde a la actualización documental anterior.

El Informe N.º 1 permanece como antecedente intacto y el Informe N.º 2 no se ha iniciado. Esta actualización no modifica F-09–F-15, no corrige requisitos por suposición y no aprueba automáticamente las propuestas del informe. El diagnóstico central está en [01](01-fuentes-y-diagnostico.md); la trazabilidad está en [02](02-requisitos-y-trazabilidad.md).

## Selección tecnológica y decisiones aún abiertas

**Stack completo aprobado por la usuaria (F-16–17; D-12):**

| Componente | Tecnología aprobada |
| --- | --- |
| Frontend | HTML5 + Alpine.js + JavaScript |
| Backend | Python + Django |
| API REST | Django REST Framework (DRF) |
| Comunicación en tiempo real | Django Channels + WebSockets |
| Servidor ASGI | Daphne |
| Mensajería y caché | Redis |
| Base de datos | PostgreSQL |

D-12 amplía D-09 y sustituye D-10. Los componentes ya no están pendientes de selección. D-13 establece PostgreSQL como fuente de verdad para persistencia e integridad del negocio, con Redis como infraestructura auxiliar de mensajería y caché.

### Reparto lógico de responsabilidades

- Presentación: HTML5 + Alpine.js + JavaScript para las interfaces del prototipo.
- Aplicación y API: Python + Django y DRF para API REST.
- Tiempo real y servicio ASGI: Channels + WebSockets y Daphne.
- Persistencia: PostgreSQL como registro de referencia de los datos y estados del negocio.
- Apoyo: Redis para mensajería y caché; los mensajes o entradas de caché no son el único registro de turnos, recetas o entregas.

Este reparto documenta la selección aprobada; no fija topología, número de procesos, módulos, endpoints, eventos, algoritmos ni parámetros. Los diagramas F-14/F-15 siguen siendo propuestas técnicas sujetas a validación, aunque reflejen tecnologías seleccionadas. No se modifican.

### Configuraciones y criterios pendientes

Versiones y compatibilidad, configuración ASGI y conexiones, estructura de aplicaciones, uso concreto de plantillas, contratos API/eventos, autenticación y permisos, esquemas de datos, transacciones, recuperación, alojamiento y despliegue requieren decisiones posteriores. Para Redis quedan pendientes backend de mensajería, conexiones, aislamiento, claves, caducidad, invalidación y comportamiento ante fallos.

WebSockets es la comunicación en tiempo real seleccionada. Un respaldo mediante polling no queda aprobado. Las plantillas pueden coexistir con una API REST; su uso concreto no está decidido.

PWA, funcionamiento sin conexión y sincronización se conservan como requisitos o propuestas por precisar según F-10: alcance instalable, almacenamiento local, eventos sincronizables, conflictos y recuperación siguen abiertos (INC-08). La selección del stack no demuestra estos comportamientos ni las métricas RNF/NS.

## Alcance funcional propuesto, por validar

Se mantienen RF-P-01 a RF-P-06: turnos, atención preferencial, llamados, recetas, importación CSV/Excel y trazabilidad domiciliaria. Las 23 HU y los RNF/NS de F-10 son fuentes de detalle y propuestas a contrastar.

Autenticación, recuperación de contraseña, perfil, mapas, sugerencias de ruta, notificaciones, confirmación del receptor y panel de mermas no se incorporan automáticamente como obligaciones nuevas por aparecer en el informe. Las correspondencias no son aprobación de alcance o de prioridades.

La importación futura, si se valida y autoriza, solo puede usar datos sintéticos sin origen clínico real. Sigue pendiente conciliar HU-23/RNF-07 con esa restricción; no se autoriza acceder a Rayén o pedir exportaciones.

## Exclusiones vigentes

- Código, instalación de dependencias, migraciones, ejecución o despliegue de aplicación.
- Diseño detallado, configuración técnica o modificación de interfaces, modelo o diagramas. Registrar los componentes aprobados, su papel lógico y observaciones de las propuestas existentes sí está autorizado.
- Creación, cambio, fusión o eliminación de ramas; commits, push y cualquier operación Git de escritura.
- Modificaciones de antecedentes originales, PNG, skills, recursos, configuraciones u otros archivos.
- Datos clínicos reales, identificadores, domicilios, fotografías o exportaciones de pacientes; integración con Rayén.
- Adopción de tecnologías adicionales al stack aprobado y reutilización de otros prototipos sin autorización. DRF, Channels, Daphne y Redis ya pertenecen al stack aprobado, pero no se autoriza instalarlos.
- Avance automático a otra etapa al aprobar documentación o requisitos.

## Decisiones pendientes priorizadas

P1: condiciona alcance, evidencia o reglas centrales. P2: condiciona coherencia técnica y validación. P3: mejora documental o posible trabajo futuro. Esta prioridad ordena preguntas; no sustituye MoSCoW ni autoriza resolverlas.

| Prioridad / decisión | Asunto y evidencia | Condición de resolución |
| --- | --- | --- |
| P1 / Q-01 | Vigencia de F-09–10, instrumentos sumativos y relación entre trabajo grupal y prototipo independiente | Confirmación de encargo, versión vigente y reglas aplicables; completar A-01, A-02 y A-06 |
| P1 / Q-06 | Calendario de 14, 6 y 5 semanas; INC-01 | Calendario confirmado y alcance temporal de cada cifra, sin asumir precedencia por el orden de archivos |
| P1 / Q-02 | Alcance, prioridades y flujo completo de turnos/despacho; INC-03, INC-09 | Aprobar HU aplicables, dependencias, categorías, reglas de prioridad, ausencia y atención presencial |
| P1 / Q-07 | Importación sintética y autonomía; INC-06 | Delimitar HU-23/RNF-07 y contrato de archivo ficticio, sin exportaciones reales ni integración |
| P1 / Q-08 | Roles y responsabilidades; INC-04 | Matriz validada de jefatura/dirección, técnico, conductor/TENS/encargado, paciente/cuidador y RACI |
| P1 / Q-09 | Demostración, cloud, capacitación, acta e implementación física; INC-02 | Acordar entregables académicos y separar futura implementación; no habilita despliegue ahora |
| P2 / Q-03 | Configuración y diseño detallado del stack aprobado; INC-07–08 | Selección resuelta por D-12; precisar versiones, ASGI, conexiones, aplicaciones, contratos API/eventos, permisos, caché, recuperación y PWA/offline/sincronización. No decidir parámetros por suposición |
| P2 / Q-10 | Cardinalidades, esquemas e integridad del modelo; MOD-01–12 | PostgreSQL es fuente de verdad por D-13; aún se requieren reglas validadas de asignación, recetas, entregas, ubicaciones, historial, auditoría y numeración antes de rediseñar |
| P2 / Q-04 | Métricas y pruebas RNF/NS; INC-10 | Aprobar umbrales, carga, entorno, recuperación y evidencias; no prometer resultados productivos |
| P2 / Q-11 | Indicadores y merma; INC-05 | Fuente, fórmula, período, población y distinción entre ausencia, no retiro y merma. No sumar poblaciones como disjuntas sin evidencia |
| P3 / Q-12 | Citas, imágenes incrustadas y anexos no consultados; INC-11 | Verificar originales y conversiones cuando se autorice; no editar documentos académicos en esta actualización |
| P3 / P-03 | Adaptación futura de skills | Propuesta y autorización separadas; no generar configuraciones ni ejecutar flujos ahora |
| Control / Q-05 | Paso al diseño o implementación | Aprobación posterior explícita que delimite actividades y archivos |

## Condición de cierre

Comprobar coherencia de los siete documentos y preservar los archivos ajenos al alcance. Entregar resumen del diff, estado de Git y decisiones pendientes. Detenerse después de la entrega. La selección de componentes y sus responsabilidades se consideran aprobadas por F-16–17; las cuestiones aún abiertas no se consideran resueltas por estar registradas.
