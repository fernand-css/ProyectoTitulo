# AGENTS.md

Fecha de actualización: 2026-11-07.

## Estado real y fuentes

Proyecto académico CESFAM San Nicolás, repositorio `fernand-css/ProyectoTitulo`, prototipo independiente desarrollado en Visual Studio Code con Codex. Trabajar exclusivamente en `irubio`; no extrapolar su estado a otras ramas.

Existen modelos, migraciones, servicios del motor de turnos y administración segura de ventanillas. La usuaria confirmó y aceptó 44 pruebas PostgreSQL aprobadas en `test_cesfam_desarrollo`. No existe aún un flujo web operativo: API, interfaces, tótem y consumidor WebSocket permanecen pendientes.

Consultar primero README y docs/00; fuentes y limitaciones en docs/01, trazabilidad en docs/02, alcance en docs/03 e historia en docs/04. Las copias académicas identifican INACAP, Proyecto de Título TIHI84; vigencia, instrumentos y aprobaciones académicas siguen pendientes de confirmación.

## Autorización actual y límites

- Verificar rama y estado de Git antes de actuar. Si la rama activa no es `irubio`, detenerse e informar; no cambiarla.
- No crear, cambiar, fusionar ni eliminar ramas.
- La autorización actual F-26 cubre exclusivamente README, AGENTS, docs/00–04, comentarios de `.env.example`, comentarios de `requirements.txt` y creación revisada de `requirements-frozen.txt`.
- Conservar `POSTGRES_PORT=5432` en la plantilla; explicar que 5433 corresponde al entorno local de la usuaria. No modificar valores de configuración.
- No modificar modelos, servicios, migraciones, pruebas, configuraciones, skills ni otros archivos. No modificar originales académicos, PNG ni `docs/referencias/`.
- No instalar, actualizar o eliminar dependencias ni modificar Python global o `.venv`. Consultar sus versiones para la instantánea no autoriza instalar.
- No modificar bases, ejecutar migraciones, pruebas PostgreSQL, servicios o despliegues. No realizar `git add`, commits, push ni otras operaciones Git de escritura.
- Registrar contradicciones como pendientes; no corregir requisitos por suposición ni ampliar alcance.
- Entregar verificaciones y detenerse. La siguiente implementación, ejecución de pruebas, staging y commit requieren autorización explícita separada.

## Autorizaciones históricas: no reutilizables

F-17 limitó el trabajo al cierre documental del 2026-11-03; ya no describe toda la implementación existente. Los commits documentales locales `cefc8e0` y `2184d47` fueron excepciones autorizadas y consumidas, sin push.

Autorizaciones posteriores permitieron el motor, la creación de `.venv`, instalación controlada, preparación local PostgreSQL, dos archivos de ventanillas y ejecución aislada de 16 y luego 44 pruebas. Son actividades terminadas, no permisos permanentes para repetirlas. Las fuentes F-19–27 y decisiones D-16–23 documentan alcance, evidencia y límites. El antiguo AGENTS que describía un MVP y specs ausentes no se convierte retrospectivamente en evidencia de esta implementación.

## Datos y contexto académico

Usar únicamente datos sintéticos sin vínculo con personas reales. No acceder, importar o copiar datos clínicos, identificadores reales, recetas, domicilios, fotografías ni exportaciones de pacientes. Anonimizar un origen clínico no lo convierte automáticamente en sintético.

No integrar Rayén ni solicitar acceso. Sus menciones en el informe son antecedentes en conflicto con estos límites. Las otras ramas son prototipos independientes del equipo: no incorporar su código o decisiones sin evaluación y autorización expresa.

Informe N.º 1 y anexos originales intactos; no comenzar ni redactar el Informe N.º 2. Las 44 pruebas acreditan escenarios técnicos del prototipo, no aprobación docente, institucional o cumplimiento completo de HU/RNF/NS. Los diagramas PNG siguen siendo propuestas sujetas a validación.

## Stack seleccionado y verificación

| Componente | Tecnología aprobada |
| --- | --- |
| Frontend | HTML5 + Alpine.js + JavaScript |
| Backend | Python + Django |
| API REST | Django REST Framework |
| Tiempo real | Django Channels + WebSockets |
| Servidor ASGI | Daphne |
| Mensajería y caché | Redis |
| Base de datos | PostgreSQL |

D-12 aprobó el stack completo, sustituyendo el carácter pendiente histórico de DRF, Channels, Daphne y Redis. PostgreSQL es fuente de verdad; Redis es auxiliar.

Entorno observado: Python 3.13.3, Django 5.2.19, DRF 3.18.3, Channels 4.3.2, Daphne 4.2.3, channels-redis 4.3.0, Psycopg/psycopg-binary 3.3.8 y redis 7.4.1. La instantánea exacta de 31 paquetes está en `requirements-frozen.txt`, sin sustituir los siete requerimientos directos.

La usuaria confirmó PostgreSQL 18.6 local en `127.0.0.1:5433`, rol `cesfam_app` y bases dedicadas. La ejecución conjunta aplicó migraciones y limpieza solo en `test_cesfam_desarrollo`, conservada y accesible. No afirmar que desarrollo está migrada. El resultado de 44/44, sin errores/fallos, código 0 y System Check sin incidencias proviene del mensaje de la usuaria; 19.027 segundos es duración de suite, no latencia. Redis estuvo simulado.

## Reglas implementadas y pendientes

El motor usa GENERAL/PREFERENCIAL, FIFO por categoría, pesos iniciales provisionales 2:1, numeración separada de PK, estados y cierres explícitos, ausencia manual y unicidades PostgreSQL.

Ventanillas ocupadas por LLAMADO/EN_ATENCION no pueden deshabilitarse, reasignarse ni perder operador. `configurar_ventanilla` valida permiso y operador; audita cambios efectivos y preserva historia. Se bloquea cola → ventanilla → turno; inconsistencias externas se rechazan sin recuperación automática.

Pendientes: identidad del tótem, API e interfaces, WebSockets reales y recuperación, cuotas, seguridad por endpoint, capacidad y latencia, recetas/importación/reparto, PWA/offline y sincronización. No seleccionar configuraciones adicionales por suposición ni atribuir al prototipo aprobación integral de requisitos académicos.

Separar exigencias académicas, necesidades levantadas, propuestas del equipo, decisiones de la usuaria, implementación y verificación. Registrar fuente, fecha conocida y limitaciones; no inventar aprobaciones, citas o fechas de mensajes.

## Skills y comunicación

Escribir en español. Las skills son material auxiliar y no amplían autorización. No modificarlas ni invocar sus flujos en esta consolidación.

`frontend-design` y `web-design-guidelines` quedan para una UI autorizada; `spec` puede generar configuración de ramas y `spec-impl` contempla crear/cambiar ramas, en conflicto con la restricción vigente. No generar configuraciones para adaptar esos automatismos. Prevalecen las instrucciones de la usuaria.

Mantener `docs/referencias/` fuera de cualquier futuro staging hasta autorización expresa. No versionar `.env`, `.venv/`, configuración local, cachés, credenciales, volcados o datos sensibles.
