"""Guiones del Evaluador para mostrar los recorridos del ciclo (main.py --escenario) y para los tests.

Un guion es una tupla inmutable indexada por `intentos`: dentro del ciclo, todo veredicto que no es
rechazo termina el grafo, así que la evaluación en curso siempre es la número `intentos`.
No hay iteradores ni contadores compartidos entre ejecuciones.
"""

from collections.abc import Sequence

from .estado import EstadoTaller, Motivo
from .nodos.evaluador import DecisionEvaluador, SalidaEvaluador, evaluar_mano_de_obra


def aprobado(detalle: str = "Presupuesto correcto.") -> SalidaEvaluador:
    return SalidaEvaluador(veredicto="aprobado", detalle=detalle)


def rechazo(motivo: Motivo, detalle: str | None = None) -> SalidaEvaluador:
    return SalidaEvaluador(veredicto="rechazado", motivo=motivo, detalle=detalle or f"Rechazado por {motivo}.")


def escalada(detalle: str = "Caso ambiguo: requiere revisión de un técnico.") -> SalidaEvaluador:
    return SalidaEvaluador(veredicto="escalar", detalle=detalle)


def evaluador_con_guion(guion: Sequence[SalidaEvaluador]) -> DecisionEvaluador:
    pasos = tuple(guion)

    def decidir(estado: EstadoTaller) -> SalidaEvaluador:
        return pasos[estado.get("intentos", 0)]

    return decidir


ESCENARIOS: dict[str, DecisionEvaluador] = {
    # Regla real simulada: rechaza la primera pasada (sin mano de obra) y aprueba la corrección.
    "normal": evaluar_mano_de_obra,
    "aprobado": evaluador_con_guion([aprobado()]),
    "motivo_repetido": evaluador_con_guion([rechazo("item_omitido"), rechazo("item_omitido")]),
    "maximo_reintentos": evaluador_con_guion(
        [rechazo("item_omitido"), rechazo("margen_incorrecto"), rechazo("item_duplicado")]
    ),
    "escalar": evaluador_con_guion([escalada()]),
}
