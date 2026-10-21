"""Recorridos completos del ciclo Evaluador -> Presupuestador, con router falso y guiones del Evaluador.

Todos verifican origen_intencion == "llm": si el router cayera en un respaldo, el recorrido sería otro
y el test fallaría por la causa real, no por un síntoma. Los casos que escalan quedan pendientes en
revision_humana, que necesita checkpointer: por eso se ejecutan con la capa de casos y un InMemorySaver.
"""

import pytest
from conftest import salida_llm
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from taller import config
from taller.casos import iniciar_caso, resolver_revision, situacion_caso
from taller.escenarios import ESCENARIOS, aprobado, escalada, evaluador_con_guion, rechazo
from taller.grafo import construir_grafo


@pytest.fixture(autouse=True)
def router_diagnostico(usar_modelo):
    usar_modelo(salida_llm(intencion="diagnostico", justificacion="Falla mecánica."))


def grafo_con(decidir, recursion_limit=None):
    grafo = construir_grafo(decidir_evaluacion=decidir, checkpointer=InMemorySaver())
    return grafo.with_config(recursion_limit=recursion_limit) if recursion_limit else grafo


@pytest.mark.parametrize(
    ("escenario", "corridas_presupuestador", "intentos", "resultado", "causa"),
    [
        ("normal", 2, 1, "aprobado", None),
        ("motivo_repetido", 2, 2, None, "motivo_repetido"),
        ("maximo_reintentos", 3, 3, None, "maximo_reintentos"),
        ("escalar", 1, 0, None, "decision_evaluador"),
        ("aprobado", 1, 0, "aprobado", None),
    ],
)
def test_criterios_de_aceptacion(entrada, contexto, escenario, corridas_presupuestador, intentos, resultado, causa):
    grafo = grafo_con(ESCENARIOS[escenario])

    ejecucion = iniciar_caso(grafo, entrada, contexto)
    estado = ejecucion.estado

    assert estado["origen_intencion"] == "llm"
    assert ejecucion.nodos.count("presupuestador") == corridas_presupuestador
    assert estado["intentos"] == intentos
    assert len(estado["retroalimentaciones"]) == intentos  # una por rechazo, ninguna al aprobar o escalar
    assert estado.get("resultado_final") == resultado
    assert estado.get("causa_escalada") == causa
    if causa:  # escaló: queda pendiente de revisión humana, sin resultado final
        assert ejecucion.pendiente
        assert ejecucion.paquete["causa_escalada"] == causa
        assert ejecucion.nodos[-1] == "preparar_revision"
        assert situacion_caso(grafo, ejecucion.thread_id) == "pendiente_revision"
    else:
        assert not ejecucion.pendiente
        assert ejecucion.nodos[-1] == "evaluador"


def test_aprobado_de_inmediato_deja_retroalimentaciones_vacia(entrada, contexto):
    estado = iniciar_caso(grafo_con(ESCENARIOS["aprobado"]), entrada, contexto).estado

    assert estado["origen_intencion"] == "llm"
    assert estado["retroalimentaciones"] == []
    assert estado["intentos"] == 0


def test_retroalimentacion_estructurada_se_acumula_en_orden(entrada, contexto):
    estado = iniciar_caso(grafo_con(ESCENARIOS["maximo_reintentos"]), entrada, contexto).estado

    assert estado["origen_intencion"] == "llm"
    assert [r["motivo"] for r in estado["retroalimentaciones"]] == [
        "item_omitido",
        "margen_incorrecto",
        "item_duplicado",
    ]
    assert all(r["detalle"] for r in estado["retroalimentaciones"])
    assert estado["presupuesto"]["correcciones_aplicadas"] == 2  # la tercera pasada vio dos rechazos


def test_el_guion_no_comparte_estado_entre_ejecuciones(entrada, contexto):
    grafo = grafo_con(evaluador_con_guion([rechazo("item_omitido"), aprobado()]))

    primera = iniciar_caso(grafo, entrada, contexto).estado
    segunda = iniciar_caso(grafo, entrada, contexto).estado

    assert primera["origen_intencion"] == "llm"
    assert primera == segunda


def test_el_guion_se_indexa_por_evaluaciones_y_sigue_con_despues(entrada, contexto):
    grafo = grafo_con(evaluador_con_guion([escalada()]))  # luego decide la regla simulada

    pendiente = iniciar_caso(grafo, entrada, contexto)
    assert pendiente.estado["evaluaciones"] == 1
    corregido = resolver_revision(
        grafo, pendiente.thread_id, {"accion": "corregir", "instruccion": "Revisar", "revisor": "ana"}, contexto
    )

    assert corregido.estado["origen_intencion"] == "llm"
    assert corregido.estado["evaluaciones"] == 2
    assert corregido.estado["resultado_final"] == "aprobado"  # la regla simulada ve la mano de obra


def test_limite_de_recursion_alcanza_justo_para_el_peor_caso(entrada, contexto):
    exacto = iniciar_caso(
        grafo_con(ESCENARIOS["maximo_reintentos"], recursion_limit=config.PASOS_PEOR_CASO), entrada, contexto
    )
    assert exacto.estado["origen_intencion"] == "llm"
    assert exacto.pendiente and exacto.paquete["causa_escalada"] == "maximo_reintentos"

    with pytest.raises(GraphRecursionError):
        iniciar_caso(
            grafo_con(ESCENARIOS["maximo_reintentos"], recursion_limit=config.PASOS_PEOR_CASO - 1), entrada, contexto
        )


def test_la_reanudacion_del_peor_caso_usa_menos_pasos_que_la_ejecucion_inicial(entrada, contexto):
    # Peor caso al reanudar: escalada sin intentos usados, corrección y tres rechazos más.
    guion = [escalada(), rechazo("item_omitido"), rechazo("margen_incorrecto"), rechazo("item_duplicado")]
    grafo = grafo_con(evaluador_con_guion(guion), recursion_limit=config.PASOS_PEOR_CASO - 1)
    pendiente = iniciar_caso(grafo, entrada, contexto)

    reanudado = resolver_revision(
        grafo, pendiente.thread_id, {"accion": "corregir", "instruccion": "Revisar", "revisor": "ana"}, contexto
    )

    assert reanudado.estado["origen_intencion"] == "llm"
    assert reanudado.nodos.count("presupuestador") == 3
    assert reanudado.pendiente and reanudado.paquete["causa_escalada"] == "maximo_reintentos"


def test_el_grafo_usa_el_limite_calculado():
    assert config.PASOS_PEOR_CASO == 10
    assert construir_grafo().config["recursion_limit"] == config.LIMITE_RECURSION == 15
