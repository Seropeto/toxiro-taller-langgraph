from conftest import ejecutar, salida_llm

from taller.contexto import TenantContext
from taller.estado import EstadoTaller
from taller.grafo import construir_grafo


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
    assert estado["resultado_final"] == "aprobado"
    # Caso normal: la primera pasada omite la mano de obra, se rechaza una vez y se aprueba la corrección.
    assert estado["intentos"] == 1
    assert estado["retroalimentaciones"] == [
        {"motivo": "item_omitido", "detalle": "Falta la mano de obra del cambio de pastillas."}
    ]
    assert "mensaje_respuesta" not in estado


def test_recorrido_mecanico(usar_modelo, entrada, contexto):
    usar_modelo(salida_llm(intencion="diagnostico", justificacion="Falla mecánica."))

    nodos, estado = ejecutar(construir_grafo(), entrada, contexto)

    assert estado["origen_intencion"] == "llm"
    assert nodos == ["router", "diagnostico", "presupuestador", "evaluador", "presupuestador", "evaluador"]


def test_recorrido_fuera_de_alcance_no_pasa_por_diagnostico(usar_modelo, entrada, contexto):
    usar_modelo(salida_llm(intencion="fuera_de_alcance", justificacion="Pregunta por horarios."))
    entrada["sintoma"] = "¿A qué hora cierran el sábado?"

    nodos, estado = ejecutar(construir_grafo(), entrada, contexto)

    assert estado["origen_intencion"] == "llm"
    assert nodos == ["router", "respuesta_directa"]


def test_fuera_de_alcance_marca_el_resultado_final(usar_modelo, entrada, contexto):
    usar_modelo(salida_llm(intencion="fuera_de_alcance", justificacion="Pregunta por horarios."))

    estado = construir_grafo().invoke(entrada, context=contexto)

    assert estado["origen_intencion"] == "llm"
    assert estado["resultado_final"] == "fuera_de_alcance"
    assert "causa_escalada" not in estado


def test_contexto_no_aparece_en_el_estado(usar_modelo, entrada, contexto):
    usar_modelo(salida_llm(intencion="diagnostico", justificacion="Falla mecánica."))

    estado = construir_grafo().invoke(entrada, context=contexto)

    assert estado["origen_intencion"] == "llm"
    assert set(estado) <= set(EstadoTaller.__annotations__)
    assert not any(isinstance(valor, TenantContext) for valor in estado.values())


def test_grafo_bifurca_desde_router_cicla_desde_evaluador_y_vuelve_desde_la_revision():
    dibujo = construir_grafo().get_graph()
    aristas = {(a.source, a.target) for a in dibujo.edges}
    assert aristas == {
        ("__start__", "router"),
        ("router", "diagnostico"),
        ("router", "respuesta_directa"),
        ("diagnostico", "presupuestador"),
        ("presupuestador", "evaluador"),
        ("evaluador", "presupuestador"),
        ("evaluador", "preparar_revision"),
        ("evaluador", "__end__"),
        ("preparar_revision", "revision_humana"),
        ("revision_humana", "presupuestador"),
        ("revision_humana", "__end__"),
        ("respuesta_directa", "__end__"),
    }
    condicionales = {(a.source, a.target) for a in dibujo.edges if a.conditional}
    assert condicionales == {
        ("router", "diagnostico"),
        ("router", "respuesta_directa"),
        ("evaluador", "presupuestador"),
        ("evaluador", "preparar_revision"),
        ("evaluador", "__end__"),
        ("revision_humana", "presupuestador"),
        ("revision_humana", "__end__"),
    }
