# 03. Alcance y pendientes

Fecha de actualización: 2026-11-07.

## Alcance actual de la consolidación

F-26 autoriza únicamente README, AGENTS, docs/00–04, comentarios de .env.example/requirements.txt y creación revisada de requirements-frozen.txt. No permite tocar código, modelos, migraciones, pruebas, bases, originales, diagramas o skills; no permite instalar, ejecutar pruebas/migraciones ni realizar staging, commits o push.

El Informe N.º 1 y sus anexos permanecen intactos. El Informe N.º 2 no está iniciado. Los antecedentes académicos y diagramas siguen sujetos a validación; las autorizaciones de la usuaria no sustituyen aprobaciones institucionales.

## Estado del prototipo y stack

El stack completo de D-12 y los papeles PostgreSQL/Redis de D-13 se mantienen. Python 3.13.3 y los paquetes instalados están registrados en README y requirements-frozen.txt. No se seleccionan componentes nuevos.

| Área | Implementado | Verificado o pendiente |
| --- | --- | --- |
| Persistencia | Usuario, paciente sintético, ventanilla, turno, cola, contador y bitácora | Modelo/migraciones probados en test_cesfam_desarrollo; desarrollo no se declara migrada |
| Motor | GENERAL/PREFERENCIAL, FIFO, ponderación 2:1 provisional configurable, numeración, estados y cierres explícitos | 16 pruebas PostgreSQL dentro de la ejecución conjunta |
| Ventanillas | Configuración administrativa, ocupación protegida, auditoría y bloqueos coherentes | 28 pruebas PostgreSQL dentro de la ejecución conjunta |
| API e interfaces | Configuración DRF y ASGI HTTP inicial | Endpoints operativos, HTML5/Alpine y flujo web pendientes |
| Tiempo real | Publicador on_commit y configuración auxiliar Redis | Redis simulado en pruebas; consumidor, recuperación y validación real pendientes |
| Tótem | Propuesta conceptual de emisión controlada | Identidad técnica, revocación, caducidad, cuota, CSRF, contrato y migraciones no aprobados para implementar |
| Otros módulos | Sin implementación en estos incrementos | Recetas, importación, reparto y criterios PWA/offline pendientes |

F-24–25 registra el resultado comunicado y aceptado por la usuaria: 44/44, 0 errores/fallos, 19.027 segundos, System Check sin incidencias y código 0. Solo test_cesfam_desarrollo tuvo migraciones/limpieza autorizadas, sin pendientes al finalizar y conservada/accesible. No es una nueva ejecución ni una medición de carga o latencia.

## Reglas operativas implementadas y límites

- Número visible separado de PK, secuencia independiente por categoría y fecha local.
- Un activo por paciente y un ocupante LLAMADO/EN_ATENCION por ventanilla.
- Ausencia manual, cancelación administrativa de pendientes y sin reapertura terminal.
- Reemisión reutiliza el activo; los pendientes antiguos no se cierran por cambio de fecha.
- Configurar ventanilla requiere permiso administrativo, operador válido y motivo de cambio.
- No deshabilitar, reasignar ni retirar operador con ocupación; sin auditoría si no hay cambios.
- Cola → ventanilla → turno, con revalidación; bitácora JSON atómica y autoría histórica preservada.
- Escrituras externas, cambios de usuarios/permisos fuera del protocolo, recuperación y capacidad permanecen como riesgos.
- La validación mediante mocks no demuestra publicación real ni entrega ordenada de eventos.

## Exclusiones y siguiente trabajo

Solo irubio; sin cambiar ramas, reutilizar otros prototipos ni incorporar docs/referencias/ al versionado. Mantener datos exclusivamente sintéticos y ausencia de integración Rayén. No instalar herramientas adicionales ni modificar PostgreSQL 17 u otras bases.

La aprobación de la implementación y de las 44 pruebas no autoriza repetir escrituras. El procedimiento protector fue temporal: nuevas pruebas requieren revisar base dedicada, rol, aislamiento y bloqueo de creación/eliminación, con autorización separada.

El siguiente incremento propuesto es emisión controlada desde tótem. No se inicia con esta consolidación. Las interfaces, WebSockets, recuperación y métricas tampoco se consideran aprobados por figurar como pendientes.

## Decisiones pendientes priorizadas

P1: condiciona alcance, evidencia o reglas centrales. P2: condiciona coherencia técnica y validación. P3: mejora documental o posible trabajo futuro. Esta prioridad ordena preguntas; no sustituye MoSCoW ni autoriza resolverlas.

| Prioridad / decisión | Asunto y evidencia | Condición de resolución |
| --- | --- | --- |
| P1 / Q-01 | Vigencia de F-09–10, instrumentos sumativos y relación entre trabajo grupal y prototipo independiente | Confirmación de encargo, versión vigente y reglas aplicables; completar A-01, A-02 y A-06 |
| P1 / Q-06 | Calendario de 14, 6 y 5 semanas; INC-01 | Calendario confirmado y alcance temporal de cada cifra, sin asumir precedencia por el orden de archivos |
| P1 / Q-02 | Alcance, prioridades y flujo completo de turnos/despacho; INC-03, INC-09 | Reglas locales del motor y ventanillas aprobadas/validadas; no equivale a aprobar íntegramente las HU o su alcance académico |
| P1 / Q-07 | Importación sintética y autonomía; INC-06 | Delimitar HU-23/RNF-07 y contrato de archivo ficticio, sin exportaciones reales ni integración |
| P1 / Q-08 | Roles y responsabilidades; INC-04 | Matriz validada de jefatura/dirección, técnico, conductor/TENS/encargado, paciente/cuidador y RACI |
| P1 / Q-09 | Demostración, cloud, capacitación, acta e implementación física; INC-02 | Acordar entregables académicos y separar futura implementación; no habilita despliegue ahora |
| P2 / Q-03 | Configuración y diseño detallado del stack aprobado; INC-07–08 | Stack seleccionado; entorno, modelo mínimo y servicios observados/validados parcialmente. Pendientes API, tótem, WebSockets, permisos por endpoint, caché, recuperación y offline; sin nuevas decisiones por suposición |
| P2 / Q-10 | Cardinalidades, esquemas e integridad del modelo; MOD-01–12 | Modelo mínimo y reglas de numeración/asignación del prototipo implementados y probados; conservar observaciones del PNG y pendientes de recetas, entregas y ubicaciones sin corregir originales |
| P2 / Q-04 | Métricas y pruebas RNF/NS; INC-10 | Aprobar umbrales, carga, entorno, recuperación y evidencias; no prometer resultados productivos |
| P2 / Q-11 | Indicadores y merma; INC-05 | Fuente, fórmula, período, población y distinción entre ausencia, no retiro y merma. No sumar poblaciones como disjuntas sin evidencia |
| P3 / Q-12 | Citas, imágenes incrustadas y anexos no consultados; INC-11 | Verificar originales y conversiones cuando se autorice; no editar documentos académicos en esta actualización |
| P3 / P-03 | Adaptación futura de skills | Propuesta y autorización separadas; no generar configuraciones ni ejecutar flujos ahora |
| Control / Q-05 | Paso al diseño o implementación | Autorizaciones posteriores consumidas para los incrementos concluidos; F-26 permite solo consolidar. Nuevo código, pruebas o Git requieren otra aprobación explícita |

## Alcances históricos y condición de cierre

F-17 cubrió exclusivamente el cierre documental del 2026-11-03. Sus prohibiciones de implementación se conservan históricamente en 04, con las ampliaciones puntuales posteriores F-19–25. No se reconstruyen como permisos generales.

Conservar las contradicciones de plazos, despliegue, roles, indicadores, importación y arquitectura académica. No ampliar funcionalidad ni dar por cumplidos todos los RF-P/HU/RNF/NS. Entregar verificaciones, lista de candidatos y Git final; staging/commit y cualquier siguiente implementación quedan pendientes de aprobación expresa.
