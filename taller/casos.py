"""Casos del taller: un hilo (thread_id) es un caso.

Punto de entrada común para main.py y la futura API: las reglas de apertura y retome viven acá,
no en quien llama. Requiere un grafo compilado con checkpointer.
"""

import uuid
from dataclasses import dataclass, field

from .contexto import TenantContext
from .estado import EstadoTaller, ResultadoFinal, Retroalimentacion

# Cada paso se persiste antes de empezar el siguiente. Con "async" (el valor por defecto de LangGraph),
# una caída dura del proceso puede perder el último checkpoint y repetir ese paso al retomar
# (por ejemplo, una segunda llamada a Haiku en el router).
DURABILIDAD = "sync"


class ErrorDeCaso(Exception):
    """Base de los errores de reglas de caso; la API los traducirá a respuestas HTTP."""


class CasoCerradoError(ErrorDeCaso):
    pass


class CasoEnCursoError(ErrorDeCaso):
    pass


class CasoSinPendientesError(ErrorDeCaso):
    pass


class CasoInexistenteError(ErrorDeCaso):
    pass


@dataclass(frozen=True)
class Ejecucion:
    thread_id: str
    nodos: list[str]
    estado: EstadoTaller


@dataclass(frozen=True)
class PasoHistorial:
    paso: int
    origen: str  # "input" (entrada) o "loop" (resultado de un nodo)
    ejecutado: tuple[str, ...]  # nodos que produjeron este checkpoint
    siguiente: tuple[str, ...]
    intentos: int
    retroalimentaciones: list[Retroalimentacion] = field(default_factory=list)
    resultado_final: ResultadoFinal | None = None


def nuevo_thread_id() -> str:
    return str(uuid.uuid4())


def _config(thread_id: str, metadatos: dict | None = None, run_name: str | None = None) -> dict:
    config: dict = {"configurable": {"thread_id": thread_id}}
    if metadatos:
        config["metadata"] = metadatos
    if run_name:
        config["run_name"] = run_name
    return config


def _ejecutar(grafo, entrada, config: dict, contexto: TenantContext) -> tuple[list[str], EstadoTaller]:
    nodos, estado = [], {}
    for modo, datos in grafo.stream(
        entrada, config, context=contexto, durability=DURABILIDAD, stream_mode=["updates", "values"]
    ):
        if modo == "updates":
            nodos.extend(datos)
        else:
            estado = datos
    return nodos, estado


def iniciar_caso(
    grafo,
    entrada: EstadoTaller,
    contexto: TenantContext,
    thread_id: str | None = None,
    metadatos: dict | None = None,
    run_name: str | None = None,
) -> Ejecucion:
    """Abre un caso nuevo. Una entrada nueva solo se acepta en un hilo vacío."""
    thread_id = thread_id or nuevo_thread_id()
    instantanea = grafo.get_state(_config(thread_id))
    if instantanea.values:
        if instantanea.values.get("resultado_final"):
            raise CasoCerradoError(
                f"El caso {thread_id} está cerrado ({instantanea.values['resultado_final']}); "
                "una consulta nueva va en un hilo nuevo."
            )
        raise CasoEnCursoError(f"El caso {thread_id} está en curso; usa retomar en vez de una entrada nueva.")

    nodos, estado = _ejecutar(grafo, entrada, _config(thread_id, metadatos, run_name), contexto)
    return Ejecucion(thread_id, nodos, estado)


def retomar_caso(grafo, thread_id: str, contexto: TenantContext, run_name: str | None = None) -> Ejecucion:
    """Continúa un caso desde el último checkpoint, sin repetir los pasos ya hechos.

    El TenantContext no está en el checkpoint: hay que volver a pasarlo.
    """
    instantanea = grafo.get_state(_config(thread_id))
    if not instantanea.values:
        raise CasoInexistenteError(f"No existe el caso {thread_id}.")
    if not instantanea.next:
        raise CasoSinPendientesError(
            f"El caso {thread_id} no tiene pasos pendientes "
            f"(resultado_final: {instantanea.values.get('resultado_final')})."
        )
    # Se reenvían los metadatos del caso para que los checkpoints nuevos los conserven.
    config = _config(thread_id, metadatos_caso(grafo, thread_id), run_name)
    nodos, estado = _ejecutar(grafo, None, config, contexto)
    return Ejecucion(thread_id, nodos, estado)


def metadatos_caso(grafo, thread_id: str) -> dict:
    """Metadatos guardados al abrir el caso (p. ej. el escenario); LangGraph los copia a cada checkpoint."""
    instantanea = grafo.get_state(_config(thread_id))
    if not instantanea.values:
        raise CasoInexistenteError(f"No existe el caso {thread_id}.")
    return {k: v for k, v in instantanea.metadata.items() if k not in ("source", "step", "parents")}


def pendientes_caso(grafo, thread_id: str) -> tuple[str, ...]:
    return grafo.get_state(_config(thread_id)).next


def historial_caso(grafo, thread_id: str) -> list[PasoHistorial]:
    """Un PasoHistorial por checkpoint, en orden cronológico."""
    instantaneas = list(grafo.get_state_history(_config(thread_id)))[::-1]
    if not instantaneas:
        raise CasoInexistenteError(f"No existe el caso {thread_id}.")
    pasos, anterior = [], ()
    for instantanea in instantaneas:
        valores = instantanea.values
        pasos.append(
            PasoHistorial(
                paso=instantanea.metadata["step"],
                origen=instantanea.metadata["source"],
                ejecutado=anterior,
                siguiente=instantanea.next,
                intentos=valores.get("intentos", 0),
                retroalimentaciones=valores.get("retroalimentaciones", []),
                resultado_final=valores.get("resultado_final"),
            )
        )
        anterior = instantanea.next
    return pasos
