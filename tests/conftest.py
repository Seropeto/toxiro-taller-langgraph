import os
from importlib import import_module

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

# Los tests no deben enviar trazas a LangSmith aunque el .env lo active.
os.environ["LANGSMITH_TRACING"] = "false"

from taller.contexto import cargar_contexto  # noqa: E402

# `taller.nodos.router` como atributo es la función (la re-exporta nodos/__init__); el módulo sale de sys.modules.
modulo_router = import_module("taller.nodos.router")


class ModeloFalso(GenericFakeChatModel):
    """Modelo falso que acepta bind_tools, para usarlo con with_structured_output.

    Devuelve AIMessages con tool calls, así el test pasa por el parser real de LangChain.
    """

    def bind_tools(self, tools, **kwargs):
        return self


class ModeloQueFalla(ModeloFalso):
    """Simula un error de API (red, autenticación, sobrecarga)."""

    def _generate(self, *args, **kwargs):
        raise ConnectionError("API de Anthropic no disponible")


def salida_llm(**argumentos) -> AIMessage:
    """AIMessage como el que devuelve Claude al llamar la herramienta SalidaRouter."""
    return AIMessage(
        content="",
        tool_calls=[{"name": "SalidaRouter", "args": argumentos, "id": "llamada-1"}],
    )


@pytest.fixture
def usar_modelo(monkeypatch):
    """Reemplaza el LLM del router: usar_modelo(salida_llm(...)) o usar_modelo(modelo)."""

    def instalar(respuesta):
        if isinstance(respuesta, ModeloFalso):
            crear = lambda: respuesta  # noqa: E731
        else:
            # Un modelo nuevo por llamada: el iterador de mensajes no se agota si el grafo corre varias veces.
            crear = lambda: ModeloFalso(messages=iter([respuesta]))  # noqa: E731
        monkeypatch.setattr(modulo_router, "crear_modelo", crear)

    return instalar


@pytest.fixture
def llamadas_router(monkeypatch):
    """Router falso (diagnóstico) que cuenta cuántas veces se construye el LLM: una por ejecución del router."""
    llamadas = []

    def crear():
        llamadas.append(1)
        return ModeloFalso(messages=iter([salida_llm(intencion="diagnostico", justificacion="Falla mecánica.")]))

    monkeypatch.setattr(modulo_router, "crear_modelo", crear)
    return llamadas


@pytest.fixture
def contexto():
    return cargar_contexto()


def ejecutar(grafo, entrada, contexto) -> tuple[list[str], dict]:
    """Ejecuta el grafo una vez y devuelve los nodos recorridos, en orden, y el estado final."""
    nodos, estado = [], {}
    for modo, datos in grafo.stream(entrada, context=contexto, stream_mode=["updates", "values"]):
        if modo == "updates":
            nodos.extend(datos)
        else:
            estado = datos
    return nodos, estado


@pytest.fixture
def entrada():
    return {"sintoma": "Rechinido metálico al frenar", "retroalimentaciones": [], "intentos": 0}
