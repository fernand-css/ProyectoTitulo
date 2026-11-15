# Plan técnico — 10 / Gestión de turnos por personal

Spec: [spec.md](spec.md). Estado: propuesta; sin código.
Autorización de implementación: pendiente.

## Inspección de la base

- `turnosapp/atencion.py`: `ocupar` exige ventanilla sin operador; `liberar` exige que actúe el propio operador (líneas 35 y 89–106); el reincorporar está en la línea 182.
- `turnosapp/cola.py`: `cerrar_esperas_anteriores` (línea 43) solo cierra turnos «esperando»; la selección excluye ventanillas con turno llamado y aplica el rescate de 15 minutos (línea 87).
- `turnosapp/models.py`: `Turno` (`entrada_cola`, `ventanilla`, `operador`, `ultimo_llamado`, restricciones `turno_llamado_ventanilla_unico` y `turno_asignacion_coherente`), `OcupacionVentanilla` (`apertura`, `cierre`), `Ventanilla` (`habilitada`, `retirada`, `automatico`), `EventoTurno` con `secuencia`.
- `usuariosapp/services.py`: `cambiar_estado_cuenta` no toca las ventanillas.
- Depende de la enmienda del spec 04 (`Turno.letra`, contador por letra) y de RF-05-13 (fila U primera).

## Diseño propuesto

Extensión de `turnosapp/atencion.py`, sin app nueva:

- `terminar_turno_ventanilla(actor, ventanilla, operacion, confirmar)`: bajo `bloquear_cola(hoy)` y `transaction.atomic()`. Si hay un turno llamado de hoy, lo devuelve a «esperando» con UPDATE condicional (`estado="llamado"`, misma ventanilla) que limpia `ventanilla`, `operador` y `ultimo_llamado` y conserva `entrada_cola`. Si es de un día anterior, lo cierra como `sin_atencion_cierre`. Luego cierra la ocupación (`cierre=ahora`), deshabilita la ventanilla y apaga `automatico`. Registra `EventoTurno("devuelto_a_cola")` y la auditoría `ventanilla.turno_terminado`. Termina pidiendo `solicitar_seleccion`.
- `reclasificar(actor, turno, letra, operacion)` y `marcar_urgencia(actor, turno, operacion)`: UPDATE condicional sobre `estado="esperando"`; reservan el número de la serie de destino con el contador por letra del spec 04 (UPDATE condicional e `IntegrityError` reintentable); registran `EventoTurno("reclasificado"|"urgencia")` con letra y número anteriores en campos propios del evento.
- `usuariosapp/services.cambiar_estado_cuenta`: al desactivar, llama a `terminar_turno_ventanilla` con `confirmar=True` dentro de la misma transacción.

## Mapa por requisito

| RF | Archivos existentes / propuestos | Cambio previsto | Evidencia prevista |
|---|---|---|---|
| RF-10-01 | `turnosapp/atencion.py`, `views.py`, `forms.py`, plantilla de configuración de ventanillas | Servicio y acción «Término de turno» con confirmación | Pruebas de servicio, vistas y concurrencia |
| RF-10-02 | `usuariosapp/services.py` | Desactivar termina la ventanilla en la misma transacción | Prueba de servicio con rollback |
| RF-10-03 | `turnosapp/atencion.py` | Rama para turno de fecha anterior | Prueba con reloj controlado |
| RF-10-04 | `turnosapp/atencion.py`, panel `_estado.html` | Acción «Cambiar fila» en turnos en espera | Pruebas de servicio y vistas |
| RF-10-05 | `turnosapp/atencion.py`, panel, `comprobante.html` | Acción «Marcar urgencia» y comprobante | Pruebas de servicio, vistas y `.cjs` |
| RF-10-06 | `turnosapp/tests/test_concurrencia.py` | Tres escenarios con `TransactionTestCase` e hilos | Invariantes registrados |
| RF-10-07 | `turnosapp/models.py` (`EventoTurno`), auditoría | Eventos nuevos sin datos personales | Prueba de auditoría |

## Datos y contratos

- `EventoTurno.tipo` gana `devuelto_a_cola`, `reclasificado` y `urgencia`; campos opcionales `letra_anterior` y `numero_anterior`.
- `TipoAtencionVentanilla` gana el código `urgencia` (letra U), con migración de datos que lo agrega a las ventanillas existentes, según RF-05-13.
- No hay modelos nuevos. Migración de turnos solo con los campos y opciones anteriores.

## Permisos e interfaz

- «Término de turno»: botón por ventanilla en la configuración de la Q.F. y en el panel del Técnico para la propia, con diálogo de confirmación cuando hay un paciente llamado.
- «Cambiar fila» y «Marcar urgencia»: acciones por turno en la lista de espera del panel, POST con CSRF y `RolRequeridoMixin`.
- Tras reclasificar o marcar urgencia, el equipo del personal abre a pantalla completa el comprobante en PDF del tótem (vista de RF-04-08, autorizada aquí por rol y por el evento recién registrado, no por la sesión del tótem), con el número nuevo y «Reemplaza a tu número anterior». Sin impresión. «Listo, volver al panel» regresa al panel.

## Migraciones y reversión

Una migración en `turnosapp` (opciones de evento, campos opcionales del evento y tipo de ventanilla urgencia). Reversible mientras no existan eventos de los tipos nuevos. Depende de la migración de la enmienda del spec 04.

## Plan de pruebas

- Servicio: término con y sin turno llamado, de hoy y de ayer; repetición idempotente; permisos por rol; desactivación con rollback; reclasificación y urgencia en espera, llamado y cerrado.
- Concurrencia (`TransactionTestCase`, hilos, conexiones separadas): término frente a cierre de la atención; urgencia frente a selección automática; dos urgencias simultáneas. Invariantes: un llamado por ventanilla, números únicos por letra, ninguna asignación a ventanilla deshabilitada.
- Vistas: confirmación obligatoria, CSRF, roles y textos; regresión completa del 02, 04, 05 y 06.

## Riesgos, alternativas y dependencias

- Toca `atencion.py` y `cola.py`, que tienen contratos concurrentes: no modificar sin correr antes sus pruebas.
- Devolver un turno a la cola podría competir con el rescate de 15 min: es lo esperado, porque conserva su antigüedad.
- Depende de que la enmienda del spec 04 (letras y contador por letra) se implemente primero.

## Documentos afectados

`docs/estructura.md`, `README.md` y `CLAUDE.md` al implementar. Este spec y el índice ya enlazan las enmiendas de los specs 04, 05 y 06.

## Decisiones para implementar

Las decisiones funcionales quedaron resueltas el 2026-11-15. Documento aprobado el 2026-11-15. Falta autorizar la implementación y que primero se implementen la enmienda del spec 04 (letras, contador por letra y comprobante en PDF) y RF-05-13.
