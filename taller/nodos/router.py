from ..estado import EstadoTaller


def router(estado: EstadoTaller) -> EstadoTaller:
    """Clasifica la intención del cliente. Simulado: siempre diagnóstico."""
    return {"intencion": "diagnostico"}
