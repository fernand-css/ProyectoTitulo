# CLAUDE.md

Guía para Claude Code en este repositorio. La fuente de verdad del proyecto es `docs/Informe.md` (informe del Proyecto de Título); si algo de aquí lo contradice, manda el informe, salvo las decisiones del equipo marcadas como tales.

## Proyecto

- **Qué es:** Plataforma Web Progresiva (PWA) para gestionar los turnos de atención y la trazabilidad de las entregas domiciliarias de la **Unidad de Farmacia del CESFAM San Nicolás** (DESAMU, Ñuble, Chile).
- **Problema:** ~600 pacientes diarios, 6 funcionarios y 4 ventanillas (una sola en la extensión horaria, hasta las 20:00). Los turnos se dan con dos rollos de papel (general y preferencial) que generan colisiones de números, aglomeraciones y malos tratos al personal. El reparto a domicilio (~70 postrados y ~600 mayores de 80 años) depende de direcciones rurales ambiguas («Dadinco, km 2 casa roja»); la comuna tiene 57,9 % de ruralidad y 17,1 % de adultos mayores.
- **Módulos:** gestión de turnos y filas (tótem con RUT, cola con prioridades ponderadas, llamado con voz y pantalla de sala de espera); logística de entregas (domicilios georreferenciados, orden de visita sugerido, registro sin conexión, notificaciones); recetas crónicas simuladas con entregas parciales; panel de mermas e indicadores; importación del padrón desde Rayén por archivo.
- **Alcance:** prototipo funcional en un entorno aislado, con demostración al CESFAM y al DESAMU. **Fuera de alcance:** integración por API con Rayén, geolocalización en tiempo real de los vehículos, app móvil nativa, otros CESFAM e instalación física en el establecimiento.
- **Equipo y método:** tres estudiantes (Fernanda Daza, Scrum Master; Claudio Rojas, Product Owner; Isidora Rubio, Developer). Scrum con 7 sprints quincenales en 14 semanas. Meta: el 100 % de las HU Must y al menos el 80 % de las Should cumplen la Definición de Terminado.

## Stack

| Capa | Tecnología | Notas |
|------|------------|-------|
| Presentación | PWA con **Alpine.js** | Vistas por perfil: tótem, ventanilla, pantalla de sala de espera, conductor/TENS, panel de la Jefatura y enlace directo del paciente o cuidador. |
| Lógica de negocio | **Python + Django**, API REST | Encolamiento ponderado, asignación de ventanilla, estimación de espera, vigencia de recetas, orden de visita y notificaciones. |
| Tiempo real | **WebSocket** | Sincroniza las ventanillas con la pantalla de sala. Librería por definir (el informe no la nombra). |
| Datos | **SQLite** (prototipo) | Decisión del equipo para el prototipo. El informe (§7.1) apunta a **PostgreSQL** para la implementación real: usa solo el ORM de Django, sin SQL crudo ni nada propio de SQLite que impida migrar. |
| Sin conexión | **Service Worker** + almacenamiento local | Módulo de reparto; sincronización diferida al recuperar la señal. |
| Servicios externos | SMS o push web; cartografía | Proveedores por definir. |
| Infraestructura | Cloud de bajo costo | Solo para el prototipo; la implementación real la decide el DESAMU con su unidad TIC. |

Todavía no hay código, comandos de build ni pruebas: agrégalos a este archivo cuando existan.

## Reglas obligatorias

1. **Solo datos sintéticos** (RNF-01; Leyes N° 19.628, 20.584 y 21.719, esta última vigente desde el 1-12-2026).
   - Nunca uses datos reales de pacientes ni de funcionarios en código, fixtures, seeds, pruebas, logs, capturas, issues o commits.
   - Los RUT son ficticios, pero con dígito verificador válido (módulo 11). El padrón de prueba es sintético (670 pacientes).
   - Si encuentras un archivo que parece contener datos reales, detente y avisa antes de seguir.
   - Las vistas públicas (tótem, sala de espera) nunca muestran el RUT ni el nombre del paciente.
2. **Sin API con Rayén** (RNF-07, HU-21, HU-23).
   - No escribas clientes, endpoints, credenciales ni scrapers hacia Rayén.
   - La única vía de entrada es la **importación periódica de un CSV/Excel** exportado de Rayén: valida el RUT (DV) y las columnas, detecta duplicados y actualiza los existentes, informa las filas rechazadas sin detener las válidas y deja una bitácora de quién cargó qué y cuándo.
   - Las recetas y su emisión son simuladas y propias del sistema (control interno anexo de farmacia).
3. **WCAG 2.1 nivel AA** (RNF-04, NS07). Es un requisito funcional, no opcional.
   - Contraste de al menos 4,5:1, tipografía ampliada y mensajes sin ambigüedad (usuarios mayoritariamente adultos mayores y rurales).
   - Cada llamado o re-llamado se comunica con un aviso visual y uno de voz que dicen lo mismo; nada depende solo del color ni solo del sonido.
   - Verificación: auditoría automática sin errores de nivel AA y una prueba de usabilidad con al menos 5 usuarios representativos.
4. **Sin condiciones de carrera en turnos** (RNF-02, NS04).
   - Garantías: 0 números duplicados, ningún turno asignado a dos ventanillas, ningún turno derivado a una ventanilla deshabilitada; el re-llamado conserva la asignación vigente.
   - En SQLite, `select_for_update()` no bloquea nada: **no confíes en él**. Usa `transaction.atomic()` junto con:
     - un **UPDATE condicional** sobre el estado (`Turno.objects.filter(pk=…, estado=…).update(...)`, revisando cuántas filas cambió) y reintento;
     - **restricciones únicas** en la base (número o correlativo diario, un turno activo por RUT y día) y reintento ante `IntegrityError`.
   - Así el mismo código sirve al migrar a PostgreSQL.
   - Todo cambio en emisión, llamado o asignación requiere pruebas concurrentes: al menos 3 escenarios de carga, con `TransactionTestCase` e hilos.
5. **Otros RNF clave:**
   - Respuesta de 2 s o menos en el 95 % de las solicitudes, y latencia de 2 s o menos entre la confirmación del llamado y la pantalla (RNF-05, NS02, NS03).
   - El reparto funciona sin señal y sincroniza el 100 % de los registros en 5 min o menos tras reconectar, sin duplicados (RNF-03, NS05).
   - Roles (Jefa de Farmacia, Técnico en Farmacia, Encargado de entrega, tótem); HTTPS; contraseñas con hash; auditoría de quién crea o modifica turnos, entregas y recetas (RNF-01).
   - Cada entrega guarda estado, fecha, hora y responsable; las no entregas guardan su motivo; las reprogramaciones conservan el historial (NS06).

## Historias de usuario

Resumen de §3.2 del informe. **Lee los criterios de aceptación completos en `docs/Informe.md` antes de implementar una HU.**

| ID | Historia | Módulo | Rol principal | Prioridad |
|----|----------|--------|---------------|-----------|
| HU-01 | Inicio de sesión | Autenticación | Jefa / Técnico / Encargado de terreno | Must |
| HU-02 | Restablecer contraseña | Autenticación | Jefa / Técnico / Encargado de terreno | Should |
| HU-03 | Editar perfil | Autenticación | Jefa / Técnico | Could |
| HU-04 | Llamar al siguiente paciente | Turnos y filas | Técnico en Farmacia | Must |
| HU-05 | Re-llamar a un paciente | Turnos y filas | Técnico en Farmacia | Must |
| HU-06 | Saltar turno (ausente tras 1 min) | Turnos y filas | Técnico en Farmacia | Must |
| HU-07 | Emisión de turno mediante RUT | Turnos y filas | Paciente | Must |
| HU-08 | Visualización clara de turnos | Turnos y filas | Paciente | Must |
| HU-09 | Alerta sonora | Turnos y filas | Paciente | Must |
| HU-10 | Configuración de ventanillas activas y turnos | Turnos y filas | Jefa de Farmacia | Should |
| HU-11 | Monitoreo de tiempos de espera | Mermas e indicadores | Jefa de Farmacia | Should |
| HU-12 | Dirección y referencias de domicilios | Logística de entregas | Encargado de terreno | Should |
| HU-13 | Asignación de entregas | Logística de entregas | Jefa de Farmacia | Should |
| HU-14 | Consulta de entregas domiciliarias | Logística de entregas | Encargado de terreno | Should |
| HU-15 | Registro de entregas (sin conexión) | Logística de entregas | Encargado de terreno | Should |
| HU-16 | Programación de entregas pendientes | Logística de entregas | Jefa de Farmacia | Should |
| HU-17 | Medicamentos preparados no retirados | Trazabilidad de medicamentos | Técnico en Farmacia | Must |
| HU-18 | Estimación de espera por volumen de cola | Turnos y filas | Paciente / Técnico | Must |
| HU-19 | Notificación de despacho en camino | Logística de entregas | Paciente con despacho / cuidador | Should |
| HU-20 | Panel de mermas por período | Mermas e indicadores | Director / Jefa de Farmacia | Must |
| HU-21 | Control de entregas parciales de receta crónica | Recetas (simulación Rayén) | Técnico en Farmacia | Must |
| HU-22 | Confirmación de entrega por el paciente | Logística de entregas | Paciente con despacho / cuidador | Should |
| HU-23 | Importación del padrón y recetas vigentes | Recetas (importación Rayén) | Jefa de Farmacia | Must |

**Totales:** 23 HU, de ellas 12 Must, 10 Should, 1 Could y 0 Won't.

## Flujo de trabajo

- El desarrollo es spec-driven: cada funcionalidad tiene su `specs/NN-slug.md`, diseñado con la skill `/spec` y llevado a código con `/spec-impl` (están en `.agents/skills/`). Hay una rama por spec.
- `/spec` y `/spec-impl` viven en `.agents/skills/`, no en `.claude/skills/`: Claude Code no las registra como comandos. Para usarlas, lee su `SKILL.md` y sigue las instrucciones. La carpeta `specs/` aún no existe; se crea con el primer spec.
- Subagente `django-architect` (`.claude/agents/django-architect.md`): planifica sin escribir código. Úsalo antes de una funcionalidad nueva o un cambio de estructura. Su propuesta de apps (`cuentas`, `recetas`, `turnos`, `reparto`, `indicadores`) es un punto de partida: si un spec o el código existente la contradicen, mandan ellos.
- Subagente `django-builder` (`.claude/agents/django-builder.md`): implementa el plan de `django-architect` (modelos, servicios, vistas, plantillas, comandos y pruebas). Las pruebas usan el ejecutor de Django; `pytest-django` no está en el stack.
- La interfaz, la documentación y los mensajes de commit van en español de Chile.
- Si una decisión de implementación se aparta del informe, déjala anotada en el spec que la tomó, con su motivo.
