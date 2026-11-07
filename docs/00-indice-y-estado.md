# 00. Índice y estado

Fecha de actualización: 2026-11-07.

## Estado actual

Motor de turnos y administración segura de ventanillas implementados; escenarios PostgreSQL validados por la usuaria. El código permanece pendiente de versionado. API REST, interfaces, tótem y consumidor WebSocket no están implementados.

| Dimensión | Estado |
| --- | --- |
| Implementado | Modelos/migraciones, usuarios y pacientes sintéticos, motor ponderado, restricciones, servicios y bitácora; administración de ventanillas |
| Verificado | Sintaxis revisada y 44 pruebas PostgreSQL aprobadas según F-24–25: 16 del motor y 28 de ventanillas |
| Entorno | Python 3.13.3, Django 5.2.19; 31 paquetes exactos en requirements-frozen.txt |
| PostgreSQL local | 18.6 en 127.0.0.1:5433, rol cesfam_app; recursos confirmados por la usuaria |
| Persistencia probada | Solo test_cesfam_desarrollo, con migraciones al día, conservada y accesible según la usuaria |
| No acreditado | Migraciones aplicadas en cesfam_desarrollo, Redis real, rendimiento, latencia o cumplimiento integral académico |

La suite conjunta duró 19.027 segundos, con 0 errores/fallos, código 0 y System Check sin incidencias según el mensaje de resultado F-24. No se ejecutó de nuevo durante la consolidación ni se incorporó un log original. La duración no demuestra respuesta de dos segundos.

## Índice documental

| Archivo | Propósito |
| --- | --- |
| [README](../README.md) | Estado técnico, entorno y límites de ejecución |
| [AGENTS](../AGENTS.md) | Autorización actual, restricciones e historia operativa |
| [01-fuentes-y-diagnostico.md](01-fuentes-y-diagnostico.md) | Inventario, fuentes, observaciones académicas y limitaciones |
| [02-requisitos-y-trazabilidad.md](02-requisitos-y-trazabilidad.md) | Correspondencias académicas y evidencia técnica parcial |
| [03-alcance-y-pendientes.md](03-alcance-y-pendientes.md) | Trabajo concluido y pendientes sin autorización de implementación |
| [04-registro-de-decisiones.md](04-registro-de-decisiones.md) | Decisiones históricas, sustituciones y acuerdos posteriores |
| [requirements-frozen.txt](../requirements-frozen.txt) | Instantánea revisada de dependencias instaladas |

## Autorización y versionado

F-26 autoriza solo siete documentos, comentarios de .env.example/requirements.txt y creación de requirements-frozen.txt. No habilita código, instalaciones, bases, migraciones, pruebas, staging, commits o push. Solo irubio; detenerse después de las verificaciones.

Los commits documentales cefc8e0 y 2184d47 son históricos y locales. En la revisión previa había 39 candidatos; con los seis documentos adicionales y la instantánea resultan 46 candidatos para una selección futura, todavía no preparada. docs/referencias/ permanece fuera; no usar selección indiscriminada del repositorio.

## Límites y próximos pasos

Informe N.º 1 intacto e Informe N.º 2 no iniciado; diagramas de referencia sin modificar. Persisten limitaciones de conversión, imágenes incrustadas, anexos, vigencia y aprobación académica descritas en 01.

El siguiente incremento propuesto es emisión controlada desde tótem. Identidad, revocación, cuotas, contrato y migraciones requieren aprobación específica. También siguen pendientes API, interfaces, recuperación, carga, latencia y criterios offline.

## Registros documentales históricos al 2026-11-03

Los siguientes registros se conservan como evidencia de revisiones anteriores. Sus estados de archivos y prohibiciones describen esas revisiones, no el estado actual ni una autorización nueva.

## Verificación histórica anterior al commit local cefc8e0

El siguiente registro describe la actualización previa autorizada por F-07, anterior al cierre local F-18; no es el estado actual. La comparación de contenido respecto del inicio confirmó cambios solo en los siete documentos autorizados y conservación de los otros 14 archivos locales, incluidos antecedentes, PNG, skills y configuración existente. Los 36 enlaces locales revisados son válidos. Se comprobó coherencia de fuentes, identificadores y estados de selección/aprobación. No se ejecutaron pruebas de aplicación.

La rama final verificada es `irubio`. Git mantiene AGENTS modificado y README, docs/ y .vscode/ sin seguimiento, igual que al inicio en cuanto a categorías de estado. No se crearon commits ni se realizó push. Los conteos del diff ordinario contra HEAD no representan por sí solos los cambios de esta actualización sobre archivos previamente modificados o sin seguimiento.

## Verificación de la actualización del stack completo

Se verificó coherencia de fuentes, decisiones y estados de selección en los siete documentos. Las menciones a complementos no aprobados se conservaron solo como antecedentes sustituidos. Los 37 enlaces locales comprobados son válidos y la comprobación de espacios del diff no presentó errores. La integridad de los archivos ajenos al alcance se compara mediante SHA-256 respecto del inicio de esta revisión.

No se ejecutaron operaciones Git de escritura ni se modificaron el Informe N.º 1, anexos, entrevistas, transcripciones, PNG, skills o configuraciones. No se inició el Informe N.º 2 ni se crearon código, dependencias o migraciones. El resultado se entrega para revisión y se detiene el trabajo.

## Verificación de esta consolidación

La comparación SHA-256 debe confirmar cambios exclusivamente en los diez archivos autorizados. Revisar coherencia, enlaces, valores no comentados de la plantilla y requerimientos directos; comprobar que la instantánea no contenga secretos, URLs o rutas locales. Entregar diff, lista exacta de candidatos y Git final sin preparar staging.
