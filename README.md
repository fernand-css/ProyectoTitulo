# Proyecto CESFAM San Nicolás

Prototipo académico independiente para procesos de farmacia del CESFAM San Nicolás. Rama exclusiva: `irubio`.

**Estado documental al 2026-11-07:** motor de turnos y administración segura de ventanillas implementados, con validación PostgreSQL de los escenarios descritos. Todavía no existe un flujo web operativo: API REST, interfaces HTML5/Alpine.js, tótem y consumidor WebSocket permanecen pendientes de autorización e implementación.

## Tecnologías seleccionadas y entorno observado

| Componente | Selección aprobada | Estado observado |
| --- | --- | --- |
| Frontend | HTML5 + Alpine.js + JavaScript | Interfaces pendientes |
| Backend | Python + Django | Python 3.13.3; Django 5.2.19 en `.venv` |
| API REST | Django REST Framework | 3.18.3 instalado; endpoints del prototipo pendientes |
| Tiempo real | Django Channels + WebSockets | Channels 4.3.2 instalado; consumidor y recuperación pendientes |
| Servidor ASGI | Daphne | 4.2.3 instalado; configuración ASGI HTTP preparada |
| Mensajería y caché | Redis | Cliente redis 7.4.1 y channels-redis 4.3.0; integración real no validada |
| Base de datos | PostgreSQL | Instancia local 18.6 confirmada por la usuaria; Psycopg y psycopg-binary 3.3.8 |

PostgreSQL es la fuente de verdad. Redis es infraestructura auxiliar y estuvo sustituido por un publicador simulado durante las pruebas. Instalar un componente no acredita su integración funcional.

`requirements.txt` conserva los siete requerimientos directos y sus rangos. [requirements-frozen.txt](requirements-frozen.txt) registra 31 paquetes instalados, directos y transitivos, obtenidos con `pip freeze --local`, sin modificar el entorno. Es una instantánea de Windows x64/Python 3.13.3, no un lockfile con hashes ni una garantía de portabilidad. Pip no forma parte de esa salida predeterminada.

## Funcionalidades implementadas

- Usuario personalizado, grupos y permisos; pacientes exclusivamente ficticios con identificadores `SINT-000001`. No se declara cumplida la validación RUT de HU-07.
- Categorías GENERAL/PREFERENCIAL, FIFO por emisión y PK dentro de cada categoría y ronda ponderada inicial 2:1, configurable con pesos enteros de 1 a 100. El 2:1 es provisional y aprobado para el prototipo.
- Números visibles G-001/P-001, independientes de la PK y únicos por jornada local, categoría y correlativo.
- Flujo PENDIENTE → LLAMADO → EN_ATENCION → ATENDIDO; cancelación administrativa de pendientes y ausencia manual desde LLAMADO. Sin ausencia automática ni reapertura de estados terminales.
- Reemisión que devuelve el turno activo sin modificar categoría ni consumir correlativo.
- Un turno activo por paciente y un turno LLAMADO/EN_ATENCION por ventanilla, respaldados por restricciones PostgreSQL.
- Transacciones, coordinación mediante fila compartida y bitácora persistente. Los cambios de pesos reinician el ciclo sin créditos anteriores.
- Administración de ventanillas mediante `configurar_ventanilla`: permiso administrativo, operador válido, motivo y auditoría de cambios efectivos.
- Prohibición de deshabilitar, reasignar o retirar operador con turnos LLAMADO/EN_ATENCION. Las solicitudes sin cambios no generan auditoría.
- Orden de bloqueos cola → ventanilla → turno y revalidación de referencias. Las inconsistencias externas se rechazan, sin reparación automática ni transferencia de autoría histórica.

Solo se llaman pendientes de la jornada actual. Un activo antiguo bloquea reemisión hasta su cierre autorizado; cambiar de fecha no lo cierra automáticamente. La capacidad del bloqueo global no ha sido medida.

## Evidencia de verificación y límites

| Evidencia | Resultado y procedencia |
| --- | --- |
| Reglas puras e inspección estructural | 18 pruebas puras y comprobación de modelos aprobadas en el bloque inicial; no repetidas en esta consolidación |
| Conexión Django/PostgreSQL | Seis comprobaciones coincidentes y `manage.py check` con código 0, confirmados por la usuaria |
| Regresión del motor | 16 pruebas de `ServicioPostgreSQLTests` |
| Administración de ventanillas | 28 pruebas de `VentanillasPostgreSQLTests` |
| Ejecución conjunta | **44/44 aprobadas; 0 errores y 0 fallos; 19.027 segundos; código 0; System Check sin incidencias**, según resultado comunicado y aceptado por la usuaria |

Las migraciones automáticas y la limpieza se ejecutaron **exclusivamente en `test_cesfam_desarrollo`**. La usuaria confirmó que no quedaron migraciones pendientes en esa base y que permaneció conservada y accesible. No se afirma que `cesfam_desarrollo` tenga las migraciones aplicadas. Las migraciones originales conservan sus cabeceras de generación con Django 5.2.1; el entorno instalado posterior usa 5.2.19.

Los resultados comunicados no son una nueva ejecución ni un registro de terminal incorporado al repositorio. Los 19.027 segundos son duración de la suite, no evidencia de latencia, carga ni cumplimiento de dos segundos. Tampoco certifican aprobación académica, cumplimiento integral de HU/RNF/NS o funcionamiento en producción.

## Configuración local y pruebas

Django lee las variables del proceso. Copiar [.env.example](.env.example) a `.env` no lo carga automáticamente. La plantilla no contiene credenciales y mantiene `POSTGRES_PORT=5432` como ejemplo configurable para otros equipos.

El entorno local validado de la usuaria utiliza PostgreSQL 18.6 en `127.0.0.1:5433`, rol `cesfam_app`, base de desarrollo `cesfam_desarrollo` y base de pruebas precreada `test_cesfam_desarrollo`. Cada integrante debe seleccionar explícitamente su instancia; el puerto 5433 no es una obligación compartida. No se modifica PostgreSQL 17.

Las credenciales se introducen localmente mediante ingreso oculto y se conservan solo durante la comprobación. No publicar secretos, volcados ni datos reales. El perfil HTTP local y las cookies seguras requieren configuración consciente; no se habilitan servidores en esta consolidación.

La validación conjunta utilizó un script Python temporal, iniciado desde PowerShell integrado en VS Code, que:
- verificó rama, identidad, versión, propietario y permisos;
- configuró en memoria `NAME` y `TEST.NAME` como `test_cesfam_desarrollo`;
- bloqueó conexiones Django a otros destinos, incluidos los hilos, y creación, clonación o eliminación de bases;
- seleccionó exactamente las dos clases y 44 pruebas, con `keepdb=True`, `parallel=1` e `interactive=False`;
- aplicó migraciones pendientes y limpieza solo mediante el runner, usando el publicador simulado, y eliminó el archivo temporal.

El script protector no es un archivo versionado. Un comando genérico `manage.py test` no reproduce por sí solo sus protecciones; `keepdb` conserva la base, pero permite migraciones y limpieza de datos. Cualquier nueva ejecución requiere procedimiento revisado y autorización expresa. No es necesario migrar desarrollo para preparar la base aislada de pruebas.

## Pendientes y restricciones actuales

- Emisión controlada desde tótem: identidad, activación/revocación, caducidad, cuotas, CSRF y contrato REST pendientes de aprobación; sin implementación autorizada.
- API REST e interfaces, permisos por endpoint, WebSockets, recuperación desde PostgreSQL, sonido y accesibilidad pendientes.
- Recuperación ante escrituras externas, cambios concurrentes de usuarios/permisos y capacidad del bloqueo global pendientes.
- Recetas, importación, reparto, PWA/offline y sincronización fuera de los incrementos implementados.
- Solo datos sintéticos; sin Rayén, datos clínicos reales ni reutilización automática de otras ramas.
- Informe N.º 1 y anexos originales intactos; Informe N.º 2 no iniciado; PNG sujetos a validación.
- Esta consolidación autoriza documentación e instantánea de dependencias. No autoriza cambios de código, nuevas pruebas, migraciones, servicios, staging, commits ni push.

## Documentación y versionado pendiente

Consultar [AGENTS.md](AGENTS.md) y [docs/00-indice-y-estado.md](docs/00-indice-y-estado.md). Fuentes y límites están en [01](docs/01-fuentes-y-diagnostico.md), trazabilidad en [02](docs/02-requisitos-y-trazabilidad.md), alcance en [03](docs/03-alcance-y-pendientes.md) e historia en [04](docs/04-registro-de-decisiones.md).

Los cierres documentales locales anteriores son históricos; no existe todavía un commit del código de estos incrementos. `docs/referencias/` permanece sin seguimiento y fuera de la selección futura. Se excluyen `.env`, `.venv/`, configuración local de VS Code, cachés, credenciales y datos sensibles. La revisión de archivos, staging y commit requieren autorizaciones separadas.
