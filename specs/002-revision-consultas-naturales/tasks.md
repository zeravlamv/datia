---
description: "Tareas de la revisión de consultas en lenguaje natural"
---

# Tasks: Revisión de consultas en lenguaje natural

**Input**: Design documents from `/specs/002-revision-consultas-naturales/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: El plan y quickstart.md piden pruebas automáticas del listado sin corte, de los dos dialectos y de la corrección del examen. Esas pruebas se escriben primero y tienen que fallar antes del cambio. No se lanza el examen completo en esta fase.

**Organization**: Cada historia se implementa y se prueba sola. No se crea una aplicación nueva ni un atajo distinto del lector del catálogo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede hacerse en paralelo (otro archivo, sin depender de una tarea sin terminar)
- **[Story]**: Historia a la que pertenece (US1, US2, US3)
- Cada tarea nombra el archivo exacto

## Path Conventions

- Monolito Django: `datia/services/ai/`, `datia/static/js/dashboard/`, `datia/tests/`
- Postgres al leer en local. Un listado completo también tiene que compilar en SQL Server, sin usar `LIMIT` allí
- El chat y la pestaña Examen ya existen

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dejar el listado dentro del lector que ya contesta el catálogo

- [X] T001 En `datia/services/query_builder.py`, mantener `consulta_de_mapeo` como primer paso de `_construir_consulta`. No añadir un atajo para «todos», «familia» ni el listado de artículos

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Reconocer el conjunto entero y poder compilar un listado sin corte en los dos dialectos

**⚠️ CRITICAL**: Ninguna historia empieza hasta cerrar esta fase

- [X] T002 En `datia/services/ai/interprete_mapeo.py`, añadir la detección del conjunto entero para `todos`, `todas`, `todo`, `completo`, `completa` y `listado completo`. Una frase con «los 10» o «los primeros» no es el conjunto entero
- [X] T003 En `datia/services/ai/interprete_mapeo.py`, hacer que `_compilar_listado` omita `LIMIT` y `TOP` cuando el plan marca el listado como completo. El corte vacío es la regla: «Corte: Vacío si la frase pide todos, todas, completo o listado completo». No subir el tope general de `_limite` en `datia/services/ai/compilador_mapeo.py`: el resto de lecturas sigue cortado
- [X] T004 En `validar_plan` de `datia/services/ai/interprete_mapeo.py`, no volver a imponer el máximo de 100 cuando el plan es un listado completo. Un listado que no pide el conjunto entero sigue pudiendo cortarse

**Checkpoint**: El lector sabe cuándo un listado es completo y puede escribirlo sin corte. El chat todavía muestra la muestra actual

---

## Phase 3: User Story 1 - Ver todos los artículos con las columnas pedidas (Priority: P1) 🎯 MVP

**Goal**: «Quiero ver una lista de todos los artículos con el código, la descripción y la familia» devuelve las 1.616 fichas de la empresa, con esas tres columnas y el recuento real

**Independent Test**: Con la empresa activa y sus artículos cargados, esa frase muestra un registro por artículo, columnas Código, Descripción y Familia, y el recuento igual al número de artículos. «Los 10 primeros» sigue devolviendo 10

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T005 [US1] En `datia/tests/test_interprete_mapeo.py`, ampliar `_catalogo()` con `CodigoFamilia` / `Familia` y la columna física `familia`. Añadir pruebas que fallen hoy: el listado de todos los artículos con código, descripción y familia no lleva `LIMIT` ni filtra por ejercicio, los títulos son Código, Descripción y Familia, y el código conserva los ceros; en SQL Server ese listado no usa `TOP`; «los 10 primeros artículos con el código y la descripción» sí corta a 10; un listado de artículos sin «todos» sigue cortado; «todos los clientes con el código y la razón social» tampoco lleva corte ni ejercicio. La prueba ya existente de la lista corta de artículos tiene que seguir esperando el corte

### Implementation for User Story 1

- [X] T006 [US1] En `plan_determinista` de `datia/services/ai/interprete_mapeo.py`, marcar completo el listado cuando T002 lo detecte y no ponerle tope numérico. Las columnas siguen siendo solo las pedidas que están mapeadas, en ese orden. Para artículos: código, descripción y familia. Los títulos visibles son Código, Descripción y Familia. El valor de familia es el guardado en el artículo, no un nombre de otra tabla. La empresa filtra; el ejercicio no
- [X] T007 [P] [US1] En `datia/services/ai/formatter.py`, el indicador de registros de un listado es el número de filas devueltas. Por encima de 10.000 filas la lista mostrada puede cortarse, pero el total anunciado sigue siendo el real y la respuesta dice que está incompleta. Con 1.616 artículos ese aviso no aparece. Marcar la respuesta para que la pantalla sepa que es el conjunto entero
- [X] T008 [P] [US1] En `datia/static/js/dashboard/ia.js`, `renderAiReport` no debe pasar 30 filas a `anadirTablaInforme` cuando la respuesta es el conjunto entero. La tabla se puede recorrer hasta la última fila y enseña el total

**Checkpoint**: La historia 1 se prueba sola en el chat. El recuento de artículos coincide con el maestro y la familia se ve

---

## Phase 4: User Story 2 - Leer cualquier pregunta del contexto mapeado por un solo camino (Priority: P2)

**Goal**: El listado completo, el total, el recuento, la agrupación y la comparativa salen del mismo lector. Una frase que pide todos no cae en un ranking ni en el modelo

**Independent Test**: Una pregunta de cada tipo del contexto actual coincide con el dato guardado. «Qué tiempo hace hoy» no recibe una cifra de artículos ni de ventas. La frase de todos los artículos no llama al modelo

### Tests for User Story 2

- [X] T009 [US2] En `datia/tests/test_interprete_mapeo.py`, añadir una prueba que falle si el listado completo llama al modelo: `consultar` con un `pedir` que lance error sigue devolviendo el listado de artículos. Mantener verdes las pruebas ya existentes de ventas del ejercicio, comparativa de dos años, clientes que han comprado un producto, albarán cuando no se dice pedido, y la frase ajena que no debe convertirse en un listado

### Implementation for User Story 2

- [X] T010 [US2] En `datia/services/ai/router.py`, si la frase pide el conjunto entero, no desviarla a `QueryBuilder._handle_ranking` aunque aparezca «familia» u otra palabra de ranking. «Mejores» o «top» sin pedir el conjunto entero siguen en el ranking que ya existe, para no mover una respuesta que ya coincidía. El modelo local no se usa para decidir este listado

**Checkpoint**: Las historias 1 y 2 funcionan a la vez. El listado completo no se sustituye por una muestra ni por un ranking

---

## Phase 5: User Story 3 - Cerrar la revisión con un examen del contexto actual (Priority: P3)

**Goal**: La pestaña Examen muestra la pregunta del catálogo entero y el examen solo se acepta cuando todas las preguntas coinciden con el dato guardado

**Independent Test**: Al abrir Examen se ve la pregunta nueva, con el total y los primeros códigos, sin lanzarla. Una respuesta de 30 filas no cuenta como coincidencia. Las preguntas que ya coincidían siguen coincidiendo

### Tests for User Story 3

- [X] T011 [P] [US3] En `datia/tests/test_examen_preguntas.py`, cubrir el modo `listado`: coincidencia solo si el recuento es el total, los primeros códigos aparecen en orden y la familia está; 30 filas con un recuento de 30 es otra cifra. No romper las pruebas ya existentes de importe, conteo, lista, textos y cifras

### Implementation for User Story 3

- [X] T012 [US3] En `clasificar` de `datia/services/ai/examen_preguntas.py`, aceptar el modo `listado` con esa regla. Coincidencia solo si el dato mostrado es el guardado
- [X] T013 [US3] En `datia/services/ai/examen_preguntas.py`, conservar el banco actual y añadir la pregunta de todos los artículos con código, descripción y familia. Lo esperado es el número de artículos de la empresa, los primeros códigos en orden y la familia de esos primeros. No se guarda el catálogo entero en la ficha. No usar palabras de ranking en esa pregunta. El banco sigue incluyendo un total filtrado por producto, un recuento, una agrupación, una comparativa de dos ejercicios y un cruce de clientes con un producto

**Checkpoint**: Las tres historias funcionan. Abrir la pestaña no lanza el examen; lanzarlo exige el cien por cien de coincidencias

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cerrar con las comprobaciones de quickstart.md

- [X] T014 Ejecutar, desde `e:\datia` y de una en una, `python -m unittest discover -s datia/tests -p test_interprete_mapeo.py -v` y `python -m unittest discover -s datia/tests -p test_examen_preguntas.py -v`
- [X] T015 Recorrer la prueba del chat y la de la pestaña Examen descritas en `specs/002-revision-consultas-naturales/quickstart.md`. El recuento visible es 1.616, la familia es la guardada y el resumen del examen queda con todas las preguntas en coincidencia

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: puede empezar ya
- **Foundational (Phase 2)**: depende de Setup y bloquea las historias
- **User Stories (Phase 3+)**: dependen de Foundational. Van en orden P1 → P2 → P3
- **Polish (Phase 6)**: depende de las tres historias

### User Story Dependencies

- **User Story 1 (P1)**: empieza tras Foundational. No depende de las otras historias
- **User Story 2 (P2)**: empieza tras Foundational. Usa el listado de US1 y no debe cambiar las lecturas que ya coinciden
- **User Story 3 (P3)**: la corrección del modo `listado` puede escribirse tras Foundational; añadir la pregunta al banco depende de que US1 ya devuelva el conjunto entero

### Within Each User Story

- La prueba se escribe primero y falla
- Después se cambia el lector, el formato o el examen
- La historia se comprueba sola antes de pasar a la siguiente

### Parallel Opportunities

- T007 y T008 pueden ir a la vez después de T006: uno toca `formatter.py` y el otro `ia.js`
- T011 puede escribirse a la vez que T005: son archivos de prueba distintos
- US2 y US3 no se paralelizan con la implementación de US1, porque las dos comprueban el listado completo

---

## Parallel Example: User Story 1

```text
# Después de T006, a la vez:
T007 en datia/services/ai/formatter.py
T008 en datia/static/js/dashboard/ia.js
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Cerrar Phase 1 y Phase 2
2. Cerrar Phase 3
3. Parar y probar en el chat la frase de todos los artículos
4. Seguir solo si el recuento es el del maestro y se ven las tres columnas

### Incremental Delivery

1. Setup y base del listado sin corte
2. Historia 1: el catálogo entero en el chat
3. Historia 2: ese listado no se va a un ranking ni al modelo, y el resto de lecturas sigue igual
4. Historia 3: la pregunta entra en el examen y una muestra deja de contar como acierto
5. Quickstart: pruebas automáticas y, al final, el examen lanzado al cien por cien

### Parallel Team Strategy

Con dos personas, tras Phase 2:

1. Una escribe T005 y la implementación de US1
2. La otra escribe T011, la corrección del examen, sin añadir todavía la pregunta al banco
3. La pregunta del banco espera a que US1 devuelva todas las filas

---

## Notes

- [P] solo si el archivo es distinto y la tarea no espera a otra sin terminar
- No cambiar `_limite` para todas las consultas: solo el listado completo va sin corte
- No mapear una tabla de nombres de familia
- No lanzar las cien preguntas del examen mientras se escribe el código
- Parar en cada checkpoint y probar esa historia sola
