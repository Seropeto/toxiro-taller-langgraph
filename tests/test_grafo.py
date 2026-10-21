from conftest import salida_llm

from taller.contexto import TenantContext
from taller.estado import EstadoTaller
from taller.grafo import construir_grafo


def recorrido(grafo, entrada, contexto) -> list[str]:
    """Nodos ejecutados, en orden."""
    return [nodo for paso in grafo.stream(entrada, context=contexto, stream_mode="updates") for nodo in paso]


def test_estado_final_poblado(usar_modelo, entrada, contexto):
    usar_modelo(salida_llm(intencion="diagnostico", justificacion="Describe un ruido al frenar."))

    estado = construir_grafo().invoke(entrada, context=contexto)

    assert estado["sintoma"] == entrada["sintoma"]
    assert estado["intencion"] == "diagnostico"
    assert estado["origen_intencion"] == "llm"
    assert len(estado["hipotesis"]) > 0
    assert all({"causa", "probabilidad", "urgencia"} <= h.keys() for h in estado["hipotesis"])
    presupuesto = estado["presupuesto"]
    assert presupuesto["items"]
    assert presupuesto["total"] == presupuesto["subtotal"] + presupuesto["iva"]
    assert estado["evaluacion"]["veredicto"] == "aprobado"
    assert estado["intentos"] == 0  # el evaluador sigue sin incrementar hasta LG-003
    assert len(estado["retroalimentaciones"]) == 1
    assert "mensaje_respuesta" not in estado


def test_recorrido_mecanico(usar_modelo, entrada, contexto):
    usar_modelo(salida_llm(intencion="diagnostico", justificacion="Falla mecánica."))

    assert recorrido(construir_grafo(), entrada, contexto) == [
        "router",
        "diagnostico",
        "presupuestador",
        "evaluador",
    ]


def test_recorrido_fuera_de_alcance_no_pasa_por_diagnostico(usar_modelo, entrada, contexto):
    usar_modelo(salida_llm(intencion="fuera_de_alcance", justificacion="Pregunta por horarios."))
    entrada["sintoma"] = "¿A qué hora cierran el sábado?"

    assert recorrido(construir_grafo(), entrada, contexto) == ["router", "respuesta_directa"]


def test_contexto_no_aparece_en_el_estado(usar_modelo, entrada, contexto):
    usar_modelo(salida_llm(intencion="diagnostico", justificacion="Falla mecánica."))

    estado = construir_grafo().invoke(entrada, context=contexto)

    assert set(estado) <= set(EstadoTaller.__annotations__)
    assert not any(isinstance(valor, TenantContext) for valor in estado.values())


def test_grafo_bifurca_desde_router():
    dibujo = construir_grafo().get_graph()
    aristas = {(a.source, a.target) for a in dibujo.edges}
    assert aristas == {
        ("__start__", "router"),
        ("router", "diagnostico"),
        ("router", "respuesta_directa"),
        ("diagnostico", "presupuestador"),
        ("presupuestador", "evaluador"),
        ("evaluador", "__end__"),
        ("respuesta_directa", "__end__"),
    }
    condicionales = {(a.source, a.target) for a in dibujo.edges if a.conditional}
    assert condicionales == {("router", "diagnostico"), ("router", "respuesta_directa")}
