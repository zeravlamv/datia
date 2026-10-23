# Research: Revisión de consultas en lenguaje natural

## Decision: «Todos» quita el corte de filas

- **Decision**: Si la frase pide el conjunto entero (`todos`, `todas`, `todo`, `completo`, `completa`, `listado completo`), el listado de un maestro no lleva tope. En Postgres no se añade `LIMIT`. En SQL Server no se añade `TOP`. El recuento que ve el usuario es el número de filas devueltas y coincide con las fichas de esa empresa.
- **Rationale**: La frase «quiero ver una lista de TODOS artículos con el código y descripción y Familia» ya arma un listado de `CodigoArticulo`, `DescripcionArticulo` y `CodigoFamilia`, pero el plan deja el límite en 100. `_limite` nunca pasa de 100 y `validar_plan` vuelve a recortar a 100. La empresa 1 tiene 1.616 artículos en `datiadb_articulos`. El chat, además, pinta como máximo 30 filas del informe (`anadirTablaInforme(..., 30)`). Por eso el usuario ve unos pocos.
- **Alternatives considered**: Subir el tope a 2.000 (sigue siendo una muestra si el maestro crece, y el usuario pidió todos). Paginar en silencio (el recuento anunciado dejaría de ser el total si se cuenta solo la página). Pedir al modelo local que reescriba la frase (más lento y no hace falta: la lectura directa ya elige las columnas).

## Decision: La pantalla muestra todas las filas del listado completo

- **Decision**: Cuando la respuesta es un listado completo, la tabla del chat se puede recorrer hasta la última fila y el indicador de registros es el total, no 30 ni 100. Un listado que no pide «todos» puede seguir acotado.
- **Rationale**: Aunque la consulta devolviera 1.616 filas, el informe actual corta la vista en 30. El criterio de éxito exige ver el catálogo o poder recorrerlo en menos de 15 segundos. 1.616 filas de tres columnas caben en una sola respuesta.
- **Alternatives considered**: Un botón de «ver más» que no dice el total (incumple el recuento). Exportar a un fichero (no es la respuesta del chat).

## Decision: Los títulos del listado son las columnas pedidas

- **Decision**: Si el usuario nombra código, descripción y familia, los títulos visibles son Código, Descripción y Familia. Los valores siguen siendo el código de artículo, la descripción y el valor guardado en `familia`. Los ceros a la izquierda del código se conservan.
- **Rationale**: Hoy los títulos salen como Articulo, DescripcionArticulo y Familia. La columna de familia sí viaja en la consulta, pero el rótulo del código y el de la descripción no dicen lo que el usuario pidió. El valor de familia es el que está guardado en el artículo; no se busca un nombre en otra tabla.
- **Alternatives considered**: Dejar el nombre técnico de la columna (el usuario ya dijo que no se entiende). Unir con una tabla de familias no mapeada (fuera del contexto actual).

## Decision: El listado completo no pasa por el modelo ni por el ranking

- **Decision**: La lectura directa reconoce el listado completo y no llama al modelo. Las palabras de ranking (`top`, `mejores`, `peores`) siguen yendo al ranking que ya existe, salvo que la frase pida a la vez el conjunto entero: en ese caso gana el listado. El examen no usa esas palabras de ranking en la pregunta nueva.
- **Rationale**: La especificación pide un solo recorrido para las lecturas del contexto mapeado y, a la vez, que una pregunta que ya coincidía no cambie. Reescribir ahora todos los rankings movería respuestas que el examen ya da por buenas. El fallo medido es el listado, y ese ya entra por el catálogo antes que por cualquier otro atajo.
- **Alternatives considered**: Hacer que cualquier frase con «artículos» ignore el ranking (cambiaría «mejores artículos»). Llamar al modelo de 14b para decidir el tope (innecesario y más lento que los 15 segundos).

## Decision: El examen suma la pregunta del catálogo entero y exige el cien por cien

- **Decision**: Se mantiene el banco actual y se añade la pregunta del listado completo de artículos con código, descripción y familia. Lo esperado es el número de artículos de la empresa y los primeros códigos, en orden, con su familia. La corrección mira el recuento, el orden de esos códigos y que la columna de familia esté. La revisión se acepta cuando todas las preguntas del banco, las antiguas y esta, coinciden con el dato guardado. Las frases ajenas al mapeo siguen fuera de ese cien por cien y reciben la negativa fija.
- **Rationale**: El banco de 100 preguntas no incluye «todos» ni la familia. Corregir solo con los primeros códigos daría por buena una muestra de 30. El recuento es la prueba de que no se ha cortado.
- **Alternatives considered**: Sustituir una de las 100 preguntas (se perdería una lectura que ya coincidía). Guardar los 1.616 códigos en la ficha del examen (ilegible y frágil). Lanzar las 100 preguntas en esta fase de diseño (el examen lo lanza el usuario; aquí solo se define la pregunta y cómo se corrige).

## Decision: El tope de seguridad queda por encima del maestro actual

- **Decision**: Un listado completo se devuelve entero mientras no pase de 10.000 filas. Si pasara, la respuesta dice el total real y que la lista mostrada está incompleta. Con 1.616 artículos ese aviso no aparece.
- **Rationale**: Hace falta un freno para no volcar una tabla enorme por una frase mal leída, sin convertir otra vez «todos» en 100 filas. El criterio de éxito habla de hasta 2.000 artículos; 10.000 deja margen sin cambiar el caso actual.
- **Alternatives considered**: Sin freno (un maestro futuro podría bloquear el chat). Freno en 2.000 (demasiado cerca del tamaño real y volvería a recortar en cuanto crezca el catálogo).
