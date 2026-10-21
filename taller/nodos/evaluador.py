from collections.abc import Callable

from pydantic import BaseModel, model_validator

from ..estado import EstadoTaller, Motivo, Veredicto


class SalidaEvaluador(BaseModel):
    veredicto: Veredicto
    # Obligatorio si el veredicto es rechazado; prohibido en cualquier otro caso.
    motivo: Motivo | None = None
    detalle: str

    @model_validator(mode="after")
    def _coherente_con_el_veredicto(self) -> "SalidaEvaluador":
        if self.veredicto == "rechazado" and self.motivo is None:
            raise ValueError("motivo es obligatorio cuando el veredicto es rechazado")
        if self.veredicto != "rechazado" and self.motivo is not None:
            raise ValueError(f"motivo debe ser None cuando el veredicto es {self.veredicto}")
        if self.veredicto in ("rechazado", "escalar") and not self.detalle.strip():
            raise ValueError(f"detalle no puede venir vacío cuando el veredicto es {self.veredicto}")
        return self


DecisionEvaluador = Callable[[EstadoTaller], SalidaEvaluador]


def evaluar_mano_de_obra(estado: EstadoTaller) -> SalidaEvaluador:
    """Regla simulada: rechaza si el presupuesto no incluye mano de obra; si la incluye, aprueba."""
    if any(item["categoria"] == "mano_de_obra" for item in estado["presupuesto"]["items"]):
        return SalidaEvaluador(veredicto="aprobado", detalle="Presupuesto completo: repuestos y mano de obra.")
    return SalidaEvaluador(
        veredicto="rechazado", motivo="item_omitido", detalle="Falta la mano de obra del cambio de pastillas."
    )


def crear_evaluador(decidir: DecisionEvaluador = evaluar_mano_de_obra):
    """Nodo Evaluador con la decisión inyectable; la contabilidad es la misma en producción y tests.

    Solo este nodo incrementa intentos, y solo al rechazar. La retroalimentación se agrega solo al rechazar.
    """

    def evaluador(estado: EstadoTaller) -> EstadoTaller:
        salida = decidir(estado)
        actualizacion: EstadoTaller = {"evaluacion": salida.model_dump()}
        if salida.veredicto == "rechazado":
            actualizacion["intentos"] = estado.get("intentos", 0) + 1
            actualizacion["retroalimentaciones"] = [{"motivo": salida.motivo, "detalle": salida.detalle}]
        elif salida.veredicto == "aprobado":
            # Seguro: aprobado siempre termina el grafo (regla 1 de decidir_ruta).
            actualizacion["resultado_final"] = "aprobado"
        return actualizacion

    return evaluador


evaluador = crear_evaluador()
