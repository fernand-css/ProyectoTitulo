# Verificación del rediseño de interfaz

## Resultado

Se aplicó la identidad «mostrador claro» a los estilos compartidos, navegación de escritorio y celular, acceso y recuperación de cuenta, inicio por perfil, pacientes, recetas y gráficos, preparación, atención, cuentas, tótem, sala, errores y administración de Django. El sistema visual y la revisión previa están en `docs/diseno-interfaz.md`.

Se conservaron los cambios locales existentes en configuración, tamaño de texto, título de Ventanillas y archivos de specs. El rediseño no agrega migraciones ni modifica servicios de negocio.

## Comprobaciones ejecutadas

| Comprobación | Resultado |
|---|---|
| Django `check` | Sin problemas |
| Migraciones `--check --dry-run` | Sin cambios |
| Suite de coreapp, usuariosapp, recetasapp y turnosapp en PostgreSQL | 642 pruebas aprobadas; 268,542 s |
| JavaScript: menú, gráficos, cola, preparación, impresión y sala/voz | 70 pruebas aprobadas |
| Comprobación final de estáticos y vistas de tótem | 33 pruebas aprobadas |
| Revisión de diferencias | Sin errores de espacios |

La suite PostgreSQL usó una base de pruebas con nombre único, creada y eliminada por Django. No se migró ni se alteró la base del proyecto. La ejecución ampliada inicial sobre SQLite no pasó las pruebas de concurrencia y búsqueda sin acentos; se resolvió la diferencia de entorno repitiendo la suite sobre el motor del proyecto, PostgreSQL.

## Revisión en navegador

Se sirvió una aplicación ASGI en `127.0.0.1:8765` con SQLite temporal, cuatro cuentas ficticias, 48 pacientes sintéticos, recetas, entregas históricas, doce turnos y cuatro ventanillas. La pantalla de sala informó conexión en vivo.

- Escritorio a 1280 × 800: acceso, inicio, resumen de recetas, preparación, atención como Q.F. y técnico, tótem, resultado, sala y administración.
- Celular a 390 y 320 px de ancho: inicio, pacientes, ficha, detalle de receta, creación, importación, perfil, usuarios, acceso, tótem y sala. No se observó desbordamiento horizontal del documento; las pestañas conservan desplazamiento propio.
- Texto muy grande a 320 px: raíz de 22 px y documento sin desbordamiento horizontal.
- Menú «Más»: apertura, cierre mediante Escape y devolución del foco al control.
- Preparación: marcar una receta actualizó el mensaje, la fila, los contadores y la estimación.
- Tótem: recuperar un turno sintético mostró el mismo número y conservó oculta la identidad del paciente. La acción «Obtener número» terminó a 717,6 px, dentro de los 800 px de alto de la ventana de escritorio.
- Fuentes locales cargadas y controles de texto restaurados al tamaño normal al finalizar.

Las capturas de la revisión quedan como artefactos de esta conversación.

## Repetir la vista previa

```powershell
.\venv\Scripts\python.exe tools\previsualizar_interfaz.py
```

La herramienta imprime cuentas y contraseña temporal. Sirve solo en localhost, utiliza correo en memoria y elimina su base al cerrarse con Ctrl+C. La configuración PostgreSQL del proyecto permanece intacta. En Windows, el entorno de ejecución necesita permitir sockets locales para iniciar Daphne.

## Límites

Esta revisión no certifica WCAG integral ni sustituye la evaluación con usuarios representativos. Siguen pendientes la prueba de voz y altavoces del establecimiento y la impresión física en papel térmico. Se mantienen los estados de aceptación de las specs existentes.
