from ..estado import EstadoTaller


def evaluador(estado: EstadoTaller) -> EstadoTaller:
    """Valida el presupuesto. Simulado: siempre aprueba y no incrementa intentos.

    A partir de LG-003 será el único nodo que incremente `intentos` (al rechazar).
    """
    retroalimentacion = "Presupuesto coherente con la hipótesis principal."
    return {
        "evaluacion": {"veredicto": "aprobado", "retroalimentacion": retroalimentacion},
        "retroalimentaciones": [retroalimentacion],
    }
