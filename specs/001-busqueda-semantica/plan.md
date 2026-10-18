# Implementation Plan: Búsqueda semántica del negocio

**Branch**: `001-busqueda-semantica` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-busqueda-semantica/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

El chat debe reconocer un cliente, un artículo o una cuenta aunque el nombre no sea exacto, y responder con la cifra que ya calcula la empresa. El significado sale de un modelo local de embeddings en Ollama. Las reglas de ventas, stock, ranking y análisis del ejercicio siguen ganando. Al cambiar el modelo se rehace el índice y no se comparan vectores viejos.

## Technical Context

**Language/Version**: Python 3 sobre Django 5 y Django Ninja. El chat en el navegador sigue en el JavaScript ya existente.

**Primary Dependencies**: Ollama en el equipo (`nomic-embed-text` para embeddings; el chat de lenguaje no cambia). El servicio actual de embeddings y el constructor de consultas.

**Storage**: Postgres de la aplicación. Catálogos ya copiados: `datia_cliente` (14.011), `datia_articulos` (9.502), `datiadb_plancuentas` (7.336). Índice nuevo de significados por empresa. `tpl_ai_embeddings` se queda para plantillas SQL. SQL Server no se consulta al preguntar.

**Testing**: Pruebas manuales del chat descritas en [quickstart.md](quickstart.md), más una prueba automática del orden de reglas, la ambigüedad y el rechazo de vectores de otro modelo.

**Target Platform**: Servidor local de la aplicación en Windows. El móvil usa el mismo chat.

**Project Type**: Aplicación web monolítica.

**Performance Goals**: Respuesta por significado en menos de 5 segundos con el índice listo (SC-006). La comparación se limita a la empresa activa.

**Constraints**: Sin servicios externos para el texto de las preguntas. No cambiar fórmulas de ratios, ventas ni stock. No corregir códigos de artículo. `pgvector` no está instalado; no se exige en esta versión.

**Scale/Scope**: Tres clases de entidad y las empresas ya cargadas. Por debajo de unos 20.000 textos por empresa la comparación en memoria es suficiente. Por encima, o si se pasan los 5 segundos, el diseño prevé un índice nativo de Postgres.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` sigue siendo la plantilla sin principios ratificados. No hay puertas que evaluar ni violaciones que justificar. El plan se limita a la especificación: significado local, cifra existente, aislamiento por empresa y reconstrucción del índice.

Revisión posterior al diseño: se mantiene. No se añade un servicio externo, no se cambia el cálculo de la cifra y el índice viejo no se consulta.

## Project Structure

### Documentation (this feature)

```text
specs/001-busqueda-semantica/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── consulta-significado.md
└── tasks.md              # lo crea /speckit-tasks, no este paso
```

### Source Code (repository root)

```text
datia/services/embedding_service.py    # vectores locales y rechazo de la huella hash
datia/services/query_builder.py        # reglas fijas antes que el significado
datia/models/ai.py                     # embeddings de plantillas, sin mezclar entidades
datia/services/ollama_service.py       # chat de lenguaje, sin usarlo para la cifra
```

**Structure Decision**: Se extiende el monolito actual. El índice de entidades vive junto a los catálogos de Postgres y lo consulta el mismo flujo del chat. No hay aplicación nueva ni contrato HTTP nuevo.

## Complexity Tracking

No aplica. La constitución no impone puertas y este plan no añade proyectos ni capas nuevas.

## Phase 0

Decisiones cerradas en [research.md](research.md). No quedan `NEEDS CLARIFICATION`.

## Phase 1

- Modelo de datos: [data-model.md](data-model.md)
- Contrato del chat: [contracts/consulta-significado.md](contracts/consulta-significado.md)
- Validación: [quickstart.md](quickstart.md)
