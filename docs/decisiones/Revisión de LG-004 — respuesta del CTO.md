# Revisión de LG-004 — respuesta del CTO

Oct 21, 2026 · @ToxiroApps

Se aprueban los cuatro acuerdos que pide Desarrollo, con dos matices y una lección de arquitectura agendada para LG-005.

## La lección: casos en vuelo

Un caso guardado puede retomarse con una configuración distinta de la que tenía al empezar. Las observaciones 2 y 3 de Desarrollo son el mismo problema visto desde dos lados:

- La decisión del Evaluador es código y no se guarda en el checkpoint.
- `TenantContext` tampoco se guarda, por decisión nuestra.
- Si entre la falla y la retoma cambia el prompt del Evaluador o un precio del catálogo, el caso termina con reglas distintas a las de su inicio.

Hoy eso pasa en minutos. En LG-005 un caso puede quedar pausado días esperando al supervisor, y en ese tiempo pueden desplegarse versiones nuevas. La solución de fondo es registrar al inicio con qué versión partió cada caso (catálogo, prompts) y decidir qué hacer si no coincide al retomar. **Agendado para LG-005.**

*Para la entrevista:* con persistencia y pausas humanas aparece el problema de los casos en vuelo: un caso puede retomarse con otra versión del código o de los datos. Registro con qué versión partió cada caso para detectarlo.

## Lo que se aprueba

| Punto | Resolución |
| --- | --- |
| Obs. 1: entrada nueva solo en hilo vacío | Aprobada, con `CasoCerradoError` y `CasoEnCursoError`. La prueba de Desarrollo mostró el riesgo: las retroalimentaciones del caso viejo se duplican |
| Obs. 2: escenario en los metadatos del hilo | Aprobada, verificando que LangGraph los copie al checkpoint. Si no, se exige el mismo `--escenario` al retomar y `main.py` advierte que no puede validarlo; no se construye más |
| Obs. 3 a 5 | Documentadas: contexto al retomar, `thread_id` no es credencial, `casos.sqlite*` en `.gitignore` con `-wal` y `-shm` |
| Pregunta 1 | `SqliteSaver` sincrónico, `langgraph-checkpoint-sqlite>=3.1,<4` |
| Pregunta 3 | `taller/casos.py` como capa de casos, independiente de `main.py` y de la API futura. Es la decisión de arquitectura más importante del ticket |
| Pregunta 4 | `durability="sync"` explícito: ante una caída dura no se le paga dos veces a Haiku |
| Pregunta 5 | `recursion_limit` protege cada ejecución, no el caso; a través de las retomas lo acota `intentos` |

*Para la entrevista:* las reglas del caso viven en una capa propia; la terminal o la API solo traducen los errores a mensajes o códigos HTTP.

## Un matiz sobre la falla forzada

La falla basada en datos (`--contexto` con `tenant_sin_pastillas.json`) se aprueba: no toca código de producción y depende solo de la entrada.

Pero modela mal el negocio. Según el criterio del Director, un ítem que falta en el catálogo es una situación de negocio que se escala al dueño, no una caída del sistema. Hoy el Presupuestador simulado lanza `KeyError`, y la demostración lo presenta como falla técnica. Sirve para enseñar a retomar; no como modelo del negocio.

**Agendado:** cuando un ítem faltante se trate como escalada, la demostración necesitará otra fuente de falla.

## Mensaje de acuerdo para Desarrollo

> **Acuerdo LG-004.** Aprobada la revisión completa:
>
> 1. Observación 1 aprobada: entrada nueva solo en hilo vacío, con `CasoCerradoError` y `CasoEnCursoError`.
> 2. Observación 2: escenario en los metadatos del hilo. Verifica que LangGraph los copie al checkpoint; si no, se exige el mismo `--escenario` al retomar y `main.py` advierte que no puede validarlo. No construyas más mecanismo.
> 3. Falla basada en datos con `--contexto` y `tenant_sin_pastillas.json`: aprobada. Documenta en el código que un ítem faltante debería escalarse según las reglas del negocio y que el `KeyError` actual es comportamiento simulado.
> 4. `durability="sync"` explícito en `taller/casos.py`: aprobado.
> 5. El resto, tal como lo propusiste: `SqliteSaver` sincrónico `>=3.1,<4`, `taller/casos.py` con sus tres funciones y errores, `casos.sqlite` configurable en `RUTA_BASE_CASOS` y `casos.sqlite*` en `.gitignore`.
>
> Puedes implementar.
