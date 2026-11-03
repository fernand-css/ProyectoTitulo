# AGENTS.md

Fecha de actualización: 2026-11-03.

## Contexto y estado real

Proyecto académico CESFAM San Nicolás, repositorio `fernand-css/ProyectoTitulo`, desarrollado de forma independiente en Visual Studio Code con Codex. Las copias locales de la guía y del informe identifican INACAP y la asignatura Proyecto de Título, TIHI84. La vigencia de los instrumentos, su revisión y las aprobaciones académicas siguen pendientes de confirmación.

El proyecto permanece en la **Etapa 1: planificación y organización documental**. No existe código de aplicación ejecutable en la copia inspeccionada de `irubio`. Existen documentación, antecedentes en `docs/referencias/` y cuatro skills en `.agents/skills/`. No extrapolar este estado a otras ramas.

El antiguo AGENTS.md describía un MVP Django y seis specs ausentes de esta rama. No reconstruir esas afirmaciones como implementación, requisitos o decisiones aprobadas. La selección tecnológica actual tiene una fuente nueva y explícita.

## Autorización y límites

- Trabajar exclusivamente en `irubio`. Verificar rama y estado de Git antes de actuar. Si la rama activa es otra, detenerse e informar; no cambiarla.
- No crear, cambiar, fusionar ni eliminar ramas.
- Solicitar autorización explícita antes de cambios sustanciales. Presentar alcance, archivos afectados y plan breve; una autorización existente cubre solamente las actividades aprobadas.
- La autorización del 2026-11-03 cubre actualizar únicamente este archivo, `README.md` y `docs/00-indice-y-estado.md` a `docs/04-registro-de-decisiones.md`: inventario, decisiones, trazabilidad y registro de inconsistencias.
- No modificar los antecedentes de `docs/referencias/`, documentos académicos originales, diagramas PNG, skills, recursos, configuraciones ni otros archivos.
- No crear código, instalar dependencias, ejecutar migraciones, realizar commits ni push.
- Registrar las contradicciones como pendientes; no corregir requisitos por suposición ni ampliar automáticamente el alcance funcional.
- Detenerse después de entregar la actualización documental. Diseño e implementación requieren aprobación posterior.
- Aprobar documentación, requisitos o tecnologías no autoriza su implementación.

## Datos y autonomía del prototipo

Usar exclusivamente datos sintéticos, inventados para el proyecto y sin vínculo con personas reales. No acceder, importar, copiar ni incorporar datos clínicos reales, identificadores reales, recetas, domicilios, fotografías o exportaciones de pacientes. Un archivo anonimizado de origen clínico no se considera automáticamente sintético.

No integrar Rayén ni solicitar acceso a sus sistemas. Las menciones a exportaciones desde Rayén en el informe son antecedentes en conflicto con estos límites, no permisos. Para describir formatos, usar especificaciones sin datos personales o ejemplos totalmente ficticios.

Las otras ramas corresponden a prototipos independientes del equipo, según la usuaria. No incorporar su código, arquitectura, requisitos o decisiones como propios o aprobados. Toda eventual reutilización requiere evaluación y autorización expresa.

## Tecnologías seleccionadas

Decisión explícita de la usuaria del 2026-11-03, reiterada en la autorización documental:

- Frontend: HTML5 + Alpine.js + JavaScript.
- Backend: Python + Django.
- Base de datos: PostgreSQL.

Django REST Framework, Django Channels, Daphne y Redis son complementos **no aprobados**, pendientes de validación. No seleccionarlos ni instalarlos. Las versiones de software, API REST, WebSockets, polling, PWA/offline, monolito modular, alojamiento y despliegue no quedan aprobados por seleccionar el stack. React, SQLite y las menciones bibliográficas a Node.js no son decisiones vigentes.

## Requisitos y decisiones

Gestión de turnos, atención preferencial, visualización de llamados, recetas, importación CSV/Excel y trazabilidad domiciliaria siguen como antecedentes por validar. Las correspondencias RF-P, HU, RNF y NS documentan relaciones entre fuentes, no aprueban el alcance ni las prioridades del informe.

Separar exigencias académicas identificadas en la guía, necesidades levantadas, propuestas del equipo y decisiones explícitas de la usuaria. Registrar fuente, fecha, versión conocida, fundamento y evidencia de aprobación. No inventar citas, páginas, fechas, aprobaciones ni criterios institucionales.

Los hallazgos sobre cardinalidades, integridad referencial y relaciones faltantes se registran en el documento 01. Son observaciones y alternativas condicionadas a validación; no autorizan rediseñar los diagramas o el modelo.

Escribir la documentación y la comunicación del proyecto en español. Mantener coherencia entre README, índice, fuentes, requisitos, alcance y decisiones.

## Skills existentes

Las skills son material auxiliar; no amplían la autorización. Su diagnóstico previo está en `docs/01-fuentes-y-diagnostico.md`. No invocar sus flujos ni modificarlas en esta actualización.

- `frontend-design`: orienta diseño y código; no corresponde ejecutarla en esta etapa.
- `spec`: escribe specs y puede generar `specs/.spec-config.yml` con `AutoCreateBranch: true`.
- `spec-impl`: contempla crear y cambiar de rama automáticamente; contradice la restricción vigente.
- `web-design-guidelines`: consulta pautas externas para revisar UI; no existe UI que revisar.

Prevalecen las restricciones de la usuaria. No crear configuraciones para corregir estos conflictos sin autorización.

## Fuentes documentales

Consultar primero `README.md` y `docs/00-indice-y-estado.md`. El inventario y las limitaciones de consulta están en el documento 01. Hay copias locales de antecedentes académicos y levantamientos; su recepción no certifica vigencia, autenticidad ni aprobación. Los mensajes de la usuaria acreditan acuerdos operativos y la selección tecnológica, sin sustituir el encargo académico.
