"""Recorridos completos del ciclo Evaluador -> Presupuestador, con router falso y guiones del Evaluador.

Todos verifican origen_intencion == "llm": si el router cayera en un respaldo, el recorrido sería otro
y el test fallaría por la causa real, no por un síntoma.
"""

import pytest
from conftest import ejecutar, salida_llm
from langgraph.errors import GraphRecursionError

from taller import config
from taller.escenarios import ESCENARIOS, aprobado, evaluador_con_guion, rechazo
from taller.grafo import construir_grafo


@pytest.fixture(autouse=True)
def router_diagnostico(usar_modelo):
    usar_modelo(salida_llm(intencion="diagnostico", justificacion="Falla mecánica."))


@pytest.mark.parametrize(
    ("escenario", "corridas_presupuestador", "intentos", "resultado", "causa"),
    [
        ("normal", 2, 1, "aprobado", None),
        ("motivo_repetido", 2, 2, "escalado", "motivo_repetido"),
        ("maximo_reintentos", 3, 3, "escalado", "maximo_reintentos"),
        ("escalar", 1, 0, "escalado", "decision_evaluador"),
        ("aprobado", 1, 0, "aprobado", None),
    ],
)
def test_criterios_de_aceptacion(entrada, contexto, escenario, corridas_presupuestador, intentos, resultado, causa):
    nodos, estado = ejecutar(construir_grafo(decidir_evaluacion=ESCENARIOS[escenario]), entrada, contexto)

    assert estado["origen_intencion"] == "llm"
    assert nodos.count("presupuestador") == corridas_presupuestador
    assert estado["intentos"] == intentos
    assert len(estado["retroalimentaciones"]) == intentos  # una por rechazo, ninguna al aprobar o escalar
    assert estado["resultado_final"] == resultado
    assert estado.get("causa_escalada") == causa
    assert nodos[-1] == ("escalar" if resultado == "escalado" else "evaluador")


def test_aprobado_de_inmediato_deja_retroalimentaciones_vacia(entrada, contexto):
    estado = construir_grafo(decidir_evaluacion=ESCENARIOS["aprobado"]).invoke(entrada, context=contexto)

    assert estado["origen_intencion"] == "llm"
    assert estado["retroalimentaciones"] == []
    assert estado["intentos"] == 0


def test_retroalimentacion_estructurada_se_acumula_en_orden(entrada, contexto):
    estado = construir_grafo(decidir_evaluacion=ESCENARIOS["maximo_reintentos"]).invoke(entrada, context=contexto)

    assert estado["origen_intencion"] == "llm"
    assert [r["motivo"] for r in estado["retroalimentaciones"]] == [
        "item_omitido",
        "margen_incorrecto",
        "item_duplicado",
    ]
    assert all(r["detalle"] for r in estado["retroalimentaciones"])
    assert estado["presupuesto"]["correcciones_aplicadas"] == 2  # la tercera pasada vio dos rechazos


def test_el_guion_no_comparte_estado_entre_ejecuciones(entrada, contexto):
    grafo = construir_grafo(decidir_evaluacion=evaluador_con_guion([rechazo("item_omitido"), aprobado()]))

    primera = grafo.invoke(entrada, context=contexto)
    segunda = grafo.invoke(entrada, context=contexto)

    assert primera["origen_intencion"] == "llm"
    assert primera == segunda


def test_limite_de_recursion_alcanza_justo_para_el_peor_caso(entrada, contexto):
    grafo = construir_grafo(decidir_evaluacion=ESCENARIOS["maximo_reintentos"])

    exacto = grafo.with_config(recursion_limit=config.PASOS_PEOR_CASO).invoke(entrada, context=contexto)
    assert exacto["origen_intencion"] == "llm"
    assert exacto["causa_escalada"] == "maximo_reintentos"

    with pytest.raises(GraphRecursionError):
        grafo.with_config(recursion_limit=config.PASOS_PEOR_CASO - 1).invoke(entrada, context=contexto)


def test_el_grafo_usa_el_limite_calculado():
    assert construir_grafo().config["recursion_limit"] == config.LIMITE_RECURSION == 15
