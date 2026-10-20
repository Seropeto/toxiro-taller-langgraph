"""Estado compartido del grafo del taller."""

import operator
from typing import Annotated, Literal, TypedDict


class Hipotesis(TypedDict):
    causa: str
    probabilidad: float
    urgencia: Literal["baja", "media", "alta"]


class ItemPresupuesto(TypedDict):
    descripcion: str
    cantidad: int
    precio_unitario: float
    subtotal: float


class Presupuesto(TypedDict):
    items: list[ItemPresupuesto]
    subtotal: float
    iva: float
    total: float


class Evaluacion(TypedDict):
    veredicto: Literal["aprobado", "rechazado"]
    retroalimentacion: str


class EstadoTaller(TypedDict, total=False):
    sintoma: str
    intencion: str
    hipotesis: list[Hipotesis]
    presupuesto: Presupuesto
    evaluacion: Evaluacion
    # Reductor: la lista que devuelve cada nodo se concatena a la existente.
    retroalimentaciones: Annotated[list[str], operator.add]
    # Solo el Evaluador lo incrementa (cuenta rechazos).
    intentos: int
    decision_humana: str | None
