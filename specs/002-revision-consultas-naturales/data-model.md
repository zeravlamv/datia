# Data Model: Revisión de consultas en lenguaje natural

No se crean tablas. Se precisan la lectura que ya devuelve el chat y la pregunta que ya guarda el examen en memoria para la empresa y el ejercicio activos.

## Lectura de listado

Lo que el usuario recibe cuando pide ver fichas, no un importe.

| Dato | Regla |
| --- | --- |
| Columnas | Solo las que la frase nombra y están mapeadas, en ese orden. Para artículos: código, descripción y familia. |
| Títulos | Código, Descripción y Familia cuando la frase usa esas palabras. |
| Filas | Una por ficha de la empresa. El código se muestra tal como está guardado, ceros incluidos. La familia es el valor guardado en el artículo. |
| Total | Igual al número de filas. En un listado completo, igual al número de fichas de esa empresa. |
| Corte | Vacío si la frase pide todos, todas, completo o listado completo. Si pide «los N», N filas. Si no dice nada de eso, se mantiene el corte actual. |
| Ejercicio | No filtra un listado de fichas. La empresa sí. |
| Tope de seguridad | Por encima de 10.000 filas la lista mostrada puede cortarse, pero el total anunciado sigue siendo el real y la respuesta dice que está incompleta. |

Relación: una lectura pertenece a una pregunta, una empresa y, si aplica, un ejercicio.

## Pregunta de examen

| Dato | Regla |
| --- | --- |
| Pregunta | Texto fijo, ligado a la empresa y al ejercicio de la petición. |
| Resultado esperado | Cifra, lista de importes, códigos en orden, o total más primeros códigos y familias. |
| Modo | `importe`, `conteo`, `lista`, `textos`, `cifras` o `listado`. El modo `listado` exige total, orden de códigos y presencia de la familia. |
| Veredicto | Coincidencia, otra cifra o sin respuesta. Coincidencia solo si el dato mostrado es el guardado. |

Estados de una pregunta en la pestaña: en espera, preguntando, coincidencia, otra cifra, sin respuesta. La revisión está aceptada solo cuando ninguna queda en otra cifra ni en sin respuesta.

## Relaciones que no cambian

- Artículo: código, descripción y familia en la ficha del artículo de la empresa.
- Venta sin la palabra pedido: albarán de cliente. Compra: documento de proveedor.
- Cliente que ha comprado un producto: cruce ya definido entre líneas, cabecera y clientes.
- Dos ejercicios en una gráfica: meses de cada ejercicio, no un listado de fichas.

## Validación

- Un listado completo de artículos sin familia, o con menos filas que el maestro, es inválido.
- Un listado completo filtrado por el ejercicio es inválido.
- Una pregunta de examen antigua que cambia de veredicto respecto al dato guardado es inválida.
- Una pregunta que no habla de datos mapeados y aun así muestra una cifra de artículos o de ventas es inválida.
