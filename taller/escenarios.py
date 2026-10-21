"""Guiones del Evaluador para mostrar los recorridos del ciclo (main.py --escenario) y para los tests.

Un guion es una tupla inmutable indexada por `evaluaciones`, el contador de evaluaciones que lleva el
Evaluador en el estado. No se indexa por `intentos` porque la revisión humana devuelve el caso al ciclo
sin cambiar `intentos`. Cuando el guion se agota, decide `despues` (por defecto, la regla simulada).
No hay iteradores ni contadores compartidos entre ejecuciones.
"""

from collections.abc import Sequence

from .estado import EstadoTaller, MotivoEvaluador
from .nodos.evaluador import DecisionEvaluador, SalidaEvaluador, evaluar_mano_de_obra


def aprobado(detalle: str = "Presupuesto correcto.") -> SalidaEvaluador:
    return SalidaEvaluador(veredicto="aprobado", detalle=detalle)


def rechazo(motivo: MotivoEvaluador, detalle: str | None = None) -> SalidaEvaluador:
    return SalidaEvaluador(veredicto="rechazado", motivo=motivo, detalle=detalle or f"Rechazado por {motivo}.")


def escalada(detalle: str = "Caso ambiguo: requiere revisión de un técnico.") -> SalidaEvaluador:
    return SalidaEvaluador(veredicto="escalar", detalle=detalle)


def evaluador_con_guion(
    guion: Sequence[SalidaEvaluador], despues: DecisionEvaluador = evaluar_mano_de_obra
) -> DecisionEvaluador:
    pasos = tuple(guion)

    def decidir(estado: EstadoTaller) -> SalidaEvaluador:
        indice = estado.get("evaluaciones", 0)
        return pasos[indice] if indice < len(pasos) else despues(estado)

    return decidir


TRES_RECHAZOS_DISTINTOS = (rechazo("item_omitido"), rechazo("margen_incorrecto"), rechazo("item_duplicado"))

ESCENARIOS: dict[str, DecisionEvaluador] = {
    # Regla real simulada: rechaza la primera pasada (sin mano de obra) y aprueba la corrección.
    "normal": evaluar_mano_de_obra,
    "aprobado": evaluador_con_guion([aprobado()]),
    "motivo_repetido": evaluador_con_guion([rechazo("item_omitido"), rechazo("item_omitido")]),
    "maximo_reintentos": evaluador_con_guion(TRES_RECHAZOS_DISTINTOS),
    "escalar": evaluador_con_guion([escalada()]),
    # Tras la corrección del supervisor, el Evaluador vuelve a rechazar con el máximo agotado.
    "correccion_insuficiente": evaluador_con_guion([*TRES_RECHAZOS_DISTINTOS, rechazo("hipotesis_excluida")]),
}
