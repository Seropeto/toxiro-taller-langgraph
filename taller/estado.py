"""Estado compartido del grafo del taller."""

import operator
from typing import Annotated, Literal, Required, TypedDict

Intencion = Literal["diagnostico", "fuera_de_alcance"]
# llm: la intención vino del modelo.
# respaldo_contenido: el modelo respondió, pero sin la herramienta o con una salida que no valida.
# respaldo_servicio: la llamada a la API falló (autenticación, red, saturación).
OrigenIntencion = Literal["llm", "respaldo_contenido", "respaldo_servicio"]

Veredicto = Literal["aprobado", "rechazado", "escalar"]
# Motivos que puede emitir el Evaluador.
MotivoEvaluador = Literal["hipotesis_excluida", "item_duplicado", "margen_incorrecto", "item_omitido"]
# Motivos que pueden aparecer en retroalimentaciones: los del Evaluador más la corrección del supervisor.
MotivoRetroalimentacion = Literal[MotivoEvaluador, "instruccion_supervisor"]
CausaEscalada = Literal["decision_evaluador", "motivo_repetido", "maximo_reintentos"]
AccionSupervisor = Literal["aprobar", "corregir", "cancelar"]
# Un caso en revisión humana no tiene resultado final: está pendiente.
ResultadoFinal = Literal["aprobado", "cancelado", "fuera_de_alcance"]


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
    # Retroalimentaciones (del Evaluador o del supervisor) tenidas en cuenta al armar este presupuesto.
    correcciones_aplicadas: int


class Evaluacion(TypedDict):
    """Última salida del Evaluador (SalidaEvaluador serializada)."""

    veredicto: Veredicto
    motivo: MotivoEvaluador | None
    detalle: str


class Retroalimentacion(TypedDict):
    motivo: MotivoRetroalimentacion
    detalle: str


class DecisionHumana(TypedDict):
    """Última decisión del supervisor (DecisionSupervisor serializada)."""

    accion: AccionSupervisor
    instruccion: str | None
    revisor: str


class PaqueteRevision(TypedDict):
    """Lo que ve el supervisor. Serializable a JSON: es el valor del interrupt."""

    sintoma: str
    hipotesis: list[Hipotesis]
    presupuesto: Presupuesto
    evaluacion: Evaluacion
    retroalimentaciones: list[Retroalimentacion]
    causa_escalada: CausaEscalada
    aviso_version_contexto: str | None


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
    # Se agrega al rechazar (Evaluador) o al corregir (supervisor).
    retroalimentaciones: Annotated[list[Retroalimentacion], operator.add]
    # Solo el Evaluador lo incrementa, y solo al rechazar: cuenta rechazos. La revisión humana no lo reinicia.
    intentos: int
    # Evaluaciones hechas, con cualquier veredicto. Solo lo incrementa el Evaluador.
    evaluaciones: int
    causa_escalada: CausaEscalada
    paquete_revision: PaqueteRevision
    decision_humana: DecisionHumana | None
    # Resultado de la última comprobación de versión del TenantContext al resolver una revisión.
    aviso_version_contexto: str | None
    resultado_final: ResultadoFinal
