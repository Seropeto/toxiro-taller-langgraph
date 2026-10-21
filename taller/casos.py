"""Casos del taller: un hilo (thread_id) es un caso.

Punto de entrada común para main.py y la futura API: las reglas de apertura, retome y revisión viven
acá, no en quien llama. Requiere un grafo compilado con checkpointer.
"""

import uuid
from dataclasses import dataclass, field
from typing import Literal

from langgraph.types import Command
from pydantic import ValidationError

from .contexto import TenantContext, aviso_cambio_de_version
from .estado import CausaEscalada, EstadoTaller, PaqueteRevision, ResultadoFinal, Retroalimentacion
from .nodos.revision import DecisionSupervisor

# Cada paso se persiste antes de empezar el siguiente. Con "async" (el valor por defecto de LangGraph),
# una caída dura del proceso puede perder el último checkpoint y repetir ese paso al retomar
# (por ejemplo, una segunda llamada a Haiku en el router).
DURABILIDAD = "sync"

# inexistente: el hilo no tiene checkpoints.
# pendiente_revision: pausado en revision_humana (interrupt); se resuelve con resolver_revision.
# fallado: tiene pasos pendientes sin pausa (un nodo lanzó una excepción o el proceso se cayó); se retoma.
# cerrado: terminó; tiene resultado_final.
SituacionCaso = Literal["inexistente", "pendiente_revision", "fallado", "cerrado"]


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


class CasoPendienteDeRevisionError(ErrorDeCaso):
    pass


class CasoNoPendienteDeRevisionError(ErrorDeCaso):
    pass


class DecisionInvalidaError(ErrorDeCaso):
    pass


@dataclass(frozen=True)
class Ejecucion:
    thread_id: str
    nodos: list[str]
    estado: EstadoTaller
    # Paquete de escalada si el caso quedó pendiente de revisión humana; None si terminó.
    paquete: PaqueteRevision | None = None
    # Solo en resolver_revision: aviso si la versión del contexto cambió desde el inicio del caso.
    aviso_version_contexto: str | None = None

    @property
    def pendiente(self) -> bool:
        return self.paquete is not None


@dataclass(frozen=True)
class PasoHistorial:
    paso: int
    origen: str  # "input" (entrada) o "loop" (resultado de un nodo)
    ejecutado: tuple[str, ...]  # nodos que produjeron este checkpoint
    siguiente: tuple[str, ...]
    intentos: int
    retroalimentaciones: list[Retroalimentacion] = field(default_factory=list)
    causa_escalada: CausaEscalada | None = None
    resultado_final: ResultadoFinal | None = None
    en_pausa: bool = False  # pausado en revision_humana esperando al supervisor


def nuevo_thread_id() -> str:
    return str(uuid.uuid4())


def _config(thread_id: str, metadatos: dict | None = None, run_name: str | None = None) -> dict:
    config: dict = {"configurable": {"thread_id": thread_id}}
    if metadatos:
        config["metadata"] = metadatos
    if run_name:
        config["run_name"] = run_name
    return config


def _ejecutar(grafo, entrada, config: dict, contexto: TenantContext):
    nodos, estado, paquete = [], {}, None
    for modo, datos in grafo.stream(
        entrada, config, context=contexto, durability=DURABILIDAD, stream_mode=["updates", "values"]
    ):
        if modo == "values":
            estado = datos
            continue
        for nodo, valor in datos.items():
            if nodo == "__interrupt__":  # pseudo-nodo que emite LangGraph al pausar
                paquete = valor[0].value
            else:
                nodos.append(nodo)
    return nodos, estado, paquete


def situacion_caso(grafo, thread_id: str) -> SituacionCaso:
    instantanea = grafo.get_state(_config(thread_id))
    if not instantanea.values:
        return "inexistente"
    if instantanea.interrupts:
        return "pendiente_revision"
    if instantanea.next:
        return "fallado"
    return "cerrado"


def iniciar_caso(
    grafo,
    entrada: EstadoTaller,
    contexto: TenantContext,
    thread_id: str | None = None,
    metadatos: dict | None = None,
    run_name: str | None = None,
) -> Ejecucion:
    """Abre un caso nuevo. Una entrada nueva solo se acepta en un hilo vacío.

    Devuelve el resultado final o, si el caso escala, la ejecución pendiente con el paquete de revisión.
    La versión del contexto se guarda en los metadatos del hilo para compararla al resolver.
    """
    thread_id = thread_id or nuevo_thread_id()
    situacion = situacion_caso(grafo, thread_id)
    if situacion == "cerrado":
        resultado = estado_caso(grafo, thread_id).get("resultado_final")
        raise CasoCerradoError(
            f"El caso {thread_id} está cerrado ({resultado}); una consulta nueva va en un hilo nuevo."
        )
    if situacion == "pendiente_revision":
        raise CasoEnCursoError(f"El caso {thread_id} está pendiente de revisión; usa resolver_revision.")
    if situacion == "fallado":
        raise CasoEnCursoError(f"El caso {thread_id} está en curso; usa retomar en vez de una entrada nueva.")

    metadatos = {**(metadatos or {}), "version_contexto": contexto.version}
    nodos, estado, paquete = _ejecutar(grafo, entrada, _config(thread_id, metadatos, run_name), contexto)
    return Ejecucion(thread_id, nodos, estado, paquete)


def retomar_caso(grafo, thread_id: str, contexto: TenantContext, run_name: str | None = None) -> Ejecucion:
    """Continúa un caso que falló desde el último checkpoint, sin repetir los pasos ya hechos.

    El TenantContext no está en el checkpoint: hay que volver a pasarlo.
    """
    situacion = situacion_caso(grafo, thread_id)
    if situacion == "inexistente":
        raise CasoInexistenteError(f"No existe el caso {thread_id}.")
    if situacion == "pendiente_revision":
        raise CasoPendienteDeRevisionError(
            f"El caso {thread_id} está pendiente de revisión humana; usa resolver_revision, no retomar."
        )
    if situacion == "cerrado":
        raise CasoSinPendientesError(
            f"El caso {thread_id} no tiene pasos pendientes "
            f"(resultado_final: {estado_caso(grafo, thread_id).get('resultado_final')})."
        )
    # Se reenvían los metadatos del caso para que los checkpoints nuevos los conserven.
    config = _config(thread_id, metadatos_caso(grafo, thread_id), run_name)
    nodos, estado, paquete = _ejecutar(grafo, None, config, contexto)
    return Ejecucion(thread_id, nodos, estado, paquete)


def resolver_revision(
    grafo, thread_id: str, decision: dict | DecisionSupervisor, contexto: TenantContext, run_name: str | None = None
) -> Ejecucion:
    """Valida la decisión del supervisor y reanuda el caso con Command(resume=decisión).

    Todo se valida antes de reanudar: si algo falla, el hilo no cambia.
    """
    situacion = situacion_caso(grafo, thread_id)
    if situacion == "inexistente":
        raise CasoInexistenteError(f"No existe el caso {thread_id}.")
    if situacion != "pendiente_revision":
        raise CasoNoPendienteDeRevisionError(
            f"El caso {thread_id} no está pendiente de revisión humana (situación: {situacion})."
        )
    try:
        validada = DecisionSupervisor.model_validate(decision)
    except ValidationError as error:
        detalle = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'decision'}: {e['msg']}" for e in error.errors())
        raise DecisionInvalidaError(f"Decisión inválida para el caso {thread_id}: {detalle}") from error

    metadatos = metadatos_caso(grafo, thread_id)
    aviso = aviso_cambio_de_version(metadatos.get("version_contexto"), contexto.version)
    config = _config(thread_id, metadatos, run_name)
    nodos, estado, paquete = _ejecutar(grafo, Command(resume=validada.model_dump()), config, contexto)
    return Ejecucion(thread_id, nodos, estado, paquete, aviso_version_contexto=aviso)


def estado_caso(grafo, thread_id: str) -> EstadoTaller:
    return grafo.get_state(_config(thread_id)).values


def metadatos_caso(grafo, thread_id: str) -> dict:
    """Metadatos guardados al abrir el caso (escenario, versión del contexto); LangGraph los copia a cada checkpoint."""
    instantanea = grafo.get_state(_config(thread_id))
    if not instantanea.values:
        raise CasoInexistenteError(f"No existe el caso {thread_id}.")
    return {k: v for k, v in instantanea.metadata.items() if k not in ("source", "step", "parents")}


def pendientes_caso(grafo, thread_id: str) -> tuple[str, ...]:
    return grafo.get_state(_config(thread_id)).next


def casos_pendientes(grafo) -> list[tuple[str, PaqueteRevision]]:
    """Bandeja del supervisor: (thread_id, paquete) de cada caso pausado en revisión humana.

    Recorre todos los checkpoints de la base: sirve para la base local; con Postgres en producción
    hará falta un índice o una tabla de pendientes.
    """
    hilos = dict.fromkeys(t.config["configurable"]["thread_id"] for t in grafo.checkpointer.list(None))
    pendientes = []
    for thread_id in hilos:
        instantanea = grafo.get_state(_config(thread_id))
        if instantanea.interrupts:
            pendientes.append((thread_id, instantanea.interrupts[0].value))
    return pendientes


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
                causa_escalada=valores.get("causa_escalada"),
                resultado_final=valores.get("resultado_final"),
                en_pausa=bool(instantanea.interrupts),
            )
        )
        anterior = instantanea.next
    return pasos
