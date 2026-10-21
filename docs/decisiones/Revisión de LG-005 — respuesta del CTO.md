# Revisión de LG-005 — respuesta del CTO

Oct 21, 2026 · @ToxiroApps

La revisión de Desarrollo se aprueba casi completa. Queda una decisión del Director (uno o dos nodos) y un ajuste del CTO al aviso de versión.

## Decisión del Director: uno o dos nodos

Un nodo solo escribe en el estado cuando termina. Si `revision_humana` calcula la causa y luego pausa, la causa queda fuera del estado mientras el caso espera, que puede ser días; solo existe dentro del paquete del `interrupt`.

|  | Un nodo (propuesta de Desarrollo) | Dos nodos: `preparar_revision` + `revision_humana` |
| --- | --- | --- |
| Causa durante la pausa | Solo en el paquete | En el estado, como un paso del historial |
| Código antes del `interrupt` | Lecturas puras: seguro hoy, depende de que nadie agregue nada | Nada: el nodo solo pausa; la seguridad la da la estructura |
| Costo | Ninguno | Un nodo y un paso más; hay que recalcular `recursion_limit` |

**Recomendación del CTO: dos nodos.**

- **Coherencia:** en LG-002 se acordó que el estado es el registro del caso; un caso pausado días sin su causa en el estado lo contradice.
- **La siguiente funcionalidad obvia es avisar al supervisor.** Con un nodo, ese aviso iría antes del `interrupt` y se repetiría en cada retoma; con dos, va en `preparar_revision` y sale una vez. Es lo que recomienda la documentación de LangGraph.

*Para la entrevista:* separé la preparación de la pausa; lo que va antes del `interrupt` no depende de la disciplina del equipo, porque el nodo que pausa no hace nada más.

## Ajuste del CTO: el aviso de versión

Desarrollo propuso que la capa de casos compare versiones y pase el aviso dentro del valor de `resume`. Se rechaza: ese valor es la decisión del supervisor, y en la auditoría `decision_humana` debe contener exactamente lo que dijo el humano, sin observaciones del sistema mezcladas.

**Propuesta:**

- `resume` lleva solo la `DecisionSupervisor`.
- La comparación de versiones es una función pura usada en dos lugares, igual que `decidir_ruta`: el nodo, después del `interrupt`, para escribir `aviso_version_contexto`; y `resolver_revision`, para mostrar el aviso.

El campo `aviso_version_contexto` se aprueba.

## Lo que se aprueba tal cual

| Punto | Resolución |
| --- | --- |
| Obs. 2: la regla 3 se salta las instrucciones del supervisor | Una instrucción no es un rechazo. Si tras corregir el Evaluador rechaza por el mismo motivo de antes, el caso vuelve al supervisor: su corrección no resolvió el problema |
| Obs. 3: `MotivoEvaluador` y `MotivoRetroalimentacion` | El Evaluador no puede hacerse pasar por el supervisor |
| Obs. 4: tests de LG-003/004 cambian de intención | Legítimo: "escalado" dejó de ser resultado final y pasó a ser caso pendiente |
| Obs. 6 y 7 | Guion con `despues` y filtrado de `__interrupt__` |
| Pregunta 1: contador `evaluaciones` | Indexa el guion y sirve como métrica de costo por caso |
| Pregunta 2: `situacion_caso()` con cuatro estados | La pieza que usará la API futura; `next` no alcanza para distinguir pausado de fallado |
| Pregunta 5: bandeja `casos_pendientes` con `--pendientes` | Recorre los checkpoints: sirve en local; en producción, tabla de pendientes con índice |

## Mensaje para Desarrollo y plazo

Se envía si el Director aprueba los dos nodos:

> **Acuerdo LG-005.** Aprobada la revisión, con dos cambios:
>
> 1. **Observación 1: dos nodos.** `preparar_revision` escribe `causa_escalada`, arma el paquete y hace la comprobación de versión al escalar. `revision_humana` solo llama a `interrupt` y aplica la decisión. Recalcula `recursion_limit` con el paso adicional y actualiza el test del peor caso.
> 2. **Observación 5:** `resume` lleva solo la `DecisionSupervisor`. La comparación de versiones es una función pura que usa el nodo después del `interrupt`, para escribir `aviso_version_contexto`, y `resolver_revision`, para mostrar el aviso.
>
> Aprobados tal como los propusiste: la regla 3 se salta las instrucciones del supervisor, `MotivoEvaluador` y `MotivoRetroalimentacion`, el cambio de intención de los tests de LG-003 y LG-004, el guion con `despues`, el filtrado de `__interrupt__`, el contador `evaluaciones`, `situacion_caso()` con sus errores, y la bandeja `casos_pendientes` con `--pendientes`. Puedes implementar.

**Plazo:** el ticket queda en unas 2,5 horas. Con LG-005 termina LangGraph; Databricks queda para el día siguiente.
