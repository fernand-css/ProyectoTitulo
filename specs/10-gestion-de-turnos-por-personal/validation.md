# Validación — 10 / Gestión de turnos por personal

Fecha: 2026-11-15. Entorno: Windows, venv del proyecto, Django 5.2.18. Pruebas Django sobre la base de pruebas de PostgreSQL; herramienta HTTP sobre SQLite temporal aislada con 670 pacientes sintéticos.
Referencia de código: rama `fdaza`, sin commit al registrar esta evidencia.
Estado: verificación técnica ejecutada; navegador, visor de PDF real, axe, usabilidad y aceptación pendientes.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-10-01 | `test_personal.TerminoTurnoTests`: sin confirmar, con confirmación, Técnico propia/ajena, repetición | Ventanilla deshabilitada con hora; turno de vuelta con su `entrada_cola`; otra ventanilla lo llama; rechazos sin cambios | Así: ocupación cerrada con `termino_turno`, evento `devuelto_a_cola`, auditoría `ventanilla.terminar_turno`; la ventanilla 2 lo llama; ajena → `PermissionDenied`; repetir la operación devuelve el mismo resultado | aprobado |
| RF-10-02 | `test_personal.DesactivacionCuentaTests` | Cuenta inactiva, ventanilla terminada, turno en la fila; ante fallo, nada cambia | Así, incluido el caso de fallo forzado (la cuenta sigue activa y con su ventanilla) | aprobado |
| RF-10-03 | `test_llamado_de_un_dia_anterior_se_cierra_sin_volver_a_la_cola` | `sin_atencion_cierre`, no vuelve a la cola | Así | aprobado |
| RF-10-04 | `CambioFilaTests`: C→P con contador P en 13; misma letra; llamado; desde U | P-014 con su antigüedad y registro de C-…; rechazos sin cambios | Así; la sala no recibe anuncio | aprobado |
| RF-10-05 | `test_urgencia_da_u_001_y_es_el_proximo_llamado`; vistas de historial y comprobante | U-001, próximo llamado; comprobante PDF a pantalla completa | Así; el PDF contiene U-001 y «Reemplaza a tu n…», sin RUT; solo lo abre quien marcó la urgencia (otro usuario → 404); sin impresión | aprobado (visor real pendiente) |
| RF-10-06 | `test_concurrencia_personal`: término vs cierre (3 vueltas), urgencia vs selección (3 vueltas), tres urgencias simultáneas | Un resultado coherente; sin doble asignación ni número; U consecutivos | Así; 5 de 5 corridas repetidas aprobadas; U-001, U-002 y U-003; el contador U coincide con los turnos U | aprobado |
| RF-10-07 | Auditoría, historial y sala | Historial con letra y número anteriores; auditoría sin datos personales; sin anuncio | Así: etiqueta «Cambio de fila (antes C-…)»; la auditoría guarda solo acción e identificadores | aprobado |

## Comandos y resultados reales

| Comando | Resultado |
|---|---|
| `manage.py makemigrations --check --dry-run` y `manage.py check` | Sin cambios ni problemas tras `0013_evento_numero_anterior`. |
| `manage.py test turnosapp.tests.test_personal --noinput` | 17 aprobadas. Un primer intento falló por el reloj fijo de las pruebas (`OcupacionVentanilla.apertura` toma el reloj real) y por suponer `pk=1`; se ajustaron las pruebas, no el código. |
| `manage.py test turnosapp.tests.test_concurrencia_personal --noinput` (×5) | 3 aprobadas en cada una de las 5 corridas. |
| `manage.py test --noinput --parallel 1` (primera corrida) | 942 pruebas con 2 errores: `terminar.html` y `comprobante_personal.html` no se dibujaban con contexto vacío (`coreapp.tests.test_plantillas`). Se pasaron las URLs resueltas desde la vista. |
| `manage.py test --noinput --parallel 1` (después de corregir) | **942 aprobadas** en 465,3 s (922 previas y 20 nuevas). |
| `node turnosapp/tests/*.test.cjs` | Cinco suites aprobadas. |
| `tools/verificar_spec_10_http.py` | Aprobado: 80 turnos del tótem, 30 urgencias con U-001 a U-030 consecutivos, 30 cambios de fila, sin anuncios de sala; al reanudar se llamó primero un U; término de turno de las cuatro ventanillas, con el llamado de vuelta en la fila y su entrada original. p95: urgencia 112,67 ms; cambio de fila 113,84 ms; PDF 43,71 ms; término de turno 166,68 ms (4 muestras). |

## Regresión de la base

Suite completa de 942 aprobada sobre PostgreSQL, con las concurrentes de los specs 04, 05, 06 y 09.

## Revisión visual si aplica

Pendiente: término de turno, historial con cambio de fila y urgencia, y comprobante a pantalla completa, en escritorio y móvil, con teclado, foco y axe. No se abrió un navegador en esta sesión.

## Límites y fallos

HTTP en loopback y carga secuencial. No se probó el visor de PDF de un navegador real ni con personas. Las acciones de cambio quedaron en el historial del turno y no en la lista del panel (ver «Revisión y cambios» del spec).

## Aplicación y reversión

Migración `turnosapp/0013_evento_numero_anterior` (dos campos opcionales y una restricción), reversible. La base local del proyecto no se migró.

## Aceptación funcional

Pendiente de la usuaria y del equipo.
