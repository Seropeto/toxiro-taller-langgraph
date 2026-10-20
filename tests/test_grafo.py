from taller.grafo import construir_grafo


def test_estado_final_poblado():
    estado = construir_grafo().invoke(
        {"sintoma": "Rechinido al frenar", "retroalimentaciones": [], "intentos": 0}
    )

    assert estado["sintoma"] == "Rechinido al frenar"
    assert estado["intencion"] == "diagnostico"
    assert len(estado["hipotesis"]) > 0
    assert all({"causa", "probabilidad", "urgencia"} <= h.keys() for h in estado["hipotesis"])
    presupuesto = estado["presupuesto"]
    assert presupuesto["items"]
    assert presupuesto["total"] == presupuesto["subtotal"] + presupuesto["iva"]
    assert estado["evaluacion"]["veredicto"] == "aprobado"
    assert estado["intentos"] == 0  # en LG-001 el evaluador no incrementa
    assert len(estado["retroalimentaciones"]) == 1


def test_grafo_lineal():
    dibujo = construir_grafo().get_graph()
    aristas = {(a.source, a.target) for a in dibujo.edges}
    assert aristas == {
        ("__start__", "router"),
        ("router", "diagnostico"),
        ("diagnostico", "presupuestador"),
        ("presupuestador", "evaluador"),
        ("evaluador", "__end__"),
    }
