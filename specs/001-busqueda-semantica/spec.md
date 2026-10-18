# Feature Specification: Búsqueda semántica del negocio

**Feature Branch**: `001-busqueda-semantica`

**Created**: 2026-10-18

**Status**: Draft

**Input**: User description: "111 — confirmar la mejora de búsqueda por significado: entender preguntas en español sobre clientes, artículos y cuentas, devolver las cifras reales de la empresa y rehacer el índice de significados al cambiar el modo de entender el lenguaje."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Encontrar a quién o a qué se refiere la pregunta (Priority: P1)

Un directivo escribe una pregunta en español con el nombre aproximado de un cliente, un artículo o una cuenta. El sistema reconoce a quién o a qué se refiere, aunque la frase no sea exacta ni esté libre de erratas, y responde con la cifra real de esa empresa y ese ejercicio.

**Why this priority**: Hoy las cifras fiables solo salen cuando la pregunta encaja en una regla conocida. El valor de esta mejora es entender el lenguaje del negocio sin inventar importes.

**Independent Test**: Con una empresa y un ejercicio ya cargados, preguntar por un cliente, un artículo y una cuenta usando una frase parecida al nombre real. La respuesta nombra la entidad correcta y muestra una cifra que coincide con el dato ya conocido de esa empresa.

**Acceptance Scenarios**:

1. **Given** un cliente existente en la empresa activa, **When** el usuario pregunta las ventas con una frase cercana al nombre, **Then** la respuesta identifica a ese cliente y muestra sus ventas del ejercicio.
2. **Given** un artículo existente, **When** el usuario pregunta el stock con una descripción parecida, **Then** la respuesta identifica el artículo y muestra el stock del ejercicio.
3. **Given** varios nombres parecidos, **When** la pregunta no distingue uno solo, **Then** el sistema pide que el usuario elija y no mezcla las cifras.

---

### User Story 2 - Conservar las respuestas que ya son fiables (Priority: P2)

Las preguntas que ya tienen una respuesta comprobada (ventas a un cliente nombrado, stock de un código, rankings del año, análisis del ejercicio) siguen respondiendo igual después de activar la búsqueda por significado.

**Why this priority**: La mejora no puede empeorar lo que el directivo ya usa cada día.

**Independent Test**: Repetir un conjunto fijo de preguntas que hoy responden bien, antes y después del cambio, y comparar que la cifra y la entidad no cambian.

**Acceptance Scenarios**:

1. **Given** una pregunta de ventas, stock o ranking que ya responde bien, **When** se vuelve a hacer tras activar la búsqueda por significado, **Then** la cifra y la entidad coinciden con la respuesta anterior.
2. **Given** una pregunta que solo pide un importe o un ranking, **When** el sistema responde, **Then** el importe sale del dato de la empresa y no de un texto generado.

---

### User Story 3 - Rehacer el índice al cambiar el modo de entender (Priority: P3)

Cuando se cambia el modo con el que el sistema entiende el lenguaje, las coincidencias antiguas dejan de usarse y el índice de significados se reconstruye con el modo nuevo antes de volver a responder.

**Why this priority**: Mezclar coincidencias de dos modos distintos haría que una pregunta encontrara al cliente o al artículo equivocado.

**Independent Test**: Cambiar el modo de entender, comprobar que una pregunta hecha durante la reconstrucción no usa el índice viejo, y que al terminar la misma pregunta encuentra la entidad correcta.

**Acceptance Scenarios**:

1. **Given** un índice construido con el modo anterior, **When** se activa el modo nuevo, **Then** las respuestas por significado quedan en espera hasta que el índice nuevo esté listo.
2. **Given** el índice nuevo terminado, **When** el usuario repite una pregunta de cliente o artículo, **Then** la coincidencia corresponde al modo nuevo.

---

### Edge Cases

- La empresa o el ejercicio no están elegidos: el sistema pide elegirlos y no responde con cifras de otra empresa.
- El nombre no existe en el catálogo de esa empresa: el sistema lo dice y no inventa una cifra.
- Hay varios candidatos igual de próximos: el sistema muestra las opciones y espera la elección.
- El índice de significados aún no está listo o falla al construirse: las preguntas con regla fija siguen respondiendo; las que dependen del significado explican que esa búsqueda no está disponible.
- La pregunta mezcla una errata y un código de artículo: el código se conserva tal cual y solo se corrige el lenguaje.
- Dos usuarios de empresas distintas preguntan a la vez: cada uno solo ve entidades y cifras de su empresa.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST entender preguntas en español sobre clientes, artículos y cuentas de la empresa activa, aunque el nombre no sea exacto.
- **FR-002**: El sistema MUST responder con la cifra ya calculada para esa empresa y ese ejercicio, identificando la entidad encontrada.
- **FR-003**: El sistema MUST pedir una elección cuando haya más de una entidad posible y MUST NOT mezclar sus cifras.
- **FR-004**: El sistema MUST decir que no encuentra la entidad cuando no hay una coincidencia suficiente, sin inventar un importe.
- **FR-005**: El sistema MUST conservar el resultado de las preguntas de ventas, stock, ranking y análisis de ejercicio que ya responden de forma comprobada.
- **FR-006**: El sistema MUST limitar cada respuesta a la empresa y al ejercicio elegidos por el usuario.
- **FR-007**: El sistema MUST reconstruir el índice de significados cuando cambie el modo de entender el lenguaje, y MUST NOT usar el índice anterior para nuevas respuestas.
- **FR-008**: Mientras el índice se reconstruye, el sistema MUST seguir contestando las preguntas con regla fija y MUST avisar de que la búsqueda por significado no está lista.
- **FR-009**: El sistema MUST conservar los códigos y los nombres propios que no deban corregirse, y solo ajustar el lenguaje de la pregunta.
- **FR-010**: El entendimiento del lenguaje MUST hacerse en el entorno de la empresa, sin enviar las preguntas ni los nombres a un servicio externo.

### Key Entities

- **Entidad de negocio**: Cliente, artículo o cuenta que el usuario nombra. Tiene un identificador estable y un texto por el que se puede reconocer.
- **Cifra de empresa**: Importe, unidades o ranking ya calculados para una empresa y un ejercicio. La búsqueda elige la entidad; la cifra no se redacta de nuevo.
- **Índice de significados**: Relación entre el lenguaje de las preguntas y las entidades de una empresa. Queda invalidado al cambiar el modo de entender.
- **Pregunta con regla fija**: Consulta de ventas, stock, ranking o análisis de ejercicio cuya respuesta ya está comprobada y no depende del índice nuevo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En una prueba de 30 preguntas con nombres aproximados de clientes, artículos y cuentas existentes, al menos el 90 % identifica la entidad correcta a la primera.
- **SC-002**: El 100 % de las cifras mostradas en esa prueba coincide con el dato ya conocido de la empresa y el ejercicio, sin importes inventados.
- **SC-003**: Una pregunta con regla fija que hoy responde bien sigue dando la misma cifra después del cambio, en una muestra de al menos 10 preguntas.
- **SC-004**: Cuando hay ambigüedad, el usuario ve opciones y elige en un solo paso, sin recibir una cifra mezclada.
- **SC-005**: Tras cambiar el modo de entender, ninguna respuesta por significado usa el índice anterior; la primera respuesta por significado llega solo cuando el índice nuevo está completo.
- **SC-006**: Una pregunta de entidad conocida recibe respuesta en menos de 5 segundos cuando el índice ya está listo.

## Assumptions

- La persona que pregunta ya ha entrado en la aplicación y tiene una empresa y un ejercicio elegidos.
- Los nombres de clientes, artículos y cuentas, y las cifras de ventas, stock y rankings, ya están cargados para esa empresa.
- El alcance de la primera versión es reconocer cliente, artículo y cuenta. No incluye buscar el texto libre de documentos, correos ni asientos contables.
- Las cifras siguen saliendo de los cálculos ya comprobados. Esta mejora elige la entidad; no cambia las fórmulas de ratios, ventas ni stock.
- El modo de entender el lenguaje es local y lo elige la empresa. Al activarlo se reconstruye el índice antes de usarlo.
- Si el modo de entender no está disponible, las preguntas con regla fija siguen funcionando y la búsqueda por significado se declara no disponible.
