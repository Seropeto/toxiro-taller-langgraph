"""Estado compartido del grafo del taller."""

import operator
from typing import Annotated, Literal, Required, TypedDict

Intencion = Literal["diagnostico", "fuera_de_alcance"]
# llm: la intención vino del modelo.
# respaldo_contenido: el modelo respondió, pero sin la herramienta o con una salida que no valida.
# respaldo_servicio: la llamada a la API falló (autenticación, red, saturación).
OrigenIntencion = Literal["llm", "respaldo_contenido", "respaldo_servicio"]


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
    taller: str
    items: list[ItemPresupuesto]
    subtotal: float
    iva: float
    total: float


class Evaluacion(TypedDict):
    veredicto: Literal["aprobado", "rechazado"]
    retroalimentacion: str


class EstadoTaller(TypedDict, total=False):
    # Obligatorio solo a nivel de tipado: LangGraph no lo valida al invocar.
    sintoma: Required[str]
    intencion: Intencion
    origen_intencion: OrigenIntencion
    mensaje_respuesta: str
    hipotesis: list[Hipotesis]
    presupuesto: Presupuesto
    evaluacion: Evaluacion
    # Reductor: la lista que devuelve cada nodo se concatena a la existente.
    retroalimentaciones: Annotated[list[str], operator.add]
    # Solo el Evaluador lo incrementa (cuenta rechazos).
    intentos: int
    decision_humana: str | None
