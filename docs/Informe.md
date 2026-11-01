<!-- Fuente: Informe_Proyecto_De_Titulo_1_Daza_Rojas_Rubio.docx — convertido a Markdown. Las figuras (imágenes) se omitieron; se conservan sus leyendas. -->

# I. Introducción

El presente informe expone la formulación del Proyecto de Título orientado a la Unidad de Farmacia del Centro de Salud Familiar (CESFAM) de San Nicolás, establecimiento de atención primaria administrado por el Departamento de Salud Municipal (DESAMU), que en 2025 registró 15.526 usuarios inscritos, con un 57,9 % de ruralidad y un 17,1 % de adultos mayores (DESAMU, 2025). La farmacia atiende cerca de 600 pacientes diarios con seis funcionarios y organiza los turnos mediante dos rollos de papel numerados, lo que genera confusión, aglomeraciones y malos tratos hacia el personal. A esto se suma la entrega de medicamentos a domicilio para pacientes postrados y mayores de 80 años, que depende del conocimiento de los conductores frente a direcciones rurales ambiguas.

Para responder a esta situación, se propone una Plataforma Web Progresiva (PWA) que permite emitir turnos con el RUT en un tótem de autoservicio, asignarlos mediante un algoritmo de encolamiento con prioridades ponderadas y sincronizar en tiempo real el llamado con la pantalla de la sala de espera, con alertas visuales y sonoras accesibles. Además, incorpora un módulo de georreferenciación y trazabilidad de entregas domiciliarias capaz de operar sin conexión, junto con el control de recetas crónicas y un panel de indicadores para la Jefatura de Farmacia.

El documento presenta la identificación y justificación del problema, el levantamiento de requerimientos, el marco teórico, la formulación de la solución con sus objetivos, indicadores y niveles de servicio, la metodología de trabajo bajo Scrum, el plan de recursos y las arquitecturas TI y empresarial que sustentan la propuesta.

**Declaración de transparencia:** En la elaboración de este informe se utilizó inteligencia artificial generativa como apoyo, específicamente los modelos Claude (Anthropic) y Gemini 3.1 Pro (Google). Su uso abarcó la asesoría metodológica y la revisión de redacción académica, la mejora de la justificación del problema, la propuesta de mejoras a las historias de usuario, la generación de la tabla de arquitectura técnica y de la tabla comparativa entre el estado actual y el propuesto, y la elaboración de una base para la Matriz RACI. Todo el contenido generado fue revisado y contrastado con las fuentes y entrevistas levantadas, y validado por el equipo, que asume la responsabilidad del informe. Cada interacción se encuentra documentada en el Registro de asistencia de IA del Anexo (XI), y las tablas elaboradas con este apoyo se identifican con la leyenda “Elaboración propia con asistencia de…”.

# II. Identificación del Problema

## 2.1 Actualización y justificación del problema

### 2.1.1 Descripción de la organización.

#### 2.1.1.1 Antecedentes de la Organización.

**Tipo y rubro de la empresa:** El Centro de Salud Familiar de San Nicolás es una institución pública sin fines de lucro enfocada en la atención primaria de salud. Su administración está a cargo de la ilustre Municipalidad de San Nicolas mediante el Departamento de Salud Municipal (DESAMU), y se regula por la Ley N° 19.378 sobre el Estatuto de Atención Primaria de Salud Municipal. Este modelo administrativo determina un financiamiento mixto compuesto por aportes estatales per cápita y recursos municipales. Además, su planificación responde al “Plan de Salud Municipal” aprobado por el consejo municipal, sumado que su operatividad se enmarca en el Modelo de Atención Integral de Salud Familiar y Comunitaria (MAIS) impulsado por el Ministerio de Salud. La red de salud comunal está integrada por el CESFAM como base, la Posta Puente Ñuble para el sector rural y el Servicio de Urgencia.

**Posicionamiento de mercado:** El centro opera como un prestador público de atención primaria con un territorio asignado, su posición corresponde a la de un proveedor único para la población beneficiaria de FONASA en la comuna, por lo que su posicionamiento se evalúa en función de su cobertura y capacidad resolutiva. Durante el año 2025, la organización registró 15.526 usuarios inscritos, evidenciando un crecimiento sostenido del 38% respecto al 2020. Esta cifra supera la población censada en la comuna debido a que se atiende a sectores pertenecientes a la comuna de San Carlos, lo que genera una alta presión sobre la capacidad instalada.

A nivel de red asistencial, el centro pertenece a la micro red de San Carlos, derivando a requerimientos de mayor complejidad al Hospital Dr. Benicio Arzola y al Hospital Herminda Martín de Chillán. El perfil demográfico de los usuarios impacta directamente en el diseño de soluciones tecnológicas, destacando un 57,9% de ruralidad, 17,1% de adultos mayores y 19,7% de población en situación vulnerable multidimensional.

**Organigrama:**

**Figura 1.** Organigrama del Departamento de Salud Municipal (DESAMU)

**Figura 2.** Organigrama CESFAM (DESAMU, 2025)

La estructura organizacional del sistema de salud comunal se articula en dos niveles jerárquicos documentados en el Plan de Salud Municipal:

**Nivel de dirección comunal:** La Alcaldía encabeza la estructura, de la cual depende el Departamento de Salud Municipal (DISAMU). De este último se desprenden cuatro unidades: la Dirección CESFAM, Recursos Humanos, la Dirección de Administración y Finanzas, y Prevención de Riesgos. A su vez, Recursos Humanos cuenta con un Técnico de RRHH; Prevención de Riesgos se vincula al Comité de Vida Laboral; y la Dirección de Administración y Finanzas agrupa las funciones de Encargado de Inventario, Técnico en Contabilidad, y Adquisiciones y Transparencia.

**Nivel de establecimiento**: La Dirección CESFAM articula un conjunto de unidades de apoyo y asesoría, entre las que se cuentan el Equipo Gestor, la Secretaría, la Administración Interna, la unidad de TIC, la Unidad de Farmacia, la Unidad GES, Telesalud, Calidad y OIRS, además de instancias de participación como el Consejo de Desarrollo, el Comité de Gestión Usuaria, el COMSE y el Comité Paritario. La línea operativa se organiza en tres ejes: la Unidad SOME (que incluye Admisión y Recaudación, Estadística, Lista de Espera, SOMES satelitales, Resolutividad y Call Center), la Coordinación General de Sector (con las jefaturas de los sectores Verde, Azul y Rojo) y la Enfermera Coordinadora (a cargo de Postrados, Toma de Muestras, Epidemiología, TBC, Esterilización, Vacunatorio, Procedimientos e Insumos). De forma transversal se disponen las Asesorías Técnicas de Programas y los Programas Transversales y Convenios.

**Sectorización territorial**: Conforme al modelo MAIS, el territorio se divide en tres sectores según criterio geográfico. El sector Verde comprende el área desde la Ruta N-50 hacia el límite norte de la comuna; el sector Azul incorpora la población desde la Ruta N-50 hacia el sur; y el sector Rojo corresponde al radio territorial de la Posta Puente Ñuble (DESAMU, 2025).

La misión y visión declaradas por el Departamento de Salud Municipal para el período 2026–2028 son las siguientes:

**Misión:** "Brindar a la comunidad una atención integral desde un enfoque biopsicosocial, que nos permite, la coordinación con el intersector, otorgando una atención inclusiva, humana eficiente, accesible y de calidad, asegurando la continuidad del cuidado en todo el ciclo vital" (DESAMU, 2025, p. 6).

**Visión:** "Ser un centro de salud familiar reconocido por los usuarios, por brindar una atención integral, inclusiva y de calidad contribuyendo a mejorar la calidad de vida de la comunidad por medio de la prevención y promoción en salud, haciendo de los usuarios actores principales de su salud y de sus familiares" (DESAMU, 2025, p. 6).

**Cadena de valor**

- Actividades primarias: Comprender la inscripción de usuarios, agendamiento de horas, atención clínica, apoyo diagnóstico, la dispensación farmacéutica y el seguimiento médico.

- Actividades de soporte: Infraestructura tecnológica (redes, servidores), abastecimiento, gestión de talento humano, aseguramiento de calidad, participación ciudadana y prevención de riesgos.

**Cuadro de Mando Integral:**

El Plan de Salud Municipal no formula un cuadro de mando integral (CMI) como instrumento formal, sin embargo, se prioriza al ámbito público en base a la perspectiva del usuario y el impacto sanitario por sobre los resultados financieros. Se evalúan objetivos estratégicos relacionados con la atención digna, la capacidad resolutiva, acreditación de calidad y eficiencia de los recursos. Se propone enriquecer la perspectiva de procesos internos mediante la incorporación de un indicador que mida la eficiencia en la dispensación (como tiempos de espera y el uso de tecnologías relacionadas al autoservicio), información que actualmente no se registra de manera automatizada.

**Estándares adoptados y certificaciones adquiridas**

Marco normativo obligatorio: La organización opera bajo la ley N° 19.378 sobre el Estatuto de Atención Primaria de Salud Municipal, y por la ley N° 18.695, que establece la participación del Concejo Municipal en la aprobación del programa de salud comunal. En calidad, debe avanzar en la acreditación del CESFAM y la Posta Puente Ñuble, cumpliendo los protocolos, indicadores, auditorías y capacitación. Su eficacia se mide en las Metas Sanitarias y el IAAPS. Además, aplica al modelo MAIS, basado en la atención familiar, comunitaria y territorial, y el proyecto incorpora las WCAG garantizando interfaces accesibles y intuitivas.

**Arquitectura tecnológica y de aplicaciones**

El Plan de Salud Municipal documenta el equipamiento tecnológico del establecimiento:

**Equipamiento clínico-diagnostico:** ecógrafo, electrocardiógrafos y equipos de rehabilitación.

**Telemedicina:** En esto destaca el sistema Heart View que permite enviar electrocardiogramas a especialistas externos.

**Comunicaciones:** Radio comunicadores, agendamiento telefónico, y telesalud para mejorar la atención.

**Sistema Locker Inteligente:** Dispensación automática de medicamentos actualmente usada en el CESFAM por licitación donde se debe inscribir el paciente para obtener sus medicamentos desde un “casillero” y se envía una notificación SMS de la dispensación completada por farmacia.

**Unidades de negocio afectadas**

El proyecto interviene de forma directa sobre una unidad e impacta de manera indirecta a otras seis, todas identificables en el organigrama del establecimiento.

| Unidad de Farmacia                             | Directa     | Es la unidad donde se localiza la problemática. El sistema modifica el mecanismo de asignación y llamado de turnos, la operación de las ventanillas y el registro de la dispensación. Además de mejorar la trazabilidad de rutas para los repartidores de medicamentos a domicilio. Sus funcionarios son usuarios finales del sistema. |
|------------------------------------------------|-------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SOME y Admisión                                | Indirecta   | Interviene en la validación de identidad del usuario y comparte con farmacia el flujo de circulación de pacientes en el establecimiento.                                                                                                                                                                                               |
| Unidad de TIC                                  | Indirecta   | Responsable del soporte, la infraestructura de red y la eventual integración con sistemas preexistentes. Contraparte técnica del proyecto.                                                                                                                                                                                             |
| OIRS                                           | Indirecta   | Recibe y registra los reclamos asociados al proceso de dispensación. Constituye fuente de verificación del impacto de la solución.                                                                                                                                                                                                     |
| Estadística                                    | Indirecta   | Consolida los registros estadísticos mensuales (REM). El sistema puede aportar datos de gestión hoy inexistentes.                                                                                                                                                                                                                      |
| Sectores clínicos Verde, Azul y Rojo           | Indirecta   | Origen de la prescripción que desencadena el flujo hacia farmacia. Relevante si se implementa la generación automática del turno al término de la atención.                                                                                                                                                                            |
| Prevención de Riesgos y Comité de Vida Laboral | Indirecta   | Competentes en la gestión del riesgo psicosocial del personal expuesto a situaciones de conflicto con usuarios.                                                                                                                                                                                                                        |
| Dirección CESFAM                               | Transversal | Autoriza la implementación, asigna recursos y evalúa resultados.                                                                                                                                                                                                                                                                       |

#### 2.1.1.2 Diagnóstico de la situación actual.

La gestión de entrega de los medicamentos en farmacia en el Cesfam ha presentado diversas situaciones, desde los reclamos y los malos tratos al personal del Cesfam. Esto debido al choque entre los pacientes teniendo un rollo de papel con números, si bien por parte del director se decidió añadir un segundo rollo numérico para diferenciar la atención general de la preferencial, esto ha generado más problemas a la situación actual en farmacia. Desde los pacientes que confunden los números de atención o que los adultos mayores se conglomeran en ventanilla esperando su turno, generando así que los técnicos en farmacia no puedan ver el número actual de paciente al que están llamando ya que solo se puede comprobar visualmente en las salas de espera, pero no desde el interior de la farmacia.

**Dotación de los recursos humanos**, durante las extensiones horarias que son hasta las 8 pm, generando que solo queden números generales y el uso de 1 sola ventanilla para la atención. Agregando que a diario se maneja un volumen de 600 pacientes y un tiempo de espera aproximado de 15 minutos, esto reafirma la dificultad del personal para la atención de los mismos pacientes al solo tener 4 ventanillas y un grupo limitado de personal.

Respecto a las **entregas de medicamentos a domicilio** por parte del Cesfam, existen dificultades reportadas por los mismos trabajadores y director del Cesfam. Actualmente en las entregas de medicamentos a domicilio, los choferes se enfrentan a un volumen de 70 pacientes postrados y a un aproximado de 600 pacientes mayores a 80 años, en base a esto los choferes han presentado diversos problemas, como lo son las direcciones “vagas” que no indican con certeza la dirección del paciente, como puede ser “Dadinco, km 2 casa roja”, por lo cual muchas veces tienen que estar preguntando por los alrededores donde vive el paciente.

**A continuación, se presenta imágenes de la estructura de trabajo actual de la farmacia del CESFAM:**

**Figura 3.** Pantallas de turno y dispensadores de números de atención preferente y público general en la farmacia del CESFAM

**Figura 4.** Ventanillas de atención y dispensador automático de medicamentos de la farmacia del CESFAM

### 2.1.2 Descripción del problema.

La problemática critica del Cesfam se presenta en cómo se organizan los pacientes a la hora de la entrega de fármacos en la propia farmacia, generando discusiones y malos tratos. Esto por la forma en que se gestiona a los pacientes mediante los números otorgados por un rollo de papel numéricos y la alta aglomeración de pacientes mayores, dificultando la visión de los médicos farmacéuticos el número actual de pacientes, el cual está indicado en posiciones que dificulta la identificación del número el cual están llamando o han llamado.

En conjunto a esto, existe la limitación de los recursos humanos que afecta directamente a los tiempos de espera y carga del personal ante los malos tratos y discusiones generadas por la propia gestión de pacientes en el sector de farmacia.

Otro añadido a la visión actual de la problemática, está el problema de la entrega de los medicamentos fuera del propio Cesfam, los cuales se entregan a domicilio, revisando la situación se observa el que los choferes presentan dificultades para encontrar algunos de los domicilios cuentan con direcciones muy poco específicas direcciones añadiendo al hecho de ser un sector rural, junto al tener que preguntar a gente para confirmar las direcciones de alrededores para poder encontrar los domicilios de sus pacientes.

## 2.2 Justificación del problema.

### 2.2.1 Relevancia del problema.

La relevancia de la problemática se ve reflejada bajo tres factores principales, siendo la alineación estratégica del establecimiento, la magnitud cuantificada de operación y el impacto hacia el personal de farmacia:

##### Posicionamiento estratégico

Se declara propiamente del CESFAM la visión y el compromiso a ser reconocido por una atención inclusiva, humana, eficiente, accesible y de calidad. Bajo el diagnostico operativo se evidencia una contradicción directa entre la declaración anterior con la experiencia real de la operación actual de farmacia: las aglomeraciones físicas en ventanilla, la perdida de diferenciación preferencial y la incertidumbre respecto al sistema de numeración en papel; constituyen una vulneración concreta y medible del posicionamiento estratégico. Con esto presente, resolver la problemática establecida se vuelve una condición necesaria para la coherencia entre la operación diaria y la misión declarada por la institución.

##### Magnitud cuantitativa del impacto

Existen indicadores claves que permiten dimensionar objetivamente la escala del problema:

1.  En el diagnostico participativo del Plan de Salud Municipal, el trato de funcionarios y usuarios obtuvo 84 puntos en la priorización mediante el método Hanlon, una magnitud estimada de 60% de insatisfacción.

2.  La falta de información sobre el funcionamiento de los centros de salud alcanzo 104 puntos, con un 70% de la población estimada como no informada.

3.  La población inscrita y validada por FONASA son 15.526 pacientes, implicando un gran número de usuarios potencialmente afectados por el proceso de dispensación.

4.  El flujo diario por farmacia es de 600 pacientes, convirtiendo en el punto de mayor concurrencia.

5.  Una dimensión normativa se puede observar en la Ley N° 21.168 que incorporo a la Ley N° 20.584 en el derecho de las personas mayores de 60 años y personas con discapacidad a ser atendidas de manera preferente. En la comuna de San Nicolás, el 17,1% de la población supera los 65 años y el 16,7% presenta discapacidad.

6.  El tiempo de espera promedio no supera los 15 minutos, si bien es un tiempo cronológico razonable, es opacado por la alta variabilidad percibida consecuente a la falta de información en línea.

7.  El mecanismo de turnos son 2 rollos de papel numerados para atención general y preferencial, con la ausencia de un algoritmo que defina ambos flujos; se reportan colisiones de números.

8.  El CESFAM enfrenta una alta carga logística con respecto a la entrega de medicamentos a domicilio, esta beneficia a un aproximado de 70 pacientes postrados y 600 adultos mayores de 80 años. El acceso hacia el resto de la localidad es limitado a falta de un sistema de transporte público establecido, sumado a esto, el 57,9% de la población es rural; es dependiente en su totalidad del factor humano y del conocimiento territorial de los conductores que son guiados con direcciones ambiguas en la mayoría de los casos.

Los antecedentes anteriormente descritos dejan evidencia de que la problemática no corresponde únicamente a una dificultad de operación, sino que afecta la eficiencia del proceso de dispensación, la experiencia de usuarios y las condiciones de trabajo del personal. Es por esto por lo que resulta de manera pertinente una solución informática que permita gestionar turnos y una dispensación más rápida y apta para los pacientes postrados y mayores de 80 años.

##### Riesgo en la continuidad actual del servicio

La deficiencia del mecanismo actual de gestión de turnos deriva en reclamos informales y momentos de malos tratos hacia el personal de farmacia. Este fenómeno constituye un riesgo psicosocial laboral documentado, con potencial de traducirse en licencias médicas y mayor rotación del personal, lo que retroalimenta negativamente la evidente limitante de recursos humanos ya existente en el recinto. En consecuencia, la relevancia del problema trasciende la experiencia del paciente e impacta directamente la sostenibilidad del servicio de farmacia.

### 2.2.2 Complejidad del problema.

La complejidad del problema se fundamenta desde el lado de ingeniería de software, evidenciado porque su resolución excede medidas administrativas simples, y requiere el diseño de una solución sistemática compuesta por múltiples componentes:

##### Modelo de encolamiento simple

Un esquema de tipo FIFO resulta inadecuado, debido a que el sistema debe sostener dos flujos de forma simultánea (atención general y preferencial) que se intercalan bajo la proporción de pacientes que son atendidos y que esta proporción se ajuste dinámicamente según el número de ventanillas, junto con el reajuste durante la extensión horaria. Esta condición introduce un problema de diseño algorítmico de encolamiento con prioridades ponderadas, no resuelto por la sola adición de un segundo rollo físico.

##### Concurrencia y sincronización en tiempo real

La solución debe sincronizar, sin latencia perceptible y sin condiciones de carrera, al menos tres componentes: la base de datos de turnos, la interfaz del funcionamiento de farmacia y la pantalla pública de la sala de espera. Evitar llamados repetidos o desincronizados exige una arquitectura con actualización en tiempo real, aspecto que constituye un desafío de complejidad media-alta para el proyecto.

##### Restricciones de accesibilidad para usuarios vulnerables

El perfil sociodemográfico del CESFAM (población mayoritariamente rural y de adultos mayores) impone restricciones de diseño de interfaz que no admiten soluciones genéricas: se requieren alertas sonoras, alto contraste, tipografía de tamaño ampliado y mensaje sin ambigüedad. Esta capa de accesibilidad debe validarse como requisito funcional del sistema y no como una característica opcional, lo que añade complejidad al proceso de diseño de interfaz (UI/UX).

##### Compatibilidad con Sistemas de Salud

Para eliminar el punto de fricción entre la atención médica y la entrega de fármacos, la solución debe trabajarse como un sistema independiente del sistema clínico institucional Rayén, ya que esta cuenta con requisitos estrictos de conexión y operación que no se puede modificar. El nuevo sistema es autónomo enfocado en la gestión de turnos de farmacia y trazabilidad de ruta para la entrega de medicamentos a postrados, lo que permitirá una adaptación especificas a los requerimientos del CESFAM de San Nicolás.

##### Trazabilidad de ruta

Parte de las direcciones y guía de los propios funcionarios no les permite la entrega optima de los medicamentos para los pacientes, se requiere una solución que permita procesar y realizar referencias geológicas de direcciones rurales no estandarizadas, junto con descripciones informales para identificar puntos georreferenciados en un mapa. Desde el punto de vista de desarrollo, se implica la integración de un mapeo que recopile y almacene coordinadas, sumado a material fotográfico del entorno para facilitar la ubicación de los domicilios.

# III. Levantamiento de Requerimientos.

## 3.1 Determinación de los instrumentos a utilizar.

Para la toma de requerimientos, se ejecutó un levantamiento real bajo la recopilación de entrevistas a cinco actores clave de la organización y en la extracción de métricas de salud pública desde el Plan de Salud Municipal (DESAMU). El análisis de los datos duros recopilados fundamenta el diagnóstico de la problemática y da origen a las Historias de Usuarios.

Para la toma de requerimientos se ha utilizado los siguientes instrumentos:

- **Entrevista estructurada:** Se realiza entrevista estructurada con guion cerrado en el contexto organizacional a Director del CESFAM (Juan Carlos Durán) y Director de Salud Municipal (Francisco Conejeros).

  - Reveló que los puntos de atención mantienen un estimado de 16.000 pacientes inscritos.

  - Se identificó que la unidad de farmacia gestiona un volumen diario de 600 atenciones.

  - Se determinó un tiempo de espera actual estimado de 15 minutos.

  - Se confirmó la existencia de reclamos informales dirigidos a la dirección, derivados exclusivamente de la confusión en los turnos.

- **Entrevista semiestructurada:** A la jefa de farmacia (Alejandra Celedón), centrada en el proceso operativo de la farmacia. Es la fuente de información más rica, aporto la descripción del proceso, origen y visión de solución esperada.

  - Permitió constatar una dotación limitada de recursos humanos contabilizando solo a 6 personas para las labores de farmacia.

  - Evidencio que la falta de personal impide cubrir las 4 ventanillas disponibles, agravándose durante la extensión horaria, donde se opera una sola ventanilla y un solo número general.

  - Confirmó que la implementación de dos rollos de papel numéricos (general y preferencial) provoca confusión en una población mayoritariamente rural y adulta mayor, generando aglomeraciones y malos tratos hacia los funcionarios.

- **Entrevistas abiertas:** Técnico en Enfermería (Paola) y Conductor (Joaquin), sobre atención a domicilio de postrados y mayores 80 años para la entrega de sus medicamentos.

  - Cuantificó la carga logística del servicio, el cual debe cubrir alrededor de 70 pacientes postrados y a unos 600 pacientes mayores de 80 años.

  - Identificó que las entregas domiciliarias son guiadas por direcciones rurales no normalizadas y altamente ambiguas.

  - Demostró que el personal depende del conocimiento empírico del entorno y de preguntar a los vecinos para ubicar los domicilios, sustentando la urgencia de integrar mapas y registros fotográficos.

- **Observación**: Se observa los procesos actuales de gestión de medicamentos para analizar el cuello de botella del sistema tradicional y las interacciones entre personal de farmacia y pacientes.

- **Revisión documental:** Plan de Salud Municipal y registros demográficos del establecimiento.

  - Validó que la organización atiende a una población de 15.526 usuarios validados por FONASA al año 2025.

  - Registró una tasa de crecimiento sostenido del 38% de los usuarios respecto al año 2020.

  - Aportó datos demográficos críticos que impacta en el diseño de la interfaz y la logística, destacando un 17,1% de población adulta mayor y un 16,7% de personas con discapacidad.

  - Demostró que el 57,9% de la población de la comuna reside en áreas rurales.

## 3.2 Detalle de los requerimientos.

Se sugiere incluir como anexo el listado de los requerimientos.

Las historias de usuario a continuación presentan su requerimiento asignado junto con la priorización MoSCoW, donde se clasifica cada tarea según su importancia:

- Must (Imprescindibles): Requisitos obligatorios y no negociables para que el proyecto sea viable.

- Should (Debería tener): Características importantes de alto valor, pero necesariamente críticas para su entrega.

- Could (Podrían tener): Elementos deseable y/o complementarios, pero cuya ausencia no afecta necesariamente el funcionamiento principal.

- Won’t (No tendrá): Requisitos descartados para el período actual; no son prioridad, pero pueden considerarse en un futuro.

| **ID**    | **Módulo / Épica**                          | **Nombre Historia**                                    | **Como**                                                                     | **Quiero**                                                                                                                   | **Para**                                                                                                             | **Prioridad** | **Criterios de Aceptación**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
|-----------|---------------------------------------------|--------------------------------------------------------|------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **HU-01** | Autenticación                               | **Inicio de sesión**                                   | Jefa de Farmacia / Técnico en Farmacia /Encargado de entrega en terreno      | Poder ingresar mis credenciales en un formulario                                                                             | Iniciar sesión en mi perfil                                                                                          | **Must**      | • El sistema muestra formulario con Usuario y Contraseña.<br>• Los campos son obligatorios.<br>• Con credenciales válidas, el sistema inicia la sesión.<br>• Con credenciales erróneas, se muestra un mensaje de error.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **HU-02** | Autenticación                               | **Restablecer contraseña**                             | Jefa de Farmacia / Técnico en Farmacia / Encargado de entrega en terreno     | Recuperar mi contraseña                                                                                                      | Ingresar nuevamente en mi perfil en caso de haberla olvidado                                                         | **Should**    | • Desde el inicio de sesión existe la opción "¿Olvidaste tu contraseña?".<br>• Al solicitar el restablecimiento se ingresa un dato de contacto para la solicitud.<br>• El sistema envía un enlace o código de restablecimiento al medio registrado.<br>• El usuario ingresa y confirma la nueva contraseña.<br>• Una vez restablecida, la contraseña anterior queda inválida.                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| **HU-03** | Autenticación                               | **Editar perfil**                                      | Jefa de Farmacia / Técnico en Farmacia                                       | Editar mi perfil                                                                                                             | Editar mis datos personales de ser necesario                                                                         | **Could**     | • Solo con sesión iniciada el usuario puede editar su perfil.<br>• La pantalla muestra los datos registrados; los campos obligatorios no pueden quedar vacíos.<br>• Los datos ingresados deben estar validados.<br>• Al guardar los cambios se muestra una confirmación.<br>• Los cambios permanecen visibles al actualizar.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **HU-04** | Gestión de Turnos y Filas                   | **Llamar al siguiente paciente**                       | Técnico en Farmacia                                                          | Presionar un botón para llamar al siguiente paciente en la fila                                                              | Que el sistema asigne automáticamente el siguiente turno, respetando la preferencia/prioridad                        | **Must**      | • Cada paciente en cola tiene un botón de llamar, ordenado por lista.<br>• Al llamar, se muestra en la pantalla de sala de espera y en la del técnico.<br>• Al realizar el llamado se escucha una voz en parlante.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **HU-05** | Gestión de Turnos y Filas                   | **Re-llamar a un paciente**                            | Técnico en Farmacia                                                          | Tener una opción para emitir nuevamente el llamado sonoro del turno actual                                                   | Alertar al paciente nuevamente que ya es su turno                                                                    | **Must**      | • En los pacientes ya llamados, el botón cambia a "Re-llamar".<br>• Al usar Re-llamar se vuelve a escuchar la voz.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **HU-06** | Gestión de Turnos y Filas                   | **Saltar turno**                                       | Técnico en Farmacia                                                          | Poder marcar un turno como ausente después de 1 minuto de espera                                                             | Continuar la fila en orden si un paciente no se presenta en ventanilla                                               | **Must**      | • Cada paciente tiene un botón de saltar/omitir.<br>• Al usarlo, el paciente registrado en la espera queda omitido.<br>**•** Si el turno marcado como ausente corresponde a una receta ya preparada, el sistema mueve el registro a un listado de "medicamentos preparados pendientes de retiro" (HU-17), en lugar de descartarlo.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **HU-07** | Gestión de Turnos y Filas                   | **Emisión de turno mediante RUT**                      | Paciente                                                                     | Digitar mi RUT en una pantalla a la entrada de la farmacia                                                                   | Registrar mi llegada e ingresar a la fila de entrega de medicamentos                                                 | **Must**      | • La pantalla muestra un campo de ingreso de RUT con teclado numérico y señalizaciones.<br>• Al ingresar el RUT, el paciente es validado y se le entrega un número.<br>• Con un RUT inválido, se notifica en pantalla y se solicita un RUT válido.<br>**•** El sistema identifica el motivo de atención y asigna la ventanilla correspondiente (general, preferencial/crónicos o urgencia); si el paciente está registrado como postrado o mayor de 80 años, no se ofrece número presencial y se muestra el estado de su despacho a domicilio.<br>• Si la receta ya alcanzó el máximo de entregas autorizadas, el sistema bloquea la emisión de turno para esa receta y notifica que requiere renovación médica (ver HU-21).                                                                                                |
| **HU-08** | Gestión de Turnos y Filas                   | **Visualización clara de turnos**                      | Paciente                                                                     | Ver el número llamado y la ventanilla correspondiente                                                                        | Saber exactamente cuándo y a dónde acercarme, sin confundirme con otros números                                      | **Must**      | • Al ser llamados, los números van apareciendo junto a su respectiva ventanilla.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **HU-09** | Gestión de Turnos y Filas                   | **Alerta sonora**                                      | Paciente                                                                     | Escuchar una alerta sonora y una voz que indique mi número y ventanilla                                                      | No depender exclusivamente de estar mirando la pantalla de la sala de espera                                         | **Must**      | • Al ser llamado o re-llamado un número, se escucha una voz en altavoz con el número/nombre del paciente.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **HU-10** | Gestión de Turnos y Filas                   | **Configuración de ventanillas activas y turnos**      | Jefa de Farmacia                                                             | Habilitar o deshabilitar el número de ventanillas operativas y realizar el término de turno                                  | Que el algoritmo recalcule el flujo de llamados y los pacientes no sean derivados a ventanillas cerradas             | **Should**    | • La vista de la jefa de farmacia muestra las ventanillas disponibles, cada una con botón de (des)habilitar.<br>• Las ventanillas deshabilitadas se mueven al final de la lista y no reciben turnos hasta ser habilitadas.<br>• Existe opción para añadir o eliminar ventanillas.<br>• Si la ventanilla tiene una atención en curso, deshabilitarla exige confirmación.<br>• Cada ventanilla tiene botón de "Término de turno", que registra la hora de término y la deshabilita.<br>• Al configurar una ventanilla, la jefa de farmacia puede asignarle uno o más tipos de atención (general, preferencial, urgencia, crónicos); el sistema solo deriva turnos compatibles.                                                                                                                                                |
| **HU-11** | Panel de Mermas e Indicadores               | **Monitoreo de tiempos de espera**                     | Jefa de Farmacia                                                             | Visualizar el tiempo de espera de los pacientes en tiempo real y un tiempo promedio                                          | Tomar decisiones operativas si se superan los 15 minutos de espera establecidos                                      | **Should**    | • En la vista de cola de espera se ven los minutos de espera de cada paciente.<br>• Al acercarse a los 15 minutos, el sistema alerta y muestra ese paciente como prioridad.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **HU-12** | Logística de Entregas                       | **Dirección y referencias de ubicación de domicilios** | Encargado de entrega en terreno                                              | Registrar y actualizar la dirección y las referencias de ubicación                                                           | Facilitar la ubicación de los domicilios de pacientes mayores y postrados                                            | **Should**    | • El registro incluye sector, dirección y referencias.<br>• Se distinguen direcciones pendientes de verificar de las ya verificadas.<br>• Se conserva quién realiza la actualización y cuándo.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **HU-13** | Logística de Entregas                       | **Asignación de entregas**                             | Jefa de Farmacia                                                             | Programar y asignar las entregas a domicilio                                                                                 | Llevar un registro de las entregas a domicilio                                                                       | **Should**    | • Cada entrega registra paciente, fecha y encagado.<br>• El sistema impide duplicar una misma entrega programada.<br>• La asignación aparece en la lista del Encargado de entrega a terreno.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **HU-14** | Logística de Entregas                       | **Consulta de entregas domiciliarias**                 | Encargado de entrega en terreno                                              | Consultar las entregas asignadas y referencias de ubicación                                                                  | Llegar a los domicilios correctos y optimizar mi ruta en base a las referencias                                      | **Should**    | • Se puede ver un mapa y un registro de las entregas del día.<br>• El mapa muestra íconos de los domicilios.<br>• Cada entrega permite consultar su ubicación y estado.<br>• El sistema sugiere un orden de visita según la ubicación geográfica registrada, priorizando reducir el tiempo total de ruta (sugerencia de recorrido, sin seguimiento GPS en tiempo real).<br>• El Encargado de entrega a terreno accede desde la misma aplicación web responsiva (PWA) usada por el resto del equipo, sin necesidad de instalar una app nativa.                                                                                                                                                                                                                                                                               |
| **HU-15** | Logística de Entregas                       | **Registro de entregas**                               | Encargado de entrega en terreno                                              | Registrar las entregas realizadas o no realizadas                                                                            | Mantener registro del trabajo y dejar declarado si se logró la entrega o no, y por qué                               | **Should**    | • El sistema permite confirmar una entrega asignada, registrando fecha, hora y responsable.<br>• El Encargado de entrega a terreno puede actualizar el estado a "entregada".<br>• El Encargado de entrega a terreno puede actualizar el estado a "no entregada" indicando el motivo; la entrega queda pendiente de gestión.<br>• El registro funciona con conexión intermitente: los cambios se guardan localmente y se sincronizan al recuperar señal.                                                                                                                                                                                                                                                                                                                                                                     |
| **HU-16** | Logística de Entregas                       | **Programación de entregas pendientes**                | Jefa de Farmacia                                                             | Programar las entregas que hayan quedado pendientes                                                                          | Organizar un nuevo intento de entrega                                                                                | **Should**    | • El sistema permite filtrar las entregas no realizadas, mostrando el motivo.<br>• Existe opción "Reasignar" para organizar nueva fecha y Encargado de entrega a terreno, conservando el historial del intento anterior.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **HU-17** | Trazabilidad y Recuperación de Medicamentos | **Gestión de medicamentos preparados no retirados**    | Técnico en Farmacia                                                          | Registrar y consultar los medicamentos ya preparados, pero no retirados por exceso de tiempo de espera                       | Ubicarlos rápidamente cuando el paciente regrese, sin perder el trabajo de preparación ya realizado                  | **Must**      | • Cuando un turno se marca como ausente (HU-06) y la receta ya fue preparada, el sistema mueve el registro a un listado de "preparados pendientes de retiro".<br>• El listado permite buscar por RUT o apellido del paciente.<br>• Al encontrar el registro, el técnico puede marcar la entrega como completada, sin pasar nuevamente por la fila.<br>• El registro conserva la fecha original de preparación para fines de trazabilidad de mermas.                                                                                                                                                                                                                                                                                                                                                                         |
| **HU-18** | Gestión de Turnos y Filas                   | **Estimación de tiempo de espera por volumen de cola** | Paciente y Técnico en Farmacia                                               | Ver un tiempo estimado de espera calculado según el volumen real de recetas en cola (no solo las personas presentes en sala) | Decidir si espero en el lugar o vuelvo en otro momento, con información real                                         | **Must**      | • El sistema registra el tiempo real que toma cada preparación, desde la recepción hasta quedar lista.<br>• Con ese historial, calcula un tiempo promedio de preparación por receta, actualizado periódicamente.<br>• Al emitir el turno (HU-07), el sistema calcula la estimación en base a la cantidad de recetas pendientes y el tiempo promedio histórico, y la muestra al paciente.<br>• La estimación se actualiza a medida que avanza la cola.                                                                                                                                                                                                                                                                                                                                                                       |
| **HU-19** | Logística de Entregas                       | **Notificación de despacho en camino**                 | Paciente postrado o mayor de 80 años con entrega a domicilio (o su cuidador) | Recibir una notificación cuando el conductor inicie el recorrido hacia mi domicilio                                          | Estar disponible para recibir mis medicamentos, de forma similar al seguimiento de un pedido de comercio electrónico | **Should**    | • Al iniciar el Encargado de entrega a terreno su recorrido del día, el sistema notifica al medio de contacto registrado de cada paciente de la ruta.<br>• La notificación indica que el despacho está en camino, sin geolocalización en tiempo real del vehículo (fuera de alcance).<br>• Si la entrega no puede realizarse (HU-15), también se notifica el motivo y la próxima fecha estimada.<br>**•** La notificación se envía por SMS o notificación push web, sin depender de que el paciente tenga una app instalada.                                                                                                                                                                                                                                                                                                |
| **HU-20** | Panel de Mermas e Indicadores               | **Panel de mermas por período**                        | Director del CESFAM / Jefa de Farmacia                                       | Visualizar un panel con la cantidad de pacientes que no retiraron sus medicamentos en un rango de fechas                     | Dimensionar la merma de medicamentos y priorizar acciones (ej. delivery) sobre esos pacientes                        | **Must**      | • El panel permite filtrar por rango de fechas y tipo de paciente (crónico/general).<br>• Se muestra el total de recetas no retiradas y su detalle por paciente.<br>• El indicador se calcula a partir de los turnos marcados como ausente (HU-06) sin retiro posterior registrado en HU-17.<br>• Desde el panel se puede derivar un paciente no retirado hacia el módulo de entregas a domicilio.                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **HU-21** | Recetas y Vigencia (simulación Rayen)       | **Control de entregas parciales de receta crónica**    | Técnico en Farmacia                                                          | Que el sistema muestre y actualice automáticamente el número de entrega de una receta crónica (ej. "3 de 6")                 | Saber en qué punto del ciclo de vigencia está la receta y evitar entregas con receta vencida o sin renovación        | **Must**      | • Cada receta crónica se crea con una vigencia total en meses y un número máximo de entregas (parametrizable).<br>• Cada entrega completada (HU-07/HU-17) aumenta en 1 el contador de esa receta.<br>• Al alcanzar el máximo, el sistema impide una nueva emisión de turno hasta registrar una renovación médica.<br>• El técnico puede consultar en cualquier momento cuántas entregas restan para una receta específica.<br>• Nota de arquitectura: este módulo opera sobre una base de datos y un mecanismo de emisión de recetas simulados, propios del sistema, sin integración real ni por API con Rayen; se presenta como un control interno anexo de farmacia.                                                                                                                                                      |
| **HU-22** | Logística de Entregas                       | **Confirmación de entrega por el paciente**            | Paciente postrado o mayor de 80 años (o su cuidador)                         | Confirmar desde la aplicación que recibí mis medicamentos                                                                    | Que quede un registro verificado de la entrega, complementario al que ingresa el Encargado de entrega a terreno      | **Should**    | • Al recibir la notificación de despacho en camino (HU-19), el paciente o su cuidador abre un enlace directo a la vista de su entrega, sin crear cuenta ni recordar contraseña.<br>• La vista muestra un único botón de "Confirmar recepción", simple de usar para personas mayores o con poca familiaridad tecnológica.<br>• Al confirmar, se registra fecha y hora, vinculando la confirmación al registro del Encargado de entrega a terreno (HU-15) como verificación cruzada.<br>• Si el paciente no confirma dentro de un plazo definido, el registro del Encargado de entrega a terreno sigue siendo la fuente válida; la falta de confirmación no bloquea el flujo.<br>• Las entregas con confirmación cruzada (Encargado de entrega a terreno + paciente) se distinguen visualmente en el panel de mermas (HU-20). |
| **HU-23** | Recetas y Vigencia (importación Rayén)      | Importación del padrón y recetas vigentes              | Como jefa de farmacia                                                        | *quiero* cargar periódicamente un archivo CSV/Excel con el padrón de crónicos/postrados y sus recetas vigentes               | *para* no digitar manualmente cada receta en dos sistemas.                                                           | **Must**      | • validar RUT (dígito verificador) y formato de columnas;<br>• detectar duplicados y actualizar registros existentes;<br>• entregar un reporte de filas rechazadas con el motivo;<br>• guardar una bitácora de quién cargó qué y cuándo.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

> Elaboración propia con asistencia de Claude Sonnet 5 Medio (Anthropic, 2026)

## 3.3 Requerimientos no funcionales

Complementando las historias de usuario, se definen los requerimientos no funcionales que establecen los atributos de calidad que la plataforma debe cumplir. Cada requerimiento incluye un criterio de aceptación verificable, su prioridad según MoSCoW y su relación con los niveles de servicio (sección 5.2.4) y las historias de usuario.

| **ID** | **Categoría**               | **Requerimiento**                                                                                                                                                                                                                                                                                                                                                                                           | **Criterio de aceptación**                                                                                                                                                     | **Prioridad** | **Relación**       |
|--------|-----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|--------------------|
| RNF-01 | Seguridad y privacidad      | Acceso autenticado con control por roles (Jefa de Farmacia, Técnico en Farmacia, Encargado de entrega, tótem de pacientes); comunicación cifrada mediante HTTPS; contraseñas almacenadas con hash; registro de auditoría de quién crea o modifica turnos, entregas y recetas. El tratamiento de datos se ajusta a las Leyes N° 19.628, 20.584 y 21.719, y el prototipo usa exclusivamente datos sintéticos. | Ningún rol accede a funciones o datos fuera de sus permisos en las pruebas; 100 % del tráfico por HTTPS; 100 % de las operaciones críticas quedan en el registro de auditoría. | Must          | NS06; HU-01        |
| RNF-02 | Concurrencia e integridad   | La emisión y asignación de turnos se ejecuta mediante transacciones que impiden condiciones de carrera, incluso con varias ventanillas y el tótem operando a la vez.                                                                                                                                                                                                                                        | 0 turnos duplicados o asignados a ventanillas deshabilitadas en al menos 3 escenarios de carga concurrente.                                                                    | Must          | NS04; HU-07, HU-04 |
| RNF-03 | Operación sin conexión      | El módulo de reparto permite consultar las entregas cargadas y registrar su estado sin señal móvil (service worker y almacenamiento local), sincronizando al recuperar la conexión sin pérdidas ni duplicados.                                                                                                                                                                                              | 100 % de los registros hechos sin conexión se sincronizan en ≤ 5 min tras reconectar; 0 registros duplicados.                                                                  | Must          | NS05; HU-14, HU-15 |
| RNF-04 | Accesibilidad               | La interfaz cumple las pautas WCAG 2.1 nivel AA: tipografía ampliada, alto contraste y avisos visuales y sonoros concordantes, sin depender solo del color o del sonido.                                                                                                                                                                                                                                    | Contraste ≥ 4,5:1; auditoría automática sin errores de nivel AA; prueba de usabilidad con al menos 5 usuarios representativos.                                                 | Must          | NS07; HU-08, HU-09 |
| RNF-05 | Rendimiento                 | La plataforma responde oportunamente a la emisión y consulta, y sincroniza la pantalla de sala de espera con la interfaz de farmacia.                                                                                                                                                                                                                                                                       | ≤ 2 s en el 95 % de las solicitudes; latencia ≤ 2 s entre la confirmación del llamado y su despliegue en pantalla.                                                             | Must          | NS02, NS03         |
| RNF-06 | Disponibilidad              | Las funciones principales están disponibles durante el horario de atención de farmacia y las jornadas de reparto.                                                                                                                                                                                                                                                                                           | ≥ 99 % mensual en horario de atención (meta de implementación; en el prototipo se monitorea durante las pruebas).                                                              | Should        | NS01               |
| RNF-07 | Interoperabilidad con Rayén | Al no existir integración vía API, la plataforma importa periódicamente el padrón de pacientes crónicos y postrados y sus recetas vigentes desde archivos CSV/Excel exportados de Rayén.                                                                                                                                                                                                                    | Importación de un padrón sintético de 670 pacientes sin errores ni digitación manual; las filas inválidas se informan sin detener la carga de las válidas.                     | Must          | HU-23, HU-21       |
| RNF-08 | Respaldo y recuperación     | La base de datos se respalda automáticamente y el servicio se restablece ante caídas sin pérdida de turnos ni entregas.                                                                                                                                                                                                                                                                                     | Respaldo diario verificado; restablecimiento ≤ 30 min en simulacro.                                                                                                            | Should        | NS08               |
| RNF-09 | Compatibilidad              | La PWA funciona en navegadores actuales de escritorio (ventanillas y pantalla) y en los dispositivos móviles del personal de reparto, y se puede instalar desde el navegador.                                                                                                                                                                                                                               | Pruebas funcionales aprobadas en al menos 2 navegadores de escritorio y 1 dispositivo móvil.                                                                                   | Should        | HU-14, HU-15       |

# IV. Marco Teórico.

## 4.1 Investigación Bibliográfica.

#### Teoría de Colas y Encolamiento ponderado

La Teoría de Colas es el estudio matemático de las líneas de espera. En el ámbito de la ingeniería de software y la gestión de servicios, esta teoría permite analizar y diseñar sistemas que administran de forma eficiente el flujo de usuarios que demandan atención (Mallick et al., 2022).

Tradicionalmente, muchos sistemas utilizan un modelo llamado FIFO (First In, First Out o "Primero en entrar, primero en salir"). Sin embargo, la literatura señala que los modelos FIFO son ineficientes en entornos de salud pública, ya que no permiten gestionar urgencias o leyes de preferencia (Torres Lopez & Pachas Huaytan, 2025).

Para solucionar esto, la informática propone los "Algoritmos de Encolamiento con Prioridades Ponderadas". Estos algoritmos permiten que el sistema informático tome decisiones automáticas basadas en reglas matemáticas; por ejemplo, asegurar que, por cada dos pacientes de la fila general, se llame a un paciente de la fila de adultos mayores. Esto garantiza que el flujo preferencial sea constante sin detener por completo la atención del público general (Mallick et al., 2022).

#### Arquitectura de sincronización en tiempo real

Para que un sistema de gestión de filas sea efectivo, la información debe fluir instantáneamente entre los distintos dispositivos involucrados. A esto se le conoce como sincronización en tiempo real. Autores como Chan et al. (2021) definen que una arquitectura en tiempo real debe ser capaz de procesar y mostrar la información en fracciones de segundo, garantizando que todos los actores (pacientes en la sala y funcionarios en la farmacia) vean exactamente los mismos datos al mismo tiempo.

Un desafío crítico en estos sistemas es el manejo de la "concurrencia", es decir, cuando múltiples eventos ocurren al mismo tiempo. En programación, existe un riesgo conocido como "condición de carrera" (*race condition*). Esto sucede, por ejemplo, si dos funcionarios en distintas ventanillas presionan el botón "Llamar siguiente paciente" en el mismo milisegundo. Si la arquitectura del sistema no es robusta, ambos podrían llamar al mismo número, generando confusión (Chang et al., 2021). Por ello, la investigación bibliográfica sugiere el uso de bases de datos transaccionales que bloquean temporalmente un registro mientras es asignado, asegurando que cada turno sea único e irrepetible.

#### Accesibilidad e interfaz para adultos mayores

El diseño de interfaz de usuario y la experiencia de usuario son disciplinas de la informática centradas en cómo las personas interactúan con las pantallas y sistemas digitales. *“Cuando el público objetivo está compuesto mayoritariamente por personas de la tercera edad o de zonas rurales, los estándares de diseño genéricos no son suficientes”* (Moreno & Martínez, 2012).

*“Según las directrices internacionales de accesibilidad web, como las WCAG (Web Content Accessibility Guidelines), los sistemas orientados a adultos mayores deben compensar la disminución natural de las capacidades visuales y auditivas”* (World Wide Web Consortium, 2010).

Esto requiere interfaces que eviten la ambigüedad, utilizando colores de alto contraste (como texto negro sobre fondo blanco o amarillo), tipografías de tamaño ampliado y sin adornos que dificulten la lectura. Además, la literatura médica y tecnológica recomienda encarecidamente que los estímulos visuales en las pantallas de las salas de espera estén siempre acompañados de alertas sonoras y locuciones de voz claras, lo que reduce la ansiedad del usuario al no depender de un solo sentido para recibir la información (Moreno & Martínez, 2012).

#### Informática médica

*“La interoperabilidad tecnológica se define como la capacidad de diferentes sistemas informáticos, aplicaciones o componentes de software para comunicarse, intercambiar datos y utilizar la información compartida de manera fluida”* (Lugo et al., 2009). En el contexto de la salud pública, esto es un pilar fundamental de la Informática Médica.

En la atención primaria, los recintos médicos suelen utilizar software clínico para registrar las atenciones (como recetas electrónicas o fichas clínicas). Si un nuevo sistema de gestión de filas no es interoperable, funcionará como una "isla", obligando al personal o al paciente a ingresar sus datos manualmente de nuevo al llegar a la farmacia (Lugo et al., 2009).

La investigación indica que integrar el sistema de turnos directamente con el sistema clínico mediante interfaces de programación (APIs) reduce los errores de digitación humana, agiliza los tiempos de tránsito del paciente dentro del recinto y permite una trazabilidad completa desde que el paciente sale del box médico hasta que recibe su medicamento (Lugo et al., 2009).

# V. Objetivos del Proyecto.

## 5.1 Solución tecnológica

### 5.1.1 Formulación de la Solución

La solución tecnológica propuesta consiste en una plataforma web progresiva (PWA) de gestión de turnos y entrega de medicamentos de la Unidad de Farmacia del CESFAM San Nicolás, El sistema permite a los pacientes emitir su turno de atención mediante el ingreso de su RUT en un tótem de autoservicio; A continuación, un algoritmo de encolamiento con prioridades ponderadas asigna una ventanilla de manera automática correspondiente a su tipo de atención (preferencial, general, crónicos o urgencia). Para el personal de farmacia, la plataforma ofrece gestión de ventanilla y un llamado sonoro sincronizada en tiempo real con la pantalla de espera, incorporando las alertas sonoras para los pacientes con dificultades visuales o auditivas.

Adicionalmente se la plataforma incorpora un módulo de logística y trazabilidad de entregas domiciliarias, que permite a los conductores (Encargados de terreno) registrar la dirección y referencias geográficas de pacientes postrados y adultos mayores, sugerir un orden de visita al conductor y la TENS está encargada de registrar y confirma el estado de la entrega, incluso en condiciones de señal intermitente como lo es un sector rural. Por último, la solución considera el control interno de vigencia y entregas parciales de recetas crónicas, junto con un panel de mermas e indicadores para la Jefatura de Farmacia.

La solución se basa en una arquitectura cliente-servidor de tres capas. La capa de presentación corresponde a la PWA, que se ejecuta en el tótem de autoservicio, en los equipos de ventanilla, en la pantalla de sala de espera y en el teléfono del conductor/tens. La capa de lógica de negocio corresponde a un servidor de aplicaciones que expone una API REST. La capa de datos corresponde a un motor de base de datos relacional transaccional.

La asignación de turnos se ejecuta dentro de transacciones con bloqueo de fila y secuencias atómicas del motor de base de datos, de modo que dos solicitudes simultáneas no puedan obtener el mismo número ni asignar un turno a dos ventanillas. Con ello se aborda el riesgo de condiciones de carrera descrito por Chang et al. (2021) para aplicaciones Node.js orientadas a eventos. La sincronización entre ventanillas y pantalla de espera se realiza mediante conexiones WebSocket, mientras que la operación sin conexión del módulo de reparto se resuelve con un Service Worker y almacenamiento local en el navegador, con sincronización diferida al recuperar la señal.

### 5.1.2 Alcance y restricciones.

El alcance del proyecto se define por el desarrollo del prototipo de una plataforma web progresiva, un módulo de gestión de turnos y filas, logística y trazabilidad de entregas, control de vigencia de recetas y panel de mermas e indicadores. Las entregas finales del proyecto incluyen el prototipo desplegado y una demostración a el Director de Salud Municipal, Director de CESFAM y Personal de Farmacia. No obstante, el diseño técnico, el nivel de servicio y presupuesto se formula considerando una implementación real en el CESFAM

Incluye:

- Emisión de turno mediante RUT y asignación automática de ventanilla (HU-07).

- Algoritmo de encolamiento con prioridades ponderadas entre atención general y preferencial (HU-04 a HU-10).

- Llamado y re-llamado de pacientes con alerta sonora (HU-05, HU-09).

- Registro de direcciones y referencias georreferenciadas, y sugerencia de orden de visita para entregas a domicilio (HU-12, HU-14).

- Notificación de despacho en camino y confirmación de recepción por el paciente o cuidador (HU-19, HU-22).

- Control interno de vigencia y entregas parciales de recetas crónicas (HU-21).

- Panel de mermas por período (HU-20).

No incluye:

- Integración real vía API con el sistema clínico institucional Rayén (se simula una base de datos y un mecanismo de emisión de recetas propios).

- Geolocalización satelital en tiempo real de los vehículos de reparto fuera de alcance en esta versión

- Despliegue en otros CESFAM de la red municipal.

- Desarrollo de una aplicación móvil nativa (el conductor opera desde la misma PWA responsiva).

- Implementación física del sistema en las instalaciones del CESFAM, que queda como una etapa posterior a cargo de la institución

Restricciones:

- Plazo: el proyecto debe completarse en un semestre académico.

- Equipo: el desarrollo está a cargo de tres estudiantes, lo que limita la cantidad de personas trabajando.

- Presupuesto: el prototipo se desarrolla con herramientas de código abierto y servicios cloud de bajo costo; la implementación real depende del financiamiento municipal.

- Conectividad: el 57,9% de la población de San Nicolás es rural, por lo que la señal móvil es intermitente, es por esto por lo que el módulo de reparto debe operar sin conexión.

- Datos sensibles: el tratamiento de datos de salud debe cumplir la Ley N° 19.628 sobre protección de la vida privada y la Ley N° 20.584 sobre derechos y deberes de los pacientes; el prototipo trabaja con datos ficticios. La Ley 21.719 sobre Protección de Datos Personales en Chile entrará en vigencia plena el 1 de diciembre de 2026, reemplazando y reformando por completo la antigua Ley N° 19.628 de 1999.

- Dependencia institucional**:** La puesta en marcha en el CESFAM requiere que la institución provea el hardware y los servicios necesarios (servidor, red, tótem, pantalla de sala de espera y equipos de ventanilla). Por esta razón, el desarrollo y la evaluación del prototipo se realizan en un entorno independiente, de modo que ningún retraso en la entrega de infraestructura por parte del CESFAM afecte el cumplimiento de los plazos del proyecto.

## 5.2 Impacto de la solución.

### 5.2.1 Proceso de negocio afectado.

El proyecto interviene de forma directa en dos procesos críticos pertenecientes a la Unidad de Farmacia del CESFAM San Nicolás.

Asignación y llamado por turnos (presencial): Se modifica el actual método manual, basado en rollos de papel que propician colisiones numéricas, aglomeraciones en ventanilla y falta de visibilidad del flujo para el personal médico. La solución tecnológica automatiza este subproceso mediante la implementación de una arquitectura cliente-servidor y un motor de base de datos transaccional que previene las condiciones de carrera (race conditions) durante la emisión. El paciente digita su RUT en una pantalla de autoservicio y un algoritmo de encolamiento con prioridades ponderadas le asigna automáticamente la ventanilla correspondiente. El llamado se sincroniza en tiempo real entre la interfaz de farmacia y la pantalla de la sala de espera, incorporando alertas visuales y sonoras.

Logística y trazabilidad de entregas: Se reestructura el proceso de distribución, el cual actualmente depende del conocimiento empírico de los conductores sobre direcciones rurales ambiguas, afectando la atención de 70 pacientes postrados y 600 adultos mayores de 80 años. El nuevo sistema incorpora un módulo dedicado a la georreferenciación rural y a la trazabilidad de ruta, permitiendo registrar las coordenadas de los domicilios y sugerir un orden óptimo de visita. Asimismo, facilita a los Técnicos en Enfermería (TENS) el registro del estado de cada despacho con capacidad de funcionamiento sin conexión (offline). Finalmente, se emiten notificaciones de estado a los pacientes o cuidadores para asegurar la entrega oportuna.

**Control de vigencia de recetas crónicas y mermas**

**Situación actual:** la farmacia no cuenta con un registro sistematizado de las recetas preparadas que no son retiradas ni del avance de las entregas parciales de cada receta crónica, lo que genera mermas de medicamentos sin trazabilidad. La información de pacientes y recetas reside en Rayén, sistema con el que no existe integración vía API.

**Situación propuesta:** el padrón de pacientes crónicos y postrados, junto con sus recetas vigentes, se carga periódicamente mediante la importación de archivos CSV/Excel exportados desde Rayén, evitando que el personal de farmacia digite dos veces cada receta. Sobre esa información, la plataforma controla las entregas parciales de cada receta (por ejemplo, “3 de 6”), alerta sobre las recetas próximas a vencer y presenta a la Jefatura de Farmacia un panel de mermas por período.

### 5.2.2 Registro de Interesados.

El registro identifica a los actores vinculados con la formulación y futura utilización de la plataforma. Dado que el proyecto se limita a un prototipo en entorno aislado, sus expectativas se expresan como requisitos y evidencias de validación, no como mejoras operacionales ya comprobadas. La participación institucional en pruebas o una eventual implementación requerirá autorización específica.

| Interesado/s                                 | Relación con el proyecto                                                                                              | Expectativa e indicadores técnicos (KPIs)                                                                                                                                                       | Interés | Impacto |
|----------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|---------|
| Jefatura y funcionarios de farmacia          | Usuarios responsables de la administración de cuentas, turnos, ventanillas y recetas simuladas.                       | Disponer de un prototipo que permita emitir y atender turnos sin duplicaciones; verificar la importación CSV/Excel de pacientes y recetas sintéticas para evitar una segunda digitación manual. | Alto    | Alto    |
| Pacientes de atención general y preferencial | Beneficiarios potenciales de la atención presencial; sus perfiles y turnos se representarán mediante datos ficticios. | Contar con una interfaz clara y accesible que muestre número de turno, ventanilla y avisos visuales y sonoros. Su impacto en la espera real queda fuera de la validación académica.             | Alto    | Alto    |
| Pacientes crónicos, postrados y cuidadores   | Beneficiarios potenciales de la consulta y trazabilidad de entregas domiciliarias.                                    | Permitir la consulta de entregas, estados y referencias geográficas simuladas, respetando la privacidad de la información.                                                                      | Alto    | Medio   |
| Conductores y personal de apoyo de reparto   | Usuarios previstos del módulo de asignación y trazabilidad de entregas                                                | Probar la consulta de rutas y direcciones ficticias, el registro de estados y la sincronización                                                                                                 | Alto    | Medio   |
| Dirección del CESFAM y DESAMU                | Contraparte institucional que aporta contexto y puede evaluar una eventual adopción futura                            | Revisar la pertinencia del prototipo y los resultados de pruebas; no se comprometen reducciones reales de tiempos ni tasas productivas de entrega.                                              | Alto    | Medio   |
| Unidad TIC del CESFAM                        | Contraparte técnica para una posible evaluación futura de infraestructura, seguridad y compatibilidad.                | Disponer de documentación de arquitectura, controles de acceso y pruebas, sin integración directa con Rayén ni despliegue físico durante esta etapa.                                            | Medio   | Medio   |

### 5.2.3 Indicadores de gestión.

Con el propósito de evaluar el impacto de la Plataforma Web Progresiva (PWA) sobre los procesos de atención en farmacia y de entrega domiciliaria de medicamentos, se definen seis indicadores de gestión. Cada indicador se asocia a una línea base levantada durante el diagnóstico (Objetivo Específico 1) y al módulo de la plataforma que permitirá medirlo.

Dado que el proyecto se limita a un prototipo operado con datos sintéticos (sección 5.1.2), las metas corresponden al impacto proyectado una vez que la plataforma sea implementada en el CESFAM. Durante el proyecto se verifica, en simulación, que la plataforma registra y calcula correctamente cada indicador (Objetivo Específico 4); la medición real de las metas queda a cargo de la institución en la etapa de implementación

| ID   | Indicadores de gestión                                             | Línea Base                                                                                                          | Meta      | Descripción                                                                                                                                                                                                                                                                                                                                                             |
|------|--------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| IG01 | Tiempo promedio de espera de pacientes                             | 15 min (Plan de Salud Municipal y entrevistas)                                                                      | \<= 8 min | Este indicador mide el tiempo promedio transcurrido desde que un paciente obtiene su turno hasta que es llamado para ser atendido en una ventanilla de farmacia.<br>Permitirá evaluar si el sistema de gestión de turno contribuye a mejorar el flujo de atención y reducir los tiempos de espera de los pacientes.                                                     |
| IG02 | Cantidad de incidencias/confusiones asociadas al sistema de turnos | 20% de los días hábiles al mes                                                                                      | \<= 10%   | Se medirá la cantidad de situaciones problemáticas relacionadas con la gestión de turnos, como confusión entre números de atención, dificultades para identificar el turno llamado o inconvenientes asociados al orden de atención. Permitirá evaluar si la implementación del sistema disminuye los problemas generados por el método actual de organización de filas. |
| IG03 | Porcentaje de entregas domiciliaras exitosas                       | 85% entregas exitosas realizadas en la semana (las que no pueden ser entregadas, el conductor debe volver otro día) | \>= 90%   | Se medirá el porcentaje de entregas de medicamentos a domicilio que son realizadas correctamente respecto del total de entregas programadas. Permitirá evaluar la efectividad del proceso de distribución domiciliaria y determinar si la plataforma contribuye a mejorar su gestión.                                                                                   |
| IG04 | Porcentaje de domicilios con dirección verificada                  | 1,74% de direcciones locales en el pueblo, el resto es rural.                                                       | 100%      | Se medirá el porcentaje de domicilios registrados cuya dirección y referencias de ubicación han sido verificadas respecto del total de domicilios almacenados en el sistema. Permitirá evaluar la calidad de la información utilizada para planificar y realizar las entregas domiciliarias                                                                             |

### 5.2.4 Niveles de servicio.

Con el fin de asegurar que la plataforma opere de forma continua y eficiente para pacientes y funcionarios, se definen niveles de servicio medibles. Las métricas comprometidas están orientadas a una implementación real en el CESFAM; la columna “Verificación en el prototipo” indica cómo se comprueba cada nivel durante el proyecto, en el entorno de pruebas con datos sintéticos (Objetivo Específico 4). Cada nivel de servicio se relaciona con un requerimiento no funcional (RNF) definido en la sección **3.X**.

| **ID** | **Nivel de servicio**                       | **Descripción**                                                                                                                                                                                                             | **Métrica comprometida**                                                  | **Verificación en el prototipo**                                                                                                                     | **RNF** |
|--------|---------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|---------|
| NS01   | Disponibilidad de las funciones principales | Las funciones de emisión y llamado de turnos, consulta de entregas y registro de su estado deben estar disponibles durante el horario de atención de farmacia y las jornadas de reparto.                                    | ≥ 99 % mensual dentro del horario de atención                             | Meta aplicable a la implementación. En el prototipo se monitorea el tiempo activo del entorno cloud durante el período de pruebas y la demostración. | RNF-06  |
| NS02   | Tiempo de respuesta de la plataforma        | La plataforma debe responder oportunamente a la emisión de turnos y la consulta de entregas, considerando el uso simultáneo de las ventanillas habilitadas, el punto de emisión y la pantalla de la sala de espera.         | ≤ 2 s en el 95 % de las solicitudes                                       | Prueba de carga con uso simultáneo de ventanillas, tótem y pantalla.                                                                                 | RNF-05  |
| NS03   | Actualización de la pantalla de turnos      | Al confirmarse un llamado, la interfaz de farmacia y la pantalla de la sala de espera deben mostrar el mismo número y ventanilla, sin información desactualizada o contradictoria.                                          | Latencia de sincronización ≤ 2 s                                          | Medición del tiempo entre la confirmación del llamado y su despliegue en pantalla durante las pruebas de carga.                                      | RNF-05  |
| NS04   | Consistencia en la asignación de turnos     | Un mismo turno no puede asignarse a distintas ventanillas ni derivarse a una ventanilla deshabilitada. Se respetan las reglas de prioridad y el re-llamado conserva la asignación vigente.                                  | 0 asignaciones duplicadas en pruebas de carga concurrente                 | Pruebas de carga concurrente en al menos 3 escenarios.                                                                                               | RNF-02  |
| NS05   | Continuidad del registro de reparto         | El módulo de reparto permite registrar el resultado de las entregas cargadas en el dispositivo aun sin conexión. Los cambios se conservan localmente y se sincronizan al recuperar la conexión, sin pérdidas ni duplicados. | 100 % de registros sincronizados ≤ 5 min después de recuperar la conexión | Prueba de registro sin conexión (modo avión) y posterior reconexión.                                                                                 | RNF-03  |
| NS06   | Trazabilidad de las entregas                | Cada entrega conserva identificador, estado, fecha, hora y funcionario responsable. Las no entregas registran su motivo y las reprogramaciones mantienen el historial de intentos.                                          | 100 % de entregas con registro completo                                   | Revisión de los registros de entregas, no entregas y reprogramaciones del set de datos sintéticos.                                                   | RNF-01  |
| NS07   | Comunicación visual y sonora de los turnos  | Cada llamado y re-llamado comunica número y ventanilla con información visual y aviso de voz concordantes, texto legible y alto contraste, sin depender solo del color o del sonido.                                        | Contraste WCAG 2.1 AA (≥ 4,5:1)                                           | Auditoría automática de accesibilidad y pruebas de usabilidad con al menos 5 usuarios.                                                               | RNF-04  |
| NS08   | Recuperación de fallas                      | Ante una caída del servidor, el servicio se restablece sin pérdida de los turnos ni de las entregas registradas.                                                                                                            | Restablecimiento ≤ 30 min; respaldo diario de la base de datos            | Simulacro de caída y restauración desde el respaldo.                                                                                                 | RNF-08  |

CITACION A CLAUDE OPUS 5.5 ALTO

## 5.3 Objetivos del proyecto

### 5.3.1 Objetivo General.

Desarrollar y validar un prototipo funcional de Plataforma Web Progresiva (PWA) para la gestión de turnos de atención y la trazabilidad de entregas domiciliarias de medicamentos en la Unidad de Farmacia del CESFAM San Nicolás, integrando mecanismos de planificación y priorización de flujos, sincronización en tiempo real, operación asíncrona sin conexión e importación periódica del padrón de pacientes desde Rayén, con el propósito de viabilizar la reducción de los tiempos de espera y de las mermas de recetas, así como asegurar el despacho rural, contribuyendo a mejorar la experiencia de atención de la población adulta mayor y las condiciones laborales del personal.

### 5.3.2 Objetivos Específicos.

- **Análisis y Planificación:** Especificar los requerimientos funcionales y no funcionales de la plataforma, levantar la línea base de los indicadores de gestión y elaborar el plan del proyecto, a partir de entrevistas y reuniones de donde se reunió la información con la Unidad de Farmacia y de la revisión los registros institucionales. El resultado se documenta en 23 historias de usuario priorizadas con MoSCoW, una tabla de requerimientos no funcionales y la planificación del proyecto (cronograma, equipo y recursos).

- **Diseñar.** Diseñar la arquitectura cliente-servidor de la PWA, el modelo de datos y el algoritmo de encolamiento con prioridades ponderadas. El diseño incorpora la sincronización en tiempo real, la operación sin conexión y la importación del padrón desde archivos CSV/Excel exportados de Rayén. Se documenta en diagramas de arquitectura, un modelo entidad-relación y prototipos de interfaz que cumplen WCAG 2.1 nivel AA.

- **Construcción.** Construir de forma incremental, en sprints Scrum, los módulos de gestión de turnos, georreferenciación y despacho de entregas, control de vigencia de recetas con panel de mermas, e importación del padrón, logrando que el 100 % de las historias de usuario priorizadas como Must y al menos el 80 % de las priorizadas como Should cumplan la Definición de Terminado (DoD).

- **Pruebas y Validación:** Validar el prototipo en un entorno aislado con datos sintéticos, mediante pruebas funcionales, de carga concurrente, de operación sin conexión y de usabilidad. Debe verificarse:

  - 0 turnos duplicados y una latencia de 2 segundos o menos, en al menos 3 escenarios de carga;

  - sincronización del 100 % de los registros hechos sin conexión, en 5 minutos o menos;

  - importación sin errores de un padrón sintético de 670 pacientes;

  - una evaluación de usabilidad con al menos 5 usuarios representativos.

- **Despliegue y capacitación:** Desplegar el prototipo validado en un entorno cloud de demostración y transferirlo a la Unidad de Farmacia mediante una sesión de demostración y capacitación con la Jefatura de Farmacia, el personal técnico y los directivos del CESFAM y del DESAMU, entregando un manual de usuario, la documentación técnica y un plan de implementación para su futura puesta en marcha institucional, con un acta de conformidad firmada por la contraparte.

# VI. Metodología de Trabajo

## 6.1 Metodología de Desarrollo de la solución.

Para la construcción de la plataforma web progresiva enfocada en la gestión de turnos y logística de entregas del CESFAM San Nicolas, se establece la adopción de la metodología ágil SCRUM. Este marco de trabajo radica en la necesidad de abordar un problema que evidencia una alta complejidad técnica, que incluye la concurrencia en tiempo real, encolamiento con conectividad intermitente. Scrum otorga la flexibilidad necesaria para desarrollar el software de manera iterativa e incremental, permitiendo la adaptación frente a los requerimientos de accesibilidad y facilitando la validación constante mediante retroalimentación temprana por parte de la Jefatura de farmacia y personal de reparto.

\- Organización a través de Sprints: Considerando que el plazo de ejecución del proyecto se circunscribe a un semestre académico de 14 semanas, el trabajo se ha estructurado estratégicamente en iteraciones cortas o Sprints de carácter quincenal. Esta división permite organizar el desarrollo en siete ciclos consecutivos, garantizando que cada quincena culmine con un incremento de software plenamente funcional y evaluable. Establecer esta periodicidad resulta fundamental para mantener un ritmo de avance constante, lo que facilita someter a pruebas progresivas los módulos más críticos del sistema, como la asignación transaccional de turnos o la trazabilidad de las rutas de despacho, sin necesidad de esperar al cierre del semestre para aplicar correcciones.

\- Roles del Equipo bajo la metodología establecida: Siguiendo los lineamientos del marco ágil, el equipo asume roles específicos para asegurar la viabilidad y calidad de la solución. Uno de los integrantes ejercerá como Product Owner, encargado de representar las necesidades operativas del CESFAM San Nicolás y de priorizar el listado de requerimientos para maximizar el valor del producto final. Otro estudiante asumirá el rol de Scrum Master, facilitando la correcta adopción de la metodología y gestionando activamente cualquier impedimento técnico o logístico que ponga en riesgo el cumplimiento de las metas quincenales. De manera transversal, los tres integrantes actuarán en conjunto como el Equipo de Desarrollo, organizándose de forma autónoma para materializar la arquitectura técnica de la plataforma.

Artefactos y Eventos: La transparencia y trazabilidad del proyecto se gestionan mediante los artefactos propios de Scrum. La totalidad de los requerimientos funcionales y técnicos se centraliza en el Product Backlog, el cual actúa como un registro dinámico que guía el rumbo de la plataforma. A partir de este documento, el equipo selecciona al inicio de cada quincena las historias de usuario prioritarias para conformar el Sprint Backlog, definiendo así el alcance concreto y las tareas de esa iteración específica.

Para coordinar este flujo de trabajo, el equipo estructura su avance en torno a ceremonias clave. Cada ciclo inicia con una sesión de planificación para definir los objetivos de la quincena, apoyada por breves reuniones periódicas de sincronización que permiten evaluar el progreso a corto plazo. Finalmente, cada Sprint concluye con una revisión destinada a demostrar de manera empírica el funcionamiento del módulo desarrollado, seguida inmediatamente por una retrospectiva que invita al equipo a reflexionar sobre sus procesos y aplicar mejoras continuas para el siguiente ciclo de desarrollo

## 6.2 Duración y cronograma.

El proyecto contempla una duración de 14 semanas, equivalente a 65 días hábiles de ejecución según los reajustes realizados por Microsoft Project. Para estructurar y priorizar el desarrollo bajo un orden lógico y secuencial coherente con la metodología ágil, se elaboró una carta Gantt que divide el trabajo en cinco bases principales:

1.  Gestión del proyecto: Contempla la planificación de Sprints, control de riesgos e informes de seguimiento quincenales.

2.  Arquitectura y Diseño de la Solución: Abarca el modelamiento de la base de datos transaccional, diseño de UI/UX accesible (WCAG 2.1 AA) y la especificación del algoritmo de encolamiento ponderado.

3.  Software PWA Farmacia CESFAM: Fase de construcción técnica que incluye los módulos de gestión de turnos, recetas crónicas, georreferenciación logística para despachos, notificaciones y seguridad.

4.  Aseguramiento de Calidad y Pruebas: Ejecución de pruebas funcionales, de carga (concurrencia) y pruebas de aceptación de usuario (UAT).

5.  Infraestructura y Despliegue: Configuración del entorno Cloud, instalación del equipamiento físico en la farmacia y capacitación del personal.

**Figura 5.** Estadísticas del proyecto en Microsoft Project

**Figura 6.** Carta Gantt del proyecto

## 6.3 Equipo de trabajo.

El equipo responsable del desarrollo de la solución está compuesto por tres estudiantes, quienes se distribuyen técnica y metodológicamente las cargas de trabajo a lo largo de las iteraciones. Para establecer responsabilidades claras de ejecución y validación, integrando a los actores clave de la institución de salud, se confeccionó la siguiente Matriz RACI.

(Nomenclatura: Responsable de ejecutar(R), Aprobador/Autoridad(A), Consultado(C), Informado(I))

| Tareas y entregables del proyecto                     | Fernanda Daza (Scrum Master) | Claudio Rojas (Product Owner) | Isidora Rubio (Developer) | Jefa de Farmacia (Stakeholder) | Unidad TIC CESFAM (Soporte) |
|-------------------------------------------------------|------------------------------|-------------------------------|---------------------------|--------------------------------|-----------------------------|
| Planificación de Sprints e informes de seguimiento.   | R / A                        | R                             | R                         | C                              | I                           |
| Diseño de arquitectura y base de datos transaccional  | C                            | A                             | C                         | I                              | C                           |
| Desarrollo del módulo de turnos y encolamiento        | C                            | A                             | R                         | C                              | I                           |
| Desarrollo del módulo de trazabilidad y despacho      | C                            | A                             | C                         | C                              | I                           |
| Configuración del entorno cloud y equipamiento físico | C                            | A                             | R                         | I                              | R                           |
| Pruebas de calidad y aceptación de usuario (UAT)      | R                            | R                             | C                         | A                              | C                           |

## 6.4 Plan de recursos.

Se elaboró un presupuesto financiero a detalle que cure todos los requerimientos del personal, equipamiento y servicios. El costo total del proyecto asciende a \$8.810.000, considerando un volumen de trabajo de 1064 horas profesionales.

**Figura 7.** Estado y distribución de costos del proyecto

**Figura 8.** Detalle de costos por tareas de nivel superior

# VII. Definición de arquitectura TI

## 7.1 Definir el tipo de arquitectura TI que requiere la solución informática.

La solución precisa una arquitectura de aplicación web cliente-servidor de tres capas (presentación, lógica del negocio y datos) se implementa como Plataforma Web Progresiva (PWA) y la complementa con tiempo real en sus acciones y opera sin conexión. Es una arquitectura autónoma respecto a sistemas institucionales como lo es “Rayén”.

**Proyecto:** Plataforma Web Progresiva (PWA) para la gestión de turnos y la trazabilidad de entregas domiciliarias de la Unidad de Farmacia del CESFAM San Nicolás.

**Arquitectura TI (tecnología sugerida):**

- **Capa de presentación:** Interfaz web progresiva (PWA) desarrollada con Alpine.js para la interactividad del lado del cliente, accesible desde el navegador, con vistas por perfil: tótem de autoservicio, ventanilla, pantalla de sala de espera, dispositivo del conductor o TENS y panel de indicadores para la Jefatura de Farmacia.

- **Capa de lógica de negocio:** Servidor de aplicaciones desarrollado en Python con el framework Django, que expone una API REST y se encarga del encolamiento con prioridades ponderadas, la asignación de ventanilla, la estimación de espera, el control de vigencia de recetas (simulado), la sugerencia de orden de visita y las notificaciones. La sincronización en tiempo real entre ventanillas y pantalla se realiza mediante WebSocket.

- **Capa de datos:** Base de datos relacional PostgreSQL, con bloqueo de fila y secuencias atómicas para la emisión de turnos, que almacenará la información de turnos, recetas y entregas (datos ficticios en el prototipo). En el dispositivo del conductor se utiliza almacenamiento local con Service Worker para operar sin conexión y sincronizar al recuperar la señal.

- **Infraestructura:** El prototipo se alojará en un servicio cloud de bajo costo. Para la implementación real, la elección entre nube y servidor local corresponde a DESAMU y su unidad de TIC. Se complementa con el equipamiento en el establecimiento: tótem, pantalla y parlantes de sala de espera, y los dispositivos de los conductores.

| Capa / componente      | Descripción                                                                                                                                                                                                                | Requisitos que resuelve                          |
|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------|
| Presentación (PWA)     | Vistas por perfil: tótem de autoservicio, ventanilla, pantalla de sala de espera, dispositivo del, panel de indicadores y enlace directo para paciente o cuidador.                                                         | HU-04 a HU-09, HU-12 a HU-15, HU-20, HU-22; NS07 |
| Lógica de negocio      | Servidor de aplicaciones con API REST: encolamiento con prioridades ponderadas, asignación de ventanilla, estimación de espera, control de vigencia de recetas (simulado), sugerencia de orden de visita y notificaciones. | HU-04, HU-07, HU-10, HU-14, HU-18, HU-19, HU-21  |
| Tiempo real            | Conexiones WebSocket entre ventanillas y pantalla de sala de espera.                                                                                                                                                       | NS03 (≤ 2 s)                                     |
| Datos                  | Base de datos relacional transaccional, con bloqueo de fila y secuencias atómicas para la emisión de turnos. Datos ficticios en el prototipo.                                                                              | NS04, NS06, NS08                                 |
| Operación sin conexión | Service Worker y almacenamiento local, con sincronización diferida al recuperar señal.                                                                                                                                     | HU-15, NS05                                      |
| Servicios externos     | Envío de notificaciones (SMS o push web) y cartografía.                                                                                                                                                                    | HU-14, HU-19                                     |

> Elaboración propia con asistencia de Claude Sonnet 5.5 Alto (Anthropic, 2026)

Esta arquitectura responde a los requerimientos levantados en terreno. La concurrencia entre las lventanillas necesita un motor transaccional. La PWA permite un único desarrollo para todos los dispositivos, por lo que ya no seria indispensable contar con una aplicación nativa para celulares. Esto tiene coherencia con que la Dirección indico que no existe presupuesto asignado para arquitectura tecnológica. (Entrevista al director del CESFAM, 24 de agosto 2026). Además, el Plan de Salud señala que la cobertura de telefonía disminuye en sectores rurales (DESAMU, 2025). Lo que lleva a la justificación de una operación sin conexión del módulo de reparto.

Respecto del despliegue, el prototipo se alojará en un servicio cloud de bajo costo con datos ficticios. Para la implementación real, el director declara preferir la nube, pero condiciona la decisión si es posible subir los datos de los pacientes a ella. También indicó que el soporte informático lo entregan Daniel Parada y David Alarcón. Por ello, la elección entre nube y servidor local corresponde a DESAMU y su unidad de TIC.

La plataforma convive con la infraestructura tecnológica existente y no se reemplaza:

- Rayén: módulos de farmacia, urgencia, clínico y administrativo. Manejo de estados de receta y descuenta del inventario.

- Locker Inteligente: su función principal es recibir los medicamentos de manera más cómoda por un casillero, fue adquirido por licitación. Tiene software, cámara y notifica por SMS. (DESAMU, 2025).

- Otros sistemas: electrocardiógrafo, telesalud, radiocomunicaciones y EPIVIGILA (DESAMU, 2025)

Al no integrarse con Rayén, la plataforma opera como un sistema aislado. Se reconoce está limitación en el alcance. Queda como líneas a la integración futura (validación del RUT de los pacientes inscritos), el estado de las recetas y la emisión automática del turno al término de la atención.

# VIII. Reconocimiento de arquitectura empresarial

## 8.1 Identificación del tipo de organización y su estructura.

El CESFAM de San Nicolás es una organización pública sin fines de lucro, del sector salud y de nivel de atención primaria. Es administrado por la Municipalidad De San Nicolás a través del Departamento de Salud Municipal (DESAMU) y se rige por la Ley N° 19.378. Es el establecimiento base de la red comunal, integra además la Posta Puente Ñuble y el Servicio de Urgencia Rural, y pertenece a la Micro Red de San Carlos. (DESAMU, 2025).

Su estructura es jerárquica de tipo funcional, en dos niveles. En el nivel comunal, la Alcaldía encabeza el DESAMU, del que dependen la Dirección CESFAM, Recursos Humanos, Administración y Finanzas, y Prevención de Riesgos. **En el nivel de establecimiento**, la Dirección CESFAM articula unidades de apoyo (entre ellas TIC y Farmacia), instancias de participación y tres ejes operativos: Unidad SOME, Coordinación General de Sector y Enfermera Coordinadora. A esto se suman programas transversales y una sectorización territorial en tres sectores (Verde, Azul y Rojo) según el modelo MAIS.

En cuanto a el tamaño del personal en 2026 es de 148 funcionarios (6.304 horas semanales) en el CESFAM y la Posta, y de 8 funcionarios (330 horas semanales) en DESAMU (DESAMU, 2025).

La población inscrita y validada por Fonasa es de 15.526 usuarios en 2025. La unidad de farmacia que es el foco del problema cuenta con 6 personas trabajando y 4 ventanillas. Después de las 14:00 una sola ventanilla hasta las 20:00.

| Capa         | Situación actual                                                                                                                                          | Con el proyecto                                                                                                                 |
|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| Negocio      | Dispensación en 4 ventanillas con dos rollos de papel (general y preferencial). Reparto a domicilio a unos 70 postrados y 600 mayores de 80 años.         | Turnos digitales con prioridades ponderadas y logística de entregas con trazabilidad.                                           |
| Datos        | Recetas y despachos en Rayén. Reportes del locker a cargo de la empresa proveedora. REM en Estadística. Direcciones de domicilio anotadas sin normalizar. | Base propia de turnos, entregas, domicilios georreferenciados y recetas simuladas.                                              |
| Aplicaciones | Rayén, software del locker, Heart View, EPIVIGILA y telesalud. Cartel numérico accionado por botón o control remoto.                                      | PWA de turnos y entregas, autónoma respecto de Rayén.                                                                           |
| Tecnología   | Internet en ambos establecimientos (no se evaluó su estabilidad), PC, router propio del locker, radiocomunicaciones.                                      | Servidor de aplicaciones y base de datos (ubicación por definir), tótem, pantalla, parlantes y dispositivos de los conductores. |

> Elaboración propia con asistencia de Claude Sonnet 5.5 Medio (Anthropic, 2026)

# IX. Conclusiones

La formulación de este proyecto permitió constatar que el problema de la Unidad de Farmacia del CESFAM San Nicolás va más allá del orden de la fila, ya que afecta la experiencia de los pacientes, el bienestar del personal y la coherencia con la misión institucional de brindar una atención inclusiva y de calidad. Además, se constató de forma directa el problema de la falta de mapeo de rutas en la comuna, sin un Chofer con conocimiento de la zona, se imposibilita reconocer las direcciones rurales. El levantamiento en terreno fue clave para dimensionarlo con datos concretos y para incorporar una segunda problemática, la logística de entregas domiciliarias en un territorio mayoritariamente rural.

Asimismo, se evidenció que la solución no pasa por medidas administrativas simples, sino por una plataforma que combine encolamiento con prioridades ponderadas, sincronización en tiempo real, operación sin conexión y una interfaz accesible para adultos mayores. Como equipo, rescatamos la importancia de diseñar pensando en las personas que usarán el sistema y de definir un alcance realista, desarrollando un prototipo con datos ficticios en su primera etapa para que pueda cumplirse en un semestre académico.

En una versión posterior se espera llegar a una implementación en conjunto con el CESFAM, donde se pueda validar a los pacientes inscritos y emitir su turno de atención. La geolocalización en tiempo real para el Conductor de despacho a domicilio, se tiene la línea base de los indicadores de éxito de esta operación, para evaluar de forma objetiva el impacto de la plataforma una vez sea implementada.

# X. Referencias bibliográficas

Anthropic. (2026b). Claude Sonnet 5.5 Alto \[Modelo de inteligencia artificial\]. <https://claude.ai>

Anthropic. (2026c). Claude Sonnet 5.5 Medio \[Modelo de inteligencia artificial\]. <https://claude.ai>

Chang, X., Dou, W., Wei, J., Huang, T., Xie, J., Deng, Y., Yang, J., & Yang, J. (2021). Race detection for event-driven Node.js applications. En 2021 36th IEEE/ACM International Conference on Automated Software Engineering (ASE) (pp. 480–491). IEEE. https://doi.org/10.1109/ASE51524.2021.9678814

Departamento de Salud Municipal de San Nicolás. (2025). Plan de salud municipal San Nicolás: Actualización 2026–2028. Ilustre Municipalidad de San Nicolás. \[Documento institucional citado en el informe; URL pública no verificada\].

Lugo, E., Villegas, H., Villegas, Á., & Pacheco, J. (2009). Lector de historias clínicas electrónicas codificadas en el estándar Health Level 7 / Clinical Document Architecture para su aplicación en servicios de telemedicina. Revista Ingeniería UC, 16(1), 1–10. \[DOI/URL no verificados\].

Mallick, S. R., Goswami, V., Lenka, R. K., & Sharma, S. (2022). Performance evaluation of queueing assisted IoMT-fog-blockchain framework for healthcare organizations. En 2022 IEEE 9th Uttar Pradesh Section International Conference on Electrical, Electronics and Computer Engineering (UPCON). IEEE. https://doi.org/10.1109/UPCON56432.2022.9986439

Moreno, L., & Martínez, P. (2012). A review of accessibility requirements in elderly users’ interactions with web applications. En Proceedings of the 13th International Conference on Interacción Persona-Ordenador. https://doi.org/10.1145/2379636.2379682

Torres López, C. A., Pachas Huaytan, J. V., Ortiz Fernandez, J. H., Navarro Veliz, J. A., & Moreno Menéndez, F. M. (2025). Gestión eficiente del flujo de clientes: Un enfoque basado en la teoría de colas en supermercados de Huancayo. e-Revista Multidisciplinaria del Saber, 3, e-RMS05072025. https://doi.org/10.61286/e-rms.v3i.192

World Wide Web Consortium. (s. f.). Older users and web accessibility: Meeting the needs of ageing web users. Web Accessibility Initiative. <https://www.w3.org/WAI/older-users/>

# XI. Anexos

Link de información de entrevistas: [entrevistas_cesfam.docx](https://inacapmailcl-my.sharepoint.com/:w:/g/personal/fernanda_daza_inacapmail_cl/IQDh-c0t1ctkSLV4gaIHw0-LAXHmUUHcM1pIEwkZt5uNRTs?e=fh7IRG)

Link Diccionario EDT: [Diccionario_EDT_CESFAM_San_Nicolas.docx](https://inacapmailcl-my.sharepoint.com/:w:/g/personal/fernanda_daza_inacapmail_cl/IQAAQcUoKPkzR6vJZjWKhy8_AWdxtwdQw7Jno95f90gapMw?e=QTWCFs)

Link EDT CESFAM: [EDT_CESFAM_SAN_NICOLAS_v2.xlsx](https://inacapmailcl-my.sharepoint.com/:x:/g/personal/isidora_rubio_inacapmail_cl/IQCHaNCwgMPtQ5hsMc5kH1SHAdMCMakPaM6sTNWqa-NEn70?e=JKUr7h)

Link archivo Microsoft Project: [Proyecto CESFAM.mpp](https://inacapmailcl-my.sharepoint.com/:u:/g/personal/isidora_rubio_inacapmail_cl/IQAzQ3EXCfBVQan7m3VwQU_7Aa04K--j28YTcJEPjhIflmY?e=7f1t9G)

Link de Carta Formal Para Permiso Municipal: [20261009014629434_261008_151741.pdf](https://inacapmailcl-my.sharepoint.com/:b:/g/personal/fernanda_daza_inacapmail_cl/IQB1YwjP5N87Q4_dcbig1pjeAc-TX1WvQsl-RO7RJiB7-IM?e=9pkBD9)

Registro de asistencia de IA:

| Fecha      | Modelo Usado                 | Prompt                                                                                                                                                                                                                                                                                                                                                                                                           | Verificación Humana |
|------------|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------|
| 09-09-2026 | Opus 5 Medio (Claude Pro)    | Actúa como asesor metodológico de mi Proyecto de Título TIHI84 (INACAP) sobre un sistema digital de turnos para la farmacia del CESFAM San Nicolás. Ayúdame a redactar y revisar el informe con lenguaje académico chileno y APA 7. No inventes información ni citas; usa solo las fuentes entregadas y marca cuando falten datos. Sé crítico, corrige inconsistencias y entrega el texto listo para pegar.      | Si                  |
| 10-09-2026 | Gemini 3.1 Pro Avanzado      | Analiza el punto "2.1   Justificación del<br>problema." del documento adjunto "Formulación-Proyecto-De-Título" e indiques de qué forma mejorar y complementar la redacción, implementando datos cuantificables y referentes la trazabilidad de ruta, tomando datos claves del resto de documentación adjunta                                                                                                     | Si                  |
| 11-09-2026 | Sonnet 5 Medio (Claude Pro)  | ¿A partir de esta transcripción de la conversación con mi profesor guía, como crees que podría mejorar las historias de usuario de mi pre-informe? Por favor genera un documento pdf                                                                                                                                                                                                                             | Si                  |
| 01-10-2026 | Sonnet 5.5 Alto (Claude Pro) | Crea una tabla de arquitectura técnica con estas tres columnas: "Capa / componente", "Descripción" y "Requisitos que resuelve".<br>Llena la tabla con las siguientes 6 filas, detallando su funcionamiento para una aplicación web PWA y los códigos de los requisitos asociados:<br>• Presentación (PWA)<br>• Lógica de negocio<br>• Tiempo real<br>• Datos<br>• Operación sin conexión<br>• Servicios externos | Si                  |
| 01-10-2026 | Sonnet 5.5 Alto (Claude Pro) | Crea una tabla comparativa que contraste el estado actual con el estado propuesto para el proyecto, utilizando exactamente estas tres columnas: "Capa", "Situación actual" y "Con el proyecto".<br>Llena la tabla con las siguientes 4 filas, detallando cómo se manejan los turnos, recetas y entregas en cada escenario:<br>• Negocio<br>• Datos<br>• Aplicaciones<br>• Tecnología                             | Si                  |
| 03-10-2026 | Gemini 3.1 Pro Avanzado      | “En base a la documentación adjunta, junto con la información del mismo documento, Genera el ejemplo de cómo debería elaborar una Matriz RACI según se indica en las instrucciones. No alusiones, ni la hagas tu.”                                                                                                                                                                                               | Si                  |
