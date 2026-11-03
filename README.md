# Proyecto CESFAM San Nicolás

Proyecto académico orientado a estudiar una solución para apoyar procesos de farmacia del CESFAM San Nicolás. Este prototipo se desarrolla de forma independiente de los otros prototipos del equipo.

**Estado al 2026-11-03:** Etapa 1, planificación y organización documental. No existe una aplicación ejecutable en la copia inspeccionada de `irubio`. Se consolidaron fuentes, selección tecnológica, trazabilidad preliminar e inconsistencias; el stack completo está aprobado, mientras el alcance funcional, la configuración y el diseño detallado permanecen por validar.

## Tecnologías seleccionadas

Decisión explícita de la usuaria del 2026-11-03, confirmada en la autorización documental F-17:

| Componente | Tecnología aprobada |
| --- | --- |
| Frontend | HTML5 + Alpine.js + JavaScript |
| Backend | Python + Django |
| API REST | Django REST Framework (DRF) |
| Comunicación en tiempo real | Django Channels + WebSockets |
| Servidor ASGI | Daphne |
| Mensajería y caché | Redis |
| Base de datos | PostgreSQL |

PostgreSQL es la fuente de verdad para persistencia e integridad; Redis cumple un papel auxiliar de mensajería y caché. La aprobación de los componentes no autoriza instalarlos ni desarrollar código.

Quedan pendientes versiones, configuración, estructura de aplicaciones, contratos de API/eventos, esquemas, políticas de caché y criterios PWA/offline y de sincronización. Un eventual respaldo mediante polling no está decidido. El reparto lógico de responsabilidades está en [alcance y pendientes](docs/03-alcance-y-pendientes.md); no fija configuraciones ni despliegue.

## Antecedentes y alcance

Se mantienen seis antecedentes funcionales por validar: gestión de turnos, atención preferencial, visualización de llamados, recetas, importación masiva CSV/Excel y trazabilidad domiciliaria.

La guía académica, el informe del equipo, las entrevistas, las transcripciones y los dos diagramas están inventariados en [fuentes y diagnóstico](docs/01-fuentes-y-diagnostico.md). Las copias permiten identificar INACAP y TIHI84; quedan pendientes su vigencia y las aprobaciones correspondientes. Las 23 HU, 9 RNF y 8 NS del informe son propuestas documentadas, no un alcance automáticamente aprobado para este prototipo.

La [matriz preliminar](docs/02-requisitos-y-trazabilidad.md) enlaza RF-P con HU, RNF y NS, distinguiendo exigencias académicas, necesidades levantadas, propuestas y acuerdos. Las contradicciones académicas y técnicas no se resolvieron por suposición. Ambos diagramas PNG son propuestas técnicas sujetas a validación; su coincidencia con el stack no aprueba sus relaciones o diseño detallado. El Informe N.º 1 permanece como antecedente intacto y el Informe N.º 2 no se ha iniciado.

## Condiciones del trabajo

- Rama exclusiva: `irubio`, sin operaciones de ramas, commits ni push.
- Datos exclusivamente sintéticos; sin datos clínicos reales ni integración con Rayén.
- La importación descrita en los antecedentes no autoriza usar exportaciones reales.
- Actualización limitada a AGENTS, README y los cinco documentos 00–04.
- Antecedentes, diagramas, skills y configuraciones conservados sin modificaciones.
- Sin código, instalación de dependencias, migraciones ni despliegue.
- Detención después de la entrega documental; diseño e implementación requieren aprobación posterior.

Las instrucciones operativas completas están en [AGENTS.md](AGENTS.md).

## Documentación

| Documento | Contenido |
| --- | --- |
| [Índice y estado](docs/00-indice-y-estado.md) | Estado, revisión y límites de la entrega |
| [Fuentes y diagnóstico](docs/01-fuentes-y-diagnostico.md) | Inventario, versiones conocidas, limitaciones e inconsistencias |
| [Requisitos y trazabilidad](docs/02-requisitos-y-trazabilidad.md) | Correspondencias preliminares y evidencias por validar |
| [Alcance y pendientes](docs/03-alcance-y-pendientes.md) | Alcance autorizado y decisiones pendientes priorizadas |
| [Registro de decisiones](docs/04-registro-de-decisiones.md) | Acuerdos históricos, decisiones actuales y asuntos abiertos |

No hay instrucciones de instalación o ejecución porque no se creó una aplicación. La actualización documental no autoriza avanzar al diseño ni a la implementación.
