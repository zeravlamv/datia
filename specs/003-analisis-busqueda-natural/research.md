# Research: Análisis de la búsqueda en lenguaje natural

## 1. Cada envío va suelto

**Decision**: La memoria de la última lectura aceptada entra en el recorrido del catálogo, antes de contestar. El punto de entrada deja de anular el turno anterior.

**Rationale**: En `qa_query` el historial está apagado a propósito: cada pregunta se trata como independiente y no se guarda `ai_last_query`. Con eso, «y en 2024» o «los mismos por cliente» no tienen de dónde completarse. Tampoco se puede demostrar que una frase posterior, entendible sola, no arrastra filtros.

**Alternatives considered**: Dejar el chat sin memoria y pedir al usuario que repita la frase entera. No cumple la especificación. Guardar solo el texto anterior y pegarlo delante de la frase nueva mezclaría también las preguntas que se entienden solas.

## 2. No reabrir el mezclador antiguo

**Decision**: No se usa `ConversationManager.enrich` como regla de memoria. Ese gestor, cuando el router lo llama, parte del estado previo y le superpone lo nuevo de la frase. Toda frase hereda. La especificación exige lo contrario cuando la frase se entiende sola.

**Rationale**: El gestor arrastra entidad, métrica, periodo y límite. Una pregunta posterior de otro concepto se contaminaría. Además está desconectado del plan del catálogo, que es el que ya produce las lecturas fiables.

**Alternatives considered**: Corregir el gestor para que a veces no mezcle. Seguirían existiendo dos memorias. La lectura aceptada del catálogo es la única que la revisión puede comparar con el dato guardado.

## 3. Cómo distinguir continuación y pregunta nueva

**Decision**: Primero se intenta la lectura de la frase sola. Si nombra datos mapeados y produce una lectura completa, es pregunta nueva y no se consulta la memoria. Si no produce lectura y, al rellenar solo los huecos con la última lectura aceptada, sí la produce, es continuación. Si tampoco, es la negativa fija y la memoria no cambia.

**Rationale**: «Se entiende sola» es comprobable: el mismo lector que ya clasifica una frase aislada devuelve una lectura. La continuación solo existe cuando ese intento falla y el completado con la lectura anterior no. Si las dos fueran posibles, manda la frase sola, como pide la especificación.

**Alternatives considered**: Una lista de muletillas («y», «ahora», «los mismos», «también»). Falla en cuanto la frase no trae esa palabra o la trae y aun así se entiende sola. Preguntar siempre al usuario si sigue o no. Rompe el uso normal del chat.

## 4. Dónde vive la memoria

**Decision**: La última lectura aceptada se guarda en la conversación del chat de esa empresa (`ConsultaConversacion`), junto a los mensajes que ya se enseñan a la izquierda. Cambiar de empresa o abrir una conversación nueva deja esa lectura fuera de uso. Una negativa no la sustituye. Si hay varias lecturas aceptadas, la continuación usa solo la última.

**Rationale**: La conversación ya está acotada por empresa y es lo que el usuario reconoce como «esta charla». Una memoria solo de sesión se perdería al recargar y no coincidiría con la lista de la izquierda. El gestor antiguo, en cambio, busca la última sesión por usuario, empresa y ejercicio, sin respetar la conversación que el usuario tiene abierta.

**Alternatives considered**: La sesión del navegador. No sobrevive a otra ventana ni a la lista de consultas guardadas. Una sola memoria por usuario, compartida entre empresas. Cruzaría cifras de una empresa a otra.

## 5. Revisión exhaustiva sin producto cartesiano

**Decision**: La revisión se genera desde el mapa activo. Hay al menos una pregunta por cada columna legible, una por cada relación que une conceptos de una pregunta, y una por cada forma de lectura (filtrar, varios filtros, agrupar, sumar, contar, promediar, máximo, mínimo, listar, conjunto entero, número concreto, un periodo, comparación de periodos, tabla y gráfica). Además, por cada forma de lectura, una pareja: una continuación que cambia solo una parte, y una pregunta posterior que se entiende sola y no hereda. Si falta alguna pieza, la revisión se declara incompleta aunque el resto coincida.

**Rationale**: El producto de todas las columnas por todas las formas y todas las relaciones no es una revisión usable ni hace falta para cubrir el territorio. La especificación pide que ninguna pieza quede sin pregunta, no que se prueben todas las combinaciones.

**Alternatives considered**: Seguir con el banco fijo de frases del examen actual. Cubre ejemplos, no el territorio, y no incluye parejas de memoria. Generar todas las combinaciones. El examen dejaría de poder lanzarse y leerse entero.

## 6. Qué cuenta como coincidencia

**Decision**: Cada pregunta generada guarda el resultado de ejecutar su lectura sobre los datos de la empresa y el periodo, igual que el examen actual compara después la respuesta del chat con ese resultado. Una continuación se compara con la lectura ya completada, no con la frase suelta. Una pregunta que se entiende sola se compara sin usar la memoria. Los probes de fuera solo coinciden si reciben la negativa fija, o si no muestran una cifra de la empresa cuando la frase ni siquiera nombra datos.

**Rationale**: Así «cualquier pregunta» tiene un veredicto: acierto dentro del territorio, rechazo correcto fuera, o fallo. No queda una zona muda.

**Alternatives considered**: Dar por buena la revisión si el recorrido está explicado en un documento y no se ejecuta. No valida el sistema.
