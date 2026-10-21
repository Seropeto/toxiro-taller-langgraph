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
        modelo = respuesta if isinstance(respuesta, ModeloFalso) else ModeloFalso(messages=iter([respuesta]))
        monkeypatch.setattr(modulo_router, "crear_modelo", lambda: modelo)

    return instalar


@pytest.fixture
def contexto():
    return cargar_contexto()


@pytest.fixture
def entrada():
    return {"sintoma": "Rechinido metálico al frenar", "retroalimentaciones": [], "intentos": 0}
