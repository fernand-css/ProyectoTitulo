# Validación — 09 / Mapa y orden de visita

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Tareas: [tasks.md](tasks.md).
Fecha: 2026-11-12. Entorno previsto: pruebas de Django sobre la base de pruebas desechable; herramienta HTTP sobre una SQLite temporal; pruebas de Node con DOM simulado. Solo datos sintéticos (670 pacientes generados y domicilios con coordenadas aleatorias).
Referencia de código: ninguna todavía.
Estado: **no ejecutada**. Una plantilla con planes no es evidencia.

| RF | Prueba / pasos / comando | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| RF-09-01 | `test_ruta_consultas.py` | Hoy y atrasadas en la ruta; próximas aparte; sin intentos de otro encargado, reasignados ni anulados | — | pendiente |
| RF-09-02 | `test_ruta.py`; `test_ruta_consultas.py` | Orden determinista; 2-opt no peor que el vecino más cercano e igual a la fuerza bruta en los casos construidos; recálculo desde la última visita registrada | — | pendiente |
| RF-09-03 | `test_ruta_consultas.py`; `test_vistas_mapa.py` | Visitas sin coordenadas al final, agrupadas y rotuladas; contador en el mapa | — | pendiente |
| RF-09-04 | `test_orden_manual.py`; `test_concurrencia_ruta.py` | Orden guardado sin recálculo; idempotencia; una edición ganadora por versión; vuelve a la sugerencia al día siguiente; solo el encargado | — | pendiente |
| RF-09-05 | `test_ruta.py`; `test_ruta_consultas.py` | Visita nueva en la inserción más barata con rótulo; sin coordenadas al final; salidas eliminadas; sin rótulo tras guardar | — | pendiente |
| RF-09-06 | `test_orden_manual.py` | Vuelve a la sugerencia y queda auditado | — | pendiente |
| RF-09-07 | `test_ruta_consultas.py`; `test_vistas_mapa.py` | Solo las registradas hoy, con resultado, motivo y hora, sin número | — | pendiente |
| RF-09-08 | `test_vistas_mapa.py`; `mapa.test.cjs` | Números iguales a la lista; línea, total, atribución; aviso si fallan las teselas; sin RUT | — | pendiente |
| RF-09-09 | `ir_a.test.cjs`; `test_vistas_mapa.py` | Distancia y rumbo correctos; detención; errores en texto; ninguna solicitud de red con la posición | — | pendiente |
| RF-09-10 | `test_vistas_mapa.py`; `test_permisos_mapa.py` | Hoy igual a lo que ve el encargado; futura sugerida; pasada rechazada; Técnico y encargado sin acceso | — | pendiente |
| RF-09-11 | `test_vistas_mapa.py` | Mapa pequeño con coordenadas; texto sin ellas | — | pendiente |
| RF-09-12 | `test_configuracion_mapa.py`; `coreapp/tests/test_estaticos.py` | Valores por defecto; `E001`, `E002` y `E003`; Leaflet local con licencia; sin CDN | — | pendiente |
| RF-09-13 | `test_generar_domicilios_demo.py` | Simulación sin cambios; creación reproducible y auditada; sin tocar los existentes; rechazo sin permiso | — | pendiente |
| RF-09-14 | `test_permisos_mapa.py`; `mapa.test.cjs` | Matriz, CSRF, `no-store`, `referrerPolicy` de solo origen, auditoría sin datos personales | — | pendiente |
| RF-09-15 | `test_concurrencia_ruta.py` (3 escenarios); regresión completa | Un orden por encargado y día; una edición ganadora; sin visitas duplicadas ni perdidas; 03 al 07 sin cambios | — | pendiente |

## Regresión de la base

No ejecutada. Referencia previa: el 08 cerró con 755 pruebas (754 aprobadas y 1 error previo de `test_sala_servidor` por `WinError 32`) y 75 pruebas de Node.

## Revisión visual si aplica

No ejecutada. Pendientes:
- escritorio y celular: «Mis entregas», «Mapa», «Ir a esta parada», «Rutas» y mapa del domicilio;
- axe, navegación del mapa por teclado y zoom al 200 %;
- carga real de teselas de OpenStreetMap y ubicación real en contexto seguro.

## Límites y fallos

Sin resultados todavía. Límites conocidos de antemano:
- distancia en línea recta, sin caminos;
- el mapa base exige conexión (sin conexión: reserva 11);
- la ubicación exige HTTPS o `localhost`;
- la posición nunca llega al servidor, así que no hay evidencia del lado del servidor sobre el seguimiento;
- el origen por defecto es aproximado.

## Aplicación y reversión

Migración prevista: `entregasapp/0002_ordenruta`. No se ha aplicado en ninguna base. La base PostgreSQL del proyecto no se migra sin aprobación.

## Aceptación funcional

Pendiente.
