# 03. Alcance y pendientes

Fecha de actualización: 2026-11-03.

## Alcance autorizado de la actualización

F-07 autoriza actualizar exclusivamente `AGENTS.md`, `README.md` y los cinco documentos 00–04 de `docs/`. Incluye inventario con versiones conocidas y límites, selección tecnológica, correspondencias preliminares y registro de inconsistencias y observaciones de los diagramas.

Esta actualización no modifica F-09–F-15, no corrige requisitos por suposición y no aprueba automáticamente las propuestas del informe. El diagnóstico central está en [01](01-fuentes-y-diagnostico.md); la trazabilidad está en [02](02-requisitos-y-trazabilidad.md).

## Selección tecnológica y decisiones aún abiertas

**Seleccionado por la usuaria (F-06–07; D-09):** HTML5 + Alpine.js + JavaScript, Python + Django y PostgreSQL.

**Complementos no aprobados (D-10):** Django REST Framework, Django Channels, Daphne y Redis. No se seleccionan ni instalan.

API REST, plantillas, WebSockets, polling, PWA/offline, monolito modular, versiones de software, alojamiento y despliegue permanecen por validar. La selección base no resuelve estas cuestiones ni demuestra requisitos de rendimiento.

## Alcance funcional propuesto, por validar

Se mantienen RF-P-01 a RF-P-06: turnos, atención preferencial, llamados, recetas, importación CSV/Excel y trazabilidad domiciliaria. Las 23 HU y los RNF/NS de F-10 son fuentes de detalle y propuestas a contrastar.

Autenticación, recuperación de contraseña, perfil, mapas, sugerencias de ruta, notificaciones, confirmación del receptor y panel de mermas no se incorporan automáticamente como obligaciones nuevas por aparecer en el informe. Las correspondencias no son aprobación de alcance o de prioridades.

La importación futura, si se valida y autoriza, solo puede usar datos sintéticos sin origen clínico real. Sigue pendiente conciliar HU-23/RNF-07 con esa restricción; no se autoriza acceder a Rayén o pedir exportaciones.

## Exclusiones vigentes

- Código, instalación de dependencias, migraciones, ejecución o despliegue de aplicación.
- Diseño nuevo o modificación de interfaces, arquitectura, modelo o diagramas. Registrar observaciones de los existentes sí está autorizado.
- Creación, cambio, fusión o eliminación de ramas; commits y push.
- Modificaciones de antecedentes originales, PNG, skills, recursos, configuraciones u otros archivos.
- Datos clínicos reales, identificadores, domicilios, fotografías o exportaciones de pacientes; integración con Rayén.
- Selección de complementos o tecnologías adicionales y reutilización de otros prototipos sin autorización.
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
| P2 / Q-03 | API REST, WebSockets, polling, PWA/offline y arquitectura; INC-07–08 | Validar requisitos antes de elegir mecanismos. Stack base ya seleccionado; complementos no aprobados |
| P2 / Q-10 | Cardinalidades e integridad del modelo; MOD-01–12 | Reglas validadas de asignación, recetas, entregas, ubicaciones, historial, auditoría y numeración antes de rediseñar |
| P2 / Q-04 | Métricas y pruebas RNF/NS; INC-10 | Aprobar umbrales, carga, entorno, recuperación y evidencias; no prometer resultados productivos |
| P2 / Q-11 | Indicadores y merma; INC-05 | Fuente, fórmula, período, población y distinción entre ausencia, no retiro y merma. No sumar poblaciones como disjuntas sin evidencia |
| P3 / Q-12 | Citas, imágenes incrustadas y anexos no consultados; INC-11 | Verificar originales y conversiones cuando se autorice; no editar documentos académicos en esta actualización |
| P3 / P-03 | Adaptación futura de skills | Propuesta y autorización separadas; no generar configuraciones ni ejecutar flujos ahora |
| Control / Q-05 | Paso al diseño o implementación | Aprobación posterior explícita que delimite actividades y archivos |

## Condición de cierre

Comprobar coherencia de los siete documentos y preservar los archivos ajenos al alcance. Entregar resumen del diff, estado de Git y decisiones pendientes. Detenerse después de la entrega. Ninguna cuestión de esta tabla se considera resuelta por estar registrada.
