# Tareas — 01 / Base del proyecto

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Evidencia: [validation.md](validation.md).

Estado: implementado, con los límites de verificación indicados en `validation.md`.

Estos identificadores organizan retrospectivamente los doce pasos del plan aprobado. Las casillas trasladan el estado ya registrado; no representan pruebas nuevas ni aceptación adicional. El spec original usa criterios de aceptación por categoría; las tareas se vinculan con ellos y con los pasos originales, sin inventar identificadores de requisitos retroactivos.

## Acuerdo de ejecución

Se conserva la instrucción del equipo del 2026-11-01: implementar en `fdaza`, guardar el spec aprobado en `fd686ec` y continuar de corrido con verificación final. Los commits de implementación requieren instrucción explícita del equipo.

## Seguimiento

- [x] T-01-01 — Entorno y archivos raíz.
  - Referencia: paso 1 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Arranque.
  - Depende de: ninguna.
  - Evidencia previa: Instalación, pip check y codificación de dependencias, detallada en [validation.md](validation.md).

- [x] T-01-02 — Proyecto y settings.
  - Referencia: paso 2 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Arranque.
  - Depende de: T-01-01.
  - Evidencia previa: check, migraciones en SQLite temporal y pruebas de configuración, detallada en [validation.md](validation.md).

- [x] T-01-03 — Seis apps.
  - Referencia: paso 3 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Estructura y guías.
  - Depende de: T-01-02.
  - Evidencia previa: check y estructura de seis apps, detallada en [validation.md](validation.md).

- [x] T-01-04 — RUT, roles y datos sintéticos.
  - Referencia: paso 4 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Seguridad y datos.
  - Depende de: T-01-03.
  - Evidencia previa: coreapp/tests/test_rut.py, detallada en [validation.md](validation.md).

- [x] T-01-05 — Modelos de auditoría.
  - Referencia: paso 5 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Seguridad y datos.
  - Depende de: T-01-04.
  - Evidencia previa: coreapp/tests/test_auditoria.py y control de migraciones, detallada en [validation.md](validation.md).

- [x] T-01-06 — Control de acceso por rol.
  - Referencia: paso 6 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Seguridad y datos.
  - Depende de: T-01-05.
  - Evidencia previa: coreapp/tests/test_mixins.py, detallada en [validation.md](validation.md).

- [x] T-01-07 — Contexto y filtros de plantilla.
  - Referencia: paso 7 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Accesibilidad y PWA.
  - Depende de: T-01-06.
  - Evidencia previa: coreapp/tests/test_plantillas.py, detallada en [validation.md](validation.md).

- [x] T-01-08 — Estáticos y PWA.
  - Referencia: paso 8 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Accesibilidad y PWA.
  - Depende de: T-01-07.
  - Evidencia previa: coreapp/tests/test_estaticos.py, detallada en [validation.md](validation.md).

- [x] T-01-09 — Plantillas base.
  - Referencia: paso 9 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Accesibilidad y PWA.
  - Depende de: T-01-08.
  - Evidencia previa: coreapp/tests/test_plantillas.py, detallada en [validation.md](validation.md).

- [x] T-01-10 — Vistas del núcleo.
  - Referencia: paso 10 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Navegación.
  - Depende de: T-01-09.
  - Evidencia previa: coreapp/tests/test_vistas.py y recorrido HTTP, detallada en [validation.md](validation.md).

- [x] T-01-11 — Login mínimo.
  - Referencia: paso 11 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Navegación.
  - Depende de: T-01-10.
  - Evidencia previa: usuariosapp/tests/test_login.py y recorrido HTTP, detallada en [validation.md](validation.md).

- [x] T-01-12 — Documentación y guías.
  - Referencia: paso 12 de [plan.md](plan.md#plan-de-implementación); allí se conservan los archivos, cambios y condiciones de terminado acordados.
  - Criterios de [spec.md](spec.md#criterios-de-aceptación): Estructura y guías.
  - Depende de: T-01-11.
  - Evidencia previa: Guías, árbol y archivos fuera de alcance, detallada en [validation.md](validation.md).

## Reanudación

La base está implementada. La revisión visual, instalación de la PWA desde navegador y usabilidad pendientes se detallan en [validation.md](validation.md). Las reservas 02, 06, 11 y 12 están en el [índice](../README.md); esta reorganización no inicia esos módulos.

## Aceptación del usuario

No consta una confirmación funcional posterior a la verificación en la evidencia original. Las pruebas aprobadas no se registran como aceptación del usuario.
