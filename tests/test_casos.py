"""Casos persistidos con checkpointer: historial, retome tras una falla, reglas de apertura y aislamiento."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from taller.casos import (
    DURABILIDAD,
    CasoCerradoError,
    CasoEnCursoError,
    CasoInexistenteError,
    CasoSinPendientesError,
    historial_caso,
    iniciar_caso,
    metadatos_caso,
    pendientes_caso,
    retomar_caso,
)
from taller.contexto import RUTA_SIN_PASTILLAS, cargar_contexto
from taller.escenarios import ESCENARIOS
from taller.grafo import construir_grafo


@pytest.fixture
def saver():
    return InMemorySaver()


@pytest.fixture
def contexto_sin_pastillas():
    return cargar_contexto(RUTA_SIN_PASTILLAS)


def grafo_con(saver, escenario="normal"):
    return construir_grafo(ESCENARIOS[escenario], checkpointer=saver)


def estado_guardado(grafo, thread_id):
    return grafo.get_state({"configurable": {"thread_id": thread_id}}).values


def ejecutados(historial) -> list[str]:
    return [nodo for paso in historial for nodo in paso.ejecutado if nodo != "__start__"]


def test_caso_se_consulta_desde_otra_ejecucion(tmp_path, llamadas_router, entrada, contexto):
    ruta = str(tmp_path / "casos.sqlite")
    with SqliteSaver.from_conn_string(ruta) as saver:
        ejecucion = iniciar_caso(grafo_con(saver), entrada, contexto)

    with SqliteSaver.from_conn_string(ruta) as otra_conexion:
        historial = historial_caso(construir_grafo(checkpointer=otra_conexion), ejecucion.thread_id)

    assert ejecucion.estado["origen_intencion"] == "llm"
    assert historial[-1].resultado_final == "aprobado"
    assert ejecutados(historial) == ejecucion.nodos


def test_historial_un_checkpoint_por_paso_con_las_tres_pasadas(saver, llamadas_router, entrada, contexto):
    grafo = grafo_con(saver, "maximo_reintentos")
    ejecucion = iniciar_caso(grafo, entrada, contexto)

    historial = historial_caso(grafo, ejecucion.thread_id)

    assert ejecucion.estado["origen_intencion"] == "llm"
    assert [p.paso for p in historial] == list(range(-1, len(historial) - 1))  # en orden, sin huecos
    assert ejecutados(historial) == ejecucion.nodos
    assert ejecutados(historial).count("presupuestador") == 3
    tras_evaluar = [p for p in historial if "evaluador" in p.ejecutado]
    assert [p.intentos for p in tras_evaluar] == [1, 2, 3]
    assert [[r["motivo"] for r in p.retroalimentaciones] for p in tras_evaluar] == [
        ["item_omitido"],
        ["item_omitido", "margen_incorrecto"],
        ["item_omitido", "margen_incorrecto", "item_duplicado"],
    ]
    # Escaló: el último checkpoint es la pausa en revision_humana, sin resultado final.
    assert all(p.resultado_final is None for p in historial)
    assert historial[-1].siguiente == ("revision_humana",)
    assert historial[-1].en_pausa and historial[-1].causa_escalada == "maximo_reintentos"


def test_falla_en_presupuestador_y_retome_sin_repetir_el_router(
    saver, llamadas_router, entrada, contexto, contexto_sin_pastillas
):
    grafo = grafo_con(saver)

    with pytest.raises(KeyError, match="FRE-PAS-DEL"):
        iniciar_caso(grafo, entrada, contexto_sin_pastillas, thread_id="caso-falla")

    # Guardado hasta el paso anterior a la falla: hay hipótesis, no hay presupuesto.
    assert pendientes_caso(grafo, "caso-falla") == ("presupuestador",)
    guardado = estado_guardado(grafo, "caso-falla")
    assert guardado["hipotesis"] and "presupuesto" not in guardado

    ejecucion = retomar_caso(grafo, "caso-falla", contexto)

    assert ejecucion.nodos[0] == "presupuestador"
    assert "router" not in ejecucion.nodos
    assert ejecucion.estado["origen_intencion"] == "llm"
    assert ejecucion.estado["resultado_final"] == "aprobado"
    assert len(llamadas_router) == 1
    assert ejecutados(historial_caso(grafo, "caso-falla")).count("router") == 1


def test_entrada_nueva_sobre_caso_cerrado_falla_y_no_modifica_el_hilo(saver, llamadas_router, entrada, contexto):
    grafo = grafo_con(saver)
    thread_id = iniciar_caso(grafo, entrada, contexto).thread_id
    historial_antes, estado_antes = historial_caso(grafo, thread_id), estado_guardado(grafo, thread_id)

    with pytest.raises(CasoCerradoError, match="cerrado"):
        iniciar_caso(grafo, {**entrada, "sintoma": "Otro problema"}, contexto, thread_id=thread_id)

    assert historial_caso(grafo, thread_id) == historial_antes
    assert estado_guardado(grafo, thread_id) == estado_antes
    assert estado_antes["origen_intencion"] == "llm"
    assert len(llamadas_router) == 1


def test_entrada_nueva_sobre_caso_en_curso_falla_y_no_modifica_el_hilo(
    saver, llamadas_router, entrada, contexto, contexto_sin_pastillas
):
    grafo = grafo_con(saver)
    with pytest.raises(KeyError):
        iniciar_caso(grafo, entrada, contexto_sin_pastillas, thread_id="caso-en-curso")
    historial_antes = historial_caso(grafo, "caso-en-curso")

    with pytest.raises(CasoEnCursoError, match="retomar"):
        iniciar_caso(grafo, entrada, contexto, thread_id="caso-en-curso")

    assert historial_caso(grafo, "caso-en-curso") == historial_antes
    assert len(llamadas_router) == 1


def test_retomar_un_caso_cerrado_o_inexistente_falla(saver, llamadas_router, entrada, contexto):
    grafo = grafo_con(saver)
    thread_id = iniciar_caso(grafo, entrada, contexto).thread_id

    with pytest.raises(CasoSinPendientesError, match="aprobado"):
        retomar_caso(grafo, thread_id, contexto)
    with pytest.raises(CasoInexistenteError):
        retomar_caso(grafo, "no-existe", contexto)
    with pytest.raises(CasoInexistenteError):
        historial_caso(grafo, "no-existe")


def test_dos_hilos_no_comparten_estado(saver, llamadas_router, entrada, contexto):
    normal = iniciar_caso(grafo_con(saver, "normal"), entrada, contexto)
    estado_normal = estado_guardado(grafo_con(saver), normal.thread_id)

    escalado = iniciar_caso(grafo_con(saver, "maximo_reintentos"), entrada, contexto)

    assert normal.thread_id != escalado.thread_id
    assert estado_guardado(grafo_con(saver), normal.thread_id) == estado_normal
    assert (estado_normal["intentos"], len(estado_normal["retroalimentaciones"])) == (1, 1)
    assert (escalado.estado["intentos"], len(escalado.estado["retroalimentaciones"])) == (3, 3)
    assert estado_normal["origen_intencion"] == escalado.estado["origen_intencion"] == "llm"


def test_el_escenario_se_guarda_en_los_metadatos_y_sobrevive_al_retome(
    saver, llamadas_router, entrada, contexto, contexto_sin_pastillas
):
    grafo = grafo_con(saver, "motivo_repetido")
    with pytest.raises(KeyError):
        iniciar_caso(grafo, entrada, contexto_sin_pastillas, thread_id="t", metadatos={"escenario": "motivo_repetido"})
    esperados = {"escenario": "motivo_repetido", "version_contexto": contexto_sin_pastillas.version}
    assert metadatos_caso(grafo, "t") == esperados

    ejecucion = retomar_caso(grafo, "t", contexto)

    assert ejecucion.estado["origen_intencion"] == "llm"
    assert ejecucion.estado["causa_escalada"] == "motivo_repetido"
    assert metadatos_caso(grafo, "t") == esperados


def test_tenant_context_no_aparece_en_los_checkpoints(
    tmp_path, llamadas_router, entrada, contexto, contexto_sin_pastillas
):
    ruta = tmp_path / "casos.sqlite"
    with SqliteSaver.from_conn_string(str(ruta)) as saver:
        grafo = grafo_con(saver)
        normal = iniciar_caso(grafo, entrada, contexto)
        with pytest.raises(KeyError):
            iniciar_caso(grafo, entrada, contexto_sin_pastillas, thread_id="t-falla")
        retomar_caso(grafo, "t-falla", contexto)
    crudo = b"".join(archivo.read_bytes() for archivo in tmp_path.glob("casos.sqlite*"))

    assert normal.estado["origen_intencion"] == "llm"
    assert b"item_omitido" in crudo  # control: el estado sí está en la base y la búsqueda funciona
    for solo_en_el_contexto in ("FRE-DIS-DEL", "LUB-ACE-5W30", "Aceite sint", "margenes", "lubricantes"):
        assert solo_en_el_contexto.encode() not in crudo


def test_los_casos_se_guardan_con_durabilidad_sync(monkeypatch, saver, llamadas_router, entrada, contexto):
    grafo = grafo_con(saver)
    durabilidades, stream_original = [], grafo.stream

    def espia(*args, **kwargs):
        durabilidades.append(kwargs.get("durability"))
        return stream_original(*args, **kwargs)

    monkeypatch.setattr(grafo, "stream", espia)
    ejecucion = iniciar_caso(grafo, entrada, contexto)

    assert ejecucion.estado["origen_intencion"] == "llm"
    assert durabilidades == [DURABILIDAD] == ["sync"]
