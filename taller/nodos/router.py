import logging

from langchain_anthropic import ChatAnthropic
from langsmith import traceable
from pydantic import BaseModel, Field

from .. import config
from ..estado import EstadoTaller, Intencion, OrigenIntencion

logger = logging.getLogger(__name__)

INSTRUCCIONES = """Eres la recepción de un taller mecánico. Clasifica el mensaje del cliente:
- diagnostico: describe un síntoma, ruido, falla o problema mecánico de su vehículo.
- fuera_de_alcance: cualquier otra cosa (horarios, ubicación, temas ajenos al vehículo)."""


class SalidaRouter(BaseModel):
    """Clasificación de la intención del mensaje del cliente."""

    intencion: Intencion
    justificacion: str = Field(description="Motivo de la clasificación en una frase corta.")


def crear_modelo():
    """Punto único de construcción del LLM; los tests lo reemplazan por un modelo falso."""
    return ChatAnthropic(model=config.MODELO_ROUTER, temperature=0, max_tokens=200)


@traceable(name="respaldo_router")
def respaldo_router(origen: OrigenIntencion, tipo_error: str, detalle: str) -> EstadoTaller:
    """Paso propio en la traza para que el respaldo no quede oculto bajo un router en verde."""
    logger.warning("Router en %s (%s): %s", origen, tipo_error, detalle)
    return {"intencion": "fuera_de_alcance", "origen_intencion": origen}


def router(estado: EstadoTaller) -> EstadoTaller:
    """Clasifica la intención con el LLM. Ante fallo o salida inválida, cae a fuera_de_alcance."""
    clasificador = crear_modelo().with_structured_output(SalidaRouter, include_raw=True)
    try:
        resultado = clasificador.invoke([("system", INSTRUCCIONES), ("human", estado["sintoma"])])
    except Exception as error:  # errores de API: red, autenticación, saturación
        return respaldo_router("respaldo_servicio", type(error).__name__, str(error))

    # Con include_raw=True, la validación fallida llega en parsing_error en vez de lanzarse.
    error = resultado["parsing_error"]
    if error is not None:
        return respaldo_router("respaldo_contenido", type(error).__name__, str(error))
    if resultado["parsed"] is None:
        return respaldo_router(
            "respaldo_contenido", "SinSalidaEstructurada", "El modelo no devolvió la herramienta esperada."
        )
    return {"intencion": resultado["parsed"].intencion, "origen_intencion": "llm"}
