from typing import get_type_hints

from langgraph.graph import END, START, StateGraph

from taller.estado import EstadoTaller


def _reductor_retroalimentaciones():
    anotacion = get_type_hints(EstadoTaller, include_extras=True)["retroalimentaciones"]
    return anotacion.__metadata__[0]


def test_reductor_unitario_dos_agregados_dan_dos_elementos():
    reductor = _reductor_retroalimentaciones()
    acumulado = reductor([], ["primera"])
    acumulado = reductor(acumulado, ["segunda"])
    assert acumulado == ["primera", "segunda"]


def test_reductor_en_grafo_aislado():
    """Grafo mínimo con el estado real y dos nodos que agregan, sin los nodos del taller."""
    builder = StateGraph(EstadoTaller)
    builder.add_node("a", lambda _: {"retroalimentaciones": ["primera"]})
    builder.add_node("b", lambda _: {"retroalimentaciones": ["segunda"]})
    builder.add_edge(START, "a")
    builder.add_edge("a", "b")
    builder.add_edge("b", END)

    estado = builder.compile().invoke({"retroalimentaciones": []})

    assert estado["retroalimentaciones"] == ["primera", "segunda"]
