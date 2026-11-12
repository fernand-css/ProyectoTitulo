# Índice de especificaciones

Organización adaptada de `SDD (1).rar`: una carpeta por módulo o cambio y cuatro documentos separados. Se conservan los identificadores de dos dígitos del proyecto para mantener sus referencias.

## Specs existentes

| Spec | Estado | Especificación | Plan | Tareas | Validación |
|---|---|---|---|---|---|
| 01 — Base del proyecto | Implementado | [spec.md](01-base-del-proyecto/spec.md) | [plan.md](01-base-del-proyecto/plan.md) | [tasks.md](01-base-del-proyecto/tasks.md) | [validation.md](01-base-del-proyecto/validation.md) |
| 02 — Autenticación, roles y auditoría | Verificación técnica final aprobada; visual y cierre pendientes | [spec.md](02-autenticacion-roles-auditoria/spec.md) | [plan.md](02-autenticacion-roles-auditoria/plan.md) | [tasks.md](02-autenticacion-roles-auditoria/tasks.md) | [validation.md](02-autenticacion-roles-auditoria/validation.md) |
| 03 — Padrón y recetas | Aprobado; código y verificación técnica completos; visual/móvil/axe pendientes | [spec.md](03-padron-y-recetas/spec.md) | [plan.md](03-padron-y-recetas/plan.md) | [tasks.md](03-padron-y-recetas/tasks.md) | [validation.md](03-padron-y-recetas/validation.md) |
| 04 — Emisión de turnos | Aprobado; código y verificación técnica completos; navegador/impresión/aceptación pendientes; `fdaza` | [spec.md](04-emision-de-turnos/spec.md) | [plan.md](04-emision-de-turnos/plan.md) | [tasks.md](04-emision-de-turnos/tasks.md) | [validation.md](04-emision-de-turnos/validation.md) |
| 05 — Cola ponderada y llamado | Aprobado; seis pasos técnicos completos, HTTP y recuperación verificados; navegador/axe/usabilidad y aceptación pendientes; `fdaza` | [spec.md](05-cola-ponderada-y-llamado/spec.md) | [plan.md](05-cola-ponderada-y-llamado/plan.md) | [tasks.md](05-cola-ponderada-y-llamado/tasks.md) | [validation.md](05-cola-ponderada-y-llamado/validation.md) |
| 06 — Pantalla de sala y voz | Aprobado; código técnico completo, 100 llamados a dos pantallas con p95 444 ms; navegador/axe, hardware, usabilidad y aceptación pendientes; `fdaza` | [spec.md](06-pantalla-sala-y-voz/spec.md) | [plan.md](06-pantalla-sala-y-voz/plan.md) | [tasks.md](06-pantalla-sala-y-voz/tasks.md) | [validation.md](06-pantalla-sala-y-voz/validation.md) |
| 07 — Preparación y tiempos de espera | Aprobado; código y verificación técnica completos; navegador/axe/usabilidad y aceptación pendientes; HU-18 parcial; `fdaza` | [spec.md](07-preparacion-y-tiempos-de-espera/spec.md) | [plan.md](07-preparacion-y-tiempos-de-espera/plan.md) | [tasks.md](07-preparacion-y-tiempos-de-espera/tasks.md) | [validation.md](07-preparacion-y-tiempos-de-espera/validation.md) |
| 08 — Domicilios y entregas a domicilio | Aprobado; código y verificación técnica completos (755 pruebas, p95 HTTP < 140 ms); navegador/axe/usabilidad y aceptación pendientes; `crojas-base` | [spec.md](08-domicilios-y-entregas/spec.md) | [plan.md](08-domicilios-y-entregas/plan.md) | [tasks.md](08-domicilios-y-entregas/tasks.md) | [validation.md](08-domicilios-y-entregas/validation.md) |
| 09 — Mapa y orden de visita | Aprobado; código y verificación técnica completos (834 pruebas, p95 HTTP < 520 ms); navegador/axe/usabilidad y aceptación pendientes; `crojas-base` | [spec.md](09-mapa-y-orden-de-visita/spec.md) | [plan.md](09-mapa-y-orden-de-visita/plan.md) | [tasks.md](09-mapa-y-orden-de-visita/tasks.md) | [validation.md](09-mapa-y-orden-de-visita/validation.md) |



El spec 01 conserva su acuerdo: implementación en `fdaza`, documento aprobado en `fd686ec` y commits de implementación sujetos a instrucción del equipo. La verificación técnica y sus pendientes no equivalen a aceptación funcional del usuario.

## Números reservados

| Número | Alcance previsto | Estado |
|---|---|---|
| 11 | Modo sin conexión y caché de la PWA | Reservado; sin documento aprobado |
| 12 | Notificaciones | Reservado; sin documento aprobado |

Para una nueva spec, comprobar las carpetas, los archivos heredados y esta tabla. Si corresponde a un tema reservado, usar su número; para otros temas, usar el primer número libre sin ocupar reservas. `02` corresponde a autenticación, roles y auditoría; `03`, a padrón y recetas; `04`, a emisión de turnos; `05`, a cola ponderada y llamado; `06`, a pantalla de sala y voz con WebSocket; `07`, a preparación de medicamentos, retiro de preparados pendientes y tiempos de espera (HU-06/17/18; aprobado, con verificación técnica y aceptación pendiente; su preparación vive en `recetasapp`). HU-18 queda cubierta parcialmente porque la estimación continua solo se muestra al personal. `08`, a domicilios, programación, registro con conexión y reprogramación de entregas a domicilio (HU-12, HU-13, HU-15 con conexión y HU-16; aprobado, con verificación técnica y aceptación pendiente). `09`, a mapa, orden de visita sugerido y ajustable, guía hacia la parada en el celular y rutas por encargado para la Q.F. (HU-14; aprobado, con verificación técnica y aceptación pendiente). Propuesto sin documento: `10` para el panel de mermas e indicadores (HU-20 y lo que falta de HU-11); `10` es el primer número libre no reservado. Las reservas no crean documentos ni autorizan implementación.

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
├── 03-padron-y-recetas/
│   ├── spec.md
│   ├── plan.md
│   ├── tasks.md
│   └── validation.md
├── 04-emision-de-turnos/
│   ├── spec.md
│   ├── plan.md
│   ├── tasks.md
│   └── validation.md
├── 05-cola-ponderada-y-llamado/
│   ├── spec.md
│   ├── plan.md
│   ├── tasks.md
│   └── validation.md
├── 06-pantalla-sala-y-voz/
│   ├── spec.md
│   ├── plan.md
│   ├── tasks.md
│   └── validation.md
├── 07-preparacion-y-tiempos-de-espera/
│   ├── spec.md
│   ├── plan.md
│   ├── tasks.md
│   └── validation.md
├── 08-domicilios-y-entregas/
│   ├── spec.md
│   ├── plan.md
│   ├── tasks.md
│   └── validation.md
└── 09-mapa-y-orden-de-visita/
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
