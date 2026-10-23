# Feature Specification: Revisión de consultas en lenguaje natural

**Feature Branch**: `002-revision-consultas-naturales`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Quiero ver una lista de TODOS los artículos con el código, la descripción y la familia. Sigue sin entender y solo ha devuelto unos pocos. Quiero una revisión del proceso de consultas en lenguaje natural, paso a paso, y un test final para resolver el 100% de las preguntas con el contexto actual."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver todos los artículos con las columnas pedidas (Priority: P1)

Un usuario de la empresa pide la lista de todos los artículos con el código, la descripción y la familia. La respuesta trae un artículo por cada artículo guardado de esa empresa, con esas tres columnas, y dice cuántos son. No devuelve una muestra ni omite la familia.

**Why this priority**: Es la pregunta que hoy falla. El usuario pide el conjunto completo y una columna que ya está en los datos mapeados, y recibe solo unos pocos artículos sin esa columna.

**Independent Test**: Con la empresa activa y sus artículos ya cargados, preguntar «quiero ver una lista de todos los artículos con el código, la descripción y la familia». Contar las filas de la respuesta y compararlas con el número de artículos de esa empresa. Comprobar que cada fila muestra código, descripción y familia.

**Acceptance Scenarios**:

1. **Given** una empresa con sus artículos cargados y la familia guardada en esos artículos, **When** el usuario pide todos los artículos con código, descripción y familia, **Then** la respuesta incluye un registro por artículo, las tres columnas, y el número de registros coincide con el de artículos de esa empresa.
2. **Given** la misma empresa, **When** el usuario usa «todos», «todas», «completo» o «listado completo», **Then** la respuesta no se queda en una muestra.
3. **Given** la misma empresa, **When** el usuario pide solo los 10 primeros artículos con código y descripción, **Then** la respuesta trae 10 registros y no el catálogo entero.
4. **Given** un artículo cuyo código conserva ceros a la izquierda, **When** aparece en el listado, **Then** el código se muestra tal como está guardado.

---

### User Story 2 - Leer cualquier pregunta del contexto mapeado por un solo camino (Priority: P2)

El usuario hace una pregunta en español sobre los datos que ya están mapeados. El sistema la lee en un solo recorrido, de la frase al dato guardado, y contesta con la cifra, el listado, la agrupación o la gráfica que corresponde. No sustituye la pregunta por otro ranking ni por una muestra.

El recorrido, en este orden, es el contrato de la revisión:

1. La pregunta se entiende contra los datos mapeados de la empresa activa.
2. Si nombra columnas, filtros, varios filtros, una agrupación, una suma, un recuento, un promedio, un máximo, un mínimo, un listado o una comparación de periodos ya guardados, se prepara una sola lectura.
3. Se aplican la empresa activa y el ejercicio elegido, salvo que la pregunta nombre otro ejercicio, varios ejercicios, o un listado de fichas que no depende del año.
4. La respuesta muestra el dato guardado: una cifra, el listado completo de las columnas pedidas, una tabla agrupada o una gráfica.
5. Si la pregunta nombra un dato que no está mapeado, la respuesta es exactamente «Esa pregunta no está en los datos mapeados.» y no muestra otra cifra en su lugar.
6. El examen final recorre las preguntas que este contexto puede contestar y cada una coincide con el dato guardado.

**Why this priority**: El listado de artículos es un caso de un fallo más amplio. La revisión tiene que dejar un solo modo de leer las preguntas, para que el mismo fallo no vuelva con otra frase.

**Independent Test**: Hacer, una detrás de otra, una pregunta de cada tipo que el contexto actual admite (listado completo, total de un producto, recuento, agrupación, comparativa de dos ejercicios y clientes que han comprado un producto). Cada respuesta coincide con el dato guardado y ninguna cae en un atajo distinto.

**Acceptance Scenarios**:

1. **Given** ventas del ejercicio ya guardadas, **When** el usuario pregunta las ventas del ejercicio, **Then** la cifra es la de los albaranes de cliente de ese ejercicio.
2. **Given** un producto con ventas, **When** el usuario pregunta qué clientes lo han comprado, **Then** la respuesta agrupa clientes de los albaranes de cliente y no lo trata como una compra a proveedor ni como un pedido.
3. **Given** dos ejercicios guardados, **When** el usuario pide la gráfica comparativa de ventas de un año frente al otro, **Then** la respuesta compara esos dos ejercicios por mes.
4. **Given** una pregunta que no habla de datos mapeados, **When** el usuario la hace, **Then** no se responde con una cifra de artículos o de ventas presentada como si fuera esa pregunta.
5. **Given** una pregunta que nombra un dato concreto que no está mapeado, **When** el usuario la hace, **Then** la respuesta es «Esa pregunta no está en los datos mapeados.»

---

### User Story 3 - Cerrar la revisión con un examen del contexto actual (Priority: P3)

El usuario abre la pestaña Examen y ve las preguntas preparadas para la empresa y el ejercicio activos, con el resultado esperado al lado. Al lanzar el examen, cada pregunta se contesta y se marca si coincide con el dato guardado. La revisión solo se da por buena cuando todas coinciden.

**Why this priority**: El usuario pide un test final para saber que el cien por cien de las preguntas del contexto actual queda resuelto, no solo el listado de artículos.

**Independent Test**: Abrir Examen con la empresa y el ejercicio activos, comprobar que la lista incluye el listado completo de artículos con familia, lanzar el examen y verificar que cada veredicto es coincidencia con el dato guardado.

**Acceptance Scenarios**:

1. **Given** la empresa y el ejercicio elegidos, **When** el usuario abre Examen, **Then** ve las preguntas y el resultado esperado sin necesidad de lanzarlas.
2. **Given** esas preguntas, **When** lanza el examen, **Then** cada una muestra la respuesta y un veredicto, y el resumen queda en el cien por cien de coincidencias.
3. **Given** el examen, **When** se revisa su contenido, **Then** incluye el listado de todos los artículos con código, descripción y familia, además de totales, recuentos, agrupaciones, comparativas de ejercicios y cruces ya posibles con las relaciones mapeadas.
4. **Given** una pregunta del examen que ya coincidía antes de la revisión, **When** se vuelve a lanzar, **Then** sigue coincidiendo.

---

### Edge Cases

- La empresa tiene más artículos de los que hoy caben en una muestra. «Todos» sigue significando el catálogo entero.
- El usuario pide columnas que existen y, en la misma frase, una columna que no está mapeada. La respuesta no finge el listado: dice que esa pregunta no está en los datos mapeados.
- El usuario pide un listado de clientes o de proveedores con columnas que sí están mapeadas. Se aplica la misma regla que en artículos: todos los registros y solo las columnas pedidas.
- La familia guardada en el artículo es un código. La respuesta muestra ese valor. No inventa el nombre de una familia que no esté en los datos mapeados.
- La empresa no tiene artículos. La respuesta dice que no hay registros y el recuento es cero.
- La pregunta pide un pedido. La lectura usa pedidos. Si no lo dice, usa albaranes.
- «Han comprado» referido a clientes es una venta, no una compra a proveedor.
- Una pregunta de motivo, previsión o tabla no mapeada no entra en el cien por cien. Su respuesta correcta es no inventar la cifra.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema debe responder a la petición de todos los artículos con código, descripción y familia con un registro por cada artículo de la empresa activa y con esas tres columnas.
- **FR-002**: El número de registros anunciado en un listado completo debe coincidir con el número de fichas guardadas de esa empresa.
- **FR-003**: «Todos», «todas», «completo», «completa» y «listado completo» deben significar el conjunto entero, no una muestra.
- **FR-004**: Si el usuario pide un número concreto de registros, la respuesta debe respetar ese número.
- **FR-005**: La misma regla de listado completo y columnas pedidas debe aplicarse a clientes y a proveedores cuando las columnas nombradas estén mapeadas.
- **FR-006**: Cada pregunta sobre datos mapeados debe resolverse en un solo recorrido: qué se pide, qué columnas, qué filtros, qué agrupación y qué empresa y ejercicio.
- **FR-007**: Ese recorrido debe poder filtrar, combinar varios filtros, agrupar, sumar, contar, promediar, obtener máximo y mínimo, listar y comparar periodos ya guardados, usando las relaciones ya definidas.
- **FR-008**: La empresa activa y el ejercicio elegido deben aplicarse siempre, salvo que la pregunta nombre otro ejercicio, varios ejercicios, o un listado de fichas que no depende del año.
- **FR-009**: Si la pregunta nombra un dato que no está mapeado, la respuesta debe ser exactamente «Esa pregunta no está en los datos mapeados.» y no debe mostrar otra cifra en su lugar.
- **FR-010**: Una venta a clientes debe leer albaranes de cliente, salvo que la pregunta diga pedido. Una compra debe leer documentos de proveedor. «Han comprado» con clientes es una venta.
- **FR-011**: El examen final debe cubrir todas las formas de lectura que el contexto mapeado actual admite, incluido el listado de todos los artículos con código, descripción y familia.
- **FR-012**: El examen debe mostrar cada pregunta, el resultado esperado según el dato guardado y el veredicto. La revisión solo está aceptada cuando todas las preguntas coinciden.
- **FR-013**: Las preguntas del examen deben verse al abrir la pestaña, antes de lanzarlas.
- **FR-014**: Una pregunta del examen que ya coincidía con el dato guardado debe seguir coincidiendo después de la revisión.
- **FR-015**: En un listado completo el usuario debe poder llegar a ver cada fila, y la respuesta debe decir cuántas son.

### Key Entities *(include if feature involves data)*

- **Pregunta**: Frase en español del usuario, ligada a la empresa y al ejercicio que tiene elegidos.
- **Dato mapeado**: Columna ya reconocida de artículos, clientes, proveedores, documentos de venta, documentos de compra o cartera. La familia del artículo es uno de esos datos.
- **Lectura**: Resultado de una pregunta: una cifra, un listado de columnas, una tabla agrupada o una gráfica de periodos.
- **Examen**: Conjunto de preguntas del contexto actual, cada una con el resultado que debe salir del dato guardado y con un veredicto de coincidencia.
- **Empresa y ejercicio**: Ámbito de la pregunta. El listado de fichas maestras pertenece a la empresa y no se recorta por el ejercicio.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Al pedir todos los artículos con código, descripción y familia, el 100% de los artículos de la empresa aparece en la respuesta y el recuento anunciado es igual al número de artículos guardados.
- **SC-002**: El examen final de la empresa y el ejercicio activos termina con el 100% de las preguntas coincidiendo con el dato guardado.
- **SC-003**: Ese examen incluye, como mínimo, el listado completo de artículos, un total filtrado por producto, un recuento, una agrupación, una comparativa de dos ejercicios y un cruce de clientes con un producto. Las seis coinciden con el dato guardado.
- **SC-004**: En un conjunto de preguntas ajenas a los datos mapeados, el 100% recibe la negativa fija y ninguna muestra una cifra de ventas o de artículos como si respondiera a esa pregunta.
- **SC-005**: Con una empresa de hasta 2.000 artículos, el usuario ve el listado completo, o puede recorrer todas sus filas, antes de 15 segundos desde que envía la pregunta.

## Assumptions

- «Contexto actual» son las tablas y columnas que ya están mapeadas y cargadas para la empresa activa. Esta revisión no incorpora tablas nuevas.
- El cien por cien se mide sobre el examen de las lecturas que ese contexto puede contestar. Motivos, previsiones y datos no mapeados quedan fuera y su respuesta correcta es la negativa fija.
- «Todos» significa cada ficha de la empresa activa. Una muestra, aunque sea amplia, no cumple.
- La familia que se muestra es el valor guardado en el artículo. Si ese valor es un código, se muestra el código. El nombre de una familia que viva en una tabla no mapeada queda fuera.
- La empresa y el ejercicio salen de los selectores que el usuario ya tiene en pantalla.
- El examen se consulta en la pestaña Examen, que ya enseña la pregunta, lo esperado y el veredicto.
- Si el usuario no dice «pedido», el documento de una venta o una compra es el albarán.
- Las relaciones que ya están definidas entre documentos, clientes, proveedores y artículos se mantienen. No se inventan cruces nuevos.
- El listado de artículos, clientes o proveedores no se filtra por el ejercicio, porque la ficha no es un movimiento del año.
