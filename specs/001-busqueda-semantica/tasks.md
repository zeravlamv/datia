---
description: "Tareas de la búsqueda semántica del negocio"
---

# Tasks: Búsqueda semántica del negocio

**Input**: Design documents from `/specs/001-busqueda-semantica/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/consulta-significado.md, quickstart.md

**Tests**: El plan pide una prueba automática del orden de las reglas, de la ambigüedad y del rechazo de vectores de otro modelo. No se pide escribir el resto de pruebas antes del código. La validación de las 30 preguntas sigue siendo manual, en quickstart.md.

**Organization**: Cada historia se implementa y se prueba sola. El alcance es cliente, artículo y cuenta de la empresa activa.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede hacerse en paralelo (otro archivo, sin depender de una tarea sin terminar)
- **[Story]**: Historia a la que pertenece (US1, US2, US3)
- Cada tarea nombra el archivo exacto

## Path Conventions

- Monolito Django: `datia/models/`, `datia/services/`, `datia/management/commands/`, `datia/tests/`, `config/settings.py`
- Postgres de la aplicación. SQL Server no se consulta al preguntar ni al reindexar
- `tpl_ai_embeddings` se queda para plantillas SQL

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Fijar el modo local de embeddings sin tocar el chat de lenguaje

- [X] T001 En `config/settings.py`, leer `DATIA_EMBED_PROVIDER` y `OLLAMA_EMBED_MODEL` del entorno que ya carga `environ.Env.read_env`, con valores de trabajo `ollama` y `nomic-embed-text`. No modificar campos LLM de GlobalConfig. No instalar paquetes ni descargar el modelo en esta tarea
- [X] T002 [P] En `datia/models/ai.py`, dejar en el docstring de `MetricsEmbeddings` que `db_table = 'tpl_ai_embeddings'` es solo el índice de plantillas SQL y no guarda clientes, artículos ni cuentas

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Índice propio, vector nativo y comparación acotada a una empresa

**⚠️ CRITICAL**: Ninguna historia empieza hasta cerrar esta fase

- [X] T003 Crear `datia/models/significado.py` y exportarlo en `datia/models/__init__.py`. `SignificadoEntidad`: `empresa` obligatoria e IntegerField, ninguna consulta cruza empresas; `clase` solo `cliente`, `articulo` o `cuenta`; `identificador` estable, no se reescribe al reindexar; `texto_indexado` copia del texto visible, vacío no se indexa; `origen` solo `datia_cliente`, `datia_articulos` o `datiadb_plancuentas`; `modelo` identificador exacto del modelo; `vector` JSONField con la lista numérica de la longitud nativa de ese modelo. Un mismo identificador y clase solo tiene un texto vigente por empresa. Unique `(empresa, clase, identificador, modelo)`. `SignificadoLote`: `empresa` obligatoria, `modelo`, `estado` solo `construyendo` o `listo`, unique `(empresa, modelo)`. El estado del lote es compartido por todas las filas de un modelo y una empresa
- [X] T004 Crear la migración `datia/migrations/0053_significado.py` para `SignificadoEntidad` y `SignificadoLote` definidos en `datia/models/significado.py`. No tocar `tpl_ai_embeddings` ni instalar `pgvector`
- [X] T005 [P] En `datia/services/embedding_service.py`, hacer que `_embed_with_ollama` devuelva el vector nativo de `nomic-embed-text` (768 números): no recortar a 384 ni rellenar con ceros. Si Ollama no responde, devolver None y no usar `_hash_embed` para el índice de entidades. `uses_semantic_vectors` permanece en falso cuando la única representación es la huella hash
- [X] T006 En `datia/services/significado_service.py`, comparar por coseno en memoria solo las filas de la empresa activa, del modelo activo y del lote en estado `listo`. No se compara un vector con otro de distinto modelo o distinta longitud. No recorrer otras empresas
- [X] T007 En `datia/management/commands/datia_significado_reindex.py`, reconstruir el índice de una empresa llamando a `datia/services/significado_service.py`. No ejecutar `datia/management/commands/datia_embeddings_reindex.py`, no escribir `tpl_ai_embeddings` y no leer SQL Server. Si `nomic-embed-text` no está en Ollama, el comando se detiene, explica que falta el modelo y no deja el lote en `listo`

**Checkpoint**: El modelo, la migración, el vector nativo y el comando existen. El chat todavía no usa el índice

---

## Phase 3: User Story 1 - Encontrar a quién o a qué se refiere la pregunta (Priority: P1) 🎯 MVP

**Goal**: Una frase aproximada en español identifica un cliente, un artículo o una cuenta de la empresa activa y la respuesta muestra la cifra ya calculada

**Independent Test**: Con la empresa 1 y el ejercicio 2025, preguntar por un cliente, un artículo y una cuenta con el nombre parecido. La respuesta nombra la entidad correcta y la cifra coincide con el dato ya conocido. Si hay varios candidatos, se elige uno y no sale un importe mezclado

### Implementation for User Story 1

- [X] T008 [US1] En `datia/services/significado_service.py`, cargar el texto visible por empresa: cliente desde `datia_cliente` (`cliente`, `nombre`); artículo desde `datia_articulos` (`articulo`, `descripcion`); cuenta desde `datiadb_plancuentas` (`codigo_cuenta`, `nombre_cuenta`). Vacío no se indexa. Un mismo identificador y clase solo tiene un texto vigente por empresa. El identificador no se reescribe al reindexar
- [X] T009 [US1] En `datia/services/significado_service.py`, buscar dentro de la empresa activa. Si dos o más entidades de la misma clase superan el umbral y la diferencia entre la primera y la segunda es pequeña, devolver hasta cinco opciones y ninguna cifra. Cada opción lleva una etiqueta legible y la pregunta a reenviar con el identificador, usando la forma `ambiguity_alert` de `QueryBuilder._party_reply` en `datia/services/query_builder.py`. Si no hay coincidencia suficiente, decir que esa entidad no está en el catálogo de la empresa, sin cifra
- [X] T010 [US1] En `datia/services/query_builder.py`, llamar a la búsqueda de `datia/services/significado_service.py` solo cuando la regla fija no ha cerrado la respuesta. Si falta empresa o ejercicio, pedir elegirlos y no usar cifras de otra empresa. Con un cliente elegido, la cifra sale de `metrics_totales_empresa_ejercicio_cliente` por el camino de `_handle_named_party`. Con un artículo elegido, la cifra de stock sale de `_handle_stock_query` y de `datia_acumulados_stocks`. Con una cuenta elegida, el saldo sale de la suma ya guardada en `datia_financial_acumulados` para esa empresa y ese ejercicio, sin cambiar la fórmula de `saldo`. Si la entidad existe y el ejercicio no tiene dato, decir que no está cargado, sin importe inventado. No pedir el importe a `datia/services/ollama_service.py`
- [X] T011 [US1] En `datia/tests/test_busqueda_semantica.py`, cubrir una sola entidad con cifra, la lista de hasta cinco opciones sin cifra, el nombre ausente del catálogo sin cifra, y la pregunta sin empresa

**Checkpoint**: La historia 1 se prueba sola en el chat de la empresa 1, ejercicio 2025

---

## Phase 4: User Story 2 - Conservar las respuestas que ya son fiables (Priority: P2)

**Goal**: Ventas a un cliente nombrado, stock de un código, rankings y análisis del ejercicio siguen dando la misma cifra

**Independent Test**: Repetir al menos 10 preguntas que hoy responden bien. La entidad y la cifra no cambian al existir el índice

### Implementation for User Story 2

- [X] T012 [US2] En `datia/services/query_builder.py`, mantener este orden dentro de `build_from_nl`: memoria aprendida, tercero nombrado, stock por código, ranking, evolución de ventas o compras, análisis del ejercicio, y solo después la búsqueda de `datia/services/significado_service.py`. Una regla fija que ya encontró la entidad responde ella y no se sustituye. Un código de artículo presente en la pregunta se conserva carácter a carácter y no se corrige con el índice. No cambiar el SQL de `_handle_named_party`, `_handle_stock_query`, `_handle_ranking` ni `_handle_year_analysis`
- [X] T013 [US2] En `datia/tests/test_busqueda_semantica.py`, comprobar que una pregunta de ventas, de stock por código, de ranking y de análisis del ejercicio no llama a la búsqueda por significado y devuelve el mismo camino de cifra que antes

**Checkpoint**: Las historias 1 y 2 funcionan a la vez. Las cifras ya aceptadas no se mueven

---

## Phase 5: User Story 3 - Rehacer el índice al cambiar el modo de entender (Priority: P3)

**Goal**: Al cambiar el modelo, las coincidencias viejas no se usan y el índice se reconstruye antes de volver a responder por significado

**Independent Test**: Cambiar el identificador del modelo. Durante la reconstrucción, el stock por código sigue respondiendo y la pregunta que solo puede resolverse por significado avisa de que el índice se está preparando. Al cerrar el lote, esa pregunta encuentra la entidad con el modelo nuevo

### Implementation for User Story 3

- [X] T014 [US3] En `datia/services/significado_service.py` y `datia/management/commands/datia_significado_reindex.py`, aplicar estas transiciones: modelo nuevo o texto de origen cambiado hace que el lote de esa empresa pase a `construyendo`; durante `construyendo`, la búsqueda por significado no lee filas de otro modelo; cuando todas las entidades de la empresa tienen vector del modelo activo, el lote pasa a `listo`; las filas de un modelo anterior se borran al cerrar el lote nuevo
- [X] T015 [US3] En `datia/services/query_builder.py`, si el lote no está `listo`, responder que la búsqueda por significado se está preparando y no mostrar ese aviso en lugar de la cifra cuando la misma pregunta encaja en una regla fija
- [X] T016 [US3] En `datia/tests/test_busqueda_semantica.py`, comprobar que un vector de otro modelo o de otra longitud no se compara, que durante `construyendo` no hay cifra por significado, y que al pasar a `listo` solo quedan filas del modelo activo

**Checkpoint**: Las tres historias funcionan. Ninguna respuesta por significado usa el índice anterior

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Comprobar el tiempo, el aislamiento y la guía manual

- [X] T017 [P] Confirmar en `datia/services/ollama_service.py` que la elección del modelo de chat no cambia: familia `qwen2.5:3b` en una pregunta normal y `qwen2.5:14b-instruct-q4_k_m` en una pregunta financiera cuando los campos de GlobalConfig siguen vacíos. Ese modelo no calcula la cifra de la búsqueda por significado
- [X] T018 Medir con el índice `listo` de la empresa 1 una pregunta de entidad conocida. El objetivo es menos de 5 segundos (SC-006). Si una empresa supera unos 20.000 textos o la respuesta pasa de 5 segundos, anotarlo en el resultado de esta tarea y no instalar `pgvector` dentro de esta versión
- [ ] T019 Ejecutar los cuatro escenarios de `specs/001-busqueda-semantica/quickstart.md` en el chat, empresa 1 y ejercicio 2025, y registrar el cumplimiento de SC-001 a SC-006 de `specs/001-busqueda-semantica/spec.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende del setup y bloquea todas las historias
- **User Story 1 (Phase 3)**: depende de la fase 2. Es el MVP
- **User Story 2 (Phase 4)**: depende de T010, porque el orden se cierra en el mismo `build_from_nl`
- **User Story 3 (Phase 5)**: T014 puede hacerse al terminar T006 y T007; T015 depende de T010
- **Polish (Phase 6)**: depende de las historias que se quieran entregar

### User Story Dependencies

- **User Story 1 (P1)**: empieza tras la fase 2. No depende de US2 ni de US3
- **User Story 2 (P2)**: empieza tras T010. Se prueba con las preguntas fijas aunque el índice esté vacío
- **User Story 3 (P3)**: el lote y el rechazo de vectores viejos se prueban en el servicio sin esperar a US2. El aviso dentro del chat espera a T010

### Within Each User Story

- El índice y la búsqueda van antes del enganche en `query_builder.py`
- La prueba automática de esa historia va después de su enganche
- No hace falta que la prueba falle antes de implementar

### Parallel Opportunities

- T001 y T002 pueden ir a la vez
- T005 puede ir a la vez que T003 y T004
- T014 puede ir a la vez que T008 y T009
- T017 puede ir a la vez que T018

---

## Parallel Example: User Story 1

```text
# Tras T006 y T007, en paralelo con el lote de la historia 3:
T008 Cargar cliente, artículo y cuenta en datia/services/significado_service.py
T014 Transiciones del lote en datia/services/significado_service.py

# En secuencia, cuando T008 ha terminado:
T009 Ambigüedad de hasta cinco opciones en datia/services/significado_service.py
T010 Enganche y cifra en datia/services/query_builder.py
T011 Prueba en datia/tests/test_busqueda_semantica.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar la fase 1
2. Completar la fase 2
3. Completar T008, T009, T010 y T011
4. Parar y probar la historia 1 en el chat de la empresa 1, ejercicio 2025
5. Seguir con la historia 2 solo si esa prueba nombra la entidad correcta y la cifra coincide

### Incremental Delivery

1. Setup + fundación
2. Historia 1: nombre aproximado y cifra real
3. Historia 2: las respuestas ya fiables no cambian
4. Historia 3: un modelo nuevo no reutiliza vectores viejos
5. Quickstart y criterio de 5 segundos

### Parallel Team Strategy

1. Una persona cierra setup y fundación
2. Después, una persona sigue la historia 1 en el chat y otra prepara las transiciones del lote (T014)
3. La historia 2 entra cuando T010 está en `build_from_nl`

---

## Notes

- [P] significa otro archivo y ninguna dependencia abierta
- La cifra no se redacta con el modelo de chat
- No se corrige un código de artículo
- No se añade `pgvector` en esta versión
- No se consulta SQL Server para responder ni para reindexar
- Cada historia se puede parar y probar sola
