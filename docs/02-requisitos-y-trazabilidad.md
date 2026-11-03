# 02. Requisitos y trazabilidad

Fecha de actualización: 2026-11-03. Estado: **trazabilidad preliminar; alcance funcional por validar**.

## Reglas y clases de registro

Las fuentes F-01–F-15 se identifican en [01-fuentes-y-diagnostico.md](01-fuentes-y-diagnostico.md). F-07 autoriza ampliar la documentación, no aprobar los requisitos del informe. Los RF-P siguen siendo identificadores locales; las HU, RNF y NS conservan los identificadores de F-10.

| Clase | Evidencia | Estado y tratamiento |
| --- | --- | --- |
| Académica | F-09, actividades y criterios de evaluación | Exigencia identificada en copia recibida; vigencia por confirmar |
| Necesidad levantada | F-11 y diálogo de F-12 | Antecedente de necesidad; fecha, alcance y validación por confirmar |
| Propuesta del equipo | F-10, F-14, F-15 y síntesis final de F-12 | No aprobada automáticamente para este prototipo |
| Decisión de la usuaria | F-06 y F-07; acuerdos históricos registrados en 04 | Aprobada solo dentro del alcance explícito |
| Evidencia de implementación | Ninguna en esta etapa | Sin implementación ni pruebas de aplicación |

Estados del registro: **por validar**, **en revisión**, **aprobado**, **descartado**. Las prioridades MoSCoW y los umbrales se atribuyen al informe, sin aprobarlos por transcripción. El estado de implementación y la verificación se mantienen separados.

## Trazabilidad académica identificada

Los ID AC son referencias documentales locales a F-09; no sustituyen los códigos de la guía.

| ID | Fuente exacta en F-09 | Contenido identificado | Evidencia candidata y pendiente |
| --- | --- | --- | --- |
| AC-01 | Actividad 2, pasos 2.1 y 2.2; criterio 1.1.1 | Diagnóstico de organización, problema, relevancia y complejidad | F-10 §II y F-11; verificar fuentes cuantitativas |
| AC-02 | Actividad 3, pasos 3.1 y 3.2 | Instrumentos y documentación mediante IEEE830 o HU | F-10 §III; F-11–13. Validar trazabilidad y aprobación |
| AC-03 | Actividad 4, pasos 4.1.1–4.1.2 y nota de referencias | Marco teórico, referencias y validación bibliográfica | F-10 §IV y bibliografía; originales no consultados |
| AC-04 | Actividad 5, pasos 5.1–5.3 | Solución, alcance, impacto, objetivo general y al menos cuatro específicos | F-10 §V; inconsistencias INC-02, INC-05, INC-06 |
| AC-05 | Actividad 6, pasos 6.1–6.4 | Metodología, cronograma, RACI y presupuesto | F-10 §VI y F-13; INC-01, INC-04; imágenes no verificadas |
| AC-06 | Actividades 7 y 8; criterios 1.1.4–1.1.5 | Arquitectura TI, compatibilidad y arquitectura empresarial | F-10 §§VII–VIII y F-14–15; INC-07–08 y MOD-01–12 |
| AC-07 | Instrucciones generales e indicaciones de entrega | Trabajo grupal con evaluación individual y entrega por AAI | Confirmar calendario, instrumentos y relación con prototipo independiente |

## Correspondencias de los seis antecedentes funcionales

Todos los RF-P continúan **por validar**. La ubicación de HU es F-10 §3.2, de RNF §3.3 y de NS §5.2.4. Las relaciones son muchos-a-muchos; no afirman equivalencia ni cobertura completa.

| ID | Antecedente / necesidad | Correspondencias de F-10 | Fuente complementaria y actor propuesto | Validación y evidencia esperada, aún no obtenida |
| --- | --- | --- | --- | --- |
| RF-P-01 | Gestión de turnos | HU-04–07, HU-10–11, HU-18; RNF-02, RNF-05; NS02–04 | F-11, farmacia; F-12, diálogo. Técnico, jefatura y paciente propuestos | Selección automática/manual, estados, ausencia y estimación. INC-03, INC-09; MOD-01, MOD-07–08. Criterios validados y futura prueba con turnos ficticios |
| RF-P-02 | Atención preferencial | HU-04, HU-07, HU-10–11; RNF-02; NS04 | F-11, farmacia. Jefatura, técnico y paciente propuestos | Categorías, ponderación, excepciones y reglas al cerrar ventanillas. No aprobar proporciones ni umbrales del informe. INC-03, INC-09; MOD-11 |
| RF-P-03 | Visualización de llamados | HU-04–05, HU-08–09; RNF-04–05; NS03, NS07 | F-11, farmacia. Técnico y paciente propuestos | Contenido visual/sonoro, accesibilidad, re-llamado y latencia. INC-07, INC-09–10; futura comprobación concordante con datos sintéticos |
| RF-P-04 | Recetas y retiro | HU-17, HU-20–21; vínculo con HU-06–07; RNF-01; NS06 como relación parcial de trazabilidad domiciliaria | F-12, diálogo sobre recetas y no retiro. Técnico y jefatura propuestos | Simulación, vigencia, preparación, retiro posterior, contador y concepto de merma. INC-05–06; MOD-02–03, MOD-06, MOD-08–09. No existe NS específico que cubra todo este RF-P |
| RF-P-05 | Importación masiva CSV/Excel | HU-23; RNF-07; dependencia HU-21; sin NS específico identificado | F-02 como antecedente; F-10 como propuesta detallada. Jefatura propuesta | Solo datos sintéticos. Columnas, duplicados, actualización parcial, reporte de errores y bitácora pendientes. INC-06, INC-10; MOD-11 |
| RF-P-06 | Trazabilidad domiciliaria | HU-12–16, HU-19, HU-22; RNF-01, RNF-03, RNF-09; NS05–06 | F-11, reparto; F-12–13. Jefatura, conductor/TENS/encargado y receptor propuestos | Roles, historial, motivos, ubicación, consulta offline y confirmación. INC-03–04, INC-08; MOD-03, MOD-05–06, MOD-09–10. No aprobar rutas, notificaciones o vista del receptor por este enlace |

Los seis RF-P nacen de F-02; F-10 aporta más detalle, con estados y aprobación pendientes. La voz, mapas, ponderaciones y formatos no se convierten en decisiones técnicas por registrarlos.

## Propuestas relacionadas, sin ampliar automáticamente el alcance

| Tema de F-10 | Referencias | Tratamiento documental |
| --- | --- | --- |
| Autenticación, recuperación y perfil | HU-01 Must, HU-02 Should, HU-03 Could; RNF-01 | Fuera de la cobertura explícita de los seis RF-P; mantener como propuestas por validar, sin crear un nuevo RF obligatorio |
| Indicadores y tiempos | HU-11, HU-18, HU-20; IG01–IG04 | Relación con RF-P-01/RF-P-04; validar fuentes, fórmulas y diferencia entre no retiro y merma (INC-05) |
| Notificaciones y confirmación del receptor | HU-19, HU-22 | Vinculadas preliminarmente a RF-P-06; no aprueban SMS, push, proveedor, enlaces de acceso ni mecanismo de confirmación |
| Renovación y contador de receta | HU-21 y dependencias HU-07/HU-17 | Resolver cómo se registra una entrega efectiva sin confundir emisión del turno con dispensación; la relación domiciliaria debe validarse |

HU-04–09, HU-17–18, HU-20–21 y HU-23 figuran como Must en F-10; HU-10–16, HU-19 y HU-22 como Should. Estas prioridades son del informe, no una aprobación del alcance. INC-03 registra el conflicto sobre despacho crítico.

## RNF y niveles de servicio del informe

Los RNF proceden de F-10 §3.3 y los NS de §5.2.4. La siguiente tabla registra correspondencias de la fuente; no acredita cumplimiento.

| RNF / prioridad declarada | NS asociado en F-10 | Criterio propuesto y validación pendiente |
| --- | --- | --- |
| RNF-01 Seguridad y privacidad / Must | NS06 | Roles, HTTPS y auditoría; NS06 solo cubre parte de la trazabilidad. Datos exclusivamente sintéticos; verificar controles y referencias normativas en una etapa autorizada |
| RNF-02 Concurrencia / Must | NS04 | Cero duplicaciones/asignaciones inválidas en al menos 3 escenarios; falta especificar carga y escenarios |
| RNF-03 Sin conexión / Must | NS05 | 100 % sincronizado en ≤ 5 min y cero duplicados; falta validar alcance y conflictos offline |
| RNF-04 Accesibilidad / Must | NS07 | WCAG 2.1 AA, contraste y 5 usuarios en la propuesta; falta aprobar alcance de evaluación, sin acreditar conformidad por estas métricas |
| RNF-05 Rendimiento / Must | NS02, NS03 | Respuesta ≤ 2 s en 95 % de solicitudes y despliegue de llamado ≤ 2 s; mecanismo y condiciones pendientes |
| RNF-06 Disponibilidad / Should | NS01 | ≥ 99 % mensual en horario de atención como meta de implementación, no disponibilidad demostrada del prototipo |
| RNF-07 Importación / Must | Sin NS específico | 670 registros sintéticos en la propuesta; no es población real acreditada. Reformulación de referencia a Rayén pendiente |
| RNF-08 Respaldo / Should | NS08 | Respaldo diario y recuperación ≤ 30 min; no resuelve por sí solo la promesa de cero pérdida posterior al último respaldo |
| RNF-09 Compatibilidad / Should | Sin NS específico | Dos navegadores de escritorio y un móvil; PWA instalable propuesta, por validar |

## Decisiones tecnológicas y restricciones operativas

La selección base es una decisión explícita, distinta de los requisitos anteriores.

| ID | Restricción o decisión vigente | Fuente / decisión | Comprobación documental |
| --- | --- | --- | --- |
| RT-01 | Solo irubio; sin operaciones de ramas | F-07; D-02 y D-08 | Rama inicial/final e informe de acciones |
| RT-02 | Solo datos sintéticos; sin datos clínicos ni integración Rayén | F-07; D-03 y D-08 | Ejemplos y descripciones limitados; INC-06 abierto |
| RT-03 | HTML5 + Alpine.js + JavaScript; Python + Django; PostgreSQL | F-06–07; D-09 | Stack coherente en los siete documentos; sustituye la suspensión tecnológica previa |
| RT-04 | Sin código, dependencias, migraciones, commits ni push | F-07; D-06 y D-08 | Informe de acciones y comparación de archivos |
| RT-05 | Solo siete documentos; antecedentes, PNG, skills y configuraciones intactos | F-07; D-08 | Comparación de contenidos inicial/final |
| RT-06 | Detención tras entrega; diseño e implementación requieren aprobación | F-07; D-07 y D-08 | Entrega documental y detención |
| RT-07 | DRF, Channels, Daphne y Redis no aprobados | F-07; D-10 | No declararlos seleccionados ni instalarlos |

RT-03 conserva su ID pero cambia su formulación por decisión nueva, sin atribuir esta selección al acuerdo del 2026-10-31.

## Plantilla de detalle para validación posterior

- ID estable, título, tipo y estado de validación.
- Actor propuesto o validado y necesidad.
- Fuente, versión conocida, sección exacta y limitaciones.
- Correspondencias RF-P/HU/RNF/NS y exigencia académica relacionada, cuando exista.
- Prioridad declarada en la fuente y prioridad aprobada, si llega a existir.
- Criterios de aceptación propuestos y evidencia esperada.
- Elemento del modelo/arquitectura propuesto y observaciones INC/MOD relacionadas.
- Dependencias, contradicciones y resolución documentada, si se aprueba.
- Decisión, responsable, fecha y evidencia explícita de aprobación.
- Implementación y verificación: sin evidencia en esta etapa.

La inspección de Git aporta evidencia de archivos y rama, no certifica por sí sola todas las acciones o aprobaciones.
