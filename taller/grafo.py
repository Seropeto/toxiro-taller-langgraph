"""Grafo del taller.

START -> router -> diagnostico -> presupuestador -> evaluador -> END
               \\-> respuesta_directa -> END   (intención fuera_de_alcance)
"""

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from .contexto import TenantContext
from .estado import EstadoTaller, Intencion
from .nodos import diagnostico, evaluador, presupuestador, respuesta_directa, router


def rutear_por_intencion(estado: EstadoTaller) -> Intencion:
    return estado["intencion"]


def construir_grafo():
    builder = StateGraph(EstadoTaller, context_schema=TenantContext)
    builder.add_node("router", router)
    builder.add_node("diagnostico", diagnostico)
    builder.add_node("presupuestador", presupuestador)
    builder.add_node("evaluador", evaluador)
    builder.add_node("respuesta_directa", respuesta_directa)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        rutear_por_intencion,
        {"diagnostico": "diagnostico", "fuera_de_alcance": "respuesta_directa"},
    )
    builder.add_edge("diagnostico", "presupuestador")
    builder.add_edge("presupuestador", "evaluador")
    builder.add_edge("evaluador", END)
    builder.add_edge("respuesta_directa", END)
    return builder.compile()


def exportar_imagen(destino: Path = Path("docs")) -> None:
    """Escribe el diagrama en Mermaid y, si hay red (mermaid.ink), también en PNG."""
    destino.mkdir(parents=True, exist_ok=True)
    dibujo = construir_grafo().get_graph()
    (destino / "grafo.mmd").write_text(dibujo.draw_mermaid(), encoding="utf-8")
    try:
        (destino / "grafo.png").write_bytes(dibujo.draw_mermaid_png())
    except Exception as error:  # el PNG depende de un servicio externo
        print(f"No se generó grafo.png: {error}")


if __name__ == "__main__":
    exportar_imagen()
