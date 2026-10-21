# Revisión de LG-002 — respuesta del CTO

Oct 20, 2026 · @ToxiroApps

La revisión de Desarrollo se aprueba casi completa; quedan dos decisiones del Director antes de autorizar la implementación.

## Lo que se aprueba tal cual

Desarrollo respetó el protocolo, verificó sus respuestas contra el código instalado y encontró un problema real en el ticket.

| Punto | Resolución |
| --- | --- |
| Tests de LG-001 | Se mantiene su intención, no su código: el test de aristas pasa al flujo nuevo y el del estado final corre con modelo falso y un `TenantContext` de prueba. El criterio original fue un error del CTO |
| `LANGSMITH_PROJECT` y `ANTHROPIC_API_KEY` | Ya estaban hechos; salen del alcance |
| Nombre del campo del mensaje | `mensaje_respuesta`, para no confundirlo con el nodo en la traza |
| Pydantic | Dependencia explícita `pydantic>=2,<3` |
| `main.py` | Recibe el síntoma como argumento |
| Diseño | Aprobado completo: `contexto.py`, JSON de ejemplo, `SalidaRouter` con justificación, `crear_modelo()` reemplazable, ruteo |
| Simular el LLM en tests | Modelo falso que pasa por el parser real de LangChain. Costo: depende de la implementación interna de la salida estructurada; aceptable con versiones fijadas |
| Dónde se captura el fallo | Dentro del nodo, con `include_raw=True` y `try/except`, no con `.with_fallbacks()` |
| Visibilidad del error | `@traceable` para el respaldo más `logger.warning` |
| Contexto ausente | Error claro si `runtime.context` es `None` |
| Test de integración | Marcador `integracion`, excluido por defecto |

## Conceptos para la entrevista

**1. `TypedDict` no valida en ejecución.** Marcar `sintoma` como obligatorio solo sirve al editor y al tipado; LangGraph no rechaza un estado incompleto al invocar. No se agrega validación dentro del grafo: la validación va en el borde de entrada, que en producción es el endpoint de FastAPI con un modelo Pydantic.

*Respuesta:* el estado tipado es un contrato para desarrolladores; la validación de datos externos va en la frontera del sistema.

**2. Reintento de transporte vs. reintento de contenido.** `ChatAnthropic` ya reintenta ante errores transitorios del servicio: es la misma pregunta otra vez porque falló la red. El bucle de LG-003 es distinto: otra pregunta, con retroalimentación, porque la respuesta fue mala. Son capas distintas y no se mezclan.

**3. `temperature=0` no garantiza determinismo.** Reduce la variación, pero la misma entrada puede dar salidas distintas. Por eso el test de integración se corre a mano y no entra en la batería normal.

## Dos decisiones del Director

| Decisión | Recomendación del CTO | Razón |
| --- | --- | --- |
| A. ¿Haiku 4.5 o 5.5? | Mantener 4.5, fijada a `claude-haiku-4-5-20251001` | Es el modelo de producción: si algo cambia en la comparación, se atribuye al marco y no al modelo. Cambiar después es una variable |
| B. ¿Campo de error en el estado? | Sí: `origen_intencion` con valores `llm` o `respaldo` | Funcional: sin el campo, `respuesta_directa` no distingue fuera de alcance real de un fallo del LLM. Gobernanza: las trazas se muestrean y se borran; el estado es el registro del caso |

Desarrollo había propuesto no agregar el campo de error; la recomendación del CTO lo contradice por las dos razones de la tabla.

## Mensaje de acuerdo para Desarrollo

Se envía si el Director aprueba A y B:

> **Acuerdo LG-002.** Aprobada la revisión completa, con estos ajustes:
>
> 1. Tests de LG-001: se mantiene su intención, no su código. Aprobada tu propuesta.
> 2. `sintoma`: solo tipado, sin validación en ejecución dentro del grafo.
> 3. Modelo: `claude-haiku-4-5-20251001` fijo por defecto en `MODELO_ROUTER`. Se mantiene 4.5 para comparar con producción.
> 4. Agregar al estado `origen_intencion` (`llm` o `respaldo`). El router lo escribe y `respuesta_directa` elige el mensaje según él: fuera de alcance real o pedido de reformular. Agregar un test con modelo falso que lo verifique.
> 5. El resto, tal como lo propusiste. Puedes implementar.
