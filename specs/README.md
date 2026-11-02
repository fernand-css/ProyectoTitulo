# Índice de especificaciones

Organización adaptada de `SDD (1).rar`: una carpeta por módulo o cambio y cuatro documentos separados. Se conservan los identificadores de dos dígitos del proyecto para mantener sus referencias.

## Specs existentes

| Spec | Estado | Especificación | Plan | Tareas | Validación |
|---|---|---|---|---|---|
| 01 — Base del proyecto | Implementado | [spec.md](01-base-del-proyecto/spec.md) | [plan.md](01-base-del-proyecto/plan.md) | [tasks.md](01-base-del-proyecto/tasks.md) | [validation.md](01-base-del-proyecto/validation.md) |
| 02 — Autenticación, roles y auditoría | Verificación técnica final aprobada; visual y cierre pendientes | [spec.md](02-autenticacion-roles-auditoria/spec.md) | [plan.md](02-autenticacion-roles-auditoria/plan.md) | [tasks.md](02-autenticacion-roles-auditoria/tasks.md) | [validation.md](02-autenticacion-roles-auditoria/validation.md) |
| 03 — Padrón y recetas | Aprobado; código y verificación técnica completos; visual/móvil/axe pendientes | [spec.md](03-padron-y-recetas/spec.md) | [plan.md](03-padron-y-recetas/plan.md) | [tasks.md](03-padron-y-recetas/tasks.md) | [validation.md](03-padron-y-recetas/validation.md) |

El spec 01 conserva su acuerdo: implementación en `fdaza`, documento aprobado en `fd686ec` y commits de implementación sujetos a instrucción del equipo. La verificación técnica y sus pendientes no equivalen a aceptación funcional del usuario.

## Números reservados

| Número | Alcance previsto | Estado |
|---|---|---|
| 06 | WebSocket y sincronización de turnos | Reservado; sin documento aprobado |
| 11 | Modo sin conexión y caché de la PWA | Reservado; sin documento aprobado |
| 12 | Notificaciones | Reservado; sin documento aprobado |

Para una nueva spec, comprobar las carpetas, los archivos heredados y esta tabla. Si corresponde a un tema reservado, usar su número; para otros temas, usar el primer número libre sin ocupar reservas. `02` corresponde a autenticación, roles y auditoría; `03`, a padrón y recetas; `04` es el primer número disponible para otro alcance. Las reservas no crean documentos ni autorizan implementación.

## Estructura

```text
specs/
├── README.md                   Índice central
├── 00-indice.md                 Acceso compatible al índice
├── .spec-config.yml            Configuración de ramas existente
├── _templates/
│   ├── spec.md
│   ├── plan.md
│   ├── tasks.md
│   └── validation.md
├── 01-base-del-proyecto/
│   ├── spec.md
│   ├── plan.md
│   ├── tasks.md
│   └── validation.md
├── 01-base-del-proyecto.md      Acceso compatible a la spec trasladada
├── 02-autenticacion-roles-auditoria/
│   ├── spec.md
│   ├── plan.md
│   ├── tasks.md
│   └── validation.md
└── 03-padron-y-recetas/
    ├── spec.md
    ├── plan.md
    ├── tasks.md
    └── validation.md
```

## Propósito de cada documento

| Archivo | Contenido |
|---|---|
| `spec.md` | Problema, actores, alcance, requisitos, permisos, decisiones y criterios de aceptación. |
| `plan.md` | Integración técnica, archivos, datos, riesgos y comprobaciones previstas. |
| `tasks.md` | Pasos acotados, dependencias, vínculos con requisitos y seguimiento. |
| `validation.md` | Comandos y resultados reales, evidencia, límites y aceptación pendiente. |

Las [plantillas](./_templates/spec.md) adaptan el kit al formato de estados y numeración del proyecto. No copiar ejemplos como hechos; los nuevos documentos comienzan en **Borrador**, con tareas propuestas y validación **no ejecutada**. Para nuevas specs, usar `RF-NN-01` y `T-NN-01` como identificadores estables. El spec 01 conserva sus criterios originales y relaciona sus tareas con los doce pasos del plan.

## Flujo

Requerimiento → `spec.md` → `plan.md` → `tasks.md` → revisión y aprobación → implementación autorizada → `validation.md` actualizado.

Usar `/spec` para la definición documental y `/spec-impl NN-slug` para una spec aprobada. Ambas skills leen la carpeta de la spec; la rama se deriva de `NN-slug`, no del nombre `spec.md`. Se conserva el valor de `AutoCreateBranch` en `.spec-config.yml` y cualquier acuerdo de ejecución vigente.

Al cambiar reglas o alcance, actualizar los documentos afectados sin reutilizar identificadores. Mantener el estado y las reservas en este índice. Los archivos antiguos son enlaces de acceso; la documentación canónica es la carpeta de cada spec.
