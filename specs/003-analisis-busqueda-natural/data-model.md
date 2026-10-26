# Data Model: Análisis de la búsqueda en lenguaje natural

## Lectura aceptada

Último resultado que el chat aceptó en una conversación y una empresa. Es lo que una continuación puede completar.

| Campo | Sentido |
| --- | --- |
| conversacion | Charla del chat en la que se aceptó |
| empresa | Empresa activa. Otra empresa no la ve |
| clase | Cifra, listado, agrupación o comparación |
| conceptos | Qué datos mapeados intervienen |
| columnas | Columnas pedidas, en el orden de la frase |
| filtros | Filtros aplicados |
| corte | Conjunto entero, o el número dicho |
| periodo | Ejercicio o ejercicios de la lectura. Vacío si es una ficha maestra |
| forma | Tabla o gráfica |
| aceptada_en | Momento en que sustituyó a la lectura anterior de esa conversación |

**Reglas**:

- Solo se guarda si la respuesta es una lectura, no una negativa.
- Una conversación tiene como mucho una lectura vigente. La nueva aceptada reemplaza a la anterior.
- Una conversación nueva empieza sin lectura.
- Cambiar de empresa no borra la memoria de la otra: simplemente no se usa.

## Pregunta clasificada

Cualquier frase enviada, después de decidir si va sola, continúa o se rechaza.

| Campo | Sentido |
| --- | --- |
| frase | Texto del usuario |
| vinculo | `sola`, `continuacion` o `rechazo` |
| lectura | Lectura con la que se contesta. Vacía si es rechazo |
| hereda | Partes tomadas de la lectura anterior. Vacío si es sola o rechazo |
| sustituye | Partes que la frase nueva cambia. Vacío si es sola o rechazo |

**Reglas**:

- Si la frase sola produce una lectura completa, el vínculo es `sola` aunque también pudiera leerse como continuación.
- Si la frase sola no produce lectura y el completado con la última aceptada sí, el vínculo es `continuacion`.
- En una continuación, lo no dicho se conserva y lo dicho sustituye. No se suman dos valores en conflicto para la misma parte.
- Si no hay lectura aceptada, una frase incompleta es `rechazo`.
- El rechazo no modifica la lectura aceptada.

## Territorio mapeado

Lo que la empresa activa puede leer hoy. No crece para la revisión.

| Pieza | Qué tiene que aparecer al menos una vez |
| --- | --- |
| Columna legible | Una pregunta que la muestra, la filtra o la agrega, según lo que esa columna permita |
| Relación usable | Una pregunta que cruza los dos conceptos que esa relación une |
| Forma de lectura | Filtrar, varios filtros, agrupar, sumar, contar, promediar, máximo, mínimo, listar, conjunto entero, número concreto, un periodo, comparación de periodos, tabla, gráfica |
| Pareja de memoria | Por cada forma, una continuación que cambia una sola parte y una pregunta posterior que se entiende sola |

**Reglas**:

- Una ficha maestra en conjunto entero no lleva filtro de ejercicio.
- Un movimiento usa el ejercicio elegido salvo que la frase nombre otro periodo o varios.
- Sin la palabra pedido, el documento es el albarán. Con pedido, es el pedido.
- «Han comprado» con clientes es una venta.

## Revisión

Conjunto generado desde el territorio, más frases que deben rechazarse.

| Campo | Sentido |
| --- | --- |
| empresa | Empresa de la que sale el territorio |
| ejercicio | Ejercicio de los movimientos |
| preguntas | Cada una con frase, vínculo, resultado esperado y pieza del territorio que cubre |
| probes | Frases de fuera, con la negativa esperada |
| incompleta | Sí, si falta una columna, una relación, una forma o una pareja |

**Estados**:

1. Preparada: se ve entera, todavía sin veredictos.
2. En curso: cada pregunta recibe respuesta.
3. Aceptada: territorio completo, todas las preguntas coinciden, todos los probes rechazan.
4. Rechazada: falta territorio, hay una no coincidencia o un probe que no se rechazó.

Una pregunta que coincidió en una revisión anterior y vuelve a incluirse debe seguir en coincidencia. Ampliar el conjunto no autoriza a perderla.

## Respuesta visible

Lo que queda en el chat.

| Campo | Sentido |
| --- | --- |
| tipo | Cifra, listado, gráfica o negativa |
| columnas | Títulos comprensibles, en la misma fila si es listado |
| recuento | Número real de fichas cuando el corte es el conjunto entero |
| recorrida | Sí, si se puede llegar a la última fila |
| texto | La negativa fija, cuando el tipo es negativa |

Un conjunto entero cuyo recuento es real pero no se puede recorrer hasta el final no coincide.
