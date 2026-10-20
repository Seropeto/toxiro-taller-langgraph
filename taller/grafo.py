"""Grafo lineal: START -> router -> diagnostico -> presupuestador -> evaluador -> END."""

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from .estado import EstadoTaller
from .nodos import diagnostico, evaluador, presupuestador, router


def construir_grafo():
    builder = StateGraph(EstadoTaller)
    builder.add_node("router", router)
    builder.add_node("diagnostico", diagnostico)
    builder.add_node("presupuestador", presupuestador)
    builder.add_node("evaluador", evaluador)

    builder.add_edge(START, "router")
    builder.add_edge("router", "diagnostico")
    builder.add_edge("diagnostico", "presupuestador")
    builder.add_edge("presupuestador", "evaluador")
    builder.add_edge("evaluador", END)
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
