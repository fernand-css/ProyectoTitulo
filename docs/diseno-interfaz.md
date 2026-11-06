# Interfaz de Farmacia: mostrador claro

Diseño para el equipo de Farmacia del CESFAM San Nicolás y para las personas que retiran sus medicamentos. El trabajo principal es encontrar una persona, entender el estado de su receta y atender su turno con seguridad.

## Sistema visual

- Blanco de mostrador `#FFFFFF`: navegación y superficies de trabajo.
- Niebla `#F3F6FA`: fondo, separación entre áreas y descanso visual.
- Tinta `#182C42`: texto y números de atención.
- Cobalto `#244BC3`: acciones principales, selección e identidad.
- Eucalipto `#245D50`: confirmaciones y orientación de autoservicio.
- Ámbar `#955A12`: situaciones que requieren atención, siempre con texto.

Figtree local para títulos y cifras; Atkinson Hyperlegible Next local para lectura, formularios y tablas. Escala aproximada 14/16/20/24/32/40, con números públicos mayores. Se conserva el tamaño base de 16 px elegido previamente y los tres tamaños de texto existentes.

## Composición

Se compararon dos opciones: una cabecera horizontal para todos los destinos y una columna lateral para los destinos de trabajo. Se elige la columna: deja las secciones visibles y conserva espacio para las pestañas de Recetas. Todo el contenido de trabajo se alinea a la izquierda.

```text
Personal, escritorio                  Acceso y autoservicio
┌───────────┬────────────────────┐     ┌────────────────┬───────────────┐
│ Farmacia  │ Aviso / texto Aa   │     │ Marca          │ Comunidad    │
│           ├────────────────────┤     │                │              │
│ Atención  │ Título     Acción  │     │ Formulario     │ Mostrador    │
│ Pacientes │ Pestañas           │     │ Ayuda          │ ilustrado    │
│ Recetas   │                    │     └────────────────┴───────────────┘
│           │ Área de trabajo   │
│ Cuenta    │                    │     Sala: último número y ventanilla
└───────────┴────────────────────┘     dominan sobre las demás señales.
```

En celular, la navegación inferior conserva destinos y texto; las filas se adaptan y las tablas mantienen su desplazamiento cuando es necesario. En acceso, el formulario aparece primero y la ilustración pasa debajo. En el tótem, el panel de identidad se vuelve una cabecera compacta.

## Revisión antes de construir

Se descarta repetir una cuadrícula de tarjetas iguales en Inicio. El trabajo principal ocupa una superficie cobalto; los accesos secundarios forman una lista tranquila. Los recuentos de turnos y preparación se agrupan en una sola banda porque indican trabajo pendiente real.

Se retira el menú azul oscuro de altura completa: la navegación blanca permite reservar el color intenso para la acción y el llamado. Los paneles usan bordes finos; los campos conservan bordes con contraste de componente. Se simplifican píldoras, bordes discontinuos y sombras. Las casillas de entregas se conservan como señal propia de la libreta de farmacia, sin animaciones al cargar.

La ilustración existente del mostrador sigue siendo el gesto memorable de las pantallas de acceso. No se agregan fotografías externas, fuentes remotas, efectos de entrada ni datos inventados en las pantallas de trabajo. Se mantienen los permisos, las rutas, las acciones POST, los anuncios accesibles y el comprobante térmico.

## Verificación

Revisar acceso, inicio por perfil, pacientes, recetas, preparación, cuentas, atención, tótem, sala y errores en escritorio y celular. Ejecutar las comprobaciones de Django, pruebas de presentación/contraste y pruebas JavaScript. Registrar resultados y límites al terminar; una revisión técnica no sustituye la aceptación de usuarios ni la impresión física.
