# 00. Índice y estado

Fecha de actualización: 2026-11-03.

## Etapa actual

**Etapa 1: planificación y organización documental.** La usuaria autorizó el 2026-11-03 una actualización controlada de siete documentos (F-07). El trabajo consolida el diagnóstico previo; no resuelve contradicciones por suposición ni autoriza diseño o implementación.

## Estado verificado y antecedentes históricos

- Rama activa al inicio de esta actualización: `irubio`.
- Estado inicial: `AGENTS.md` modificado; `README.md`, `docs/` y `.vscode/` sin seguimiento. Son cambios previos que deben preservarse.
- No existe código de aplicación ejecutable en la copia inspeccionada. No se consultaron ni incorporaron otras ramas.
- El registro del 2026-10-31 (F-03) describía un estado inicialmente limpio y el commit `69ad505`. Es información histórica, no el estado inicial de esta actualización.
- Se dispone de cinco antecedentes Markdown y dos diagramas PNG en `docs/referencias/`. Hay fuentes académicas recibidas, con vigencia y aprobaciones pendientes de confirmar.
- La usuaria seleccionó HTML5 + Alpine.js + JavaScript, Python + Django y PostgreSQL (F-06 y F-07). DRF, Channels, Daphne y Redis siguen no aprobados.
- Se conservaron los seis RF-P y se ampliaron sus correspondencias con el informe: 23 HU, 9 RNF y 8 NS. Esto no aprueba sus prioridades ni su alcance.
- Se registraron discrepancias de plazos, despliegue, roles, prioridades, indicadores, importación, arquitectura y modelo de datos.
- Los antecedentes originales, diagramas y skills no se modifican. El diagnóstico previo de skills se conserva sin ejecutar sus flujos.

## Índice documental

| Archivo | Propósito |
| --- | --- |
| [01-fuentes-y-diagnostico.md](01-fuentes-y-diagnostico.md) | Fuentes, versiones conocidas, limitaciones y hallazgos |
| [02-requisitos-y-trazabilidad.md](02-requisitos-y-trazabilidad.md) | Clases de evidencia y correspondencias RF-P/HU/RNF/NS |
| [03-alcance-y-pendientes.md](03-alcance-y-pendientes.md) | Alcance autorizado y decisiones pendientes priorizadas |
| [04-registro-de-decisiones.md](04-registro-de-decisiones.md) | Acuerdos, sustituciones parciales y cuestiones abiertas |

Consultar también [README](../README.md) y [AGENTS.md](../AGENTS.md). El inventario completo de los siete documentos de control y los siete antecedentes está en el documento 01.

## Límites de evidencia

Se revisaron los textos Markdown y los dos PNG independientes. No se inspeccionaron visualmente las imágenes incrustadas en el informe y la guía, ni se consultaron anexos externos, AAI, fuentes bibliográficas originales o normativa. No se certifica aprobación académica, fidelidad de transcripciones ni integridad de las conversiones.

Las fechas de archivo no acreditan una versión. La selección tecnológica tiene evidencia en mensajes de la usuaria; no se atribuye a una aprobación del docente o del CESFAM.

## Verificación de entrega

Comprobar coherencia entre los siete documentos, enlaces locales, fuentes e identificadores; comparar el contenido con el estado inicial y verificar que solo cambien los siete archivos autorizados. Informar rama, estado final de Git y limitaciones del diff: seis documentos ya estaban sin seguimiento y no aparecen en el diff ordinario.

La revisión es documental. No corresponden pruebas de aplicación porque no se creó código ni se instalaron dependencias.

## Resultado de la verificación del 2026-11-03

La comparación de contenido respecto del inicio confirmó cambios solo en los siete documentos autorizados y conservación de los otros 14 archivos locales, incluidos antecedentes, PNG, skills y configuración existente. Los 36 enlaces locales revisados son válidos. Se comprobó coherencia de fuentes, identificadores y estados de selección/aprobación. No se ejecutaron pruebas de aplicación.

La rama final verificada es `irubio`. Git mantiene AGENTS modificado y README, docs/ y .vscode/ sin seguimiento, igual que al inicio en cuanto a categorías de estado. No se crearon commits ni se realizó push. Los conteos del diff ordinario contra HEAD no representan por sí solos los cambios de esta actualización sobre archivos previamente modificados o sin seguimiento.

## Próximos pasos, sujetos a validación y autorización

1. Confirmar fuentes académicas vigentes y calendario.
2. Validar alcance funcional, roles, prioridades y criterios de aceptación.
3. Resolver las cuestiones de importación sintética, arquitectura y modelo registradas en 01 y 03.
4. Obtener aprobación específica antes del diseño o la implementación.

**Punto de detención:** entregar esta actualización y detenerse. La lista anterior no autoriza su ejecución.
