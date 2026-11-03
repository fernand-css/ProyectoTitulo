# 04. Registro de decisiones

Fecha de actualización: 2026-11-03.

## Convención y evidencia

**Aprobada:** acuerdo explícito con fuente identificada. **Propuesta:** opción no aprobada. **Pendiente:** cuestión abierta. **Sustituida parcialmente:** conserva valor histórico y las partes no reemplazadas. **Histórica sustituida:** conserva el acuerdo anterior, pero ya no define el estado vigente.

Las fuentes se identifican en [01-fuentes-y-diagnostico.md](01-fuentes-y-diagnostico.md). Los acuerdos históricos conservan las fechas y fuentes del registro del 2026-10-31; esta actualización no acredita de nuevo mensajes anteriores ni les atribuye una aprobación académica. F-06–07 son antecedentes de la selección parcial; F-16–17 contienen la aprobación y autorización actuales del 2026-11-03. F-18 registra el cierre local anterior expresamente autorizado.

## Acuerdos históricos y estado actual

| ID | Fecha registrada | Acuerdo original y fuente | Estado al 2026-11-03 |
| --- | --- | --- | --- |
| D-01 | 2026-10-31 | Etapa 1: siete documentos y revisión de skills sin modificar; F-02 | Antecedente de la primera preparación. La actualización actual se delimita por D-14; no exige repetir revisión de skills |
| D-02 | 2026-10-31 | Solo irubio; sin operaciones de ramas, commits ni push; F-02 | Vigente, reiterado por F-17. D-15 registra la excepción puntual anterior de commit, ya ejecutada |
| D-03 | 2026-10-31 | Datos sintéticos, sin datos clínicos reales ni integración Rayén; F-02 | Vigente, reiterado por F-17 |
| D-04 | 2026-10-31 | Independencia de otros prototipos y suspensión de selección definitiva hasta comparación; F-01–02 | Sustituido parcialmente por D-09 y ampliado por D-12 en la selección tecnológica. La independencia y la prohibición de reutilización automática siguen vigentes. No se afirma que se haya realizado comparación técnica |
| D-05 | 2026-10-31 | Seis antecedentes funcionales sujetos a validación; F-02 | Vigente. F-07 autoriza correspondencias, no aprobación automática de HU/RNF/NS |
| D-06 | 2026-10-31 | Sin código, dependencias, migraciones ni cambios fuera del alcance; F-02 | Vigente, reiterado por F-17 |
| D-07 | 2026-10-31 | Autorización para cambios sustanciales y detención tras entrega; F-02 | Vigente. F-17 autoriza esta actualización y exige nueva detención |

## Decisiones explícitas y evolución

| ID | Fecha | Decisión aprobada y alcance | Fuente, fundamento y evidencia de aprobación |
| --- | --- | --- | --- |
| D-08 | 2026-11-03 | Actualizar solo AGENTS, README y docs/00–04: inventario, stack, trazabilidad e inconsistencias; preservar originales, PNG, skills y configuraciones; entregar verificación y detenerse | F-07. Antecedente de la actualización anterior; D-14 delimita la actual. No autorizó diseño, código, instalación, despliegue, commits o push |
| D-09 | 2026-11-03 | Seleccionar HTML5 + Alpine.js + JavaScript; Python + Django; PostgreSQL | F-06 y reiteración expresa en F-07. Sustituye la suspensión de selección base de D-04 y actualiza RT-03. Ampliada por D-12; conserva la selección base. No acredita comparación realizada ni aprueba versiones o configuración detallada |
| D-10 | 2026-11-03 | Acuerdo histórico: mantener Django REST Framework, Django Channels, Daphne y Redis como complementos no aprobados en ese momento | F-07. **Histórica sustituida por D-12**: los cuatro componentes están ahora aprobados. Se conserva el antecedente; no se mantiene su suspensión de selección |
| D-11 | 2026-11-03 | Conservar requisitos académicos, necesidades, propuestas del equipo y decisiones aprobadas como clases distintas | F-07, actividades 3 y 7. Autoriza documentación de correspondencias RF-P/HU/RNF/NS, sin ampliar el alcance funcional ni aprobar prioridades |
| D-12 | 2026-11-03 | Aprobar HTML5 + Alpine.js + JavaScript; Python + Django; DRF para API REST; Channels + WebSockets para tiempo real; Daphne como servidor ASGI; Redis para mensajería y caché; PostgreSQL como base de datos | F-16 y confirmación expresa F-17. Amplía D-09 y sustituye D-10. Los componentes no están pendientes de selección; no autoriza instalación, implementación ni configuración detallada |
| D-13 | 2026-11-03 | PostgreSQL es fuente de verdad para persistencia e integridad del negocio; Redis es infraestructura auxiliar de mensajería y caché | F-16–17. Los mensajes o entradas de Redis no son el único registro de turnos, recetas o entregas. No fija esquemas, claves, caducidad, invalidación o recuperación |
| D-14 | 2026-11-03 | Actualizar solo los siete documentos para reflejar D-12/D-13, conservar historial y pendientes, y detenerse tras entrega | F-17. Prohíbe modificar antecedentes, PNG, skills y configuraciones, iniciar Informe N.º 2, instalar dependencias, crear código, migrar o realizar Git de escritura. Los diagramas siguen como propuestas sujetas a validación |
| D-15 | 2026-11-03 | Cierre local anterior: exclusión local de settings.json y commit de los siete documentos, sin referencias ni push | F-18. Excepción puntual ya ejecutada: commit cefc8e0. Se registra históricamente, sin ejecutar operaciones nuevas ni modificar exclusiones en esta revisión |

La autoridad de estos acuerdos es la usuaria para este prototipo independiente. No se atribuyen al docente o al CESFAM. D-12 aprueba tecnologías y mecanismos generales; siguen pendientes versiones, configuración, estructura de aplicaciones, contratos API/eventos, esquemas, políticas de caché, recuperación y PWA/offline/sincronización. Un eventual respaldo mediante polling, uso concreto de plantillas, monolito modular, cloud y servicios externos no están decididos. No hay autorización de implementación.

## Propuestas y evolución del registro

| ID | Fecha inicial | Propuesta | Estado actual y fundamento |
| --- | --- | --- | --- |
| P-01 | 2026-10-31 | Identificadores RF-P y plantilla de trazabilidad | F-07 autoriza conservarlos y ampliar correspondencias como registro preliminar. No implica aprobación de los requisitos o de todos sus criterios |
| P-02 | 2026-10-31 | Recibir fuentes, validar alcance y comparar tecnología posteriormente | Fuentes recibidas, stack base seleccionado por D-09 y ampliado por D-12. Vigencia, alcance y mecanismos siguen pendientes; no se supone comparación realizada |
| P-03 | 2026-10-31 | Evaluar adaptación de skills a la política de rama y autorización | Sigue sin autorización de ejecución o modificación |
| P-04 | 2026-11-03 | Validar alternativas de cardinalidad y completar relaciones del modelo | Observaciones MOD-01–12, no correcciones aprobadas ni autorización de rediseño |
| P-05 | 2026-11-03 | Conciliar informe y arquitectura sobre comunicación y operación offline | Resolución parcial: D-12 aprueba DRF, Channels + WebSockets, Daphne y Redis. Persisten discrepancias del PNG, detalles de comunicación y criterios offline/sincronización de INC-07–08; no se modifica el diagrama |

INC y MOD fueron registrados el 2026-11-03 conforme a D-08. Su descripción y evidencia están en el documento 01; D-14 autoriza reflejar la resolución parcial de INC-07 por selección de componentes, sin dar por resueltas las demás cuestiones o las observaciones del modelo.

## Cuestiones pendientes

Las prioridades y condiciones de resolución se detallan en [03-alcance-y-pendientes.md](03-alcance-y-pendientes.md).

| ID | Registro inicial | Cuestión y estado al 2026-11-03 |
| --- | --- | --- |
| Q-01 | 2026-10-31 | Fuentes oficiales y vigencia: recepción parcial F-09–13, sin certificación de aprobación o versión vigente. A-01–06 siguen con evidencia incompleta |
| Q-02 | 2026-10-31 | Alcance, actores, prioridades y criterios: pendientes. Enlaces RF-P/HU/RNF/NS documentados, sin aprobación funcional |
| Q-03 | 2026-10-31 | Selección del stack completo resuelta por D-12 y responsabilidades por D-13; D-10 es histórico sustituido. Pendientes versiones, configuración ASGI/conexiones, aplicaciones, contratos API/eventos, permisos, caché, recuperación y criterios PWA/offline/sincronización. Diagramas no aprobados como diseños definitivos |
| Q-04 | 2026-10-31 | RNF y evidencias: F-10 aporta propuestas; umbrales, carga, compatibilidad, disponibilidad y recuperación por validar |
| Q-05 | 2026-10-31 | Paso a otra etapa: F-17 autoriza solo actualización documental. Configuración técnica, diseño detallado e implementación siguen sin autorización |
| Q-06 | 2026-11-03 | Calendario: INC-01 abierto; no elegir entre 14 y 6 semanas ni confundirlas con 5 semanas de unidad |
| Q-07 | 2026-11-03 | Importación: INC-06 abierto; datos solo sintéticos y ninguna integración. La prohibición de datos reales está resuelta, el requisito detallado no |
| Q-08 | 2026-11-03 | Roles, permisos y RACI: INC-04 abierto |
| Q-09 | 2026-11-03 | Entregables, demostración y despliegue: INC-02 abierto; no hay autorización actual de despliegue |
| Q-10 | 2026-11-03 | Modelo lógico: MOD-01–12 abiertos; cardinalidades y esquemas condicionados a reglas validadas. PostgreSQL es fuente de verdad por D-13, sin resolver el modelo |
| Q-11 | 2026-11-03 | Indicadores, línea base y merma: INC-05 abierto; métricas productivas no demostradas |
| Q-12 | 2026-11-03 | Citas, anexos e imágenes incrustadas: INC-11 y limitaciones de consulta abiertas |

## Regla de actualización y cierre

Todo cambio de estado debe conservar el vínculo con el acuerdo que sustituye y registrar fecha, fuente, fundamento y evidencia explícita de aprobación. No basta que una propuesta aparezca en el informe, README, AGENTS, un diagrama o un spec.

Esta actualización deja pendientes las contradicciones de los antecedentes y termina con la entrega documental. No continuar al diseño o la implementación sin aprobación posterior.
