# Implementation Plan: Análisis de la búsqueda en lenguaje natural

**Branch**: `003-analisis-busqueda-natural` | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-analisis-busqueda-natural/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Cualquier pregunta en español termina en una lectura de los datos mapeados o en la negativa fija. La revisión que lo demuestra no sale de una lista de ejemplos: se arma con cada columna legible, cada relación usable y cada forma de lectura del territorio de la empresa activa. La pregunta siguiente puede continuar la última lectura aceptada o ser independiente. Si la frase se entiende sola, no hereda nada. Si solo se entiende al completar la anterior, conserva lo no dicho y sustituye lo que repite. Hoy el chat trata cada envío como suelto y hay un recuerdo antiguo que, cuando se usa, mezcla siempre el estado previo. Ninguno de los dos cumple las dos posibilidades.

## Technical Context

**Language/Version**: Python 3 sobre Django. El chat sigue en el JavaScript ya existente.

**Primary Dependencies**: El lector del catálogo mapeado (`datia/services/ai/interprete_mapeo.py`), el examen (`datia/services/ai/examen_preguntas.py`), el guardado de la conversación del chat (`ConsultaConversacion`) y el punto de entrada de la pregunta (`datia/api/endpoints.py`). No se reactiva el mezclador de `ConversationManager`.

**Storage**: Postgres de la aplicación para leer y para guardar la última lectura aceptada de la conversación. Producción sigue en SQL Server: la revisión ejecuta la misma lectura en el dialecto que corresponda. La memoria no se guarda en un almacén distinto del chat.

**Testing**: Pruebas automáticas de tres decisiones: frase sola, continuación y frase posterior que no hereda. Pruebas de cobertura del territorio (columna, relación y forma de lectura sin pregunta dejan la revisión incompleta). La comprobación en el navegador está en [quickstart.md](quickstart.md).

**Target Platform**: Servidor local en Windows y el mismo chat en el navegador.

**Project Type**: Aplicación web monolítica.

**Performance Goals**: Cada pregunta, incluido un listado del conjunto entero de hasta 6.000 fichas, puede empezar a leerse antes de 15 segundos (SC-007). La revisión entera puede tardar más: se mide pregunta a pregunta, no como un solo bloque.

**Constraints**: No mapear tablas nuevas. No inventar un nombre que no esté guardado. La negativa fija sigue siendo «Esa pregunta no está en los datos mapeados.» Una frase que se entiende sola no hereda contexto. Una frase rechazada no sustituye a la última lectura aceptada. El análisis semántico sigue siendo local. No se usa el mezclador antiguo, que aplica el estado previo a toda frase.

**Scale/Scope**: La revisión es un cubrimiento, no el producto cartesiano de columnas, relaciones y formas. Hay una pregunta por cada pieza del territorio, más parejas de memoria (continuación y pregunta suelta) para las formas de lectura. El tamaño esperado es de decenas a unos pocos cientos de preguntas, según lo mapeado en la empresa activa.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` sigue siendo la plantilla sin principios ratificados. No hay puertas que evaluar ni violaciones que justificar. El plan se limita a la especificación: clasificar cualquier pregunta, cubrir el territorio mapeado y recordar la última lectura aceptada sin forzar el vínculo.

Revisión posterior al diseño: se mantiene. No hay servicio nuevo ni tablas de negocio nuevas. La memoria se guarda en la conversación que el chat ya tiene. El cubrimiento no multiplica todas las combinaciones.

## Project Structure

### Documentation (this feature)

```text
specs/003-analisis-busqueda-natural/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── memoria-conversacion.md
│   └── revision-exhaustiva.md
└── tasks.md
```

### Source Code (repository root)

```text
datia/services/ai/interprete_mapeo.py    # frase sola, continuación o negativa
datia/services/ai/examen_preguntas.py    # revisión generada desde el territorio
datia/api/endpoints.py                   # deja de forzar que cada envío vaya suelto
datia/models (ConsultaConversacion)      # guarda la última lectura aceptada
datia/tests/test_interprete_mapeo.py
datia/tests/test_examen_preguntas.py
```

**Structure Decision**: Se queda en el monolito Django. El lector del catálogo decide si la frase va sola o continúa. La conversación del chat guarda esa lectura. La revisión exhaustiva vive en el examen, generada desde el mapa, no en una lista escrita a mano.

## Complexity Tracking

Sin violaciones. No aplica.
