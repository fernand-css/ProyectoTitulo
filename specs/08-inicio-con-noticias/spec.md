# SPEC 08 — Inicio con noticias de San Nicolás

> **Estado:** Implementado técnicamente; aceptación del equipo, revisión con axe y autorización de uso de fotos pendientes
> **Depende de:** 01 (base), 02 (roles y menú)
> **Fecha:** 2026-11-04
> **Objetivo:** Al iniciar sesión, la persona ve primero las noticias recientes de San Nicolás (Municipalidad y salud), conservando el menú y los accesos que ya tenía.

Módulo: `coreapp`. Fuente: pedido de la usuaria («cambiar el inicio después de iniciar sesión… conservar el menú y las opciones tal cual, pero al inicio colocar noticias de San Nicolás»), con diseño aprobado por ella: opción «B compacta». Implementación autorizada por la usuaria el 2026-11-04 («Implementa la opción B compacta»).

Documentos: [plan.md](plan.md), [tasks.md](tasks.md), [validation.md](validation.md).

## Problema y resultado
El inicio solo tenía saludo y accesos. La unidad quiere que el primer contenido sea lo que ocurre en la comuna, sobre todo lo de salud. Se reconoce resuelto cuando, con noticias guardadas, el inicio muestra una noticia destacada con foto chica y una lista de otras cuatro, y sigue mostrando el menú, los accesos y los paneles de cada perfil.

## Actores y permisos
| Acción / datos | Anónimo | Cuenta habilitada (cualquier perfil) | Superusuario |
|---|---|---|---|
| Ver noticias en el inicio | Redirige al ingreso | Sí | Sí |
| Copiar noticias del sitio municipal (`actualizar_noticias`) | No | No (comando de servidor) | No (comando de servidor) |

Las noticias son públicas y no llevan datos de pacientes ni de funcionarios. El inicio conserva la validación de cuenta habilitada de 02.

## Alcance y exclusiones
Incluye: modelo `NoticiaComuna`, lectura del sitio municipal, comando `actualizar_noticias`, nuevo inicio (franja de saludo baja, noticia destacada, lista, accesos y paneles) y retiro de la tarjeta y del panel de «Administración» del inicio.
No incluye: noticias propias del CESFAM ni edición manual de noticias, copia de las fotos al servidor, programación automática de la actualización, ni integración con Rayén (RNF-07). «Administración» sigue en el menú lateral.

## Historias y flujo
1. El servidor ejecuta `actualizar_noticias` (a mano o programado). Se guardan texto, fecha, resumen y enlaces de hasta 24 noticias.
2. La persona inicia sesión y abre el inicio. La página solo lee la base; nunca sale a Internet.
3. Pulsa «Leer la noticia completa» o un título: se abre la noticia en el sitio de la Municipalidad, en otra pestaña.
4. Si no hay noticias guardadas, ve cómo leerlas en el sitio municipal.

## Requisitos funcionales
- RF-08-01: CUANDO se ejecuta `actualizar_noticias`, EL SISTEMA guarda por noticia número, título, fecha, primer párrafo resumido, enlace, enlace de la imagen y si trata de salud; repetirlo no duplica ni vuelve a pedir el detalle de lo ya completo.
- RF-08-02: SI el sitio municipal no responde o su formato cambia, ENTONCES el comando termina con error explicado y conserva las noticias guardadas; si falla solo el detalle de una noticia, guarda lo del listado y lo reintenta en la siguiente ejecución.
- RF-08-03: CUANDO se abre el inicio, EL SISTEMA muestra como destacada la noticia de salud más reciente con a lo más 180 días, o la más reciente de todas, y bajo «Más noticias de la comuna» las cuatro siguientes más recientes.
- RF-08-04: EL SISTEMA no copia imágenes: la foto se pide al sitio municipal desde el navegador, sin enviar la página de origen, y es decorativa (`alt` vacío); sin foto o sin fecha, la noticia se muestra completa.
- RF-08-05: EL SISTEMA descarta imágenes y enlaces que no sean `https` del sitio `www.municipalidadsannicolas.cl`.
- RF-08-06: EL SISTEMA conserva en el inicio los accesos y paneles de 02/03 por perfil, salvo la tarjeta y el panel de «Administración» del superusuario.
- RF-08-07: Los enlaces externos abren en otra pestaña con `rel="noopener noreferrer"` y lo avisan en texto para lectores de pantalla.

## Datos y reglas
`NoticiaComuna`: `id_externo` único, `titulo` (300), `resumen`, `publicada_el` (nula si no se pudo leer; va al final), `url`, `imagen_url`, `es_salud`, `obtenida_en`. «Salud» se decide por palabras clave (salud, CESFAM, vacuna, influenza, hospital, posta, médico, farmacia, paciente, sanitaria). No hay auditoría de usuario porque la escribe un comando, no una persona.

## Criterios de aceptación
| RF | Dado / cuando | Entonces |
|---|---|---|
| RF-08-01 | Sitio con 3 noticias | Se guardan 3 con fecha y resumen; una segunda ejecución informa 0 nuevas y no pide los detalles. |
| RF-08-02 | Sitio caído o sin tarjetas | Error del comando y 3 noticias intactas; detalle caído: noticia guardada sin fecha y completada después. |
| RF-08-03 | Salud de 160 días y otras más nuevas / salud de 181 días | Destaca la de salud / destaca la más reciente. |
| RF-08-04, 08-05 | Imagen `http`, de otro sitio o `javascript:` | No se guarda; el inicio no llama a Internet. |
| RF-08-06 | Superusuario | Ve Usuarios, Mi perfil, Padrón y recetas y Sesión activa; no ve «Cuentas, grupos y registro de auditoría» ni el panel de administración. |

## No funcionales
WCAG 2.1 AA: contraste con la paleta existente, objetivos táctiles de 44 px o más, foco visible, texto escalable con el control de tamaño. Sin animaciones. El inicio no hace solicitudes externas del servidor (RNF-05). Privacidad: ver «Supuestos».

## Compatibilidad
Preserva el menú de 02 y los contratos de roles. No modifica turnos, recetas ni sala.

## Supuestos y decisiones pendientes
- **Fotos de terceros:** se enlazan, no se copian, y se muestran con crédito a la Municipalidad. Aún no hay autorización formal para usarlas; conviene pedirla al DESAMU o a la Municipalidad antes de la demostración. La foto de una noticia de vacunación antigua mostraba a un paciente real: no se adoptó como foto fija y hoy la destacada es otra noticia de salud.
- **Lectura del sitio municipal:** no ofrece API; el lector depende de su HTML y falla de forma segura. Respeta una pausa de 0,5 s entre páginas.
- **Actualización:** manual o con el Programador de tareas; no se agrega un proceso permanente.

## Revisión y cambios
2026-11-04: definición e implementación a pedido de la usuaria, tras revisar cuatro diseños en un lienzo. No se marca aceptado.
