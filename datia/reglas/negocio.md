# Reglas de negocio del chat

El chat lee todos los `.md` de esta carpeta, en orden de nombre y de arriba abajo, y se queda con la primera regla que encaja.
El año de un informe o de los kilos sale de la frase. Si la frase no trae año, usa el del hilo. Si el hilo tampoco, usa el ejercicio seleccionado.

`motor: informe` y `motor: kilos` los aplica el chat en cuanto el fichero está guardado.
`motor: mapeo` lo aplica el intérprete de columnas mapeadas. El bloque deja escrita la regla.
`motor: cobertura` obliga a leer la frase entera antes de mostrar una respuesta.
La pestaña Actualidad no usa estos ficheros. Un top o un resumen comercial sale de las tablas mapeadas, no de un informe preparado.

:::regla
id: lectura-completa
motor: cobertura
cuando: la frase nombra un corte o una operación que las reglas, el diccionario o el mapeo ya conocen
nota: se lee la frase entera antes de elegir qué mostrar. La respuesta solo vale si cubre todos esos significados. Un total del año no cubre un trimestre, un semestre, un mes ni un día. Una cifra en euros no cubre kilos ni unidades. Si ningún motor cubre la frase, no se muestra una respuesta a medias.
:::

## Informes con nombre propio

:::regla
id: coste-por-100
motor: informe
informe: finanzas.per100
contiene: coste por cada 100 | costes por cada 100 | coste por 100 | costes por 100 | per 100 | estructura de costes
anio: frase, hilo, ejercicio
:::

:::regla
id: ratios
motor: informe
informe: financiera.ratios
contiene: ratios financieros | ratio financiero | ratios | ratio | liquidez | test acido | solvencia | endeudamiento | roe | roa | margen neto | margen ebitda | cobertura de interes | fondo de maniobra
anio: frase, hilo, ejercicio
:::

:::regla
id: prevision-tesoreria
motor: informe
informe: tesoreria.forecast
contiene: prevision de tesoreria | forecast de tesoreria | proyeccion de tesoreria | tesoreria prevista | prevision de caja
anio: frase, hilo, ejercicio
:::

:::regla
id: pool-bancario
motor: informe
informe: tesoreria.pool_bancario
contiene: pool bancario | linea de credito | confirming | factoring
anio: frase, hilo, ejercicio
:::

:::regla
id: tesoreria-mensual
motor: informe
informe: tesoreria.caja_mensual
contiene: tesoreria mensual | tesoreria por mes | caja mensual | evolucion de tesoreria | evolucion de caja
anio: frase, hilo, ejercicio
:::

:::regla
id: tesoreria
motor: informe
informe: tesoreria.resumen
contiene: tesoreria
anio: frase, hilo, ejercicio
:::

:::regla
id: presupuesto
motor: informe
informe: presupuestos.comparativa
contiene: presupuesto | presupuestos | budget
anio: frase, hilo, ejercicio
:::

:::regla
id: analisis-financiero
motor: informe
informe: finanzas.resumen_ejercicio
contiene: analisis financiero | analisis financiera | analisis de finanzas | informe financiero | informe financiera | informe de finanzas | resumen financiero | resumen financiera | resumen de finanzas
anio: frase, hilo, ejercicio
:::

## Kilos y unidades por mes

«Vendidos» es una venta y «comprados» es una compra. Esa decisión solo vale en esta regla, no en el resto de las frases.
La fórmula del kilo es el importe neto dividido por el precio cuando el precio no es cero. No se usa la suma de unidades.
Si la frase no dice el mes, el total del año lo calcula el constructor de consultas.
«Qué clientes han comprado el producto» sigue siendo una venta al cliente, no una compra a proveedor.

:::regla
id: kilos-por-mes
motor: kilos
señal: kilos | kg | kilogramo*
corte: por mes | mensual | mensuales | mes a mes
venta: vendid* | venta | ventas
compra: comprad* | compra | compras | proveedor | proveedores
anio: frase, hilo, ejercicio
:::

## Lectura de datos mapeados

El modelo no escribe SQL. Elige campos del catálogo y el compilador arma el SELECT.
Solo se leen columnas ya mapeadas y relaciones que ya existen. No se mapean tablas nuevas.
Fuera de esta lectura quedan el porqué de negocio, el pronóstico y cualquier tabla que no esté mapeada.

:::regla
id: resumen-comercial
motor: mapeo
cuando: la frase dice resumen y no dice financiero, finanzas, ingresos, gastos ni resultado, y no pide a la vez ventas y compras
nota: es el total del año, el top 10 de artículos y el top 10 de clientes. Si la frase dice compras, el tercer bloque es el top 10 de proveedores. El año no forma parte de la frase del top, para que no se convierta en un filtro. Los artículos suman el importe neto de la línea. Los clientes y los proveedores suman la cabecera.
:::

:::regla
id: han-comprado-es-venta
motor: mapeo
cuando: la frase junta clientes con han comprado o comprado, y no dice pedido
nota: es un albarán de cliente. Solo es compra a proveedor si la frase dice compra o proveedor. Solo es un pedido si la frase dice pedido.
:::

:::regla
id: agrupacion-articulos
motor: mapeo
cuando: la frase agrupa por artículo o producto
nota: la cifra es el importe neto de la línea. Si la línea tiene importe de coste, se suma. Si tiene las tres claves del albarán, se cuentan los albaranes distintos.
:::

:::regla
id: precio-medio
motor: mapeo
cuando: la frase dice precio medio, ticket medio o importe medio, sin un cliente, un artículo o un proveedor concreto, y sin pedir ventas y compras a la vez
nota: es el neto dividido por el número de albaranes. No hereda un ranking anterior. Promedio de ventas del ejercicio no es esta regla: sigue siendo la media SQL del examen.
:::

:::regla
id: dato-no-mapeado
motor: mapeo
cuando: la frase nombra un dato concreto que no es un informe de este fichero ni una columna mapeada
nota: la respuesta es exactamente «Esa pregunta no está en los datos mapeados.» Kilos y unidades vendidos o comprados se responden aunque no exista una columna con ese nombre.
:::

:::regla
id: lectura-mapeada
motor: mapeo
cuando: la frase pide un filtro, varios filtros, un grupo, una suma, un conteo, una media, un listado o una gráfica de datos mapeados
nota: el corte numerado va de 1 a 100. Todos, todas, todo, completo o completa quita el límite y no convierte la consulta en un listado. El año que se muestra es el de la lectura. Un atajo de informe solo puede adelantarse si la frase no nombra datos mapeados.
:::

:::regla
id: cruces
motor: mapeo
cuando: la frase cruza dos tablas mapeadas
nota: solo se usan las relaciones guardadas. Cartera de efectos enlaza con clientes y con proveedores por el código contable, no por el código del cliente. El código de cliente no está en las líneas. La cabecera y la línea del albarán se unen por empresa, ejercicio, serie y número de albarán. El pedido se une por empresa, ejercicio, serie y número de pedido.
:::

## Memoria del hilo

:::regla
id: memoria
motor: mapeo
cuando: hay una conversación abierta de la misma empresa
nota: se recuerda la última lectura aceptada. Primero se lee la frase sola. Si ya trae clase, concepto y forma, es una pregunta nueva y no hereda filtros, columnas, concepto ni corte. Si no trae año y el hilo sí, hereda ese año. «Y en 2024» sustituye solo el año. Cambiar de empresa o abrir otra conversación no arrastra la memoria.
:::

:::regla
id: top-y-todos
motor: mapeo
cuando: la frase es Top N, los N primeros, o Todos, y hay una lectura anterior con concepto
nota: Top N cambia solo el corte. Sin lectura anterior, se pregunta si busca productos, clientes o proveedores. Todos, sobre una cifra agrupada, solo quita el límite.
:::

:::regla
id: ambiguedad
motor: mapeo
cuando: siguen encajando dos conceptos mapeados o dos relaciones, y ni la frase ni el hilo dicen cuál
nota: se preguntan esas dos opciones y no se calcula una cifra mezclada. El aviso no sustituye la última lectura aceptada. Guarda la pregunta pendiente. Una respuesta corta, «clientes», «proveedores» o «de cliente», cierra esa pregunta y no vuelve a preguntarla. Una frase posterior que ya se entiende sola ignora lo pendiente. Si la frase nombra cliente y proveedor a la vez, sigue siendo ambigua. Una duda de relación no se resuelve solo porque el hilo hable de cliente o de proveedor. El número de líneas de albarán, sin hilo, pregunta si es el de cliente o el de proveedor. Un listado con la razón social pregunta si es de clientes o de proveedores.
:::

## Atajos que no pasan por el mapeo

:::regla
id: estado-general
motor: mapeo
cuando: la frase es exactamente como va, como vamos, situacion, balance, report o status, o contiene informe anual, informe general, situacion global, resumen anual o balance anual
nota: responde el informe de estado del ejercicio. No se aplica si la frase es un pedido concreto.
:::

:::regla
id: calculo-python
motor: mapeo
cuando: la frase pide media móvil, normalizar, pronóstico, tendencia o correlación
nota: lo calcula el módulo de cálculo, no una columna mapeada.
:::
