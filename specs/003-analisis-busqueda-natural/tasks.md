---
description: "Tareas del análisis de la búsqueda en lenguaje natural"
---

# Tasks: Análisis de la búsqueda en lenguaje natural

**Input**: Design documents from `/specs/003-analisis-busqueda-natural/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/memoria-conversacion.md, contracts/revision-exhaustiva.md, quickstart.md

**Tests**: El plan pide pruebas de tres decisiones (frase sola, continuación y frase posterior que no hereda) y de cobertura del territorio. Esas pruebas se escriben primero y tienen que fallar antes del cambio de cada historia. No se lanza la revisión completa contra la empresa real en las tareas de implementación.

**Organization**: Cada historia se implementa y se prueba sola. La historia 4 va antes que la 2, aunque las dos son P2, porque la revisión necesita la decisión de memoria para armar sus parejas. No se crea una aplicación nueva ni se reactiva `ConversationManager.enrich`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede hacerse en paralelo (otro archivo, sin depender de una tarea sin terminar)
- **[Story]**: Historia a la que pertenece (US1, US2, US3, US4)
- Cada tarea nombra el archivo exacto

## Path Conventions

- Monolito Django: `datia/services/ai/`, `datia/api/`, `datia/models/ai.py`, `datia/static/js/`, `datia/tests/`
- Postgres al leer en local. La lectura aceptada vive en la conversación del chat, no en un almacén distinto
- Producción sigue en SQL Server para los datos de negocio: la revisión ejecuta la misma lectura en el dialecto que corresponda. El campo nuevo de la conversación tiene que poder migrarse en los dos motores de Django
- El chat y la pestaña Examen ya existen

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dejar la pregunta en el lector del catálogo y no reabrir el mezclador antiguo

- [X] T001 En `datia/services/query_builder.py`, mantener `consulta_de_mapeo` como primer paso de `_construir_consulta`. No añadir un atajo por muletillas de continuación («y», «ahora», «los mismos», «también»). No llamar a `ConversationManager.enrich` desde ese recorrido

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Tener dónde guardar la última lectura aceptada y cómo representarla, sin cambiar todavía las respuestas

**⚠️ CRITICAL**: Ninguna historia empieza hasta cerrar esta fase

- [X] T002 En `datia/models/ai.py`, añadir a `ConsultaConversacion` el campo `lectura_aceptada` como `JSONField` nulo, con defecto vacío (None). Crear la migración siguiente en `datia/migrations/`. Reglas literales del modelo: «Solo se guarda si la respuesta es una lectura, no una negativa.» «Una conversación tiene como mucho una lectura vigente. La nueva aceptada reemplaza a la anterior.» «Una conversación nueva empieza sin lectura.» «Cambiar de empresa no borra la memoria de la otra: simplemente no se usa.» El campo queda vacío en las filas ya guardadas. No crear otra tabla
- [X] T003 En `datia/services/ai/interprete_mapeo.py`, extraer de un plan aceptado el diccionario de lectura con estas claves y solo estas: `clase` (cifra, listado, agrupación o comparación), `conceptos`, `columnas`, `filtros`, `corte`, `periodo`, `forma` (`tabla` o `grafica`). `periodo` vacío si es una ficha maestra. `corte` es el conjunto entero o el número dicho. Esta tarea no cambia lo que `consultar` devuelve hoy

**Checkpoint**: La conversación puede guardar una lectura y el lector sabe describirla. El chat sigue contestando cada envío suelto

---

## Phase 3: User Story 1 - Clasificar cualquier pregunta (Priority: P1) 🎯 MVP

**Goal**: Cualquier frase termina en una lectura de datos mapeados o en una negativa. No hay una tercera salida que conteste con el dato de otra pregunta

**Independent Test**: Un conjunto de frases cubre lecturas posibles, frases ajenas a los datos y frases que nombran un dato concreto no mapeado. Cada frase queda en una sola clase. Ninguna frase de una clase recibe la respuesta de otra

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T004 [US1] En `datia/tests/test_interprete_mapeo.py`, añadir pruebas que fallen hoy si el comportamiento no cumple esto: una frase que nombra datos mapeados devuelve una sola lectura, con sus columnas, filtros, corte y periodo; una frase que nombra un dato concreto no mapeado devuelve exactamente «Esa pregunta no está en los datos mapeados.»; una frase que no habla de datos mapeados no devuelve una cifra ni un listado de la empresa; dos frases de lecturas distintas, llamadas por separado, no comparten columnas, filtros, corte ni periodo; hay dos lecturas cuando, aplicadas las reglas ya cerradas (sin «pedido» es albarán, y «han comprado» con clientes es una venta), siguen encajando dos conceptos mapeados o dos relaciones usables y la frase no nombra cuál: la respuesta es exactamente «Esa pregunta admite más de una lectura. Indica cuál quieres.», sin SQL y sin mezclar cifras, y ese aviso no sustituye a la última lectura aceptada; si la frase nombra uno de los dos, esa es la lectura. Mantener verdes las pruebas ya existentes del listado, del corte numérico, del albarán y de la frase ajena

### Implementation for User Story 1

- [X] T005 [P] [US1] En `datia/services/query_builder.py`, si la frase no nombra datos mapeados, no dejar que un atajo posterior devuelva una cifra ni un listado de la empresa como si respondieran a esa frase. Si nombra un dato concreto que no está mapeado, la única salida es «Esa pregunta no está en los datos mapeados.» No añadir una tercera salida
- [X] T006 [P] [US1] En `datia/services/ai/interprete_mapeo.py`, cuando, aplicadas las reglas ya cerradas (sin «pedido» es albarán, y «han comprado» con clientes es una venta), siguen encajando dos conceptos mapeados o dos relaciones usables y la frase no nombra cuál, devolver exactamente «Esa pregunta admite más de una lectura. Indica cuál quieres.» sin componer un SQL ni mezclar esas cifras. Si la frase nombra uno, ese es el plan. Una frase con una sola lectura sigue el plan que ya tiene. Ese aviso no sustituye a la última lectura aceptada
- [X] T007 [US1] En la salida de `datia/services/ai/interprete_mapeo.py` y en el JSON de `qa_query` en `datia/api/endpoints.py`, incluir un recorrido en lenguaje de negocio: qué clase tuvo la frase, si fue sustituida, recortada o rechazada, y qué quedó visible. Sirve para cualquier frase, no para un ejemplo fijo

**Checkpoint**: La historia 1 se prueba sola. Una frase mapeada tiene una lectura; una frase de fuera no recibe datos de la empresa; un dato concreto no mapeado recibe la negativa fija

---

## Phase 4: User Story 4 - Recordar la pregunta anterior sin forzar el vínculo (Priority: P2)

**Goal**: La pregunta siguiente puede continuar la última lectura aceptada de esa conversación y esa empresa, o ser una pregunta nueva. Si se entiende sola, no hereda nada

**Independent Test**: Aceptar una lectura. Enviar una frase incompleta que solo cambia el periodo, la agrupación, el corte o una columna, y comprobar que el resto se conserva. Enviar después una frase que se entiende sola y comprobar que no conserva nada

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T008 [US4] En `datia/tests/test_interprete_mapeo.py`, añadir pruebas que fallen hoy: una lectura es completa cuando, sin memoria, ya hay clase, concepto y forma; si la frase sola produce una lectura completa, el vínculo es `sola` aunque también pudiera leerse como continuación, y no se usan filtros, columnas, concepto, corte ni periodo de la anterior; si falta clase, concepto o forma y el completado con la última aceptada sí produce lectura, el vínculo es `continuacion`, lo no dicho se conserva y lo dicho sustituye, sin sumar dos valores en conflicto para la misma parte; si la frase nombra un dato concreto que no está mapeado, aunque haya una lectura aceptada, el vínculo es `rechazo`, el texto es exactamente «Esa pregunta no está en los datos mapeados.» y no se rellenan huecos; si no hay lectura aceptada, una frase incompleta es `rechazo`; el rechazo no modifica la lectura aceptada; otra empresa o una conversación nueva no usa esa lectura; si hay varias lecturas aceptadas, la continuación usa solo la última. El aviso «Esa pregunta admite más de una lectura. Indica cuál quieres.» tampoco modifica la lectura aceptada

### Implementation for User Story 4

- [X] T009 [US4] En `datia/services/ai/interprete_mapeo.py`, decidir en este orden, tal como está en `specs/003-analisis-busqueda-natural/contracts/memoria-conversacion.md`: si la frase nombra un dato concreto que no está mapeado, el vínculo es `rechazo`, la respuesta es exactamente «Esa pregunta no está en los datos mapeados.» y no se rellenan huecos; si no, intentar la frase sola; una lectura es completa cuando, sin memoria, ya hay clase, concepto y forma; si lo es, es nueva y no se consulta la memoria; si falta uno de esos tres y hay lectura aceptada, completar solo los huecos y sustituir lo que la frase nueva dice; si ese completado es una lectura, es continuación; si no, negativa fija y la memoria no cambia. La salida lleva `vinculo` (`sola`, `continuacion` o `rechazo`), la lectura o ninguna, y, si es continuación, `hereda` y `sustituye`. No usar `ConversationManager.enrich`
- [X] T010 [US4] En `qa_query` de `datia/api/endpoints.py`, aceptar `conversacion_id`, cargar `lectura_aceptada` solo si esa fila es de la empresa activa, y pasarla a la decisión de T009. Dejar de tratar cada envío como suelto: quitar el comentario y la anulación que dejan `last_query = None`, y no guardar `request.session['ai_last_query']`. Si la respuesta es una lectura aceptada, devolverla en el JSON como `lectura_aceptada`. Si es rechazo o el aviso «Esa pregunta admite más de una lectura. Indica cuál quieres.», devolver ese campo vacío: vacío significa que no se sustituye la anterior. No escribir la fila dentro de `/qa`, porque en la primera pregunta todavía no existe. Sin conversación, la frase no tiene lectura anterior
- [X] T011 [US4] En `datia/static/js/dashboard/ia.js`, `askAI` envía `conversacionActual` en la llamada a `/qa`. `guardarConversacionActual` envía ese mismo id, no un id vacío, y envía la `lectura_aceptada` que devolvió `/qa`. En `guardar_conversacion` de `datia/api/endpoints.py`, el mensaje se añade a esa fila aunque el texto sea distinto. Si llega una lectura, reemplaza `lectura_aceptada`. Si el campo llega vacío, se deja como estaba. La primera pregunta crea la fila, guarda la lectura y desde entonces `conversacionActual` es ese id. Una conversación nueva, o un cambio de empresa, deja ese id fuera de uso. Abrir una conversación de la lista izquierda usa la suya

**Checkpoint**: Las historias 1 y 4 funcionan a la vez. «Y en 2024» continúa; una frase posterior que se entiende sola no arrastra el contexto; una negativa deja la memoria donde estaba

---

## Phase 5: User Story 2 - Revisar todas las lecturas que el contexto permite (Priority: P2)

**Goal**: La revisión se genera desde el territorio mapeado de la empresa activa. Cada columna legible, cada relación usable, cada forma de lectura y cada pareja de memoria tiene al menos una pregunta. Si falta una pieza, la revisión está incompleta

**Independent Test**: Generar la revisión desde los datos mapeados y comprobar que cada columna, cada relación y cada forma aparecen al menos una vez, y que cada forma tiene su pareja. Lanzar una pregunta y comparar la respuesta con el dato guardado

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T012 [US2] En `datia/tests/test_examen_preguntas.py`, cubrir el generador con un territorio pequeño de catálogo: falta una columna, una relación, una forma o una pareja y la revisión queda incompleta nombrando esa pieza, aunque el resto coincida; con el territorio completo hay una pregunta por columna legible, una por relación usable y una por cada forma (filtrar, varios filtros, agrupar, sumar, contar, promediar, máximo, mínimo, listar, conjunto entero, número concreto de filas, un periodo, comparación de periodos guardados, tabla y gráfica), más la pareja de esa forma; no se genera el cruce de todas las piezas entre sí; una ficha maestra en conjunto entero no lleva filtro de ejercicio; un movimiento usa el ejercicio elegido salvo que la frase nombre otro periodo; sin la palabra pedido el documento es el albarán; «han comprado» con clientes es una venta; un número dicho no se convierte en el conjunto entero; una continuación se compara con la lectura ya completada y una frase que se entiende sola se compara sin memoria; un probe que nombra un dato concreto no mapeado solo coincide con «Esa pregunta no está en los datos mapeados.»; una frase ajena no coincide si muestra una cifra o un listado de la empresa. No romper las pruebas ya existentes de `clasificar`

### Implementation for User Story 2

- [X] T013 [US2] En `datia/services/ai/examen_preguntas.py`, sustituir el banco armado por una lista fija de frases por una revisión generada del mapa activo de la empresa, según `specs/003-analisis-busqueda-natural/contracts/revision-exhaustiva.md`. Una pregunta por columna legible, una por relación usable, una por cada forma de lectura y, por cada forma, la pareja: continuación que cambia una sola parte (periodo, agrupación, corte o columna) y pregunta posterior que se entiende sola. Añadir probes de frases ajenas y de un dato concreto no mapeado. Si falta una pieza, `incompleta` es verdadero y se nombra la pieza. No es el producto cartesiano. El resultado esperado sale de ejecutar la lectura sobre los datos de esa empresa y ese periodo. Una pregunta que el banco actual ya hacía coincidir y sigue siendo legible en el territorio permanece y su lectura no cambia. No usar palabras de ranking en una pregunta que pide el conjunto entero. Invalidar `_CACHE` para que no se reutilice el banco fijo anterior
- [X] T014 [US2] En `clasificar` y `responder_una` de `datia/services/ai/examen_preguntas.py`, una continuación se ejecuta con la lectura aceptada de su pareja y se compara con la lectura ya completada; una pregunta `sola` se ejecuta sin memoria. Una continuación que hereda de más o de menos no coincide. Los modos ya existentes (`importe`, `conteo`, `lista`, `textos`, `cifras`, `listado`) siguen decidiendo como ahora. `responder_una` sigue sin guardar la pregunta como SQL aprendido

**Checkpoint**: Las historias 1, 4 y 2 funcionan. La revisión sale del territorio. Una pieza sin pregunta la deja incompleta

---

## Phase 6: User Story 3 - Ver si cualquier pregunta queda validada (Priority: P3)

**Goal**: Quien revisa ve el conjunto entero antes de lanzarlo. Solo se acepta si el territorio está completo, todas las preguntas coinciden y todas las frases de fuera quedan rechazadas

**Independent Test**: Abrir la revisión de la empresa y el ejercicio activos, ver cada pregunta y lo esperado sin lanzarla, comprobar si falta alguna pieza, lanzarla y comprobar que no queda ninguna pregunta sin veredicto ni ninguna coincidencia perdida

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T015 [US3] En `datia/tests/test_examen_preguntas.py`, la salida de `listar` incluye, antes de cualquier veredicto, cada pregunta con su vínculo (`sola` o `continuacion`) y el resultado esperado, cada probe con la negativa esperada, y, si falta territorio, `incompleta` más la pieza que falta. El resumen que se puede calcular al terminar dice cuántas preguntas cubren el territorio, cuántas coinciden y cuántas frases de fuera fueron rechazadas. Ese resumen solo puede darse por aceptado cuando las tres cosas ocurren a la vez: no falta ninguna columna, relación, forma ni pareja; todas las preguntas coinciden; todos los probes rechazan. Repetir la revisión no cambia una coincidencia anterior a no coincidencia

### Implementation for User Story 3

- [X] T016 [P] [US3] En `listar` de `datia/services/ai/examen_preguntas.py`, devolver ese conjunto visible: pregunta, vínculo, esperado, probes, `incompleta` y la pieza que falta. `datia/api/introspection_endpoints.py` ya reexpone `listar` en `examen_preguntas_api`; no recortar esos campos. El estado de la revisión es Preparada mientras no hay veredictos. Pasa a Aceptada solo con las tres condiciones de T015; si no, queda Rechazada
- [X] T017 [P] [US3] En `datia/static/js/tab_auto_training.js`, `pintarListaExamen` muestra cada pregunta, su vínculo y lo esperado al abrir la pestaña, sin lanzar el examen. Si `incompleta` es verdadero, el estado nombra la pieza que falta y el resumen no puede quedar como aceptado. `pintarResumenExamen` dice cuántas preguntas cubren el territorio, cuántas coinciden y cuántas frases de fuera fueron rechazadas. Volver a lanzar mantiene en coincidencia las que ya coincidían

**Checkpoint**: Las cuatro historias funcionan. Abrir Examen no lanza la revisión. Aceptarla exige territorio completo, coincidencias y rechazos de fuera

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Cerrar con las pruebas automáticas y el recorrido de quickstart.md

- [X] T018 Ejecutar, desde `e:\datia` y de una en una, `python -m unittest discover -s datia/tests -p test_interprete_mapeo.py -v` y `python -m unittest discover -s datia/tests -p test_examen_preguntas.py -v`
- [X] T019 Recorrer los cinco pasos de `specs/003-analisis-busqueda-natural/quickstart.md` en el chat y en la pestaña Examen: frase sola, continuación, pregunta nueva que no hereda, frase de fuera, y revisión entera vista antes de lanzarla. Una respuesta de una sola pregunta, incluido un listado del conjunto entero de hasta 6.000 fichas, puede empezar a leerse antes de 15 segundos

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias
- **Foundational (Phase 2)**: Depende de Setup. Bloquea todas las historias
- **User Story 1 (Phase 3)**: Depende de Foundational. No depende de las demás
- **User Story 4 (Phase 4)**: Depende de Foundational y de la clasificación de la historia 1
- **User Story 2 (Phase 5)**: Depende de la decisión de memoria de la historia 4, porque cada forma lleva una pareja
- **User Story 3 (Phase 6)**: Depende de la revisión generada en la historia 2
- **Polish (Phase 7)**: Depende de las historias que se quieran cerrar

### User Story Dependencies

- **User Story 1 (P1)**: Empieza tras Foundational. Es el MVP
- **User Story 4 (P2)**: Empieza tras la historia 1. Se prueba sola en el chat, con una conversación y una empresa
- **User Story 2 (P2)**: Empieza tras la historia 4. El generador se prueba con un territorio pequeño, sin lanzar la revisión real
- **User Story 3 (P3)**: Empieza tras la historia 2. La pestaña solo muestra lo que `listar` ya devuelve

### Within Each User Story

- Las pruebas se escriben y fallan antes de la implementación
- La lectura y la decisión van antes que la respuesta de `/qa`
- `/qa` devuelve la lectura y el guardado del mensaje la escribe en la misma fila. La pregunta siguiente envía el id de esa fila
- El generador va antes que la pantalla de la revisión

### Parallel Opportunities

- T005 y T006 tocan archivos distintos y pueden hacerse a la vez tras T004
- T016 y T017 tocan archivos distintos y pueden hacerse a la vez tras T015
- T009, T010 y T011 van en ese orden: primero la decisión, después `/qa` devuelve la lectura sin escribir la fila, después el chat guarda esa lectura en la misma fila y la reenvía en la pregunta siguiente
- La historia 2 no se adelanta a la 4

---

## Parallel Example: User Story 1

```text
# Tras T004, en paralelo:
Tarea: "T005 En datia/services/query_builder.py, cerrar la tercera salida"
Tarea: "T006 En datia/services/ai/interprete_mapeo.py, pedir que se distinga si hay dos lecturas"
```

## Parallel Example: User Story 3

```text
# Tras T015, en paralelo:
Tarea: "T016 En datia/services/ai/examen_preguntas.py, devolver el conjunto visible"
Tarea: "T017 En datia/static/js/tab_auto_training.js, mostrar vínculo y esperado antes de lanzar"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1 y Phase 2
2. Completar Phase 3 (User Story 1)
3. Parar y validar la historia 1 sola: lectura o negativa, nunca el dato de otra pregunta
4. Seguir con la memoria solo si esa clasificación se sostiene

### Incremental Delivery

1. Setup + Foundational
2. Historia 1: clasificar cualquier pregunta
3. Historia 4: continuación o pregunta nueva
4. Historia 2: revisión generada del territorio
5. Historia 3: verla entera y aceptarla solo si cierra las tres condiciones
6. Cada historia deja las anteriores intactas

### Parallel Team Strategy

Con más de una persona, tras Foundational:

1. Una persona cierra la historia 1
2. La memoria (historia 4) espera a esa clasificación
3. Tras la memoria, el generador (historia 2) y, después, la pantalla (historia 3)

---

## Notes

- [P] = otro archivo, sin depender de una tarea sin terminar
- La negativa fija es «Esa pregunta no está en los datos mapeados.»
- El aviso de dos lecturas es «Esa pregunta admite más de una lectura. Indica cuál quieres.»
- Una lectura completa, sin memoria, ya tiene clase, concepto y forma
- No mapear tablas nuevas. No subir el tope general de 100 en `datia/services/ai/compilador_mapeo.py`. No reactivar el mezclador de `datia/services/ai/conversation_manager.py`
- Una frase que se entiende sola manda, aunque también pudiera continuar
- Una frase rechazada no sustituye a la última lectura aceptada
- La revisión es un cubrimiento, no el producto cartesiano
- Parar en cualquier checkpoint y probar esa historia sola
