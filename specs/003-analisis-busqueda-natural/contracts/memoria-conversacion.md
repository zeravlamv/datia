# Contrato: Memoria de la conversación

La pregunta siguiente puede continuar la última lectura aceptada o no. El chat no elige el vínculo por costumbre: lo decide con estas reglas, en este orden.

## Entrada

- La frase nueva.
- La empresa activa.
- La conversación abierta. Si no hay conversación, la frase no tiene lectura anterior.
- La última lectura aceptada de esa conversación, si existe.

## Decisión

1. Si la frase nombra un dato concreto que no está mapeado, la respuesta es exactamente «Esa pregunta no está en los datos mapeados.» No se rellenan huecos con la lectura anterior. La lectura aceptada no cambia.
2. Se intenta leer la frase sola, con los datos mapeados de la empresa.
3. Una lectura es completa cuando, sin memoria, ya hay clase, concepto y forma. Si lo es, la frase es nueva. No se usan filtros, columnas, concepto, corte ni periodo de la anterior.
4. Si no es completa y hay una lectura aceptada, se completan solo los huecos con esa lectura. Lo que la frase nueva dice sustituye a la parte correspondiente.
5. Si ese completado es una lectura, la frase es continuación.
6. Si no lo es, la respuesta es exactamente «Esa pregunta no está en los datos mapeados.» La lectura aceptada no cambia.
7. Una frase que no nombra datos mapeados y tampoco completa la anterior no muestra una cifra ni un listado de la empresa.

## Salida

- Vínculo: sola, continuación o rechazo.
- Lectura con la que se contesta, o ninguna.
- Si es continuación, qué se heredó y qué se sustituyó.
- Si la lectura se acepta, `/qa` la devuelve en la respuesta. El guardado del mensaje la escribe en `lectura_aceptada` de esa misma conversación y esa empresa. `/qa` no escribe la fila: en la primera pregunta todavía no existe.
- Si la respuesta es rechazo, o el aviso «Esa pregunta admite más de una lectura. Indica cuál quieres.», el campo devuelto va vacío y el guardado no sustituye la lectura anterior.

## Límites

- Otra empresa no ve esta lectura.
- Una conversación nueva empieza sin ella.
- Varias lecturas aceptadas: la continuación usa solo la última.
- Una negativa no pasa a ser la memoria.
- Si la frase sola y la continuación fueran ambas posibles, manda la frase sola.
- Hay dos lecturas cuando, aplicadas las reglas ya cerradas (sin «pedido» es albarán, y «han comprado» con clientes es una venta), siguen encajando dos conceptos mapeados o dos relaciones usables y la frase no nombra cuál. Si nombra uno, ese es el que vale. Si siguen las dos, la respuesta es exactamente «Esa pregunta admite más de una lectura. Indica cuál quieres.» Ese aviso no sustituye a la última lectura aceptada.

## Parejas que la revisión debe incluir

Para cada forma de lectura del territorio:

- Una frase posterior incompleta que cambia una sola parte (periodo, agrupación, corte o columna) y conserva el resto.
- Una frase posterior que se entiende sola y no conserva nada.

Las dos se comparan con el dato guardado de su propia lectura, no de la frase anterior.
