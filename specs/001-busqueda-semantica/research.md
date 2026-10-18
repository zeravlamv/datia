# Research: Búsqueda semántica del negocio

## Decision: El significado se calcula en local con un modelo de embeddings de Ollama

- **Decision**: Usar Ollama con el modelo `nomic-embed-text` para convertir textos de negocio y preguntas en vectores. El proveedor queda fijado en el entorno local (`DATIA_EMBED_PROVIDER=ollama`). No se recorta el vector a 384 números.
- **Rationale**: En este equipo Ollama ya está instalado y el chat ya lo usa. `nomic-embed-text` no está instalado todavía; hay que descargarlo una vez. El modelo previsto `all-MiniLM-L6-v2` no carga y está pensado sobre todo para inglés. La huella SHA-256 actual no distingue frases y la búsqueda semántica permanece apagada mientras solo exista esa huella.
- **Alternatives considered**: Seguir con la huella hash (no cumple el 90 % de aciertos). Reparar `sentence-transformers` en el proceso de la aplicación (dependencia rota y peor en español). Enviar los textos a un servicio externo (queda fuera: las preguntas no salen de la empresa).

## Decision: El chat de lenguaje sigue en los modelos ya instalados

- **Decision**: No se cambia el modelo que redacta o genera SQL. Con los campos de configuración vacíos, una pregunta normal sigue eligiendo la familia `qwen2.5:3b` y una pregunta financiera `qwen2.5:14b-instruct-q4_k_m`. Esos modelos no calculan la cifra de la búsqueda por significado.
- **Rationale**: La especificación exige que el importe salga del dato ya cargado. El modelo de embeddings solo elige la entidad.
- **Alternatives considered**: Usar `qwen3:30b` para toda pregunta (más lento, no mejora la cifra). Dejar que el modelo de chat invente el importe (incumple el criterio de cero cifras inventadas).

## Decision: Un índice propio de entidades, separado de las plantillas SQL

- **Decision**: Guardar en Postgres un índice de significados por empresa para tres clases: cliente (`datia_cliente`, 14.011 filas en total), artículo (`datia_articulos`, 9.502) y cuenta (`datiadb_plancuentas`, 7.336). Cada fila guarda el texto visible, el identificador estable, la empresa, el identificador del modelo y el vector. `tpl_ai_embeddings` (123 filas de plantillas) no se usa para elegir la entidad.
- **Rationale**: Mezclar plantillas de SQL con nombres de clientes hace que una pregunta de ventas caiga en una plantilla genérica. El volumen por empresa cabe en una comparación acotada a esa empresa.
- **Alternatives considered**: Reutilizar solo `tpl_ai_embeddings` (demasiado pequeño y de otro propósito). Indexar documentos, correos y asientos (fuera de alcance de esta versión).

## Decision: La comparación de la primera versión no exige pgvector

- **Decision**: Comparar el vector de la pregunta solo con las entidades de la empresa activa, en memoria, con similitud coseno. `pgvector` no está instalado (extensiones actuales: `plpgsql`, `pgcrypto`). Se pasa a un índice nativo de Postgres si una empresa supera unos 20.000 textos o si la respuesta pasa de 5 segundos.
- **Rationale**: El catálogo actual es de miles de filas por tipo, no de millones. Instalar una extensión nueva no es necesario para cumplir el tiempo de la especificación.
- **Alternatives considered**: Instalar `pgvector` ahora (más operación, sin beneficio medido todavía). Recorrer todas las empresas en cada pregunta (rompe el aislamiento por empresa y el tiempo).

## Decision: Las reglas fijas ganan a la búsqueda por significado

- **Decision**: Si la pregunta ya tiene respuesta comprobada (ventas a un cliente nombrado, stock de un código, ranking, análisis del ejercicio), se responde por esa regla. La búsqueda por significado solo entra cuando la frase señala un cliente, un artículo o una cuenta y la regla fija no ha cerrado la respuesta. Un código de artículo no se corrige. Si hay varios candidatos por encima del umbral y demasiado próximos, se devuelve la elección ya usada por el chat (sugerencias con la consulta a repetir).
- **Rationale**: La historia 2 exige que las cifras actuales no cambien. La historia 1 cubre el nombre aproximado que esas reglas no reconocen.
- **Alternatives considered**: Sustituir las reglas por vectores (riesgo de cambiar importes ya aceptados).

## Decision: Cambiar de modelo invalida el índice antes de responder

- **Decision**: Cada vector guarda el identificador del modelo que lo creó. Si el modelo activo no coincide, la búsqueda por significado responde que el índice se está rehaciendo y no usa los vectores viejos. Las reglas fijas siguen contestando durante la reconstrucción. Al terminar, solo quedan vectores del modelo nuevo.
- **Rationale**: Un vector de huella hash y un vector de `nomic-embed-text` no son comparables. La especificación prohíbe usar el índice anterior.
- **Alternatives considered**: Comparar vectores de longitudes distintas rellenando con ceros (produce coincidencias falsas).
