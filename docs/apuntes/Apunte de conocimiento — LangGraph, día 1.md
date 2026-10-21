# Apunte de conocimiento — LangGraph, día 1

Oct 20, 2026 · @ToxiroApps

En el día 1 se construyeron LG-001 y LG-002: un grafo con estado tipado, un Router con Haiku 4.5 y salida estructurada, el primer borde condicional, respaldos ante fallos del modelo y el catálogo del taller como contexto de ejecución, todo con trazabilidad en LangSmith.

## Lo construido

| Ticket | Qué entrega | Estado |
| --- | --- | --- |
| LG-001 | Repo base con `uv` y Python 3.12, estado tipado, 4 nodos simulados, grafo lineal, trazas en LangSmith | En `main` |
| LG-002 | Router con Haiku 4.5 y salida estructurada, borde condicional hacia `diagnostico` o `respuesta_directa`, respaldos de contenido y de servicio, `TenantContext` como contexto de ejecución | En `main`, commit `66d4bd0` |

La suite por defecto tiene 28 tests sin llamadas a la API. El test de integración con Haiku real dio 3/3. Repo: `toxiro-taller-langgraph`; el de producción no se tocó.

## Conceptos de LangGraph

| Concepto | Qué es | Cómo se vio en Toxiro Taller |
| --- | --- | --- |
| Estado | Objeto tipado único que todos los nodos leen y modifican: la ficha de la orden de trabajo | `TypedDict` con `sintoma`, `intencion`, `hipotesis`, `presupuesto`, `evaluacion`, `retroalimentaciones`, `intentos`, `decision_humana`, `origen_intencion`, `mensaje_respuesta` |
| Actualización parcial | Cada nodo devuelve solo los campos que cambió; LangGraph los mezcla con el estado existente | En la traza, el output del Router fue solo `intencion`, y el input del Diagnóstico trajo los cinco campos acumulados |
| Reductor | Define cómo se combinan escrituras sucesivas de un campo; por defecto el último valor reemplaza | `retroalimentaciones` acumula con `operator.add`; `intencion` usa reemplazo |
| Nodo | Función que recibe el estado y devuelve una actualización; no sabe qué viene después | Un archivo por agente en `taller/nodos/` |
| Borde normal | Después de A, siempre B | Diagnóstico → Presupuestador → Evaluador |
| Borde condicional | Una función lee el estado y elige el destino | `rutear_por_intencion` desde `router` |
| Compilación | Valida la estructura del grafo y conecta el checkpointer | `construir_grafo()`; la imagen sale de `get_graph()` |
| Salida estructurada | El LLM llena un modelo Pydantic con valores cerrados, no texto libre | `SalidaRouter` con `intencion: Literal[...]` y `justificacion` |
| Contexto de ejecución | Datos fijos de la ejecución que los nodos leen sin que pasen por el estado | `TenantContext` con `context_schema`, `runtime.context` y `invoke(..., context=)` |
| Traza | Registro de cada paso con entrada, salida, llamadas al LLM y tokens | Proyecto `toxiro-taller-langgraph` en LangSmith |

**`TypedDict` no valida en ejecución:** marcar un campo como obligatorio solo sirve al editor y al tipado. `context_schema` tampoco valida: si se invoca sin `context=`, `runtime.context` es `None`.

## El grafo hoy

&#91;embedded content: grafo al cierre de LG-002 · un nodo con LLM real, una bifurcación\]

Solo el Router usa un LLM real; los otros tres nodos siguen simulados. El Presupuestador lee el catálogo desde el contexto de ejecución, sin que pase por el estado. El bucle de corrección y la revisión humana llegan en LG-003 y LG-005.

## Orquestador propio vs. LangGraph

| Pieza | Orquestador propio | LangGraph | Qué se gana |
| --- | --- | --- | --- |
| Contexto | Objeto de caso que se enriquece; cada agente recibe todo | Estado tipado con actualizaciones parciales y reductores | Contrato explícito de qué campos existen y quién los escribe |
| Configuración del taller | `TenantContext` separado del caso | Contexto de ejecución formal | No se guarda en cada checkpoint ni aparece en cada traza |
| Quién decide el flujo | El orquestador, con `if` y `while` | Bordes declarados en el grafo | El flujo se compila, se valida, se dibuja y se ve en la traza |
| Reintento | Contador interno del orquestador | `intentos` en el estado (desde LG-003) | El control de flujo pasa a ser estado auditable |
| Escalada | Marcador terminal, sin retoma | `interrupt` + checkpointer + `thread_id` (desde LG-005) | Resuelve un pendiente real de producción |

**Lo que se pierde:** control total sobre cada línea, independencia de un proveedor y simplicidad en flujos lineales.

**Regla:** orquestador propio si el flujo es lineal, corto y sin intervención humana; LangGraph cuando hay que pausar, retomar, auditar el control de flujo o ramificar.

## Decisiones y por qué

| Decisión | Por qué |
| --- | --- |
| Bordes condicionales, no `Command` | El flujo queda legible y auditable en un solo lugar |
| `TypedDict` para el estado, Pydantic para la salida del LLM | La validación va donde está el riesgo: la respuesta del modelo |
| Nodos simulados en LG-001 | Aprender la estructura sin el ruido del LLM |
| Solo el Router con LLM real en LG-002 | Un prompt a la vez; el ticket cabe en 2 horas |
| Dos intenciones: `diagnostico` y `fuera_de_alcance` | Una tercera agregaba un camino sin enseñar nada nuevo |
| `TenantContext` como contexto de ejecución | No se copia en cada checkpoint ni en cada traza; en el día 2 vendrá de Unity Catalog |
| `origen_intencion` en el estado, con `llm`, `respaldo_contenido` y `respaldo_servicio` | Cada falla pide un mensaje distinto, y el estado es el registro del caso: las trazas se muestrean y se borran |
| Captura del fallo dentro del nodo con `include_raw=True` | El respaldo es lógica propia, visible y probable; `.with_fallbacks()` lo ocultaba |
| Tests con un modelo falso que pasa por el parser real | Prueba justo donde ocurre el fallo de validación |
| Integración con Haiku real, marcada aparte | Cuesta, tarda y no es determinista |
| Haiku 4.5 fijado a `claude-haiku-4-5-20251001` | Mismo modelo que producción: los cambios se atribuyen al marco, no al modelo |
| `main.py` falla al arrancar sin key real | Un error de configuración se detecta al inicio, no disfrazado de respuesta |
| Solo el Evaluador incrementa `intentos`; rechazo vuelve solo al Presupuestador; `MAX_REINTENTOS = 2` | Decidido para LG-003 |

## Errores encontrados y cómo se resolvieron

| Error | Quién lo detectó | Resolución |
| --- | --- | --- |
| El respaldo mezclaba fallas de contenido y de servicio: con un 401 le decía al recepcionista "reformule" | Error real al correr sin key | `origen_intencion` con tres valores y un mensaje por caso |
| El criterio "los tests de LG-001 siguen pasando" era imposible al cambiar el flujo | Desarrollo | Se mantiene la intención de los tests, no su código |
| Un test dependía de `builder.branches`, atributo semi-interno | Desarrollo lo advirtió | Reemplazado por la API pública `get_graph()` |
| El Evaluador agrega retroalimentación incluso al aprobar | CTO, en la revisión de LG-001 | Agendado para LG-003: solo se agrega en rechazos |
| Desarrollo implementó LG-001 sin esperar el acuerdo de los tres | CTO | Desde LG-002 entrega primero la revisión |
| El CTO planteó que en el orquestador propio decide el agente; en realidad decide el orquestador | Respuesta del Director | Corregido en la explicación |
| `TypedDict` y `context_schema` no validan en ejecución | Desarrollo | Validación en el borde de entrada; error claro si falta el contexto |
| Las imágenes del grafo pasan por mermaid.ink, un servicio externo | CTO | Aceptable para aprender; en un entorno corporativo es un tema de gobernanza |

## Lecciones de arquitecto

1. **El flujo es un artefacto auditable.** En LangGraph el control de flujo se declara, se compila y se dibuja; deja de estar escondido en código imperativo.
2. **La validación va en la frontera.** El estado tipado es un contrato para desarrolladores; los datos externos se validan al entrar al sistema.
3. **Reintento de transporte no es reintento de contenido.** El SDK reintenta ante fallas de red; el bucle del Evaluador reintenta porque la respuesta fue mala. Son capas distintas.
4. **Cada falla pide su propia respuesta.** Una falla de contenido se le explica al usuario; una de servicio se le avisa al equipo.
5. **El estado es el registro del caso; la traza es para diagnosticar.** Lo que importa para auditar el resultado va en el estado, porque las trazas se muestrean y se borran.
6. **Probar un sistema no determinista exige dos niveles.** Tests deterministas con modelo falso, e integración con el modelo real aparte. `temperature=0` reduce la variación, pero no la elimina.
7. **Medir costos con datos.** En el Router, cerca de 800 de los \~835 tokens de entrada son la definición de la herramienta de salida estructurada; el prompt pesa unas decenas.
8. **Validar en real cambia el diseño.** El defecto del respaldo solo apareció con un error real; en papel parecía correcto.

## Preguntas probables de entrevista

**1. ¿Por qué LangGraph y no un orquestador propio?**

*Tenía un orquestador propio en producción con cuatro agentes. Funcionaba, pero el flujo vivía en código imperativo y la escalada a supervisor era un marcador terminal: no se podía retomar. LangGraph me da el flujo declarado y auditable, y pausa y retoma con checkpointer. Para un flujo lineal sin intervención humana seguiría con un orquestador propio.*

**2. ¿Cómo manejas que el LLM responda algo inválido?**

*Salida estructurada con Pydantic y un conjunto cerrado de valores. El fallo se captura dentro del nodo y cae a un respaldo trazado. Separé fallas de contenido de fallas de servicio después de probarlo con un error real: un 401 le estaba pidiendo al usuario que reformulara.*

**3. ¿Cómo pruebas un sistema con LLM, que no es determinista?**

*En dos niveles. Tests deterministas con un modelo falso que pasa por el parser real de LangChain, para probar ruteo y respaldos sin costo. Y una integración aparte con el modelo real, marcada para correr a mano.*

**4. ¿Dónde pones la configuración de cada cliente y por qué?**

*Como contexto de ejecución, no en el estado. El estado se guarda en cada checkpoint y aparece en cada traza; el catálogo de un taller no tiene por qué copiarse ahí. Lo verifiqué buscando en las trazas datos que solo existen en el contexto.*

**5. ¿Qué observabilidad tiene tu sistema?**

*Trazas en LangSmith desde el primer ticket: cada nodo con su entrada y salida, cada llamada al modelo con tokens. El respaldo aparece como paso propio para filtrarlo. Y lo que importa para auditar el caso, como el origen de la intención, queda en el estado, porque las trazas se muestrean.*

## Repaso pendiente y mañana

**Responder antes de LG-003, con palabras propias:**

1. ¿Por qué el Router escribe `intencion` en el estado en vez de decidir él mismo a qué nodo ir?
2. Si Haiku responde una intención que no existe, como `consulta_precio`, ¿qué la detiene y qué ve el recepcionista?
3. ¿Por qué el catálogo llega por `runtime.context` y no en el estado, y cómo se verificó que no se filtró a la traza?

**Pendientes:**

- [ ] Correr `uv run pytest -m integracion -v` sobre lo que quedó en `main` después de separar el respaldo
- [ ] Decidir el plan: LG-003 a LG-005 en la mañana y Databricks comprimido en la tarde, o un tercer día

**Mañana:** LG-003, el bucle Evaluador → Presupuestador con retroalimentación y máximo de reintentos. Primer ajuste agendado: el Evaluador solo agrega a `retroalimentaciones` cuando rechaza.
