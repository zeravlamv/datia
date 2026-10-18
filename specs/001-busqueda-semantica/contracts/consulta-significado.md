# Contract: Consulta por significado

Interfaz existente del chat. No se añade una pantalla nueva. La pregunta entra como texto y la respuesta usa las formas que el chat ya pinta.

## Entrada

- Texto de la pregunta, en español.
- Empresa y ejercicio ya elegidos en la sesión. Si falta uno de los dos, no hay cifra y se pide elegirlos.

## Salida cuando hay una sola entidad

Respuesta de texto con:

- la clase y el nombre visible encontrados;
- el identificador estable;
- la cifra del ejercicio, tomada del cálculo ya existente para esa entidad;
- si la entidad existe y el ejercicio no tiene dato, la frase de que no está cargado, sin importe inventado.

## Salida cuando hay que elegir

Misma forma de ambigüedad que el chat ya muestra: tipo de aviso y una lista de sugerencias. Cada sugerencia tiene una etiqueta legible y la pregunta que el usuario puede reenviar, incluyendo el identificador. Máximo cinco. Sin cifra en este paso.

## Salida cuando no hay coincidencia

Texto que dice que esa entidad no está en el catálogo de la empresa. Sin cifra.

## Salida cuando el índice no está listo

Texto que dice que la búsqueda por significado se está preparando. Si la misma pregunta también encaja en una regla fija, se responde por la regla fija y no se muestra este aviso en lugar de la cifra.

## Reglas de prioridad

1. Regla fija de ventas, stock por código, ranking o análisis del ejercicio.
2. Búsqueda por significado dentro de la empresa activa, solo con el modelo vigente y el lote en estado listo.
3. Aviso de índice no listo, o de entidad no encontrada.

## Aislamiento

Dos empresas no comparten candidatos ni cifras. Un código de artículo presente en la pregunta se conserva carácter a carácter.
