# Ticket-LG-005 — Revisión humana con interrupt

Oct 21, 2026 · @ToxiroApps

LG-005 reemplaza la escalada provisional por una revisión humana real: el caso se pausa con `interrupt`, el supervisor decide y el caso continúa donde quedó. Pendiente: visto bueno del Director a cinco decisiones.

## El concepto

1. Dentro de `revision_humana`, el código llama a `interrupt(paquete)`. El grafo se detiene, el checkpointer guarda el estado y quien invocó recibe el paquete en `resultado["__interrupt__"]`. El caso queda pausado, no terminado.
2. Horas o días después, se invoca con el mismo `thread_id` y `Command(resume=decision)`. El nodo se ejecuta otra vez desde el principio, y esta vez `interrupt()` devuelve la decisión del supervisor.
3. Según la decisión, el caso termina o vuelve al Presupuestador.

**Dos reglas de LangGraph:**

- **Todo lo que está antes del `interrupt` se repite al retomar.** Un correo enviado ahí saldría de nuevo cada vez; por eso debe ser idempotente o ir en otro nodo.
- **El `interrupt` no va dentro de un `try/except` general.** La pausa funciona con una excepción interna que un `except` genérico atraparía.

**Comparado con producción:** hoy la escalada es un marcador final con `status: escalated` y `escalation_package`; el supervisor ve el caso pero no puede continuarlo. Con LG-005, ese paquete es el contenido del `interrupt` y la respuesta del supervisor retoma el mismo caso sin repetir Diagnóstico ni Router. LangGraph da la pausa y la reanudación; el panel y el endpoint que recibe la decisión siguen siendo propios, y aquí ese papel lo cumple `taller/casos.py`.

## Cinco decisiones

| # | Decisión | Recomendación | Alternativa |
| --- | --- | --- | --- |
| 1 | ¿Qué puede decidir el supervisor? | Aprobar, corregir con una instrucción o cancelar | Solo aprobar o cancelar: más simple, pero no permite corregir |
| 2 | ¿La corrección vuelve a pasar por el Evaluador? | Sí, como retroalimentación con motivo `instruccion_supervisor`; el humano también puede equivocarse | Corrección definitiva: más rápida, deja sin validar los casos difíciles |
| 3 | ¿La intervención humana renueva los reintentos? | No; el presupuesto de reintentos es por caso | Reiniciar `intentos`: un caso difícil podría consumir rondas sin fin |
| 4 | ¿Se registra quién decidió? | Sí, campo obligatorio `revisor` | No registrarlo: la auditoría queda coja |
| 5 | Casos en vuelo | Versión mínima: `version` en `TenantContext`, guardada al iniciar; si cambió al resolver, se avisa y se registra, sin bloquear | Dejarlo fuera: ahorra unos 20 minutos, pero es el ticket donde las pausas largas lo vuelven real |
