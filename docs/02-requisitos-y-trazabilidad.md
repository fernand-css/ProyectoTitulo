# 02. Requisitos y trazabilidad

Fecha de actualización: 2026-11-07. Estado: **trazabilidad académica preliminar y evidencia técnica parcial del prototipo**.

## Reglas y clases de registro

Las fuentes F-01–F-27 se identifican en [01-fuentes-y-diagnostico.md](01-fuentes-y-diagnostico.md). F-17 y F-07 describen cierres documentales anteriores. F-19–25 documentan implementación y validación posteriores; F-26 delimita la consolidación actual. Ninguna de estas autorizaciones aprueba automáticamente los requisitos del informe. Los RF-P siguen siendo identificadores locales; las HU, RNF y NS conservan los identificadores de F-10.

| Clase | Evidencia | Estado y tratamiento |
| --- | --- | --- |
| Académica | F-09, actividades y criterios de evaluación | Exigencia identificada en copia recibida; vigencia por confirmar |
| Necesidad levantada | F-11 y diálogo de F-12 | Antecedente de necesidad; fecha, alcance y validación por confirmar |
| Propuesta del equipo | F-10, F-14, F-15 y síntesis final de F-12 | No aprobada automáticamente para este prototipo |
| Decisión de la usuaria | F-06–07, F-16–17 y F-19–26; acuerdos registrados en 04 | Aprobada solo dentro del alcance explícito; autorizaciones consumidas no son permisos permanentes |
| Evidencia de implementación | Modelos, migraciones, servicios y dos clases PostgreSQL; F-22–25 | 44 escenarios aprobados según la usuaria; evidencia parcial, sin aprobación académica integral |

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

Los RF-P como formulaciones académicas integrales continúan **por validar**; las reglas operativas explícitamente aprobadas para el prototipo tienen la evidencia parcial separada más abajo. La ubicación de HU es F-10 §3.2, de RNF §3.3 y de NS §5.2.4. Las relaciones son muchos-a-muchos; no afirman equivalencia ni cobertura completa.

| ID | Antecedente / necesidad | Correspondencias de F-10 | Fuente complementaria y actor propuesto | Validación de la fuente y evidencia académica pendiente |
| --- | --- | --- | --- | --- |
| RF-P-01 | Gestión de turnos | HU-04–07, HU-10–11, HU-18; RNF-02, RNF-05; NS02–04 | F-11, farmacia; F-12, diálogo. Técnico, jefatura y paciente propuestos | Selección automática/manual, estados, ausencia y estimación. INC-03, INC-09; MOD-01, MOD-07–08. Criterios validados y futura prueba con turnos ficticios |
| RF-P-02 | Atención preferencial | HU-04, HU-07, HU-10–11; RNF-02; NS04 | F-11, farmacia. Jefatura, técnico y paciente propuestos | Categorías, ponderación, excepciones y reglas al cerrar ventanillas. No aprobar proporciones ni umbrales del informe. INC-03, INC-09; MOD-11 |
| RF-P-03 | Visualización de llamados | HU-04–05, HU-08–09; RNF-04–05; NS03, NS07 | F-11, farmacia. Técnico y paciente propuestos | Contenido visual/sonoro, accesibilidad, re-llamado y latencia. INC-07, INC-09–10; futura comprobación concordante con datos sintéticos |
| RF-P-04 | Recetas y retiro | HU-17, HU-20–21; vínculo con HU-06–07; RNF-01; NS06 como relación parcial de trazabilidad domiciliaria | F-12, diálogo sobre recetas y no retiro. Técnico y jefatura propuestos | Simulación, vigencia, preparación, retiro posterior, contador y concepto de merma. INC-05–06; MOD-02–03, MOD-06, MOD-08–09. No existe NS específico que cubra todo este RF-P |
| RF-P-05 | Importación masiva CSV/Excel | HU-23; RNF-07; dependencia HU-21; sin NS específico identificado | F-02 como antecedente; F-10 como propuesta detallada. Jefatura propuesta | Solo datos sintéticos. Columnas, duplicados, actualización parcial, reporte de errores y bitácora pendientes. INC-06, INC-10; MOD-11 |
| RF-P-06 | Trazabilidad domiciliaria | HU-12–16, HU-19, HU-22; RNF-01, RNF-03, RNF-09; NS05–06 | F-11, reparto; F-12–13. Jefatura, conductor/TENS/encargado y receptor propuestos | Roles, historial, motivos, ubicación, consulta offline y confirmación. INC-03–04, INC-08; MOD-03, MOD-05–06, MOD-09–10. No aprobar rutas, notificaciones o vista del receptor por este enlace |

Los seis RF-P nacen de F-02; F-10 aporta más detalle, con estados y aprobación pendientes. La voz, mapas, ponderaciones y formatos no se convierten en decisiones técnicas por registrarlos.


## Implementación y verificación del prototipo

| Referencia | Implementación identificada | Evidencia y límite |
| --- | --- | --- |
| RF-P-01 / HU-04–07, HU-10–11, HU-18 | Emisión, numeración independiente, llamados, estados, cierres manuales, reutilización, bitácora y servicios transaccionales | 16 pruebas de ServicioPostgreSQLTests; flujo web y varios criterios de las HU pendientes; no se implementa validación RUT ni dispensación |
| RF-P-02 / RNF-02 / NS04 | GENERAL/PREFERENCIAL, FIFO por categoría, ronda inicial provisional 2:1 configurable, ocupación y unicidades | Casos de ponderación/concurrencia del motor; no acredita carga o todo el nivel de servicio |
| RF-P-01/02 / RNF-01/02 | configurar_ventanilla, permiso administrativo, operador válido, cambios bloqueados en LLAMADO/EN_ATENCION, auditoría e historia | 28 pruebas de VentanillasPostgreSQLTests: 14 de validación/permisos, 3 de ocupación, 4 de auditoría/historia/rollback, 3 de inconsistencias/revalidación y 4 de concurrencia |
| RF-P-03 | Publicador posterior al commit, sin datos del paciente en el evento | Publicador simulado: no hay pantalla, sonido, consumidor o recuperación validados |
| RF-P-04–06 | Sin módulos de recetas, importación ni reparto | Fuera de estos incrementos; no declarar cumplimiento |
| RNF-01 | Permisos y bitácora dentro del servicio | Seguridad por endpoint, identidad del tótem y HTTPS pendientes; no acreditar seguridad integral |
| RNF-05 / NS02–03 | Sin medición de latencia o carga | 19.027 segundos es duración de suite, no cumplimiento de dos segundos |

F-24–25 registra 44/44 aprobadas, sin errores/fallos, código 0 y System Check sin incidencias, comunicados y aceptados por la usuaria. Migraciones al día solo en test_cesfam_desarrollo, conservada/accesible. No se ejecutaron de nuevo en esta consolidación ni hay log original versionado. No afirmar migración de cesfam_desarrollo.

La protección del procedimiento temporal fijó NAME y TEST.NAME a la base dedicada, bloqueó otros destinos y creación/clonación/eliminación, y usó keepdb=True, parallel=1 e interactive=False. No está incorporada automáticamente en un comando genérico de Django. Una futura ejecución requiere autorización y procedimiento revisado.

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

La selección del stack completo (D-12) y los papeles de PostgreSQL/Redis (D-13) son decisiones explícitas, distintas de la validación funcional o del cumplimiento de los RNF/NS. No aprueban por sí solas los diagramas de referencia.

| ID | Restricción o decisión vigente | Fuente / decisión | Comprobación documental |
| --- | --- | --- | --- |
| RT-01 | Solo irubio; sin operaciones de ramas ni Git de escritura | F-26; D-02/D-22 | Rama inicial/final e informe de acciones |
| RT-02 | Solo datos sintéticos; sin datos clínicos ni integración Rayén | F-17; D-03 y D-14 | Ejemplos y descripciones limitados; INC-06 abierto |
| RT-03 | Stack completo aprobado, sin nuevas selecciones | F-16–17; D-12 y F-20/F-27 | Versiones instaladas en README e instantánea; integración de componentes pendiente parcialmente |
| RT-04 | Sin nuevos cambios de código, instalaciones, bases, migraciones, pruebas ni escrituras Git en esta consolidación | F-26; D-22 | Comparación con el inicio; no repetir autorizaciones históricas |
| RT-05 | Solo diez archivos autorizados: siete documentos, comentarios de plantilla/requerimientos e instantánea; originales y skills intactos; Informe N.º 2 no iniciado | F-26; D-22–23 | Comparación SHA-256 y verificación de valores/requerimientos sin cambios |
| RT-06 | Detención tras entrega; tótem, staging, commit y siguientes actividades requieren aprobación separada | F-26; D-07/D-22 | Entrega documental y detención |
| RT-07 | PostgreSQL fuente de verdad; Redis auxiliar de mensajería y caché | F-16–17; D-13 | No atribuir a Redis el único registro de datos del negocio; políticas de caché pendientes |

RT-03 conserva su ID y amplía la selección base de D-09 mediante D-12. RT-07 sustituye su formulación anterior sobre complementos no aprobados: ese antecedente queda conservado en D-10 como histórico sustituido. No atribuir estas decisiones a F-02/F-07 ni a una aprobación institucional.

## Correspondencias tecnológicas de apoyo

Estas relaciones registran responsabilidades del stack. La evidencia parcial de implementación y pruebas se limita a la tabla anterior; no implica implementación de todos sus contratos o interfaces.

| Componente aprobado | Necesidad o referencia relacionada | Detalle todavía pendiente |
| --- | --- | --- |
| HTML5 + Alpine.js + JavaScript | Interfaces de RF-P-01–06; RNF-04, RNF-09 | Vistas, interacción, accesibilidad y alcance PWA |
| Python + Django y DRF | Operaciones de los RF-P y propuesta de API REST de F-10 §7.1 | Aplicaciones usuarios/pacientes/turnos y servicios existentes; endpoints y autenticación del tótem pendientes |
| Channels + WebSockets y Daphne | RF-P-03; RNF-05; NS03 | Configuración ASGI, eventos, autorización, reconexión, carga y medición de latencia |
| PostgreSQL | Datos de RF-P-01–06; RNF-02, RNF-08; NS04, NS06, NS08 | Modelo mínimo, restricciones y transacciones probados en la base dedicada; recuperación y modelos de otros módulos pendientes |
| Redis | Apoyo a mensajería de tiempo real y caché | Conexiones, backend de mensajería, claves, caducidad, invalidación, aislamiento y manejo de fallos. No sustituye PostgreSQL |

RNF-03, RNF-09 y NS05 mantienen sus criterios PWA/offline/sincronización por precisar según F-10. La selección de estos componentes no demuestra funcionamiento sin conexión ni define almacenamiento local o resolución de conflictos.

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
- Implementación y verificación: enlazar archivo, clase/caso de prueba, resultado, fuente y límites; no extrapolar la evidencia parcial.

La inspección de Git aporta evidencia de archivos y rama, no certifica por sí sola todas las acciones o aprobaciones.
