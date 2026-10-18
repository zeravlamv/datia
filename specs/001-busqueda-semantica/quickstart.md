# Quickstart: Búsqueda semántica del negocio

Validación manual sobre la empresa de prueba ya cargada (empresa 1, ejercicio 2025). No hace falta una pantalla nueva: se usa el chat.

## Antes de probar

1. Ollama en marcha en el equipo.
2. Modelo de embeddings `nomic-embed-text` descargado en Ollama.
3. Proveedor de embeddings local apuntando a Ollama, no a la huella hash.
4. Índice de cliente, artículo y cuenta reconstruido para la empresa 1 con ese modelo. Hasta que el lote figure como listo, las pruebas de significado deben mostrar el aviso de preparación y las reglas fijas deben seguir respondiendo.

Detalle de campos y estados: [data-model.md](data-model.md). Forma de la respuesta: [contracts/consulta-significado.md](contracts/consulta-significado.md).

## 1. Una entidad, una cifra

- Preguntar las ventas de un cliente con el nombre ligeramente cambiado, no el código.
- Esperado: un solo cliente, el de esa empresa, y el importe del ejercicio 2025 igual al que ya devuelve la pregunta exacta de ese cliente.
- Repetir con la descripción aproximada de un artículo existente y con el nombre aproximado de una cuenta del plan.

## 2. Lo que ya funciona no cambia

Repetir, con la misma empresa y ejercicio, al menos estas preguntas y guardar la cifra:

- ventas a un cliente concreto bien escrito;
- stock de un código de artículo;
- artículos más vendidos de un año dicho en la pregunta;
- análisis de ese ejercicio.

Esperado: la misma entidad y la misma cifra que antes de activar el índice.

## 3. Ambos y nadie

- Preguntar con un texto que se parezca a dos clientes. Esperado: lista de hasta cinco opciones, sin importe. Elegir una y obtener solo la cifra de esa.
- Preguntar por un nombre que no existe. Esperado: mensaje de que no está en el catálogo, sin importe.

## 4. Cambio de modelo

- Marcar un modelo distinto o vaciar el lote.
- Durante la reconstrucción, repetir la pregunta de stock por código. Esperado: respuesta de la regla fija.
- Repetir una pregunta que solo puede resolverse por significado. Esperado: aviso de que el índice se está preparando, sin usar vectores del modelo anterior.
- Al cerrar el lote, repetir esa pregunta. Esperado: la entidad correcta con el modelo nuevo.

## Hecho cuando

Se cumplen los criterios SC-001 a SC-006 de [spec.md](spec.md): al menos 30 preguntas aproximadas con 90 % de entidad correcta, 100 % de cifras coincidentes con el dato conocido, 10 preguntas fijas sin cambio, la elección en un paso, ningún vector viejo tras el cambio de modelo, y respuesta en menos de 5 segundos con el índice listo.
