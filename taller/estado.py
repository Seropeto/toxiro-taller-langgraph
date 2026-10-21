"""Estado compartido del grafo del taller."""

import operator
from typing import Annotated, Literal, Required, TypedDict

Intencion = Literal["diagnostico", "fuera_de_alcance"]
# llm: la intención vino del modelo.
# respaldo_contenido: el modelo respondió, pero sin la herramienta o con una salida que no valida.
# respaldo_servicio: la llamada a la API falló (autenticación, red, saturación).
OrigenIntencion = Literal["llm", "respaldo_contenido", "respaldo_servicio"]

Veredicto = Literal["aprobado", "rechazado", "escalar"]
Motivo = Literal["hipotesis_excluida", "item_duplicado", "margen_incorrecto", "item_omitido"]
CausaEscalada = Literal["decision_evaluador", "motivo_repetido", "maximo_reintentos"]
ResultadoFinal = Literal["aprobado", "escalado", "fuera_de_alcance"]


class Hipotesis(TypedDict):
    causa: str
    probabilidad: float
    urgencia: Literal["baja", "media", "alta"]


class ItemPresupuesto(TypedDict):
    descripcion: str
    categoria: str
    cantidad: int
    precio_unitario: float
    subtotal: float


class Presupuesto(TypedDict):
    taller: str
    items: list[ItemPresupuesto]
    subtotal: float
    iva: float
    total: float
    # Retroalimentaciones del Evaluador tenidas en cuenta al armar este presupuesto.
    correcciones_aplicadas: int


class Evaluacion(TypedDict):
    """Última salida del Evaluador (SalidaEvaluador serializada)."""

    veredicto: Veredicto
    motivo: Motivo | None
    detalle: str


class Retroalimentacion(TypedDict):
    motivo: Motivo
    detalle: str


class EstadoTaller(TypedDict, total=False):
    # Obligatorio solo a nivel de tipado: LangGraph no lo valida al invocar.
    sintoma: Required[str]
    intencion: Intencion
    origen_intencion: OrigenIntencion
    mensaje_respuesta: str
    hipotesis: list[Hipotesis]
    presupuesto: Presupuesto
    evaluacion: Evaluacion
    # Reductor: la lista que devuelve cada nodo se concatena a la existente. Solo se agrega al rechazar.
    retroalimentaciones: Annotated[list[Retroalimentacion], operator.add]
    # Solo el Evaluador lo incrementa, y solo al rechazar: cuenta rechazos.
    intentos: int
    resultado_final: ResultadoFinal
    causa_escalada: CausaEscalada
    decision_humana: str | None
