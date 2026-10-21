# Revisión de LG-003 — respuesta del CTO

Oct 21, 2026 · @ToxiroApps

La revisión de Desarrollo se aprueba casi completa, con dos ajustes y tres notas para LG-005. El punto 0 quedó hecho: la integración de LG-002 sobre `main` dio 3/3 con Haiku real.

## Cómo registrar la causa de la escalada

Gana la propuesta de Desarrollo: una función pura `decidir_ruta` usada en el borde y en el nodo `escalar`. Una función de ruteo lee el estado pero no lo modifica, así que la causa tiene que escribirla un nodo.

| Solución | Ventaja | Problema |
| --- | --- | --- |
| Función pura `decidir_ruta`, usada en el borde y en `escalar` (elegida) | La regla vive en un solo lugar y se prueba sin ejecutar el grafo | Calcula dos veces lo mismo; es seguro porque el estado no cambia entre el borde y el nodo siguiente |
| El Evaluador aplica la regla y escribe la causa | Más simple de seguir | Vuelve a mezclar juicio con política |
| Nodo explícito `decidir` entre el Evaluador y el ruteo | La decisión queda como paso visible en la traza | Agrega un paso en cada evaluación sin aportar lógica |

*Para la entrevista:* las funciones de ruteo son puras; la política vive en una función que se reutiliza en el borde y en el nodo que registra la decisión.

## Lo que se aprueba tal cual

| Punto | Resolución |
| --- | --- |
| Obs. 1: `categoria` en `ItemPresupuesto` | El Evaluador detecta la mano de obra sin leer `TenantContext` |
| Obs. 2: el Presupuestador omite la mano de obra en la primera pasada | El test de LG-002 cambia su número, no su intención |
| Obs. 3: la regla 3 compara `retroalimentaciones[-1]` con `[-2]` | Evita el error de uno de más |
| Obs. 4: si coinciden las reglas 3 y 4, gana la 3 | Se cubre con un test |
| Obs. 6: el Evaluador escribe `aprobado` y `escalar` escribe `escalado` | Un nodo `finalizar` no aportaría nada |
| Obs. 7: `correcciones_aplicadas = len(retroalimentaciones)` | Lo más fiel en la versión simulada |
| Pregunta 2: guion indexado por `intentos` y decisión inyectable en `construir_grafo` | Producción y tests comparten la contabilidad; sin `monkeypatch` |
| Pregunta 3: `--escenario` con `stream(stream_mode="updates")` | Muestra los recorridos sin tocar código |
| Pregunta 4: `recursion_limit` con fórmula más margen de 5, hoy 15 | El valor por defecto en 1.2.16 es 10007: la red de seguridad por defecto casi no existe, así que fijarla es una decisión de arquitectura |

## Dos ajustes

**A. `resultado_final` necesita `"fuera_de_alcance"`.** El ticket pedía cubrir aprobado, escalado y fuera de alcance; Desarrollo propuso solo los dos primeros. Sin el tercero, el camino por `respuesta_directa` termina sin resultado final, y un caso cerrado sin resultado es un hueco en el registro. Lo escribe `respuesta_directa`; si fue un respaldo, eso ya queda en `origen_intencion`.

**B. `detalle` no puede venir vacío en un rechazo ni en una escalada.** Prohibir `motivo` fuera del rechazo está bien, pero cuando el Evaluador escala, la razón solo queda en `detalle`. Si viene vacío, el supervisor recibe un caso escalado sin explicación. Las categorías de escalada quedan para LG-005.

## Tres notas para LG-005

No cambian nada en LG-003.

1. **El guion indexado por `intentos` se rompe.** Hoy funciona porque la única vía de vuelta al Evaluador es un rechazo. Cuando el supervisor pueda devolver el caso al Presupuestador, el número de evaluación deja de ser igual a `intentos`.
2. **La fórmula de `recursion_limit` tendrá que incluir la vuelta desde la revisión humana.** Hay que verificar también si el contador de pasos se reinicia al retomar después de un `interrupt`.
3. **Alcanzar el límite lanza una excepción.** Es una red de seguridad técnica: el punto de entrada de una futura API debe capturarla y no mostrársela al recepcionista.

## Mensaje de acuerdo para Desarrollo

> **Acuerdo LG-003.** Aprobada la revisión completa, con dos ajustes:
>
> 1. `resultado_final` pasa a ser `Literal["aprobado", "escalado", "fuera_de_alcance"]`. `respuesta_directa` escribe `"fuera_de_alcance"`. Agrega un test que lo verifique.
> 2. Observación 5 aprobada, con una condición más en el `model_validator`: `detalle` no puede venir vacío cuando el veredicto es rechazado o escalar.
>
> Aprobados tal como los propusiste: la categoría en los ítems, el Evaluador escribe el resultado al aprobar, `decidir_ruta` como función pura reutilizada por el borde y por `escalar`, la decisión del evaluador inyectable en `construir_grafo` y `recursion_limit` calculado con la fórmula más un margen de 5. Puedes implementar.
