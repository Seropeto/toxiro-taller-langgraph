import logging

import pytest
from conftest import ModeloQueFalla, salida_llm
from langchain_core.messages import AIMessage

from taller.grafo import construir_grafo, rutear_por_intencion
from taller.nodos import router
from taller.nodos.respuesta_directa import (
    MENSAJE_FUERA_DE_ALCANCE,
    MENSAJE_REFORMULAR,
    MENSAJE_SERVICIO_NO_DISPONIBLE,
)

RESPALDO_CONTENIDO = {"intencion": "fuera_de_alcance", "origen_intencion": "respaldo_contenido"}
RESPALDO_SERVICIO = {"intencion": "fuera_de_alcance", "origen_intencion": "respaldo_servicio"}


def ramas_del_router() -> dict[str, str]:
    """Valor de la función de ruteo -> nodo destino, leído del grafo compilado.

    get_graph() omite la etiqueta de la arista cuando coincide con el nombre del destino.
    """
    aristas = construir_grafo().get_graph().edges
    return {(a.data or a.target): a.target for a in aristas if a.source == "router" and a.conditional}


@pytest.mark.parametrize(
    ("intencion", "nodo_destino"),
    [("diagnostico", "diagnostico"), ("fuera_de_alcance", "respuesta_directa")],
)
def test_ruteo_envia_cada_intencion_a_su_nodo(intencion, nodo_destino):
    valor = rutear_por_intencion({"sintoma": "x", "intencion": intencion})

    assert ramas_del_router()[valor] == nodo_destino


def test_ruteo_cubre_exactamente_las_intenciones():
    assert ramas_del_router() == {"diagnostico": "diagnostico", "fuera_de_alcance": "respuesta_directa"}


def test_router_con_salida_valida_usa_el_llm(usar_modelo):
    usar_modelo(salida_llm(intencion="diagnostico", justificacion="Ruido al frenar."))

    assert router({"sintoma": "Rechinido al frenar"}) == {
        "intencion": "diagnostico",
        "origen_intencion": "llm",
    }


def test_salida_invalida_es_respaldo_de_contenido(usar_modelo, caplog):
    usar_modelo(salida_llm(intencion="cotizacion", justificacion="Pide precio."))

    with caplog.at_level(logging.WARNING, logger="taller.nodos.router"):
        resultado = router({"sintoma": "¿Cuánto cuesta un cambio de aceite?"})

    assert resultado == RESPALDO_CONTENIDO
    assert "ValidationError" in caplog.text


def test_sin_llamada_a_la_herramienta_es_respaldo_de_contenido(usar_modelo, caplog):
    usar_modelo(AIMessage(content="Creo que es un tema de frenos."))

    with caplog.at_level(logging.WARNING, logger="taller.nodos.router"):
        resultado = router({"sintoma": "Rechinido al frenar"})

    assert resultado == RESPALDO_CONTENIDO
    assert "SinSalidaEstructurada" in caplog.text


def test_error_de_api_es_respaldo_de_servicio(usar_modelo, caplog):
    usar_modelo(ModeloQueFalla(messages=iter([])))

    with caplog.at_level(logging.WARNING, logger="taller.nodos.router"):
        resultado = router({"sintoma": "Rechinido al frenar"})

    assert resultado == RESPALDO_SERVICIO
    assert "ConnectionError" in caplog.text


@pytest.mark.parametrize(
    ("respuesta_modelo", "origen", "mensaje"),
    [
        (salida_llm(intencion="fuera_de_alcance", justificacion="Horarios."), "llm", MENSAJE_FUERA_DE_ALCANCE),
        (salida_llm(intencion="otra", justificacion="Inválida."), "respaldo_contenido", MENSAJE_REFORMULAR),
        (AIMessage(content="Sin herramienta."), "respaldo_contenido", MENSAJE_REFORMULAR),
        (ModeloQueFalla(messages=iter([])), "respaldo_servicio", MENSAJE_SERVICIO_NO_DISPONIBLE),
    ],
    ids=["llm_fuera_de_alcance", "contenido_salida_invalida", "contenido_sin_herramienta", "servicio_error_api"],
)
def test_respuesta_directa_elige_mensaje_por_origen(usar_modelo, entrada, contexto, respuesta_modelo, origen, mensaje):
    usar_modelo(respuesta_modelo)

    estado = construir_grafo().invoke(entrada, context=contexto)

    assert estado["intencion"] == "fuera_de_alcance"
    assert estado["origen_intencion"] == origen
    assert estado["mensaje_respuesta"] == mensaje
    assert "hipotesis" not in estado


def test_los_tres_mensajes_son_distintos():
    assert len({MENSAJE_FUERA_DE_ALCANCE, MENSAJE_REFORMULAR, MENSAJE_SERVICIO_NO_DISPONIBLE}) == 3
