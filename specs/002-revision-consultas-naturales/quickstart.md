# Quickstart: Revisión de consultas en lenguaje natural

Comprueba el listado completo y que el examen lo incluye. No hace falta lanzar las cien preguntas para ver la ficha nueva; el cierre del cien por cien sí las lanza.

## Antes

- Aplicación en marcha en `http://127.0.0.1:8001/`.
- Empresa UNION INDUSTRIAS DEL CAFE S.L.U. y ejercicio 2025.
- Artículos de esa empresa ya cargados: 1.616, con código, descripción y familia.

## Prueba automática

Desde `e:\datia`, un comando cada vez:

```text
python -m unittest discover -s datia/tests -p test_interprete_mapeo.py -v
python -m unittest discover -s datia/tests -p test_examen_preguntas.py -v
```

Tiene que pasar, en concreto:

- la frase de todos los artículos con código, descripción y familia no lleva corte de filas;
- la lectura pide el código, la descripción y la familia, y no filtra por ejercicio;
- el mismo listado en SQL Server no usa un corte de Postgres;
- la corrección del examen no da por buena una muestra de 30 filas si el total no es 1.616;
- una pregunta que ya coincidía sigue coincidiendo.

## Prueba en el chat

1. Abrir el chat con esa empresa y ese ejercicio.
2. Preguntar: `quiero ver una lista de todos los artículos con el código, la descripción y la familia`.
3. Comprobar que el recuento es 1.616, que se pueden recorrer las filas hasta el final, y que hay columnas Código, Descripción y Familia.
4. El primer código conserva los ceros (`0000000001`) y la familia es la guardada en esa ficha.
5. Preguntar `los 10 primeros artículos con el código y la descripción` y comprobar que son 10 filas, no 1.616.

## Prueba del examen

1. Abrir Auto entreno y la pestaña Examen.
2. Ver la pregunta del listado completo, con el total y los primeros códigos, sin pulsar el botón.
3. Pulsar Hacer el examen.
4. El resumen queda con todas las preguntas en coincidencia, incluida la del listado y las que ya estaban.

## Qué no debe ocurrir

- Un listado de 30 o de 100 artículos presentado como si fueran todos.
- La familia ausente o sustituida por un nombre que no está en la ficha.
- El ejercicio 2025 usado como filtro de las fichas.
- Una cifra de ventas como respuesta a una pregunta que no habla de datos mapeados.
