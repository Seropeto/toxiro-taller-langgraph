"""Regla de ruteo del ciclo Evaluador -> Presupuestador.

Función pura del estado: la usan el borde condicional (destino) y el nodo escalar (causa),
porque una función de ruteo no puede escribir en el estado.
"""

from typing import Literal, NamedTuple

from . import config
from .estado import CausaEscalada, EstadoTaller

Destino = Literal["fin", "escalar", "presupuestador"]


class Decision(NamedTuple):
    destino: Destino
    causa: CausaEscalada | None = None


def decidir_ruta(estado: EstadoTaller) -> Decision:
    """Aplica la regla en orden; gana el primer paso que se cumple."""
    veredicto = estado["evaluacion"]["veredicto"]
    if veredicto == "aprobado":
        return Decision("fin")
    if veredicto == "escalar":
        return Decision("escalar", "decision_evaluador")

    # Rechazado. El Evaluador ya agregó este rechazo: [-1] es el actual y [-2] el inmediatamente anterior.
    retroalimentaciones = estado.get("retroalimentaciones", [])
    if len(retroalimentaciones) >= 2 and retroalimentaciones[-1]["motivo"] == retroalimentaciones[-2]["motivo"]:
        return Decision("escalar", "motivo_repetido")
    if estado.get("intentos", 0) > config.MAX_REINTENTOS:
        return Decision("escalar", "maximo_reintentos")
    return Decision("presupuestador")


def rutear_por_veredicto(estado: EstadoTaller) -> Destino:
    return decidir_ruta(estado).destino
