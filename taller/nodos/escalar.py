from ..estado import EstadoTaller
from ..ruteo import decidir_ruta


def escalar(estado: EstadoTaller) -> EstadoTaller:
    """Provisional: marca el resultado y termina. En LG-005 pasa a revisión humana con interrupt.

    La causa sale de la misma regla que eligió el borde: el estado no cambia entre el borde y este nodo.
    """
    return {"resultado_final": "escalado", "causa_escalada": decidir_ruta(estado).causa}
