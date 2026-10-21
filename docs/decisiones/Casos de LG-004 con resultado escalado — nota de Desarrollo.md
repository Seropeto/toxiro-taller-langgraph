# Casos de LG-004 con resultado escalado — nota de Desarrollo

Oct 21, 2026 · Desarrollo

## Qué existe

La base local `casos.sqlite` (excluida de git) puede tener casos creados entre LG-004 y LG-005 con `resultado_final = "escalado"`. Se reconocen por tres señales:

- `resultado_final` vale `"escalado"`, un valor que ya no existe en `ResultadoFinal`.
- Su historial pasa por el nodo `escalar`, que LG-005 eliminó.
- Sus metadatos no tienen `version_contexto`.

## Por qué

En LG-003 y LG-004, la escalada era provisional: el nodo `escalar` marcaba `resultado_final = "escalado"` y el caso terminaba. LG-005 reemplazó ese nodo por `preparar_revision` y `revision_humana`. Ahora un caso que escala queda pendiente con `interrupt` y no tiene resultado final hasta que decide el supervisor. Los casos que ya estaban guardados quedaron con el valor anterior.

## Qué pasa con ellos hoy

Se verificó contra la base real:

- `situacion_caso()` los ve como `cerrado`, porque no tienen pasos pendientes.
- `--historial` los muestra completos; el paso de `escalar` aparece sin nodo siguiente.
- `--pendientes` no los lista, porque no tienen `interrupt`.
- `resolver_revision` los rechaza con `CasoNoPendienteDeRevisionError` y `retomar_caso` con `CasoSinPendientesError`.
- Al no tener `version_contexto`, la comprobación de versión no avisa.

## Decisión: no se migran en este repo

- **Son datos de demostración** en una base local que no se versiona. No hay casos reales afectados.
- **Migrarlos exigiría inventar una decisión** que nadie tomó. Convertirlos en pendientes los reabriría, y dejarlos con otro resultado reescribiría lo que pasó.
- **Se pueden leer y no bloquean nada:** ninguna operación nueva los toma por pendientes ni por abiertos.

Si molestan en la demostración, basta con borrar `casos.sqlite`. Si en producción hubiera datos con una escalada provisional, la migración sería un ticket propio, con una regla de negocio explícita para cada caso.
