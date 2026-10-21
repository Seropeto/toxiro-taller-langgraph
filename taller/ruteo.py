"""Reglas de ruteo del ciclo Evaluador -> Presupuestador y de la revisión humana.

Funciones puras del estado: la usan los bordes condicionales (destino) y preparar_revision (causa),
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

    # Rechazado. El Evaluador ya agregó este rechazo: [-1] es el actual y [-2] el anterior del Evaluador.
    # Las instrucciones del supervisor no son rechazos: se saltan.
    rechazos = [r for r in estado.get("retroalimentaciones", []) if r["motivo"] != "instruccion_supervisor"]
    if len(rechazos) >= 2 and rechazos[-1]["motivo"] == rechazos[-2]["motivo"]:
        return Decision("escalar", "motivo_repetido")
    if estado.get("intentos", 0) > config.MAX_REINTENTOS:
        return Decision("escalar", "maximo_reintentos")
    return Decision("presupuestador")


def rutear_por_veredicto(estado: EstadoTaller) -> Destino:
    return decidir_ruta(estado).destino


def rutear_por_decision(estado: EstadoTaller) -> Literal["fin", "presupuestador"]:
    """Tras la revisión humana: corregir vuelve al Presupuestador; aprobar y cancelar terminan."""
    return "presupuestador" if estado["decision_humana"]["accion"] == "corregir" else "fin"
