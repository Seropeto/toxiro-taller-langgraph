"""Revisión humana con interrupt: pausa, decisión del supervisor, validación y versión del contexto."""

import json
from typing import get_type_hints

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from taller.casos import (
    CasoEnCursoError,
    CasoInexistenteError,
    CasoNoPendienteDeRevisionError,
    CasoPendienteDeRevisionError,
    DecisionInvalidaError,
    casos_pendientes,
    estado_caso,
    historial_caso,
    iniciar_caso,
    resolver_revision,
    retomar_caso,
    situacion_caso,
)
from taller.contexto import RUTA_EJEMPLO_V2, RUTA_SIN_PASTILLAS, cargar_contexto
from taller.escenarios import ESCENARIOS
from taller.estado import PaqueteRevision
from taller.grafo import construir_grafo
from taller.nodos.revision import DecisionSupervisor

APROBAR = {"accion": "aprobar", "revisor": "ana"}
CANCELAR = {"accion": "cancelar", "revisor": "ana"}
CORREGIR = {"accion": "corregir", "instruccion": "Revisar el margen de las pastillas.", "revisor": "ana"}


@pytest.fixture
def saver():
    return InMemorySaver()


def grafo_con(saver, escenario):
    return construir_grafo(ESCENARIOS[escenario], checkpointer=saver)


def abrir_pendiente(saver, entrada, contexto, escenario="maximo_reintentos"):
    grafo = grafo_con(saver, escenario)
    ejecucion = iniciar_caso(grafo, entrada, contexto)
    assert ejecucion.pendiente
    return grafo, ejecucion


# --- DecisionSupervisor ---------------------------------------------------------------------------------


@pytest.mark.parametrize("datos", [APROBAR, CANCELAR, CORREGIR], ids=["aprobar", "cancelar", "corregir"])
def test_decisiones_validas(datos):
    assert DecisionSupervisor(**datos).model_dump() == {"instruccion": None, **datos}


DECISIONES_INVALIDAS = {
    "accion_desconocida": {"accion": "archivar", "revisor": "ana"},
    "corregir_sin_instruccion": {"accion": "corregir", "revisor": "ana"},
    "corregir_instruccion_vacia": {"accion": "corregir", "instruccion": "   ", "revisor": "ana"},
    "sin_revisor": {"accion": "aprobar"},
    "revisor_vacio": {"accion": "aprobar", "revisor": "  "},
    "aprobar_con_instruccion": {"accion": "aprobar", "instruccion": "x", "revisor": "ana"},
    "cancelar_con_instruccion": {"accion": "cancelar", "instruccion": "x", "revisor": "ana"},
    "campo_desconocido": {"accion": "aprobar", "revisor": "ana", "instrucion": "x"},
}


@pytest.mark.parametrize("datos", DECISIONES_INVALIDAS.values(), ids=DECISIONES_INVALIDAS.keys())
def test_decisiones_invalidas_del_modelo(datos):
    with pytest.raises(ValidationError):
        DecisionSupervisor(**datos)


# --- Pausa ----------------------------------------------------------------------------------------------


def test_un_caso_que_escala_queda_pendiente_con_el_paquete(saver, llamadas_router, entrada, contexto):
    grafo, ejecucion = abrir_pendiente(saver, entrada, contexto)

    assert ejecucion.estado["origen_intencion"] == "llm"
    assert set(ejecucion.paquete) == set(get_type_hints(PaqueteRevision))
    assert ejecucion.paquete["causa_escalada"] == "maximo_reintentos"
    assert ejecucion.paquete["aviso_version_contexto"] is None
    json.dumps(ejecucion.paquete)  # serializable a JSON
    assert "resultado_final" not in estado_caso(grafo, ejecucion.thread_id)
    assert estado_caso(grafo, ejecucion.thread_id)["causa_escalada"] == "maximo_reintentos"
    ultimo = historial_caso(grafo, ejecucion.thread_id)[-1]
    assert ultimo.en_pausa and ultimo.siguiente == ("revision_humana",)
    assert situacion_caso(grafo, ejecucion.thread_id) == "pendiente_revision"


# --- Resolución -----------------------------------------------------------------------------------------


def test_aprobar_termina_sin_repetir_router_diagnostico_ni_presupuestador(saver, llamadas_router, entrada, contexto):
    grafo, pendiente = abrir_pendiente(saver, entrada, contexto)

    resuelto = resolver_revision(grafo, pendiente.thread_id, APROBAR, contexto)

    assert resuelto.nodos == ["revision_humana"]
    assert resuelto.estado["origen_intencion"] == "llm"
    assert resuelto.estado["resultado_final"] == "aprobado"
    assert resuelto.estado["decision_humana"] == {"accion": "aprobar", "instruccion": None, "revisor": "ana"}
    assert situacion_caso(grafo, pendiente.thread_id) == "cerrado"
    assert len(llamadas_router) == 1


def test_cancelar_termina_en_cancelado(saver, llamadas_router, entrada, contexto):
    grafo, pendiente = abrir_pendiente(saver, entrada, contexto)

    resuelto = resolver_revision(grafo, pendiente.thread_id, CANCELAR, contexto)

    assert resuelto.estado["origen_intencion"] == "llm"
    assert resuelto.estado["resultado_final"] == "cancelado"
    assert resuelto.nodos == ["revision_humana"]


def test_corregir_vuelve_al_presupuestador_y_al_evaluador(saver, llamadas_router, entrada, contexto):
    grafo, pendiente = abrir_pendiente(saver, entrada, contexto)

    resuelto = resolver_revision(grafo, pendiente.thread_id, CORREGIR, contexto)
    estado = resuelto.estado

    assert resuelto.nodos == ["revision_humana", "presupuestador", "evaluador"]
    assert estado["origen_intencion"] == "llm"
    assert estado["retroalimentaciones"][-1] == {
        "motivo": "instruccion_supervisor",
        "detalle": "Revisar el margen de las pastillas.",
    }
    # El Presupuestador recibió la instrucción (4 retroalimentaciones) y el Evaluador volvió a evaluar.
    assert estado["presupuesto"]["correcciones_aplicadas"] == 4
    assert estado["evaluaciones"] == pendiente.estado["evaluaciones"] + 1
    assert estado["intentos"] == 3  # la intervención humana no reinicia intentos
    assert estado["resultado_final"] == "aprobado"
    assert len(llamadas_router) == 1


def test_correccion_que_vuelve_a_fallar_queda_pendiente_otra_vez(saver, llamadas_router, entrada, contexto):
    grafo, pendiente = abrir_pendiente(saver, entrada, contexto, "correccion_insuficiente")

    otra_vez = resolver_revision(grafo, pendiente.thread_id, CORREGIR, contexto)

    assert otra_vez.estado["origen_intencion"] == "llm"
    assert otra_vez.nodos == ["revision_humana", "presupuestador", "evaluador", "preparar_revision"]
    assert otra_vez.pendiente and otra_vez.paquete["causa_escalada"] == "maximo_reintentos"
    assert otra_vez.estado["intentos"] == 4
    assert "resultado_final" not in otra_vez.estado
    assert situacion_caso(grafo, pendiente.thread_id) == "pendiente_revision"

    final = resolver_revision(grafo, pendiente.thread_id, APROBAR, contexto)
    assert final.estado["resultado_final"] == "aprobado"
    assert len(llamadas_router) == 1  # una sola vez en todo el caso, con dos pausas incluidas
    assert [n for p in historial_caso(grafo, pendiente.thread_id) for n in p.ejecutado].count("router") == 1


@pytest.mark.parametrize(
    "decision",
    [DECISIONES_INVALIDAS[k] for k in ("accion_desconocida", "corregir_sin_instruccion", "sin_revisor")],
    ids=["accion_desconocida", "corregir_sin_instruccion", "sin_revisor"],
)
def test_decision_invalida_se_rechaza_sin_modificar_el_hilo(saver, llamadas_router, entrada, contexto, decision):
    grafo, pendiente = abrir_pendiente(saver, entrada, contexto)
    historial_antes = historial_caso(grafo, pendiente.thread_id)

    with pytest.raises(DecisionInvalidaError, match="Decisión inválida"):
        resolver_revision(grafo, pendiente.thread_id, decision, contexto)

    assert historial_caso(grafo, pendiente.thread_id) == historial_antes
    assert situacion_caso(grafo, pendiente.thread_id) == "pendiente_revision"
    assert pendiente.estado["origen_intencion"] == "llm"


# --- Errores de situación -------------------------------------------------------------------------------


def test_resolver_un_caso_que_no_esta_pendiente_da_error(saver, llamadas_router, entrada, contexto):
    grafo = grafo_con(saver, "normal")
    cerrado = iniciar_caso(grafo, entrada, contexto)
    assert cerrado.estado["origen_intencion"] == "llm"
    with pytest.raises(KeyError):
        iniciar_caso(grafo, entrada, cargar_contexto(RUTA_SIN_PASTILLAS), thread_id="fallado")

    with pytest.raises(CasoNoPendienteDeRevisionError, match="cerrado"):
        resolver_revision(grafo, cerrado.thread_id, APROBAR, contexto)
    with pytest.raises(CasoNoPendienteDeRevisionError, match="fallado"):
        resolver_revision(grafo, "fallado", APROBAR, contexto)
    with pytest.raises(CasoInexistenteError):
        resolver_revision(grafo, "no-existe", APROBAR, contexto)


def test_un_caso_pendiente_no_se_retoma_ni_recibe_entrada_nueva(saver, llamadas_router, entrada, contexto):
    grafo, pendiente = abrir_pendiente(saver, entrada, contexto)

    with pytest.raises(CasoPendienteDeRevisionError, match="resolver_revision"):
        retomar_caso(grafo, pendiente.thread_id, contexto)
    with pytest.raises(CasoEnCursoError, match="resolver_revision"):
        iniciar_caso(grafo, entrada, contexto, thread_id=pendiente.thread_id)
    assert pendiente.estado["origen_intencion"] == "llm"


# --- Versión del contexto -------------------------------------------------------------------------------


def test_cambio_de_version_al_resolver_se_avisa_y_se_registra(saver, llamadas_router, entrada, contexto):
    grafo, pendiente = abrir_pendiente(saver, entrada, contexto)

    resuelto = resolver_revision(grafo, pendiente.thread_id, APROBAR, cargar_contexto(RUTA_EJEMPLO_V2))

    assert resuelto.estado["origen_intencion"] == "llm"
    assert "2026.10.1 -> 2026.11.0" in resuelto.aviso_version_contexto
    assert resuelto.estado["aviso_version_contexto"] == resuelto.aviso_version_contexto
    assert resuelto.estado["resultado_final"] == "aprobado"  # avisa, no bloquea


def test_misma_version_al_resolver_no_avisa(saver, llamadas_router, entrada, contexto):
    grafo, pendiente = abrir_pendiente(saver, entrada, contexto)

    resuelto = resolver_revision(grafo, pendiente.thread_id, APROBAR, contexto)

    assert resuelto.estado["origen_intencion"] == "llm"
    assert resuelto.aviso_version_contexto is None
    assert resuelto.estado["aviso_version_contexto"] is None


def test_cambio_de_version_antes_de_escalar_va_en_el_paquete(saver, llamadas_router, entrada):
    grafo = grafo_con(saver, "escalar")
    with pytest.raises(KeyError):  # empieza con 2026.10.1 y falla en el Presupuestador
        iniciar_caso(grafo, entrada, cargar_contexto(RUTA_SIN_PASTILLAS), thread_id="t")

    pendiente = retomar_caso(grafo, "t", cargar_contexto(RUTA_EJEMPLO_V2))  # se retoma con 2026.11.0 y escala

    assert pendiente.estado["origen_intencion"] == "llm"
    assert pendiente.pendiente
    assert "2026.10.1 -> 2026.11.0" in pendiente.paquete["aviso_version_contexto"]


# --- Bandeja --------------------------------------------------------------------------------------------


def test_casos_pendientes_lista_solo_los_pausados(saver, llamadas_router, entrada, contexto):
    _, primero = abrir_pendiente(saver, entrada, contexto, "maximo_reintentos")
    _, segundo = abrir_pendiente(saver, entrada, contexto, "escalar")
    cerrado = iniciar_caso(grafo_con(saver, "normal"), entrada, contexto)

    bandeja = dict(casos_pendientes(construir_grafo(checkpointer=saver)))

    assert cerrado.estado["origen_intencion"] == "llm"
    assert set(bandeja) == {primero.thread_id, segundo.thread_id}
    assert bandeja[primero.thread_id]["causa_escalada"] == "maximo_reintentos"
    assert bandeja[segundo.thread_id]["causa_escalada"] == "decision_evaluador"
