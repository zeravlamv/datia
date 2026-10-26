# Feature Specification: Análisis de la búsqueda en lenguaje natural

**Feature Branch**: `003-analisis-busqueda-natural`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Analiza el sistema de búsqueda con lenguaje natural. No te centres en un caso concreto. Quiero una revisión exhaustiva para validar el sistema para cualquier pregunta. El sistema debe tener memoria: la pregunta siguiente puede ir relacionada con la anterior o no."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clasificar cualquier pregunta (Priority: P1)

Cualquier frase en español que se envía al chat queda clasificada. O bien nombra datos ya mapeados y entonces se sabe qué lectura le corresponde, o bien no puede leerse con esos datos y se rechaza. No hay una tercera salida en la que la frase se conteste con el dato de otra pregunta.

La lectura, cuando existe, dice sin ambigüedad qué se pide: una cifra, un listado, una agrupación o una comparación; qué conceptos mapeados intervienen; qué filtros lleva; si el corte es el conjunto entero o un número dicho en la frase; y qué empresa y qué periodo aplican.

**Why this priority**: Validar el sistema para cualquier pregunta exige primero que ninguna frase quede sin sitio. Un acierto en una frase suelta no dice nada de la siguiente.

**Independent Test**: Formular un conjunto de frases que cubra lecturas posibles, frases ajenas a los datos y frases que nombran un dato concreto no mapeado. Cada frase queda en una sola clase. Ninguna frase de una clase recibe la respuesta de otra.

**Acceptance Scenarios**:

1. **Given** cualquier pregunta sobre datos mapeados, **When** el sistema la clasifica, **Then** indica la lectura que le corresponde y no la sustituye por otra.
2. **Given** una pregunta que no habla de datos mapeados, **When** el usuario la hace, **Then** no recibe una cifra ni un listado de la empresa presentados como si respondieran a esa frase.
3. **Given** una pregunta que nombra un dato concreto que no está mapeado, **When** el usuario la hace, **Then** la respuesta es exactamente «Esa pregunta no está en los datos mapeados.»
4. **Given** dos frases que piden lecturas distintas, **When** se contestan, **Then** cada una conserva sus columnas, sus filtros, su corte y su periodo.

---

### User Story 2 - Revisar todas las lecturas que el contexto permite (Priority: P2)

La revisión no se arma con unas frases elegidas de antemano. Se arma a partir de lo que hoy está mapeado para la empresa activa, de modo que no quede fuera ninguna columna legible, ninguna relación ya definida ni ninguna forma de lectura admitida.

Las formas de lectura son: filtrar, combinar varios filtros, agrupar, sumar, contar, promediar, obtener el máximo, obtener el mínimo, listar las columnas pedidas, pedir el conjunto entero, pedir un número concreto de filas, leer un periodo, comparar periodos ya guardados y mostrar el resultado como tabla o como gráfica. Cada forma se cruza con los conceptos mapeados que de verdad pueden sostenerla y con las relaciones que ya unen esos conceptos.

Cada pregunta de esa revisión se contesta y el resultado coincide con el dato guardado. Si una columna, una relación o una forma de lectura no tiene ninguna pregunta, la revisión está incompleta aunque las preguntas que sí están coincidan.

**Why this priority**: Una revisión exhaustiva se mide por el territorio que cubre, no por un ejemplo que haya fallado antes.

**Independent Test**: Con la empresa activa, generar la revisión desde los datos mapeados y comprobar tres cosas: que cada columna legible aparece en alguna pregunta, que cada relación usable aparece en algún cruce, y que cada forma de lectura admitida aparece al menos una vez. Lanzar la revisión y comparar cada respuesta con el dato guardado.

**Acceptance Scenarios**:

1. **Given** el mapa actual de la empresa, **When** se prepara la revisión, **Then** toda columna legible, toda relación usable y toda forma de lectura admitida tienen al menos una pregunta.
2. **Given** esa revisión, **When** se lanza, **Then** cada respuesta coincide con el dato guardado de la empresa y el periodo que la pregunta usa.
3. **Given** una pregunta que pide el conjunto entero de una ficha maestra, **When** se responde, **Then** el recuento es el de todas las fichas de la empresa y se puede llegar hasta la última fila.
4. **Given** una pregunta que dice un número de filas, **When** se responde, **Then** llegan esas filas y no el conjunto entero.
5. **Given** una pregunta de movimientos, **When** no nombra otro periodo, **Then** usa el ejercicio elegido. **Given** una pregunta de fichas maestras, **When** no habla de un año, **Then** no se recorta por el ejercicio.
6. **Given** una pregunta que no dice pedido, **When** lee una venta o una compra, **Then** usa el albarán. Si dice pedido, usa el pedido. «Han comprado» referido a clientes es una venta, no una compra a proveedor.

---

### User Story 3 - Ver si cualquier pregunta queda validada (Priority: P3)

Quien revisa abre el conjunto antes de lanzarlo y ve cada pregunta con el resultado esperado. Al lanzarlo, cada pregunta recibe un veredicto. La validación solo se acepta cuando ocurre todo esto a la vez: el conjunto cubre el territorio mapeado, todas sus preguntas coinciden con el dato guardado, y las frases de fuera reciben la negativa fija. Una frase que ya coincidía no deja de coincidir al ampliar la revisión.

**Why this priority**: El resultado tiene que poder mirarse entero. Si solo se enseña un puñado de aciertos, no se ha validado el sistema.

**Independent Test**: Abrir la revisión de la empresa y el ejercicio activos, contar si falta alguna columna, relación o forma de lectura, lanzarla y comprobar que no queda ninguna pregunta sin veredicto ni ninguna coincidencia perdida respecto de la pasada anterior.

**Acceptance Scenarios**:

1. **Given** la empresa y el ejercicio elegidos, **When** se abre la revisión, **Then** se ven todas las preguntas y lo esperado, antes de lanzarlas.
2. **Given** la revisión lanzada, **When** termina, **Then** cada pregunta del conjunto coincide con el dato guardado y cada frase de fuera queda rechazada.
3. **Given** una pregunta que coincidió en una revisión anterior, **When** se vuelve a incluir, **Then** sigue coincidiendo.
4. **Given** el resumen final, **When** se lee, **Then** dice cuántas preguntas cubren el territorio mapeado, cuántas coinciden y cuántas frases de fuera fueron rechazadas.

---

### User Story 4 - Recordar la pregunta anterior sin forzar el vínculo (Priority: P2)

El chat recuerda la última lectura aceptada de la misma conversación y de la misma empresa. La pregunta siguiente puede continuar esa lectura o ser una pregunta distinta. Si la frase se entiende sola, es una pregunta nueva y no hereda filtros, columnas, concepto, corte ni periodo. Si no se entiende sola y sí se entiende al completar lo que falta con la lectura anterior, es una continuación: conserva lo que no repite y sustituye lo que vuelve a decir. Si no se entiende de ninguna de las dos maneras, se rechaza.

**Why this priority**: Las preguntas llegan una detrás de otra. Tratarlas siempre como sueltas rompe el diálogo. Tratarlas siempre como continuación contamina la siguiente con la anterior.

**Independent Test**: Aceptar una lectura. Enviar después una frase incompleta que solo cambia el periodo, la agrupación, el corte o una columna, y comprobar que el resto se conserva. Enviar entonces una frase que se entiende sola y comprobar que no conserva nada de la lectura anterior.

**Acceptance Scenarios**:

1. **Given** una lectura ya aceptada en la conversación, **When** la frase siguiente no se entiende sola y sí al completarla con esa lectura, **Then** la respuesta conserva lo no dicho y sustituye lo que la frase nueva dice.
2. **Given** una lectura ya aceptada, **When** la frase siguiente se entiende sola sobre los datos mapeados, **Then** no hereda filtros, columnas, concepto, corte ni periodo de la anterior.
3. **Given** una frase que no se entiende sola ni como continuación, **When** el usuario la envía, **Then** recibe la negativa fija y la memoria no pasa a ser esa frase rechazada.
4. **Given** un cambio de empresa o una conversación nueva, **When** llega la siguiente pregunta, **Then** no usa la memoria de la empresa o de la conversación anterior.
5. **Given** varias lecturas aceptadas en la misma conversación, **When** una continuación no dice a cuál se refiere, **Then** usa solo la última aceptada.

---

### Edge Cases

- La frase puede leerse de dos maneras con los datos mapeados. Hay dos lecturas cuando, aplicadas las reglas ya cerradas (sin «pedido» es albarán, y «han comprado» con clientes es una venta), siguen encajando dos conceptos mapeados o dos relaciones usables y la frase no nombra cuál. Si nombra uno, ese es el que vale. Si siguen las dos, la respuesta es exactamente «Esa pregunta admite más de una lectura. Indica cuál quieres.» No se ejecuta ninguna de las dos y no se mezclan las cifras. Ese aviso no sustituye a la última lectura aceptada.
- La frase pide columnas que existen y, en la misma frase, una columna que no está mapeada. No se finge la lectura. La respuesta es la negativa fija.
- La frase siguiente nombra un dato concreto que no está mapeado. Aunque haya una lectura aceptada, no se rellenan huecos. La respuesta es la negativa fija y la memoria sigue en la última aceptada.
- La frase pide el conjunto entero y la pantalla anuncia el recuento real, pero no deja llegar a la última fila. Cuenta como no coincidencia.
- La frase pide un número y la respuesta trae otro corte, más corto o más largo. Cuenta como no coincidencia.
- Una ficha maestra no tiene registros. La respuesta dice que no hay registros y el recuento es cero. Eso coincide.
- El valor pedido es un código guardado, aunque sea el de una familia o un identificador con ceros a la izquierda. Se muestra ese valor. No se inventa un nombre que viva fuera de los datos mapeados.
- Una palabra de ranking, como «mejores» o «top», sin pedir el conjunto entero, sigue siendo un ranking. Si la frase pide el conjunto entero, no se sustituye por ese ranking.
- Motivos, previsiones y tablas no mapeadas no se convierten en una clase pendiente de acertar. Su resultado correcto es la negativa, y la revisión debe incluir probes de ese tipo para comprobarlo.
- La empresa activa no tiene cargado alguno de los datos mapeados. La revisión lo señala como sin dato, no como una cifra de otra empresa.
- La frase siguiente se entiende sola y, además, podría leerse como continuación. Prevalece la lectura sola. No se arrastra el contexto.
- No hay ninguna lectura aceptada todavía. Una frase incompleta no tiene de dónde completarse y se rechaza.
- La continuación cambia solo una parte: el periodo, la agrupación, el corte o una columna. El resto de la última lectura aceptada se mantiene. Lo que la frase nueva dice reemplaza a lo anterior, no se suma en conflicto.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Cualquier pregunta debe terminar en una de estas dos salidas: una lectura de datos mapeados, o la negativa. No debe existir una salida que conteste con el dato de otra pregunta.
- **FR-002**: La negativa, cuando la frase nombra un dato concreto que no está mapeado, debe ser exactamente «Esa pregunta no está en los datos mapeados.»
- **FR-003**: Una frase que no habla de datos mapeados no debe recibir una cifra ni un listado de la empresa como si fueran la respuesta.
- **FR-004**: La revisión debe construirse desde el territorio mapeado de la empresa activa, no desde una lista fija de ejemplos.
- **FR-005**: El territorio de la revisión debe incluir cada columna legible, cada relación ya definida que una pregunta pueda usar, y cada forma de lectura admitida: filtrar, varios filtros, agrupar, sumar, contar, promediar, máximo, mínimo, listar, conjunto entero, número concreto de filas, un periodo, comparación de periodos guardados, tabla y gráfica.
- **FR-006**: Si falta una columna legible, una relación usable o una forma de lectura, la revisión debe declararse incompleta aunque el resto coincida.
- **FR-007**: Cada pregunta de la revisión debe guardar el resultado esperado según el dato almacenado y, al ejecutarse, coincidir con ese resultado.
- **FR-008**: La empresa activa debe acotar toda lectura. El ejercicio elegido debe acotar los movimientos, salvo que la frase nombre otro periodo o varios. El listado de fichas maestras no debe filtrarse por el ejercicio.
- **FR-009**: Una venta a clientes debe leer albaranes de cliente, salvo que la frase diga pedido. Una compra debe leer documentos de proveedor. «Han comprado» con clientes es una venta.
- **FR-010**: Las columnas que la frase pide y que están mapeadas deben mostrarse, con un título comprensible, y un código guardado debe verse tal como está guardado.
- **FR-011**: En un conjunto entero, el recuento anunciado debe ser el número real de fichas y quien pregunta debe poder llegar a la última fila. Un número dicho en la frase debe respetarse.
- **FR-012**: La revisión debe verse entera antes de lanzarla, con la pregunta y el resultado esperado.
- **FR-013**: Al terminar, el resumen debe decir cuántas preguntas cubren el territorio, cuántas coinciden y cuántas frases de fuera fueron rechazadas. Solo se acepta si el territorio está completo, todas las preguntas coinciden y todas las frases de fuera quedan rechazadas.
- **FR-014**: Una pregunta que ya coincidía debe seguir coincidiendo al repetir o ampliar la revisión.
- **FR-015**: Hay dos lecturas cuando, aplicadas las reglas ya cerradas (sin «pedido» es albarán, y «han comprado» con clientes es una venta), siguen encajando dos conceptos mapeados o dos relaciones usables y la frase no nombra cuál. Si nombra uno, ese es el que vale. Si siguen las dos, la respuesta es exactamente «Esa pregunta admite más de una lectura. Indica cuál quieres.» No se ejecuta ninguna y no se mezclan las cifras. Ese aviso no sustituye a la última lectura aceptada.
- **FR-016**: El análisis del recorrido debe poder aplicarse a cualquier pregunta, no a un caso elegido: para esa frase, qué clase tuvo, si fue sustituida, recortada o rechazada, y qué quedó visible.
- **FR-017**: El sistema debe recordar la última lectura aceptada de la conversación y de la empresa activas. `/qa` devuelve esa lectura en la respuesta. La conversación se crea o se reutiliza al guardar el mensaje, y es ese guardado el que escribe `lectura_aceptada` en la misma fila. La pregunta siguiente envía el id de esa fila.
- **FR-018**: Si la pregunta siguiente se entiende sola, debe tratarse como pregunta nueva y no debe heredar filtros, columnas, concepto, corte ni periodo.
- **FR-019**: Si la pregunta siguiente no se entiende sola y sí al completarla con la última lectura aceptada, debe conservar lo no dicho y sustituir lo que la frase nueva dice.
- **FR-020**: Si no se entiende sola ni como continuación, debe recibir la negativa fija. Una frase rechazada no sustituye a la última lectura aceptada en la memoria. Si la frase nombra un dato concreto que no está mapeado, la respuesta es la negativa fija y no se rellenan huecos con la lectura anterior.
- **FR-021**: Cambiar de empresa o abrir una conversación nueva debe dejar la memoria anterior fuera de uso. Si hay varias lecturas aceptadas, una continuación usa solo la última.
- **FR-022**: La revisión exhaustiva debe incluir parejas de preguntas: una continuación que cambia una sola parte de la lectura, y una pregunta posterior que se entiende sola y no hereda nada. Ambas deben coincidir con el dato guardado que les corresponde.

### Key Entities *(include if feature involves data)*

- **Pregunta**: Cualquier frase en español enviada con la empresa y el ejercicio elegidos.
- **Clase de lectura**: Lo que la frase pide sobre datos mapeados: cifra, listado, agrupación o comparación, con sus filtros, su corte y su periodo. Una frase tiene una sola clase, o ninguna.
- **Territorio mapeado**: Columnas legibles, relaciones ya definidas y formas de lectura que la empresa activa puede sostener hoy.
- **Revisión**: Conjunto de preguntas generado desde ese territorio, más probes de frases que deben rechazarse. Cada pregunta lleva el resultado esperado y, tras lanzarla, un veredicto.
- **Respuesta visible**: Cifra, tabla o gráfica que queda en el chat, o la negativa fija. En un listado, incluye columnas, recuento y la posibilidad de llegar a la última fila.
- **Memoria**: Última lectura aceptada de una conversación y una empresa. Una continuación la completa. Una pregunta que se entiende sola no la usa. Una negativa no la borra ni la reemplaza.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las preguntas enviadas termina en una lectura de datos mapeados o en una negativa. El 0% recibe el dato de otra pregunta.
- **SC-002**: La revisión cubre el 100% de las columnas legibles, el 100% de las relaciones usables y el 100% de las formas de lectura admitidas. Si falta una, no se acepta.
- **SC-003**: El 100% de las preguntas de la revisión coincide con el dato guardado de su empresa y su periodo.
- **SC-004**: El 100% de las frases de fuera queda rechazado. Cuando la frase nombra un dato concreto no mapeado, el texto es la negativa fija.
- **SC-005**: Antes de lanzar la revisión, una persona ve el conjunto completo y puede comprobar que no es una selección de ejemplos.
- **SC-006**: Al repetir la revisión, el 100% de las preguntas que ya coincidían sigue coincidiendo.
- **SC-007**: Cualquier respuesta de una sola pregunta, incluido un listado del conjunto entero, puede empezar a leerse antes de 15 segundos desde que se envía, para un territorio de hasta 6.000 fichas en la ficha maestra más grande.
- **SC-008**: En el 100% de las parejas de la revisión, la continuación conserva solo lo no dicho y la pregunta que se entiende sola no hereda nada de la anterior.

## Assumptions

- «Cualquier pregunta» significa toda frase que un usuario puede enviar: las que los datos mapeados pueden leer y las que no. No significa inventar motivos, previsiones ni lecturas de tablas que no están mapeadas. Esas frases se validan comprobando que se rechazan.
- El territorio es el de la empresa activa en el momento de la revisión. No se añaden columnas ni relaciones para que la revisión quede más grande.
- La revisión se considera exhaustiva solo si sale de ese territorio. Un puñado de frases, aunque coincidan, no valida el sistema.
- Los nombres que se muestran son los que están guardados. Si un concepto de negocio no tiene columna mapeada, no se rellena con otra columna parecida.
- La empresa y el ejercicio son los que el usuario tiene elegidos.
- Si la frase no dice «pedido», el documento de una venta o de una compra es el albarán.
- La revisión se consulta donde ya se comprueban las preguntas, se ve antes de lanzarla y deja un veredicto por frase.
- Una coincidencia anterior se conserva. Ampliar la revisión no autoriza a perder lecturas que ya eran correctas.
- El recorrido de una pregunta se explica en lenguaje de negocio, de forma que sirva para cualquier frase y no solo para un ejemplo.
- La memoria es de la conversación y de la empresa, no un recuerdo global de todo lo preguntado en el pasado. Si la frase se entiende sola, manda esa frase. La continuación solo existe cuando, sin la lectura anterior, la frase no tendría una lectura.
- Una frase rechazada no cuenta como lectura aceptada. La memoria sigue en la última que sí se aceptó, o queda vacía si todavía no hay ninguna.
