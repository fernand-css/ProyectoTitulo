# SPEC NN — <Nombre del módulo o cambio>

> **Estado:** Borrador
> **Depende de:** <specs existentes o ninguno>
> **Fecha:** <fecha real>
> **Objetivo:** <resultado observable en una oración>

Módulo solicitado: <NombreAPP>. Fuente: <resumen del pedido>.
Implementación autorizada: NO. Revisión del usuario: pendiente.

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md).

## Problema y resultado
<Qué necesita la persona y cómo reconocerá que fue resuelto.>

## Actores y permisos
| Acción / datos | Anónimo | Usuario/propietario | Cargos aplicables | Superusuario |
|---|---|---|---|---|
| <acción> | <permiso> | <permiso> | <permiso> | <política explícita> |

Considerar usuario inactivo, perfil ausente y acceso directo a URL. No inventar una excepción o permiso que contradiga la base sin decisión expresa.

## Alcance y exclusiones
<Incluye / no incluye. Distinguir futuro de lo solicitado.>

## Historias y flujo
<Quién hace qué, pasos y errores relevantes.>

## Requisitos funcionales
- RF-<NN>-01: CUANDO <evento>, EL SISTEMA <resultado observable>.
- RF-<NN>-02: SI <condición>, ENTONCES <validación/restricción>.

## Datos y reglas
<Campos, obligatoriedad, formatos, unicidad, relaciones, fechas, precisión, conservación y auditoría según el dominio. No elegir reglas comerciales por omisión.>

## Criterios de aceptación
| RF | Dado / cuando | Entonces |
|---|---|---|
| <ID> | <escenario normal> | <resultado verificable> |
| <ID> | <escenario inválido/límite> | <rechazo o respuesta esperada> |

## No funcionales
<Usabilidad, privacidad y desempeño con criterios acordados. No inventar SLA ni certificaciones.>

## Compatibilidad
<Flujos existentes a preservar y specs relacionadas.>

## Supuestos y decisiones pendientes
<Supuestos técnicos reversibles separados de bloqueos críticos. «Ninguno» si corresponde. Sin entrevista obligatoria.>

## Revisión y cambios
<Fecha, pedido que cambia la regla, decisión, aceptación real. No marcar aprobado sin confirmación.>
