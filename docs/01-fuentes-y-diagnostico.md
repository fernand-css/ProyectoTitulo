# 01. Fuentes y diagnóstico

Fecha de actualización: 2026-11-03. Revisión documental; sin modificación de antecedentes.

## Fuentes operativas e históricas

| ID | Fuente y fecha | Alcance y limitaciones |
| --- | --- | --- |
| F-01 | Contexto inicial de la usuaria; fecha no explicitada en el registro previo | Independencia del prototipo y planificación. Conservado como antecedente del registro del 2026-10-31. |
| F-02 | Autorización inicial de Etapa 1, registrada con fecha 2026-10-31 | Siete documentos, seis antecedentes funcionales y revisión de skills. No aprobó requisitos funcionales. |
| F-03 | Inspección local registrada el 2026-10-31 | Estado entonces limpio, remoto y commit 69ad505; no describe el estado actual. |
| F-04 | AGENTS.md anterior, referido al commit 69ad505 | Describía MVP Django y specs ausentes; no acredita implementación ni selección vigente. |
| F-05 | Cuatro SKILL.md locales; diagnóstico del 2026-10-31 | Material auxiliar. Se conserva su diagnóstico sin ejecutar flujos ni modificarlo. |
| F-06 | Solicitud de revisión documental de la usuaria, 2026-11-03 | Selecciona el stack base; complementos pendientes; solicita diagnóstico sin cambios. |
| F-07 | Autorización de actualización controlada de la usuaria, 2026-11-03 | Aprueba actualizar solo los siete documentos y registrar correspondencias y pendientes. Reitera stack y complementos no aprobados; exige detenerse tras entregar. |
| F-08 | Inspección local y revisión documental, 2026-11-03 | Rama irubio; AGENTS modificado y README, docs/ y .vscode/ sin seguimiento al inicio. Texto de cinco antecedentes y dos PNG revisados; limitaciones abajo. |

F-01 a F-05 conservan el registro previo; no se reconstituyen mensajes ni aprobaciones académicas ausentes. F-06 y F-07 se identifican por fecha y contenido de esta conversación, sin inventar un ID externo o una transcripción exportada.

## Inventario de documentos de control

| Archivo | Fecha y versión conocida | Propósito |
| --- | --- | --- |
| [AGENTS.md](../AGENTS.md) | Actualización 2026-11-03; sin versión numerada | Restricciones y autorizaciones operativas |
| [README.md](../README.md) | Actualización 2026-11-03; sin versión numerada | Presentación y estado del repositorio |
| [00-indice-y-estado.md](00-indice-y-estado.md) | Actualización 2026-11-03; sin versión numerada | Índice, estado y verificación |
| Este documento 01 | Actualización 2026-11-03; sin versión numerada | Fuentes, límites de evidencia y diagnóstico |
| [02-requisitos-y-trazabilidad.md](02-requisitos-y-trazabilidad.md) | Actualización 2026-11-03; matriz preliminar | Clases de requisitos y correspondencias |
| [03-alcance-y-pendientes.md](03-alcance-y-pendientes.md) | Actualización 2026-11-03; sin versión numerada | Alcance y validaciones pendientes |
| [04-registro-de-decisiones.md](04-registro-de-decisiones.md) | Actualización 2026-11-03; sin versión numerada | Decisiones y evolución del registro |

Estas son fechas de actualización documental, no aprobaciones académicas.

## Inventario de antecedentes recibidos

Todos están en `docs/referencias/`, fueron revisados el 2026-11-03 y se conservan sin cambios. Las fechas de modificación del sistema de archivos no acreditan versiones.

| ID | Archivo y autoría declarada | Fecha / versión conocida | Propósito y limitaciones |
| --- | --- | --- | --- |
| F-09 | [Rubrica_Informe_N1.md](referencias/Rubrica_Informe_N1.md), guía académica asociada a INACAP | Guía ABPro Unidad 1, TIHI84; sin fecha ni revisión explícitas | Instrucciones de formulación y lista de cotejo formativa N° 1. No se recibió una rúbrica sumativa completa. Contiene 9 imágenes incrustadas no inspeccionadas visualmente y marcadores de conversión. |
| F-10 | [Informe_N1_Proyecto.md](referencias/Informe_N1_Proyecto.md), equipo de tres integrantes declarado en portada | Portada 2026-10-08; sin revisión explícita | Formulación del proyecto: 23 HU, 9 RNF, 8 NS, planificación y arquitectura sugerida. No consta aprobación docente o de contraparte. Contiene 10 imágenes incrustadas no inspeccionadas visualmente. |
| F-11 | [Entrevistas_CESFAM.md](referencias/Entrevistas_CESFAM.md), entrevistas a dirección, farmacia y reparto | Sin fecha ni versión explícitas | Necesidades y proceso actual. Sin acta de validación ni contraste con registro original. La fecha atribuida en F-10 no acredita la fecha del archivo completo. |
| F-12 | [Transcripcion_Requerimientos_CESFAM.md](referencias/Transcripcion_Requerimientos_CESFAM.md), voces rotuladas profesor/cliente y estudiante/equipo | Sin fecha ni versión explícitas | Discusión funcional y sugerencias. La sección final «Análisis Arquitectónico y Valor Agregado» es síntesis añadida, no intervención transcrita acreditada. |
| F-13 | [Transcripción_Reunión_Proyecto_CESFAM.md](referencias/Transcripción_Reunión_Proyecto_CESFAM.md), minuta sin autoría individual explícita | Sin fecha ni versión explícitas | Revisión de arquitectura, IA, recursos, seis semanas y MVP. No permite establecer por sí sola precedencia cronológica frente a F-10. |
| F-14 | [diagrama_modelo_de_datos.png](referencias/diagrama_modelo_de_datos.png), sin autoría visible | Sin fecha, revisión ni aprobación visibles | Modelo lógico propuesto, inspeccionado visualmente. El rótulo de normalización/alineación no prueba esas propiedades. |
| F-15 | [diagrama_arquitectura.png](referencias/diagrama_arquitectura.png), sin autoría visible | Sin fecha, revisión ni aprobación visibles | Arquitectura propuesta, inspeccionada visualmente. Coincide con el stack seleccionado, pero no acredita aprobación de su organización interna. |

## Clasificación de la evidencia

- **Exigencias académicas identificadas:** F-09, actividades 1 a 8, criterios 1.1.1 a 1.1.6 e indicaciones de entrega. Su vigencia debe confirmarse.
- **Necesidades levantadas:** F-11 y diálogo de F-12; F-13 recoge orientaciones, no una aprobación verificable de todas las HU.
- **Propuestas del equipo:** F-10, incluidos MoSCoW, métricas, arquitectura y mecanismos; F-14 y F-15 son propuestas gráficas.
- **Decisiones aprobadas por la usuaria:** F-06 y F-07, dentro de su ámbito operativo y tecnológico. No constituyen aprobación académica ni autorización de implementación.

La guía identifica trabajo grupal con evaluación individual. El prototipo independiente descrito por la usuaria no debe confundirse con una exención académica del trabajo grupal.

## Inconsistencias documentales por validar

Los ID INC son observaciones de revisión, no requisitos ni decisiones resueltas.

| ID | Evidencia y contradicción | Validación pendiente |
| --- | --- | --- |
| INC-01 | F-10 §§6.1–6.2: 14 semanas y sprints quincenales; F-13 §5: 6 semanas y entregas semanales; F-09: 5 semanas de la unidad académica | Calendario vigente y separación entre unidad, proyecto y desarrollo restante |
| INC-02 | F-10 §5.1.2 excluye implementación física; §6.2 la incluye; §5.3 compromete cloud, capacitación y acta | Entregables académicos frente a futura implementación; no hay autorización actual de despliegue |
| INC-03 | F-10 HU-13–16: Should; F-13 §5: despacho y turnos críticos; HU-04 mezcla selección automática con botones por paciente | Prioridades, dependencias y regla de selección del siguiente turno |
| INC-04 | F-10 HU-01, HU-20, §§5.1.1 y 6.3: jefatura, dirección, técnico, conductor, TENS y encargado con responsabilidades no uniformes; RACI sin R en diseño y despacho | Roles, permisos y responsabilidades aplicables al prototipo independiente |
| INC-05 | F-10 §5.2.3 anuncia seis indicadores y muestra cuatro; 20 %, 85 % y 1,74 % sin respaldo suficiente en F-11; HU-20 equipara ausencia sin retiro con merma | Fuentes, fórmulas, períodos y diferencia entre ausencia, no retiro y merma efectiva |
| INC-06 | F-10 HU-23, RNF-07, §§5.2.1 y 5.3 describen exportaciones de Rayén; F-07 exige datos sintéticos y ninguna integración | Contrato de importación sintética y delimitación de HU-23/RNF-07. No usar exportaciones reales |
| INC-07 | F-10 §§5.1.1 y 7.1 fija API REST/WebSockets; F-15 propone plantillas Django y consulta periódica; F-07 deja complementos no aprobados | Mecanismo de comunicación, medición de latencia y eventual justificación de complementos |
| INC-08 | F-10 RNF-03, RNF-09, NS05 y §7.1 requieren PWA/offline; F-15 no representa almacenamiento local ni sincronización diferida | Alcance instalable, operación sin señal y manejo de sincronización; pendientes, sin diseño nuevo |
| INC-09 | F-10 HU-07 bloquea turno presencial a ciertos pacientes; HU-09 alterna número/ventanilla con número/nombre; HU-10 incorpora urgencia y crónicos | Reglas y categorías válidas, contenido público y excepciones; F-11 no acredita todas esas reglas |
| INC-10 | F-10 §§3.3 y 5.3 propone metas técnicas, disponibilidad mensual y set de 670 pacientes | Condiciones de prueba y aprobación de umbrales. 70 postrados + 600 mayores no acredita 670 personas distintas |
| INC-11 | F-10 §§3.3 y 5.2.4 conserva marcadores de citación y «3.X»; marco teórico/bibliografía difieren en Chan/Chang y fecha W3C | Revisar fuentes originales y referencias internas sin inventar citas o vigencias normativas |

La discrepancia del antiguo control documental con el stack quedó actualizada por F-07; las inconsistencias del informe y los diagramas siguen abiertas. No se encontró React o SQLite como selección de la arquitectura actual; Node.js figura en una referencia bibliográfica. No se realizó comparación técnica de alternativas.

## Observaciones del modelo lógico F-14

Las cardinalidades siguientes son lecturas y alternativas condicionadas, no correcciones aprobadas del modelo.

| ID | Hallazgo | Relación con antecedentes y validación pendiente |
| --- | --- | --- |
| MOD-01 | Ventanilla–Turno indica una ventanilla obligatoria por turno, pero la FK es opcional | Si el turno puede esperar sin asignación, correspondería 0..1 ventanilla por turno y 0..N turnos históricos por ventanilla. Validar HU-04/HU-07 |
| MOD-02 | Paciente–Receta exige 1..N recetas crónicas | Considerar 0..N si hay pacientes generales o aún sin receta. No está aprobada la obligatoriedad |
| MOD-03 | Receta–Entrega no explicita claramente el extremo opcional, pese a receta_id opcional | Validar 0..1 receta por entrega o si una entrega puede agrupar varias recetas; no asumir ninguna de las dos reglas |
| MOD-04 | Usuario–Intento fallido exige usuario identificado | Definir qué evento representa. Si incluye acceso con cuenta inexistente, no puede exigir siempre un usuario |
| MOD-05 | Las FK citan Usuario.id/Paciente.id, pero las PK visibles usan id_usuario/id_paciente | Unificar referencias y comprobar integridad; faltan relaciones dibujadas para paciente–entrega, conductor–entrega y otras FK |
| MOD-06 | Entrega referencia paciente, receta y ubicación sin expresar su coherencia conjunta | Validar que receta y domicilio correspondan al paciente; precisar opcionalidades, claves y reglas de conservación histórica |
| MOD-07 | Turno no explicita unicidad de correlativo/fecha/categoría; estados no incluyen claramente ausencia | Validar ámbito de numeración, transiciones y concurrencia; no imponer una clave compuesta por suposición |
| MOD-08 | No se representan preparación, retiro posterior ni tiempos suficientes de preparación | Brecha con HU-06, HU-17, HU-18 y HU-20; no hay vínculo explícito turno–receta |
| MOD-09 | No se representan motivo de no entrega, historial de intentos o reprogramaciones ni confirmación del receptor | Brecha con HU-15, HU-16, HU-22 y NS06; un contador de receta no prueba historial de entregas |
| MOD-10 | Ubicación carece de verificación, sector y autor/fecha de actualización; notificaciones y contacto no quedan representados | Brecha con HU-12 y HU-19; solo datos ficticios en cualquier validación futura |
| MOD-11 | Lote de importación carece de detalle de errores por fila; no hay auditoría general ni tipos de atención por ventanilla | Brecha con HU-23, RNF-01 y HU-10; no autoriza añadir entidades o campos ahora |
| MOD-12 | La leyenda anuncia Crow’s Foot pero las relaciones usan flechas y etiquetas numéricas | Aclarar notación en una revisión futura. Usuario–Ventanilla no es necesariamente incorrecta: falta distinguir administración, asignación actual e historial |

## Estado de los antecedentes académicos pendientes

Se conservan A-01 a A-06 como necesidades de evidencia, no como documentos necesariamente existentes.

| ID | Evidencia requerida | Estado al 2026-11-03 |
| --- | --- | --- |
| A-01 | Enunciado o propuesta aprobada con versión vigente | F-10 aporta formulación; aprobación y enunciado vigentes no acreditados |
| A-02 | Guía, rúbrica e instrucciones vigentes | F-09 recibida parcialmente a estos efectos; falta confirmar vigencia e instrumentos sumativos completos |
| A-03 | Levantamiento validado | F-11–13 disponibles; fechas, fidelidad y validaciones pendientes |
| A-04 | Requisitos y anexos vigentes | F-10 contiene HU/RNF/NS; aprobación para este prototipo y anexos pendientes |
| A-05 | Observaciones y aprobaciones del docente/contraparte | F-12–13 contienen orientaciones, sin actas o evidencia suficiente de aprobación |
| A-06 | Reglas de datos, demostración y trabajo grupal/individual | F-09 aporta reglas grupales; compatibilidad del prototipo independiente y condiciones finales por confirmar |

## Limitaciones de consulta

- Se revisó el texto de los cinco Markdown y se inspeccionaron los dos PNG independientes. No se inspeccionaron visualmente las 10 imágenes incrustadas de F-10 ni las 9 de F-09; no quedan validados organigramas, Gantt, presupuestos ni otros contenidos exclusivamente gráficos.
- No se consultaron los anexos externos enlazados en F-10: entrevistas originales, diccionario EDT, Excel EDT v2, archivo Project y carta municipal. Sus nombres no prueban su contenido o versión.
- No se consultaron AAI, plantilla original, instrumentos EA1/EA2, Plan de Salud Municipal, publicaciones bibliográficas ni normativa original. No se certifican citas, afirmaciones jurídicas o cifras institucionales.
- Las conversiones Markdown contienen imágenes base64 y artefactos de formato. No se acredita fidelidad de conversión, paginación original, autenticidad ni aprobación. Se citan secciones, no páginas deducidas del índice.
- No se copiaron ejemplos de domicilios o identificadores de personas a esta consolidación. La recepción de antecedentes no autoriza incorporar datos reales a un futuro prototipo.

## Diagnóstico previo de skills, conservado

Revisión registrada el 2026-10-31 (F-05), sin nueva ejecución ni modificación.

| Skill | Hallazgo previo y límite vigente |
| --- | --- |
| [frontend-design](../.agents/skills/frontend-design/SKILL.md) | Lleva de planificación visual a código; fuera de esta etapa |
| [spec](../.agents/skills/spec/SKILL.md) | Puede escribir specs y generar configuración con AutoCreateBranch: true; fuera de alcance |
| [spec-impl](../.agents/skills/spec-impl/SKILL.md) | Puede crear/cambiar ramas por defecto; incompatible con irubio exclusivo |
| [web-design-guidelines](../.agents/skills/web-design-guidelines/SKILL.md) | Descarga pautas y revisa UI; no existe UI ni se autoriza ese flujo |

Las skills no son fuentes académicas ni amplían F-07. No se creó configuración para adaptar sus automatismos.
