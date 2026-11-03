# 04. Registro de decisiones

Fecha de actualización: 2026-11-03.

## Convención y evidencia

**Aprobada:** acuerdo explícito con fuente identificada. **Propuesta:** opción no aprobada. **Pendiente:** cuestión abierta. **Sustituida parcialmente:** conserva valor histórico y las partes no reemplazadas.

Las fuentes se identifican en [01-fuentes-y-diagnostico.md](01-fuentes-y-diagnostico.md). Los acuerdos históricos conservan las fechas y fuentes del registro del 2026-10-31; esta actualización no acredita de nuevo mensajes anteriores ni les atribuye una aprobación académica. F-06 y F-07 son los mensajes actuales de la usuaria del 2026-11-03.

## Acuerdos históricos y estado actual

| ID | Fecha registrada | Acuerdo original y fuente | Estado al 2026-11-03 |
| --- | --- | --- | --- |
| D-01 | 2026-10-31 | Etapa 1: siete documentos y revisión de skills sin modificar; F-02 | Antecedente de la primera preparación. La actualización actual se delimita por D-08; no exige repetir revisión de skills |
| D-02 | 2026-10-31 | Solo irubio; sin operaciones de ramas, commits ni push; F-02 | Vigente, reiterado por F-07 |
| D-03 | 2026-10-31 | Datos sintéticos, sin datos clínicos reales ni integración Rayén; F-02 | Vigente, reiterado por F-07 |
| D-04 | 2026-10-31 | Independencia de otros prototipos y suspensión de selección definitiva hasta comparación; F-01–02 | Sustituido parcialmente por D-09 en la selección base. La independencia y la prohibición de reutilización automática siguen vigentes. No se afirma que se haya realizado comparación técnica |
| D-05 | 2026-10-31 | Seis antecedentes funcionales sujetos a validación; F-02 | Vigente. F-07 autoriza correspondencias, no aprobación automática de HU/RNF/NS |
| D-06 | 2026-10-31 | Sin código, dependencias, migraciones ni cambios fuera del alcance; F-02 | Vigente, reiterado por F-07 |
| D-07 | 2026-10-31 | Autorización para cambios sustanciales y detención tras entrega; F-02 | Vigente. F-07 autoriza esta actualización y exige nueva detención |

## Decisiones explícitas actuales

| ID | Fecha | Decisión aprobada y alcance | Fuente, fundamento y evidencia de aprobación |
| --- | --- | --- | --- |
| D-08 | 2026-11-03 | Actualizar solo AGENTS, README y docs/00–04: inventario, stack, trazabilidad e inconsistencias; preservar originales, PNG, skills y configuraciones; entregar verificación y detenerse | F-07, mensaje «autorizo una actualización controlada». Consolidar estado documental sin resolver por suposición. No autoriza diseño, código, instalación, despliegue, commits o push |
| D-09 | 2026-11-03 | Seleccionar HTML5 + Alpine.js + JavaScript; Python + Django; PostgreSQL | F-06 y reiteración expresa en F-07. Sustituye la suspensión de selección base de D-04 y actualiza RT-03. No acredita comparación realizada ni aprueba versiones o arquitectura |
| D-10 | 2026-11-03 | Mantener Django REST Framework, Django Channels, Daphne y Redis como complementos no aprobados | F-07, sección «Tecnologías seleccionadas» y restricciones. No seleccionar, instalar ni tratarlos como dependencias obligatorias |
| D-11 | 2026-11-03 | Conservar requisitos académicos, necesidades, propuestas del equipo y decisiones aprobadas como clases distintas | F-07, actividades 3 y 7. Autoriza documentación de correspondencias RF-P/HU/RNF/NS, sin ampliar el alcance funcional ni aprobar prioridades |

La autoridad de estos acuerdos es la usuaria para este trabajo. No se atribuyen al docente o al CESFAM. Seleccionar el stack no autoriza implementación, API REST, WebSockets, polling, PWA/offline, monolito modular, cloud ni servicios externos.

## Propuestas y evolución del registro

| ID | Fecha inicial | Propuesta | Estado actual y fundamento |
| --- | --- | --- | --- |
| P-01 | 2026-10-31 | Identificadores RF-P y plantilla de trazabilidad | F-07 autoriza conservarlos y ampliar correspondencias como registro preliminar. No implica aprobación de los requisitos o de todos sus criterios |
| P-02 | 2026-10-31 | Recibir fuentes, validar alcance y comparar tecnología posteriormente | Fuentes recibidas y stack seleccionado por D-09. Vigencia, alcance y mecanismos siguen pendientes; no se supone comparación realizada |
| P-03 | 2026-10-31 | Evaluar adaptación de skills a la política de rama y autorización | Sigue sin autorización de ejecución o modificación |
| P-04 | 2026-11-03 | Validar alternativas de cardinalidad y completar relaciones del modelo | Observaciones MOD-01–12, no correcciones aprobadas ni autorización de rediseño |
| P-05 | 2026-11-03 | Conciliar informe y arquitectura sobre comunicación y operación offline | INC-07–08; mecanismos y complementos pendientes, sin adoptar una alternativa |

INC y MOD fueron registrados el 2026-11-03 conforme a D-08. Su descripción y evidencia están en el documento 01; no se duplican como decisiones resueltas.

## Cuestiones pendientes

Las prioridades y condiciones de resolución se detallan en [03-alcance-y-pendientes.md](03-alcance-y-pendientes.md).

| ID | Registro inicial | Cuestión y estado al 2026-11-03 |
| --- | --- | --- |
| Q-01 | 2026-10-31 | Fuentes oficiales y vigencia: recepción parcial F-09–13, sin certificación de aprobación o versión vigente. A-01–06 siguen con evidencia incompleta |
| Q-02 | 2026-10-31 | Alcance, actores, prioridades y criterios: pendientes. Enlaces RF-P/HU/RNF/NS documentados, sin aprobación funcional |
| Q-03 | 2026-10-31 | Selección tecnológica y arquitectura: selección base resuelta por D-09; arquitectura, versiones y mecanismos siguen pendientes. Complementos no aprobados por D-10 |
| Q-04 | 2026-10-31 | RNF y evidencias: F-10 aporta propuestas; umbrales, carga, compatibilidad, disponibilidad y recuperación por validar |
| Q-05 | 2026-10-31 | Paso a otra etapa: F-07 autoriza solo actualización documental. Diseño e implementación siguen sin autorización |
| Q-06 | 2026-11-03 | Calendario: INC-01 abierto; no elegir entre 14 y 6 semanas ni confundirlas con 5 semanas de unidad |
| Q-07 | 2026-11-03 | Importación: INC-06 abierto; datos solo sintéticos y ninguna integración. La prohibición de datos reales está resuelta, el requisito detallado no |
| Q-08 | 2026-11-03 | Roles, permisos y RACI: INC-04 abierto |
| Q-09 | 2026-11-03 | Entregables, demostración y despliegue: INC-02 abierto; no hay autorización actual de despliegue |
| Q-10 | 2026-11-03 | Modelo lógico: MOD-01–12 abiertos; cardinalidades alternativas condicionadas a reglas validadas |
| Q-11 | 2026-11-03 | Indicadores, línea base y merma: INC-05 abierto; métricas productivas no demostradas |
| Q-12 | 2026-11-03 | Citas, anexos e imágenes incrustadas: INC-11 y limitaciones de consulta abiertas |

## Regla de actualización y cierre

Todo cambio de estado debe conservar el vínculo con el acuerdo que sustituye y registrar fecha, fuente, fundamento y evidencia explícita de aprobación. No basta que una propuesta aparezca en el informe, README, AGENTS, un diagrama o un spec.

Esta actualización deja pendientes las contradicciones de los antecedentes y termina con la entrega documental. No continuar al diseño o la implementación sin aprobación posterior.
