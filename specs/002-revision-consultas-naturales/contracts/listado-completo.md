# Contract: Listado completo

Interfaz existente del chat. No se añade una pantalla. La pregunta entra como texto y la respuesta usa el informe que el chat ya pinta.

## Entrada

- Texto de la pregunta, en español.
- Empresa y ejercicio ya elegidos. El listado de fichas usa la empresa y no el ejercicio.

Frases de este contrato:

- «quiero ver una lista de todos los artículos con el código, la descripción y la familia»
- La misma petición para clientes o proveedores, con columnas que estén mapeadas.
- «los 10 primeros artículos con el código y la descripción» sigue siendo un corte, no este contrato.

## Salida cuando el maestro tiene fichas

Informe con:

- indicador de registros igual al número de fichas de la empresa;
- columnas Código, Descripción y Familia, en ese orden, si la frase las nombra;
- una fila por ficha, recorrible hasta la última;
- código con los ceros a la izquierda;
- familia igual al valor guardado en el artículo;
- sin filtro de ejercicio en la lectura.

## Salida cuando no hay fichas

Texto de que no hay registros. El recuento es cero. Sin filas de otra empresa.

## Salida cuando se pasa el tope de seguridad

Si hay más de 10.000 fichas, se muestran las primeras 10.000, se anuncia el total real y se dice que la lista está incompleta. Con el maestro actual (1.616 artículos) esta salida no se usa.

## Salida cuando la columna no está mapeada

Texto exacto: «Esa pregunta no está en los datos mapeados.» Sin listado de otras columnas presentado como si fuera la respuesta.

## Prioridad

1. Si la frase pide el conjunto entero, esta lectura gana a un ranking y al modelo.
2. Si pide un número concreto, se respeta ese número.
3. Si no habla de datos mapeados, no se fabrica un listado de artículos.
