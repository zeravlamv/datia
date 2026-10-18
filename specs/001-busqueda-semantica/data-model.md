# Data Model: Búsqueda semántica del negocio

## Entidad de negocio

Texto reconocible de un cliente, un artículo o una cuenta, siempre de una empresa.

| Campo | Regla |
| --- | --- |
| Empresa | Obligatoria. Ninguna consulta cruza empresas. |
| Clase | `cliente`, `articulo` o `cuenta`. |
| Identificador | Código estable dentro de la empresa y la clase. No se reescribe al reindexar. |
| Texto visible | Nombre o descripción que el usuario puede decir. Vacío no se indexa. |
| Origen | `datia_cliente`, `datia_articulos` o `datiadb_plancuentas`. |

Validación: un mismo identificador y clase solo tiene un texto vigente por empresa. Si el origen desaparece, la fila del índice se retira en la siguiente reconstrucción.

## Cifra de empresa

No es una tabla nueva. Es el resultado que ya calculan las respuestas de ventas, stock, rankings y análisis del ejercicio para una empresa y un ejercicio.

Relación: la búsqueda elige como máximo una entidad (o una lista corta para elegir). La cifra se pide después a la respuesta ya comprobada de esa entidad. Si no hay cifra cargada para el ejercicio, se dice que la entidad existe y que el dato no está cargado.

## Índice de significados

| Campo | Regla |
| --- | --- |
| Empresa, clase, identificador | Identidad de la fila. |
| Texto indexado | Copia del texto visible en el momento de la reconstrucción. |
| Modelo | Identificador exacto del modelo de embeddings usado. |
| Vector | Lista numérica de la longitud nativa de ese modelo. |
| Estado del lote | `construyendo` o `listo`, compartido por todas las filas de un modelo y una empresa. |

Transiciones:

1. Modelo nuevo o texto de origen cambiado → el lote de esa empresa pasa a `construyendo`.
2. Durante `construyendo`, la búsqueda por significado no lee filas de otro modelo.
3. Cuando todas las entidades de la empresa tienen vector del modelo activo → `listo`.
4. Las filas de un modelo anterior se borran al cerrar el lote nuevo.

Validación: no se compara un vector con otro de distinto modelo o distinta longitud.

## Pregunta con regla fija

No se almacena en este índice. Sigue el camino actual de ventas a un cliente nombrado, stock por código, ranking y análisis del ejercicio. Si esa regla responde, el índice no la sustituye.

## Elección ambigua

No persiste. Si dos o más entidades de la misma clase superan el umbral y la diferencia entre la primera y la segunda es pequeña, la respuesta ofrece hasta cinco opciones. Cada opción repite la pregunta con el identificador elegido. No se muestra ninguna cifra hasta esa elección.
