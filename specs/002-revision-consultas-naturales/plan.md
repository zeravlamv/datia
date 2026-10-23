# Implementation Plan: Revisión de consultas en lenguaje natural

**Branch**: `002-revision-consultas-naturales` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-revision-consultas-naturales/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Pedir todos los artículos con código, descripción y familia ya elige esas tres columnas del maestro mapeado, pero la lectura se corta en 100 filas y el chat solo pinta 30. La empresa activa tiene 1.616 artículos. La revisión quita ese corte cuando la frase pide el conjunto entero, enseña todas las filas y el recuento real, y añade esa pregunta al examen del contexto mapeado. El resto de lecturas (filtro, agrupación, suma, recuento, comparativa) sigue el mismo recorrido que ya contesta el catálogo. No se abre otro atajo.

## Technical Context

**Language/Version**: Python 3 sobre Django. El chat en el navegador sigue en el JavaScript ya existente.

**Primary Dependencies**: El lector del catálogo mapeado (`interprete_mapeo`), el formateo de la respuesta y la pestaña Examen. Sin modelo externo para el listado completo: la frase la resuelve la lectura directa.

**Storage**: Postgres de la aplicación para leer. La copia de artículos de la empresa 1 está en `datiadb_articulos` (columna `familia`, 1.616 filas). Producción sigue en SQL Server: un listado completo no puede depender de una cláusula que solo exista en Postgres.

**Testing**: Pruebas automáticas del plan, del SQL de los dos dialectos y de la corrección del examen. La comprobación en el navegador está en [quickstart.md](quickstart.md).

**Target Platform**: Servidor local en Windows y el mismo chat en el navegador.

**Project Type**: Aplicación web monolítica.

**Performance Goals**: El listado completo de hasta 2.000 artículos se ve, o se puede recorrer entero, en menos de 15 segundos (SC-005).

**Constraints**: No mapear tablas nuevas. No cambiar una pregunta del examen que ya coincidía. No inventar el nombre de una familia que no esté guardado en el artículo. La negativa fija sigue siendo «Esa pregunta no está en los datos mapeados.» Las herramientas de análisis semántico siguen siendo locales.

**Scale/Scope**: El caso que falla es un maestro de 1.616 artículos y tres columnas. El examen actual tiene 100 preguntas de lecturas ya cubiertas; se amplía con el listado completo, no se sustituye.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` sigue siendo la plantilla sin principios ratificados. No hay puertas que evaluar ni violaciones que justificar. El plan se limita a la especificación: listado completo con las columnas pedidas, un solo recorrido para el contexto mapeado y examen al cien por cien.

Revisión posterior al diseño: se mantiene. No hay servicio nuevo, no se añaden tablas y el corte de 100 filas solo desaparece cuando la frase pide el conjunto entero.

## Project Structure

### Documentation (this feature)

```text
specs/002-revision-consultas-naturales/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── listado-completo.md
│   └── examen-final.md
└── tasks.md              # lo crea /speckit-tasks, no este paso
```

### Source Code (repository root)

```text
datia/services/ai/interprete_mapeo.py     # listado sin tope y columna familia
datia/services/ai/compilador_mapeo.py     # el tope de 100 no aplica al conjunto entero
datia/services/ai/formatter.py            # recuento igual al número de filas devueltas
datia/static/js/dashboard/ia.js           # la tabla del listado no se queda en 30 filas
datia/services/ai/examen_preguntas.py     # pregunta del listado completo y su corrección
datia/tests/test_interprete_mapeo.py
datia/tests/test_examen_preguntas.py
```

**Structure Decision**: Se extiende el monolito actual. La frase entra por el chat que ya existe y el examen sigue en la pestaña Examen. No hay aplicación nueva ni contrato HTTP nuevo.

## Complexity Tracking

No aplica. La constitución no impone puertas y este plan no añade proyectos ni capas nuevas.

## Phase 0

Decisiones cerradas en [research.md](research.md). No quedan `NEEDS CLARIFICATION`.

## Phase 1

- Modelo de la lectura y del examen: [data-model.md](data-model.md)
- Contrato del listado: [contracts/listado-completo.md](contracts/listado-completo.md)
- Contrato del examen: [contracts/examen-final.md](contracts/examen-final.md)
- Validación: [quickstart.md](quickstart.md)
