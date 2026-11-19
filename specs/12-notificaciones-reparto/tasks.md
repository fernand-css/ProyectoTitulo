# Tareas — 12 / Aviso de reparto en camino por correo

[Especificación](spec.md) · [Plan técnico](plan.md) · [Validación](validation.md)

Estado **Aprobado**. Desarrollo completado; recepción SMTP pendiente.

- [x] **T-12-01 — Persistir el inicio y el aviso.**  
  **RF** RF-12-02 y RF-12-03. **Depende de** aprobación del spec. Las verificaciones del esquema usan PostgreSQL sintético autorizado.  
  **Archivos** `entregasapp/models.py`, migración dependiente de `0002_ordenruta`, `entregasapp/services.py`, `entregasapp/notificaciones.py`, `cesfam/settings.py`, `.env.example` y pruebas del inicio.  
  **Hecho cuando** una operación válida guarda exactamente un inicio y aviso, el historial existente no genera eventos y se acredita rollback ante un fallo de bandeja o auditoría.
- [x] **T-12-02 — Confirmar la salida desde «Mis entregas».**  
  **RF** RF-12-01 y RF-12-02. **Depende de** T-12-01.  
  **Archivos** `entregasapp/views.py`, `entregasapp/urls.py`, `templates/entregas/_tarjeta_intento.html` y pruebas HTTP.  
  **Hecho cuando** el Encargado asignado puede completar la acción con teclado y sin JavaScript, incluso sin coordenadas. Las consultas y las solicitudes sin permiso o CSRF no crean avisos.
- [x] **T-12-03 — Procesar en modo simulado y por SMTP.**  
  **RF** RF-12-03, RF-12-04 y RF-12-05. **Depende de** T-12-01.  
  **Archivos** `entregasapp/notificaciones.py`, `entregasapp/management/commands/procesar_avisos_reparto.py` y `entregasapp/tests/test_avisos_reparto.py`.  
  **Hecho cuando** las pruebas acreditan destinos correctos, caída y reanudación, caducidad exacta, descarte de intentos desactualizados y tratamiento de fallos inciertos sin reenvíos.
- [ ] **T-12-04 — Validar el circuito y documentar la demo.**  
  **RF** RF-12-01 a RF-12-06. **Depende de** T-12-02, T-12-03 y autorización de la base y los buzones de prueba.  
  **Archivos** `README.md` y [validation.md](validation.md).  
  **Hecho cuando** quedan documentadas la regresión, la revisión de interfaz y la recepción en todos los buzones asignados del conjunto de validación real sin cruces de destinatario.

## Autorización y seguimiento

La usuaria autorizó la implementación, las migraciones y los envíos de prueba el 2026-11-18. Rama `spec-12-notificaciones-reparto`, derivada de `crojas-base@4b68242`. Las tareas T-12-01 a T-12-03 quedaron completadas. T-12-04 tiene regresión e interfaz verificadas. Falta acreditar recepción en cada buzón autorizado de la base sintética elegida.

Consulta la evidencia en [validation.md](validation.md).

## Enmienda del 2026-11-18 — Aviso del día (Borrador)

La usuaria aprobó la [enmienda](spec.md#enmienda-del-2026-11-18--aviso-del-día-borrador) y pidió implementarla el 2026-11-18. Se trabajó sobre `fdaza`, sin commit. T-12-05 a T-12-07 quedaron completas; T-12-08 tiene la documentación y la regresión, y le falta la recepción SMTP real.

- [x] **T-12-05 — Modelo, migración y configuración del aviso del día.**  
  **RF** RF-12-09 y RF-12-13. **Depende de** la aprobación de la enmienda.  
  **Archivos** `entregasapp/models.py`, `entregasapp/migrations/0005_avisoreparto_del_dia.py`, `cesfam/settings.py`, `.env.example`, `entregasapp/checks.py` y sus pruebas.  
  **Hecho cuando** la migración aplica y revierte sobre `0004`, la restricción única impide un segundo aviso del día por entrega y fecha, `check` rechaza los valores inválidos y `makemigrations --check --dry-run` no informa cambios.
- [x] **T-12-06 — Encolar y preparar el aviso del día.**  
  **RF** RF-12-07, RF-12-08, RF-12-10, RF-12-11 y RF-12-12. **Depende de** T-12-05.  
  **Archivos** `entregasapp/notificaciones.py`, `entregasapp/management/commands/procesar_avisos_reparto.py` (solo si hace falta) y `entregasapp/tests/test_aviso_del_dia.py`.  
  **Hecho cuando** las pruebas con reloj simulado acreditan la franja, las programadas durante el día, la exclusión de atrasadas, la caducidad a la hora límite, el descarte de entregas cerradas, los textos por tipo y la regresión completa de `test_avisos_reparto` sin cambios de comportamiento.
- [x] **T-12-07 — Pruebas concurrentes del aviso del día.**  
  **RF** RF-12-09. **Depende de** T-12-06.  
  **Archivos** `entregasapp/tests/test_aviso_del_dia.py`.  
  **Hecho cuando** los tres escenarios de carga con `TransactionTestCase` e hilos dejan un solo aviso del día por entrega y fecha y un solo envío.
- [ ] **T-12-08 — Documentar y validar el aviso del día.**  
  **RF** RF-12-06 ampliado y RF-12-07 a RF-12-13. **Depende de** T-12-06, T-12-07 y la base y los buzones de prueba autorizados.  
  **Archivos** `README.md`, [validation.md](validation.md) y `CLAUDE.md`.  
  **Hecho cuando** el README explica la franja y cómo dejar el procesador corriendo, la suite completa pasa y queda documentada la recepción real del aviso del día en cada buzón del conjunto de validación, sin cruces.

## Enmienda del 2026-11-18 — Destino desde el padrón (Borrador)

La usuaria aprobó la [segunda enmienda](spec.md#enmienda-del-2026-11-18--destino-desde-el-padrón-borrador) y la del spec 03 el 2026-11-18 y pidió implementarlas. Se trabajó sobre `fdaza`, sin commit. T-12-09 a T-12-11 quedaron completas; T-12-12 tiene la documentación y la regresión, y le falta la recepción SMTP real.

- [x] **T-12-09 — Configuración del freno y retiro de la lista.**  
  **RF** RF-12-14, RF-12-15 y RF-12-18. **Depende de** T-03-07.  
  **Archivos** `cesfam/settings.py`, `.env.example`, `entregasapp/checks.py` y pruebas de configuración.  
  **Hecho cuando** `REPARTO_BUZONES_PRUEBA_ARCHIVO` ya no se lee, la lista de dominios se normaliza y `check` informa E008 con dominios inválidos.
- [x] **T-12-10 — Destino desde el padrón en ambos avisos.**  
  **RF** RF-12-14 a RF-12-17. **Depende de** T-12-09.  
  **Archivos** `entregasapp/notificaciones.py`, `entregasapp/management/commands/procesar_avisos_reparto.py` y las pruebas `test_avisos_reparto`, `test_inicio_traslado` y `test_aviso_del_dia`.  
  **Hecho cuando** los dos avisos salen al correo del padrón, el freno y la falta de destino se comportan como dice el spec, la revalidación omite los cambiados y las pruebas ya no usan el archivo JSON.
- [x] **T-12-11 — Concurrencia del destino.**  
  **RF** RF-12-17. **Depende de** T-12-10 y T-03-09.  
  **Archivos** `entregasapp/tests/test_aviso_del_dia.py` o una prueba nueva.  
  **Hecho cuando** el cambio de correo simultáneo con la preparación nunca envía a un tercero, y los escenarios concurrentes existentes siguen verdes.
- [ ] **T-12-12 — Documentar y validar.**  
  **RF** RF-12-06 ampliado y RF-12-14 a RF-12-18. **Depende de** T-12-10, T-12-11 y T-03-10.  
  **Archivos** `README.md`, [validation.md](validation.md) y `CLAUDE.md`.  
  **Hecho cuando** el README describe el correo del padrón y el freno, la suite completa pasa y queda documentada la recepción real en cada buzón de prueba, sin cruces.

## Enmienda del 2026-11-18 — Envío a cualquier correo

Decidida por la usuaria en el chat («yo quiero que pueda enviarse a cualquier correo») e implementada el mismo día sobre `fdaza`, sin commit.

- [x] **T-12-13 — Dominios opcionales.**
  **RF** RF-12-15 y RF-12-18 modificados.
  **Archivos** `entregasapp/notificaciones.py` (`destino` y `encolar_del_dia`), `entregasapp/management/commands/procesar_avisos_reparto.py`, `cesfam/settings.py`, `.env.example`, `README.md`, `CLAUDE.md` y las pruebas `test_avisos_reparto` y `test_destino_padron`.
  **Hecho cuando** la lista vacía permite cualquier correo, una lista con dominios sigue restringiendo, `--smtp` funciona sin la variable y la suite completa pasa.

## Enmienda del 2026-11-18 — Avisos de reasignación y resultado

Pedida y aprobada por la usuaria en el chat («cuando la reasigne igual envia un correo, cuando marque entregada o no entregada igual»), con las opciones recomendadas. Se trabaja sobre `fdaza`, sin commit.

- [x] **T-12-14 — Tipos y migración.**
  **RF** RF-12-19 a RF-12-21. **Archivos** `entregasapp/models.py` y `entregasapp/migrations/0006_avisoreparto_resultados.py`.
  **Hecho cuando** `makemigrations --check --dry-run` no informa cambios.
- [x] **T-12-15 — Encolar en los servicios y preparar por tipo.**
  **RF** RF-12-19 a RF-12-23. **Archivos** `entregasapp/services.py`, `entregasapp/notificaciones.py`.
  **Hecho cuando** cada operación crea su aviso una sola vez y el procesador revalida y envía el texto de cada tipo.
- [x] **T-12-16 — Pruebas.**
  **RF** RF-12-19 a RF-12-23. **Archivos** `entregasapp/tests/test_avisos_resultado.py`.
  **Hecho cuando** pasan los criterios de la enmienda, incluidos tres escenarios concurrentes con `TransactionTestCase` e hilos, y la suite completa.

## Enmienda del 2026-11-18 — Envío automático desde el servidor web

Pedida y aprobada por la usuaria en el chat («necesito que el correo se envie al hacer click en el boton, no por comandos»), con las opciones recomendadas. Se trabaja sobre `fdaza`, sin commit.

- [x] **T-12-17 — Despachador y configuración.**
  **RF** RF-12-24, RF-12-26 a RF-12-28. **Archivos** `entregasapp/despachador.py`, `cesfam/asgi.py`, `cesfam/wsgi.py`, `cesfam/settings.py`, `.env.example`, `entregasapp/checks.py` (E009) y `coreapp/ejecutor_pruebas.py`.
- [x] **T-12-18 — Despertar al confirmar.**
  **RF** RF-12-25. **Archivos** `entregasapp/notificaciones.py` (`transaction.on_commit` al crear un aviso pendiente).
- [x] **T-12-19 — Pruebas y documentación de despliegue.**
  **RF** RF-12-24 a RF-12-28. **Archivos** `entregasapp/tests/test_despachador.py`, `README.md`, [validation.md](validation.md) y `CLAUDE.md`.
  **Hecho cuando** pasan los criterios de la enmienda y la suite completa, y el README explica el despliegue en AWS o Railway.
