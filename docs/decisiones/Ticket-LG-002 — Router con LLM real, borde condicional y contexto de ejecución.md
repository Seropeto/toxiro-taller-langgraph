# Ticket-LG-002 — Router con LLM real, borde condicional y contexto de ejecución

Oct 20, 2026 · @ToxiroApps

LG-002 reemplaza el Router simulado por Haiku 4.5 con salida estructurada, agrega el primer borde condicional e incorpora `TenantContext` como contexto de ejecución. Pendiente: visto bueno del Director a cuatro decisiones nuevas.

## El concepto en corto

Este ticket junta tres piezas:

1. **Borde condicional.** El Router escribe `intencion` en el estado; una función de ruteo aparte lee ese campo y decide el nodo siguiente. El Router clasifica, el grafo enruta.
2. **Salida estructurada.** Al LLM no se le pide texto libre: llena un modelo Pydantic con un conjunto cerrado de valores. Si inventa una intención que no existe, la validación falla en vez de que el error siga por la cadena.
3. **Contexto de ejecución.** `TenantContext` se declara aparte del estado con `context_schema`, cada nodo lo lee con `runtime.context` y se entrega al invocar el grafo con `context=`.

**Comparado con el orquestador propio:** hoy el Router con Haiku clasifica y el orquestador decide con un `if` a quién llamar. LangGraph separa lo mismo, pero el `if` pasa a ser un borde declarado que se ve en el dibujo del grafo y en la traza. El `TenantContext` que ya estaba separado encuentra su lugar formal en el marco.

## Cuatro decisiones nuevas

El ticket asume la recomendación del CTO en las cuatro; requieren visto bueno del Director antes de enviarlo.

| # | Decisión | Recomendación | Alternativa |
| --- | --- | --- | --- |
| 1 | ¿Qué nodos pasan a LLM real? | Solo el Router; los otros tres siguen simulados | Los cuatro a la vez: más vistoso, pero son 4 prompts que afinar y el ticket pasa de 2 horas |
| 2 | Conjunto de intenciones | Dos: `diagnostico` y `fuera_de_alcance` | Una tercera, como `consulta_precio`: más realista, pero agrega un nodo y un camino sin enseñar nada nuevo |
| 3 | Si el LLM falla o su salida no valida | Respaldo seguro: intención `fuera_de_alcance`, respuesta directa que pide reformular y error registrado en la traza | Dejar que la excepción corte la ejecución: más honesto en desarrollo, pero en producción deja al recepcionista sin respuesta |
| 4 | Cómo probar un nodo con LLM | Dos niveles: tests con modelo falso (sin costo, deterministas) y un test de integración con Haiku real, marcado aparte y corrido a mano | Solo tests con LLM real: cuestan, tardan y fallan de forma intermitente |

Las decisiones 3 y 4 son las que más pesan para el cargo: *qué pasa cuando el modelo responde mal* y *cómo pruebas un sistema no determinista* son preguntas casi seguras en la entrevista.

## Ticket para Desarrollo

**Protocolo:** primero entrega la revisión y las respuestas a las preguntas del final. No implementes hasta tener el acuerdo de los tres.

**Objetivo:** reemplazar el Router simulado por uno con Haiku 4.5 y salida estructurada, agregar el primer borde condicional del grafo e incorporar `TenantContext` como contexto de ejecución.

**Decisiones ya tomadas por Director y CTO:**

- Solo el Router pasa a LLM real. Diagnóstico, Presupuestador y Evaluador siguen simulados.
- Intenciones posibles: `diagnostico` y `fuera_de_alcance`, como conjunto cerrado tipado con `Literal` en el modelo Pydantic.
- Si la llamada al LLM falla o su salida no valida, la intención queda en `fuera_de_alcance` y el error se registra para que se vea en la traza. El grafo no se corta.
- `TenantContext` va como contexto de ejecución (`context_schema` en el `StateGraph`, `runtime.context` en los nodos, `context=` al invocar). No va en el estado.
- Ruteo con borde condicional, no con `Command`.
- `MAX_REINTENTOS = 2` sigue sin uso y el Evaluador sigue sin tocar `intentos`; ambas cosas son para LG-003.

**Alcance:**

1. Fijar `langchain-anthropic>=1.7,<2` y actualizar `uv.lock`.
2. Marcar `sintoma` como obligatorio en el estado, manteniendo `total=False` para el resto.
3. Modelo Pydantic para la salida del Router con `intencion` como `Literal["diagnostico", "fuera_de_alcance"]`. Se puede agregar un campo corto de justificación si sirve para la traza.
4. Nodo `router` con `ChatAnthropic` y salida estructurada sobre ese modelo. El nombre del modelo va en `taller/config.py`, configurable por variable de entorno, con Haiku 4.5 por defecto.
5. Respaldo ante fallo o salida inválida, según la decisión de arriba.
6. Nuevo nodo simulado `respuesta_directa` que devuelve un mensaje fijo: consulta fuera de alcance o pedido de reformular. Se agrega al estado un campo para ese mensaje, con el nombre que proponga Desarrollo.
7. Función de ruteo y borde condicional desde `router`: `diagnostico` va a `diagnostico`; `fuera_de_alcance` va a `respuesta_directa` y luego a `END`.
8. `TenantContext` como dataclass en su propio archivo, cargado desde un archivo local de ejemplo con nombre del taller, un catálogo de 3 a 5 ítems y un margen por categoría. El Presupuestador simulado lo lee desde `runtime.context` y usa al menos un dato del catálogo en su salida.
9. `ANTHROPIC_API_KEY` en `.env.example`, y `LANGSMITH_PROJECT` corregido a `toxiro-taller-langgraph`.
10. Regenerar la imagen del grafo.

**Fuera de alcance:** LLM real en Diagnóstico, Presupuestador o Evaluador; bucle de reintentos; checkpointer; interrupt; Databricks; FastAPI y Docker.

## Criterios de aceptación, preguntas y estimación

**Criterios de aceptación:**

- [ ] Con un síntoma mecánico (*"rechinido metálico al frenar"*), el grafo recorre Router → Diagnóstico → Presupuestador → Evaluador → END.
- [ ] Con una consulta fuera de alcance (*"¿a qué hora cierran el sábado?"*), el grafo recorre Router → Respuesta directa → END, sin pasar por Diagnóstico.
- [ ] La traza en LangSmith muestra la llamada al LLM dentro de `router`, con su entrada, su salida estructurada y los tokens usados.
- [ ] `TenantContext` no aparece en el estado: ni en la salida de `main.py` ni en los inputs y outputs de los nodos en la traza.
- [ ] El presupuesto simulado contiene un dato tomado del catálogo de `TenantContext`.
- [ ] Tests con modelo falso, sin llamar a la API: la función de ruteo envía cada intención a su nodo; una salida inválida activa el respaldo con intención `fuera_de_alcance`; el Presupuestador lee un dato de `runtime.context`.
- [ ] Test de integración con Haiku real: 3 casos (2 mecánicos y 1 fuera de alcance), marcado para que no corra por defecto con `uv run pytest`, con instrucción de cómo correrlo a mano.
- [ ] Los tests de LG-001 siguen pasando.
- [ ] La imagen del grafo muestra la bifurcación desde `router`.

**Preguntas para Desarrollo:**

1. ¿Cómo propones simular el LLM en los tests: modelo falso de LangChain, `monkeypatch` u otra alternativa?
2. ¿Dónde capturas el fallo de validación: dentro del nodo o con un mecanismo de reintento o respaldo de LangChain? Explica la diferencia.
3. ¿Cómo haces que el error del respaldo quede visible en la traza y no se pierda en silencio?
4. ¿Algún problema con el tipado de `Runtime` o con `context_schema` en langgraph 1.2.16?
5. ¿Algo del alcance no cabe en 1 a 2 horas?

**Estimación:** 1,5 a 2 horas, más que LG-001 por el LLM real y los tests con modelo falso. Si pasa de 2 horas, se detiene y se revisa.

## Fuentes

- [LangGraph Reference — Runtime](https://reference.langchain.com/python/langgraph/runtime/Runtime)
- [LangChain docs — Runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [LangChain docs — Context](https://docs.langchain.com/oss/python/concepts/context.md)
